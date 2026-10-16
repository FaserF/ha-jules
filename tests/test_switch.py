"""Tests for Google Jules switches."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.jules.switch import (
    JulesAutoApproveSwitch,
    JulesTokenCompressionSwitch,
)


@pytest.mark.asyncio
async def test_auto_approve_switch(mock_coordinator, mock_config_entry):
    switch = JulesAutoApproveSwitch(mock_coordinator, mock_config_entry)
    switch.hass = MagicMock()
    mock_coordinator.async_request_refresh = AsyncMock()

    assert switch.is_on is False
    await switch.async_turn_on()
    switch.hass.config_entries.async_update_entry.assert_called_once()


@pytest.mark.asyncio
async def test_token_compression_switch(
    mock_coordinator, mock_config_entry, mock_client
):
    switch = JulesTokenCompressionSwitch(
        mock_coordinator, mock_config_entry, mock_client
    )
    switch.hass = MagicMock()

    assert switch.is_on is True
    await switch.async_turn_off()
    assert mock_client.compression_enabled is False
