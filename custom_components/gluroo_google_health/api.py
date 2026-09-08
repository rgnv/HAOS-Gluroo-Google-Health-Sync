"""Async clients for Gluroo Global Connect and Google Health API."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from typing import Any
from urllib.parse import urljoin

import aiohttp
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import GOOGLE_HEALTH_BASE
from .models import GlurooSnapshot, GlucoseReading, as_documents, blood_glucose_payload


class GlurooApiError(RuntimeError):
    """Raised when Gluroo rejects a request or returns invalid data."""


class GlurooApi:
    """Read the Nightscout-compatible Gluroo Global Connect API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/") + "/"
        self._token = token

    async def _get(self, path: str, count: int, optional: bool = False) -> Any:
        """Fetch a Nightscout v1 collection without logging the secret."""
        url = urljoin(self._base_url, path.lstrip("/"))
        # Gluroo's Global Connect endpoint accepts its API secret as the
        # Nightscout-compatible token query parameter. Older Nightscout-style
        # deployments use the SHA-1 api-secret header instead. Do not send the
        # raw secret header: Gluroo rejects that combination even when token is
        # also present in the query.
        attempts = (
            ({"count": str(count), "token": self._token}, {"Accept": "application/json"}),
            (
                {"count": str(count)},
                {
                    "Accept": "application/json",
                    "api-secret": hashlib.sha1(self._token.encode()).hexdigest(),
                },
            ),
            (
                {"count": str(count)},
                {"Accept": "application/json", "Authorization": f"Bearer {self._token}"},
            ),
        )
        for index, (params, headers) in enumerate(attempts):
            async with self._session.get(url, params=params, headers=headers) as response:
                if response.status == 404 and optional:
                    return []
                if response.status in {401, 403} and index < len(attempts) - 1:
                    continue
                if response.status >= 400:
                    detail = await response.text()
                    raise GlurooApiError(f"Gluroo HTTP {response.status}: {detail[:300]}")
                if response.status == 204:
                    return []
                try:
                    return await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise GlurooApiError("Gluroo returned invalid JSON") from err
        raise GlurooApiError("Gluroo authentication failed")

    async def async_fetch_snapshot(self) -> GlurooSnapshot:
        """Fetch glucose entries and optional treatment/device status."""
        entries_raw, treatments_raw, status_raw = await asyncio.gather(
            self._get("api/v1/entries.json", 20),
            self._get("api/v1/treatments.json", 20, optional=True),
            self._get("api/v1/devicestatus.json", 5, optional=True),
        )
        entries = tuple(
            sorted(
                (reading for item in as_documents(entries_raw) if (reading := GlucoseReading.from_entry(item))),
                key=lambda reading: reading.measured_at,
                reverse=True,
            )
        )
        treatments = tuple(as_documents(treatments_raw))
        status = tuple(as_documents(status_raw))
        return GlurooSnapshot(
            entries=entries,
            treatments=treatments,
            devicestatus=status,
            fetched_at=datetime.now(timezone.utc),
        )


class GoogleHealthApiError(RuntimeError):
    """Raised when Google Health API rejects a write."""


class GoogleHealthApi:
    """Write Gluroo glucose readings through a Home Assistant OAuth session."""

    def __init__(self, session: aiohttp.ClientSession, oauth_session: OAuth2Session) -> None:
        self._session = session
        self._oauth_session = oauth_session

    async def async_create_blood_glucose(self, reading: GlucoseReading) -> dict[str, Any]:
        """Create one blood-glucose data point."""
        await self._oauth_session.async_ensure_token_valid()
        token = self._oauth_session.token.get("access_token")
        if not token:
            raise GoogleHealthApiError("Google OAuth session has no access token")
        url = f"{GOOGLE_HEALTH_BASE}/blood-glucose/dataPoints"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with self._session.post(url, json=blood_glucose_payload(reading), headers=headers) as response:
            if response.status >= 400:
                detail = await response.text()
                raise GoogleHealthApiError(
                    f"Google Health API HTTP {response.status}: {detail[:300]}"
                )
            if response.status == 204:
                return {"_http_status": response.status}
            try:
                result = await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                result = {}
            if not isinstance(result, dict):
                result = {}
            result["_http_status"] = response.status
            return result
