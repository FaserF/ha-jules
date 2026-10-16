"""Helper utilities for Google Jules integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_API_URL, DOMAIN, INTEGRATION_VERSION


def get_integration_version() -> str:
    """Return integration version."""
    return INTEGRATION_VERSION


def get_device_info(entry: ConfigEntry, sw_version: str | None = None) -> DeviceInfo:
    """Return device registry DeviceInfo for Google Jules entry."""
    version = sw_version or get_integration_version() or None
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Google Jules",
        manufacturer="Google Labs",
        model="Autonomous AI Coding Agent",
        sw_version=version,
        configuration_url=entry.data.get(CONF_API_URL, "https://jules.google.com"),
    )
