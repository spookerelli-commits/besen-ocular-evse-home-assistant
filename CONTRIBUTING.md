# Contributing

Contributions are welcome, especially compatibility reports from other BESEN
BS20, regional OEM/rebrands and EVSEMaster-compatible chargers.

## Before changing the protocol

1. Open an issue describing the brand, exact model, firmware, phase count and
   Bluetooth path.
2. Separate observation from inference. Record the command, payload length,
   direction and controlled action that produced it.
3. Never publish a PIN, complete Bluetooth address, charging-record user ID,
   unrelated Home Assistant data or unredacted HCI capture.
4. Supervise real-hardware tests. Use conservative current limits and respect
   the integration's 30-second start/stop cooldown.

## Pull requests

- Preserve entity unique IDs unless the change includes a registry migration.
- Keep BLE writes serialised, bounded by a timeout and followed by confirmation
  where the protocol supplies one.
- Add protocol fixtures or pure state-machine tests for behavioural changes.
- Update README and CHANGELOG when user-visible behaviour changes.
- Run:

  ```bash
  python -m compileall -q custom_components
  python -m unittest discover -s tests -v
  ```

The integration deliberately avoids logging credentials or raw packet bodies.
New diagnostics should follow the same rule.
