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
    """Set up SEV sensors from a config entry. Only the 9 entities the user asked for."""
    coordinator: SevCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SevSensorBase] = []

    for meter in coordinator.meters:
        mid = meter.get("meter_id")
        if mid is None:
            continue
        name = meter.get("meter_name") or meter.get("serial_number") or f"Meter {mid}"
        # Order: Estimated cost til EOM, Estimated energy til EOM, Cost last month, Cost yesterday,
        # Cost today, Energy yesterday, Energy today, Energy last month, CO2 yesterday
        entities.extend([
            SevEstimatedCostSensor(coordinator, entry.entry_id, meter, name),
            SevEstimatedEnergySensor(coordinator, entry.entry_id, meter, name),
            SevCostSensor(coordinator, entry.entry_id, meter, name, "cost_last_month", "Cost last month"),
            SevCostSensor(coordinator, entry.entry_id, meter, name, "cost_yesterday", "Cost yesterday"),
            SevCostSensor(coordinator, entry.entry_id, meter, name, "cost", "Cost today"),
            SevEnergySensor(coordinator, entry.entry_id, meter, name, "usage_yesterday", "Energy yesterday"),
            SevEnergySensor(coordinator, entry.entry_id, meter, name, "usage", "Energy today"),
            SevEnergySensor(coordinator, entry.entry_id, meter, name, "usage_last_month", "Energy last month"),
            SevCo2Sensor(coordinator, entry.entry_id, meter, name, "co2_yesterday", "CO2 yesterday"),
        ])

    async_add_entities(entities)


class SevSensorBase(CoordinatorEntity[SevCoordinator], SensorEntity):
    """Base class for SEV sensors."""

    _attr_has_entity_name = True

    async def async_added_to_hass(self) -> None:
        """When entity is added, sync state from coordinator so we show data immediately."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

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
    """Energy consumption (kWh) for one meter (today or yesterday)."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key=key,
            name_suffix=name_suffix,
            device_class=SensorDeviceClass.ENERGY,
            unit=UnitOfEnergy.KILO_WATT_HOUR,
        )


class SevCo2Sensor(SevSensorBase):
    """Estimated CO2 (kg) for one meter (today or yesterday)."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key=key,
            name_suffix=name_suffix,
            device_class=SensorDeviceClass.CO2,
            unit="kg",
            state_class=SensorStateClass.MEASUREMENT,
        )


class SevCostSensor(SevSensorBase):
    """Estimated cost (DKK) for one meter (today, yesterday, or last month)."""

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the cost sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            meter=meter,
            meter_name=meter_name,
            key=key,
            name_suffix=name_suffix,
            device_class=SensorDeviceClass.MONETARY,
            unit="DKK",
            state_class=SensorStateClass.TOTAL,
        )


def _estimated_til_end_of_month(
    value_so_far: float,
    days_elapsed: int,
    days_in_month: int,
) -> float | None:
    """Linear extrapolation: (value_so_far / days_elapsed) * days_in_month. Returns None if no data."""
    if days_elapsed is None or days_elapsed < 1 or days_in_month is None:
        return None
    return round((value_so_far / days_elapsed) * days_in_month, 2)


class SevEstimatedCostSensor(CoordinatorEntity[SevCoordinator], SensorEntity):
    """Estimated cost (DKK) til end of month – extrapolated from this month so far."""

    _attr_has_entity_name = True
    _attr_name = "Estimated cost til end of month"
    _attr_native_unit_of_measurement = "DKK"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._meter_id = meter.get("meter_id")
        self._attr_unique_id = f"{entry_id}_{self._meter_id}_estimated_cost_eom"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{self._meter_id}")},
            "name": meter_name,
            "manufacturer": "SEV",
            "model": meter.get("meter_type") or "Electricity meter",
            "via_device": (DOMAIN, entry_id),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if not data:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return
        cost_this_month = _sum_readings(data.get("cost_this_month") or [], self._meter_id)
        days_elapsed = data.get("days_elapsed_this_month") or 0
        days_in_month = data.get("days_in_month") or 31
        self._attr_native_value = _estimated_til_end_of_month(
            cost_this_month, days_elapsed, days_in_month
        )
        super()._handle_coordinator_update()


class SevEstimatedEnergySensor(CoordinatorEntity[SevCoordinator], SensorEntity):
    """Estimated energy (kWh) til end of month – extrapolated from this month so far."""

    _attr_has_entity_name = True
    _attr_name = "Estimated energy til end of month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: SevCoordinator,
        entry_id: str,
        meter: dict,
        meter_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._meter_id = meter.get("meter_id")
        self._attr_unique_id = f"{entry_id}_{self._meter_id}_estimated_energy_eom"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{self._meter_id}")},
            "name": meter_name,
            "manufacturer": "SEV",
            "model": meter.get("meter_type") or "Electricity meter",
            "via_device": (DOMAIN, entry_id),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if not data:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return
        usage_this_month = _sum_readings(data.get("usage_this_month") or [], self._meter_id)
        days_elapsed = data.get("days_elapsed_this_month") or 0
        days_in_month = data.get("days_in_month") or 31
        self._attr_native_value = _estimated_til_end_of_month(
            usage_this_month, days_elapsed, days_in_month
        )
        super()._handle_coordinator_update()
