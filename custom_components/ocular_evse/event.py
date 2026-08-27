"""Charging-session history events for Ocular EVSE."""

from homeassistant.components.event import EventEntity

from .const import DOMAIN
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((OcularChargingSessionEvent(client),))


class OcularChargingSessionEvent(OcularEntity, EventEntity):
    """Emit one recorder-backed event for each unique charger record."""

    _attr_translation_key = "charging_session"
    _attr_event_types = ["completed"]
    _attr_icon = "mdi:ev-station"

    def __init__(self, client) -> None:
        super().__init__(client, "charging_session")
        self._seen: set[str] = set()

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.client.add_charging_record_listener(self._handle_record)
        )

    def _handle_record(self, record: dict[str, object]) -> None:
        record_id = str(record.get("charge_id") or "")
        dedupe_key = record_id or repr(sorted(record.items()))
        if dedupe_key in self._seen:
            return
        self._seen.add(dedupe_key)
        self._trigger_event("completed", dict(record))
