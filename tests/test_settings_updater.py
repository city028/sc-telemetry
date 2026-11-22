from app import settings, updater


def test_settings_defaults_roundtrip_and_damage(tmp_path):
    path = tmp_path / "settings.json"
    assert settings.load(path) == settings.DEFAULTS
    data = settings.load(path)
    data.update(on_top=True, game_dir="D:\\SC", junk=1)
    settings.save(data, path)
    assert settings.load(path) == {**settings.DEFAULTS, "on_top": True, "game_dir": "D:\\SC"}
    path.write_text("{not json")
    assert settings.load(path) == settings.DEFAULTS


def test_versions():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.is_newer("v0.2.0", "0.1.0")
    assert not updater.is_newer("v0.1.0", "0.1.0")
    assert not updater.is_newer("junk", "0.1.0")


def test_release_needs_installer_and_checksum():
    base = {"tag_name": "v9.0.0", "published_at": "2026-12-01T00:00:00Z", "body": "notes"}
    asset = {"name": updater.ASSET_NAME, "browser_download_url": "https://x/setup.exe", "size": 10}
    assert not updater.read_release({**base, "assets": [asset]})["available"]
    info = updater.read_release({**base, "assets": [{**asset, "digest": "sha256:ab"}]})
    assert info["available"] and info["sha256"] == "ab" and info["latest"] == "9.0.0"
