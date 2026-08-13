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
        WaterFullSensor(coordinator, entry),
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
    """加湿タンクの水が空（給水が必要）。実機検証済み: water_supply=1 で ON。"""

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


class WaterFullSensor(_BaseBinarySensor):
    """除湿タンク満水。挙動は未検証（実機で満水状態を作れないため）。

    実機（FW 3.15.0）の get_unit_status には water_full フラグが存在し、
    通常は 0 を返す。満水時に 1 になる想定（water_supply と同じ警告系の極性）。
    """

    _attr_translation_key = "dehumidifier_tank_full"
    _field = "water_full"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "water_full")
