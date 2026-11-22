# SC Telemetry

A companion app for Star Citizen. It shows your character's and ship's live state and has buttons to control them, using the game's own local telemetry API.

> Unofficial. Not affiliated with or endorsed by Cloud Imperium Games. The API was found in a PTU build (13248297, November 2026) and may change or disappear.

## What it does

- **Live telemetry**, about 19 updates a second:
  - **Character:** health, oxygen, hunger, thirst, body temperature, heart rate, aUEC balance
  - **Environment**
  - **Ship:** health, shields per face, power, the 10 warning lights, doors, master mode
  - **Flight instruments:** speed, altitude, heading, fuel, G-meter, boost, gear, VTOL
  - **Flight assist** status
  - **Weapons:** each weapon's state, countermeasures
  - **Force feedback**
  - **Event log:** spawn, death, seat changes
- **Controls:** buttons for the actions the game exposes (112 in the tested build):
  - mobiGlas, flashlight, lights, doors, power
  - landing gear, VTOL, decoupled, G-safe, NAV/SCM, operator modes
  - quantum drive, radar ping, ATC, docking, hailing, emotes
  - a search box over all of them
  - Buttons light up when that function is on. Eject, emergency exit and self-destruct must be held for 1.5 s.
- **One-click setup:** the app turns the API on in the game's `user.cfg` for LIVE or PTU and keeps a backup.
- **Updates itself** from GitHub Releases, checking the installer's SHA-256 checksum before running it.

## Install

1. Download `sc-telemetry-setup.exe` from the [latest release](https://github.com/city028/sc-telemetry/releases/latest) and run it. It installs for your user only, with no admin prompt. Windows SmartScreen may warn about an unknown publisher, because the installer is not code-signed.
2. Start **SC Telemetry**. If it says *telemetry off*, click **Enable for LIVE** (or PTU).
3. Start, or restart, Star Citizen. The app connects by itself.

To turn the API on by hand, add this line to `StarCitizen\LIVE\user.cfg` (or `PTU\user.cfg`) and restart the game:

```
server.game.telemetry.enabled = 1
```

Settings and the log are in `%LocalAppData%\SC Telemetry`.

## How it works

With the setting on, the game runs a gRPC server on `127.0.0.1:2942`: unencrypted, no authentication, reachable only from the same PC. The service is `sc.game.telemetry.v1.GameTelemetryService`, with three methods:

| Method | Does |
| --- | --- |
| `TelemetryStream` | Streams game-state frames |
| `ListTriggerableActions` | Lists action names, categories, and whether each can be held |
| `TriggerGameAction` | Performs an action, optionally held for `hold_ms` |

The schema in [`proto/`](proto/) was decoded from the definitions built into `StarCitizen.exe`. The full write-up is in [DOCS/Star Citizen Local Telemetry API.md](DOCS/Star%20Citizen%20Local%20Telemetry%20API.md).

While the API is on, **any program on your PC** can read this data and trigger actions, including self-destruct.

## Build from source

Needs Python 3.12+ and [Inno Setup](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

```
pip install -r requirements.txt
python -m app                 # run from source
python -m pytest              # tests
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1    # dist\sc-telemetry-setup.exe
```

To release: bump `VERSION` in `app/updater.py`, run `build.ps1`, then create a GitHub release tagged `vX.Y.Z` with `dist\sc-telemetry-setup.exe` attached. Installed copies offer it as an update.

## Layout

| Path | What |
| --- | --- |
| `app/` | The program: `main.py` (window), `api.py` (calls from the page), `telemetry.py` (gRPC client), `gamecfg.py` (game folder and `user.cfg`), `settings.py`, `updater.py` |
| `ui/index.html` | The window's page |
| `proto/` | API schema: `.proto` text and the raw descriptors the app loads |
| `tests/` | pytest, including a fake game server |
| `installer/`, `sc_telemetry.spec`, `build.ps1` | Packaging |
| `tools/` | Node.js tools used to find the API: command-line client, browser dashboard, descriptor extraction |
| `design/mockup.html` | Clickable design mockup on made-up data |
| `DOCS/` | Findings write-up and the implementation plan |

## License

MIT, see [LICENSE](LICENSE).
