# Star Citizen Local Telemetry API: Findings

Nov 22, 2026 · CityGamer

## Overview

The Star Citizen client has a local API. It is off by default. When switched on, the game runs a gRPC server on `127.0.0.1:2942`. That server streams live character and ship state at about 19 updates per second, and it can trigger 112 in-game actions on request.

The API appears to be built for sim hardware and companion apps. The game log tags it `[Haptic]`, and the stream includes a force-feedback frame for sticks. It enables dashboards, button boxes, motion rigs and stream overlays without screen-scraping or key-press macros.

| Item | Value |
| --- | --- |
| How to enable | `server.game.telemetry.enabled = 1` in `user.cfg`, then restart the game |
| Endpoint | `127.0.0.1:2942`, TCP, reachable only from the same PC |
| Protocol | gRPC over plain HTTP/2: no TLS, no authentication |
| Service | `sc.game.telemetry.v1.GameTelemetryService` |
| Methods | 3: `TelemetryStream`, `ListTriggerableActions`, `TriggerGameAction` |
| Stream rate observed | About 19 messages per second |
| Triggerable actions | 112, in 11 categories |
| Self-description (reflection) | Disabled; the full schema was recovered from the game executable |
| Build tested | PTU build 13248297, 22 Nov 2026 |

All three methods were tested against a running game. The stream and the action list work; triggering `toggle_flashlight` turned the flashlight on in game.

## Quick start

One config line and a restart turn the API on; the log confirms it.

1. Create or edit `user.cfg` in the game channel folder (for example `...\StarCitizen\PTU\user.cfg`) and add:

   ```
   server.game.telemetry.enabled = 1
   ```
2. Start the game. Setting it in the in-game console did not start the server in testing; it appears to be read only at startup.
3. Check `Game.log` in the same folder for these lines:

   ```
   [User CFG ] server.game.telemetry.enabled=true
   <Register Service> Service 'sc.game.telemetry.v1.GameTelemetryService' registered
      Endpoint '127.0.0.1:2942' Secured: False
   <GameTelemetry> Local services server is running on 127.0.0.1:2942
   ```
4. Connect any gRPC client to `127.0.0.1:2942` (plaintext) using the `.proto` files in the appendix. Or use the tools from this investigation (Node.js, no packages needed):

   ```
   node tools/live.js proto list
   node tools/live.js proto stream 10
   node tools/live.js proto trigger toggle_flashlight
   node tools/dashboard.js        (then open http://localhost:8088)
   ```

## How it was found

Port scanning was a dead end. The game log named the endpoint, and the schema came from the game executable.

1. **Port scan.** With the console variable set, a scan showed TCP ports 28198, 50159 and 63291. None was the API. Port 28198 belongs to the Elgato Stream Deck software. The other two were short-lived outbound connections that had already closed.
2. **Game sockets.** The game's own listeners (for example TCP 31318) accept connections but do not answer HTTP, WebSocket or TLS. They carry other, binary game traffic.
3. **Console vs. config.** Setting `server.game.telemetry.enabled 1` in the console left no trace in `Game.log` and opened no port. Adding the line to `user.cfg` and restarting did: the log then showed the service registering on `127.0.0.1:2942`.
4. **Reflection.** gRPC servers can describe their own methods (server reflection). This server answers `UNIMPLEMENTED` (status 12) to both reflection versions, so it cannot be queried for its schema.
5. **Schema from the executable.** gRPC/protobuf programs embed their compiled `.proto` definitions. `StarCitizen.exe` contains `sc/game/telemetry/v1/types.proto` (7,869 bytes) and `sc/game/telemetry/v1/api.proto` (1,650 bytes). Both were extracted byte for byte and decoded back into `.proto` text (appendix). The method paths also appear as plain strings, for example `/sc.game.telemetry.v1.GameTelemetryService/TelemetryStream`.
6. **Live test.** A small client built from that schema called all three methods against the running game. Every response decoded cleanly against the recovered schema.

