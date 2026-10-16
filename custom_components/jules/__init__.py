"""The Google Jules integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import JulesClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_API_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import JulesDataUpdateCoordinator
from .services import async_setup_services, async_unload_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Jules from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data.get(CONF_API_KEY, "")
    api_url = entry.data.get(CONF_API_URL, DEFAULT_API_URL)

    session = async_get_clientsession(hass)
    client = JulesClient(session=session, api_key=api_key, api_url=api_url)

    scan_interval_sec = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = JulesDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        update_interval=timedelta(seconds=scan_interval_sec),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    # Register services
    await async_setup_services(hass)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for option changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    LOGGER.info(
        "Google Jules integration successfully loaded for entry %s", entry.title
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Google Jules config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
