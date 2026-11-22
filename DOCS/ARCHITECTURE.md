# Architecture

SC Telemetry is a Python desktop app: a pywebview (Edge WebView2) window showing `ui/index.html`, fed by Star Citizen's local gRPC telemetry API.

```
StarCitizen.exe ──gRPC 127.0.0.1:2942──► app/telemetry.py  GameClient (stream thread, reconnects every 2 s)
                ◄── TriggerGameAction ──        │ on_frame → FrameBatcher (newest per section + all events)
                                                ▼
                         app/main.py  push loop, ≤ 20/s ──evaluate_js──► ui/index.html
                                                                          │ window.pywebview.api.*
                         app/api.py   (thin)  ◄───────────────────────────┘
                           ├─ app/gamecfg.py   find game folder, channels, enable telemetry in user.cfg
                           ├─ app/settings.py  %LocalAppData%\SC Telemetry\settings.json
                           └─ app/updater.py   GitHub latest release, SHA-256 check, silent install
```

## Modules

| File | Role |
| --- | --- |
| `app/main.py` | Entry point: logging, single-instance mutex `Local\sc-telemetry`, window, push loop |
| `app/api.py` | Methods the page calls; no logic of its own |
| `app/telemetry.py` | `Schema` (from `proto/*.desc`), `GameClient` (stream, `list_actions`, `trigger`), `FrameBatcher` |
| `app/gamecfg.py` | Install detection, channel list, `user.cfg` read/enable with timestamped backup |
| `app/settings.py` | Settings with defaults, atomic save |
| `app/updater.py` | Copied from SC Locator; `VERSION` is the release version |
| `ui/index.html` | Panels, controls, dialogs; receives `onFrame`, `onStatus`, `onUpdate`, `onUpdateProgress` |

## Packaging and release

- `sc_telemetry.spec`: PyInstaller in folder mode, no console. Bundles `ui/`, `proto/*.desc` and `icon.ico`.
- `installer/sc-telemetry.iss`: Inno Setup, per-user. Fixed `AppId` `8DF1A568-6CF6-457C-A91D-1387810A4525`, which must never change. Waits on the app mutex during silent updates.
- `build.ps1`: tests → PyInstaller → installer → `dist\sc-telemetry-setup.exe`.
- Release: bump `VERSION` in `app/updater.py`, build, `gh release create vX.Y.Z dist\sc-telemetry-setup.exe`.

## Other folders

- `tools/`: Node.js tools used for discovery (CLI client, browser dashboard, descriptor extraction).
- `proto/`: recovered `.proto` text and raw descriptors.
- `design/mockup.html`: design reference on made-up data.
- `tests/`: pytest; `test_telemetry.py` runs a fake game server.
