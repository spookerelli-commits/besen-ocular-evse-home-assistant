# BESEN / Ocular EVSE for Home Assistant — Project History

This document records the development of the unofficial native Bluetooth
integration for the Ocular LTE Plus / EVSE BS20. The integration was developed
against charger firmware `405.3251.0Q03196` and communicates locally through
Home Assistant's Bluetooth layer, including ESPHome Bluetooth proxies.

The project began as a Home Assistant port of the reverse-engineered
[`spudstuff/HA-ESP32-Ocular-EVSE`](https://github.com/spudstuff/HA-ESP32-Ocular-EVSE)
firmware. Repeated scheduling was subsequently decoded from an Android HCI
snoop capture of EVSEMaster communicating with the charger.

## Current project status

- Latest release: **v0.3.2** (field-test release).
- Discovery, authentication, telemetry, charge control, current limiting and
  charger-stored repeated schedules are working in live use.
- Live charging values have been compared with the EVSE display, and a schedule
  written by Home Assistant was read back correctly by EVSEMaster.
- The schedule UI exposes the protocol's seven independent weekday records and
  stages edits until they are explicitly applied.
- The observed development connection is weak, approximately -95 to -98 dBm.
  Connection diagnostics are included so proxy placement can be evaluated.
- This remains an unofficial integration tested with one BS20 charger and one
  known firmware version.

## Protocol findings

- BLE service UUIDs: `FFE4` and `FFE9`.
- EVSEMaster uses the charger's six-character PIN for authentication.
- Repeated-schedule write command: `0x810E`.
- Repeated-schedule response/readback: `0x010E`.
- The repeated-schedule payload contains seven discrete nine-byte records,
  ordered Monday through Sunday.
- Each day stores enabled state, start minute and duration. The app derives the
  displayed stop time; a stop earlier than the start represents the next day.
- EVSEMaster sends the schedule only when Enable or Disable is pressed, not
  while individual fields are being edited.
- The schedule is stored in the charger and continues to operate without Home
  Assistant, Wi-Fi or the Bluetooth proxy.

## Release history

### v0.3.2 — 2026-08-27

#### Fixed

- Reset **Reconnects today** at Home Assistant local midnight even when the BLE
  connection remains continuously healthy. The existing connection-time date
  check remains as a fallback for restarts, missed callbacks and clock changes.
- Corrected documentation to use the actual **Apply daily schedule** button
  label and clarified that pressing it without editing preserves independent
  weekday records.
- Removed the development charger's Bluetooth address from public examples.

#### Changed

- Grouped entities into related **Repeated charging**, **Once-off charging** and
  **Diagnostics** devices while retaining every existing entity unique ID.
- Broadened the displayed integration identity to **BESEN / Ocular EVSE** to
  reflect the underlying BS20 platform. Confirmed support remains limited to
  the field-tested Ocular LTE Plus firmware.

#### Project and collaboration

- Added HACS custom-repository metadata, automated compile/JSON/unit-test
  checks, contribution and security guidance, pull-request checks, and issue
  forms for bugs and regional charger compatibility.
- Added clear experimental status, supported/untested model boundaries, live
  validation results and privacy guidance.
- Added prominent upstream project attribution and a dedicated `CREDITS.md`
  describing inherited protocol foundations and subsequent development.
- Replaced the abbreviated licence notice with the complete GPL-3.0 text and
  retained upstream attribution.

### v0.3.1 — 2026-08-24

#### Fixed

- Corrected charger-clock synchronization from the incorrectly split
  `0x079C` command to the captured OCPP Set Tool exchange: command `0x8207`,
  payload `9C YY MM DD HH MM SS`, and response `0x0207` with success byte `01`.
- Clock synchronization now distinguishes a positive charger acknowledgement
  from a rejection instead of treating any response as success.

#### Improved

- Renamed the compatible common schedule controls to **All-days start** and
  **All-days stop**. They now stage the chosen time across all seven weekday
  records; **Apply daily schedule** performs the single verified write.
- Schedule debug logging now reports all seven requested and returned daily
  records, confirms exact matches, and identifies individual mismatched days.
- Existing entity IDs and unique IDs are retained for the renamed all-days
  controls.

### v0.3.0 — 2026-08-24

#### Added

- Independent start time, stop time and enable controls for Monday through
  Sunday, matching the seven discrete records in command `0x810E`.
- Staged schedule editing with **Apply daily schedule**, **Discard schedule
  changes** and **Refresh schedule from charger** actions.
- Exact seven-record readback verification after every staged schedule write.
- Charger-stored once-off charging settings for delay, maximum duration and
  energy target, plus an explicit start action using captured command `0x8007`.
- Manual charger-clock synchronization using the OCPP Set Tool protocol. The
  action is intentionally blocked while the charger is actively outputting.
- **Vehicle plugged in** binary sensor for reminder automations.
- Persisted **Reconnects today**, **Last reconnect** and **Integration health**
  diagnostics.
- A startup grace period for Home Assistant's connectable Bluetooth path.
- A **Schedule changes pending** diagnostic exposing the staged records.

#### Changed

- Renamed the measured Current sensor to **Charge current**. The writable
  control remains **Current limit** and retains its existing entity identity.
- Reconnect count now rolls over by local calendar day instead of increasing
  forever, and survives Home Assistant restarts during that day.
- Existing common schedule start/stop controls are retained for compatibility;
  using them deliberately writes one common window to selected days.

#### Safety and verification

- Once-off charging waits for the charger acknowledgement and reports a timeout
  or rejected result instead of assuming that the write succeeded.
- Daily schedule writes are accepted only when every enabled weekday's echoed
  start and duration exactly match the requested records.
- OCPP/network/password configuration observed in the separate OCPP Set Tool is
  not exposed by this release.

#### Field-test focus

- Confirm that this firmware persists different time windows for different
  weekdays after reconnecting EVSEMaster or power-cycling the charger.
- Supervise the first once-off delayed session and confirm its delay, duration
  and energy target in EVSEMaster.
- Continue monitoring daily reconnects at the development proxy's weak signal
  level; a closer proxy remains the preferred remedy for repeated dropouts.

### v0.2.11 — 2026-08-23

#### Added

- Decode manual/user charging records (`0x0009`) as well as scheduled/clock
  records (`0x000A`) and acknowledge them with `0x8009` or `0x800A`.
- Persist the most recent 100 decoded records in Home Assistant storage so the
  Last charging session survives integration and Home Assistant restarts.
- Record diagnostics now include record type, source command, raw flag bytes,
  raw mode/source values and the complete raw payload.

#### Fixed

- Match EVSEMaster current reads (`02 00 00`) and writes
  (`01 <amps> 0B`) exactly.
- Match EVSEMaster's 17-byte manual-stop payload.
- Match the captured manual-start layout by clearing its unused timestamp
  bytes.
- Render charger record timestamps using the firmware's fixed UTC+8 wall-clock
  convention, preventing Adelaide times from appearing 90 minutes late.
- Remove the incorrect interpretation of the raw record mode byte as
  configured current.

#### Test focus

- Start and stop a short manual charging session from Home Assistant. Confirm
  the requested current in EVSEMaster, then verify that HA creates a manual
  completed-session event and retains Last charging session after a restart.

### v0.2.10 — 2026-08-23

#### Added

- Decode charger command `0x000A` into a session record with charge ID, user
  ID, termination reason, start/end timestamps, duration, meter readings,
  configured current and session energy.
- A **Charging session history** event entity. Home Assistant records one
  `completed` event per unique stored charging session, with all decoded fields
  as event attributes.
- A **Last charging session** sensor with the newest record as attributes.
- Recognition of the observed `0x0009` charge-completion notification.

#### Fixed

- Acknowledge every charging record with the captured `0x800A` response. This
  stops repeated delivery of the same record and lets the charger advance
  through any stored history backlog.
- Map raw protocol state 14 plus output state 2 to **Stopped by EV**. The
  Charging switch remains on while the vehicle has paused an active session.

Existing entity identities are retained. The event timestamp is when Home
Assistant receives the record; charger start/end times are event attributes.

### v0.2.9 — 2026-08-23

#### Added

- Diagnostic sensors for the raw plug, output and protocol-state values.
- A `source_packet` attribute on each raw-state sensor, identifying the most
  recent Bluetooth packet that supplied the value.

#### Changed

- Renamed the displayed **Start current limit** control to **Current limit**.
  Its unique ID and entity identity remain unchanged.

This release is deliberately limited to state-mapping diagnostics and the
current-control label. It does not infer or rename “Stop by EV” yet; the raw
values will establish whether that condition has its own protocol code.

### v0.2.8 — 2026-08-23

#### Fixed

- Serialised Bluetooth notifications through a single receive-order queue.
- Published decoded AC and charging status before sending the corresponding
  acknowledgement, preventing a slow BLE write from withholding entity updates.
- Added a finite timeout to every BLE write.
- A parser failure, write timeout or queue overflow now stops the protocol
  worker and causes a clean reconnect instead of allowing packet timestamps to
  advance while packet-type and status entities remain stale.
- Reset the packet reassembly buffer when reconnecting.

#### Retained

- The v0.2.7 operational watchdog, recovery logic and command counters.

This release addressed a concurrency risk discovered while investigating an
incident where traffic timestamps continued updating but decoded packet and
status entities did not. It does not claim that the recorded login beacon was
the cause; that beacon was simply the last packet successfully published.

### v0.2.7 — 2026-08-23

#### Added

- A separate **Last operational packet received** diagnostic.
- Command counters, consecutive-login count and reauthentication count as
  attributes of **Last packet type**.
- Session-health monitoring that distinguishes BLE traffic from authenticated
  heartbeat and status traffic.

#### Changed

- Repeated login beacons after 45 seconds without operational traffic trigger
  one guarded reauthentication and initial synchronisation.
- A missing login response or prolonged absence of operational traffic causes
  a clean reconnect.

This release improved recovery and observability. v0.2.8 subsequently hardened
the underlying notification-processing path.

### v0.2.6 — 2026-08-23

#### Added

- **Last connection error**, separate from **Last disconnect reason**.

#### Changed

- Wait for Home Assistant's Bluetooth-adapter layer during startup.
- Changed the integration dependency from `bluetooth` to
  `bluetooth_adapters`.
- Labelled plug-state value `3` as **Negotiating**.

#### Fixed

- Startup failures such as “No connectable Bluetooth path” no longer appear as
  disconnects from an established session.

### v0.2.5 — 2026-08-23

#### Added

- Persistent **Last unknown packet** diagnostic.
- Unknown command, receive time, payload length and direction attributes.

Raw packet bodies and credentials are deliberately not exposed.

### v0.2.4 — 2026-08-23

#### Added

- **Last packet type** diagnostic with decoded command name, hexadecimal
  command, payload length and direction.

### v0.2.3 — 2026-08-23

#### Fixed

- Acknowledge AC-status pushes with `0x8004` and charging-status pushes with
  `0x8005`, matching the behaviour captured from EVSEMaster.
- Preserve the most recent disconnect reason after an automatic reconnection.

### v0.2.2 — 2026-08-23

#### Fixed

- Made login and initial synchronisation idempotent.
- Ignore duplicate login beacons after authentication so they do not repeatedly
  trigger current and schedule queries.

### v0.2.1 — 2026-08-22

#### Added

- Passive diagnostics for Bluetooth connectivity, last packet time, connection
  uptime, reconnect count, disconnect reason and last schedule verification.
- Debug logging of command numbers and payload lengths without logging the PIN
  or raw packet body.

This release intentionally did not alter connection, retry, polling, schedule
or control behaviour.

### v0.2.0 — 2026-08-22

#### Added

- Read and write support for the charger-stored repeated schedule.
- Master schedule switch, weekday switches and common start/stop controls.
- Readback confirmation after schedule writes.
- Protocol tests for the decoded seven-day schedule format.

#### Validated

- A Home Assistant schedule of 00:09 to 05:59 was subsequently displayed
  correctly by EVSEMaster.

### v0.1.3 — 2026-08-22

#### Changed

- Replaced direct `BleakClient.connect()` use with Home Assistant's recommended
  retry connector for reliable connection establishment and Bluetooth-proxy
  connection-slot coordination.

### v0.1.2 — 2026-08-22

#### Fixed

- Corrected Home Assistant metadata types for session-energy and diagnostic
  sensors.
- Used Home Assistant's `EntityCategory` enum for diagnostic entities.

### v0.1.1 — 2026-08-22

#### Fixed

- Corrected the session-energy state class to a value valid for an energy
  sensor.

### v0.1.0 — 2026-08-22

#### Added

- Initial native Home Assistant Bluetooth integration.
- Bluetooth discovery and manual configuration flow.
- EVSEMaster PIN authentication.
- Charging start/stop switch and 6–32 A current control.
- Voltage, current, power, total energy, session energy, session duration,
  maximum current, temperature, plug state, output state and protocol status.
- ESPHome Bluetooth-proxy support through Home Assistant's Bluetooth layer.
- Initial protocol parser tests.

## Known limitations

- Only the Ocular LTE Plus / EVSE BS20 with firmware `405.3251.0Q03196` has
  been exercised during development.
- BESEN-branded, three-phase and other EVSEMaster-compatible models have not yet
  been tested and may use different payloads or state mappings.
- The charger may allow only one BLE client, so EVSEMaster should be fully
  closed while Home Assistant is connected.
- BLE stability is sensitive to proxy placement and radio conditions.
- Long-term multi-device and multi-firmware testing is still in progress.

## Attribution

The integration is licensed under GPL-3.0. Protocol framing and original
behaviour were ported from `spudstuff/HA-ESP32-Ocular-EVSE`, also GPL-3.0.
