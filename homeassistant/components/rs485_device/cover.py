"""RS485 Curtain component."""
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """通過配置條目設置開關實體."""

    # 從 entry.data 中獲取配置數據
    config = {
        **entry.data,
        "entry_id": entry.entry_id,
    }

    async_add_entities([RS485CurtainCover(hass, config)], True)


class RS485CurtainCover(CoverEntity):
    """表示一个窗帘类的 cover 设备."""

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.CURTAIN

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """初始化窗帘 cover 实体."""
        self._is_open = True
        self._entry_id: str = config.get("entry_id", "")
        self._name: str = f"{config.get(CONF_NAME)}"
        self._unique_id: str = f"{self._entry_id}"
        self._position = 100  # 完全打开

    @property
    def name(self) -> str:
        """返回实体的名字."""
        return self._name

    @property
    def unique_id(self) -> str:
        """返回實體的唯一 ID."""
        return self._unique_id

    @property
    def is_closed(self) -> bool:
        """如果窗帘关闭返回 True."""
        return not self._is_open

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        device = self.hass.data[DOMAIN][self._entry_id]["device"]
        return {
            "identifiers": device.identifiers,
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "connections": device.connections,
        }

    @property
    def supported_features(self) -> CoverEntityFeature:
        """返回该实体支持的功能."""
        supported_features = CoverEntityFeature(0)
        if self.current_cover_position is not None:
            supported_features |= (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION
            )

        return supported_features

    @property
    def current_cover_position(self) -> int | None:
        """返回当前窗帘的位置."""
        return self._position

    def open_cover(self, **kwargs: Any) -> None:
        """打开窗帘."""
        _LOGGER.info("Opening the curtain")
        self._is_open = True
        self._position = 100
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs: Any) -> None:
        """关闭窗帘."""
        _LOGGER.info("Closing the curtain")
        self._is_open = False
        self._position = 0
        self.schedule_update_ha_state()

    def set_cover_position(self, **kwargs: Any) -> None:
        """设置窗帘的位置."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.info("Setting the curtain position to %s", position)
            self._position = position
            self._is_open = position > 0
            self.schedule_update_ha_state()
            self.schedule_update_ha_state()
