"""Fan entity for the Daikin MCZ70 integration."""

from __future__ import annotations

import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import current_params, device_info
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Device modes 0-5. The operation mode (acOpeMode: purification/dehumidify/
# humidify) is independent of the fan mode and is exposed via the operation
# mode select instead of as a preset.
_MODE_TO_LABEL = {
    "0": "自動",
    "1": "おまかせ",
    "2": "節電",
    "3": "花粉",
    "4": "のどはだ",
    "5": "サーキュ",
}
_LABEL_TO_MODE = {v: k for k, v in _MODE_TO_LABEL.items()}
# 手動 is mode 0 with a manually selected airvol (fan speed select becomes active).
_LABEL_TO_MODE["手動"] = "0"
_PRESET_MODES = ["自動", "手動", "おまかせ", "節電", "花粉", "のどはだ", "サーキュ"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([McZ70Fan(data["coordinator"], data["cloud"], entry)])


class McZ70Fan(CoordinatorEntity, FanEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "fan"
    _attr_supported_features = (
        FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = _PRESET_MODES

    def __init__(self, coordinator, api, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"daikin_mcz70_fan_{entry.entry_id}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get("pow") == "1"

    @property
    def preset_mode(self) -> str | None:
        mode = (self.coordinator.data or {}).get("mode")
        return _MODE_TO_LABEL.get(mode or "", None)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        patch: dict = {"pow": "1"}
        if preset_mode is not None:
            patch.update(self._mode_patch(preset_mode))
        await self._set(patch)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set({"pow": "0"})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._set({"pow": "1", **self._mode_patch(preset_mode)})

    def _mode_patch(self, preset_mode: str) -> dict:
        mode = _LABEL_TO_MODE.get(preset_mode)
        if mode is None:
            raise ValueError(f"Unknown preset mode: {preset_mode}")
        if preset_mode == "自動":
            # 自動: airvol=0 means fan speed is automatic
            return {"mode": "0", "airvol": "0"}
        # 手動 keeps the current airvol so the fan speed select stays usable.
        return {"mode": mode}

    async def _set(self, patch: dict) -> None:
        data = {**current_params(self.coordinator), **patch}
        await self._api.set_control_info(data)
        await self.coordinator.async_request_refresh()
