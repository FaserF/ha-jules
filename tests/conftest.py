"""Pytest configuration and fixtures for the Google Jules integration tests."""

import sys
import types
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

if sys.platform == "win32":
    if "fcntl" not in sys.modules:
        fcntl_mock = types.ModuleType("fcntl")
        fcntl_mock.LOCK_EX = 2
        fcntl_mock.LOCK_NB = 4
        fcntl_mock.LOCK_SH = 1
        fcntl_mock.LOCK_UN = 8
        fcntl_mock.flock = MagicMock()
        sys.modules["fcntl"] = fcntl_mock

    if "resource" not in sys.modules:
        resource_mock = types.ModuleType("resource")
        resource_mock.RLIMIT_NOFILE = 7
        resource_mock.getrlimit = MagicMock(return_value=(1024, 2048))
        resource_mock.setrlimit = MagicMock()
        sys.modules["resource"] = resource_mock

if "voluptuous" not in sys.modules:
    vol_mock = MagicMock()
    vol_mock.Schema = lambda schema, *args, **kwargs: schema
    vol_mock.Required = lambda key, *args, **kwargs: key
    vol_mock.Optional = lambda key, *args, **kwargs: key
    vol_mock.Coerce = lambda typ: typ
    vol_mock.In = lambda items: items
    sys.modules["voluptuous"] = vol_mock

import pytest


def mock_submodule(name: str) -> None:
    """Recursively mock submodules to ensure they are available in sys.modules."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        full_name = ".".join(parts[:i])
        if full_name not in sys.modules:
            mock = MagicMock()
            sys.modules[full_name] = mock
            if i > 1:
                parent_name = ".".join(parts[: i - 1])
                setattr(sys.modules[parent_name], parts[i - 1], mock)


@dataclass(frozen=True, kw_only=True)
class MockEntityDescription:
    """Base class for mocked entity descriptions."""

    key: str
    name: str | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    entity_category: Any = None
    translation_key: str | None = None
    has_entity_name: bool = False
    device_class: Any = None
    native_unit_of_measurement: str | None = None
    state_class: Any = None
    options: list[str] | None = None


class MockEntity:
    """Base class for mocked Home Assistant entities."""

    _attr_has_entity_name: bool = False
    _attr_name: str | None = None
    _attr_unique_id: str | None = None
    _attr_device_info: dict[str, Any] | None = None
    _attr_extra_state_attributes: dict[str, Any] | None = None
    _attr_icon: str | None = None
    entity_description: Any = None
    hass: Any = None

    @property
    def name(self) -> str | None:
        if self._attr_name is not None:
            return self._attr_name
        if hasattr(self, "entity_description") and self.entity_description:
            return getattr(self.entity_description, "name", None)
        return None

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def device_info(self) -> dict[str, Any] | None:
        return self._attr_device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attr_extra_state_attributes

    def async_write_ha_state(self) -> None:
        pass


class MockCoordinatorEntity(MockEntity):
    """Base class for coordinator entities."""

    @classmethod
    def __class_getitem__(cls, _):
        return cls

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass = getattr(coordinator, "hass", None)

    @property
    def available(self) -> bool:
        if self.coordinator and hasattr(self.coordinator, "last_update_success"):
            return self.coordinator.last_update_success
        return True


class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator."""

    @classmethod
    def __class_getitem__(cls, _):
        return cls

    def __init__(
        self,
        hass: Any,
        logger: Any,
        *,
        name: str,
        update_interval: Any = None,
        update_method: Any = None,
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.update_method = update_method
        self.data: Any = None
        self.last_update_success = True
        self._listeners: list[Any] = []

    def async_add_listener(self, update_callback: Any, context: Any = None) -> Any:
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    async def async_refresh(self) -> None:
        if hasattr(self, "_async_update_data"):
            self.data = await self._async_update_data()

    async def async_config_entry_first_refresh(self) -> None:
        await self.async_refresh()


class MockConfigFlow:
    """Mock ConfigFlow."""

    def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._domain = domain

    def __init__(self) -> None:
        self.hass: Any = None
        self._unique_id: str | None = None

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        pass

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: Any = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {},
        }

    def async_create_entry(
        self,
        *,
        title: str,
        data: dict[str, Any],
        description: str | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
            "description": description,
            "description_placeholders": description_placeholders,
        }

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}

    def async_update_reload_and_abort(
        self,
        entry: Any,
        *,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        reason: str = "reconfigure_successful",
    ) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}


