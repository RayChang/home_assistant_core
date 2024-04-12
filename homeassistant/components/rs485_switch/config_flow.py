"""Config flow for RS-485 Switch integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNT, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SLAVE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id

from .const import DOMAIN, KEY_COUNT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Wall Switch 1"): cv.string,
        vol.Required(CONF_HOST, default="10.0.4.101"): cv.string,
        vol.Required(CONF_PORT, default=4196): int,
        vol.Required(CONF_SLAVE, default=1): cv.positive_int,
        vol.Required(CONF_COUNT, default=1): vol.In(KEY_COUNT),
    }
)


class RS485SwitchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RS-485 Switch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input["entity_id"] = async_generate_entity_id(
                    DOMAIN + ".{}",
                    f"{user_input[CONF_NAME]}.{user_input[CONF_SLAVE]}",
                    hass=self.hass,
                )
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]}_{user_input[CONF_SLAVE]}",
                    data=user_input,
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

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
