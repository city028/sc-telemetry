from datetime import datetime

from app import gamecfg


def make_game(base, *chans):
    root = base / "StarCitizen"
    for ch in chans:
        (root / ch / "Bin64").mkdir(parents=True)
        (root / ch / "Bin64" / "StarCitizen.exe").write_bytes(b"")
    return root


def test_find_root_configured_and_usual_places(tmp_path):
    root = make_game(tmp_path, "LIVE", "PTU")
    assert gamecfg.find_root(str(root), drives=[]) == root
    assert gamecfg.find_root(None, drives=[str(tmp_path)]) == root
    assert gamecfg.find_root(str(tmp_path / "nope"), drives=[]) is None


def test_channels_in_fixed_order(tmp_path):
    root = make_game(tmp_path, "PTU", "LIVE")
    assert gamecfg.channels(root) == ["LIVE", "PTU"]


def test_enabled_reads_the_last_setting(tmp_path):
    ch = make_game(tmp_path, "PTU") / "PTU"
    assert not gamecfg.telemetry_enabled(ch)
    (ch / "user.cfg").write_text("r_DisplayInfo = 2\nserver.game.telemetry.enabled = 1\n")
    assert gamecfg.telemetry_enabled(ch)
    (ch / "user.cfg").write_text("server.game.telemetry.enabled 1\nserver.game.telemetry.enabled=0\n")
    assert not gamecfg.telemetry_enabled(ch)
    (ch / "user.cfg").write_text("SERVER.GAME.TELEMETRY.ENABLED = true\n")
    assert gamecfg.telemetry_enabled(ch)


def test_enable_creates_user_cfg(tmp_path):
    ch = make_game(tmp_path, "LIVE") / "LIVE"
    assert gamecfg.enable_telemetry(ch)
    assert (ch / "user.cfg").read_text() == gamecfg.LINE + "\n"
    assert not list(ch.glob("*.bak"))


def test_enable_appends_keeps_other_lines_and_backs_up(tmp_path):
    ch = make_game(tmp_path, "LIVE") / "LIVE"
    (ch / "user.cfg").write_text("r_DisplayInfo = 2")
    assert gamecfg.enable_telemetry(ch, now=datetime(2026, 11, 22, 12, 0, 0))
    assert (ch / "user.cfg").read_text() == "r_DisplayInfo = 2\n" + gamecfg.LINE + "\n"
    assert (ch / "user.cfg.20261122-120000.bak").read_text() == "r_DisplayInfo = 2"


def test_enable_replaces_an_off_setting_and_is_idempotent(tmp_path):
    ch = make_game(tmp_path, "PTU") / "PTU"
    (ch / "user.cfg").write_text("a = 1\nserver.game.telemetry.enabled = 0\nb = 2\n")
    assert gamecfg.enable_telemetry(ch)
    assert (ch / "user.cfg").read_text() == "a = 1\n" + gamecfg.LINE + "\nb = 2\n"
    assert not gamecfg.enable_telemetry(ch)
    assert (ch / "user.cfg").read_text().count("telemetry") == 1


def test_status(tmp_path):
    root = make_game(tmp_path, "LIVE", "PTU")
    gamecfg.enable_telemetry(root / "PTU")
    assert gamecfg.status(root) == [{"channel": "LIVE", "enabled": False}, {"channel": "PTU", "enabled": True}]