class MockOptionsFlow:
    """Mock OptionsFlow."""

    def __init__(self, config_entry: Any = None) -> None:
        self._config_entry = config_entry
        self.hass: Any = None

    @property
    def config_entry(self) -> Any:
        return self._config_entry

    @config_entry.setter
    def config_entry(self, value: Any) -> None:
        self._config_entry = value

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: Any = None,
        errors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(
        self, *, title: str = "", data: dict[str, Any]
    ) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}


# Setup homeassistant mock structure
mock_submodule("homeassistant.const")
mock_submodule("homeassistant.core")
mock_submodule("homeassistant.exceptions")
mock_submodule("homeassistant.data_entry_flow")
mock_submodule("homeassistant.config_entries")
mock_submodule("homeassistant.helpers.update_coordinator")
mock_submodule("homeassistant.helpers.entity")
mock_submodule("homeassistant.helpers.entity_platform")
mock_submodule("homeassistant.helpers.aiohttp_client")
mock_submodule("homeassistant.helpers.config_validation")
mock_submodule("homeassistant.helpers.template")
mock_submodule("homeassistant.helpers.selector")
mock_submodule("homeassistant.helpers.llm")
mock_submodule("homeassistant.components.sensor")
mock_submodule("homeassistant.components.binary_sensor")
mock_submodule("homeassistant.components.button")
mock_submodule("homeassistant.components.diagnostics")
mock_submodule("homeassistant.components.conversation")
mock_submodule("homeassistant.components.repairs")
mock_submodule("homeassistant.components.event")
mock_submodule("homeassistant.components.image")
mock_submodule("homeassistant.components.select")
mock_submodule("homeassistant.components.switch")
mock_submodule("homeassistant.helpers.device_registry")
mock_submodule("homeassistant.helpers.entity_registry")
mock_submodule("homeassistant.helpers.issue_registry")

# Setup repairs mocks
repairs_mod = sys.modules["homeassistant.components.repairs"]
repairs_mod.RepairsFlow = MockConfigFlow
repairs_mod.RepairsFlowResult = dict

ir_mod = sys.modules["homeassistant.helpers.issue_registry"]
ir_mod.IssueSeverity = types.SimpleNamespace(ERROR="error", WARNING="warning")
ir_mod.async_create_issue = MagicMock()
ir_mod.async_delete_issue = MagicMock()

# Setup event, image, select, switch mocks
event_mod = sys.modules["homeassistant.components.event"]
event_mod.EventEntity = MockEntity

image_mod = sys.modules["homeassistant.components.image"]
image_mod.ImageEntity = MockEntity

select_mod = sys.modules["homeassistant.components.select"]
select_mod.SelectEntity = MockEntity

switch_mod = sys.modules["homeassistant.components.switch"]
switch_mod.SwitchEntity = MockEntity

# Assign standard attributes
ha_const = sys.modules["homeassistant.const"]
ha_const.Platform = types.SimpleNamespace(
    CONVERSATION="conversation",
    SENSOR="sensor",
    TTS="tts",
    STT="stt",
    BINARY_SENSOR="binary_sensor",
    BUTTON="button",
    SWITCH="switch",
    SELECT="select",
    EVENT="event",
    IMAGE="image",
)
ha_const.CONF_NAME = "name"
ha_const.EntityCategory = types.SimpleNamespace(
    DIAGNOSTIC="diagnostic",
    CONFIG="config",
)

ha_core = sys.modules["homeassistant.core"]
ha_core.HomeAssistant = MagicMock
ha_core.ServiceCall = MagicMock
ha_core.SupportsResponse = types.SimpleNamespace(
    NONE="none",
    OPTIONAL="optional",
    ONLY="only",
)
ha_core.callback = lambda fn: fn

ha_exc = sys.modules["homeassistant.exceptions"]


class MockHomeAssistantError(Exception):
    pass


ha_exc.HomeAssistantError = MockHomeAssistantError


class MockUpdateFailed(MockHomeAssistantError):
    pass


coord_module = sys.modules["homeassistant.helpers.update_coordinator"]
coord_module.DataUpdateCoordinator = MockDataUpdateCoordinator
coord_module.CoordinatorEntity = MockCoordinatorEntity
coord_module.UpdateFailed = MockUpdateFailed

