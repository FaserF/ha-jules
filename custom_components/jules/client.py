"""Asynchronous API client for Google Jules."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER


class JulesError(HomeAssistantError):
    """Base exception for Google Jules integration."""


class CannotConnect(JulesError):
    """Exception indicating connection failure."""


class InvalidAuth(JulesError):
    """Exception indicating invalid authentication."""


class SessionNotFoundError(JulesError):
    """Exception indicating requested session does not exist."""


class SourceNotFoundError(JulesError):
    """Exception indicating requested source does not exist."""


class JulesClient:
    """Async API Client for interacting with Google Jules and proxy gateways."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        api_url: str = "https://jules.googleapis.com/v1alpha",
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Jules client."""
        self._session = session
        self._api_key = api_key.strip() if api_key else ""
        self._timeout = timeout

        clean_url = api_url.rstrip("/")
        self._base_url = clean_url

    @property
    def base_url(self) -> str:
        """Return configured base URL."""
        return self._base_url

    def _get_headers(self) -> dict[str, str]:
        """Construct request headers with Google API and standard Bearer support."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "HomeAssistant-Jules/2026.10.0",
        }
        if self._api_key:
            # Google Cloud endpoints use x-goog-api-key
            headers["x-goog-api-key"] = self._api_key
            # Also provide standard Authorization header for proxies / OmniRoute
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _resolve_url(self, path: str) -> str:
        """Resolve endpoint URL safely handling base path prefixes."""
        clean_path = path.lstrip("/")
        return f"{self._base_url}/{clean_path}"

    async def _async_request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an asynchronous HTTP request with error translation."""
        url = self._resolve_url(path)
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params,
                ) as resp:
                    if resp.status in (401, 403):
                        error_text = await resp.text()
                        raise InvalidAuth(
                            f"Authentication failed ({resp.status}): {error_text}"
                        )
                    if resp.status == 404:
                        error_text = await resp.text()
                        raise SessionNotFoundError(
                            f"Resource not found (404): {error_text}"
                        )
                    if resp.status not in (200, 201, 204):
                        error_text = await resp.text()
                        raise JulesError(
                            f"HTTP error {resp.status} for {method} {url}: {error_text}"
                        )
                    if resp.status == 204:
                        return {}
                    return await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect(f"Connection error to {url}: {err}") from err

    async def async_test_connection(self) -> bool:
        """Verify API connectivity and authentication credentials."""
        # Check either /sessions, /sources or /models
        paths_to_try = ["sessions", "sources", "models"]
        last_error: Exception | None = None

        for path in paths_to_try:
            try:
                await self._async_request("GET", path, params={"pageSize": 1})
                return True
            except InvalidAuth:
                raise
            except Exception as err:
                last_error = err
                continue

        LOGGER.warning("Connection test failed across endpoints: %s", last_error)
        if last_error:
            raise CannotConnect(
                f"Unable to connect to Jules endpoint: {last_error}"
            ) from last_error
        return False

    async def async_get_sources(self) -> list[dict[str, Any]]:
        """Fetch authorized code repositories/sources."""
        try:
            data = await self._async_request("GET", "sources")
            if isinstance(data, dict):
                return data.get("sources", [])
            if isinstance(data, list):
                return data
            return []
        except SessionNotFoundError:
            return []
        except Exception as err:
            LOGGER.debug("Could not fetch sources: %s", err)
            return []

    async def async_get_source(self, source_id: str) -> dict[str, Any]:
        """Fetch details of a specific source repository."""
        data = await self._async_request("GET", f"sources/{source_id}")
        return data if isinstance(data, dict) else {}

    async def async_get_sessions(self, page_size: int = 50) -> list[dict[str, Any]]:
        """Fetch recent coding sessions."""
        try:
            data = await self._async_request(
                "GET", "sessions", params={"pageSize": page_size}
            )
            if isinstance(data, dict):
                return data.get("sessions", [])
            if isinstance(data, list):
                return data
            return []
        except Exception as err:
            raise JulesError(f"Failed to fetch sessions: {err}") from err

    async def async_get_session(self, session_id: str) -> dict[str, Any]:
        """Fetch details for a specific session."""
        clean_id = session_id.split("/")[-1]
        data = await self._async_request("GET", f"sessions/{clean_id}")
        return data if isinstance(data, dict) else {}

    async def async_create_session(
        self,
        prompt: str,
        source: str | None = None,
        title: str | None = None,
        branch: str = "main",
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """Create a new autonomous coding session."""
        payload: dict[str, Any] = {
            "prompt": prompt,
            "branch": branch,
        }
        if source:
            payload["source"] = source
        if title:
            payload["title"] = title
        if auto_approve:
            payload["autoApprovePlan"] = True

        data = await self._async_request("POST", "sessions", json_data=payload)
        return data if isinstance(data, dict) else {}

    async def async_approve_plan(self, session_id: str) -> dict[str, Any]:
        """Approve proposed implementation plan for a session."""
        clean_id = session_id.split("/")[-1]
        data = await self._async_request("POST", f"sessions/{clean_id}:approve")
        return data if isinstance(data, dict) else {}

    async def async_send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send feedback or follow-up instruction to a running session."""
        clean_id = session_id.split("/")[-1]
        data = await self._async_request(
            "POST", f"sessions/{clean_id}:sendMessage", json_data={"message": message}
        )
        return data if isinstance(data, dict) else {}

    async def async_get_activities(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch activity logs for a session."""
        clean_id = session_id.split("/")[-1]
        try:
            data = await self._async_request("GET", f"sessions/{clean_id}/activities")
            if isinstance(data, dict):
                return data.get("activities", [])
            if isinstance(data, list):
                return data
            return []
        except Exception as err:
            LOGGER.debug("Could not fetch activities for session %s: %s", clean_id, err)
            return []
