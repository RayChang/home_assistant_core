"""Constants for the RS-485 Switch integration."""

from typing import Final

from homeassistant.const import CONF_COVERS, CONF_SENSORS, CONF_SWITCHES

DOMAIN: Final = "rs485_switch"
MODBUS_HUB: Final = "rs-485_switch_hub"
MODEL: Final = "LP-F8"
DEFAULT_STATE: Final = 256
PLACEHOLDER: Final = "00000000"
REGISTER_ADDRESS: Final = 0x1008

# 按鈕數量
KEY_COUNT: Final = list(range(1, 7))

# 含有繼電器
HAS_RELAY: Final = "has_relay"

# 設備類型
DEVICE_TYPE: Final = {
    CONF_SWITCHES: CONF_SWITCHES,
    CONF_COVERS: CONF_COVERS,
    CONF_SENSORS: CONF_SENSORS,
}
