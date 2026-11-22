# TODO

## Next

- [ ] Release v0.1.1 and test the in-app update on the installed 0.1.0 (download, checksum, silent install, restart)
- [ ] Check ship panels against the game while flying: speed, altitude, fuel, hull health, shields (confirm units and scales)
- [ ] Check that lit buttons match the game: lights, power, gear, VTOL, decoupled, G-safe, prox assist, ESP, NAV/SCM, light amp
- [ ] Test Flashlight, Visor wipe and Emotes while seated (Player group is dimmed on the assumption they are refused)
- [ ] Test radar ping hold (`hold_ms`) and the danger-zone hold-to-confirm in game
- [ ] Find out when the game returns `RATE_LIMITED` and `FILTERED`

## Later

- [ ] Compact or overlay mode for a second screen
- [ ] Custom button layouts or favourites
- [ ] Hotkeys
- [ ] Stream-overlay output
- [ ] Recording sessions to a file
- [ ] Update `design/mockup.html` to the seated Player-group behaviour (design reference only)
- [ ] Watch for the API on LIVE builds and for schema changes (re-extract `proto/` with `tools/desc.js`)
