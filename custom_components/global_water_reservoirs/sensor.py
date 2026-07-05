"""Sensor platform for Global Water Reservoirs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import GlobalWaterReservoirsDataUpdateCoordinator
from .providers.base import ReservoirData

_STALE_DATA_HOURS = 72
_SENSOR_PRECISION: dict[str, int] = {
    "percent": 1,
    "volume": 1,
    "level": 2,
    "capacity": 1,
    "data_age": 1,
    "aggregate_percent": 1,
    "aggregate_volume": 1,
    "aggregate_capacity": 1,
}


@dataclass(frozen=True, kw_only=True)
class ReservoirSensorEntityDescription(SensorEntityDescription):
    """Describes a reservoir sensor."""

    key_name: str  # key inside ReservoirData to read


@dataclass(frozen=True, kw_only=True)
class AggregateSensorEntityDescription(SensorEntityDescription):
    """Describes an aggregate hub sensor."""

    aggregate_key: str


SENSORS: list[ReservoirSensorEntityDescription] = [
    ReservoirSensorEntityDescription(
        key="percent",
        translation_key="percent",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        key_name="percent",
    ),
    ReservoirSensorEntityDescription(
        key="volume",
        translation_key="volume",
        icon="mdi:cup-water",
        native_unit_of_measurement="hm³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        key_name="volume_hm3",
    ),
    ReservoirSensorEntityDescription(
        key="level",
        translation_key="level",
        icon="mdi:water",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        key_name="level_m",
    ),
    ReservoirSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        icon="mdi:database",
        native_unit_of_measurement="hm³",
        suggested_display_precision=2,
        key_name="capacity_hm3",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ReservoirSensorEntityDescription(
        key="record_datetime",
        translation_key="record_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
        key_name="record_dt",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ReservoirSensorEntityDescription(
        key="data_age",
        translation_key="data_age",
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        key_name="data_age",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


AGGREGATE_SENSORS: list[AggregateSensorEntityDescription] = [
    AggregateSensorEntityDescription(
        key="aggregate_percent",
        translation_key="aggregate_percent",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        aggregate_key="aggregate_percent",
    ),
    AggregateSensorEntityDescription(
        key="aggregate_volume",
        translation_key="aggregate_volume",
        icon="mdi:cup-water",
        native_unit_of_measurement="hm³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        aggregate_key="aggregate_volume",
    ),
    AggregateSensorEntityDescription(
        key="aggregate_capacity",
        translation_key="aggregate_capacity",
        icon="mdi:database",
        native_unit_of_measurement="hm³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        aggregate_key="aggregate_capacity",
    ),
    AggregateSensorEntityDescription(
        key="reservoir_count",
        translation_key="reservoir_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        aggregate_key="reservoir_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AggregateSensorEntityDescription(
        key="reservoirs_with_data",
        translation_key="reservoirs_with_data",
        icon="mdi:database-check",
        state_class=SensorStateClass.MEASUREMENT,
        aggregate_key="reservoirs_with_data",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AggregateSensorEntityDescription(
        key="stale_reservoir_count",
        translation_key="stale_reservoir_count",
        icon="mdi:database-clock",
        state_class=SensorStateClass.MEASUREMENT,
        aggregate_key="stale_reservoir_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AggregateSensorEntityDescription(
        key="latest_record_datetime",
        translation_key="latest_record_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
        aggregate_key="latest_record_datetime",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


def _data_age_hours(record_dt: datetime | None) -> float | None:
    if record_dt is None:
        return None
    now = datetime.now(timezone.utc)
    dt = record_dt if record_dt.tzinfo is not None else record_dt.replace(tzinfo=timezone.utc)
    return max((now - dt).total_seconds() / 3600, 0)


def _reservoirs_with_attr(reservoirs: list[ReservoirData], attr: str) -> list[float]:
    values: list[float] = []
    for reservoir in reservoirs:
        value = getattr(reservoir, attr)
        if value is not None:
            values.append(float(value))
    return values


def _aggregate_percent(reservoirs: list[ReservoirData]) -> tuple[float | None, str | None]:
    total_volume = 0.0
    total_capacity = 0.0
    for reservoir in reservoirs:
        if reservoir.volume_hm3 is None or not reservoir.capacity_hm3:
            continue
        total_volume += reservoir.volume_hm3
        total_capacity += reservoir.capacity_hm3

    if total_capacity > 0:
        return (total_volume / total_capacity) * 100, "capacity_weighted"

    percentages = _reservoirs_with_attr(reservoirs, "percent")
    if percentages:
        return sum(percentages) / len(percentages), "average_percent"

    return None, None


def _latest_record_dt(reservoirs: list[ReservoirData]) -> datetime | None:
    dates = [
        reservoir.record_dt if reservoir.record_dt.tzinfo is not None else reservoir.record_dt.replace(tzinfo=timezone.utc)
        for reservoir in reservoirs
        if reservoir.record_dt is not None
    ]
    if not dates:
        return None
    return max(dates)


def _stale_reservoir_count(reservoirs: list[ReservoirData]) -> int:
    return sum(
        1
        for reservoir in reservoirs
        if (age_hours := _data_age_hours(reservoir.record_dt)) is not None and age_hours > _STALE_DATA_HOURS
    )


def _aggregate_value(key: str, reservoirs: list[ReservoirData]) -> Any:
    if key == "aggregate_percent":
        value, _method = _aggregate_percent(reservoirs)
        return value

    if key == "aggregate_volume":
        values = _reservoirs_with_attr(reservoirs, "volume_hm3")
        return sum(values) if values else None

    if key == "aggregate_capacity":
        values = _reservoirs_with_attr(reservoirs, "capacity_hm3")
        return sum(values) if values else None

    if key == "reservoir_count":
        return len(reservoirs)

    if key == "reservoirs_with_data":
        return sum(
            1
            for reservoir in reservoirs
            if reservoir.percent is not None
            or reservoir.volume_hm3 is not None
            or reservoir.level_m is not None
        )

    if key == "stale_reservoir_count":
        return _stale_reservoir_count(reservoirs)

    if key == "latest_record_datetime":
        return _latest_record_dt(reservoirs)

    return None


def _round_value(value: Any, precision: int | None) -> Any:
    if value is None or precision is None:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return round(float(value), precision)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: GlobalWaterReservoirsDataUpdateCoordinator = data["coordinator"]
    provider = data["provider"]

    entities: list[SensorEntity] = []
    provider_source_url = getattr(provider, "source_url", None)
    current_reservoirs = list(coordinator.data.values())

    for desc in AGGREGATE_SENSORS:
        if _aggregate_value(desc.aggregate_key, current_reservoirs) is None:
            continue
        entities.append(
            AggregateEmbalseSensor(
                coordinator=coordinator,
                entry=entry,
                description=desc,
                provider_id=provider.id,
                provider_name=provider.name,
                provider_source_url=provider_source_url,
            )
        )

    for reservoir_key, reservoir in coordinator.data.items():
        # Create only sensors that have data; age depends on record_dt.
        for desc in SENSORS:
            if desc.key_name == "data_age":
                if reservoir.record_dt is None:
                    continue
            else:
                if getattr(reservoir, desc.key_name, None) is None:
                    continue
            entities.append(
                EmbalseSensor(
                    coordinator=coordinator,
                    description=desc,
                    provider_id=provider.id,
                    provider_name=provider.name,
                    provider_source_url=provider_source_url,
                    reservoir=reservoir,
                )
            )

    async_add_entities(entities)


class EmbalseSensor(CoordinatorEntity[GlobalWaterReservoirsDataUpdateCoordinator], SensorEntity):
    """A sensor for a reservoir."""

    entity_description: ReservoirSensorEntityDescription
    has_entity_name = True

    def __init__(
        self,
        coordinator: GlobalWaterReservoirsDataUpdateCoordinator,
        description: ReservoirSensorEntityDescription,
        provider_id: str,
        provider_name: str,
        provider_source_url: str | None,
        reservoir: ReservoirData,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._reservoir_key = reservoir.key
        self._reservoir_name = reservoir.name

        # Stable unique id across reloads.
        self._attr_unique_id = f"{provider_id}:{reservoir.unique_id}:{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{provider_id}:{reservoir.unique_id}")},
            name=reservoir.name,
            manufacturer=provider_name,
            model="Embalse",
            configuration_url=reservoir.source_url or provider_source_url,
        )

    @property
    def native_value(self) -> Any:
        reservoir = self.coordinator.data.get(self._reservoir_key)
        if reservoir is None:
            return None

        key_name = self.entity_description.key_name

        if key_name == "record_dt":
            return reservoir.record_dt

        if key_name == "data_age":
            if reservoir.record_dt is None:
                return None
            return _round_value(
                _data_age_hours(reservoir.record_dt),
                _SENSOR_PRECISION.get(self.entity_description.key),
            )

        return _round_value(
            getattr(reservoir, key_name, None),
            _SENSOR_PRECISION.get(self.entity_description.key),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reservoir = self.coordinator.data.get(self._reservoir_key)
        if reservoir is None:
            return {}

        attrs: dict[str, Any] = {
            "provider": self._provider_id,
            "source_name": self._provider_name,
            "reservoir_key": reservoir.key,
        }
        if reservoir.record_dt:
            attrs["record_datetime"] = reservoir.record_dt.isoformat()
            age_hours = _data_age_hours(reservoir.record_dt)
            if age_hours is not None:
                attrs["data_age_hours"] = round(age_hours, 2)
                attrs["data_stale"] = age_hours > _STALE_DATA_HOURS
        if reservoir.basin:
            attrs["basin"] = reservoir.basin
        if reservoir.province:
            attrs["province"] = reservoir.province
        if reservoir.source_url:
            attrs["source_url"] = reservoir.source_url
        return attrs


class AggregateEmbalseSensor(CoordinatorEntity[GlobalWaterReservoirsDataUpdateCoordinator], SensorEntity):
    """A hub-level aggregate sensor."""

    entity_description: AggregateSensorEntityDescription
    has_entity_name = True

    def __init__(
        self,
        coordinator: GlobalWaterReservoirsDataUpdateCoordinator,
        entry: ConfigEntry,
        description: AggregateSensorEntityDescription,
        provider_id: str,
        provider_name: str,
        provider_source_url: str | None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._provider_source_url = provider_source_url

        entry_unique = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{provider_id}:{entry_unique}:aggregate:{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{provider_id}:{entry_unique}:aggregate")},
            name=entry.title,
            manufacturer=provider_name,
            model="Hub de embalses",
            configuration_url=provider_source_url,
        )

    @property
    def native_value(self) -> Any:
        reservoirs = list(self.coordinator.data.values())
        return _round_value(
            _aggregate_value(self.entity_description.aggregate_key, reservoirs),
            _SENSOR_PRECISION.get(self.entity_description.key),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reservoirs = list(self.coordinator.data.values())
        percent_value, percent_method = _aggregate_percent(reservoirs)
        latest_record = _latest_record_dt(reservoirs)
        volume_values = _reservoirs_with_attr(reservoirs, "volume_hm3")
        capacity_values = _reservoirs_with_attr(reservoirs, "capacity_hm3")
        percent_values = _reservoirs_with_attr(reservoirs, "percent")

        attrs: dict[str, Any] = {
            "provider": self._provider_id,
            "source_name": self._provider_name,
            "selected_reservoirs": len(self.coordinator.selected_reservoir_keys),
            "returned_reservoirs": len(reservoirs),
            "reservoirs_with_volume": len(volume_values),
            "reservoirs_with_capacity": len(capacity_values),
            "reservoirs_with_percent": len(percent_values),
            "stale_data_threshold_hours": _STALE_DATA_HOURS,
            "stale_reservoirs": _stale_reservoir_count(reservoirs),
        }

        if percent_value is not None:
            attrs["aggregate_percent"] = round(percent_value, 2)
        if percent_method:
            attrs["aggregate_percent_method"] = percent_method
        if latest_record:
            attrs["latest_record_datetime"] = latest_record.isoformat()
            age_hours = _data_age_hours(latest_record)
            if age_hours is not None:
                attrs["latest_data_age_hours"] = round(age_hours, 2)
        if self._provider_source_url:
            attrs["source_url"] = self._provider_source_url
        return attrs