## Transport and security

The API is plain, unauthenticated gRPC, reachable only from the PC running the game.

- **Transport:** gRPC over HTTP/2 without TLS ("h2c", prior knowledge). The log states `Secured: False`.
- **Binding:** `127.0.0.1` only. Other machines on the network cannot connect unless something on the PC forwards the port.
- **Authentication:** none. Any program on the PC can read the stream and trigger actions, including `v_self_destruct` and `v_eject`.
- **Browsers:** a web page cannot call it directly, because browsers do not expose raw HTTP/2 trailers. A small local bridge is needed (see Tooling).
- **Game-side limits:** `TriggerGameAction` can return `RATE_LIMITED`, `FILTERED` and `MAP_INACTIVE`. This suggests the game throttles and filters actions, but the exact limits were not measured.

The same gRPC stack (version 1.49.2) carries the game's online services (login, analytics, presence and others). Those go to Cloud Imperium servers over TLS on port 443 and are separate from this local API.

## Service and methods

`sc.game.telemetry.v1.GameTelemetryService` has three methods: one streams data, two handle actions.

| Method | Request | Response | What it does | Tested |
| --- | --- | --- | --- | --- |
| `TelemetryStream` | `TelemetryStreamRequest` (empty) | stream of `TelemetryStreamResponse` | Pushes live game-state frames until the client disconnects | Yes, about 19 messages/s |
| `ListTriggerableActions` | `ListTriggerableActionsRequest` (empty) | `ListTriggerableActionsResponse` | Returns every action name with its category and whether it can be held | Yes, 112 actions |
| `TriggerGameAction` | `TriggerGameActionRequest` (`action_name`, optional `hold_ms`) | `TriggerGameActionResponse` (`status`, `message`) | Performs one action in game, optionally held for `hold_ms` milliseconds | Yes, see below |

In testing, the gRPC call returned `OK` even for an unknown action name; the result of an action is in the response's `status` field.

| `TriggerGameActionStatus` | Meaning (from the name) | Seen in testing |
| --- | --- | --- |
| `OK` | Action performed | Yes: `toggle_flashlight` turned the flashlight on |
| `UNKNOWN_ACTION` | Name not in the action list | Yes: a made-up name |
| `MAP_INACTIVE` | The action's control set is not active (for example a ship action while on foot) | No |
| `RATE_LIMITED` | Too many requests | No |
| `FAILED` | Action could not be performed | No |
| `HOLD_NOT_ALLOWED` | `hold_ms` given for an action that cannot be held | No |
| `FILTERED` | Action blocked by the game | No |

Each status name has the prefix `TRIGGER_GAME_ACTION_STATUS_`, left out above. The meanings of statuses not seen in testing are inferred from their names.

## Telemetry stream data

Each stream message is a `TelemetryStreamResponse` holding up to six frames: actor, vehicle, weapons, events, force feedback and turret. While on foot, each message carried only the actor frame (97 bytes). The schema uses proto3, so a field that is zero, false or empty is left out of the message.

| Frame (field no.) | Main contents |
| --- | --- |
| `actor` (6) | Vitals, locomotion state, crew role, seat, aUEC balance, environment |
| `vehicle` (3) | Ship identity, health, shields, power, warning lights, doors, flight state, settings and instruments |
| `weapons` (4) | Weapon group, each weapon's state, countermeasures, weapon HUD settings |
| `events` (5) | List of game events since the last message |
| `force_feedback` (7) | Stick resistance and damping per axis, gunfire, stick shaker |
| `turret` (8) | Turret light amplification on or off |

### Field reference

