"""Tests for the Jules binary sensor platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.jules.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    JulesBinarySensorEntity,
    async_setup_entry,
)
from custom_components.jules.const import DATA_COORDINATOR, DOMAIN


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "active_sessions": 1,
        "awaiting_approval": 1,
    }
    coord.last_update_success = True
    return coord


@pytest.mark.asyncio
async def test_binary_sensors(mock_coordinator, mock_config_entry):
    entities = [
        JulesBinarySensorEntity(mock_coordinator, desc, mock_config_entry)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    ]
    sensor_map = {ent.entity_description.key: ent for ent in entities}

    assert sensor_map["connected"].is_on is True
    assert sensor_map["working"].is_on is True
    assert sensor_map["action_required"].is_on is True

    # Test idle/off state
    mock_coordinator.data = {"active_sessions": 0, "awaiting_approval": 0}
    mock_coordinator.last_update_success = False

    assert sensor_map["connected"].is_on is False
    assert sensor_map["working"].is_on is False
    assert sensor_map["action_required"].is_on is False


@pytest.mark.asyncio
async def test_async_setup_entry_binary_sensor(
    hass, mock_config_entry, mock_coordinator
):
    hass.data = {
        DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: mock_coordinator}}
    }
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert len(added_entities) == len(BINARY_SENSOR_DESCRIPTIONS)
