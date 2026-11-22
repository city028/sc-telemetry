"""What the page can call: window.pywebview.api.<method>(...).

pywebview exposes every public attribute, so state lives in _underscored
attributes. Each method is thin: the work is in telemetry, gamecfg, settings
and updater. Return values must be JSON-serialisable.
"""
import logging
import webbrowser
from pathlib import Path

from app import gamecfg, settings, updater

log = logging.getLogger(__name__)


class Api:
    def __init__(self, client, prefs, on_ready):
        self._client = client
        self._prefs = prefs
        self._on_ready = on_ready
        self._window = None
        self._update = None

    def _bind(self, window):
        self._window = window

    def _js(self, code):
        if self._window:
            self._window.evaluate_js(code)

    # ---- start-up ----
    def get_init(self):
        return {"version": updater.VERSION, "settings": self._prefs,
                "game": self.game_info(), "actions": self._client.list_actions()}

    def ready(self):
        """The page has its handlers in place: start streaming to it."""
        self._on_ready()

    # ---- game ----
    def game_info(self):
        root = gamecfg.find_root(self._prefs.get("game_dir"))
        return {"root": str(root) if root else None,
                "channels": gamecfg.status(root) if root else []}

    def list_actions(self):
        return self._client.list_actions()

    def trigger(self, action, hold_ms=None):
        return self._client.trigger(str(action), hold_ms)

    def enable_telemetry(self, channel):
        root = gamecfg.find_root(self._prefs.get("game_dir"))
        if not root or channel not in gamecfg.channels(root):
            return {"ok": False, "error": f"{channel} not found", "game": self.game_info()}
        try:
            changed = gamecfg.enable_telemetry(root / channel)
        except OSError as exc:
            log.warning("enable_telemetry %s: %s", channel, exc)
            return {"ok": False, "error": f"Could not write {root / channel / 'user.cfg'}: {exc.strerror or exc}",
                    "game": self.game_info()}
        return {"ok": True, "changed": changed, "game": self.game_info()}

    def pick_game_folder(self):
        dialog = getattr(getattr(self._window_module(), "FileDialog", None), "FOLDER", None)
        chosen = self._window.create_file_dialog(dialog) if self._window else None
        if not chosen:
            return {"ok": False, "game": self.game_info()}
        path = Path(chosen[0])
        if not gamecfg.is_root(path):
            return {"ok": False, "error": f"No LIVE or PTU folder in {path}", "game": self.game_info()}
        self.set_setting("game_dir", str(path))
        return {"ok": True, "game": self.game_info()}

    @staticmethod
    def _window_module():
        import webview
        return webview

    # ---- settings ----
    def set_setting(self, key, value):
        if key not in settings.DEFAULTS:
            return False
        self._prefs[key] = value
        settings.save(self._prefs)
        if key == "on_top" and self._window:
            self._window.on_top = bool(value)
        return True

    # ---- updates ----
    def check_update(self):
        self._update = updater.check()
        return self._update

    def install_update(self):
        info = self._update
        if not info or not info.get("available"):
            return {"ok": False, "error": "No update to install"}
        if not updater.can_install():
            webbrowser.open(updater.RELEASE_PAGE)
            return {"ok": True, "opened": True}
        try:
            setup = updater.download(info, settings.APP_DIR / "update" / updater.ASSET_NAME,
                                     progress=lambda p: self._js(f"window.onUpdateProgress({p:.3f})"))
        except Exception as exc:
            log.warning("update download failed: %s", exc)
            return {"ok": False, "error": str(exc)}
        updater.start_install(setup)
        self._window.destroy()        # the installer waits for this program to close
        return {"ok": True}

    def open_release_page(self):
        webbrowser.open(updater.RELEASE_PAGE)
