"""GameClient against an in-process fake of the game's gRPC service."""
import time
from concurrent import futures
from pathlib import Path

import grpc
import pytest

from app.telemetry import FrameBatcher, GameClient, Schema, to_dict

PROTO = Path(__file__).resolve().parent.parent / "proto"


@pytest.fixture(scope="module")
def schema():
    return Schema(PROTO)


def frame(schema, health=99.5, event_type=None):
    msg = schema.StreamResponse()
    msg.actor.vitals.health.current = health
    msg.actor.vitals.health.max = 100
    msg.actor.state.locomotion = 1               # ON_FOOT
    msg.actor.state.uec_balance = 1234
    if event_type:
        msg.events.events.add(type=event_type)
    return msg


@pytest.fixture
def game(schema):
    """A fake game on a free port: streams two frames, knows one action."""
    def stream(req, ctx):
        yield frame(schema)
        yield frame(schema, 50.0, event_type=3)  # ACTOR_ENTER_SEAT
        time.sleep(0.2)

    def trigger(req, ctx):
        resp = schema.TriggerResponse()
        resp.status = 1 if req.action_name == "toggle_flashlight" else 2    # OK / UNKNOWN_ACTION
        if req.HasField("hold_ms"):
            resp.message = f"held {req.hold_ms}"
        return resp

    def list_actions(req, ctx):
        resp = schema.ListResponse()
        resp.actions.add(action_name="toggle_flashlight", category="player")
        resp.actions.add(action_name="v_invoke_ping", category="spaceship_radar", holdable=True)
        return resp

    S = schema
    handler = grpc.method_handlers_generic_handler("sc.game.telemetry.v1.GameTelemetryService", {
        "TelemetryStream": grpc.unary_stream_rpc_method_handler(
            stream, S.StreamRequest.FromString, S.StreamResponse.SerializeToString),
        "TriggerGameAction": grpc.unary_unary_rpc_method_handler(
            trigger, S.TriggerRequest.FromString, S.TriggerResponse.SerializeToString),
        "ListTriggerableActions": grpc.unary_unary_rpc_method_handler(
            list_actions, S.ListRequest.FromString, S.ListResponse.SerializeToString),
    })
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    server.add_generic_rpc_handlers((handler,))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield f"127.0.0.1:{port}"
    server.stop(None)


def wait_for(cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_to_dict_uses_field_and_enum_names(schema):
    d = to_dict(frame(schema, event_type=6))
    assert d["actor"]["vitals"]["health"] == {"current": 99.5, "max": 100.0}
    assert d["actor"]["state"]["locomotion"] == "ACTOR_LOCOMOTION_STATE_ON_FOOT"
    assert d["actor"]["state"]["uec_balance"] == "1234"          # int64 comes as a string
    assert d["events"]["events"] == [{"type": "GAME_EVENT_TYPE_ACTOR_DOWNED"}]


def test_stream_delivers_frames_and_status(schema, game):
    frames, statuses = [], []
    client = GameClient(schema, frames.append, statuses.append, target=game, retry=0.2)
    client.start()
    try:
        assert wait_for(lambda: len(frames) >= 2)
        assert statuses[0] is True
        assert frames[1]["actor"]["vitals"]["health"]["current"] == 50.0
        assert frames[1]["events"]["events"][0]["type"] == "GAME_EVENT_TYPE_ACTOR_ENTER_SEAT"
    finally:
        client.stop()
    assert statuses[-1] is False


def test_stream_reconnects_after_the_game_ends_it(schema, game):
    frames = []
    client = GameClient(schema, frames.append, lambda s: None, target=game, retry=0.1)
    client.start()
    try:
        assert wait_for(lambda: len(frames) >= 4)      # 2 frames per stream: it came back
    finally:
        client.stop()


def test_no_game_means_not_connected(schema):
    statuses = []
    client = GameClient(schema, lambda f: None, statuses.append, target="127.0.0.1:1", retry=0.1)
    client.start()
    time.sleep(0.5)
    client.stop()
    assert statuses == []


def test_trigger_statuses(schema, game):
    client = GameClient(schema, None, None, target=game)
    try:
        assert client.trigger("toggle_flashlight") == {"status": "OK", "message": ""}
        assert client.trigger("nope")["status"] == "UNKNOWN_ACTION"
        assert client.trigger("v_invoke_ping", 500)["message"] == "held 500"
    finally:
        client.stop()


def test_trigger_unreachable(schema):
    client = GameClient(schema, None, None, target="127.0.0.1:1")
    assert client.trigger("toggle_flashlight", timeout=0.5)["status"] == "UNREACHABLE"
    assert client.list_actions(timeout=0.5) == []
    client.stop()


def test_list_actions(schema, game):
    client = GameClient(schema, None, None, target=game)
    try:
        actions = client.list_actions()
    finally:
        client.stop()
    assert actions == [{"action_name": "toggle_flashlight", "category": "player"},
                       {"action_name": "v_invoke_ping", "category": "spaceship_radar", "holdable": True}]


def test_batcher_keeps_newest_sections_and_all_events():
    b = FrameBatcher()
    assert b.take() is None
    b.add({"actor": {"x": 1}, "events": {"events": [{"type": "A"}]}})
    b.add({"actor": {"x": 2}, "vehicle": {"y": 1}})
    b.add({"events": {"events": [{"type": "B"}]}})
    assert b.take() == {"actor": {"x": 2}, "vehicle": {"y": 1}, "events": {"events": [{"type": "A"}, {"type": "B"}]}}
    assert b.take() is None
