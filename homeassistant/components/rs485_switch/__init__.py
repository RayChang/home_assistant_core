"""The RS-485 Switch integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    CONF_STATE,
    CONF_SWITCHES,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MODEL
from .rs485_tcp_publisher import RS485TcpPublisher

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """獲取裝置註冊表。."""
    device_registry = dr.async_get(hass)

    # 在裝置註冊表中創建一個新的裝置
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_SLAVE])},
        name=entry.data[CONF_NAME],
        model=MODEL,
    )

    hass.data.setdefault(
        DOMAIN,
        {
            "rs485_tcp_publisher": RS485TcpPublisher(
                host=entry.data[CONF_HOST], port=entry.data[CONF_PORT], byte_length=12
            )
        },
    )
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][CONF_DEVICE] = device
    hass.data[DOMAIN][entry.entry_id][CONF_STATE] = None
    hass.data[DOMAIN][entry.entry_id][CONF_SWITCHES] = None
    hass.data[DOMAIN][entry.entry_id]["watchdog_task"] = None

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
