"""RS485 switch component."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNT, CONF_NAME, CONF_SLAVE, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_STATE, DOMAIN, PLACEHOLDER
from .rs485_tcp_publisher import RS485TcpPublisher

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """通過配置條目設置開關實體."""

    # 獲取實體註冊表
    entity_reg = er.async_get(hass)
    modbus_switch_sensor_entity_id = entity_reg.async_get_entity_id(
        "sensor", "modbus", f"wall_switch_status_{entry.data[CONF_SLAVE]}"
    )

    # 從 entry.data 中獲取配置數據
    config = {
        **entry.data,
        "entry_id": entry.entry_id,
        "sensor_id": modbus_switch_sensor_entity_id,
        "modbus": ModbusHub(hass, entry.data[CONF_SLAVE]),
    }

    switch_count = entry.data.get(CONF_COUNT, 1)
    switches = []
    for i in range(switch_count):
        switches.append(RS485Switch(hass, config, i + 1))
        # 添加開關實體到 Home Assistant
    async_add_entities(switches, True)


class ModbusHub:
    """表示 Modbus 通信的主機."""

    def __init__(self, hass: HomeAssistant, unit: int) -> None:
        """Initialize the RS485Switch class."""
        self.hass = hass
        self._unit = unit
        self._hub = "rs-485_switch_hub"
        self._address = 0x1008

    async def write_register(self, value: int):
        """調用服務."""
        await self.hass.services.async_call(
            "modbus",
            "write_register",
            {
                "hub": self._hub,
                "unit": self._unit,  # Modbus 单元地址
                "address": self._address,  # 寄存器地址
                "value": value,  # 要写入的值
            },
            blocking=True,
        )


class RS485Switch(SwitchEntity):
    """表示一個示例開關的實體."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], switch_index: int
    ) -> None:
        """初始化开关."""
        self.hass = hass
        self._is_on = False
        self._name = config.get(CONF_NAME)
        self._slave = config.get(CONF_SLAVE)
        self._sensor_id = config.get("sensor_id")
        self._entry_id = config.get("entry_id")
        self._modbus = config.get("modbus")
        self._index = switch_index
        self._now = False
        # 使用從機ID、入口ID和開關索引來構造一個唯一識別符
        self._unique_id = f"{self._entry_id}_{self._index}"
        # 獲取 RS485TcpPublisher 實例
        self._publisher: RS485TcpPublisher = self.hass.data[DOMAIN][
            "rs485_tcp_publisher"
        ]

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
    def unique_id(self) -> str:
        """返回實體的唯一 ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """返回實體的名稱."""
        return f"{self._name} - {self._index}"

    @property
    def is_on(self) -> bool:
        """如果開關打開，返回 True."""
        return self._is_on

    async def _subscribe_callback(self, sub_id: str, data: tuple[int]) -> None:
        """訂閱回調."""
        # 检查 data 是否有足够的长度
        if len(data) < 7:
            _LOGGER.error("Data too short, received: %s", data)
            return

        slave, func, *last = data[6:]
        if slave == self._slave and sub_id == self._entry_id:
            _LOGGER.info(
                "🚧 %s - Subscribe callback 🚧 slave:%s, func:%s, last:%s",
                self._slave,
                slave,
                func,
                last,
            )

    async def async_added_to_hass(self):
        """當實體添加到 Home Assistant 時，設置狀態更新的計劃."""
        await self._publisher.start()
        await self._publisher.subscribe(self._subscribe_callback, self._entry_id)
        # 設置狀態更新的計劃
        _LOGGER.info("🚧 Added to hass 🚧 %s", self._index)

    async def async_will_remove_from_hass(self):
        """當實體從 Home Assistant 中移除時，取消計劃."""
        await self._publisher.unsubscribe(self._entry_id)
        sub_length = self._publisher.subscribers_length
        # 取消狀態更新的計劃
        _LOGGER.info("🚧 Removed from hass 🚧 %s", self._index)

        if sub_length == 0:
            await self._publisher.close()
            _LOGGER.info("🚧 Close publisher connect 🚧")

    async def async_update(self):
        """更新開關的狀態."""
        # 實現更新開關狀態的邏輯
        sensor: int = self.hass.states.get(self._sensor_id)
        if sensor is not None and sensor.state != "unavailable" and self._now is False:
            self.hass.data[DOMAIN][self._entry_id][CONF_STATE] = int(sensor.state)

        _LOGGER.info(
            "💊 Sensor 💊 %s: %s",
            self._name,
            self.hass.data[DOMAIN][self._entry_id][CONF_STATE],
        )
        state = self.hass.data[DOMAIN][self._entry_id][CONF_STATE]
        state = bin(state % DEFAULT_STATE)[2:]
        binary_string = PLACEHOLDER[: len(PLACEHOLDER) - len(state)] + state
        self._is_on = binary_string[::-1][self._index - 1] == "1"
        self._now = False

    async def async_turn_on(self, **kwargs):
        """異步打開開關."""
        # 實現打開開關的邏輯
        state = self.hass.data[DOMAIN][self._entry_id][CONF_STATE]
        value = state ^ self._index
        await self._modbus.write_register(value)
        self.hass.data[DOMAIN][self._entry_id][CONF_STATE] = value
        self._now = True
        _LOGGER.info("Turning on: %s, %i, %i", self._name, value, self._index)
        self._is_on = True
        # 在狀態變化後，通知 Home Assistant 更新狀態
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """異步關閉開關."""
        # 實現關閉開關的邏輯
        state = self.hass.data[DOMAIN][self._entry_id][CONF_STATE]
        value = state ^ self._index
        await self._modbus.write_register(value)
        self.hass.data[DOMAIN][self._entry_id][CONF_STATE] = value
        self._now = True
        _LOGGER.info("Turning off: %s, %i, %i", self._name, value, self._index)
        self._is_on = False
        # 在狀態變化後，通知 Home Assistant 更新狀態
        self.async_write_ha_state()
