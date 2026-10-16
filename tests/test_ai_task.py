"""Tests for Google Jules AI Task platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.jules.ai_task import JulesAITaskEntity


@pytest.mark.asyncio
async def test_ai_task_execution(mock_coordinator, mock_config_entry, mock_client):
    entity = JulesAITaskEntity(mock_config_entry, mock_client, mock_coordinator)
    entity.hass = MagicMock()
    mock_client.async_chat_completion = AsyncMock(
        return_value={
            "choices": [{"message": {"content": "Task completed successfully."}}],
            "usage": {"total_tokens": 42},
        }
    )

    result = await entity.async_execute_task("Analyze my kitchen automation")
    assert result["response"] == "Task completed successfully."
    assert result["usage"]["total_tokens"] == 42
    assert entity.state == "ready"
