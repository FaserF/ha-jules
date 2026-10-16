"""Config flow for Google Jules integration."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import CannotConnect, InvalidAuth, JulesClient
from .const import (
    CONF_AI_TASK_MODEL,
    CONF_API_KEY,
    CONF_API_URL,
    CONF_AUTO_APPROVE,
    CONF_CHAT_MODEL,
    CONF_DEFAULT_BRANCH,
    CONF_DEFAULT_SOURCE,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_AI_TASK_MODEL,
    DEFAULT_API_URL,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_NAME,
    DEFAULT_PROMPT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    LOGGER,
)


class JulesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Jules."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._reconfigure_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip()
            api_url = user_input.get(CONF_API_URL, DEFAULT_API_URL).strip()

            # Hash key for unique_id
            key_hash = hashlib.sha256(f"{api_url}_{api_key}".encode()).hexdigest()[:12]
            await self.async_set_unique_id(f"jules_{key_hash}")
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = JulesClient(session=session, api_key=api_key, api_url=api_url)

            try:
                await client.async_test_connection()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:
                LOGGER.exception("Unexpected error during connection test: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input.get("title") or DEFAULT_NAME,
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_DEFAULT_SOURCE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_AUTO_APPROVE, default=False): BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        self._reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm(user_input)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and validate reconfigured parameters."""
        errors: dict[str, str] = {}
        entry = self._reconfigure_entry
        assert entry is not None

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip()
            api_url = user_input.get(
                CONF_API_URL, entry.data.get(CONF_API_URL, DEFAULT_API_URL)
            ).strip()

            session = async_get_clientsession(self.hass)
            client = JulesClient(session=session, api_key=api_key, api_url=api_url)

            try:
                await client.async_test_connection()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:
                LOGGER.exception("Unexpected error during reconfigure test: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY, default=entry.data.get(CONF_API_KEY, "")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Optional(
                    CONF_API_URL, default=entry.data.get(CONF_API_URL, DEFAULT_API_URL)
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Optional(
                    CONF_DEFAULT_SOURCE,
                    default=entry.data.get(CONF_DEFAULT_SOURCE, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_AUTO_APPROVE,
                    default=entry.data.get(CONF_AUTO_APPROVE, False),
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return JulesOptionsFlowHandler()


class JulesOptionsFlowHandler(OptionsFlow):
    """Handle Jules options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CHAT_MODEL,
                    default=self.config_entry.options.get(
                        CONF_CHAT_MODEL,
                        self.config_entry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_AI_TASK_MODEL,
                    default=self.config_entry.options.get(
                        CONF_AI_TASK_MODEL,
                        self.config_entry.data.get(
                            CONF_AI_TASK_MODEL, DEFAULT_AI_TASK_MODEL
                        ),
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_PROMPT,
                    default=self.config_entry.options.get(
                        CONF_PROMPT,
                        self.config_entry.data.get(CONF_PROMPT, DEFAULT_PROMPT),
                    ),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=self.config_entry.options.get(
                        CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.1,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=self.config_entry.options.get(
                        CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=100,
                        max=8192,
                        step=100,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    "scan_interval",
                    default=self.config_entry.options.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=15,
                        max=3600,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Optional(
                    CONF_AUTO_APPROVE,
                    default=self.config_entry.options.get(
                        CONF_AUTO_APPROVE,
                        self.config_entry.data.get(CONF_AUTO_APPROVE, False),
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_DEFAULT_SOURCE,
                    default=self.config_entry.options.get(
                        CONF_DEFAULT_SOURCE,
                        self.config_entry.data.get(CONF_DEFAULT_SOURCE, ""),
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_DEFAULT_BRANCH,
                    default=self.config_entry.options.get(CONF_DEFAULT_BRANCH, "main"),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
