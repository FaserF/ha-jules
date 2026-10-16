"""Tests for the Jules button platform."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.jules.button import (
    JulesApprovePlanButton,
    JulesRefreshButton,
    async_setup_entry,
)
from custom_components.jules.const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "sessions": [
            {"name": "sessions/10", "state": "AWAITING_APPROVAL"},
        ]
    }
    coord.async_request_refresh = AsyncMock()
    return coord


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.async_approve_plan = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_refresh_button_press(mock_coordinator, mock_config_entry):
    btn = JulesRefreshButton(mock_coordinator, mock_config_entry)
    await btn.async_press()
    mock_coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_approve_plan_button_press_success(
    mock_coordinator, mock_client, mock_config_entry
):
    btn = JulesApprovePlanButton(mock_coordinator, mock_client, mock_config_entry)
    await btn.async_press()
    mock_client.async_approve_plan.assert_called_once_with("sessions/10")
    mock_coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_approve_plan_button_press_no_pending(
    mock_coordinator, mock_client, mock_config_entry
):
    mock_coordinator.data = {"sessions": [{"name": "sessions/11", "state": "COMPLETED"}]}
    btn = JulesApprovePlanButton(mock_coordinator, mock_client, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await btn.async_press()


@pytest.mark.asyncio
async def test_async_setup_entry_buttons(
    hass, mock_config_entry, mock_coordinator, mock_client
):
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_COORDINATOR: mock_coordinator,
                DATA_CLIENT: mock_client,
            }
        }
    }
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert len(added_entities) == 2
