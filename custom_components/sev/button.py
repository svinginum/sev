"""SEV button to fetch data now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SevCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SEV fetch-now button from a config entry."""
    coordinator: SevCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SevFetchDataButton(coordinator, entry)])


class SevFetchDataButton(ButtonEntity):
    """Button that triggers an immediate SEV data fetch."""

    _attr_has_entity_name = True
    _attr_name = "Fetch data now"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: SevCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_fetch_data_now"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "SEV",
        }

    async def async_press(self) -> None:
        """Trigger an immediate refresh of SEV data."""
        await self._coordinator.async_request_refresh()
