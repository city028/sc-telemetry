"""Talks to Star Citizen's local telemetry API: gRPC on 127.0.0.1:2942.

The game only runs it with `server.game.telemetry.enabled = 1` in user.cfg.
Message types come from the descriptors extracted from StarCitizen.exe
(proto/*.desc), so no generated code is needed. Nothing here touches a window.
"""
import logging
import threading
from pathlib import Path

import grpc
from google.protobuf import descriptor_pool, json_format, message_factory

TARGET = "127.0.0.1:2942"
PKG = "sc.game.telemetry.v1."
SERVICE = "/sc.game.telemetry.v1.GameTelemetryService/"
STATUS_PREFIX = "TRIGGER_GAME_ACTION_STATUS_"
RETRY_S = 2.0
CALL_TIMEOUT_S = 3.0

log = logging.getLogger(__name__)


class Schema:
    """The API's message classes, built from the extracted descriptors."""

    def __init__(self, proto_dir):
        pool = descriptor_pool.DescriptorPool()
        for name in ("types.proto.desc", "api.proto.desc"):
            pool.AddSerializedFile((Path(proto_dir) / name).read_bytes())
        cls = lambda n: message_factory.GetMessageClass(pool.FindMessageTypeByName(PKG + n))
        self.StreamRequest = cls("TelemetryStreamRequest")
        self.StreamResponse = cls("TelemetryStreamResponse")
        self.TriggerRequest = cls("TriggerGameActionRequest")
        self.TriggerResponse = cls("TriggerGameActionResponse")
        self.ListRequest = cls("ListTriggerableActionsRequest")
        self.ListResponse = cls("ListTriggerableActionsResponse")


def to_dict(msg):
    """A message as plain data: proto field names, enums as their names.
    Fields at their default (0, false, empty) are left out, as on the wire."""
    return json_format.MessageToDict(msg, preserving_proto_field_name=True)


class FrameBatcher:
    """Collects stream frames between pushes to the window: the newest of
    each section, and every event (events are never dropped)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latest, self._events = {}, []

    def add(self, frame):
        with self._lock:
            for key, value in frame.items():
                if key == "events":
                    self._events.extend(value.get("events", []))
                else:
                    self._latest[key] = value

    def take(self):
        """Everything collected since the last take, or None."""
        with self._lock:
            if not self._latest and not self._events:
                return None
            out = dict(self._latest)
            if self._events:
                out["events"] = {"events": self._events}
            self._latest, self._events = {}, []
            return out


class GameClient:
    """Keeps a TelemetryStream open, reconnecting every RETRY_S seconds, and
    makes the one-off action calls. on_frame(dict) gets each stream message;
    on_status(bool) gets connected / disconnected changes. Both are called
    from the stream thread."""

    def __init__(self, schema, on_frame, on_status, target=TARGET, retry=RETRY_S):
        self.schema, self.on_frame, self.on_status = schema, on_frame, on_status
        self.target, self.retry = target, retry
        self.connected = False
        self._stop = threading.Event()
        self._call = None
        self._thread = None
        self._actions_channel = None

    # ---- stream ----
    def start(self):
        self._thread = threading.Thread(target=self._run, name="telemetry", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._call:
            self._call.cancel()
        if self._actions_channel:
            self._actions_channel.close()
        if self._thread:
            self._thread.join(timeout=5)

    def _set_connected(self, value):
        if value != self.connected:
            self.connected = value
            self.on_status(value)

    def _run(self):
        while not self._stop.is_set():
            channel = grpc.insecure_channel(self.target)
            try:
                grpc.channel_ready_future(channel).result(timeout=self.retry)
                stream = channel.unary_stream(
                    SERVICE + "TelemetryStream",
                    request_serializer=self.schema.StreamRequest.SerializeToString,
                    response_deserializer=self.schema.StreamResponse.FromString)
                self._call = stream(self.schema.StreamRequest())
                self._set_connected(True)
                for msg in self._call:
                    self.on_frame(to_dict(msg))
            except grpc.FutureTimeoutError:
                pass                                    # game or API not up yet
            except grpc.RpcError as exc:
                if not self._stop.is_set():
                    log.info("stream ended: %s", exc.code().name)
            except Exception:
                log.exception("stream failed")
            finally:
                self._call = None
                channel.close()
                self._set_connected(False)
            self._stop.wait(self.retry)

    # ---- one-off calls ----
    def _unary(self, method, request, response_cls, timeout):
        if self._actions_channel is None:
            self._actions_channel = grpc.insecure_channel(self.target)
        call = self._actions_channel.unary_unary(
            SERVICE + method,
            request_serializer=type(request).SerializeToString,
            response_deserializer=response_cls.FromString)
        return call(request, timeout=timeout)

    def list_actions(self, timeout=CALL_TIMEOUT_S):
        """[{action_name, category, holdable?}, ...]; [] if unreachable."""
        try:
            resp = self._unary("ListTriggerableActions", self.schema.ListRequest(),
                               self.schema.ListResponse, timeout)
        except grpc.RpcError as exc:
            log.info("list_actions: %s", exc.code().name)
            return []
        return to_dict(resp).get("actions", [])

    def trigger(self, action, hold_ms=None, timeout=CALL_TIMEOUT_S):
        """{"status": "OK" | "UNKNOWN_ACTION" | ... | "UNREACHABLE", "message": str}"""
        req = self.schema.TriggerRequest(action_name=action)
        if hold_ms:
            req.hold_ms = int(hold_ms)
        try:
            resp = self._unary("TriggerGameAction", req, self.schema.TriggerResponse, timeout)
        except grpc.RpcError as exc:
            return {"status": "UNREACHABLE", "message": exc.code().name}
        data = to_dict(resp)
        status = data.get("status", STATUS_PREFIX + "UNSPECIFIED")
        return {"status": status.removeprefix(STATUS_PREFIX), "message": data.get("message", "")}