| Path | Type | Notes |
| --- | --- | --- |
| `actor.vitals.health`, `oxygen`, `hunger`, `thirst`, `body_temperature` | Gauge (`current`, `max`) | Observed: health 100/100, oxygen 1/1, body temperature 36.5 |
| `actor.vitals.heart_rate`, `gravity`, `pressure` | float | Observed about 59, 1.0, 1.0 |
| `actor.vitals.intoxication_level` | int32 |  |
| `actor.state.locomotion` | enum | `ON_FOOT`, `EVA`, `SEATED` |
| `actor.state.crew_role` | enum | `PILOT`, `GUNNER`, `CREW` |
| `actor.state.seat_name` | string |  |
| `actor.state.uec_balance` | int64 | The character's aUEC balance |
| `actor.environment.external_temperature`, `ambient_radiation_rate` | float | Observed 21.0 and 0.0 |
| `actor.environment.breathable_atmosphere` | bool |  |
| `vehicle.state.name`, `class_name`, `manufacturer` | string |  |
| `vehicle.state.type` | enum | `SPACESHIP`, `GROUND`, `GRAVLEV`, `BOAT` |
| `vehicle.state.health` | float | Scale unknown |
| `vehicle.state.lights_enabled` | bool |  |
| `vehicle.state.doors` | open state, lock state | `OPENED` / `CLOSED`, `UNLOCKED` / `LOCKED` |
| `vehicle.state.shields` | `level` float, `faces` repeated float | One value per shield face |
| `vehicle.state.power` | 9 bools | Power plants, engines, weapons, coolers, life support, gravity generators, sensors, shield generators, shield emitters |
| `vehicle.state.annunciators` | 10 enums | `pwr`, `wpn`, `thr`, `shld`, `cool`, `qdrv`, `radr`, `prox`, `hit`, `misl`; each `NOMINAL`, `OFF`, `MINOR_ON`, `MINOR_FLASHING`, `MAJOR_ON` or `MAJOR_FLASHING` |
| `vehicle.state.master_mode` | `mode` enum, `spooled` bool | `NAVIGATION`, `SCM`, `STEALTH` |
| `vehicle.state.flight.state` | `is_landed`, `gear`, `vtol`, `transformation` | Deployment states: `RETRACTED`, `DEPLOYING`, `DEPLOYED`, `RETRACTING` |
| `vehicle.state.flight.instruments` | floats | `speed`, `altitude`, `radar_altitude`, `vertical_speed_indicator`, `heading`, `atmospheric_density`, `hydrogen_fuel`, `quantum_fuel`; units not confirmed |
| `vehicle.state.flight.instruments.g_meter` | Gauge |  |
| `vehicle.state.flight.instruments.boost` | `engaged`, `output`, `reserves`, `critical` |  |
| `vehicle.state.flight.settings` | 12 Availability (`enabled`, `active`) + 7 bools | Flight assist: coupled, ESP, gravity compensation, G-safe, cruise, speed limiter, proximity assist (and landing), stability, core, wind compensation, command behaviour; plus advanced HUD, course prediction and light amplification flags |
| `weapons.preset_index`, `preset_name` | uint32, string | Active weapon group |
| `weapons.weapons[]` | `name`, `is_powered`, `ready_to_fire`, `contained_in_preset` | One entry per weapon |
| `weapons.countermeasures[]` | `type`, `amount` | `DECOY` or `NOISE` |
| `weapons.settings` | 8 bools | Gimbals locked, staggered fire, precision lines, pip styles, magnified UI, fallback convergence distance |
| `events.events[].type` | enum | `ACTOR_SPAWN`, `ACTOR_DEAD`, `ACTOR_ENTER_SEAT`, `ACTOR_LEAVE_SEAT`, `ACTOR_RESPAWN`, `ACTOR_DOWNED` |
| `force_feedback.angular`, `linear` | x, y, z each with `resistance`, `damping` | For force-feedback sticks |
| `force_feedback.gunfire`, `stick_shaker` | float |  |
| `turret.light_amplification` | bool |  |

Enum values are shown without their type prefix (for example `ACTOR_LOCOMOTION_STATE_ON_FOOT` is shown as `ON_FOOT`). Only the actor frame has been seen with real data so far; the others are described from the schema.

