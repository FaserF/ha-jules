"""Asynchronous API client for Google Jules."""

from __future__ import annotations

import asyncio
import time
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


class ModelNotFoundError(JulesError):
    """Exception indicating requested model or endpoint does not exist."""


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
        self._compression_enabled: bool = True

        clean_url = api_url.rstrip("/")
        if clean_url.endswith("/api/v1/agents/tasks"):
            clean_url = clean_url[: -len("/api/v1/agents/tasks")]
        elif clean_url.endswith("/api/v1"):
            clean_url = clean_url[: -len("/api/v1")]
        self._base_url = clean_url

        self._is_omniroute: bool = (
            ":20128" in self._base_url or "omniroute" in self._base_url.lower()
        )
        self._discovered_sources: set[str] = set()

    @property
    def compression_enabled(self) -> bool:
        """Return whether prompt token compression is enabled."""
        return self._compression_enabled

    @compression_enabled.setter
    def compression_enabled(self, val: bool) -> None:
        """Set token compression state."""
        self._compression_enabled = bool(val)

    @property
    def base_url(self) -> str:
        """Return configured base URL."""
        return self._base_url

    @property
    def is_omniroute(self) -> bool:
        """Return whether client is talking to OmniRoute proxy."""
        return self._is_omniroute

    def _get_headers(self) -> dict[str, str]:
        """Construct request headers with Google API, compression, and standard Bearer support."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "HomeAssistant-Jules/2026.10.2",
        }
        if self._api_key:
            # Google Cloud endpoints use x-goog-api-key
            headers["x-goog-api-key"] = self._api_key
            # Also provide standard Authorization header for proxies / OmniRoute
            headers["Authorization"] = f"Bearer {self._api_key}"
        if self._compression_enabled:
            headers["x-omniroute-compression"] = "true"
        return headers

    def _resolve_url(self, path: str) -> str:
        """Resolve endpoint URL safely handling base path prefixes."""
        clean_path = path.lstrip("/")
        return f"{self._base_url}/{clean_path}"

    def _normalize_omniroute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Normalize an OmniRoute cloud agent task into standard Jules session format."""
        if not isinstance(task, dict):
            return {}
        status = (task.get("status") or "").lower()
        state_map = {
            "queued": "QUEUED",
            "pending": "QUEUED",
            "planning": "PLANNING",
            "awaiting_approval": "AWAITING_APPROVAL",
            "running": "IN_PROGRESS",
            "in_progress": "IN_PROGRESS",
            "completed": "COMPLETED",
            "failed": "FAILED",
            "cancelled": "FAILED",
        }
        state = state_map.get(status, status.upper() or "UNKNOWN")
        task_id = str(task.get("id") or "")
        external_id = str(task.get("externalId") or task_id)
        clean_id = external_id.split("/")[-1] if "/" in external_id else task_id

        source_raw = task.get("source")
        source_name = ""
        if isinstance(source_raw, dict):
            source_name = source_raw.get("source") or source_raw.get("repoName") or ""
        elif isinstance(source_raw, str):
            source_name = source_raw
        if source_name:
            self._discovered_sources.add(source_name)

        prompt = task.get("prompt") or ""
        title = task.get("title") or (
            prompt.strip().split("\n")[0][:100] if prompt else clean_id
        )
        result = task.get("result") or {}
        pr_url = result.get("prUrl") if isinstance(result, dict) else None

        return {
            "name": f"sessions/{clean_id}",
            "id": clean_id,
            "raw_id": task_id,
            "state": state,
            "prompt": prompt,
            "title": title,
            "source": source_name,
            "pullRequestUrl": pr_url,
            "createTime": task.get("createdAt"),
            "updateTime": task.get("updatedAt"),
            "completedTime": task.get("completedAt"),
            "activities": task.get("activities", []),
        }

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
        if self._is_omniroute:
            try:
                await self._async_request(
                    "GET",
                    "api/v1/agents/tasks",
                    params={"provider": "jules", "limit": 1},
                )
                return True
            except InvalidAuth:
                raise
            except Exception as err:
                raise CannotConnect(f"Unable to connect to OmniRoute: {err}") from err

        # Standard Jules API endpoints to probe
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

        # Try fallback to OmniRoute agents endpoint
        try:
            await self._async_request(
                "GET", "api/v1/agents/tasks", params={"provider": "jules", "limit": 1}
            )
            self._is_omniroute = True
            return True
        except Exception:
            pass

        LOGGER.warning("Connection test failed across endpoints: %s", last_error)
        if last_error:
            raise CannotConnect(
                f"Unable to connect to Jules endpoint: {last_error}"
            ) from last_error
        return False

    async def async_get_sources(self) -> list[dict[str, Any]]:
        """Fetch authorized code repositories/sources."""
        if self._is_omniroute:
            if not self._discovered_sources:
                try:
                    await self.async_get_sessions(page_size=20)
                except Exception:
                    pass
            return [{"name": s, "id": s} for s in sorted(self._discovered_sources)]

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
        if self._is_omniroute:
            return {"name": source_id, "id": source_id}

        data = await self._async_request("GET", f"sources/{source_id}")
        return data if isinstance(data, dict) else {}

    async def async_get_sessions(self, page_size: int = 50) -> list[dict[str, Any]]:
        """Fetch recent coding sessions."""
        try:
            if self._is_omniroute:
                data = await self._async_request(
                    "GET",
                    "api/v1/agents/tasks",
                    params={"provider": "jules", "limit": page_size},
                )
                tasks: list[dict[str, Any]] = []
                if (
                    isinstance(data, dict)
                    and "data" in data
                    and isinstance(data["data"], list)
                ):
                    tasks = data["data"]
                elif isinstance(data, list):
                    tasks = data
                return [self._normalize_omniroute_task(t) for t in tasks]

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
        if self._is_omniroute:
            data = await self._async_request("GET", f"api/v1/agents/tasks/{clean_id}")
            task = (
                data.get("data") if isinstance(data, dict) and "data" in data else data
            )
            return (
                self._normalize_omniroute_task(task) if isinstance(task, dict) else {}
            )

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
        if self._is_omniroute:
            payload: dict[str, Any] = {
                "providerId": "jules",
                "prompt": prompt,
                "options": {
                    "autoCreatePr": True,
                    "planApprovalRequired": not auto_approve,
                },
            }
            if source:
                payload["source"] = {"repoName": source, "branch": branch}
            else:
                payload["source"] = {"branch": branch}
            if title:
                payload["title"] = title

            res = await self._async_request(
                "POST", "api/v1/agents/tasks", json_data=payload
            )
            task = res.get("data", res) if isinstance(res, dict) else {}
            return (
                self._normalize_omniroute_task(task) if isinstance(task, dict) else {}
            )

        payload = {
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
        if self._is_omniroute:
            return await self._async_request(
                "POST",
                f"api/v1/agents/tasks/{clean_id}",
                json_data={"action": "approve"},
            )

        data = await self._async_request("POST", f"sessions/{clean_id}:approve")
        return data if isinstance(data, dict) else {}

    async def async_send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send feedback or follow-up instruction to a running session."""
        clean_id = session_id.split("/")[-1]
        if self._is_omniroute:
            return await self._async_request(
                "POST",
                f"api/v1/agents/tasks/{clean_id}",
                json_data={"action": "message", "message": message},
            )

        data = await self._async_request(
            "POST", f"sessions/{clean_id}:sendMessage", json_data={"message": message}
        )
        return data if isinstance(data, dict) else {}

    async def async_get_activities(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch activity logs for a session."""
        clean_id = session_id.split("/")[-1]
        if self._is_omniroute:
            session = await self.async_get_session(clean_id)
            return session.get("activities", [])

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

    async def async_get_models(self) -> list[str]:
        """Fetch available models from OmniRoute or defaults."""
        if self._is_omniroute:
            url = f"{self._base_url}/v1/models"
            headers = self._get_headers()
            try:
                async with asyncio.timeout(self._timeout):
                    async with self._session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            model_list = data.get("data", [])
                            models = [
                                m["id"]
                                for m in model_list
                                if isinstance(m, dict)
                                and "id" in m
                                and not m["id"].startswith("meta-")
                            ]
                            if models:
                                return sorted(models)
            except Exception as exc:
                LOGGER.debug("Could not fetch models from OmniRoute: %s", exc)
        return [
            "coding-cascade",
            "chat-cascade",
            "fast-cascade",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ]

    async def async_check_health(self) -> dict[str, Any]:
        """Check Jules endpoint health and measure latency."""
        headers = self._get_headers()
        start = time.perf_counter()
        if self._is_omniroute:
            health_url = f"{self._base_url}/api/health"
            try:
                async with asyncio.timeout(10.0):
                    async with self._session.get(health_url, headers=headers) as resp:
                        latency_ms = round((time.perf_counter() - start) * 1000, 2)
                        if resp.status == 200:
                            try:
                                data = await resp.json()
                                if isinstance(data, dict):
                                    data["latency_ms"] = latency_ms
                                    data["reachable"] = True
                                    return data
                            except Exception:
                                pass
                            return {
                                "status": "ok",
                                "latency_ms": latency_ms,
                                "reachable": True,
                            }
            except Exception as exc:
                LOGGER.debug("OmniRoute /api/health unavailable: %s", exc)

        start = time.perf_counter()
        try:
            await self.async_test_connection()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {"status": "ok", "latency_ms": latency_ms, "reachable": True}
        except Exception as err:
            return {
                "status": "offline",
                "latency_ms": None,
                "reachable": False,
                "error": str(err),
            }

    async def async_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "coding-cascade",
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send chat completion request to OmniRoute or Google Gemini endpoint."""
        url = (
            f"{self._base_url}/v1/chat/completions"
            if self._is_omniroute
            else f"{self._base_url}/chat/completions"
        )
        headers = self._get_headers()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.post(
                    url, headers=headers, json=payload
                ) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Invalid authentication token")
                    if resp.status == 404:
                        raise ModelNotFoundError(
                            f"Model or endpoint '{model}' not found: {await resp.text()}"
                        )
                    if resp.status != 200:
                        raise JulesError(
                            f"HTTP {resp.status} during chat completion: {await resp.text()}"
                        )
                    return await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect(
                f"Connection error during chat completion: {err}"
            ) from err
        except (InvalidAuth, ModelNotFoundError, JulesError):
            raise
        except Exception as err:
            raise JulesError(f"Unexpected chat completion error: {err}") from err
