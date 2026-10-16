"""Helper utilities for Google Jules integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_API_URL, DEFAULT_API_URL, DOMAIN, INTEGRATION_VERSION


def get_integration_version() -> str:
    """Return integration version."""
    return INTEGRATION_VERSION


def get_jules_version(entry: ConfigEntry | None = None) -> str:
    """Return Google Jules API / platform version (e.g. v1alpha)."""
    if entry:
        api_url = entry.data.get(CONF_API_URL, DEFAULT_API_URL)
        if "v1alpha" in api_url:
            return "v1alpha"
        if "/v1" in api_url:
            return "v1"
    return "v1alpha"


def get_device_info(entry: ConfigEntry, sw_version: str | None = None) -> DeviceInfo:
    """Return device registry DeviceInfo for Google Jules entry."""
    # Always display the Jules API/Agent version (e.g. v1alpha), never the integration version
    version = sw_version or get_jules_version(entry)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Google Jules",
        manufacturer="Google Labs",
        model="Autonomous AI Coding Agent",
        sw_version=version,
        configuration_url=entry.data.get(CONF_API_URL, "https://jules.google.com"),
    )
