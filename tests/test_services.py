"""Tests for Jules services."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.jules.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    SERVICE_APPROVE_PLAN,
    SERVICE_CREATE_SESSION,
    SERVICE_REFRESH_SESSIONS,
    SERVICE_SEND_MESSAGE,
)
from custom_components.jules.services import async_setup_services, async_unload_services


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.async_create_session = AsyncMock(
        return_value={
            "name": "sessions/200",
            "title": "Service session",
            "state": "QUEUED",
        }
    )
    client.async_approve_plan = AsyncMock(return_value={"status": "approved"})
    client.async_send_message = AsyncMock(return_value={"status": "message_sent"})
    return client


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "sessions": [{"name": "sessions/201", "state": "AWAITING_APPROVAL"}],
        "latest_session": {"name": "sessions/201"},
    }
    coord.async_request_refresh = AsyncMock()
    return coord


@pytest.mark.asyncio
async def test_services_lifecycle(
    hass, mock_config_entry, mock_client, mock_coordinator
):
    mock_coordinator.config_entry = mock_config_entry
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_CLIENT: mock_client,
                DATA_COORDINATOR: mock_coordinator,
            }
        }
    }

    registered_services = {}

    def mock_register(domain, service, handler, **kwargs):
        registered_services[service] = handler

    hass.services.async_register = mock_register
    hass.services.has_service = lambda domain, service: service in registered_services
    hass.services.async_remove = lambda domain, service: registered_services.pop(
        service, None
    )

    await async_setup_services(hass)
    assert SERVICE_CREATE_SESSION in registered_services
    assert SERVICE_APPROVE_PLAN in registered_services
    assert SERVICE_SEND_MESSAGE in registered_services
    assert SERVICE_REFRESH_SESSIONS in registered_services

    # Test create_session
    call = MagicMock()
    call.data = {"prompt": "Solve issue", "source": "sources/github/FaserF/ha-jules"}
    res = await registered_services[SERVICE_CREATE_SESSION](call)
    assert res["session_id"] == "sessions/200"
    mock_client.async_create_session.assert_called_once()
    mock_coordinator.async_request_refresh.assert_called_once()

    # Test approve_plan
    call_approve = MagicMock()
    call_approve.data = {"session_id": "sessions/201"}
    res_approve = await registered_services[SERVICE_APPROVE_PLAN](call_approve)
    assert res_approve["session_id"] == "sessions/201"
    mock_client.async_approve_plan.assert_called_once_with("sessions/201")

    # Test send_message
    call_msg = MagicMock()
    call_msg.data = {"message": "Great job, wrap it up"}
    res_msg = await registered_services[SERVICE_SEND_MESSAGE](call_msg)
    assert res_msg["result"]["status"] == "message_sent"
    mock_client.async_send_message.assert_called_once_with(
        "sessions/201", "Great job, wrap it up"
    )

    # Test refresh_sessions
    call_refresh = MagicMock()
    call_refresh.data = {}
    res_refresh = await registered_services[SERVICE_REFRESH_SESSIONS](call_refresh)
    assert res_refresh["status"] == "refreshed"

    # Test execute_ai_task
    mock_client.async_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": "AI response"}}], "usage": {}}
    )
    # Test get_session_activities
    from custom_components.jules.const import (
        SERVICE_GET_FLEET_STATUS,
        SERVICE_GET_SESSION_ACTIVITIES,
        SERVICE_SYNC_SOURCES,
    )

    mock_client.async_get_activities = AsyncMock(
        return_value=[{"id": "act-1", "type": "thought", "summary": "Thinking"}]
    )
    call_act = MagicMock()
    call_act.data = {"session_id": "sessions/201"}
    res_act = await registered_services[SERVICE_GET_SESSION_ACTIVITIES](call_act)
    assert res_act["session_id"] == "sessions/201"
    assert res_act["count"] == 1
    mock_client.async_get_activities.assert_called_once_with("sessions/201")

    # Test get_fleet_status
    mock_coordinator.data.update(
        {
            "remaining_quota": 80,
            "today_used": 20,
            "active_sessions": 1,
            "reachable": True,
            "account_plan": "Google AI Pro",
            "daily_limit": 100,
        }
    )
    call_fleet = MagicMock()
    call_fleet.data = {}
    res_fleet = await registered_services[SERVICE_GET_FLEET_STATUS](call_fleet)
    assert res_fleet["total_accounts"] == 1
    assert res_fleet["fleet_quota_remaining"] == 80
    assert res_fleet["recommended_entry_id"] == mock_config_entry.entry_id

    # Test sync_sources
    call_sync = MagicMock()
    call_sync.data = {}
    res_sync = await registered_services[SERVICE_SYNC_SOURCES](call_sync)
    assert res_sync["synced_count"] == 1

    # Test unload
    await async_unload_services(hass)
    assert len(registered_services) == 0
