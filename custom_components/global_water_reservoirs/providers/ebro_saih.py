"""Ebro basin reservoirs from SAIH Ebro."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://home.saihebro.com"
MAP_SLUG = "mapa-embalses-HG-toda-la-cuenca"
DATA_URL = f"{BASE_URL}/api/mapa/getDatosMapa?slug={MAP_SLUG}"


class EbroSAIHProvider(BaseReservoirProvider):
    id = "ebro_saih"
    name = "SAIH Ebro"
    source_url = f"{BASE_URL}/tiempo-real/estacion-embalses-E001-ebro"
    allowed_update_intervals_hours = [1, 2, 6, 12, 24]
    default_update_interval_hours = 2

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        data = await self._download(session)
        out: dict[str, str] = {}
        for item in data:
            key = _station_key(item)
            name = _station_name(item)
            if key and name:
                out[key] = name
        return dict(sorted(out.items(), key=lambda kv: kv[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        data = await self._download(session)
        wanted = set(only_keys) if only_keys else None

        out: dict[str, ReservoirData] = {}
        for item in data:
            key = _station_key(item)
            if not key:
                continue
            if wanted is not None and key not in wanted:
                continue

            name = _station_name(item)
            slug = str(item.get("LR_NOMBRE_CORTO_SLUG") or "").strip()
            source_url = f"{BASE_URL}/tiempo-real/estacion-embalses-{key}-{slug}" if slug else self.source_url

            tags = item.get("TAGS") if isinstance(item.get("TAGS"), list) else []
            level_m = _find_tag_value(tags, "NEMBA")
            volume_hm3 = _find_tag_value(tags, "VEMBA")
            percent = _find_tag_value(tags, "PORCE")
            record_dt = _latest_record_dt(tags) or _parse_local_dt(item.get("ULTIMA_FECHA"))

            capacity_hm3 = None
            if volume_hm3 is not None and percent and percent > 0:
                capacity_hm3 = volume_hm3 / (percent / 100.0)

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=name,
                percent=percent,
                volume_hm3=volume_hm3,
                capacity_hm3=capacity_hm3,
                level_m=level_m,
                record_dt=record_dt,
                basin="Ebro",
                source_url=source_url,
                raw={
                    "station": key,
                    "map_slug": MAP_SLUG,
                    "source_name": item.get("LR_NOMBRE_CORTO"),
                    "tags": tags,
                },
            )

        return out

    async def _download(self, session) -> list[dict[str, Any]]:
        async with async_timeout.timeout(45):
            resp = await session.get(DATA_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            resp.raise_for_status()
            payload = await resp.json(content_type=None)

        data = payload.get("DATOS") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ValueError("Unexpected JSON structure from SAIH Ebro")
        return [item for item in data if isinstance(item, dict)]


def _station_key(item: dict[str, Any]) -> str | None:
    key = item.get("CW_REMOTA_TXT")
    return str(key).strip() if key else None


def _station_name(item: dict[str, Any]) -> str | None:
    name = item.get("LR_NOMBRE_CORTO")
    if not name:
        return None
    return _title_name(str(name).strip())


def _title_name(name: str) -> str:
    small_words = {"de", "del", "la", "las", "los", "el", "y"}
    words = []
    for idx, word in enumerate(name.lower().split()):
        words.append(word if idx > 0 and word in small_words else word.capitalize())
    return " ".join(words)


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_tag_value(tags: list[Any], signal_type: str) -> float | None:
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if str(tag.get("LS_TIPO_SENAL") or "").upper() == signal_type:
            return _parse_float(tag.get("VALOR") or tag.get("VALOR_QM") or tag.get("LS_VALOR_QM"))
    return None


def _latest_record_dt(tags: list[Any]) -> datetime | None:
    dates = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        dt = _parse_local_dt(tag.get("ULTIMA_FECHA"))
        if dt is not None:
            dates.append(dt)
    return max(dates) if dates else None


def _parse_local_dt(value: Any) -> datetime | None:
    if not value:
        return None
    dt = dt_util.parse_datetime(str(value))
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(dt)
