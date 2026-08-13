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

# Fan speed (device-tested, FW 3_15_0): 0 = automatic (fan preset 自動),
# 1-5 manual levels.
_AIRVOL_TO_LABEL = {"0": "自動", "1": "しずか", "2": "弱", "3": "標準", "4": "高", "5": "ターボ"}
_LABEL_TO_AIRVOL = {v: k for k, v in _AIRVOL_TO_LABEL.items()}

# MCZ70 humidity level (manual "しつど設定"): 1-4 apply while humidifying
# (acOpeMode=2). The operation mode itself is driven by acOpeMode, not humd.
_HUMD_TO_LABEL = {"1": "低め", "2": "標準", "3": "高め", "4": "連続"}
_LABEL_TO_HUMD = {v: k for k, v in _HUMD_TO_LABEL.items()}

# MCZ704A LED (device-tested, FW 3_15_0): Bright = led_dsp "-" (the device
# reports "-" when the "brighten" button is pressed; sending 0 is ignored by
# the cloud server even though it answers ret=OK). 1 = dim, 2 = off.
_LED_TO_LABEL = {"-": "明", "1": "暗め", "2": "消灯"}
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
    humidify toggle it. Driven by acOpeMode (0 = air purification only,
    1 = dehumidifying, 2 = humidifying) — device-tested on FW 3.15.0, where
    the old humd=5 dehumidify signal is no longer acted on."""

    _attr_translation_key = "operation_mode"
    _attr_options = ["空気清浄", "除湿空気清浄", "加湿空気清浄"]

    _AC_OPE_MODE = {"空気清浄": "0", "除湿空気清浄": "1", "加湿空気清浄": "2"}

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "mode")

    @property
    def current_option(self) -> str | None:
        ac_ope_mode = (self.coordinator.data or {}).get("acOpeMode")
        if ac_ope_mode == "0":
            return "空気清浄"
        if ac_ope_mode == "1":
            return "除湿空気清浄"
        if ac_ope_mode == "2":
            return "加湿空気清浄"
        return None

    async def async_select_option(self, option: str) -> None:
        ac_ope_mode = self._AC_OPE_MODE.get(option)
        if ac_ope_mode is None:
            _LOGGER.error("Unknown operation mode option: %s", option)
            return
        # acOpeMode is appended to the full-send params; humd is left untouched
        # (device-tested: an acOpeMode-less set keeps the current operation mode).
        await self._set({"acOpeMode": ac_ope_mode})


class AirvolSelect(_BaseSelect):
    """Fan speed (manual "風量"). Always operable — the physical air volume
    button works in every operation mode, and a full-send set (current
    params + airvol) is applied by the device (device-tested FW 3.15.0;
    single-parameter sends may be ignored by the server)."""

    _attr_translation_key = "fan_speed"
    _attr_options = list(_AIRVOL_TO_LABEL.values())

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "airvol")

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
    """Humidity level (manual "しつど設定"). Always operable — the physical
    button works regardless of operation mode; the level is sent as humd
    1-4 and is applied during the next humidifying run. Sent via full-send
    (device-tested FW 3.15.0; single-parameter sends may be ignored)."""

    _attr_translation_key = "humidity_mode"
    _attr_options = list(_HUMD_TO_LABEL.values())

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator, api, entry, "humd")

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
    """LED brightness: 明 = led_dsp "-", 暗め = 1, 消灯 = 2.

    Device-tested (FW 3_15_0): the device reports "-" for bright and the
    cloud server ignores led_dsp=0 (returns ret=OK but nothing changes),
    so 0 is intentionally not offered.
    """

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
        # Send the raw value as-is ("-" included): cloud accepts it (ret=OK).
        await self._api.set_device_setting({"led_dsp": val})
        await self.coordinator.async_request_refresh()
