"""Custom services for the Google Jules integration."""

from __future__ import annotations

import base64
import time
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import camera, persistent_notification
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError

from .client import JulesClient
from .const import (
    CONF_AI_TASK_MODEL,
    CONF_AUTO_APPROVE,
    CONF_DEFAULT_BRANCH,
    CONF_DEFAULT_SOURCE,
    DATA_AI_TASK_ENTITY,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_IMAGE_ENTITY,
    DEFAULT_AI_TASK_MODEL,
    DOMAIN,
    LOGGER,
    SERVICE_ANALYZE_AUTOMATION,
    SERVICE_ANALYZE_CAMERA,
    SERVICE_APPROVE_PLAN,
    SERVICE_CANCEL_SESSION,
    SERVICE_CREATE_SESSION,
    SERVICE_DIAGNOSE_LOGS,
    SERVICE_EXECUTE_AI_TASK,
    SERVICE_GET_BASH_OUTPUTS,
    SERVICE_GET_CODE_REVIEW,
    SERVICE_GET_SESSION_STATE,
    SERVICE_LIST_SESSIONS,
    SERVICE_REFRESH_SESSIONS,
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_REPLY,
    SERVICE_SHOW_CODE_DIFF,
    SERVICE_SUGGEST_AUTOMATIONS,
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

CANCEL_SESSION_SCHEMA = vol.Schema(
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

LIST_SESSIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("page_size", default=10): vol.Coerce(int),
        vol.Optional("entry_id"): cv.string,
    }
)

GET_SESSION_STATE_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

GET_BASH_OUTPUTS_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("activity_ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("entry_id"): cv.string,
    }
)

