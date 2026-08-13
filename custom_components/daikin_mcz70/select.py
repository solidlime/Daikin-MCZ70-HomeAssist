"""Select entities for the Daikin MCZ70 integration (fan speed, humidity mode, LED)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import current_params, device_info
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_AIRVOL_TO_LABEL = {"1": "弱", "2": "標準", "3": "高", "5": "最高"}
_LABEL_TO_AIRVOL = {v: k for k, v in _AIRVOL_TO_LABEL.items()}

# MCZ70 humidity setting (manual "しつど設定"): 1-4 apply while humidifying,
# independent of the fan mode. 0 and 5 are the operation-mode domain.
_HUMD_TO_LABEL = {"1": "低め", "2": "標準", "3": "高め", "4": "連続"}
_LABEL_TO_HUMD = {v: k for k, v in _HUMD_TO_LABEL.items()}

_LED_TO_LABEL = {"0": "点灯", "1": "暗め", "2": "消灯"}
_LABEL_TO_LED = {v: k for k, v in _LED_TO_LABEL.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        OperationModeSelect(data["coordinator"], data["cloud"], entry),
        AirvolSelect(data["coordinator"], data["cloud"], entry),
        HumdSelect(data["coordinator"], data["cloud"], entry),
        LedSelect(data["coordinator"], data["cloud"], entry),
    ])


class _BaseSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, entry: ConfigEntry, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"daikin_mcz70_{unique_suffix}_{entry.entry_id}"
        self._attr_device_info = device_info(entry)

    async def _set(self, patch: dict) -> None:
        data = {**current_params(self.coordinator), **patch}
        await self._api.set_control_info(data)
        await self.coordinator.async_request_refresh()


class OperationModeSelect(_BaseSelect):
    """Operation switch of the MCZ70: purification always runs, dehumidify and
    humidify toggle it. Driven by humd (0 = air purification only,
    5 = dehumidifying, 1-4 = humidifying at the chosen level)."""

    _attr_translation_key = "operation_mode"
    _attr_options = ["空気清浄", "除湿空気清浄", "加湿空気清浄"]

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "mode")

    @property
    def current_option(self) -> str | None:
        humd = (self.coordinator.data or {}).get("humd")
        if humd == "0":
            return "空気清浄"
        if humd == "5":
            return "除湿空気清浄"
        if humd in _HUMD_TO_LABEL:
            return "加湿空気清浄"
        return None

    async def async_select_option(self, option: str) -> None:
        if option == "空気清浄":
            await self._set({"humd": "0"})
        elif option == "除湿空気清浄":
            await self._set({"humd": "5"})
        elif option == "加湿空気清浄":
            # Keep the current humidify level, default to 標準 when off.
            humd = (self.coordinator.data or {}).get("humd")
            if humd not in _HUMD_TO_LABEL:
                humd = "2"
            await self._set({"humd": humd})
        else:
            _LOGGER.error("Unknown operation mode option: %s", option)


class AirvolSelect(_BaseSelect):
    _attr_translation_key = "fan_speed"
    _attr_options = list(_AIRVOL_TO_LABEL.values())

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "airvol")

    @property
    def available(self) -> bool:
        d = self.coordinator.data or {}
        return d.get("mode") == "0" and d.get("airvol", "0") != "0"

    @property
    def current_option(self) -> str | None:
        airvol = (self.coordinator.data or {}).get("airvol")
        return _AIRVOL_TO_LABEL.get(airvol or "", None)

    async def async_select_option(self, option: str) -> None:
        airvol = _LABEL_TO_AIRVOL.get(option)
        if airvol is None:
            _LOGGER.error("Unknown airvol option: %s", option)
            return
        await self._set({"airvol": airvol})


class HumdSelect(_BaseSelect):
    """Humidity level (manual "しつど設定"). Only meaningful while
    humidifying (humd 1-4); 0 (off) and 5 (dehumidifying) are operation
    modes and are handled by OperationModeSelect."""

    _attr_translation_key = "humidity_mode"
    _attr_options = list(_HUMD_TO_LABEL.values())

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "humd")

    @property
    def available(self) -> bool:
        humd = (self.coordinator.data or {}).get("humd")
        return humd in _HUMD_TO_LABEL

    @property
    def current_option(self) -> str | None:
        humd = (self.coordinator.data or {}).get("humd")
        return _HUMD_TO_LABEL.get(humd or "", None)

    async def async_select_option(self, option: str) -> None:
        humd = _LABEL_TO_HUMD.get(option)
        if humd is None:
            _LOGGER.error("Unknown humd option: %s", option)
            return
        await self._set({"humd": humd})


class LedSelect(_BaseSelect):
    _attr_translation_key = "led"
    _attr_options = list(_LED_TO_LABEL.values())
    _attr_icon = "mdi:led-variant-on"

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "led")

    @property
    def current_option(self) -> str | None:
        val = (self.coordinator.data or {}).get("led_dsp")
        return _LED_TO_LABEL.get(val or "", None)

    async def async_select_option(self, option: str) -> None:
        val = _LABEL_TO_LED.get(option)
        if val is None:
            _LOGGER.error("Unknown led option: %s", option)
            return
        await self._api.set_device_setting({"led_dsp": val})
        await self.coordinator.async_request_refresh()
