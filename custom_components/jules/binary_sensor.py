"""Binary sensor platform for the Google Jules integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


@dataclass(frozen=True, kw_only=True)
class JulesBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Jules binary sensor entities."""

    is_on_fn: Callable[[JulesDataUpdateCoordinator], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[JulesBinarySensorDescription, ...] = (
    JulesBinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda coord: coord.last_update_success,
    ),
    JulesBinarySensorDescription(
        key="working",
        translation_key="working",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:robot-industrial",
        is_on_fn=lambda coord: bool(
            coord.data and coord.data.get("active_sessions", 0) > 0
        ),
    ),
    JulesBinarySensorDescription(
        key="action_required",
        translation_key="action_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-decagram",
        is_on_fn=lambda coord: bool(
            coord.data and coord.data.get("awaiting_approval", 0) > 0
        ),
    ),
    JulesBinarySensorDescription(
        key="quota_exceeded",
        translation_key="quota_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle-outline",
        is_on_fn=lambda coord: bool(
            coord.data and coord.data.get("remaining_quota", 100) <= 0
        ),
    ),
    JulesBinarySensorDescription(
        key="pr_ready",
        translation_key="pr_ready",
        icon="mdi:git-pull-request",
        entity_registry_enabled_default=False,
        is_on_fn=lambda coord: bool(coord.data and bool(coord.data.get("latest_pr"))),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules binary sensors based on a config entry."""
    coordinator: JulesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        JulesBinarySensorEntity(
            coordinator=coordinator, description=description, entry=entry
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class JulesBinarySensorEntity(
    CoordinatorEntity[JulesDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Google Jules binary sensor entity."""

    entity_description: JulesBinarySensorDescription

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        description: JulesBinarySensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

        self._attr_device_info = get_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator)