## Triggerable actions

`ListTriggerableActions` returned 112 actions in 11 categories. Only one, `v_invoke_ping` (radar ping), can be held with `hold_ms`.

| Category | Count | Actions |
| --- | --- | --- |
| `player_emotes` | 34 | `emote_agree`, `angry`, `atease`, `attention`, `blah`, `bored`, `bow`, `burp`, `cheer`, `chicken`, `clap`, `come`, `cry`, `dance`, `disagree`, `failure`, `flex`, `flirt`, `gasp`, `gloat`, `greet`, `laugh`, `launch`, `point`, `rude`, `salute`, `sit`, `sleep`, `smell`, `taunt`, `threaten`, `wait`, `wave`, `whistle` (all prefixed `emote_`) |
| `spaceship_movement` | 27 | `v_atc_request`; landing system toggle / deploy / retract; advanced HUD on / off / toggle; G-safe toggle / on / off; proximity assist on / off / toggle; `v_ifcs_reset_gmeter_max`; `v_ifcs_toggle_esp`; vector decoupling on / off / toggle; master mode cycle / set NAV / set SCM; transform cycle / deploy / retract; VTOL on / off / toggle |
| `seat_general` | 17 | `v_eject`, `v_emergency_exit`; enter remote turret 1 / 2 / 3; light amplification on / off / toggle; operator mode cycle back / forward; set flight, guns, mining, quantum, refuel, salvage or scan mode |
| `spaceship_power` | 12 | Power on / off / toggle for the whole ship, shields, thrusters and weapons |
| `spaceship_general` | 11 | `v_flightready`, `v_self_destruct`; open / close / toggle all doors; lock / unlock / toggle all door locks; lock / unlock / toggle all ports |
| `player` | 4 | `mobiglas`, `toggle_flashlight`, `v_starmap`, `visor_wipe` |
| `lights_controller` | 3 | `v_lights`, `v_lights_on`, `v_lights_off` |
| `spaceship_docking` | 1 | `v_toggle_docking_request` |
| `spaceship_quantum` | 1 | `v_toggle_qdrive_engagement` |
| `spaceship_radar` | 1 | `v_invoke_ping` (holdable) |
| `spaceship_target_hailing` | 1 | `v_target_hail` |

Some names above are shortened; `ListTriggerableActions` returns the exact names. Ship actions likely return `MAP_INACTIVE` when not seated in a ship; this was not tested.

**Take care with:** `v_self_destruct`, `v_eject` and `v_emergency_exit`. Any program on the PC can send these while the API is enabled.

## Tooling built

Two working clients exist: a command-line client for all three methods and a live web dashboard. Both are Node.js with no packages to install.

&#91;embedded content: tooling architecture: game, CLI client, dashboard bridge, browser\]

Browsers cannot speak gRPC directly, so the dashboard uses a small bridge. It keeps one `TelemetryStream` open and forwards each frame to the page as Server-Sent Events (SSE).

| File | Purpose |
| --- | --- |
| `proto/api.proto`, `proto/types.proto` | Recovered schema (appendix); usable with any gRPC toolkit |
| `proto/*.desc` | The raw descriptors exactly as extracted from the executable |
| `tools/desc.js` | Protobuf decoding, descriptor-to-`.proto` conversion and extraction from `StarCitizen.exe` |
| `tools/schema.js` | Loads the descriptors and decodes any message into JSON |
| `tools/live.js` | CLI: `list`, `stream [seconds]`, `trigger <action> [hold_ms]` |
| `tools/dashboard.js` | Bridge: gRPC stream in, SSE out, serves the page on `http://localhost:8088` |
| `tools/dashboard.html` | Dashboard: character, environment, ship, flight, systems and warning lights, flight assist, weapons, force feedback, event log |
| `tools/findstr.js` | Searches a large binary for a string and prints the readable text around each hit |

