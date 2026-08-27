"""Config flow for Ocular EVSE."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from .const import CONF_PIN, CONF_USER_ID, DEFAULT_USER_ID, DOMAIN


def _schema(default_address: str = "") -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_ADDRESS, default=default_address): str,
        vol.Required(CONF_PIN): vol.All(str, vol.Length(min=6, max=6)),
        vol.Optional(CONF_USER_ID, default=DEFAULT_USER_ID): vol.All(str, vol.Length(min=1, max=16)),
    })


class OcularEvseConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._address = ""

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        self._address = discovery_info.address
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": discovery_info.name or self._address}
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            try:
                user_input[CONF_PIN].encode("ascii")
                user_input[CONF_USER_ID].encode("ascii")
            except UnicodeEncodeError:
                errors["base"] = "ascii_only"
            if not errors:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="BESEN / Ocular EVSE",
                    data={**user_input, CONF_ADDRESS: address},
                )
        return self.async_show_form(step_id="user", data_schema=_schema(self._address), errors=errors)
