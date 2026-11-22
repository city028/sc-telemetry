# Session handover

Last session: 2026-11-22.

## State

- **SC Telemetry 0.1.0 is released:** https://github.com/city028/sc-telemetry/releases/tag/v0.1.0 (public repo, branch `main`).
- Installed on this PC in `%LocalAppData%\Programs\SC Telemetry`. Settings and log are in `%LocalAppData%\SC Telemetry`.
- Local folder `Y:\sc-api` (NAS) is the repo. It needs a git `safe.directory` entry, which has been added.

## What was done

1. Found Star Citizen's local telemetry API: gRPC on `127.0.0.1:2942`, switched on by `server.game.telemetry.enabled = 1` in `user.cfg` (the console command does not work). Server reflection is off; the schema was extracted from `StarCitizen.exe` into `proto/`.
2. Built Node tools (`tools/`): a CLI client (`live.js`), a browser dashboard and the extraction scripts.
3. Wrote the findings doc (Claude Doc, exported to `DOCS/Star Citizen Local Telemetry API.md`).
4. Designed the app (`design/mockup.html`) and planned it (`DOCS/PLAN.md`).
5. Built the app (Python + pywebview + grpcio). Packaging, installer and updater follow SC Locator.
6. Fixed: Player and Emotes controls flashing (`classList.toggle` given `undefined`).
7. Changed: Player group dims while seated, because the game answers `MAP_INACTIVE` to player actions in a seat. Pop-ups explain the game's statuses in words.

## Verified

- 18 pytest tests pass, including a fake game server.
- Installer installs per user; the app connects to the live game; only one copy runs at a time.
- The release's SHA-256 digest matches the build; the updater reads the release correctly.
- Seated in an Anvil Arrow, vehicle frames arrive. `v_starmap` and `mobiglas` return `MAP_INACTIVE`.

## Not verified

- A real update (v0.1.0 → v0.1.1) on an installed copy.
- Ship panels and lit buttons against real ship data in detail; units for speed, altitude, fuel and hull health.
- Whether Flashlight, Visor wipe and Emotes work while seated.

## Next steps

See [TODO.md](TODO.md).