entity_module = sys.modules["homeassistant.helpers.entity"]
entity_module.Entity = MockEntity

sensor_module = sys.modules["homeassistant.components.sensor"]


class MockSensorEntity(MockEntity):
    _attr_native_value: Any = None
    _attr_native_unit_of_measurement: str | None = None
    _attr_state_class: Any = None
    _attr_device_class: Any = None

    @property
    def native_value(self) -> Any:
        return self._attr_native_value


sensor_module.SensorEntity = MockSensorEntity
sensor_module.SensorEntityDescription = MockEntityDescription
sensor_module.SensorStateClass = types.SimpleNamespace(
    MEASUREMENT="measurement",
    TOTAL="total",
    TOTAL_INCREASING="total_increasing",
)
sensor_module.SensorDeviceClass = types.SimpleNamespace(
    DURATION="duration",
    DATA_SIZE="data_size",
)

# Binary Sensor module
bs_module = sys.modules["homeassistant.components.binary_sensor"]


class MockBinarySensorEntity(MockEntity):
    _attr_is_on: bool = False

    @property
    def is_on(self) -> bool:
        return self._attr_is_on


bs_module.BinarySensorEntity = MockBinarySensorEntity
bs_module.BinarySensorEntityDescription = MockEntityDescription
bs_module.BinarySensorDeviceClass = types.SimpleNamespace(
    CONNECTIVITY="connectivity",
    PROBLEM="problem",
    RUNNING="running",
)

# Button module
btn_module = sys.modules["homeassistant.components.button"]


class MockButtonEntity(MockEntity):
    async def async_press(self) -> None:
        pass


btn_module.ButtonEntity = MockButtonEntity
btn_module.ButtonEntityDescription = MockEntityDescription
btn_module.ButtonDeviceClass = types.SimpleNamespace(
    RESTART="restart",
    UPDATE="update",
)

# Diagnostics module
diag_module = sys.modules["homeassistant.components.diagnostics"]


def mock_async_redact_data(data: dict[str, Any], to_redact: Any) -> dict[str, Any]:
    redacted = dict(data)
    for k in data:
        if k in to_redact:
            redacted[k] = "**REDACTED**"
    return redacted


diag_module.async_redact_data = mock_async_redact_data

# Device Registry and Entity Registry
dr_module = sys.modules["homeassistant.helpers.device_registry"]


class MockDeviceInfo(dict):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)


dr_module.DeviceInfo = MockDeviceInfo
mock_dev_reg = MagicMock()
mock_dev_reg.devices = {}
mock_dev_entry = MagicMock()
mock_dev_entry.id = "dev_123"
mock_dev_entry.name = "Google Jules Gateway"
mock_dev_entry.identifiers = {("jules", "test_jules_entry")}
mock_dev_entry.manufacturer = "Google Jules"
mock_dev_entry.model = "AI Gateway & Router"
mock_dev_entry.sw_version = "0.1.0"
mock_dev_entry.configuration_url = "https://jules.googleapis.com/v1alpha"
dr_module.async_get = MagicMock(return_value=mock_dev_reg)
dr_module.async_entries_for_config_entry = MagicMock(return_value=[mock_dev_entry])

er_module = sys.modules["homeassistant.helpers.entity_registry"]
mock_ent_reg = MagicMock()
mock_ent_entry = MagicMock()
mock_ent_entry.entity_id = "sensor.jules_gateway_response_time"
mock_ent_entry.domain = "sensor"
mock_ent_entry.platform = "jules"
mock_ent_entry.unique_id = "test_jules_entry_latency_ms"
mock_ent_entry.disabled = False
mock_ent_entry.disabled_by = None
mock_ent_entry.entity_category = None
er_module.async_get = MagicMock(return_value=mock_ent_reg)
er_module.async_entries_for_config_entry = MagicMock(return_value=[mock_ent_entry])

# Conversation module
conv_module = sys.modules["homeassistant.components.conversation"]


class MockConversationEntity(MockEntity):
    _attr_supported_features = 1


conv_module.ConversationEntity = MockConversationEntity
conv_module.ConversationEntityFeature = types.SimpleNamespace(CONTROL=1)


@dataclass
class MockConversationInput:
    text: str
    context: Any = None
    conversation_id: str | None = None
    device_id: str | None = None
    language: str = "en"
    agent_id: str | None = None