GET_CODE_REVIEW_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("format", default="markdown"): cv.string,
        vol.Optional("filter", default="all"): cv.string,
        vol.Optional("detail", default="standard"): cv.string,
        vol.Optional("activity_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SHOW_CODE_DIFF_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("file"): cv.string,
        vol.Optional("activity_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SEND_REPLY_SCHEMA = vol.Schema(
    {
        vol.Optional("session_id"): cv.string,
        vol.Optional("action", default="send"): cv.string,
        vol.Optional("message"): cv.string,
        vol.Optional("plan_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

REFRESH_SESSIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)

EXECUTE_AI_TASK_SCHEMA = vol.Schema(
    {
        vol.Required("prompt"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("system_prompt"): cv.string,
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("max_tokens"): vol.Coerce(int),
        vol.Optional("entry_id"): cv.string,
    }
)

ANALYZE_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Optional("automation_entity_id"): cv.string,
        vol.Optional("automation_yaml"): cv.string,
        vol.Optional("custom_prompt"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SUGGEST_AUTOMATIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("domains"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("entity_limit", default=30): vol.Coerce(int),
        vol.Optional("custom_prompt"): cv.string,
        vol.Optional("model", default=DEFAULT_AI_TASK_MODEL): cv.string,
        vol.Optional("send_notification", default=True): cv.boolean,
        vol.Optional("entry_id"): cv.string,
    }
)

DIAGNOSE_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("log_text"): cv.string,
        vol.Optional("hours_back", default=2): vol.Coerce(int),
        vol.Optional("custom_prompt"): cv.string,
        vol.Optional("model", default=DEFAULT_AI_TASK_MODEL): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

ANALYZE_CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required("camera_entity_id"): cv.entity_id,
        vol.Optional(
            "prompt",
            default="Describe what you see in this security camera snapshot in detail, highlighting any people, activity, or risks.",
        ): cv.string,
        vol.Optional("model", default=DEFAULT_AI_TASK_MODEL): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)


def _get_entry_context(
    hass: HomeAssistant, entry_id: str | None = None
) -> tuple[JulesClient, JulesDataUpdateCoordinator, dict[str, Any], Any | None]:
    """Resolve client, coordinator, entry options/data, and optional ai_task_entity."""
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
    ai_task_entity = entry_data.get(DATA_AI_TASK_ENTITY)
    config_entry = coordinator.config_entry

    defaults = {
        CONF_DEFAULT_SOURCE: config_entry.options.get(
            CONF_DEFAULT_SOURCE, config_entry.data.get(CONF_DEFAULT_SOURCE, "")
        ),
        CONF_DEFAULT_BRANCH: config_entry.options.get(CONF_DEFAULT_BRANCH, "main"),
        CONF_AUTO_APPROVE: config_entry.options.get(
            CONF_AUTO_APPROVE, config_entry.data.get(CONF_AUTO_APPROVE, False)
        ),
        CONF_AI_TASK_MODEL: config_entry.options.get(
            CONF_AI_TASK_MODEL,
            config_entry.data.get(CONF_AI_TASK_MODEL, DEFAULT_AI_TASK_MODEL),
        ),
    }

    return client, coordinator, defaults, ai_task_entity


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Google Jules services."""

    async def handle_create_session(call: ServiceCall) -> ServiceResponse:
        """Handle creating a new coding session."""
        prompt = call.data["prompt"]
        entry_id = call.data.get("entry_id")
        client, coordinator, defaults, _ = _get_entry_context(hass, entry_id)

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

    async def handle_approve_plan(call: ServiceCall) -> ServiceResponse:
        """Handle approving a session plan."""
        session_id = call.data.get("session_id")
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)

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

    async def handle_cancel_session(call: ServiceCall) -> ServiceResponse:
        """Handle cancelling or stopping an active Jules coding session."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        LOGGER.info("Cancelling Jules session %s", session_id)
        result = await client.async_cancel_session(session_id)
        await coordinator.async_request_refresh()
        return {"session_id": session_id, "status": "cancelled", "result": result}

    async def handle_send_message(call: ServiceCall) -> ServiceResponse:
        """Handle sending feedback/message to a session."""
        message = call.data["message"]
        session_id = call.data.get("session_id")
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)

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

    def _resolve_session_id(
        coordinator: JulesDataUpdateCoordinator, raw_id: str | None
    ) -> str:
        """Resolve session ID from argument or latest known session."""
        if raw_id:
            return raw_id
        latest = (coordinator.data or {}).get("latest_session")
        if latest:
            return str(latest.get("name") or latest.get("id") or "")
        sessions = (coordinator.data or {}).get("sessions", [])
        if sessions:
            return str(sessions[0].get("name") or sessions[0].get("id") or "")
        raise HomeAssistantError(
            "No session ID specified and no active or recent session found"
        )

    async def handle_list_sessions(call: ServiceCall) -> ServiceResponse:
        """Handle listing recent Jules sessions matching @google/jules-mcp."""
        page_size = call.data.get("page_size", 10)
        entry_id = call.data.get("entry_id")
        client, _, _, _ = _get_entry_context(hass, entry_id)
        sessions = await client.async_get_sessions(page_size=page_size)
        return {"sessions": sessions, "count": len(sessions)}

    async def handle_get_session_state(call: ServiceCall) -> ServiceResponse:
        """Handle getting session operational dashboard status matching @google/jules-mcp."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        return await client.async_get_session_state(session_id)

    async def handle_get_bash_outputs(call: ServiceCall) -> ServiceResponse:
        """Handle getting bash terminal outputs from a Jules session matching @google/jules-mcp."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        activity_ids = call.data.get("activity_ids")
        return await client.async_get_bash_outputs(
            session_id, activity_ids=activity_ids
        )

    async def handle_get_code_review_context(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle reviewing code changes and file additions/deletions matching @google/jules-mcp."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        fmt = call.data.get("format", "markdown")
        flt = call.data.get("filter", "all")
        det = call.data.get("detail", "standard")
        act_id = call.data.get("activity_id")
        return await client.async_get_code_review_context(
            session_id=session_id,
            format=fmt,
            filter_type=flt,
            detail=det,
            activity_id=act_id,
        )

    async def handle_show_code_diff(call: ServiceCall) -> ServiceResponse:
        """Handle showing unified code diff patch matching @google/jules-mcp."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        target_file = call.data.get("file")
        act_id = call.data.get("activity_id")
        return await client.async_show_code_diff(
            session_id=session_id,
            file=target_file,
            activity_id=act_id,
        )

    async def handle_send_reply(call: ServiceCall) -> ServiceResponse:
        """Handle interacting with an active Jules session matching @google/jules-mcp."""
        entry_id = call.data.get("entry_id")
        client, coordinator, _, _ = _get_entry_context(hass, entry_id)
        session_id = _resolve_session_id(coordinator, call.data.get("session_id"))
        action = call.data.get("action", "send")
        message = call.data.get("message")
        plan_id = call.data.get("plan_id")
        res = await client.async_send_reply(
            session_id=session_id,
            action=action,
            message=message,
            plan_id=plan_id,
        )
        await coordinator.async_request_refresh()
        return res

    async def handle_refresh_sessions(call: ServiceCall) -> ServiceResponse:
        """Handle manual data refresh."""
        entry_id = call.data.get("entry_id")
        _, coordinator, _, _ = _get_entry_context(hass, entry_id)
        await coordinator.async_request_refresh()
        return {"status": "refreshed"}

    async def handle_execute_ai_task(call: ServiceCall) -> ServiceResponse:
        """Execute arbitrary AI reasoning or generative task."""
        prompt = call.data["prompt"]
        entry_id = call.data.get("entry_id")
        client, _, defaults, ai_task_entity = _get_entry_context(hass, entry_id)

        model = call.data.get("model") or defaults[CONF_AI_TASK_MODEL]
        system_prompt = call.data.get("system_prompt")
        temperature = call.data.get("temperature")
        max_tokens = call.data.get("max_tokens")

        if ai_task_entity:
            return await ai_task_entity.async_execute_task(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        messages = [
            {
                "role": "system",
                "content": system_prompt or "You are Jules AI Task Engine.",
            },
            {"role": "user", "content": prompt},
        ]
        start = time.perf_counter()
        resp = await client.async_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature if temperature is not None else 0.2,
            max_tokens=max_tokens if max_tokens is not None else 2048,
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        choices = resp.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        return {
            "response": content,
            "model": model,
            "latency_ms": elapsed_ms,
            "usage": resp.get("usage", {}),
        }

    async def handle_analyze_automation(call: ServiceCall) -> ServiceResponse:
        """Analyze a Home Assistant automation and recommend fixes / improvements."""
        entity_id = call.data.get("automation_entity_id")
        raw_yaml = call.data.get("automation_yaml")
        custom_prompt = call.data.get("custom_prompt")
        model = call.data.get("model")
        entry_id = call.data.get("entry_id")
        client, _, defaults, _ = _get_entry_context(hass, entry_id)
        selected_model = model or defaults[CONF_AI_TASK_MODEL]

        automation_info = ""
        if entity_id:
            state = hass.states.get(entity_id)
            if state:
                automation_info = (
                    f"Entity ID: {entity_id}\n"
                    f"Friendly Name: {state.attributes.get('friendly_name')}\n"
                    f"State: {state.state}\n"
                    f"Attributes: {state.attributes}\n"
                )
            else:
                automation_info = (
                    f"Entity ID: {entity_id} (not found in current state machine)"
                )

        if raw_yaml:
            automation_info += f"\nAutomation YAML:\n```yaml\n{raw_yaml}\n```\n"

        if not automation_info:
            raise HomeAssistantError(
                "Must provide either automation_entity_id or automation_yaml"
            )

        user_content = (
            f"Please analyze this Home Assistant automation in detail:\n\n{automation_info}\n\n"
            f"Instructions:\n"
            f"1. Identify potential bugs, race conditions, edge cases, or mode conflicts.\n"
            f"2. Suggest reliability and performance optimizations.\n"
            f"3. Provide a complete, improved replacement YAML block.\n"
        )
        if custom_prompt:
            user_content += f"\nAdditional User Instructions: {custom_prompt}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Jules, Home Assistant automation engineer and expert troubleshooter. "
                    "Analyze automations rigorously and provide clean, modern Home Assistant YAML."
                ),
            },
            {"role": "user", "content": user_content},
        ]

        resp = await client.async_chat_completion(
            messages=messages,
            model=selected_model,
            temperature=0.2,
            max_tokens=3000,
        )
        choices = resp.get("choices", [])
        analysis = choices[0].get("message", {}).get("content", "") if choices else ""
        return {
            "entity_id": entity_id,
            "analysis": analysis,
            "model": selected_model,
        }

    async def handle_suggest_automations(call: ServiceCall) -> ServiceResponse:
        """Analyze existing devices and suggest new high-value automations."""
        target_domains = call.data.get("domains")
        entity_limit = call.data.get("entity_limit", 30)
        custom_prompt = call.data.get("custom_prompt")
        model = call.data.get("model", DEFAULT_AI_TASK_MODEL)
        send_notif = call.data.get("send_notification", True)
        entry_id = call.data.get("entry_id")
        client, _, _, _ = _get_entry_context(hass, entry_id)

        all_states = hass.states.async_all()
        filtered = []
        for s in all_states:
            domain = s.entity_id.split(".")[0]
            if target_domains and domain not in target_domains:
                continue
            if domain in (
                "light",
                "switch",
                "binary_sensor",
                "sensor",
                "climate",
                "cover",
                "media_player",
            ):
                filtered.append(
                    f"- {s.entity_id}: state={s.state}, name={s.attributes.get('friendly_name')}"
                )
            if len(filtered) >= entity_limit:
                break

        entities_summary = "\n".join(filtered)
        user_prompt = (
            f"Analyze these available Home Assistant entities:\n{entities_summary}\n\n"
            f"Suggest 3 creative, practical, and highly reliable automations. "
            f"For each suggestion, provide:\n"
            f"- Title & Purpose\n"
            f"- Trigger, Condition, and Action explanation\n"
            f"- Complete Home Assistant automation YAML block\n"
        )
        if custom_prompt:
            user_prompt += f"\nUser Goal / Preferences: {custom_prompt}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Jules, smart home architect for Home Assistant. "
                    "You design practical, reliable, and elegant automation scenarios."
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

        resp = await client.async_chat_completion(
            messages=messages,
            model=model,
            temperature=0.4,
            max_tokens=3500,
        )
        choices = resp.get("choices", [])
        suggestions = (
            choices[0].get("message", {}).get("content", "") if choices else ""
        )

        if send_notif:
            persistent_notification.async_create(
                hass,
                suggestions[:1000] + ("..." if len(suggestions) > 1000 else ""),
                title="Google Jules Automation Ideas 💡",
                notification_id="jules_automation_suggestions",
            )

        return {
            "suggestions": suggestions,
            "entities_analyzed": len(filtered),
            "model": model,
        }

    async def handle_diagnose_logs(call: ServiceCall) -> ServiceResponse:
        """Analyze Home Assistant error logs and provide actionable fix guidance."""
        log_text = call.data.get("log_text")
        custom_prompt = call.data.get("custom_prompt")
        model = call.data.get("model", DEFAULT_AI_TASK_MODEL)
        entry_id = call.data.get("entry_id")
        client, _, _, _ = _get_entry_context(hass, entry_id)

        logs_content = log_text or ""
        if not logs_content:
            # Fallback to system log entries if available
            system_log = hass.data.get("system_log")
            if system_log and hasattr(system_log, "records"):
                records = [
                    f"[{r.level}] {r.name}: {r.message}"
                    for r in list(system_log.records)[-20:]
                ]
                logs_content = "\n".join(records)

        if not logs_content:
            logs_content = (
                "No direct error log text provided or found in recent system log cache."
            )

        user_prompt = (
            f"Analyze the following Home Assistant error log excerpt:\n\n```text\n{logs_content}\n```\n\n"
            f"Please identify:\n"
            f"1. Root cause of each error\n"
            f"2. Severity (Benign vs Critical)\n"
            f"3. Concrete step-by-step instructions to fix each issue\n"
        )
        if custom_prompt:
            user_prompt += f"\nAdditional Context: {custom_prompt}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Jules, senior Python and Home Assistant core debugging expert. "
                    "Diagnose log traces clearly and provide actionable solutions."
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

        resp = await client.async_chat_completion(
            messages=messages,
            model=model,
            temperature=0.2,
            max_tokens=3000,
        )
        choices = resp.get("choices", [])
        diagnosis = choices[0].get("message", {}).get("content", "") if choices else ""
        return {"diagnosis": diagnosis, "model": model}

    async def handle_analyze_camera(call: ServiceCall) -> ServiceResponse:
        """Capture camera frame and analyze image with Jules vision."""
        camera_entity_id = call.data["camera_entity_id"]
        prompt = call.data.get(
            "prompt", "Describe this security camera image in detail."
        )
        model = call.data.get("model", DEFAULT_AI_TASK_MODEL)
        entry_id = call.data.get("entry_id")
        client, _, _, _ = _get_entry_context(hass, entry_id)

        try:
            image_frame = await camera.async_get_image(hass, camera_entity_id)
        except Exception as exc:
            raise HomeAssistantError(
                f"Failed to capture snapshot from {camera_entity_id}: {exc}"
            ) from exc

        b64_image = base64.b64encode(image_frame.content).decode("utf-8")
        data_url = f"data:{image_frame.content_type};base64,{b64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        resp = await client.async_chat_completion(
            messages=messages,
            model=model,
            temperature=0.3,
            max_tokens=2048,
        )
        choices = resp.get("choices", [])
        analysis = choices[0].get("message", {}).get("content", "") if choices else ""

        # Update latest analyzed image entity in HA if present
        target_entry_id = entry_id or next(iter(hass.data.get(DOMAIN, {})), None)
        if target_entry_id and target_entry_id in hass.data.get(DOMAIN, {}):
            entry_dict = hass.data[DOMAIN][target_entry_id]
            if DATA_IMAGE_ENTITY in entry_dict:
                img_entity = entry_dict[DATA_IMAGE_ENTITY]
                if hasattr(img_entity, "set_image"):
                    img_entity.set_image(
                        image_data=image_frame.content,
                        analysis_text=analysis,
                        camera_entity_id=camera_entity_id,
                        prompt=prompt,
                    )

        return {
            "camera_entity_id": camera_entity_id,
            "analysis": analysis,
            "model": model,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SESSION,
        handle_create_session,
        schema=CREATE_SESSION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_SESSION,
        handle_cancel_session,
        schema=CANCEL_SESSION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_SESSIONS,
        handle_list_sessions,
        schema=LIST_SESSIONS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SESSION_STATE,
        handle_get_session_state,
        schema=GET_SESSION_STATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_BASH_OUTPUTS,
        handle_get_bash_outputs,
        schema=GET_BASH_OUTPUTS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CODE_REVIEW,
        handle_get_code_review_context,
        schema=GET_CODE_REVIEW_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SHOW_CODE_DIFF,
        handle_show_code_diff,
        schema=SHOW_CODE_DIFF_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_REPLY,
        handle_send_reply,
        schema=SEND_REPLY_SCHEMA,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_AI_TASK,
        handle_execute_ai_task,
        schema=EXECUTE_AI_TASK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_AUTOMATION,
        handle_analyze_automation,
        schema=ANALYZE_AUTOMATION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SUGGEST_AUTOMATIONS,
        handle_suggest_automations,
        schema=SUGGEST_AUTOMATIONS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DIAGNOSE_LOGS,
        handle_diagnose_logs,
        schema=DIAGNOSE_LOGS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_CAMERA,
        handle_analyze_camera,
        schema=ANALYZE_CAMERA_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Google Jules services."""
    for service in (
        SERVICE_CREATE_SESSION,
        SERVICE_CANCEL_SESSION,
        SERVICE_LIST_SESSIONS,
        SERVICE_GET_SESSION_STATE,
        SERVICE_GET_BASH_OUTPUTS,
        SERVICE_GET_CODE_REVIEW,
        SERVICE_SHOW_CODE_DIFF,
        SERVICE_SEND_REPLY,
        SERVICE_APPROVE_PLAN,
        SERVICE_SEND_MESSAGE,
        SERVICE_REFRESH_SESSIONS,
        SERVICE_EXECUTE_AI_TASK,
        SERVICE_ANALYZE_AUTOMATION,
        SERVICE_SUGGEST_AUTOMATIONS,
        SERVICE_DIAGNOSE_LOGS,
        SERVICE_ANALYZE_CAMERA,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
