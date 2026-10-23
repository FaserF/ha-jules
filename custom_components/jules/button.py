"""Button platform for the Google Jules integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import JulesClient
from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    STATE_AWAITING_APPROVAL,
    STATE_AWAITING_PLAN_APPROVAL,
    STATE_AWAITING_USER_FEEDBACK,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules buttons based on a config entry."""
    coordinator: JulesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: JulesClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    async_add_entities(
        [
            JulesRefreshButton(coordinator=coordinator, entry=entry),
            JulesApprovePlanButton(coordinator=coordinator, client=client, entry=entry),
        ]
    )


class JulesRefreshButton(CoordinatorEntity[JulesDataUpdateCoordinator], ButtonEntity):
    """Button to force refresh Jules sessions and metrics."""

    def __init__(
        self, coordinator: JulesDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = ButtonEntityDescription(
            key="refresh",
            translation_key="refresh",
            icon="mdi:refresh",
        )
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_has_entity_name = True

        self._attr_device_info = get_device_info(entry)

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_request_refresh()


class JulesApprovePlanButton(
    CoordinatorEntity[JulesDataUpdateCoordinator], ButtonEntity
):
    """Button to approve the latest pending plan."""

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        client: JulesClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._client = client
        self.entity_description = ButtonEntityDescription(
            key="approve_latest_plan",
            translation_key="approve_latest_plan",
            icon="mdi:check-decagram",
        )
        self._attr_unique_id = f"{entry.entry_id}_approve_latest_plan"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(entry)

    async def async_press(self) -> None:
        """Handle the button press."""
        sessions = (self.coordinator.data or {}).get("sessions", [])
        pending_session: str | None = None

        for s in sessions:
            st = (s.get("state") or "").upper()
            if st in (
                STATE_AWAITING_APPROVAL,
                STATE_AWAITING_PLAN_APPROVAL,
                STATE_AWAITING_USER_FEEDBACK,
            ):
                pending_session = s.get("name") or s.get("id")
                break

        if not pending_session:
            raise HomeAssistantError("No sessions currently awaiting approval")

        await self._client.async_approve_plan(pending_session)
        await self.coordinator.async_request_refresh()
