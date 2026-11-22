"""Where Star Citizen is installed, and whether telemetry is on in user.cfg.

The game reads `server.game.telemetry.enabled = 1` from user.cfg only at
startup, so enabling it here takes effect at the next game start.
"""
import re
import shutil
import string
from datetime import datetime
from pathlib import Path

CHANNELS = ("LIVE", "PTU", "EPTU", "TECH-PREVIEW", "HOTFIX")
LINE = "server.game.telemetry.enabled = 1"
_SETTING = re.compile(r"^\s*server\.game\.telemetry\.enabled\b\s*=?\s*(\S*)", re.IGNORECASE)
_SUBPATHS = (r"Program Files\Roberts Space Industries\StarCitizen",
             r"Roberts Space Industries\StarCitizen",
             r"Games\Roberts Space Industries\StarCitizen",
             r"StarCitizen")


def is_channel(path):
    path = Path(path)
    return (path / "Bin64" / "StarCitizen.exe").exists() or (path / "Game.log").exists()


def is_root(path):
    """Is this the StarCitizen folder that holds LIVE, PTU, ...?"""
    return bool(path) and any(is_channel(Path(path) / ch) for ch in CHANNELS)


def candidates(drives=None):
    """Usual install folders on every drive letter."""
    drives = drives if drives is not None else [f"{d}:\\" for d in string.ascii_uppercase]
    for drive in drives:
        for sub in _SUBPATHS:
            yield Path(drive) / sub


def find_root(configured=None, drives=None):
    """The configured folder if it is a game folder, else the first usual one found."""
    if configured and is_root(configured):
        return Path(configured)
    for path in candidates(drives):
        try:
            if is_root(path):
                return path
        except OSError:                 # drive not ready (card reader, DVD)
            continue
    return None


def channels(root):
    return [ch for ch in CHANNELS if is_channel(Path(root) / ch)]


def _read(cfg):
    return cfg.read_text(encoding="utf-8", errors="surrogateescape") if cfg.exists() else ""


def telemetry_enabled(channel_dir):
    """True when the last telemetry line in user.cfg sets it to 1 or true."""
    value = None
    for line in _read(Path(channel_dir) / "user.cfg").splitlines():
        m = _SETTING.match(line)
        if m:
            value = m.group(1).lower()
    return value in ("1", "true")


def enable_telemetry(channel_dir, now=None):
    """Turn telemetry on in this channel's user.cfg. Any existing user.cfg is
    copied to user.cfg.<timestamp>.bak first. Returns False if it was already on.
    Raises OSError if the file cannot be written."""
    cfg = Path(channel_dir) / "user.cfg"
    if telemetry_enabled(channel_dir):
        return False
    text = _read(cfg)
    if cfg.exists():
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        shutil.copy2(cfg, cfg.with_name(f"user.cfg.{stamp}.bak"))
    lines = text.splitlines()
    if any(_SETTING.match(line) for line in lines):
        lines = [LINE if _SETTING.match(line) else line for line in lines]
    else:
        lines.append(LINE)
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="surrogateescape")
    return True


def status(root):
    """[{"channel": "LIVE", "enabled": bool}, ...] for each installed channel."""
    return [{"channel": ch, "enabled": telemetry_enabled(Path(root) / ch)} for ch in channels(root)]
