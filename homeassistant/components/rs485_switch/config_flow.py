"""Config flow for RS-485 Switch integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_COUNT,
    CONF_COVERS,
    CONF_DEVICE,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_SWITCHES,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id

from .const import DEVICE_TYPE, DOMAIN, HAS_RELAY, KEY_COUNT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="10.0.4.101"): cv.string,
        vol.Required(CONF_PORT, default=4196): int,
        vol.Required(CONF_DEVICE, default=CONF_SWITCHES): vol.In(DEVICE_TYPE),
    }
)

STEP_SWITCH_CONFIG_SCHEMA = {
    vol.Required(CONF_SLAVE, default=1): cv.positive_int,
    vol.Required(CONF_COUNT, default=1): vol.In(KEY_COUNT),
    vol.Required(HAS_RELAY, default=True): cv.boolean,
}
STEP_COVERS_CONFIG_SCHEMA = {
    vol.Required(CONF_TYPE, default=True): cv.boolean,
    vol.Required(CONF_COUNT, default=1): vol.In(KEY_COUNT),
}
STEP_SENSORS_CONFIG_SCHEMA = {
    vol.Required(CONF_NAME, default="Wall Switch"): cv.string,
    vol.Required(CONF_SLAVE, default=1): cv.positive_int,
}

DEVICE_SCHEMA = {
    CONF_SWITCHES: STEP_SWITCH_CONFIG_SCHEMA,
    CONF_COVERS: STEP_COVERS_CONFIG_SCHEMA,
    CONF_SENSORS: STEP_SENSORS_CONFIG_SCHEMA,
}


class RS485SwitchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RS-485 Switch."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.rs485_config = {}

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step of the config flow."""
        if user_input is not None:
            self.rs485_config.update(user_input)
            return await self.async_step_device_config()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_device_config(
        self, user_input: Optional[dict[str, Any]] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self.rs485_config.update(user_input)
            try:
                self.rs485_config[CONF_ENTITY_ID] = async_generate_entity_id(
                    DOMAIN + ".{}",
                    f"{self.rs485_config[CONF_NAME]}.{self.rs485_config[CONF_DEVICE]}.{self.rs485_config[CONF_SLAVE]}",
                    hass=self.hass,
                )
                return self.async_create_entry(
                    title=f"{self.rs485_config[CONF_NAME]} Configuration",
                    data=self.rs485_config,
                )
            except ValueError as e:
                _LOGGER.exception("Error generating entity ID: %s", e)
                errors["base"] = "entity_id_error"
            except KeyError as e:
                _LOGGER.exception("Missing required input: %s", e)
                errors["base"] = "missing_input"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", e)
                errors["base"] = "unknown"

        device_type = self.rs485_config[CONF_DEVICE]
        return self.async_show_form(
            step_id="device_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Wall Switch"): cv.string,
                    vol.Required(CONF_SLAVE, default=1): cv.positive_int,
                    **DEVICE_SCHEMA[device_type],
                }
            ),
        )
