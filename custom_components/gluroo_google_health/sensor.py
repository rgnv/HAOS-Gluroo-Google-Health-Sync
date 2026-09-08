"""Home Assistant sensors backed by the Gluroo coordinator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfBloodGlucoseConcentration
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GlurooCoordinator
from .models import GlurooSnapshot, find_numeric


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Create stable sensors for the configured Gluroo account."""
    coordinator = cast(GlurooCoordinator, entry.runtime_data.coordinator)
    async_add_entities(
        [
            GlurooGlucoseSensor(coordinator, entry.entry_id),
            GlurooDeltaSensor(coordinator, entry.entry_id),
            GlurooTrendSensor(coordinator, entry.entry_id),
            GlurooAgeSensor(coordinator, entry.entry_id),
            GlurooTreatmentSensor(coordinator, entry.entry_id),
            GlurooInsulinSensor(coordinator, entry.entry_id),
            GlurooCarbsSensor(coordinator, entry.entry_id),
            GlurooIobSensor(coordinator, entry.entry_id),
            GlurooCobSensor(coordinator, entry.entry_id),
        ]
    )


class GlurooSensorBase(CoordinatorEntity[GlurooCoordinator], SensorEntity):
    """Common entity behavior."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GlurooCoordinator, entry_id: str, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Gluroo",
            manufacturer="Gluroo",
            model="Global Connect",
        )

    @property
    def available(self) -> bool:
        """Only expose values after a successful coordinator refresh."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def _snapshot(self) -> GlurooSnapshot | None:
        return self.coordinator.data


class GlurooGlucoseSensor(GlurooSensorBase):
    """Latest glucose value."""

    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION
    _attr_native_unit_of_measurement = UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "glucose", "Blood glucose")

    @property
    def native_value(self) -> float | None:
        reading = self._snapshot.latest if self._snapshot else None
        return reading.glucose_mgdl if reading else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        reading = self._snapshot.latest if self._snapshot else None
        if not reading:
            return None
        return {
            "entry_id": reading.entry_id,
            "measured_at": reading.measured_at.isoformat(),
            "delta": reading.delta,
            "direction": reading.direction,
            "source": "Gluroo Global Connect",
        }


class GlurooDeltaSensor(GlurooSensorBase):
    """Latest glucose delta."""

    _attr_native_unit_of_measurement = UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "delta", "Glucose delta")

    @property
    def native_value(self) -> float | None:
        reading = self._snapshot.latest if self._snapshot else None
        return reading.delta if reading else None


class GlurooTrendSensor(GlurooSensorBase):
    """Latest Nightscout trend direction."""

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "trend", "Glucose trend")

    @property
    def native_value(self) -> str | None:
        reading = self._snapshot.latest if self._snapshot else None
        return reading.direction if reading else None


class GlurooAgeSensor(GlurooSensorBase):
    """Age of the latest reading in seconds."""

    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "age", "Glucose reading age")

    @property
    def native_value(self) -> float | None:
        snapshot = self._snapshot
        if not snapshot or not snapshot.latest:
            return None
        return max(0.0, (snapshot.fetched_at - snapshot.latest.measured_at).total_seconds())


class GlurooTreatmentSensor(GlurooSensorBase):
    """Most recent treatment event, with full event fields as attributes."""

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "last_treatment", "Last treatment")

    @property
    def native_value(self) -> str | None:
        treatment = _latest_document(self._snapshot.treatments if self._snapshot else ())
        return str(treatment.get("eventType") or treatment.get("event_type") or "unknown") if treatment else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        treatment = _latest_document(self._snapshot.treatments if self._snapshot else ())
        return dict(treatment) if treatment else None


class GlurooInsulinSensor(GlurooSensorBase):
    """Insulin amount in the latest treatment."""

    _attr_native_unit_of_measurement = "U"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "last_insulin", "Last insulin")

    @property
    def native_value(self) -> float | None:
        treatment = _latest_document(self._snapshot.treatments if self._snapshot else ())
        return _first_number(treatment, ("insulin", "bolus"))


class GlurooCarbsSensor(GlurooSensorBase):
    """Carbohydrates in the latest treatment."""

    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "last_carbs", "Last carbohydrates")

    @property
    def native_value(self) -> float | None:
        treatment = _latest_document(self._snapshot.treatments if self._snapshot else ())
        return _first_number(treatment, ("carbs", "carb_input", "carbs_hr"))


class GlurooIobSensor(GlurooSensorBase):
    """Insulin on board from the latest device-status payload."""

    _attr_native_unit_of_measurement = "U"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "iob", "Insulin on board")

    @property
    def native_value(self) -> float | None:
        status = _latest_document(self._snapshot.devicestatus if self._snapshot else ())
        return find_numeric(status, {"iob", "insulin_on_board"})


class GlurooCobSensor(GlurooSensorBase):
    """Carbohydrates on board from the latest device-status payload."""

    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "cob", "Carbohydrates on board")

    @property
    def native_value(self) -> float | None:
        status = _latest_document(self._snapshot.devicestatus if self._snapshot else ())
        return find_numeric(status, {"cob", "carbs_on_board"})


def _first_number(document: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    """Return the first finite numeric treatment field."""
    for key in keys:
        value = document.get(key)
        try:
            result = float(value)
        except (TypeError, ValueError):
            continue
        if result == result and result not in (float("inf"), float("-inf")):
            return result
    return None


def _latest_document(documents: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Return the most recent document using common Nightscout time fields."""
    if not documents:
        return {}
    return max(documents, key=_document_time)


def _document_time(document: dict[str, Any]) -> datetime:
    """Parse a common Nightscout document time for local ordering."""
    value = document.get("date")
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    raw = document.get("created_at") or document.get("dateString")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)
