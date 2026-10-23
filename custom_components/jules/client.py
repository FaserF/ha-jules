"""Asynchronous API client for Google Jules."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER, STATUS_BUSY, STATUS_FAILED, STATUS_STABLE


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
        timeout: float = 120.0,
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
            if "googleapis.com" in self._base_url:
                # Direct Google Cloud endpoints require x-goog-api-key without Bearer
                headers["x-goog-api-key"] = self._api_key
            else:
                # Proxies / OmniRoute use standard Authorization header and x-goog-api-key
                headers["Authorization"] = f"Bearer {self._api_key}"
                headers["x-goog-api-key"] = self._api_key
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
            data = None
            try:
                data = await self._async_request(
                    "GET", f"api/v1/agents/tasks/{clean_id}"
                )
            except Exception:
                if not clean_id.startswith("jules_"):
                    try:
                        data = await self._async_request(
                            "GET", f"api/v1/agents/tasks/jules_sessions_{clean_id}"
                        )
                    except Exception:
                        pass
            if not data or (isinstance(data, dict) and "error" in data):
                sessions = await self.async_get_sessions(page_size=50)
                for s in sessions:
                    if (
                        s.get("id") == clean_id
                        or s.get("name") == session_id
                        or s.get("raw_id") == clean_id
                    ):
                        return s
                data = {}
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

        try:
            data = await self._async_request("POST", f"sessions/{clean_id}:approvePlan")
        except Exception:
            data = await self._async_request("POST", f"sessions/{clean_id}:approve")
        return data if isinstance(data, dict) else {}

    async def async_cancel_session(self, session_id: str) -> dict[str, Any]:
        """Cancel or stop an active Jules session."""
        clean_id = session_id.split("/")[-1]
        if self._is_omniroute:
            try:
                return await self._async_request(
                    "POST",
                    f"api/v1/agents/tasks/{clean_id}",
                    json_data={"action": "cancel"},
                )
            except Exception:
                pass

        try:
            return await self._async_request(
                "POST", f"sessions/{clean_id}:cancel", json_data={}
            )
        except Exception:
            try:
                return await self._async_request(
                    "POST", f"sessions/{clean_id}/cancel", json_data={}
                )
            except Exception:
                return await self._async_request("DELETE", f"sessions/{clean_id}")

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
                            raw_models = [
                                str(m["id"])
                                for m in model_list
                                if isinstance(m, dict)
                                and "id" in m
                                and not str(m["id"]).startswith("meta-")
                            ]
                            cascades = [m for m in raw_models if "cascade" in m]
                            curated = [
                                m
                                for m in raw_models
                                if m.startswith(
                                    (
                                        "gemini-",
                                        "claude-",
                                        "gpt-",
                                        "deepseek-",
                                        "qwen-",
                                        "o1",
                                        "o3",
                                    )
                                )
                                and not m.endswith(("-embedding", "-embed", "-tts"))
                                and len(m) <= 35
                            ]
                            seen: set[str] = set()
                            filtered: list[str] = []
                            for m in cascades + curated:
                                if m not in seen:
                                    seen.add(m)
                                    filtered.append(m)
                            if filtered:
                                return sorted(filtered[:40])
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
                                "version": "v1alpha",
                            }
            except Exception as exc:
                LOGGER.debug("OmniRoute /api/health unavailable: %s", exc)

        start = time.perf_counter()
        try:
            await self.async_test_connection()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "reachable": True,
                "version": "v1alpha",
            }
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

    async def async_get_session_state(self, session_id: str) -> dict[str, Any]:
        """Get semantic operational status and dashboard state for a Jules session."""
        clean_id = session_id.split("/")[-1]
        session = await self.async_get_session(clean_id)
        activities = await self.async_get_activities(clean_id)

        status = _compute_semantic_status(session.get("state", ""))
        pr_url = session.get("pullRequestUrl") or session.get("pr_url")
        pr_info = {"url": pr_url, "title": session.get("title", "")} if pr_url else None

        last_activity: dict[str, Any] | None = None
        last_agent_message: dict[str, Any] | None = None
        pending_plan: dict[str, Any] | None = None

        if activities:
            last_act = activities[-1]
            act_type = (
                last_act.get("activityType")
                or ("planGenerated" if "planGenerated" in last_act else None)
                or ("agentMessaged" if "agentMessaged" in last_act else None)
                or ("userMessaged" if "userMessaged" in last_act else None)
                or last_act.get("type")
                or "unknown"
            )
            last_activity = {
                "activityId": last_act.get("id")
                or last_act.get("name", "").split("/")[-1],
                "type": act_type,
                "timestamp": last_act.get("createTime") or last_act.get("createdAt"),
            }

            for act in reversed(activities):
                content = None
                if isinstance(act.get("agentMessaged"), dict):
                    content = act["agentMessaged"].get("agentMessage") or act[
                        "agentMessaged"
                    ].get("content")
                elif isinstance(act.get("agentMessage"), dict):
                    content = act["agentMessage"].get("content")
                elif act.get("originator") == "agent" and act.get("content"):
                    content = act["content"]
                elif act.get("type") == "agentMessaged" and act.get("message"):
                    content = act.get("message")

                if content:
                    last_agent_message = {
                        "activityId": act.get("id")
                        or act.get("name", "").split("/")[-1],
                        "content": content,
                        "timestamp": act.get("createTime") or act.get("createdAt"),
                    }
                    break

            for act in reversed(activities):
                plan_data = None
                if isinstance(act.get("planGenerated"), dict):
                    plan_data = act["planGenerated"].get("plan")
                elif isinstance(act.get("plan"), dict):
                    plan_data = act["plan"]

                if plan_data and isinstance(plan_data, dict):
                    steps_raw = plan_data.get("steps", [])
                    steps = [
                        {
                            "title": step.get("title", f"Step {i + 1}"),
                            "description": step.get("description", ""),
                        }
                        for i, step in enumerate(steps_raw)
                        if isinstance(step, dict)
                    ]
                    pending_plan = {
                        "activityId": act.get("id")
                        or act.get("name", "").split("/")[-1],
                        "planId": plan_data.get("id") or plan_data.get("planId", ""),
                        "steps": steps,
                    }
                    break

        return {
            "id": clean_id,
            "status": status,
            "state": session.get("state"),
            "url": f"https://jules.google.com/task/{clean_id}",
            "title": session.get("title", ""),
            "prompt": session.get("prompt", ""),
            "pr": pr_info,
            "lastActivity": last_activity,
            "lastAgentMessage": last_agent_message,
            "pendingPlan": pending_plan,
        }

    async def async_get_bash_outputs(
        self,
        session_id: str,
        activity_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get all bash command outputs from a Jules session matching @google/jules-mcp."""
        clean_id = session_id.split("/")[-1]
        activities = await self.async_get_activities(clean_id)
        target_ids = set(activity_ids) if activity_ids else None

        outputs: list[dict[str, Any]] = []
        summary = {"totalCommands": 0, "succeeded": 0, "failed": 0}

        for act in activities:
            act_id = str(act.get("id") or act.get("name", "").split("/")[-1])
            if target_ids and act_id not in target_ids:
                continue

            artifacts = act.get("artifacts", [])
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                bash_data = (
                    artifact.get("bashOutput")
                    if "bashOutput" in artifact
                    else (
                        artifact
                        if artifact.get("type") in ("bashOutput", "bash_output")
                        or "command" in artifact
                        else None
                    )
                )
                if bash_data and isinstance(bash_data, dict):
                    exit_code = bash_data.get("exitCode")
                    outputs.append(
                        {
                            "command": bash_data.get("command", ""),
                            "stdout": bash_data.get("stdout", ""),
                            "stderr": bash_data.get("stderr", ""),
                            "exitCode": exit_code,
                            "activityId": act_id,
                        }
                    )
                    summary["totalCommands"] += 1
                    if exit_code in (0, None):
                        summary["succeeded"] += 1
                    else:
                        summary["failed"] += 1

        return {
            "sessionId": clean_id,
            "outputs": outputs,
            "summary": summary,
        }

    async def async_show_code_diff(
        self,
        session_id: str,
        file: str | None = None,
        activity_id: str | None = None,
    ) -> dict[str, Any]:
        """Show unified git code diff from a Jules session matching @google/jules-mcp."""
        clean_id = session_id.split("/")[-1]
        activities = await self.async_get_activities(clean_id)

        unidiff_patch = ""
        files: list[dict[str, Any]] = []

        for act in reversed(activities):
            act_id = str(act.get("id") or act.get("name", "").split("/")[-1])
            if activity_id and act_id != activity_id:
                continue

            artifacts = act.get("artifacts", [])
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                change_set = artifact.get("changeSet") or (
                    artifact
                    if artifact.get("type") in ("changeSet", "change_set")
                    or "gitPatch" in artifact
                    else None
                )
                if change_set and isinstance(change_set, dict):
                    git_patch = change_set.get("gitPatch", {})
                    patch = git_patch.get("unidiffPatch") or change_set.get(
                        "unidiffPatch", ""
                    )
                    if patch and not unidiff_patch:
                        unidiff_patch = patch

                    raw_files = change_set.get("files", [])
                    if raw_files and not files:
                        files = [
                            {
                                "path": f.get("path", ""),
                                "changeType": f.get("changeType", "modified"),
                                "additions": f.get("additions", 0),
                                "deletions": f.get("deletions", 0),
                            }
                            for f in raw_files
                            if isinstance(f, dict)
                        ]
            if unidiff_patch:
                break

        if file and unidiff_patch:
            unidiff_patch = _extract_file_diff(unidiff_patch, file)
            if files:
                files = [f for f in files if f.get("path") == file]

        summary = {
            "totalFiles": len(files),
            "created": len([f for f in files if f.get("changeType") == "created"]),
            "modified": len([f for f in files if f.get("changeType") == "modified"]),
            "deleted": len([f for f in files if f.get("changeType") == "deleted"]),
        }

        return {
            "sessionId": clean_id,
            "activityId": activity_id,
            "file": file,
            "unidiffPatch": unidiff_patch,
            "files": files,
            "summary": summary,
        }

    async def async_get_code_review_context(
        self,
        session_id: str,
        format: str = "markdown",
        filter_type: str = "all",
        detail: str = "standard",
        activity_id: str | None = None,
    ) -> dict[str, Any]:
        """Get code review summary with file changes and insights matching @google/jules-mcp."""
        clean_id = session_id.split("/")[-1]
        session = await self.async_get_session(clean_id)
        diff_res = await self.async_show_code_diff(clean_id, activity_id=activity_id)
        bash_res = await self.async_get_bash_outputs(clean_id)

        status = _compute_semantic_status(session.get("state", ""))
        files = diff_res.get("files", [])
        if filter_type != "all":
            files = [f for f in files if f.get("changeType") == filter_type]

        summary = diff_res.get("summary", {})
        pr_url = session.get("pullRequestUrl") or session.get("pr_url")
        pr_dict = {"url": pr_url, "title": session.get("title", "")} if pr_url else None

        insights = {
            "failedCommandCount": bash_res.get("summary", {}).get("failed", 0),
            "totalCommands": bash_res.get("summary", {}).get("totalCommands", 0),
        }

        lines = [
            f"# Jules Session Review: {session.get('title', clean_id)}",
            f"- **Session ID**: `{clean_id}`",
            f"- **Status**: `{status}` (State: {session.get('state')})",
            f"- **Repository**: {session.get('source') or 'N/A'}",
        ]
        if pr_url:
            lines.append(f"- **Pull Request**: [{pr_url}]({pr_url})")
        lines.append(
            f"\n### File Changes Summary ({summary.get('totalFiles', 0)} files)"
        )
        lines.append(
            f"- Created: {summary.get('created', 0)} | Modified: {summary.get('modified', 0)} | Deleted: {summary.get('deleted', 0)}"
        )

        if files:
            lines.append("\n| Path | Type | +Add | -Del |")
            lines.append("|---|---|---|---|")
            for f in files:
                lines.append(
                    f"| `{f['path']}` | {f['changeType']} | +{f.get('additions', 0)} | -{f.get('deletions', 0)} |"
                )
        else:
            lines.append("\n*No file changes recorded in changeset yet.*")

        formatted = "\n".join(lines)
        return {
            "sessionId": clean_id,
            "title": session.get("title", ""),
            "state": session.get("state", ""),
            "status": status,
            "url": f"https://jules.google.com/task/{clean_id}",
            "pr": pr_dict,
            "files": files,
            "summary": summary,
            "insights": insights,
            "formatted": formatted,
        }

    async def async_send_reply(
        self,
        session_id: str,
        action: str = "send",
        message: str | None = None,
        plan_id: str | None = None,
    ) -> dict[str, Any]:
        """Interacts with an active Jules session (approving plans or sending messages) matching @google/jules-mcp."""
        clean_id = session_id.split("/")[-1]
        action_clean = action.lower()
        if action_clean == "approve":
            res = await self.async_approve_plan(clean_id)
            return {
                "success": True,
                "message": f"Approved plan for session {clean_id}",
                "reply": None,
                "raw": res,
            }

        if not message:
            raise JulesError("Message is required for action 'send' or 'ask'")

        send_res = await self.async_send_message(clean_id, message)
        if action_clean == "ask":
            reply = None
            start = time.perf_counter()
            for _ in range(10):
                await asyncio.sleep(2.0)
                state = await self.async_get_session_state(clean_id)
                msg_info = state.get("lastAgentMessage")
                if msg_info and msg_info.get("content"):
                    reply = msg_info["content"]
                    break
                if time.perf_counter() - start > 120:
                    break
            return {
                "success": True,
                "message": f"Message sent to session {clean_id}",
                "reply": reply,
                "raw": send_res,
            }

        return {
            "success": True,
            "message": f"Message sent to session {clean_id}",
            "reply": None,
            "raw": send_res,
        }


def _compute_semantic_status(state: str) -> str:
    """Map raw session state to @google/jules-mcp semantic status."""
    st = (state or "").lower().replace("-", "_").replace(" ", "_")
    if st in ("queued", "planning", "in_progress", "inprogress", "running", "busy"):
        return STATUS_BUSY
    if st in (
        "awaiting_approval",
        "awaiting_plan_approval",
        "awaitingplanapproval",
        "awaiting_user_feedback",
        "awaitinguserfeedback",
        "paused",
        "completed",
        "stable",
    ):
        return STATUS_STABLE
    if st in ("failed", "cancelled", "error"):
        return STATUS_FAILED
    return STATUS_STABLE


def _extract_file_diff(patch: str, target_file: str) -> str:
    """Extract diff hunks for a specific file from unified diff string."""
    if not patch:
        return ""
    chunks = patch.split("diff --git ")
    matched: list[str] = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        first_line = chunk.splitlines()[0]
        if f"a/{target_file}" in first_line or f"b/{target_file}" in first_line:
            matched.append(f"diff --git {chunk}")
    return "\n".join(matched)
