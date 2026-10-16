"""Constants for the Google Jules integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "jules"
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

# Storage keys
DATA_COORDINATOR: Final = "coordinator"
DATA_CLIENT: Final = "client"

# Platforms
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

# Service names
SERVICE_CREATE_SESSION: Final = "create_session"
SERVICE_APPROVE_PLAN: Final = "approve_plan"
SERVICE_SEND_MESSAGE: Final = "send_message"
SERVICE_REFRESH_SESSIONS: Final = "refresh_sessions"

# Jules Session States
STATE_UNSPECIFIED: Final = "UNSPECIFIED"
STATE_QUEUED: Final = "QUEUED"
STATE_PLANNING: Final = "PLANNING"
STATE_AWAITING_APPROVAL: Final = "AWAITING_APPROVAL"
STATE_IN_PROGRESS: Final = "IN_PROGRESS"
STATE_COMPLETED: Final = "COMPLETED"
STATE_FAILED: Final = "FAILED"
STATE_CANCELLED: Final = "CANCELLED"

ACTIVE_STATES: Final[set[str]] = {
    STATE_QUEUED,
    STATE_PLANNING,
    STATE_AWAITING_APPROVAL,
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
