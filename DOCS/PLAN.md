# SC Telemetry: implementation plan

A Windows app that shows Star Citizen's live telemetry and has buttons to control the character and ship. It installs, uninstalls and updates itself the same way SC Locator does.

Design: [design/mockup.html](../design/mockup.html). It runs on made-up data. Serve the repo root and open `/design/mockup.html`. The purple **MOCKUP** bar switches between states: game connected / not running / telemetry off, on foot / in a ship, and update available.

## 1. Decisions

| Topic | Recommendation | Why | Alternative |
| --- | --- | --- | --- |
| Language / UI | Python 3 + **pywebview** (an Edge WebView2 window) showing the HTML page | Reuses the dashboard and mockup HTML as-is. Same toolchain as SC Locator (Python, PyInstaller, Inno Setup). WebView2 ships with Windows 11. | Electron: reuses the Node tools, but installs at about 150 MB and needs a new toolchain and updater. Tauri: small, but needs Rust. |
| gRPC client | **grpcio**, with classes generated from `proto/*.proto` by `grpcio-tools` at build time | The official library: handles HTTP/2, streaming and reconnects | Port the hand-written Node decoder to Python: no dependency, but more code to maintain |
| Page ↔ Python | pywebview `js_api` for button presses; Python pushes frames to the page with `evaluate_js`, at most 20 per second | No local web server, no open port | A local HTTP/SSE server, like `tools/dashboard.js` |
| Packaging | PyInstaller in folder mode + an Inno Setup per-user installer (no admin prompt) | Exactly as SC Locator does it | — |
| Updates | Copy SC Locator's `updater.py`: GitHub "latest release", installer checked against its SHA-256 digest, silent install, app restarts | Already proven; drafts and pre-releases never reach users | — |
| Settings / logs | `%LocalAppData%\SC Telemetry\` | Survives updates and uninstall/reinstall | — |

## 2. Architecture

```
StarCitizen.exe ──gRPC 127.0.0.1:2942──► telemetry.py (stream thread, reconnects every 2 s)
                ◄── TriggerGameAction ──          │
                                                   ▼
                     main.py (window, single instance) ──evaluate_js──► ui/index.html
                                    ▲                                        │
                                    └────────── api.py (js_api) ◄────────────┘  button presses
gamecfg.py: finds the game folder, enables telemetry in user.cfg, reads Game.log
updater.py: checks GitHub releases, downloads, starts the installer
```

### Project layout

```
app/
  main.py        entry point: single-instance mutex, window, wiring (thin)
  api.py         js_api methods the page calls: trigger, list_actions, enable_telemetry,
                 check_update, install_update, get/set settings (thin, calls the modules below)
  telemetry.py   GameClient: stream with reconnect, list_actions(), trigger(action, hold_ms)
  gamecfg.py     find install + channels (LIVE, PTU, EPTU, TECH-PREVIEW), read/enable the
                 user.cfg line (backup first), check Game.log for "Local services server is running"
  settings.py    load/save settings.json
  updater.py     copied from sc-locator; REPO, ASSET_NAME, VERSION changed
  proto/         generated *_pb2.py / *_pb2_grpc.py (build step)
