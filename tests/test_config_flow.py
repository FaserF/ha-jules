"""Tests for the Jules config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.jules.client import CannotConnect, InvalidAuth
from custom_components.jules.config_flow import JulesConfigFlow, JulesOptionsFlowHandler


@pytest.mark.asyncio
async def test_flow_user_init(hass):
    flow = JulesConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_flow_user_success(hass):
    flow = JulesConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.jules.config_flow.JulesClient.async_test_connection",
        new=AsyncMock(return_value=True),
    ):
        result = await flow.async_step_user(
            {
                "api_key": "valid-token-123",
                "api_url": "https://jules.googleapis.com/v1alpha",
                "default_source": "FaserF/ha-jules",
                "auto_approve": False,
            }
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Google Jules"
    assert result["data"]["api_key"] == "valid-token-123"


@pytest.mark.asyncio
async def test_flow_user_invalid_auth(hass):
    flow = JulesConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.jules.config_flow.JulesClient.async_test_connection",
        side_effect=InvalidAuth("Invalid key"),
    ):
        result = await flow.async_step_user(
            {
                "api_key": "bad-token",
                "api_url": "https://jules.googleapis.com/v1alpha",
            }
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_flow_user_cannot_connect(hass):
    flow = JulesConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.jules.config_flow.JulesClient.async_test_connection",
        side_effect=CannotConnect("Timeout"),
    ):
        result = await flow.async_step_user(
            {
                "api_key": "any-token",
                "api_url": "https://jules.googleapis.com/v1alpha",
            }
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_flow_reconfigure_success(hass, mock_config_entry):
    flow = JulesConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": mock_config_entry.entry_id}
    hass.config_entries.async_get_entry = lambda _: mock_config_entry

    with patch(
        "custom_components.jules.config_flow.JulesClient.async_test_connection",
        new=AsyncMock(return_value=True),
    ):
        result = await flow.async_step_reconfigure()
        assert result["type"] == "form"

        result2 = await flow.async_step_reconfigure_confirm(
            {
                "api_key": "new-secret-key",
                "api_url": "https://jules.googleapis.com/v1alpha",
            }
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_options_flow(hass, mock_config_entry):
    options_flow = JulesOptionsFlowHandler()
    options_flow._config_entry = mock_config_entry
    options_flow.hass = hass

    result = await options_flow.async_step_init()
    assert result["type"] == "form"

    result2 = await options_flow.async_step_init(
        {
            "scan_interval": 120,
            "auto_approve": True,
            "default_source": "sources/github/FaserF/ha-jules",
            "default_branch": "main",
        }
    )
    assert result2["type"] == "create_entry"
    assert result2["data"]["scan_interval"] == 120
