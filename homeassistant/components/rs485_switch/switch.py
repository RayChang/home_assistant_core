"""RS485 switch component."""
import asyncio
from datetime import timedelta
import logging
import math
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COUNT,
    CONF_NAME,
    CONF_SLAVE,
    CONF_STATE,
    CONF_SWITCHES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_STATE, DOMAIN, PLACEHOLDER, REGISTER_ADDRESS
from .rs485_tcp_publisher import RS485TcpPublisher

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """通過配置條目設置開關實體."""

    # 從 entry.data 中獲取配置數據
    config = {
        **entry.data,
        "entry_id": entry.entry_id,
    }

    switch_count = entry.data.get(CONF_COUNT, 1)
    switches = []
    for i in range(switch_count):
        switches.append(RS485Switch(hass, config, i + 1))
    async_add_entities(switches, True)


class RS485Switch(SwitchEntity):
    """表示一個示例開關的實體."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], switch_index: int
    ) -> None:
        """初始化開關."""
        self.hass = hass
        self._is_on: bool = False
        self._name: str = config.get(CONF_NAME, "")
        self._slave: int = config.get(CONF_SLAVE, 0)
        self._state: int = DEFAULT_STATE
        self._entry_id: str = config.get("entry_id", "")
        self._index: int = switch_index
        self._unique_id: str = f"{self._entry_id}_{self._index}"
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

    def _binary_list_to_int(self, binary_list: list[int]) -> int:
        """將二進制列表轉換為整數."""
        high_byte = binary_list[0]
        low_byte = binary_list[1]
        result = (high_byte << 8) + (low_byte & 0xFF)
        return result

    async def _watchdogs(self):
        """監控 Publisher 是否運行."""
        watchdog_task: asyncio.Task = self.hass.data[DOMAIN][self._entry_id][
            "watchdog_task"
        ]
        try:
            while True:
                _LOGGER.warning(
                    "❓ Publisher is running?: %s ❓", self._publisher.is_running
                )
                if self._publisher.is_running:
                    await asyncio.sleep(0.1 + self._slave / 10)
                    await asyncio.wait_for(
                        self._publisher.read_register(self._slave, REGISTER_ADDRESS, 1),
                        timeout=2 * self._slave,
                    )
                    watchdog_task.cancel()
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            _LOGGER.info("Watchdog task was cancelled")
            return

    async def _handle_switch(self, is_on: bool) -> None:
        """處理開關的切換."""
        self.hass.data[DOMAIN][self._entry_id][CONF_SWITCHES] = self._index
        await self._publisher.read_register(self._slave, REGISTER_ADDRESS, 1)
        await asyncio.sleep(0.1)
        state = self.hass.data[DOMAIN][self._entry_id][CONF_STATE]
        value = state ^ self._index
        await self._publisher.write_register(self._slave, REGISTER_ADDRESS, value)
        self.hass.data[DOMAIN][self._entry_id][CONF_STATE] = value
        self._is_on = is_on
        self.async_write_ha_state()

    async def _subscribe_callback(self, sub_id: str, data: tuple[int]) -> None:
        """訂閱回調."""

        if len(data) < 8:
            _LOGGER.error("Data too short, received: %s", data)
            return

        _LOGGER.info(
            "🚧 Subscribe callback DATA:%s 🚧 ",
            data,
        )

        length, slave, function_code, *last = data[5:]
        if length == 6 and function_code == 3:
            self.hass.data[DOMAIN][self._entry_id][CONF_SWITCHES] = (
                int(math.log(last[len(last) - 1], 2)) + 1
            )

        switch_index = self.hass.data[DOMAIN][self._entry_id][CONF_SWITCHES]
        if slave == self._slave:
            if switch_index == self._index:
                _LOGGER.info(
                    "🚧 Subscribe callback DATA:%s / SLAVE: %s / INDEX: %s / index: %s / LAST: %s 🚧 ",
                    self._slave,
                    data,
                    switch_index,
                    self._index,
                    last,
                )

                if function_code == 3:
                    if length == 5:
                        self.hass.data[DOMAIN][self._entry_id][
                            CONF_STATE
                        ] = self._binary_list_to_int(last[-2:])
                    elif length == 6:
                        await self._publisher.read_register(
                            self._slave, REGISTER_ADDRESS, 1
                        )
                elif function_code == 6:
                    self.hass.data[DOMAIN][self._entry_id][
                        CONF_STATE
                    ] = self._binary_list_to_int(last[-2:])
            elif (function_code == 3 and length == 5) or function_code == 6:
                self.hass.data[DOMAIN][self._entry_id][
                    CONF_STATE
                ] = self._binary_list_to_int(last[-2:])

        await self.async_update()

    async def async_added_to_hass(self):
        """當實體添加到 Home Assistant 時，設置狀態更新的計劃."""
        await self._publisher.start()
        await self._publisher.subscribe(self._subscribe_callback, self._unique_id)
        if self.hass.data[DOMAIN][self._entry_id]["watchdog_task"] is None:
            self.hass.data[DOMAIN][self._entry_id][
                "watchdog_task"
            ] = asyncio.create_task(self._watchdogs())
        # 設置狀態更新的計劃
        _LOGGER.info("🚧 Added to hass 🚧 %s", self._index)

    async def async_will_remove_from_hass(self):
        """當實體從 Home Assistant 中移除時，取消計劃."""
        await self._publisher.unsubscribe(self._unique_id)
        sub_length = self._publisher.subscribers_length
        # 取消狀態更新的計劃
        _LOGGER.info("🚧 Removed from hass 🚧 %s", self._index)

        if sub_length == 0:
            await self._publisher.close()
            _LOGGER.info("🚧 Close publisher connect 🚧")

    async def async_update(self):
        """更新開關的狀態."""
        state = self.hass.data[DOMAIN][self._entry_id][CONF_STATE]
        _LOGGER.info(
            "🚧 ------- SLAVE: %s / STATE:%s / index: %s ------- 🚧",
            self._slave,
            state,
            self._index,
        )

        if state is not None:
            state_str = bin(state % DEFAULT_STATE)[2:]
            binary_string = PLACEHOLDER[: len(PLACEHOLDER) - len(state_str)] + state_str
            self._is_on = binary_string[::-1][self._index - 1] == "1"
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """異步打開開關."""
        # 實現打開開關的邏輯
        await self._handle_switch(True)

    async def async_turn_off(self, **kwargs):
        """異步關閉開關."""
        # 實現關閉開關的邏輯
        await self._handle_switch(False)
