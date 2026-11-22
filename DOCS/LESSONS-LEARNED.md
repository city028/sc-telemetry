# Lessons learned

## Star Citizen telemetry API

- **`user.cfg`, not the console.** `server.game.telemetry.enabled 1` in the in-game console did nothing. The same setting in `user.cfg` starts the gRPC server at the next game start. Game.log then shows `Local services server is running on 127.0.0.1:2942`.
- **Port scans mislead.** The ports seen first (28198, 50159, 63291) were Stream Deck and short-lived outbound connections. Game.log named the real endpoint.
- **No reflection, but the schema is in the exe.** gRPC/protobuf programs embed their `FileDescriptorProto`s. Find `\x0a<len>sc/game/telemetry/v1/types.proto` in `StarCitizen.exe` and read top-level fields until field 12 (`syntax`) to cut out the exact descriptor.
- **Load descriptors, skip codegen.** Python: `DescriptorPool.AddSerializedFile` + `message_factory.GetMessageClass`. No `grpcio-tools` step, and the types are exactly the game's.
- **Proto3 leaves out defaults.** A missing field means 0, false or empty: for example, a missing `ifcs_coupled.active` means decoupled. int64 arrives as a string in `MessageToDict`.
- **Action groups follow the seat.** Seated, the game answers `MAP_INACTIVE` to player-group actions (`v_starmap`, `mobiglas`). There is no ship version of the starmap action in this build.

## App and UI

- **`classList.toggle(name, undefined)` flips the class.** Always pass a real boolean (`!!x`). This made the Player and Emotes groups flash every 100 ms.
- **The browser pane pauses hidden pages.** `requestAnimationFrame` loops stop while the pane is in the background, so tests sampled stale state. Take a screenshot (which brings the pane forward) or call the render function directly.
- **Bust the cache when re-testing a page.** The browser pane kept the old `index.html`; add `?v=N` to the URL.
- **pywebview exposes every public attribute** of the `js_api` object. Keep state in `_underscored` attributes.

## Environment

- **`Y:` is a NAS share.** git refuses it as "dubious ownership" until it has a `safe.directory` entry (`%(prefix)///NAS/Projects/<repo>`).
- **`grep -m1` after a streaming Node script** prints an EPIPE stack trace from Node. It is harmless.
