"""Binary sensor entities for the Daikin MCZ70 integration (water/tank status)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import device_info
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WaterSupplySensor(coordinator, entry),
        HumdTankSensor(coordinator, entry),
        DehumdTankSensor(coordinator, entry),
    ])


class _BaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    #: coordinator data field this sensor reflects
    _field: str

    def __init__(self, coordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"daikin_mcz70_{suffix}_{entry.entry_id}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get(self._field) == "1"


class WaterSupplySensor(_BaseBinarySensor):
    _attr_translation_key = "water_supply"
    _field = "water_supply"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "water_supply")


class HumdTankSensor(_BaseBinarySensor):
    _attr_translation_key = "humd_tank"
    _field = "humd_tank"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "humd_tank")

    @property
    def is_on(self) -> bool:
        # 0 = 加湿タンク未装着（実機検証: タンクを外すと 1→0）
        return (self.coordinator.data or {}).get(self._field) == "0"


class DehumdTankSensor(_BaseBinarySensor):
    _attr_translation_key = "dehumd_tank"
    _field = "dehumd_tank"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "dehumd_tank")

    @property
    def is_on(self) -> bool:
        # 0 = 満水 or タンク未装着（実機検証: 満水時0 / 空+装着時1 / 外し時0）
        return (self.coordinator.data or {}).get(self._field) == "0"
