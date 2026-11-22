"""Entry point: one window showing ui/index.html, fed by the telemetry stream."""
import ctypes
import json
import logging
import sys
import threading
import time
from pathlib import Path

import webview

from app import settings, telemetry, updater
from app.api import Api

MUTEX_NAME = "Local\\sc-telemetry"      # installer/sc-telemetry.iss waits on this
PUSH_INTERVAL_S = 0.05                  # at most 20 window updates per second
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))

log = logging.getLogger("sc-telemetry")


def single_instance():
    """Hold the app's mutex; False if another copy already has it."""
    if sys.platform != "win32":
        return True
    single_instance.handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != 183      # ERROR_ALREADY_EXISTS


def setup_logging():
    settings.APP_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=settings.APP_DIR / "sc-telemetry.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: log.critical("unhandled", exc_info=exc)


def main():
    setup_logging()
    if not single_instance():
        log.info("already running")
        return
    log.info("start %s", updater.VERSION)
    prefs = settings.load()
    batcher = telemetry.FrameBatcher()
    window = None
    started = threading.Event()

    def js(code):
        try:
            window.evaluate_js(code)
        except Exception:
            log.debug("evaluate_js failed", exc_info=True)

    def on_status(connected):
        log.info("game %s", "connected" if connected else "disconnected")
        batcher.take()                                     # drop frames from the old session
        js(f"window.onStatus({json.dumps({'connected': connected})})")

    client = telemetry.GameClient(telemetry.Schema(HERE / "proto"), batcher.add, on_status)

    def push_loop():
        while window is not None:
            frame = batcher.take()
            if frame:
                js(f"window.onFrame({json.dumps(frame)})")
            time.sleep(PUSH_INTERVAL_S)

    def on_ready():
        """Called by the page once its handlers exist; runs once."""
        if started.is_set():
            return
        started.set()
        client.start()
        threading.Thread(target=push_loop, name="push", daemon=True).start()
        if prefs.get("check_updates"):
            threading.Thread(target=lambda: js(f"window.onUpdate({json.dumps(api.check_update())})"),
                             name="update-check", daemon=True).start()

    api = Api(client, prefs, on_ready)
    window = webview.create_window(
        "SC Telemetry", str(HERE / "ui" / "index.html"), js_api=api,
        width=1440, height=900, min_size=(1000, 640), background_color="#0b0f14",
        on_top=bool(prefs.get("on_top")))
    api._bind(window)
    webview.start(private_mode=False, storage_path=str(settings.APP_DIR / "webview"))
    window = None
    client.stop()
    log.info("exit")


if __name__ == "__main__":
    main()