ui/index.html    the mockup with the mock data and MOCKUP bar removed
installer/sc-telemetry.iss
build.ps1, sc_telemetry.spec, requirements.txt
tests/           pytest: gamecfg, updater, telemetry decoding from recorded frames
tools/, proto/, design/, DOCS/   as now
```

Business logic stays in `telemetry.py`, `gamecfg.py`, `settings.py` and `updater.py`. `main.py` and `api.py` only wire them up.

## 3. Features

### Version 0.1.0

- Telemetry panels from the dashboard: character, environment, ship, flight, systems and warning lights, flight assist, weapons, force feedback, event log.
- Control panel with grouped buttons (Player, Ship, Power, Flight, Modes, Navigation & comms, Seat, Emotes, Danger zone) and a search over all 112 actions.
- Buttons light up from live state: lights, power, gear, VTOL, decoupled, G-safe, prox assist, ESP, advanced HUD, NAV/SCM, light amp.
- Ship groups greyed out while on foot; everything disabled while the game is not connected.
- Radar ping: press-and-hold sends `hold_ms`. Eject, emergency exit and self-destruct: hold 1.5 s to send.
- A pop-up for each action with the game's status (`OK`, `MAP_INACTIVE`, `RATE_LIMITED`, …).
- Connection states: connected / waiting for game / telemetry off. In the "telemetry off" state, buttons add the setting to LIVE or PTU `user.cfg`.
- Update check at start, an "Update available" badge and an install dialog.
- Settings: game folder, telemetry status per channel, confirm dangerous actions, keep on top, check updates at start.

### Later (not in 0.1.0)

- Compact or overlay mode for a second screen
- Custom button layouts or favourites
- Hotkeys
- Stream-overlay output
- Recording sessions to a file

## 4. Build steps and how each is checked

| # | Step | Done when |
| --- | --- | --- |
| 1 | Scaffold: venv, `requirements.txt` (pywebview, grpcio, grpcio-tools, pyinstaller), generate stubs | `python -m app` opens a window showing `ui/index.html` |
| 2 | `telemetry.py` stream + reconnect | With the game running, frames reach the window at about 19/s; closing and restarting the game reconnects without restarting the app |
| 3 | Controls → `TriggerGameAction` | Flashlight toggles in game; an unknown action shows `UNKNOWN_ACTION`; a ship action on foot shows the game's status |
| 4 | `gamecfg.py` | Finds the install. "Enable" adds the line once (no duplicates) and keeps a backup of `user.cfg`. Tests pass on sample folders. |
| 5 | Settings | Saved settings survive a restart |
| 6 | Packaging: `build.ps1`, `.spec`, `.iss` | `dist\sc-telemetry-setup.exe` installs per-user, adds a Start menu entry, runs, and uninstalls cleanly |
| 7 | Updates | Publish v0.1.0, install it, publish v0.1.1: the installed app offers the update, installs it and restarts as 0.1.1 |
| 8 | GitHub | README, LICENSE, `.gitignore` checked; repo pushed; v0.1.0 release with `sc-telemetry-setup.exe` attached |
| 9 | Live test in a ship | Vehicle, weapons and events panels show real data; units checked (open questions in the findings doc) |

## 5. Release process (same as SC Locator)

1. Bump `VERSION` in `app/updater.py`.
2. Run `powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1`. It produces `dist\sc-telemetry-setup.exe`.
3. Tag `vX.Y.Z`, push, then `gh release create vX.Y.Z dist\sc-telemetry-setup.exe --notes "..."`.
4. GitHub records the asset's SHA-256 digest; the updater only offers releases that have one.

## 6. Risks

- **Unofficial API:** it comes from a PTU build and may change or disappear. The app keeps working without it (panels show "No data") and shows the game's status codes.
- **Publishing the schema:** `proto/` was decoded from the game executable. It describes an interface, not game assets, but CIG's terms of service may still apply. Your call before making the repo public.
- **Unsigned installer:** Windows SmartScreen shows "unknown publisher", as with SC Locator. Code signing costs money and is out of scope.
- **Any program on the PC can trigger actions** while telemetry is on. The app adds hold-to-confirm for the dangerous ones, but cannot stop other programs.

## 7. Open questions for you

1. ~~App and repo name~~ Decided: "SC Telemetry" / `city028/sc-telemetry`.
2. ~~Stack~~ Decided: Python + pywebview.
3. Branch: push to `main` (as SC Locator) or `develop` (your session-close default)?
4. Put `proto/`, the findings document and `tools/` in the public repo?
5. Layout: keep panels on the left and controls on the right? Hide the ship panels while on foot, or keep them greyed?
6. Any button groups to add, remove or reorder? Should on/off variants (e.g. `v_lights_on`) get their own buttons, or stay in search?
7. Licence: MIT, as SC Locator?
