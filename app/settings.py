"""The app's settings, in %LocalAppData%\\SC Telemetry\\settings.json.
Kept out of the install folder so updates and reinstalls never touch them."""
import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "SC Telemetry"
PATH = APP_DIR / "settings.json"
DEFAULTS = {
    "game_dir": None,           # StarCitizen folder; None = look in the usual places
    "confirm_danger": True,     # eject / self-destruct need a 1.5 s hold
    "on_top": False,            # keep the window above the game
    "check_updates": True,      # look for a new release at start
}


def load(path=PATH):
    """DEFAULTS overlaid with what is saved; unknown keys are dropped and a
    damaged file is ignored."""
    data = dict(DEFAULTS)
    try:
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        data.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError, AttributeError):
        pass
    return data


def save(data, path=PATH):
    """Write atomically: a crash mid-write leaves the old file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({k: data.get(k) for k in DEFAULTS}, indent=2), encoding="utf-8")
    tmp.replace(path)
