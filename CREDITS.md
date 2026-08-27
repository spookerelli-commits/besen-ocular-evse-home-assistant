# Credits and project lineage

## Upstream foundation

This project is built on the reverse-engineering and implementation work by
**spudstuff** in
[`HA-ESP32-Ocular-EVSE`](https://github.com/spudstuff/HA-ESP32-Ocular-EVSE).
That GPL-3.0 project implemented an ESP32 bridge between an Ocular LTE Plus /
EVSE BS20 charger and Home Assistant through Bluetooth Low Energy and MQTT.

The upstream work established the foundation used here, including:

- EVSEMaster packet framing and checksums
- Six-character PIN authentication
- BLE service and characteristic behaviour
- Heartbeat request/response handling
- Initial AC, charging and error-state decoding
- Basic charge start/stop commands and safety cooldown behaviour

Without that published work, this native Home Assistant integration would not
have had its starting protocol implementation.

## Native Home Assistant project

This repository is a separate project rather than an ESP32 firmware variant.
It ports the protocol foundation into a Python integration that connects
through Home Assistant's Bluetooth layer, including ESPHome Bluetooth proxies,
without requiring MQTT or custom firmware on the proxy.

Subsequent development added or substantially reworked:

- Native Home Assistant discovery, config flow, devices and entities
- Bluetooth-proxy connection coordination and ordered notification processing
- Operational watchdog, reauthentication and reconnect diagnostics
- Charger-stored seven-day repeated schedules and exact readback verification
- Independent weekday schedule controls and staged editing
- Once-off delayed/duration/energy-limited charging
- Charger-clock synchronisation
- Manual and scheduled charging-session record decoding
- Unknown-packet and raw-state diagnostics
- Field validation on an Ocular LTE Plus / BESEN BS20

These additions were developed from controlled EVSEMaster and vendor-tool
Bluetooth captures, protocol analysis and live charger testing.

## Licence

The upstream project is GPL-3.0 licensed. This project is distributed under
GPL-3.0-or-later and retains the upstream attribution. See [LICENSE](LICENSE)
for the complete licence text.

The project is unofficial and is not affiliated with spudstuff, BESEN, Ocular
Charging or EVSEMaster. References to those names identify project lineage and
compatible products; they do not imply endorsement.
