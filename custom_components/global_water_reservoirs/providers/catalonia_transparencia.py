"""Catalunya reservoirs from Transparència Catalunya (Socrata)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://analisi.transparenciacatalunya.cat/resource/gn9e-3qhr.json"


class CatalunyaTransparenciaProvider(BaseReservoirProvider):
    id = "catalonia_transparencia"
    name = "Catalunya"
    source_url = BASE_URL
    allowed_update_intervals_hours = [12, 24]
    default_update_interval_hours = 12

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        # Efficient listing: distinct stations.
        # SoQL: $select=distinct estaci
        url = f"{BASE_URL}?$select=distinct%20estaci&$order=estaci%20ASC"

        async with async_timeout.timeout(30):
            resp = await session.get(url)
            resp.raise_for_status()
            data = await resp.json()

        reservoirs: dict[str, str] = {}
        for item in data:
            name = item.get("estaci")
            if not name:
                continue
            reservoirs[name] = name
        return reservoirs

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        # We fetch a limited number of latest rows and take the most recent per station.
        # This avoids one-request-per-reservoir and stays light.
        url = (
            f"{BASE_URL}?$select=dia,estaci,nivell_absolut,volum_embassat,percentatge_volum_embassat"
            f"&$order=dia%20DESC&$limit=500"
        )

        async with async_timeout.timeout(30):
            resp = await session.get(url)
            resp.raise_for_status()
            rows: list[dict[str, Any]] = await resp.json()

        wanted = set(only_keys) if only_keys else None

        latest_by_station: dict[str, dict[str, Any]] = {}
        for row in rows:
            station = row.get("estaci")
            if not station:
                continue
            if wanted is not None and station not in wanted:
                continue
            if station not in latest_by_station:
                latest_by_station[station] = row

        out: dict[str, ReservoirData] = {}
        for station, row in latest_by_station.items():
            # Record date is a daily measurement; treat as local midnight.
            record_dt = _parse_socrata_date(row.get("dia"))
            unique_id = self.stable_unique_id(station, prefix="cat")

            out[station] = ReservoirData(
                key=station,
                unique_id=unique_id,
                name=_pretty_name(station),
                percent=_to_float(row.get("percentatge_volum_embassat")),
                volume_hm3=_to_float(row.get("volum_embassat")),
                level_m=_to_float(row.get("nivell_absolut")),
                record_dt=record_dt,
                source_url=self.source_url,
                raw=row,
            )

        return out


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_socrata_date(v: Any) -> datetime | None:
    if not v:
        return None
    # Socrata can return ISO strings like 2025-12-30T00:00:00.000 or 2025-12-30
    try:
        # dt_util.parse_datetime handles many ISO formats.
        dt = dt_util.parse_datetime(str(v))
        if dt is None:
            d = dt_util.parse_date(str(v))
            if d is None:
                return None
            # local midnight -> UTC
            local_dt = datetime.combine(d, time.min).replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt_util.as_utc(local_dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return dt_util.as_utc(dt)
    except Exception:  # noqa: BLE001
        return None


def _pretty_name(station: str) -> str:
    # The dataset already provides friendly names; we keep as-is.
    return station
