"""Diagnostics support for GlobalWaterReservoirs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_STALE_DATA_HOURS = 72


def _data_age_hours(record_dt: datetime | None) -> float | None:
    if record_dt is None:
        return None
    dt = record_dt if record_dt.tzinfo is not None else record_dt.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    provider = data["provider"]

    reservoirs = {}
    for key, res in coordinator.data.items():
        age_hours = _data_age_hours(res.record_dt)
        reservoirs[key] = {
            "key": res.key,
            "name": res.name,
            "unique_id": res.unique_id,
            "percent": res.percent,
            "volume_hm3": res.volume_hm3,
            "capacity_hm3": res.capacity_hm3,
            "level_m": res.level_m,
            "record_dt": res.record_dt.isoformat() if res.record_dt else None,
            "data_age_hours": round(age_hours, 2) if age_hours is not None else None,
            "data_stale": age_hours > _STALE_DATA_HOURS if age_hours is not None else None,
            "basin": res.basin,
            "province": res.province,
            "source_url": res.source_url,
            "raw": res.raw,
        }

    selected = list(coordinator.selected_reservoir_keys)
    returned = set(coordinator.data)
    missing_selected = [key for key in selected if key not in returned]

    last_exception = getattr(coordinator, "last_exception", None)
    last_update_success_time = getattr(coordinator, "last_update_success_time", None)

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": getattr(entry, "version", None),
            "minor_version": getattr(entry, "minor_version", None),
        },
        "provider": {
            "id": provider.id,
            "name": provider.name,
            "source_url": getattr(provider, "source_url", None),
            "allowed_update_intervals_hours": provider.allowed_update_intervals_hours,
        },
        "coordinator": {
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "last_update_success_time": last_update_success_time.isoformat()
            if last_update_success_time
            else None,
            "last_exception": str(last_exception) if last_exception else None,
        },
        "selected_reservoirs": selected,
        "selected_count": len(selected),
        "returned_count": len(reservoirs),
        "missing_selected_reservoirs": missing_selected,
        "stale_data_threshold_hours": _STALE_DATA_HOURS,
        "update_interval_seconds": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "reservoirs": reservoirs,
    }
