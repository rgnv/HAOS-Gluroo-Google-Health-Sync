"""Models and conversions for Gluroo Nightscout-compatible data."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import math
from typing import Any


def _number(value: Any) -> float | None:
    """Return a finite float, or None for missing/invalid values."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(entry: dict[str, Any]) -> datetime | None:
    """Read a Nightscout timestamp."""
    raw = entry.get("date")
    if raw is not None:
        try:
            milliseconds = float(raw)
            if math.isfinite(milliseconds):
                return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            pass
    date_string = entry.get("dateString") or entry.get("created_at")
    if isinstance(date_string, str):
        try:
            value = date_string.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _entry_id(entry: dict[str, Any], measured_at: datetime | None) -> str:
    """Return a stable ID even when a provider omits _id."""
    for key in ("_id", "id", "identifier"):
        value = entry.get(key)
        if value:
            return str(value)
    seed = "|".join(
        str(entry.get(key, ""))
        for key in ("date", "dateString", "sgv", "direction", "delta")
    )
    if not seed.strip("|") and measured_at:
        seed = measured_at.isoformat()
    return "gluroo-" + hashlib.sha256(seed.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class GlucoseReading:
    """One Nightscout-compatible glucose entry."""

    entry_id: str
    glucose_mgdl: float
    measured_at: datetime
    delta: float | None
    direction: str | None
    raw: dict[str, Any]

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> GlucoseReading | None:
        """Parse a glucose entry, ignoring malformed/non-glucose documents."""
        glucose = _number(entry.get("sgv", entry.get("glucose")))
        measured_at = _timestamp(entry)
        if glucose is None or measured_at is None or not 20 <= glucose <= 1000:
            return None
        return cls(
            entry_id=_entry_id(entry, measured_at),
            glucose_mgdl=glucose,
            measured_at=measured_at,
            delta=_number(entry.get("delta")),
            direction=str(entry["direction"]) if entry.get("direction") else None,
            raw=dict(entry),
        )


def derive_missing_deltas(readings: tuple[GlucoseReading, ...]) -> tuple[GlucoseReading, ...]:
    """Fill missing deltas from the immediately preceding CGM reading.

    Gluroo Global Connect currently omits Nightscout's optional ``delta`` field.
    Only derive a delta when the adjacent older sample is no more than fifteen
    minutes away; a long data gap should remain unknown rather than look like a
    real rate of change.
    """
    result: list[GlucoseReading] = []
    for index, reading in enumerate(readings):
        if reading.delta is None and index + 1 < len(readings):
            previous = readings[index + 1]
            if reading.measured_at - previous.measured_at <= timedelta(minutes=15):
                reading = replace(
                    reading,
                    delta=round(reading.glucose_mgdl - previous.glucose_mgdl, 3),
                )
        result.append(reading)
    return tuple(result)


def sample_time(value: datetime) -> dict[str, str]:
    """Build the Google Health API observation time."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("measured_at must include a timezone")
    offset_seconds = int(value.utcoffset().total_seconds())
    utc = value.astimezone(timezone.utc)
    return {
        "physicalTime": utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "utcOffset": f"{offset_seconds}s",
    }


def blood_glucose_payload(reading: GlucoseReading) -> dict[str, Any]:
    """Build the Google Health API blood-glucose data point."""
    return {
        "bloodGlucose": {
            "bloodGlucoseMilligramsPerDeciliter": round(reading.glucose_mgdl, 3),
            "sampleTime": sample_time(reading.measured_at),
            "measurementSource": "CONTINUOUS_GLUCOSE_MONITORING",
            "specimen": "INTERSTITIAL_FLUID",
            "notes": "Imported from Gluroo",
        }
    }


@dataclass(frozen=True)
class GlurooSnapshot:
    """Latest data returned by Gluroo's Nightscout-compatible API."""

    entries: tuple[GlucoseReading, ...]
    treatments: tuple[dict[str, Any], ...]
    devicestatus: tuple[dict[str, Any], ...]
    fetched_at: datetime

    @property
    def latest(self) -> GlucoseReading | None:
        """Return the newest valid glucose reading."""
        return self.entries[0] if self.entries else None


def as_documents(value: Any) -> list[dict[str, Any]]:
    """Normalize Nightscout list responses."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("entries", "treatments", "devicestatus", "data"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def find_numeric(value: Any, names: set[str]) -> float | None:
    """Find a named numeric value in nested OpenAPS/Loop status data."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            suffix = normalized.removeprefix("gluroo").lstrip("_")
            if normalized in names or suffix in names:
                number = _number(item)
                if number is not None:
                    return number
            found = find_numeric(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_numeric(item, names)
            if found is not None:
                return found
    return None
