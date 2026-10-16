"""DataUpdateCoordinator for the Google Jules integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import CannotConnect, InvalidAuth, JulesClient
from .const import (
    ACCOUNT_PLANS,
    ACTIVE_STATES,
    CONF_ACCOUNT_PLAN,
    CONF_AUTO_APPROVE,
    CONF_DAILY_QUOTA,
    DEFAULT_ACCOUNT_PLAN,
    DEFAULT_DAILY_QUOTA,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    STATE_AWAITING_APPROVAL,
    STATE_AWAITING_PLAN_APPROVAL,
    STATE_AWAITING_USER_FEEDBACK,
    STATE_COMPLETED,
    STATE_FAILED,
)
from .repairs import (
    async_create_auth_repair,
    async_create_connection_repair,
    async_delete_auth_repair,
    async_delete_connection_repair,
)


class JulesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Jules sessions and sources data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: JulesClient,
        entry: ConfigEntry,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator."""
        if update_interval is None:
            update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=update_interval,
        )
        self.client = client
        self.config_entry = entry
        self._previous_states: dict[str, str] = {}
        self.event_entity: Any = None

    def _fire_event_entity(self, event_type: str, data: dict[str, Any]) -> None:
        """Forward lifecycle event to EventEntity if registered."""
        if self.event_entity is not None and hasattr(
            self.event_entity, "trigger_session_event"
        ):
            self.event_entity.trigger_session_event(event_type, data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Jules API."""
        try:
            sessions = await self.client.async_get_sessions(page_size=50)
            sources = await self.client.async_get_sources()
            health = await self.client.async_check_health()
            models = await self.client.async_get_models()
            async_delete_auth_repair(self.hass, self.config_entry)
            async_delete_connection_repair(self.hass, self.config_entry)
        except InvalidAuth as err:
            LOGGER.error("Authentication failed for Jules API: %s", err)
            async_create_auth_repair(self.hass, self.config_entry)
            raise UpdateFailed(f"Invalid authentication for Jules: {err}") from err
        except CannotConnect as err:
            LOGGER.error("Connection failed for Jules API: %s", err)
            async_create_connection_repair(self.hass, self.config_entry, str(err))
            raise UpdateFailed(f"Cannot connect to Jules: {err}") from err
        except Exception as err:
            LOGGER.error("Error communicating with Jules API: %s", err)
            raise UpdateFailed(f"Error fetching Jules data: {err}") from err

        # Process statistics
        total_sessions = len(sessions)
        active_sessions = 0
        awaiting_approval = 0
        completed_sessions = 0
        failed_sessions = 0

        latest_session: dict[str, Any] | None = None
        if sessions:
            latest_session = sessions[0]

        auto_approve_enabled = self.config_entry.options.get(
            CONF_AUTO_APPROVE,
            self.config_entry.data.get(CONF_AUTO_APPROVE, False),
        )

        for s in sessions:
            state = (s.get("state") or "").upper()
            s_id = s.get("name") or s.get("id") or ""

            if state in ACTIVE_STATES:
                active_sessions += 1

            if state in (
                STATE_AWAITING_APPROVAL,
                STATE_AWAITING_PLAN_APPROVAL,
                STATE_AWAITING_USER_FEEDBACK,
            ):
                awaiting_approval += 1
                # Check for auto-approval if configured
                if auto_approve_enabled and s_id:
                    LOGGER.info("Auto-approving plan for session %s", s_id)
                    try:
                        await self.client.async_approve_plan(s_id)
                    except Exception as exc:
                        LOGGER.warning("Auto-approve failed for %s: %s", s_id, exc)

            elif state == STATE_COMPLETED:
                completed_sessions += 1
            elif state == STATE_FAILED:
                failed_sessions += 1

            # Fire events on state transitions
            prev_state = self._previous_states.get(s_id)
            if prev_state and prev_state != state:
                event_data = {
                    "session_id": s_id,
                    "previous_state": prev_state,
                    "new_state": state,
                    "title": s.get("title"),
                    "source": s.get("source"),
                    "pr_url": s.get("pullRequestUrl") or s.get("pr_url"),
                }
                if state == STATE_COMPLETED:
                    self.hass.bus.async_fire("jules_session_completed", event_data)
                    self._fire_event_entity("session_completed", event_data)
                elif state == STATE_FAILED:
                    self.hass.bus.async_fire("jules_session_failed", event_data)
                    self._fire_event_entity("session_failed", event_data)
                elif state in (
                    STATE_AWAITING_APPROVAL,
                    STATE_AWAITING_PLAN_APPROVAL,
                    STATE_AWAITING_USER_FEEDBACK,
                ):
                    self.hass.bus.async_fire("jules_plan_awaiting_approval", event_data)
                    self._fire_event_entity("plan_awaiting_approval", event_data)
            elif prev_state is None and state in ACTIVE_STATES and s_id:
                event_data = {
                    "session_id": s_id,
                    "new_state": state,
                    "title": s.get("title"),
                    "source": s.get("source"),
                }
                self.hass.bus.async_fire("jules_session_started", event_data)
                self._fire_event_entity("session_started", event_data)

            if s_id:
                self._previous_states[s_id] = state

        # Determine plan and daily quota limit from config/options
        plan = self.config_entry.options.get(
            CONF_ACCOUNT_PLAN,
            self.config_entry.data.get(CONF_ACCOUNT_PLAN, DEFAULT_ACCOUNT_PLAN),
        )
        default_limit = ACCOUNT_PLANS.get(plan, DEFAULT_DAILY_QUOTA)
        daily_limit = int(
            self.config_entry.options.get(
                CONF_DAILY_QUOTA,
                self.config_entry.data.get(CONF_DAILY_QUOTA, default_limit),
            )
        )

        now_utc = datetime.now(UTC)
        today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=UTC)
        next_reset = today_start + timedelta(days=1)

        today_used = 0
        latest_pr: dict[str, Any] | None = None

        for s in sessions:
            c_time = s.get("createTime") or s.get("created_at")
            if c_time:
                try:
                    c_dt = datetime.fromisoformat(str(c_time).replace("Z", "+00:00"))
                    if c_dt >= today_start:
                        today_used += 1
                except Exception:
                    pass

            if not latest_pr:
                pr_url = s.get("pullRequestUrl") or s.get("pr_url")
                pr_title = None
                base_ref = None
                head_ref = None
                for out in s.get("outputs", []):
                    if isinstance(out, dict) and "pullRequest" in out:
                        pr_info = out["pullRequest"]
                        if isinstance(pr_info, dict):
                            pr_url = pr_url or pr_info.get("url")
                            pr_title = pr_info.get("title")
                            base_ref = pr_info.get("baseRef")
                            head_ref = pr_info.get("headRef")
                            break
                if pr_url or pr_title:
                    latest_pr = {
                        "url": pr_url,
                        "title": pr_title or s.get("title") or "Pull Request",
                        "base_ref": base_ref,
                        "head_ref": head_ref,
                        "session_id": s.get("name") or s.get("id"),
                    }

        remaining_quota = max(0, daily_limit - today_used)
        total_finished = completed_sessions + failed_sessions
        success_rate = (
            round((completed_sessions / total_finished) * 100, 1)
            if total_finished > 0
            else 100.0
        )

        return {
            "version": health.get("version") or "v1alpha",
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "awaiting_approval": awaiting_approval,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "latest_session": latest_session,
            "sources": sources,
            "sources_count": len(sources),
            "sessions": sessions,
            "health": health,
            "latency_ms": health.get("latency_ms"),
            "reachable": health.get("reachable", True),
            "models": models,
            "account_plan": plan,
            "daily_limit": daily_limit,
            "today_used": today_used,
            "remaining_quota": remaining_quota,
            "reset_time_utc": next_reset.isoformat(),
            "latest_pr": latest_pr,
            "success_rate": success_rate,
        }
