"""Sensor platform for the Google Jules integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BRANCH,
    ATTR_CREATED_TIME,
    ATTR_ERROR_MESSAGE,
    ATTR_PLAN,
    ATTR_PR_URL,
    ATTR_PROMPT,
    ATTR_SESSION_ID,
    ATTR_SOURCE,
    ATTR_TITLE,
    ATTR_UPDATED_TIME,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


@dataclass(frozen=True, kw_only=True)
class JulesSensorDescription(SensorEntityDescription):
    """Class describing Jules sensor entities."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[JulesSensorDescription, ...] = (
    JulesSensorDescription(
        key="total_sessions",
        translation_key="total_sessions",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("total_sessions", 0),
    ),
    JulesSensorDescription(
        key="active_sessions",
        translation_key="active_sessions",
        icon="mdi:robot",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("active_sessions", 0),
    ),
    JulesSensorDescription(
        key="awaiting_approval",
        translation_key="awaiting_approval",
        icon="mdi:account-clock",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("awaiting_approval", 0),
    ),
    JulesSensorDescription(
        key="completed_sessions",
        translation_key="completed_sessions",
        icon="mdi:check-circle-outline",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("completed_sessions", 0),
    ),
    JulesSensorDescription(
        key="failed_sessions",
        translation_key="failed_sessions",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("failed_sessions", 0),
    ),
    JulesSensorDescription(
        key="sources_count",
        translation_key="sources_count",
        icon="mdi:source-repository",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("sources_count", 0),
        attributes_fn=lambda data: {
            "sources": [
                s.get("name") or s.get("id") or s for s in data.get("sources", [])
            ]
        },
    ),
    JulesSensorDescription(
        key="latest_session",
        translation_key="latest_session",
        icon="mdi:git",
        value_fn=lambda data: (
            (data.get("latest_session") or {}).get("state", "idle").lower()
            if data.get("latest_session")
            else "idle"
        ),
        attributes_fn=lambda data: (
            _extract_latest_session_attributes(data.get("latest_session"))
            if data.get("latest_session")
            else {}
        ),
    ),
)


def _extract_latest_session_attributes(
    session: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract formatted attributes from session dictionary."""
    if not session:
        return {}
    return {
        ATTR_SESSION_ID: session.get("name") or session.get("id"),
        "status": session.get("status") or "stable",
        "url": (
            f"https://jules.google.com/task/{session.get('id')}"
            if session.get("id")
            else None
        ),
        ATTR_TITLE: session.get("title"),
        ATTR_PROMPT: session.get("prompt"),
        ATTR_SOURCE: session.get("source"),
        ATTR_BRANCH: session.get("branch"),
        ATTR_PR_URL: session.get("pullRequestUrl") or session.get("pr_url"),
        ATTR_PLAN: session.get("plan"),
        ATTR_ERROR_MESSAGE: session.get("errorMessage") or session.get("error"),
        ATTR_CREATED_TIME: session.get("createTime") or session.get("created_at"),
        ATTR_UPDATED_TIME: session.get("updateTime") or session.get("updated_at"),
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules sensors based on a config entry."""
    coordinator: JulesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        JulesSensorEntity(coordinator=coordinator, description=description, entry=entry)
        for description in SENSOR_DESCRIPTIONS
    )


class JulesSensorEntity(CoordinatorEntity[JulesDataUpdateCoordinator], SensorEntity):
    """Representation of a Google Jules sensor entity."""

    entity_description: JulesSensorDescription

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        description: JulesSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

        self._attr_device_info = get_device_info(entry)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or not self.entity_description.attributes_fn:
            return {}
        return self.entity_description.attributes_fn(self.coordinator.data)
