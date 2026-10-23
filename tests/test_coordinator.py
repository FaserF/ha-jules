"""Tests for the JulesDataUpdateCoordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.jules.coordinator import JulesDataUpdateCoordinator


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.async_get_sessions = AsyncMock()
    client.async_get_sources = AsyncMock()
    client.async_approve_plan = AsyncMock()
    client.async_check_health = AsyncMock(return_value={"status": "healthy"})
    client.async_get_models = AsyncMock(return_value=["coding-cascade"])
    return client


@pytest.mark.asyncio
async def test_coordinator_data_processing(hass, mock_config_entry, mock_client):
    sessions = [
        {"name": "sessions/1", "state": "IN_PROGRESS", "title": "Session 1"},
        {"name": "sessions/2", "state": "COMPLETED", "title": "Session 2"},
        {"name": "sessions/3", "state": "FAILED", "title": "Session 3"},
        {"name": "sessions/4", "state": "AWAITING_APPROVAL", "title": "Session 4"},
    ]
    sources = [{"name": "sources/github/FaserF/ha-jules"}]

    mock_client.async_get_sessions.return_value = sessions
    mock_client.async_get_sources.return_value = sources

    coordinator = JulesDataUpdateCoordinator(hass, mock_client, mock_config_entry)
    data = await coordinator._async_update_data()

    assert data["total_sessions"] == 4
    assert data["active_sessions"] == 2  # IN_PROGRESS + AWAITING_APPROVAL
    assert data["awaiting_approval"] == 1
    assert data["completed_sessions"] == 1
    assert data["failed_sessions"] == 1
    assert data["sources_count"] == 1
    assert data["latest_session"]["title"] == "Session 1"


@pytest.mark.asyncio
async def test_coordinator_auto_approve(hass, mock_config_entry, mock_client):
    mock_config_entry.options["auto_approve"] = True
    sessions = [
        {"name": "sessions/5", "state": "AWAITING_APPROVAL", "title": "Needs Approval"},
    ]
    mock_client.async_get_sessions.return_value = sessions
    mock_client.async_get_sources.return_value = []

    coordinator = JulesDataUpdateCoordinator(hass, mock_client, mock_config_entry)
    await coordinator._async_update_data()

    mock_client.async_approve_plan.assert_called_once_with("sessions/5")


@pytest.mark.asyncio
async def test_coordinator_state_transition_events(
    hass, mock_config_entry, mock_client
):
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    coordinator = JulesDataUpdateCoordinator(hass, mock_client, mock_config_entry)

    # Initial update: in progress
    mock_client.async_get_sessions.return_value = [
        {"name": "sessions/6", "state": "IN_PROGRESS"}
    ]
    mock_client.async_get_sources.return_value = []
    await coordinator._async_update_data()
    hass.bus.async_fire.assert_called_once()
    assert hass.bus.async_fire.call_args[0][0] == "jules_session_started"
    hass.bus.async_fire.reset_mock()

    # Second update: transitioned to COMPLETED
    mock_client.async_get_sessions.return_value = [
        {
            "name": "sessions/6",
            "state": "COMPLETED",
            "pullRequestUrl": "https://github.com/pull/1",
        }
    ]
    await coordinator._async_update_data()

    hass.bus.async_fire.assert_called_once()
    assert hass.bus.async_fire.call_args[0][0] == "jules_session_completed"


@pytest.mark.asyncio
async def test_coordinator_update_failure(hass, mock_config_entry, mock_client):
    mock_client.async_get_sessions.side_effect = Exception("API Timeout")

    coordinator = JulesDataUpdateCoordinator(hass, mock_client, mock_config_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
