"""Tests for integration lifecycle in __init__.py."""

from unittest.mock import AsyncMock, patch
import pytest

from custom_components.jules import async_reload_entry, async_setup_entry, async_unload_entry
from custom_components.jules.const import DOMAIN


@pytest.mark.asyncio
async def test_init_setup_and_unload(hass, mock_config_entry):
    with patch(
        "custom_components.jules.coordinator.JulesDataUpdateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ), patch(
        "custom_components.jules.services.async_setup_services",
        new=AsyncMock(),
    ), patch(
        "custom_components.jules.services.async_unload_services",
        new=AsyncMock(),
    ):
        setup_ok = await async_setup_entry(hass, mock_config_entry)
        assert setup_ok is True
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        unload_ok = await async_unload_entry(hass, mock_config_entry)
        assert unload_ok is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_init_reload(hass, mock_config_entry):
    await async_reload_entry(hass, mock_config_entry)
    hass.config_entries.async_reload.assert_called_once_with(mock_config_entry.entry_id)
