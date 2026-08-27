# Security

## Reporting

Open a GitHub security advisory for vulnerabilities that could expose credentials or
operate the charger unexpectedly. Do not put a charger PIN or unredacted capture in a
public issue.

## Sensitive information

The integration stores the EVSEMaster PIN in the Home Assistant config entry, as is
normal for a local integration credential. Debug logs record command identifiers and
payload lengths, not the PIN or packet body. Charging-record attributes can contain the
configured charging-record user ID; sanitise diagnostics before sharing them.

The Bluetooth PIN is an application credential, not a substitute for physical access
control or electrical protection.
