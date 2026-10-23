"""Switch platform for Google Jules integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import JulesClient
from .const import (
    CONF_AUTO_APPROVE,
    CONF_TOKEN_COMPRESSION,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules switch entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: JulesClient = data[DATA_CLIENT]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    async_add_entities(
        [
            JulesAutoApproveSwitch(coordinator, entry),
            JulesTokenCompressionSwitch(coordinator, entry, client),
        ]
    )


class JulesAutoApproveSwitch(
    CoordinatorEntity[JulesDataUpdateCoordinator], SwitchEntity
):
    """Switch entity for toggling auto-approval of proposed plans."""

    _attr_has_entity_name = True
    _attr_name = "Auto-Approve Plans"
    _attr_icon = "mdi:check-decagram-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize auto-approve switch."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_auto_approve"
        self._attr_device_info = get_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return true if auto approval is enabled."""
        return self.entry.options.get(
            CONF_AUTO_APPROVE,
            self.entry.data.get(CONF_AUTO_APPROVE, False),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-approval of plans."""
        new_options = {**self.entry.options, CONF_AUTO_APPROVE: True}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-approval of plans."""
        new_options = {**self.entry.options, CONF_AUTO_APPROVE: False}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.coordinator.async_request_refresh()


class JulesTokenCompressionSwitch(
    CoordinatorEntity[JulesDataUpdateCoordinator], SwitchEntity
):
    """Switch entity for prompt token optimization / compression."""

    _attr_has_entity_name = True
    _attr_name = "Token Compression"
    _attr_icon = "mdi:arrow-collapse-horizontal"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
        client: JulesClient,
    ) -> None:
        """Initialize token compression switch."""
        super().__init__(coordinator)
        self.entry = entry
        self.client = client
        self._attr_unique_id = f"{entry.entry_id}_token_compression"
        self._attr_device_info = get_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return true if token compression is active."""
        return self.client.compression_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on token compression."""
        self.client.compression_enabled = True
        new_options = {**self.entry.options, CONF_TOKEN_COMPRESSION: True}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off token compression."""
        self.client.compression_enabled = False
        new_options = {**self.entry.options, CONF_TOKEN_COMPRESSION: False}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.async_write_ha_state()
