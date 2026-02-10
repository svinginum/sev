"""SEV sensors: energy, CO2, cost per meter."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CUMULATIVE_VALUE,
    ATTR_READING,
    ATTR_READINGS,
    ATTR_UNIT,
    DOMAIN,
)
from .coordinator import SevCoordinator

_LOGGER = logging.getLogger(__name__)


def _sum_readings(response_list: list, meter_id: int) -> float:
    """Sum 'reading' values for a meter from API response list (usage/CO2/cost)."""
    mid_str = str(meter_id)
    for item in response_list:
        if str(item.get("meter_id")) == mid_str:
            readings = item.get("readings") or []
            return sum(float(r.get(ATTR_READING, 0) or 0) for r in readings)
    return 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SEV sensors from a config entry."""
    coordinator: SevCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SevSensor] = []

    for meter in coordinator.meters:
        mid = meter.get("meter_id")
        if mid is None:
            continue
        name = meter.get("meter_name") or meter.get("serial_number") or f"Meter {mid}"
        entities.extend([
            SevEnergySensor(coordinator, entry.entry_id, meter, name),
            SevCo2Sensor(coordinator, entry.entry_id, meter, name),
            SevCostSensor(coordinator, entry.entry_id, meter, name),
        ])

    async_add_entities(entities)


class SevSensorBase(CoordinatorEntity[SevCoordinator], SensorEntity):
    """Base class for SEV sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
        key: str,
        name_suffix: str,
        device_class: SensorDeviceClass | None,
        unit: str,
        state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._meter = meter
        self._meter_id = meter.get("meter_id")
        self._key = key
        self._attr_name = name_suffix
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_unique_id = f"{entry_id}_{self._meter_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{self._meter_id}")},
            "name": meter_name,
            "manufacturer": "SEV",
            "model": meter.get("meter_type") or "Electricity meter",
            "via_device": (DOMAIN, entry_id),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if not data:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return
        lst = data.get(self._key) or []
        value = _sum_readings(lst, self._meter_id)
        self._attr_native_value = round(value, 2)
        super()._handle_coordinator_update()


class SevEnergySensor(SevSensorBase):
    """Today's energy consumption (kWh) for one meter."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key="usage",
            name_suffix="Energy today",
            device_class=SensorDeviceClass.ENERGY,
            unit=UnitOfEnergy.KILO_WATT_HOUR,
        )


class SevCo2Sensor(SevSensorBase):
    """Estimated CO2 (kg) for today for one meter."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
    ) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key="co2",
            name_suffix="CO2 today",
            device_class=SensorDeviceClass.CO2,
            unit="kg",
            state_class=SensorStateClass.MEASUREMENT,
        )


class SevCostSensor(SevSensorBase):
    """Estimated cost (DKK) for today for one meter."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
    ) -> None:
        """Initialize the cost sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key="cost",
            name_suffix="Cost today",
            device_class=SensorDeviceClass.MONETARY,
            unit="DKK",
            state_class=SensorStateClass.TOTAL,
        )
