"""Button platform for the Danske Fragtmænd parcel tracker integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DanskeFragtmaendConfigEntry
from .device import ATTRIBUTION, build_device_info

# A manual refresh is a single API round-trip per tracked parcel; HA's
# per-entity throttling adds nothing here.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DanskeFragtmaendConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Danske Fragtmænd refresh button from a config entry."""
    async_add_entities([DanskeFragtmaendRefreshButton(entry)])


class DanskeFragtmaendRefreshButton(ButtonEntity):
    """Button that forces an immediate poll of all tracked Danske Fragtmænd parcels."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_attribution = ATTRIBUTION

    def __init__(self, entry: DanskeFragtmaendConfigEntry) -> None:
        """Initialize the button."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = build_device_info(entry)

    async def async_press(self) -> None:
        """Trigger an immediate refresh of the coordinator."""
        await self._entry.runtime_data.coordinator.async_request_refresh()
