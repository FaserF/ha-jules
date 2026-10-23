"""Tests for Google Jules conversation platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.conversation import ConversationInput

from custom_components.jules.conversation import JulesConversationEntity


@pytest.mark.asyncio
async def test_conversation_entity_process(
    mock_coordinator, mock_config_entry, mock_client
):
    entity = JulesConversationEntity(mock_config_entry, mock_client, mock_coordinator)
    entity.hass = MagicMock()
    mock_client.async_chat_completion = AsyncMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello, I am Jules. I can help with code and smart home automations.",
                    }
                }
            ]
        }
    )

    user_input = ConversationInput(
        text="Hello Jules",
        context=MagicMock(),
        conversation_id="conv_123",
        device_id=None,
        language="en",
        agent_id="jules",
    )

    result = await entity.async_process(user_input)
    assert (
        result.response.speech["plain"]["speech"]
        == "Hello, I am Jules. I can help with code and smart home automations."
    )
    assert result.conversation_id == "conv_123"
