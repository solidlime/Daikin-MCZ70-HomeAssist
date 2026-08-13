"""Sensor entities for the Daikin MCZ70 integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDensity,
    UnitOfTemperature,
)
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
        TemperatureSensor(coordinator, entry),
        HumiditySensor(coordinator, entry),
        PM25Sensor(coordinator, entry),
        DustSensor(coordinator, entry),
        OdorSensor(coordinator, entry),
    ])


class _BaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"daikin_mcz70_{suffix}_{entry.entry_id}"
        self._attr_device_info = device_info(entry)


class TemperatureSensor(_BaseSensor):
    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "temp")

    @property
    def native_value(self) -> float | None:
        val = (self.coordinator.data or {}).get("htemp")
        try:
            return float(val) if val not in (None, "") else None
        except ValueError:
            return None


class HumiditySensor(_BaseSensor):
    _attr_translation_key = "humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "hum")

    @property
    def native_value(self) -> int | None:
        val = (self.coordinator.data or {}).get("hhum")
        try:
            return int(val) if val not in (None, "") else None
        except ValueError:
            return None


class PM25Sensor(_BaseSensor):
    _attr_name = "PM2.5"
    _attr_device_class = SensorDeviceClass.PM25
    _attr_native_unit_of_measurement = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "pm25")

    @property
    def native_value(self) -> float | None:
        val = (self.coordinator.data or {}).get("pm25")
        try:
            return float(val) if val not in (None, "") else None
        except ValueError:
            return None


class DustSensor(_BaseSensor):
    _attr_translation_key = "dust"
    _attr_native_unit_of_measurement = "μg/m³"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "dust")

    @property
    def native_value(self) -> float | None:
        val = (self.coordinator.data or {}).get("dust")
        try:
            return float(val) if val not in (None, "") else None
        except ValueError:
            return None


class OdorSensor(_BaseSensor):
    _attr_translation_key = "odor"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "odor")

    @property
    def native_value(self) -> int | None:
        val = (self.coordinator.data or {}).get("odor")
        try:
            return int(val) if val not in (None, "") else None
        except ValueError:
            return None
