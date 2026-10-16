"""Home Assistant Repairs issue management for Google Jules."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import CONF_API_URL, DOMAIN

ISSUE_AUTH_FAILED = "auth_failed_{entry_id}"
ISSUE_CANNOT_CONNECT = "cannot_connect_{entry_id}"


@callback
def async_create_auth_repair(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create a repair issue for authentication failure."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_AUTH_FAILED.format(entry_id=entry.entry_id),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="auth_failed",
        translation_placeholders={
            "api_url": entry.data.get(CONF_API_URL, "https://jules.googleapis.com"),
            "entry_title": entry.title,
        },
        data={"entry_id": entry.entry_id},
    )


@callback
def async_delete_auth_repair(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear the authentication failure repair issue."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        ISSUE_AUTH_FAILED.format(entry_id=entry.entry_id),
    )


@callback
def async_create_connection_repair(
    hass: HomeAssistant, entry: ConfigEntry, error: str
) -> None:
    """Create a repair issue for connection failure."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_CANNOT_CONNECT.format(entry_id=entry.entry_id),
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="cannot_connect",
        translation_placeholders={
            "api_url": entry.data.get(CONF_API_URL, "https://jules.googleapis.com"),
            "error": error,
            "entry_title": entry.title,
        },
        data={"entry_id": entry.entry_id},
    )


@callback
def async_delete_connection_repair(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear the connection failure repair issue."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        ISSUE_CANNOT_CONNECT.format(entry_id=entry.entry_id),
    )


class JulesAuthRepairFlow(RepairsFlow):
    """Handler for an authentication repair flow."""

    def __init__(self, entry_id: str) -> None:
        """Initialize repair flow."""
        self.entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle first step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Confirm step triggers reauthentication flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create repair fix flow."""
    entry_id = data.get("entry_id", "") if data else ""
    return JulesAuthRepairFlow(entry_id)
