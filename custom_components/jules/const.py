"""Constants for the Google Jules integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "jules"
INTEGRATION_VERSION: Final = "2026.10.5"
LOGGER: Final = logging.getLogger(__package__)

DEFAULT_NAME: Final = "Google Jules"
DEFAULT_API_URL: Final = "https://jules.googleapis.com/v1alpha"
DEFAULT_SCAN_INTERVAL: Final = 60  # seconds

# Config keys
CONF_API_KEY: Final = "api_key"
CONF_API_URL: Final = "api_url"
CONF_AUTO_APPROVE: Final = "auto_approve"
CONF_DEFAULT_SOURCE: Final = "default_source"
CONF_DEFAULT_BRANCH: Final = "default_branch"
CONF_TOKEN_COMPRESSION: Final = "token_compression"

# Conversation & AI Task options
CONF_CHAT_MODEL: Final = "chat_model"
CONF_PROMPT: Final = "prompt"
CONF_TEMPERATURE: Final = "temperature"
CONF_TOP_P: Final = "top_p"
CONF_MAX_TOKENS: Final = "max_tokens"
CONF_LLM_HASS_API: Final = "llm_hass_api"

CONF_AI_TASK_MODEL: Final = "ai_task_model"
CONF_AI_TASK_PROMPT: Final = "ai_task_prompt"
CONF_AI_TASK_TEMPERATURE: Final = "ai_task_temperature"
CONF_AI_TASK_MAX_TOKENS: Final = "ai_task_max_tokens"

# Defaults
DEFAULT_CHAT_MODEL: Final = "coding-cascade"
DEFAULT_AI_TASK_MODEL: Final = "coding-cascade"
DEFAULT_FAST_MODEL: Final = "fast-cascade"
DEFAULT_CASCADES: Final[list[str]] = [
    "coding-cascade",
    "chat-cascade",
    "fast-cascade",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]

DEFAULT_TEMPERATURE: Final = 0.7
DEFAULT_TOP_P: Final = 1.0
DEFAULT_MAX_TOKENS: Final = 2048
DEFAULT_AI_TASK_TEMPERATURE: Final = 0.2
DEFAULT_AI_TASK_MAX_TOKENS: Final = 4096
DEFAULT_TOKEN_COMPRESSION: Final = True

DEFAULT_PROMPT: Final = (
    "You are Jules, Google Labs' autonomous AI coding and smart home automation specialist. "
    "You assist users with smart home control, analyzing Home Assistant automations, debugging configuration issues, "
    "and dispatching and managing autonomous coding sessions in GitHub repositories. "
    "You can inspect session states, show code diffs, review file changes, approve generated plans, "
    "and inspect bash terminal outputs executed by Jules."
)
DEFAULT_AI_TASK_PROMPT: Final = (
    "You are Jules AI Task Engine. You analyze smart home state, optimize automations, "
    "diagnose error logs, and generate clean YAML and code."
)

# Storage keys
DATA_COORDINATOR: Final = "coordinator"
DATA_CLIENT: Final = "client"
DATA_AI_TASK_ENTITY: Final = "ai_task_entity"
DATA_IMAGE_ENTITY: Final = "latest_image_entity"
DATA_EVENT_ENTITY: Final = "session_event_entity"

# Platforms
PLATFORM_AI_TASK: Final = "ai_task"
PLATFORMS: Final[list[Platform | str]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CONVERSATION,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.EVENT,
    Platform.IMAGE,
    PLATFORM_AI_TASK,
]

# Service names (Full parity with @google/jules-mcp + Smart Home AI)
SERVICE_CREATE_SESSION: Final = "create_session"
SERVICE_LIST_SESSIONS: Final = "list_sessions"
SERVICE_GET_SESSION_STATE: Final = "get_session_state"
SERVICE_GET_BASH_OUTPUTS: Final = "get_bash_outputs"
SERVICE_GET_CODE_REVIEW: Final = "get_code_review_context"
SERVICE_SHOW_CODE_DIFF: Final = "show_code_diff"
SERVICE_SEND_REPLY: Final = "send_reply"
SERVICE_APPROVE_PLAN: Final = "approve_plan"
SERVICE_CANCEL_SESSION: Final = "cancel_session"
SERVICE_SEND_MESSAGE: Final = "send_message"
SERVICE_REFRESH_SESSIONS: Final = "refresh_sessions"
SERVICE_EXECUTE_AI_TASK: Final = "execute_ai_task"
SERVICE_ANALYZE_AUTOMATION: Final = "analyze_automation"
SERVICE_SUGGEST_AUTOMATIONS: Final = "suggest_automations"
SERVICE_DIAGNOSE_LOGS: Final = "diagnose_logs"
SERVICE_ANALYZE_CAMERA: Final = "analyze_camera"

# Semantic Status (matching @google/jules-mcp)
STATUS_BUSY: Final = "busy"
STATUS_STABLE: Final = "stable"
STATUS_FAILED: Final = "failed"

# Max tool calling iterations in conversation agent
MAX_TOOL_ITERATIONS: Final = 10

# Jules Session States
STATE_UNSPECIFIED: Final = "UNSPECIFIED"
STATE_QUEUED: Final = "QUEUED"
STATE_PLANNING: Final = "PLANNING"
STATE_AWAITING_APPROVAL: Final = "AWAITING_APPROVAL"
STATE_AWAITING_PLAN_APPROVAL: Final = "AWAITING_PLAN_APPROVAL"
STATE_AWAITING_USER_FEEDBACK: Final = "AWAITING_USER_FEEDBACK"
STATE_IN_PROGRESS: Final = "IN_PROGRESS"
STATE_COMPLETED: Final = "COMPLETED"
STATE_FAILED: Final = "FAILED"
STATE_CANCELLED: Final = "CANCELLED"

ACTIVE_STATES: Final[set[str]] = {
    STATE_QUEUED,
    STATE_PLANNING,
    STATE_AWAITING_APPROVAL,
    STATE_AWAITING_PLAN_APPROVAL,
    STATE_AWAITING_USER_FEEDBACK,
    STATE_IN_PROGRESS,
}

# Attributes
ATTR_SESSION_ID: Final = "session_id"
ATTR_PROMPT: Final = "prompt"
ATTR_TITLE: Final = "title"
ATTR_STATE: Final = "state"
ATTR_SOURCE: Final = "source"
ATTR_BRANCH: Final = "branch"
ATTR_PR_URL: Final = "pr_url"
ATTR_PLAN: Final = "plan"
ATTR_ERROR_MESSAGE: Final = "error_message"
ATTR_CREATED_TIME: Final = "created_time"
ATTR_UPDATED_TIME: Final = "updated_time"
ATTR_TOTAL_SESSIONS: Final = "total_sessions"
ATTR_ACTIVE_SESSIONS: Final = "active_sessions"
ATTR_AWAITING_APPROVAL: Final = "awaiting_approval"
ATTR_COMPLETED_SESSIONS: Final = "completed_sessions"
ATTR_FAILED_SESSIONS: Final = "failed_sessions"
ATTR_SOURCES_LIST: Final = "sources_list"
ATTR_LATENCY_MS: Final = "latency_ms"
ATTR_ACTIVE_MODELS: Final = "active_models"
