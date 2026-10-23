"""Select platform for Google Jules integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CHAT_MODEL,
    CONF_DEFAULT_BRANCH,
    CONF_DEFAULT_SOURCE,
    DATA_COORDINATOR,
    DEFAULT_CASCADES,
    DEFAULT_CHAT_MODEL,
    DOMAIN,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules select entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    entities: list[SelectEntity] = [
        JulesActiveModelSelect(coordinator, entry),
        JulesActiveSourceSelect(coordinator, entry),
        JulesDefaultBranchSelect(coordinator, entry),
    ]
    async_add_entities(entities)


class JulesActiveModelSelect(
    CoordinatorEntity[JulesDataUpdateCoordinator], SelectEntity
):
    """Select entity for active LLM cascade / chat model."""

    _attr_has_entity_name = True
    _attr_name = "Active Model"
    _attr_icon = "mdi:routes"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize active model select."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_active_model"
        self._attr_device_info = get_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return available model/cascade options."""
        models: list[str] = []
        if self.coordinator.data and "models" in self.coordinator.data:
            models = list(self.coordinator.data["models"])
        if not models:
            models = list(DEFAULT_CASCADES)
        selected = self.entry.options.get(
            CONF_CHAT_MODEL,
            self.entry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
        )
        if selected and selected not in models:
            models.insert(0, selected)
        return models[:40]

    @property
    def current_option(self) -> str | None:
        """Return currently selected model."""
        selected = self.entry.options.get(
            CONF_CHAT_MODEL,
            self.entry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
        )
        if selected in self.options:
            return selected
        return self.options[0] if self.options else None

    async def async_select_option(self, option: str) -> None:
        """Change the selected model."""
        new_options = {**self.entry.options, CONF_CHAT_MODEL: option}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.async_write_ha_state()


class JulesActiveSourceSelect(
    CoordinatorEntity[JulesDataUpdateCoordinator], SelectEntity
):
    """Select entity for active target repository/source."""

    _attr_has_entity_name = True
    _attr_name = "Active Repository"
    _attr_icon = "mdi:source-repository-multiple"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize active repository select."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_active_repository"
        self._attr_device_info = get_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return available repository sources."""
        sources: list[dict[str, Any]] = (
            self.coordinator.data.get("sources", []) if self.coordinator.data else []
        )
        source_names = [
            s.get("id") or s.get("name", "")
            for s in sources
            if isinstance(s, dict) and (s.get("id") or s.get("name"))
        ]
        default_configured = self.entry.options.get(
            CONF_DEFAULT_SOURCE,
            self.entry.data.get(CONF_DEFAULT_SOURCE, ""),
        )
        if default_configured and default_configured not in source_names:
            source_names.insert(0, default_configured)

        if not source_names:
            source_names = ["FaserF/ha-jules"]
        return sorted(set(source_names))

    @property
    def current_option(self) -> str | None:
        """Return currently selected repository."""
        selected = self.entry.options.get(
            CONF_DEFAULT_SOURCE,
            self.entry.data.get(CONF_DEFAULT_SOURCE, ""),
        )
        if selected and selected in self.options:
            return selected
        return self.options[0] if self.options else None

    async def async_select_option(self, option: str) -> None:
        """Change the active repository."""
        new_options = {**self.entry.options, CONF_DEFAULT_SOURCE: option}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.async_write_ha_state()


class JulesDefaultBranchSelect(
    CoordinatorEntity[JulesDataUpdateCoordinator], SelectEntity
):
    """Select entity for default git branch."""

    _attr_has_entity_name = True
    _attr_name = "Default Branch"
    _attr_icon = "mdi:source-branch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize default branch select."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_default_branch"
        self._attr_device_info = get_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return available branch options."""
        return ["main", "master", "dev", "develop"]

    @property
    def current_option(self) -> str | None:
        """Return currently selected branch."""
        return self.entry.options.get(
            CONF_DEFAULT_BRANCH,
            self.entry.data.get(CONF_DEFAULT_BRANCH, "main"),
        )

    async def async_select_option(self, option: str) -> None:
        """Change default branch."""
        new_options = {**self.entry.options, CONF_DEFAULT_BRANCH: option}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.async_write_ha_state()
