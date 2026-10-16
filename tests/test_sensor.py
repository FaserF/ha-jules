"""Tests for the Jules sensor platform."""

from unittest.mock import MagicMock
import pytest

from custom_components.jules.const import DATA_COORDINATOR, DOMAIN
from custom_components.jules.sensor import (
    SENSOR_DESCRIPTIONS,
    JulesSensorEntity,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "total_sessions": 10,
        "active_sessions": 2,
        "awaiting_approval": 1,
        "completed_sessions": 7,
        "failed_sessions": 0,
        "sources_count": 3,
        "sources": [{"name": "sources/github/FaserF/ha-jules"}],
        "latest_session": {
            "name": "sessions/42",
            "state": "IN_PROGRESS",
            "title": "Add testing",
            "prompt": "Write unit tests",
            "source": "sources/github/FaserF/ha-jules",
            "branch": "main",
            "pullRequestUrl": "https://github.com/pull/42",
        },
    }
    coord.last_update_success = True
    return coord


@pytest.mark.asyncio
async def test_sensors_values(mock_coordinator, mock_config_entry):
    entities = [
        JulesSensorEntity(mock_coordinator, desc, mock_config_entry)
        for desc in SENSOR_DESCRIPTIONS
    ]

    sensor_map = {ent.entity_description.key: ent for ent in entities}

    assert sensor_map["total_sessions"].native_value == 10
    assert sensor_map["active_sessions"].native_value == 2
    assert sensor_map["awaiting_approval"].native_value == 1
    assert sensor_map["completed_sessions"].native_value == 7
    assert sensor_map["failed_sessions"].native_value == 0
    assert sensor_map["sources_count"].native_value == 3
    assert sensor_map["latest_session"].native_value == "in_progress"

    attrs = sensor_map["latest_session"].extra_state_attributes
    assert attrs["session_id"] == "sessions/42"
    assert attrs["title"] == "Add testing"
    assert attrs["pr_url"] == "https://github.com/pull/42"


@pytest.mark.asyncio
async def test_async_setup_entry(hass, mock_config_entry, mock_coordinator):
    hass.data = {DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: mock_coordinator}}}
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert len(added_entities) == len(SENSOR_DESCRIPTIONS)
