# BESEN / Ocular EVSE for Home Assistant

Unofficial local Bluetooth integration for BESEN BS20-based chargers, including
the Australian Ocular LTE Plus. It uses Home Assistant's Bluetooth layer and
works through a local adapter or ESPHome Bluetooth proxy without MQTT or proxy
firmware changes.

> [!WARNING]
> This reverse-engineered integration is experimental. It has been exercised
> on one single-phase Ocular LTE Plus / BESEN BS20 running firmware
> `405.3251.0Q03196`. Supervise the first use of every charging control and
> schedule. It is not affiliated with BESEN, Ocular or EVSEMaster.

## Origin and attribution

This integration originated as a native Home Assistant port of
[`spudstuff/HA-ESP32-Ocular-EVSE`](https://github.com/spudstuff/HA-ESP32-Ocular-EVSE),
a GPL-3.0 ESP32 BLE-to-MQTT bridge. Spudstuff's work established the EVSEMaster
BLE framing, authentication, heartbeat handling, initial telemetry and state
decoding, and basic charging-control behaviour on which this project was built.

This repository is independent because it has a substantially different
architecture: it is a Python integration using Home Assistant's native
Bluetooth stack rather than ESP32 firmware and MQTT. Charger-stored repeated
schedules, independent weekday records, charging-session records, once-off
charging, charger-clock synchronisation, readback verification and the current
connection-management implementation were subsequently developed from
controlled EVSEMaster/vendor-tool captures and field testing.

The upstream contribution remains fundamental to this project and is retained
under the same GPL-compatible terms. See [CREDITS.md](CREDITS.md) for the
detailed acknowledgement and [LICENSE](LICENSE) for the licence.

## Confirmed features

- Bluetooth discovery and six-character EVSEMaster PIN authentication
- ESPHome Bluetooth proxy support
- Live status, plug state, voltage, current, power, energy and temperature
- Start/stop control and live 6–32 A current limiting
- Seven independent charger-stored weekday schedules
- Staged schedule edits with exact seven-record write/readback verification
- Charger-stored once-off delay, duration and energy limit
- Manual charger-clock synchronisation while idle
- Charging-session records and a vehicle-plugged-in sensor
- Connection, packet, unknown-command and schedule diagnostics
- Local-midnight reset of the daily reconnect counter

The repeated schedule continues operating without Home Assistant, Wi-Fi or the
Bluetooth proxy. A live test confirmed an all-days schedule write, exact charger
readback and autonomous scheduled charging at the stored start time.

## Compatibility

| Charger | Status |
| --- | --- |
| Ocular LTE Plus, single-phase, firmware `405.3251.0Q03196` | Field tested |
| BESEN BS20 APP variants | Expected; community testing required |
| Three-phase BS20 | Unverified |
| Other EVSEMaster models (BN70, BS30, BN30, SQ20, SQW45, CC40) | Protocol compatibility unknown |

Matching enclosure or EVSEMaster support alone does not prove protocol
compatibility. Please submit the compatibility-report issue form for another
brand, firmware or electrical configuration.

## Requirements

- Home Assistant 2026.8 or newer recommended
- A connectable Bluetooth adapter or ESPHome proxy in range
- The six-character PIN used by EVSEMaster
- EVSEMaster fully closed while Home Assistant is connected; tested BS20
  firmware appears to permit only one BLE client

## Installation

### HACS custom repository

1. In HACS, open **Integrations**, then its custom repositories menu.
2. Add this repository as an **Integration**.
3. Install **BESEN / Ocular EVSE** and restart Home Assistant.

### Manual

1. Download the release ZIP.
2. Copy `custom_components/ocular_evse` to
   `/config/custom_components/ocular_evse`.
3. Restart Home Assistant.

Open **Settings > Devices & services**. A compatible charger advertising the
`FFE4` or `FFE9` service should be discovered. Otherwise select **Add
integration**, search for **BESEN / Ocular EVSE**, and enter the Bluetooth
address, EVSEMaster PIN and optional charging-record user ID.

## Device layout

Entities retain their established unique IDs but are separated into related
devices to reduce clutter:

- **BESEN / Ocular EVSE** — live telemetry, manual charging, current limit,
  plug state, clock sync and charging history
- **Repeated charging** — all-days and weekday schedule controls, Apply daily
  schedule, discard, refresh and verification state
- **Once-off charging** — delay, duration, energy limit and start action
- **Diagnostics** — Bluetooth health, RSSI, packets, reconnects and errors

## Repeated charging

Each weekday has its own enable switch, start time and stop time. Edits are
local drafts until **Apply daily schedule** is pressed. The integration writes
all seven records and accepts success only when the charger echoes an exact
match. **Discard schedule changes** restores the last confirmed values and
**Refresh schedule from charger** rereads them.

Changing **All-days start** or **All-days stop** stages that value across all
seven records. Merely pressing **Apply daily schedule** preserves existing
per-day differences. A stop time earlier than its start time means the following
day, matching EVSEMaster.

## Once-off charging

Set the delay, maximum duration and/or energy limit, then press **Start once-off
charging**. Zero duration or energy means unlimited. The integration waits for
the charger acknowledgement before reporting success.

## First live test

Keep the vehicle and charger supervised. Verify read-only values first. Set a
conservative current, start charging, confirm the vehicle starts, wait at least
30 seconds for the anti-cycling cooldown, then stop. Test repeated and once-off
schedules only after manual operation is confirmed.

Enable sanitised debug logging when needed:

```yaml
logger:
  logs:
    custom_components.ocular_evse: debug
```

Logs contain command numbers and payload lengths, not the PIN or raw packet
body. Charging-record attributes can contain the configured record user ID, so
review exports before posting them publicly.

## Development

The protocol and session-health tests require only Python:

```bash
python -m compileall -q custom_components
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing protocol or charging
control changes. See [CHANGELOG.md](CHANGELOG.md) for protocol findings and the
complete release history, and [CREDITS.md](CREDITS.md) for project lineage.

## Licence and attribution

GPL-3.0-or-later. Original protocol framing and behaviour were ported from
`spudstuff/HA-ESP32-Ocular-EVSE`, also GPL-3.0. See [LICENSE](LICENSE) and
[CREDITS.md](CREDITS.md).