The dashboard dims the ship panels when no ship data arrives, and shows "waiting for game" until the API is reachable.

## Caveats and open questions

This is an unofficial, undocumented feature, found in a test build; expect it to change.

- **Build:** everything was found on PTU build 13248297 on 22 Nov 2026. Names, fields and the port may change before or after release to LIVE.
- **Not announced:** the console variable came from leaked information. There is no official documentation, and the game's terms of service may limit how it can be used.
- **Ship data not yet seen:** only the actor frame has been observed live (on foot). Vehicle, weapons, events, force-feedback and turret frames are known from the schema but not yet confirmed with real data.
- **Units unknown:** speed, altitude, fuel, hull health and shield values have no units in the schema. The dashboard assumes m/s, metres and °C, as the game HUD uses; fuel, hull and shields are shown raw.
- **Action limits untested:** when `RATE_LIMITED`, `FILTERED` and `MAP_INACTIVE` occur has not been measured.
- **Security:** while enabled, any program on the PC can read the character's state and trigger actions, including self-destruct. There is no authentication.

### Open questions

- [ ] Confirm vehicle, weapons and event frames with real data while flying
- [ ] Confirm units for speed, altitude, fuel, hull health and shields
- [ ] Measure the rate limit for `TriggerGameAction`
- [ ] Check whether the stream rate changes in a ship (about 19 per second on foot)
- [ ] Check whether the API appears on LIVE builds

## Appendix: recovered .proto files

Both files were decoded from the descriptors built into `StarCitizen.exe` (PTU build 13248297). Every live response decoded cleanly against them. They work with any gRPC toolkit, for example `protoc` or `grpcurl -proto`.

### api.proto

```protobuf
// file: sc/game/telemetry/v1/api.proto
syntax = "proto3";
package sc.game.telemetry.v1;
import "sc/game/telemetry/v1/types.proto";

service GameTelemetryService {
  rpc TelemetryStream (.sc.game.telemetry.v1.TelemetryStreamRequest) returns (stream .sc.game.telemetry.v1.TelemetryStreamResponse);
  rpc TriggerGameAction (.sc.game.telemetry.v1.TriggerGameActionRequest) returns (.sc.game.telemetry.v1.TriggerGameActionResponse);
  rpc ListTriggerableActions (.sc.game.telemetry.v1.ListTriggerableActionsRequest) returns (.sc.game.telemetry.v1.ListTriggerableActionsResponse);
}

enum TriggerGameActionStatus {
  TRIGGER_GAME_ACTION_STATUS_UNSPECIFIED = 0;
  TRIGGER_GAME_ACTION_STATUS_OK = 1;
  TRIGGER_GAME_ACTION_STATUS_UNKNOWN_ACTION = 2;
  TRIGGER_GAME_ACTION_STATUS_MAP_INACTIVE = 3;
  TRIGGER_GAME_ACTION_STATUS_RATE_LIMITED = 4;
  TRIGGER_GAME_ACTION_STATUS_FAILED = 5;
  TRIGGER_GAME_ACTION_STATUS_HOLD_NOT_ALLOWED = 6;
  TRIGGER_GAME_ACTION_STATUS_FILTERED = 7;
}

message TelemetryStreamRequest {
}

message TelemetryStreamResponse {
  .sc.game.telemetry.v1.VehicleFrame vehicle = 3;
  .sc.game.telemetry.v1.WeaponsFrame weapons = 4;
  .sc.game.telemetry.v1.EventsFrame events = 5;
  .sc.game.telemetry.v1.ActorFrame actor = 6;
  .sc.game.telemetry.v1.ForceFeedbackFrame force_feedback = 7;
  .sc.game.telemetry.v1.TurretFrame turret = 8;
}

message TriggerGameActionRequest {
  string action_name = 1;
  optional uint32 hold_ms = 2;
}

message TriggerGameActionResponse {
  .sc.game.telemetry.v1.TriggerGameActionStatus status = 1;
  string message = 2;
}

message ListTriggerableActionsRequest {
}

message TriggerableAction {
  string action_name = 1;
  string category = 2;
  bool holdable = 3;
}

message ListTriggerableActionsResponse {
  repeated .sc.game.telemetry.v1.TriggerableAction actions = 1;
}
```

