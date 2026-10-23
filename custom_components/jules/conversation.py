"""Support for Google Jules conversation agent."""

from __future__ import annotations

import json
import uuid
from typing import Any

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import JulesClient
from .const import (
    CONF_CHAT_MODEL,
    CONF_DEFAULT_SOURCE,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
    LOGGER,
    MAX_TOOL_ITERATIONS,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: JulesClient = data[DATA_CLIENT]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    async_add_entities([JulesConversationEntity(entry, client, coordinator)])


class JulesConversationEntity(
    CoordinatorEntity[JulesDataUpdateCoordinator], ConversationEntity
):
    """Google Jules conversation agent entity."""

    _attr_has_entity_name = True
    _attr_name = "Assist"
    _attr_supported_features = ConversationEntityFeature.CONTROL

    def __init__(
        self,
        entry: ConfigEntry,
        client: JulesClient,
        coordinator: JulesDataUpdateCoordinator,
    ) -> None:
        """Initialize the conversation entity."""
        super().__init__(coordinator)
        self.entry = entry
        self.client = client
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        self._attr_device_info = get_device_info(entry)
        self.history: dict[str, list[dict[str, Any]]] = {}

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["*"]

    def _get_target_session_id(self, fn_args: dict[str, Any]) -> str:
        """Extract session ID from tool arguments or default to latest session."""
        if fn_args.get("session_id"):
            return str(fn_args["session_id"])
        data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        coordinator = data.get(DATA_COORDINATOR)
        if coordinator and coordinator.data:
            latest = coordinator.data.get("latest_session")
            if latest:
                return str(latest.get("name") or latest.get("id") or "")
            sessions = coordinator.data.get("sessions", [])
            if sessions:
                return str(sessions[0].get("name") or sessions[0].get("id") or "")
        return ""

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversational input sentence."""
        options = self.entry.options
        chat_model = options.get(
            CONF_CHAT_MODEL,
            self.entry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
        )
        prompt_raw = options.get(CONF_PROMPT, DEFAULT_PROMPT)
        temperature = options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        top_p = options.get(CONF_TOP_P, DEFAULT_TOP_P)
        max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)

        try:
            prompt_str = template.Template(prompt_raw, self.hass).async_render(
                parse_result=False
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Error rendering Jules prompt template: %s", exc)
            prompt_str = prompt_raw

        tools: list[dict[str, Any]] = []
        llm_api = None
        try:
            from homeassistant.helpers import llm

            llm_context = llm.LLMContext(
                platform=DOMAIN,
                context=user_input.context,
                language=user_input.language,
                assistant="conversation",
                device_id=user_input.device_id,
            )
            llm_api = await llm.async_get_api(
                self.hass, llm.LLM_API_ASSIST, llm_context
            )
            if llm_api and getattr(llm_api, "tools", None):
                tools.extend(
                    [
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.parameters,
                            },
                        }
                        for tool in llm_api.tools
                    ]
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("LLM tools could not be loaded: %s", exc)

        # Full Jules MCP toolset
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "create_jules_coding_session",
                        "description": "Dispatch an autonomous coding or refactoring session to Google Jules.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prompt": {
                                    "type": "string",
                                    "description": "The coding or bugfix instruction for Jules",
                                },
                                "source": {
                                    "type": "string",
                                    "description": "Target repository (e.g. FaserF/ha-jules)",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Short title for the task",
                                },
                                "branch": {
                                    "type": "string",
                                    "description": "Target git branch (default: main)",
                                },
                            },
                            "required": ["prompt"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "list_jules_sessions",
                        "description": "List recent Jules coding sessions with status, prompt, and PR details.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "page_size": {
                                    "type": "number",
                                    "description": "Maximum sessions to retrieve (default: 10)",
                                }
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_jules_session_state",
                        "description": "Get current status ('busy', 'stable', 'failed'), last activity, last agent message, and pending plan of a Jules session.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Target session ID (optional, defaults to latest)",
                                }
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "approve_jules_plan",
                        "description": "Approve a generated execution plan for a Jules session awaiting approval.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Session ID to approve (optional, defaults to session awaiting approval)",
                                }
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "send_jules_reply",
                        "description": "Send a message or follow-up feedback to an active Jules session.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Target session ID (optional, defaults to latest)",
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Feedback or prompt to send to Jules",
                                },
                                "action": {
                                    "type": "string",
                                    "enum": ["send", "ask", "approve"],
                                    "description": "Action type ('send' fire-and-forget, 'ask' waits for answer, 'approve' approves plan)",
                                },
                            },
                            "required": ["message"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_jules_code_review",
                        "description": "Review file changes, additions/deletions, and insights from a Jules session.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Target session ID (optional, defaults to latest)",
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["markdown", "summary", "tree", "detailed"],
                                    "description": "Output format",
                                },
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_jules_code_diff",
                        "description": "Get unified git code diff patch from a Jules session or specific file.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Target session ID (optional, defaults to latest)",
                                },
                                "file": {
                                    "type": "string",
                                    "description": "Specific file path to show diff for",
                                },
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_jules_bash_outputs",
                        "description": "Get bash shell commands executed by Jules in the cloud container, including stdout, stderr, and exit codes.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Target session ID (optional, defaults to latest)",
                                }
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "cancel_jules_session",
                        "description": "Cancel or stop an active or stuck Jules coding session.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Session ID to cancel (optional, defaults to latest session)",
                                }
                            },
                        },
                    },
                },
            ]
        )

        conversation_id = user_input.conversation_id or uuid.uuid4().hex
        prior_messages = self.history.get(conversation_id, [])

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": prompt_str},
            *prior_messages,
            {"role": "user", "content": user_input.text},
        ]

        iterations = 0
        final_text = "I encountered an issue processing your request."

        while iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            try:
                response = await self.client.async_chat_completion(
                    messages=messages,
                    model=chat_model,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    tools=tools if tools else None,
                )
            except Exception as err:
                LOGGER.error("Jules chat completion error: %s", err)
                final_text = f"Error communicating with Jules: {err}"
                break

            choices = response.get("choices", [])
            if not choices or "message" not in choices[0]:
                break

            msg = choices[0]["message"]
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                final_text = msg.get("content") or ""
                messages.append({"role": "assistant", "content": final_text})
                break

            # Handle tool calls
            messages.append(msg)
            for call in tool_calls:
                call_id = call.get("id", "")
                fn_name = call.get("function", {}).get("name", "")
                fn_args_raw = call.get("function", {}).get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw)
                except Exception:
                    fn_args = {}

                if fn_name == "create_jules_coding_session":
                    try:
                        source = fn_args.get("source") or self.entry.options.get(
                            CONF_DEFAULT_SOURCE,
                            self.entry.data.get(CONF_DEFAULT_SOURCE, ""),
                        )
                        task_res = await self.client.async_create_session(
                            prompt=fn_args["prompt"],
                            source=source,
                            title=fn_args.get("title"),
                            branch=fn_args.get("branch", "main"),
                        )
                        tool_content = json.dumps(
                            {
                                "status": "session_dispatched",
                                "session_id": task_res.get("id"),
                                "title": task_res.get("title"),
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "list_jules_sessions":
                    try:
                        page_size = fn_args.get("page_size", 10)
                        sessions = await self.client.async_get_sessions(
                            page_size=page_size
                        )
                        tool_content = json.dumps(
                            {"sessions": sessions, "count": len(sessions)}
                        )
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "get_jules_session_state":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            state_res = await self.client.async_get_session_state(s_id)
                            tool_content = json.dumps(state_res)
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "approve_jules_plan":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps(
                                {"error": "No session ID found to approve"}
                            )
                        else:
                            app_res = await self.client.async_approve_plan(s_id)
                            tool_content = json.dumps(
                                {
                                    "status": "approved",
                                    "session_id": s_id,
                                    "result": app_res,
                                }
                            )
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "send_jules_reply":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            rep_res = await self.client.async_send_reply(
                                session_id=s_id,
                                action=fn_args.get("action", "send"),
                                message=fn_args.get("message", ""),
                            )
                            tool_content = json.dumps(rep_res)
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "get_jules_code_review":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            rev_res = await self.client.async_get_code_review_context(
                                session_id=s_id,
                                format=fn_args.get("format", "markdown"),
                            )
                            tool_content = json.dumps(rev_res)
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "get_jules_code_diff":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            diff_res = await self.client.async_show_code_diff(
                                session_id=s_id,
                                file=fn_args.get("file"),
                            )
                            tool_content = json.dumps(diff_res)
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "get_jules_bash_outputs":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            bash_res = await self.client.async_get_bash_outputs(
                                session_id=s_id
                            )
                            tool_content = json.dumps(bash_res)
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif fn_name == "cancel_jules_session":
                    try:
                        s_id = self._get_target_session_id(fn_args)
                        if not s_id:
                            tool_content = json.dumps({"error": "No session ID found"})
                        else:
                            can_res = await self.client.async_cancel_session(
                                session_id=s_id
                            )
                            await self.coordinator.async_request_refresh()
                            tool_content = json.dumps(
                                {
                                    "status": "cancelled",
                                    "session_id": s_id,
                                    "result": can_res,
                                }
                            )
                    except Exception as exc:  # noqa: BLE001
                        tool_content = json.dumps({"error": str(exc)})
                elif llm_api:
                    try:
                        from homeassistant.helpers import llm

                        tool_input = llm.ToolInput(
                            id=call_id,
                            tool_name=fn_name,
                            tool_args=fn_args,
                        )
                        tool_res = await llm_api.async_call_tool(tool_input)
                        tool_content = json.dumps(tool_res)
                    except Exception as err:  # noqa: BLE001
                        LOGGER.warning("Tool execution error for %s: %s", fn_name, err)
                        tool_content = json.dumps({"error": str(err)})
                else:
                    tool_content = json.dumps(
                        {"error": f"Tool {fn_name} not supported"}
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": tool_content,
                    }
                )

        self.history[conversation_id] = messages[1:][-20:]

        intent_response = conversation.intent.IntentResponse(
            language=user_input.language
        )
        intent_response.async_set_speech(final_text)
        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )
