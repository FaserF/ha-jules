"""Diagnostics support for Google Jules."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, DATA_COORDINATOR, DOMAIN
from .coordinator import JulesDataUpdateCoordinator

TO_REDACT = {
    CONF_API_KEY,
    "api_key",
    "password",
    "token",
    "access_token",
    "authorization",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: JulesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    coord_data = coordinator.data or {}

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "total_sessions": coord_data.get("total_sessions", 0),
            "active_sessions": coord_data.get("active_sessions", 0),
            "awaiting_approval": coord_data.get("awaiting_approval", 0),
            "completed_sessions": coord_data.get("completed_sessions", 0),
            "failed_sessions": coord_data.get("failed_sessions", 0),
            "sources_count": coord_data.get("sources_count", 0),
            "has_latest_session": bool(coord_data.get("latest_session")),
        },
    }
