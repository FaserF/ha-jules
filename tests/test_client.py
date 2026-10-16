"""Tests for the JulesClient."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.jules.client import (
    CannotConnect,
    InvalidAuth,
    JulesClient,
    SessionNotFoundError,
)


@pytest.fixture
def mock_session():
    return MagicMock(spec=aiohttp.ClientSession)


def make_mock_response(status=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


@pytest.mark.asyncio
async def test_client_init_and_headers(mock_session):
    client = JulesClient(
        mock_session,
        api_key="secret-key",
        api_url="https://jules.googleapis.com/v1alpha/",
    )
    assert client.base_url == "https://jules.googleapis.com/v1alpha"

    headers = client._get_headers()
    assert headers["x-goog-api-key"] == "secret-key"
    assert headers["Authorization"] == "Bearer secret-key"
    assert "HomeAssistant-Jules" in headers["User-Agent"]


@pytest.mark.asyncio
async def test_async_test_connection_success(mock_session):
    mock_session.request = MagicMock(
        return_value=make_mock_response(200, {"sessions": []})
    )
    client = JulesClient(mock_session, api_key="valid-key")

    result = await client.async_test_connection()
    assert result is True


@pytest.mark.asyncio
async def test_async_test_connection_invalid_auth(mock_session):
    mock_session.request = MagicMock(
        return_value=make_mock_response(401, text="Unauthorized")
    )
    client = JulesClient(mock_session, api_key="bad-key")

    with pytest.raises(InvalidAuth):
        await client.async_test_connection()


@pytest.mark.asyncio
async def test_async_test_connection_cannot_connect(mock_session):
    mock_session.request = MagicMock(side_effect=aiohttp.ClientError("DNS fail"))
    client = JulesClient(mock_session, api_key="bad-key")

    with pytest.raises(CannotConnect):
        await client.async_test_connection()


@pytest.mark.asyncio
async def test_async_get_sources(mock_session):
    mock_data = {
        "sources": [
            {"name": "sources/github/FaserF/ha-jules", "id": "github/FaserF/ha-jules"}
        ]
    }
    mock_session.request = MagicMock(return_value=make_mock_response(200, mock_data))
    client = JulesClient(mock_session, api_key="key")

    sources = await client.async_get_sources()
    assert len(sources) == 1
    assert sources[0]["id"] == "github/FaserF/ha-jules"


@pytest.mark.asyncio
async def test_async_get_sessions(mock_session):
    mock_data = {
        "sessions": [
            {
                "name": "sessions/1001",
                "title": "Fix bug",
                "state": "IN_PROGRESS",
            }
        ]
    }
    mock_session.request = MagicMock(return_value=make_mock_response(200, mock_data))
    client = JulesClient(mock_session, api_key="key")

    sessions = await client.async_get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Fix bug"


@pytest.mark.asyncio
async def test_async_get_session(mock_session):
    mock_data = {"name": "sessions/1001", "state": "COMPLETED"}
    mock_session.request = MagicMock(return_value=make_mock_response(200, mock_data))
    client = JulesClient(mock_session, api_key="key")

    session = await client.async_get_session("sessions/1001")
    assert session["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_async_create_session(mock_session):
    mock_data = {"name": "sessions/1002", "state": "QUEUED"}
    mock_session.request = MagicMock(return_value=make_mock_response(201, mock_data))
    client = JulesClient(mock_session, api_key="key")

    result = await client.async_create_session(
        prompt="Fix issues",
        source="sources/github/FaserF/ha-jules",
        title="Quick Fix",
        branch="main",
        auto_approve=True,
    )
    assert result["name"] == "sessions/1002"


@pytest.mark.asyncio
async def test_async_approve_plan(mock_session):
    mock_session.request = MagicMock(
        return_value=make_mock_response(200, {"status": "approved"})
    )
    client = JulesClient(mock_session, api_key="key")

    result = await client.async_approve_plan("sessions/1001")
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_async_send_message(mock_session):
    mock_session.request = MagicMock(
        return_value=make_mock_response(200, {"status": "sent"})
    )
    client = JulesClient(mock_session, api_key="key")

    result = await client.async_send_message("sessions/1001", "Continue with task")
    assert result["status"] == "sent"


@pytest.mark.asyncio
async def test_async_get_activities(mock_session):
    mock_data = {"activities": [{"step": 1, "description": "Cloned repo"}]}
    mock_session.request = MagicMock(return_value=make_mock_response(200, mock_data))
    client = JulesClient(mock_session, api_key="key")

    activities = await client.async_get_activities("sessions/1001")
    assert len(activities) == 1
    assert activities[0]["description"] == "Cloned repo"


@pytest.mark.asyncio
async def test_client_not_found(mock_session):
    mock_session.request = MagicMock(
        return_value=make_mock_response(404, text="Not Found")
    )
    client = JulesClient(mock_session, api_key="key")

    with pytest.raises(SessionNotFoundError):
        await client._async_request("GET", "sessions/unknown")
