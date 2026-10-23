"""Support for Google Jules AI Task platform."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import JulesClient
from .const import (
    CONF_AI_TASK_MAX_TOKENS,
    CONF_AI_TASK_MODEL,
    CONF_AI_TASK_PROMPT,
    CONF_AI_TASK_TEMPERATURE,
    DATA_AI_TASK_ENTITY,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_AI_TASK_MAX_TOKENS,
    DEFAULT_AI_TASK_MODEL,
    DEFAULT_AI_TASK_PROMPT,
    DEFAULT_AI_TASK_TEMPERATURE,
    DOMAIN,
    LOGGER,
)
from .coordinator import JulesDataUpdateCoordinator
from .helpers import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AI Task entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: JulesClient = data[DATA_CLIENT]
    coordinator: JulesDataUpdateCoordinator = data[DATA_COORDINATOR]

    entity = JulesAITaskEntity(entry, client, coordinator)
    data[DATA_AI_TASK_ENTITY] = entity
    async_add_entities([entity])


class JulesAITaskEntity(CoordinatorEntity[JulesDataUpdateCoordinator], Entity):
    """Jules AI Task entity for smart home reasoning and generative workflows."""

    _attr_has_entity_name = True
    _attr_name = "Task Engine"

    def __init__(
        self,
        entry: ConfigEntry,
        client: JulesClient,
        coordinator: JulesDataUpdateCoordinator,
    ) -> None:
        """Initialize the AI Task entity."""
        super().__init__(coordinator)
        self.entry = entry
        self.client = client
        self._attr_unique_id = f"{entry.entry_id}_ai_task"
        self._attr_device_info = get_device_info(entry)
        self._tasks_executed = 0
        self._last_latency_ms: float | None = None
        self._last_model_used: str | None = None
        self._last_task_timestamp: str | None = None
        self._state = "ready"

        try:
            from homeassistant.components.ai_task import AITaskEntityFeature

            self._attr_supported_features = (
                AITaskEntityFeature.GENERATE_DATA
                | getattr(AITaskEntityFeature, "GENERATE_IMAGE", 0)
                | getattr(AITaskEntityFeature, "SUPPORT_ATTACHMENTS", 0)
            )
        except (ImportError, AttributeError):
            self._attr_supported_features = 7

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        options = self.entry.options
        return {
            "model": options.get(
                CONF_AI_TASK_MODEL,
                self.entry.data.get(CONF_AI_TASK_MODEL, DEFAULT_AI_TASK_MODEL),
            ),
            "temperature": options.get(
                CONF_AI_TASK_TEMPERATURE, DEFAULT_AI_TASK_TEMPERATURE
            ),
            "max_tokens": options.get(
                CONF_AI_TASK_MAX_TOKENS, DEFAULT_AI_TASK_MAX_TOKENS
            ),
            "tasks_executed": self._tasks_executed,
            "last_latency_ms": self._last_latency_ms,
            "last_model_used": self._last_model_used,
            "last_task_timestamp": self._last_task_timestamp,
        }

    async def async_execute_task(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Execute generative task and return structured output."""
        options = self.entry.options
        selected_model = model or options.get(
            CONF_AI_TASK_MODEL,
            self.entry.data.get(CONF_AI_TASK_MODEL, DEFAULT_AI_TASK_MODEL),
        )
        selected_temp = (
            temperature
            if temperature is not None
            else options.get(CONF_AI_TASK_TEMPERATURE, DEFAULT_AI_TASK_TEMPERATURE)
        )
        selected_max_tokens = (
            max_tokens
            if max_tokens is not None
            else options.get(CONF_AI_TASK_MAX_TOKENS, DEFAULT_AI_TASK_MAX_TOKENS)
        )
        sys_prompt = system_prompt or options.get(
            CONF_AI_TASK_PROMPT, DEFAULT_AI_TASK_PROMPT
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        self._state = "running"
        self.async_write_ha_state()

        start = time.perf_counter()
        try:
            resp = await self.client.async_chat_completion(
                messages=messages,
                model=selected_model,
                temperature=selected_temp,
                max_tokens=selected_max_tokens,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            self._tasks_executed += 1
            self._last_latency_ms = elapsed_ms
            self._last_model_used = selected_model
            self._last_task_timestamp = datetime.now(UTC).isoformat()
            self._state = "ready"
            self.async_write_ha_state()

            choices = resp.get("choices", [])
            output_text = (
                choices[0].get("message", {}).get("content", "") if choices else ""
            )
            usage = resp.get("usage", {})

            return {
                "response": output_text,
                "model": selected_model,
                "latency_ms": elapsed_ms,
                "usage": usage,
            }
        except Exception as err:
            self._state = "error"
            self.async_write_ha_state()
            LOGGER.error("Jules AI Task error: %s", err)
            raise