### types.proto

```protobuf
// file: sc/game/telemetry/v1/types.proto
syntax = "proto3";
package sc.game.telemetry.v1;

enum VehicleComponentDeploymentState {
  VEHICLE_COMPONENT_DEPLOYMENT_STATE_UNSPECIFIED = 0;
  VEHICLE_COMPONENT_DEPLOYMENT_STATE_RETRACTED = 1;
  VEHICLE_COMPONENT_DEPLOYMENT_STATE_DEPLOYING = 2;
  VEHICLE_COMPONENT_DEPLOYMENT_STATE_DEPLOYED = 3;
  VEHICLE_COMPONENT_DEPLOYMENT_STATE_RETRACTING = 4;
}

enum VehicleType {
  VEHICLE_TYPE_UNSPECIFIED = 0;
  VEHICLE_TYPE_SPACESHIP = 1;
  VEHICLE_TYPE_GROUND = 2;
  VEHICLE_TYPE_GRAVLEV = 3;
  VEHICLE_TYPE_BOAT = 4;
}

enum VehicleMasterMode {
  VEHICLE_MASTER_MODE_UNSPECIFIED = 0;
  VEHICLE_MASTER_MODE_NAVIGATION = 1;
  VEHICLE_MASTER_MODE_SCM = 2;
  VEHICLE_MASTER_MODE_STEALTH = 3;
}

enum ActorLocomotionState {
  ACTOR_LOCOMOTION_STATE_UNSPECIFIED = 0;
  ACTOR_LOCOMOTION_STATE_ON_FOOT = 1;
  ACTOR_LOCOMOTION_STATE_EVA = 2;
  ACTOR_LOCOMOTION_STATE_SEATED = 3;
}

enum ActorCrewRole {
  ACTOR_CREW_ROLE_UNSPECIFIED = 0;
  ACTOR_CREW_ROLE_PILOT = 1;
  ACTOR_CREW_ROLE_GUNNER = 2;
  ACTOR_CREW_ROLE_CREW = 3;
}

message Availability {
  bool enabled = 1;
  bool active = 2;
}

message Gauge {
  float current = 1;
  float max = 2;
}

message VehicleDoorState {
  enum DoorOpenState {
    DOOR_OPEN_STATE_UNSPECIFIED = 0;
    DOOR_OPEN_STATE_OPENED = 1;
    DOOR_OPEN_STATE_CLOSED = 2;
  }
  enum DoorLockState {
    DOOR_LOCK_STATE_UNSPECIFIED = 0;
    DOOR_LOCK_STATE_UNLOCKED = 1;
    DOOR_LOCK_STATE_LOCKED = 2;
  }
  .sc.game.telemetry.v1.VehicleDoorState.DoorOpenState open_state = 1;
  .sc.game.telemetry.v1.VehicleDoorState.DoorLockState lock_state = 2;
}

message VehicleFlightSettings {
  .sc.game.telemetry.v1.Availability ifcs_coupled = 1;
  .sc.game.telemetry.v1.Availability ifcs_esp = 2;
  .sc.game.telemetry.v1.Availability ifcs_gravity_compensation = 3;
  .sc.game.telemetry.v1.Availability ifcs_g_safe = 4;
  .sc.game.telemetry.v1.Availability ifcs_cruise_mode = 5;
  bool ifcs_spacebreak_enables_boost = 6;
  .sc.game.telemetry.v1.Availability ifcs_speed_limiter = 7;
  .sc.game.telemetry.v1.Availability ifcs_proximity_assist = 8;
  .sc.game.telemetry.v1.Availability ifcs_proximity_assist_landing = 9;
  .sc.game.telemetry.v1.Availability ifcs_stability = 10;
  .sc.game.telemetry.v1.Availability ifcs_core = 11;
  bool advanced_hud_enabled_scm = 12;
  bool advanced_hud_enabled_nav = 13;
  bool advanced_hud_labels = 14;
  bool course_prediction = 15;
  .sc.game.telemetry.v1.Availability ifcs_wind_compensation = 16;
  bool ifcs_g_safe_disabled_by_boost = 17;
  .sc.game.telemetry.v1.Availability ifcs_command_behaviour = 18;
  bool flight_light_amplification = 19;
}

message VehicleFlightState {
  bool is_landed = 1;
  optional .sc.game.telemetry.v1.VehicleComponentDeploymentState gear = 2;
  optional .sc.game.telemetry.v1.VehicleComponentDeploymentState vtol = 3;
  optional .sc.game.telemetry.v1.VehicleComponentDeploymentState transformation = 4;
}

message VehicleFlight {
  .sc.game.telemetry.v1.VehicleFlightState state = 1;
  .sc.game.telemetry.v1.VehicleFlightSettings settings = 2;
  .sc.game.telemetry.v1.VehicleFlightInstruments instruments = 3;
}

message VehicleFlightInstruments {
  float speed = 1;
  float hydrogen_fuel = 2;
  float quantum_fuel = 3;
  optional .sc.game.telemetry.v1.Gauge g_meter = 4;
  .sc.game.telemetry.v1.VehicleThrusterBoost boost = 5;
  float altitude = 6;
  float radar_altitude = 7;
  float vertical_speed_indicator = 8;
  float atmospheric_density = 9;
  float heading = 10;
}

message VehicleThrusterBoost {
  bool engaged = 1;
  float output = 2;
  float reserves = 3;
  bool critical = 4;
}

message VehiclePowerState {
  bool powerplants = 1;
  bool engines = 2;
  bool weapons = 3;
  bool coolers = 4;
  bool life_support = 5;
  bool gravity_generators = 6;
  bool sensors = 7;
  bool shield_generators = 8;
  bool shield_emitters = 9;
}

message VehicleAnnunciator {
  enum AnnunciatorState {
    ANNUNCIATOR_STATE_UNSPECIFIED = 0;
    ANNUNCIATOR_STATE_NOMINAL = 1;
    ANNUNCIATOR_STATE_OFF = 2;
    ANNUNCIATOR_STATE_MINOR_FLASHING = 3;
    ANNUNCIATOR_STATE_MINOR_ON = 4;
    ANNUNCIATOR_STATE_MAJOR_FLASHING = 5;
    ANNUNCIATOR_STATE_MAJOR_ON = 6;
  }
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState pwr = 1;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState wpn = 2;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState thr = 3;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState shld = 4;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState cool = 5;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState qdrv = 6;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState radr = 7;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState prox = 8;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState hit = 9;
  .sc.game.telemetry.v1.VehicleAnnunciator.AnnunciatorState misl = 10;
}

message VehicleShields {
  float level = 1;
  repeated float faces = 2;
}

message VehicleMasterModeState {
  .sc.game.telemetry.v1.VehicleMasterMode mode = 1;
  bool spooled = 2;
}

message VehicleState {
  string name = 1;
  string class_name = 2;
  string manufacturer = 3;
  .sc.game.telemetry.v1.VehicleType type = 4;
  bool lights_enabled = 5;
  optional .sc.game.telemetry.v1.VehicleDoorState doors = 6;
  optional .sc.game.telemetry.v1.VehicleAnnunciator annunciators = 7;
  optional .sc.game.telemetry.v1.VehicleFlight flight = 8;
  optional .sc.game.telemetry.v1.VehiclePowerState power = 9;
  optional .sc.game.telemetry.v1.VehicleShields shields = 10;
  float health = 11;
  optional .sc.game.telemetry.v1.VehicleMasterModeState master_mode = 12;
}

message VehicleFrame {
  .sc.game.telemetry.v1.VehicleState state = 2;
}

message WeaponsSettings {
  bool fallback_convergence_distance = 1;
  bool magnified_ui = 2;
  bool precision_lines = 3;
  bool staggered_fire = 4;
  bool use_lag_pips = 5;
  bool use_single_pips = 6;
  bool use_fading_pips = 7;
  bool gimbals_locked = 8;
}

message WeaponState {
  string name = 1;
  bool is_powered = 2;
  bool ready_to_fire = 3;
  bool contained_in_preset = 4;
}

message Countermeasures {
  enum CountermeasureType {
    COUNTERMEASURE_TYPE_UNSPECIFIED = 0;
    COUNTERMEASURE_TYPE_DECOY = 1;
    COUNTERMEASURE_TYPE_NOISE = 2;
  }
  .sc.game.telemetry.v1.Countermeasures.CountermeasureType type = 1;
  uint32 amount = 2;
}

message WeaponsFrame {
  .sc.game.telemetry.v1.WeaponsSettings settings = 1;
  uint32 preset_index = 2;
  string preset_name = 3;
  repeated .sc.game.telemetry.v1.WeaponState weapons = 4;
  repeated .sc.game.telemetry.v1.Countermeasures countermeasures = 5;
}

message GameEvent {
  enum GameEventType {
    GAME_EVENT_TYPE_UNSPECIFIED = 0;
    GAME_EVENT_TYPE_ACTOR_SPAWN = 1;
    GAME_EVENT_TYPE_ACTOR_DEAD = 2;
    GAME_EVENT_TYPE_ACTOR_ENTER_SEAT = 3;
    GAME_EVENT_TYPE_ACTOR_LEAVE_SEAT = 4;
    GAME_EVENT_TYPE_ACTOR_RESPAWN = 5;
    GAME_EVENT_TYPE_ACTOR_DOWNED = 6;
  }
  .sc.game.telemetry.v1.GameEvent.GameEventType type = 1;
}

message EventsFrame {
  repeated .sc.game.telemetry.v1.GameEvent events = 1;
}

message AxisFeedback {
  float resistance = 1;
  float damping = 2;
}

message FeedbackAxes {
  .sc.game.telemetry.v1.AxisFeedback x = 1;
  .sc.game.telemetry.v1.AxisFeedback y = 2;
  .sc.game.telemetry.v1.AxisFeedback z = 3;
}

message ForceFeedbackFrame {
  .sc.game.telemetry.v1.FeedbackAxes angular = 2;
  .sc.game.telemetry.v1.FeedbackAxes linear = 3;
  float gunfire = 4;
  float stick_shaker = 5;
}

message ActorVitals {
  .sc.game.telemetry.v1.Gauge health = 1;
  .sc.game.telemetry.v1.Gauge oxygen = 2;
  .sc.game.telemetry.v1.Gauge hunger = 3;
  .sc.game.telemetry.v1.Gauge thirst = 4;
  .sc.game.telemetry.v1.Gauge body_temperature = 5;
  float heart_rate = 7;
  float gravity = 8;
  float pressure = 9;
  int32 intoxication_level = 10;
}

message ActorEnvironment {
  float external_temperature = 1;
  float ambient_radiation_rate = 2;
  bool breathable_atmosphere = 3;
}

message ActorState {
  .sc.game.telemetry.v1.ActorLocomotionState locomotion = 1;
  .sc.game.telemetry.v1.ActorCrewRole crew_role = 2;
  string seat_name = 3;
  int64 uec_balance = 4;
}

message ActorFrame {
  .sc.game.telemetry.v1.ActorVitals vitals = 1;
  .sc.game.telemetry.v1.ActorState state = 2;
  .sc.game.telemetry.v1.ActorEnvironment environment = 3;
}

message TurretFrame {
  bool light_amplification = 1;
}
```
