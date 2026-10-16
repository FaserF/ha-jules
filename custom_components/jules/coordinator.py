"""DataUpdateCoordinator for the Google Jules integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import JulesClient
from .const import (
    ACTIVE_STATES,
    CONF_AUTO_APPROVE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    STATE_AWAITING_APPROVAL,
    STATE_COMPLETED,
    STATE_FAILED,
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Jules API."""
        try:
            sessions = await self.client.async_get_sessions(page_size=50)
            sources = await self.client.async_get_sources()
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

            if state == STATE_AWAITING_APPROVAL:
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
                elif state == STATE_FAILED:
                    self.hass.bus.async_fire("jules_session_failed", event_data)
                elif state == STATE_AWAITING_APPROVAL:
                    self.hass.bus.async_fire("jules_plan_awaiting_approval", event_data)

            if s_id:
                self._previous_states[s_id] = state

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "awaiting_approval": awaiting_approval,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "latest_session": latest_session,
            "sources": sources,
            "sources_count": len(sources),
            "sessions": sessions,
        }
