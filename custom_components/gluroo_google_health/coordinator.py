"""Coordinator and Google Health upload state."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoogleHealthApi, GlurooApi, GlurooApiError, GoogleHealthApiError
from .const import CONF_POLL_INTERVAL, CONF_SYNC_GOOGLE, DEFAULT_POLL_INTERVAL, DOMAIN
from .models import GlurooSnapshot

_LOGGER = logging.getLogger(__name__)


class GlurooCoordinator(DataUpdateCoordinator[GlurooSnapshot]):
    """Poll Gluroo and expose a single coherent snapshot to all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: GlurooApi,
    ) -> None:
        interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.api = api

    async def _async_update_data(self) -> GlurooSnapshot:
        """Fetch one Gluroo snapshot."""
        try:
            return await self.api.async_fetch_snapshot()
        except GlurooApiError as err:
            raise UpdateFailed(str(err)) from err


class GoogleUploader:
    """Upload unseen glucose entries exactly once per local entry ID."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: GoogleHealthApi | None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.api = api
        self._lock = asyncio.Lock()
        self._unsupported = False
        self._synced_ids: list[str] = list(entry.data.get("synced_entry_ids", []))[-200:]

    async def async_sync(self, snapshot: GlurooSnapshot) -> None:
        """Upload readings oldest-first and persist the bounded dedupe set."""
        if self.api is None or self._unsupported or not self.entry.options.get(CONF_SYNC_GOOGLE, True):
            return
        async with self._lock:
            changed = False
            for reading in reversed(snapshot.entries):
                if reading.entry_id in self._synced_ids:
                    continue
                try:
                    result = await self.api.async_create_blood_glucose(reading)
                except GoogleHealthApiError as err:
                    if err.unsupported:
                        self._unsupported = True
                        _LOGGER.error(
                            "Google Health API currently does not support creating blood-glucose "
                            "data points; Gluroo sensors remain available but upload is disabled "
                            "for this runtime: %s",
                            err,
                        )
                    else:
                        _LOGGER.warning("Google Health upload failed for %s: %s", reading.entry_id, err)
                    break
                self._synced_ids.append(reading.entry_id)
                self._synced_ids = self._synced_ids[-200:]
                changed = True
                _LOGGER.info(
                    "Accepted Gluroo glucose %s by Google Health API (http=%s)",
                    reading.entry_id,
                    result.get("_http_status"),
                )
            if changed:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, "synced_entry_ids": self._synced_ids},
                )
