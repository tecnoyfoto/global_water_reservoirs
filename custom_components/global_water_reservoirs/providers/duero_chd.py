"""Cuenca del Duero reservoirs from CHD open data portal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

# Public JSON distribution (CKAN resource download)
DATA_URL = (
    "https://datos.chduero.es/dataset/f2eebe21-10eb-4b04-bf5b-71578dc3562c/"
    "resource/9b642c38-59b8-4ab0-8abd-6580ed64d261/download/estado_embalses.json"
)


class DueroCHDProvider(BaseReservoirProvider):
    id = "duero_chd"
    name = "Cuenca del Duero"
    source_url = DATA_URL
    allowed_update_intervals_hours = [6, 12, 24]
    default_update_interval_hours = 12

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        data = await self._download(session)
        out: dict[str, str] = {}
        for row in data:
            name = row.get("punto_control") or row.get("punto") or row.get("embalse")
            if not name:
                continue
            out[name] = str(name)
        # Keep deterministic ordering in UI (multi_select sorts by dict insertion order).
        return dict(sorted(out.items(), key=lambda kv: kv[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        data = await self._download(session)
        wanted = set(only_keys) if only_keys else None

        out: dict[str, ReservoirData] = {}
        for row in data:
            name = row.get("punto_control") or row.get("punto") or row.get("embalse")
            if not name:
                continue
            if wanted is not None and name not in wanted:
                continue

            codigo = row.get("codigo")
            unique_id = str(codigo) if codigo else self.stable_unique_id(str(name), prefix="du")
            record_dt = _parse_utc_dt(row.get("actualizacion"))

            out[str(name)] = ReservoirData(
                key=str(name),
                unique_id=str(unique_id),
                name=str(name),
                percent=_to_float(row.get("volumen_actual_percent")),
                volume_hm3=_to_float(row.get("volumen_actual_hm3")),
                capacity_hm3=_to_float(row.get("capacidad_hm3")),
                level_m=_to_float(row.get("nivel_actual_masl")),
                record_dt=record_dt,
                basin=row.get("sistema"),
                province=row.get("provincia"),
                source_url=self.source_url,
                raw=row,
            )

        return out

    async def _download(self, session) -> list[dict[str, Any]]:
        async with async_timeout.timeout(45):
            resp = await session.get(DATA_URL)
            resp.raise_for_status()
            data = await resp.json()

        # Most CKAN resources are arrays; tolerate dict-wrapped payloads.
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Common patterns: {"result": [...]}, {"data": [...]}
            for key in ("result", "data", "records"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        raise ValueError("Unexpected JSON structure from CHD")

def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _parse_utc_dt(v: Any) -> datetime | None:
    if not v:
        return None
    dt = dt_util.parse_datetime(str(v))
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Dataset says UTC; assume UTC when tz missing.
        dt = dt.replace(tzinfo=dt_util.UTC)
    return dt_util.as_utc(dt)