conv_module.ConversationInput = MockConversationInput


@dataclass
class MockConversationResult:
    response: Any
    conversation_id: str | None = None


conv_module.ConversationResult = MockConversationResult


class MockIntentResponse:
    def __init__(self, language: str = "en") -> None:
        self.language = language
        self.speech: dict[str, Any] = {}

    def async_set_speech(self, speech: str) -> None:
        self.speech = {"plain": {"speech": speech}}


conv_module.intent = types.SimpleNamespace(IntentResponse=MockIntentResponse)

cfg_module = sys.modules["homeassistant.config_entries"]
cfg_module.ConfigFlow = MockConfigFlow
cfg_module.OptionsFlow = MockOptionsFlow
cfg_module.ConfigEntry = MagicMock

tpl_module = sys.modules["homeassistant.helpers.template"]


class MockTemplate:
    def __init__(self, template_str: str, hass: Any = None) -> None:
        self.template_str = template_str
        self.hass = hass

    def async_render(self, parse_result: bool = False) -> str:
        return self.template_str


tpl_module.Template = MockTemplate

aio_mod = sys.modules["homeassistant.helpers.aiohttp_client"]
aio_mod.async_get_clientsession = lambda hass: MagicMock()

sel_mod = sys.modules["homeassistant.helpers.selector"]
sel_mod.BooleanSelector = lambda *args, **kwargs: MagicMock()
sel_mod.NumberSelector = lambda *args, **kwargs: MagicMock()
sel_mod.NumberSelectorConfig = MagicMock
sel_mod.NumberSelectorMode = types.SimpleNamespace(BOX="box", SLIDER="slider")
sel_mod.TextSelector = lambda *args, **kwargs: MagicMock()
sel_mod.TextSelectorConfig = MagicMock
sel_mod.TextSelectorType = types.SimpleNamespace(
    TEXT="text", PASSWORD="password", URL="url"
)

cv_mod = sys.modules["homeassistant.helpers.config_validation"]
cv_mod.string = str
cv_mod.boolean = bool
cv_mod.positive_int = int


@pytest.fixture
def hass() -> MagicMock:
    """Mock Home Assistant core fixture."""
    mock = MagicMock()
    mock.data = {}
    mock.services = MagicMock()
    mock.services.has_service = MagicMock(return_value=False)
    mock.services.async_register = MagicMock()
    mock.config_entries = MagicMock()
    mock.config_entries.async_entries = MagicMock(return_value=[])
    mock.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    mock.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    mock.config_entries.async_reload = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_jules_entry"
    entry.version = "1.0.0"
    entry.title = "Google Jules"
    entry.data = {
        "api_url": "https://jules.googleapis.com/v1alpha",
        "api_key": "test-key-123",
    }
    entry.options = {
        "scan_interval": 60,
        "auto_approve": False,
        "default_source": "sources/github/FaserF/ha-jules",
        "default_branch": "main",
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock()
    return entry


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock JulesClient fixture."""
    client = MagicMock()
    client.async_get_sessions = AsyncMock(return_value=[])
    client.async_get_sources = AsyncMock(return_value=[])
    client.async_check_health = AsyncMock(return_value={"status": "healthy"})
    client.async_get_models = AsyncMock(return_value=["coding-cascade", "chat-cascade"])
    client.async_approve_plan = AsyncMock()
    client.async_send_reply = AsyncMock()
    client.async_cancel_session = AsyncMock()
    client.async_create_session = AsyncMock()
    client.async_execute_ai_task = AsyncMock(
        return_value={"status": "completed", "output": "Done"}
    )
    client.async_chat = AsyncMock(return_value={"response": "Hello"})
    client.compression_enabled = True
    return client


@pytest.fixture
def mock_coordinator(mock_config_entry: MagicMock) -> MagicMock:
    """Mock JulesDataUpdateCoordinator fixture."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.config_entry = mock_config_entry
    coordinator.data = {
        "sessions": [],
        "total_sessions": 0,
        "active_sessions": 0,
        "awaiting_approval": 0,
        "completed_sessions": 0,
        "failed_sessions": 0,
        "latest_session": None,
        "sources": [],
        "models": ["coding-cascade", "chat-cascade"],
        "healthy": True,
        "response_time_ms": 120,
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator
