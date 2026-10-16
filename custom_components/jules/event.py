"""Event platform for Google Jules integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_EVENT_ENTITY, DOMAIN
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules event entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    entity = JulesSessionEventEntity(coordinator, entry)
    data[DATA_EVENT_ENTITY] = entity
    coordinator.event_entity = entity
    async_add_entities([entity])


class JulesSessionEventEntity(
    CoordinatorEntity[JulesDataUpdateCoordinator], EventEntity
):
    """Event entity for Jules coding session lifecycle events."""

    _attr_has_entity_name = True
    _attr_name = "Session Event"
    _attr_icon = "mdi:bell-ring-outline"
    _attr_event_types = [
        "session_started",
        "plan_awaiting_approval",
        "session_completed",
        "session_failed",
    ]

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Jules session event entity."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_session_event"
        self._attr_device_info = get_device_info(entry)

    @callback
    def trigger_session_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Trigger event entity and record attributes."""
        if event_type in self._attr_event_types:
            self._trigger_event(event_type, data)
            self.async_write_ha_state()
