"""Sensors for Ocular EVSE."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower, UnitOfTemperature, UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.entity import EntityCategory

from .const import DEVICE_DIAGNOSTICS, DEVICE_MAIN, DEVICE_REPEATED, DOMAIN
from .entity import OcularEntity


@dataclass(frozen=True, kw_only=True)
class OcularSensorDescription(SensorEntityDescription):
    state_attr: str
    always_available: bool = False
    source_attr: str | None = None
    device_group: str = DEVICE_MAIN


SENSORS = (
    OcularSensorDescription(key="status", translation_key="status", state_attr="status"),
    OcularSensorDescription(key="plug_state", translation_key="plug_state", state_attr="plug_state"),
    OcularSensorDescription(key="output_state", translation_key="output_state", state_attr="output_state"),
    OcularSensorDescription(key="protocol_state", translation_key="protocol_state", state_attr="protocol_state", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="raw_plug_state", translation_key="raw_plug_state", state_attr="raw_plug_state", source_attr="raw_plug_state_source", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="raw_output_state", translation_key="raw_output_state", state_attr="raw_output_state", source_attr="raw_output_state_source", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="raw_protocol_state", translation_key="raw_protocol_state", state_attr="raw_protocol_state", source_attr="raw_protocol_state_source", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="power", translation_key="power", state_attr="power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="total_energy", translation_key="total_energy", state_attr="total_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING),
    OcularSensorDescription(key="session_energy", translation_key="session_energy", state_attr="session_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL),
    OcularSensorDescription(key="session_duration", translation_key="session_duration", state_attr="session_duration", native_unit_of_measurement=UnitOfTime.SECONDS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="session_max_current", translation_key="session_max_current", state_attr="session_max_current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="l1_voltage", translation_key="voltage", state_attr="l1_voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="l1_current", translation_key="current", state_attr="l1_current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="temperature", translation_key="temperature", state_attr="temperature", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    OcularSensorDescription(key="errors", translation_key="errors", state_attr="errors", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_command_result", translation_key="last_command_result", state_attr="last_command_result", entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="rssi", translation_key="rssi", state_attr="rssi", native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT, device_class=SensorDeviceClass.SIGNAL_STRENGTH, state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_packet_received", translation_key="last_packet_received", state_attr="last_packet_received", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_operational_packet_received", translation_key="last_operational_packet_received", state_attr="last_operational_packet_received", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_packet_type", translation_key="last_packet_type", state_attr="last_packet_type", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_unknown_packet", translation_key="last_unknown_packet", state_attr="last_unknown_packet", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="connection_uptime", translation_key="connection_uptime", state_attr="connection_uptime", native_unit_of_measurement=UnitOfTime.SECONDS, device_class=SensorDeviceClass.DURATION, entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="reconnect_count", translation_key="reconnect_count", state_attr="reconnect_count", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_reconnect", translation_key="last_reconnect", state_attr="last_reconnect", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="integration_health", translation_key="integration_health", state_attr="integration_health", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="schedule_draft", translation_key="schedule_draft", state_attr="schedule_draft_dirty", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_REPEATED),
    OcularSensorDescription(key="last_disconnect_reason", translation_key="last_disconnect_reason", state_attr="last_disconnect_reason", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="last_connection_error", translation_key="last_connection_error", state_attr="last_connection_error", entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_DIAGNOSTICS),
    OcularSensorDescription(key="schedule_last_verified", translation_key="schedule_last_verified", state_attr="schedule_last_verified", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC, always_available=True, device_group=DEVICE_REPEATED),
    OcularSensorDescription(key="last_charging_record", translation_key="last_charging_record", state_attr="last_charging_record", always_available=True),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(OcularSensor(client, description) for description in SENSORS)


class OcularSensor(OcularEntity, SensorEntity):
    entity_description: OcularSensorDescription

    def __init__(self, client, description) -> None:
        super().__init__(client, description.key, description.device_group)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.entity_description.state_attr == "connection_uptime":
            connected_since = self.client.state.connected_since
            if not self.client.state.connected or connected_since is None:
                return 0
            return round((datetime.now(timezone.utc) - connected_since).total_seconds())
        return getattr(self.client.state, self.entity_description.state_attr)

    @property
    def available(self) -> bool:
        return self.entity_description.always_available or super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.source_attr is not None:
            return {
                "source_packet": getattr(
                    self.client.state, self.entity_description.source_attr
                )
            }
        if self.entity_description.state_attr == "last_packet_type":
            command = self.client.state.last_packet_command
            return {
                "command": None if command is None else f"0x{command:04X}",
                "payload_length": self.client.state.last_packet_payload_length,
                "direction": "Received",
                "total_packets": self.client.state.total_packet_count,
                "operational_packets": self.client.state.operational_packet_count,
                "login_beacons": self.client.state.login_beacon_count,
                "consecutive_login_beacons": self.client.state.consecutive_login_beacon_count,
                "reauthentication_count": self.client.state.reauthentication_count,
                "command_counts": dict(self.client.state.packet_command_counts),
            }
        if self.entity_description.state_attr == "last_unknown_packet":
            command = self.client.state.last_unknown_packet_command
            received = self.client.state.last_unknown_packet_received
            return {
                "command": None if command is None else f"0x{command:04X}",
                "payload_length": self.client.state.last_unknown_packet_payload_length,
                "direction": "Received",
                "received_at": None if received is None else received.isoformat(),
            }
        if self.entity_description.state_attr == "last_connection_error":
            occurred = self.client.state.last_connection_error_time
            return {
                "occurred_at": None if occurred is None else occurred.isoformat(),
            }
        if self.entity_description.state_attr == "last_charging_record":
            return dict(self.client.state.last_charging_record_data)
        if self.entity_description.state_attr == "schedule_draft_dirty":
            state = self.client.state
            return {
                "enabled_days": list(state.schedule_draft_enabled_days),
                "start_minutes": list(state.schedule_draft_start_minutes),
                "duration_minutes": list(state.schedule_draft_duration_minutes),
            }
        return None
