"""Image platform for Google Jules integration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_IMAGE_ENTITY, DOMAIN
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Jules image entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    entity = JulesLatestAnalyzedImage(hass, coordinator, entry)
    data[DATA_IMAGE_ENTITY] = entity
    async_add_entities([entity])


class JulesLatestAnalyzedImage(
    CoordinatorEntity[JulesDataUpdateCoordinator], ImageEntity
):
    """Image entity showing the most recently analyzed camera snapshot."""

    _attr_has_entity_name = True
    _attr_name = "Latest Analyzed Image"
    _attr_icon = "mdi:camera-iris"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: JulesDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize latest analyzed image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_latest_analyzed_image"
        self._attr_device_info = get_device_info(entry)
        self._image_bytes: bytes | None = None
        self._image_last_updated: datetime | None = None
        self._camera_entity_id: str | None = None
        self._analysis_text: str | None = None
        self._prompt: str | None = None

    @property
    def image_last_updated(self) -> datetime | None:
        """Return timestamp when image was last updated."""
        return self._image_last_updated

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "camera_entity_id": self._camera_entity_id,
            "prompt": self._prompt,
            "analysis": self._analysis_text,
            "last_updated": (
                self._image_last_updated.isoformat()
                if self._image_last_updated
                else None
            ),
        }

    def set_image(
        self,
        image_data: bytes,
        analysis_text: str | None = None,
        camera_entity_id: str | None = None,
        prompt: str | None = None,
    ) -> None:
        """Update current image bytes and metadata."""
        self._image_bytes = image_data
        self._image_last_updated = datetime.now(UTC)
        self._analysis_text = analysis_text
        self._camera_entity_id = camera_entity_id
        self._prompt = prompt
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of latest analyzed image."""
        return self._image_bytes
