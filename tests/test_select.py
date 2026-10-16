"""Tests for Google Jules selects."""

from unittest.mock import MagicMock

import pytest

from custom_components.jules.select import (
    JulesActiveModelSelect,
    JulesActiveSourceSelect,
    JulesDefaultBranchSelect,
)


@pytest.mark.asyncio
async def test_selects(mock_coordinator, mock_config_entry):
    model_select = JulesActiveModelSelect(mock_coordinator, mock_config_entry)
    model_select.hass = MagicMock()
    assert "coding-cascade" in model_select.options
    await model_select.async_select_option("fast-cascade")
    model_select.hass.config_entries.async_update_entry.assert_called_once()

    source_select = JulesActiveSourceSelect(mock_coordinator, mock_config_entry)
    source_select.hass = MagicMock()
    assert "sources/github/FaserF/ha-jules" in source_select.options

    branch_select = JulesDefaultBranchSelect(mock_coordinator, mock_config_entry)
    branch_select.hass = MagicMock()
    assert branch_select.current_option == "main"
    assert "main" in branch_select.options
