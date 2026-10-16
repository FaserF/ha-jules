"""Tests for Jules diagnostics."""

from unittest.mock import MagicMock

import pytest

from custom_components.jules.const import DATA_COORDINATOR, DOMAIN
from custom_components.jules.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redaction(hass, mock_config_entry):
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {
        "total_sessions": 5,
        "active_sessions": 1,
        "awaiting_approval": 0,
        "completed_sessions": 4,
        "failed_sessions": 0,
        "sources_count": 2,
        "latest_session": {"name": "sessions/1"},
    }

    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_COORDINATOR: mock_coordinator,
            }
        }
    }

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diag["coordinator"]["total_sessions"] == 5
    assert diag["entry"]["data"]["api_key"] == "**REDACTED**"
