"""Tests for pure Gluroo/Google Health data handling."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "gluroo_google_health"
    / "models.py"
)
_spec = importlib.util.spec_from_file_location("gluroo_models", _MODULE_PATH)
assert _spec and _spec.loader
models = importlib.util.module_from_spec(_spec)
sys.modules["gluroo_models"] = models
_spec.loader.exec_module(models)


def test_glucose_entry_parses_and_keeps_provider_id() -> None:
    reading = models.GlucoseReading.from_entry(
        {
            "_id": "entry-123",
            "date": 1788835200000,
            "sgv": 142,
            "delta": -3.5,
            "direction": "FortyFiveDown",
        }
    )

    assert reading is not None
    assert reading.entry_id == "entry-123"
    assert reading.glucose_mgdl == 142
    assert reading.delta == -3.5
    assert reading.measured_at.tzinfo == timezone.utc


def test_glucose_entry_rejects_malformed_values() -> None:
    assert models.GlucoseReading.from_entry({"date": 1, "sgv": 0}) is None
    assert models.GlucoseReading.from_entry({"date": 1, "sgv": "not-a-number"}) is None
    assert models.GlucoseReading.from_entry({"sgv": 120}) is None


def test_missing_provider_id_gets_stable_deterministic_id() -> None:
    entry = {"date": 1788835200000, "sgv": 142, "direction": "Flat"}
    first = models.GlucoseReading.from_entry(entry)
    second = models.GlucoseReading.from_entry(dict(entry))

    assert first and second
    assert first.entry_id == second.entry_id
    assert first.entry_id.startswith("gluroo-")


def test_google_health_payload_uses_mgdl_and_original_time() -> None:
    reading = models.GlucoseReading(
        entry_id="entry-123",
        glucose_mgdl=142.25,
        measured_at=datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc),
        delta=None,
        direction="Flat",
        raw={},
    )

    assert models.blood_glucose_payload(reading) == {
        "bloodGlucose": {
            "bloodGlucoseMilligramsPerDeciliter": 142.25,
            "sampleTime": {"physicalTime": "2026-09-07T20:00:00Z", "utcOffset": "0s"},
            "measurementSource": "CONTINUOUS_GLUCOSE_MONITORING",
            "specimen": "INTERSTITIAL_FLUID",
            "notes": "Imported from Gluroo",
        }
    }


def test_document_and_nested_status_normalization() -> None:
    assert models.as_documents({"entries": [{"sgv": 100}, "bad"]}) == [{"sgv": 100}]
    assert models.as_documents({"data": []}) == []
    assert models.find_numeric({"openaps": {"iob": 1.25}}, {"iob"}) == 1.25
    assert models.find_numeric({"loop": {"cob": "42"}}, {"cob"}) == 42
