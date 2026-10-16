"""Custom services for the Google Jules integration."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .client import JulesClient
from .const import (
    CONF_AUTO_APPROVE,
    CONF_DEFAULT_BRANCH,
    CONF_DEFAULT_SOURCE,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
    SERVICE_APPROVE_PLAN,
    SERVICE_CREATE_SESSION,
    SERVICE_REFRESH_SESSIONS,
    SERVICE_SEND_MESSAGE,
    STATE_AWAITING_APPROVAL,
)
from .coordinator import JulesDataUpdateCoordinator

CREATE_SESSION_SCHEMA = vol.Schema(
    {
        vol.Required("prompt"): cv.string,
        vol.Optional("source"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("branch"): cv.string,
        vol.Optional("auto_approve"): cv.boolean,
        vol.Optional("entry_id"): cv.string,
    }
)

APPROVE_PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("session_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

REFRESH_SESSIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)


def _get_entry_context(
    hass: HomeAssistant, entry_id: str | None = None
) -> tuple[JulesClient, JulesDataUpdateCoordinator, dict[str, Any]]:
    """Resolve client, coordinator, and entry options/data."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("No Jules integration entries configured")

    target_entry_id = entry_id
    if not target_entry_id:
        target_entry_id = next(iter(entries.keys()))

    entry_data = entries.get(target_entry_id)
    if not entry_data:
        raise HomeAssistantError(f"Entry {target_entry_id} not found for Jules")

    client: JulesClient = entry_data[DATA_CLIENT]
    coordinator: JulesDataUpdateCoordinator = entry_data[DATA_COORDINATOR]
    config_entry = coordinator.config_entry

    defaults = {
        CONF_DEFAULT_SOURCE: config_entry.options.get(
            CONF_DEFAULT_SOURCE, config_entry.data.get(CONF_DEFAULT_SOURCE, "")
        ),
        CONF_DEFAULT_BRANCH: config_entry.options.get(CONF_DEFAULT_BRANCH, "main"),
        CONF_AUTO_APPROVE: config_entry.options.get(
            CONF_AUTO_APPROVE, config_entry.data.get(CONF_AUTO_APPROVE, False)
        ),
    }

    return client, coordinator, defaults


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Google Jules services."""

    async def handle_create_session(call: ServiceCall) -> dict[str, Any]:
        """Handle creating a new coding session."""
        prompt = call.data["prompt"]
        entry_id = call.data.get("entry_id")
        client, coordinator, defaults = _get_entry_context(hass, entry_id)

        source = call.data.get("source") or defaults[CONF_DEFAULT_SOURCE] or None
        branch = call.data.get("branch") or defaults[CONF_DEFAULT_BRANCH] or "main"
        title = call.data.get("title")
        auto_approve = call.data.get("auto_approve", defaults[CONF_AUTO_APPROVE])

        LOGGER.info("Creating Jules session for source '%s'", source)
        session_data = await client.async_create_session(
            prompt=prompt,
            source=source,
            title=title,
            branch=branch,
            auto_approve=auto_approve,
        )

        await coordinator.async_request_refresh()
        return {
            "session": session_data,
            "session_id": session_data.get("name") or session_data.get("id"),
            "title": session_data.get("title"),
            "state": session_data.get("state"),
        }

    async def handle_approve_plan(call: ServiceCall) -> dict[str, Any]:
        """Handle approving a session plan."""
        session_id = call.data.get("session_id")
        entry_id = call.data.get("entry_id")
        client, coordinator, _ = _get_entry_context(hass, entry_id)

        if not session_id:
            sessions = (coordinator.data or {}).get("sessions", [])
            for s in sessions:
                if (s.get("state") or "").upper() == STATE_AWAITING_APPROVAL:
                    session_id = s.get("name") or s.get("id")
                    break

        if not session_id:
            raise HomeAssistantError(
                "No session ID specified and no session awaiting approval"
            )

        LOGGER.info("Approving plan for session %s", session_id)
        result = await client.async_approve_plan(session_id)
        await coordinator.async_request_refresh()
        return {"session_id": session_id, "result": result}

    async def handle_send_message(call: ServiceCall) -> dict[str, Any]:
        """Handle sending feedback/message to a session."""
        message = call.data["message"]
        session_id = call.data.get("session_id")
        entry_id = call.data.get("entry_id")
        client, coordinator, _ = _get_entry_context(hass, entry_id)

        if not session_id:
            latest = (coordinator.data or {}).get("latest_session")
            if latest:
                session_id = latest.get("name") or latest.get("id")

        if not session_id:
            raise HomeAssistantError("No target session ID found to send message to")

        LOGGER.info("Sending message to session %s", session_id)
        result = await client.async_send_message(session_id, message)
        await coordinator.async_request_refresh()
        return {"session_id": session_id, "result": result}

    async def handle_refresh_sessions(call: ServiceCall) -> dict[str, Any]:
        """Handle manual data refresh."""
        entry_id = call.data.get("entry_id")
        _, coordinator, _ = _get_entry_context(hass, entry_id)
        await coordinator.async_request_refresh()
        return {"status": "refreshed"}

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SESSION,
        handle_create_session,
        schema=CREATE_SESSION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPROVE_PLAN,
        handle_approve_plan,
        schema=APPROVE_PLAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        handle_send_message,
        schema=SEND_MESSAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_SESSIONS,
        handle_refresh_sessions,
        schema=REFRESH_SESSIONS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Google Jules services."""
    for service in (
        SERVICE_CREATE_SESSION,
        SERVICE_APPROVE_PLAN,
        SERVICE_SEND_MESSAGE,
        SERVICE_REFRESH_SESSIONS,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
