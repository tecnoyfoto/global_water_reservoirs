"""Tajo basin reservoirs from SAIH Tajo."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://saihtajo.chtajo.es"
APP_URL = f"{BASE_URL}/index.php?url=/tr/mapas/ambito:E/mapa:H7"

_WRAPPER_RE = re.compile(r"accAjax\('([^']*get-wrapperentorno[^']*)'")


class TajoSAIHProvider(BaseReservoirProvider):
    """Provider backed by SAIH Tajo's public JSON endpoints."""

    id = "tajo_saih"
    name = "SAIH Tajo"
    source_url = APP_URL
    allowed_update_intervals_hours = [1, 2, 6, 12, 24]
    default_update_interval_hours = 2

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        stations = await self._get_stations(session, include_auxiliary=False)
        return dict(sorted(((s["codigo"], _title_name(s["nombre"])) for s in stations), key=lambda kv: kv[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        stations = await self._get_stations(session, include_auxiliary=True)
        wanted = set(only_keys) if only_keys else None

        out: dict[str, ReservoirData] = {}
        for station in stations:
            key = station.get("codigo")
            if not key:
                continue
            if wanted is not None and key not in wanted:
                continue

            detail = await self._get_json(session, station["url"])
            payload = detail.get("response") if isinstance(detail, dict) else None
            if not isinstance(payload, dict):
                continue

            signals = payload.get("senales") if isinstance(payload.get("senales"), list) else []
            volume_value, volume_dt = _latest_signal(signals, "VE")
            percent_value, percent_dt = _latest_signal(signals, "PO")
            level_value, level_dt = _latest_signal(signals, "NE")
            record_dt = max((dt for dt in (volume_dt, percent_dt, level_dt) if dt is not None), default=None)

            capacity_hm3 = None
            if volume_value is not None and percent_value and percent_value > 0:
                capacity_hm3 = volume_value / (percent_value / 100.0)

            name = _title_name(str(payload.get("nombre") or station.get("nombre") or key))
            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=name,
                percent=percent_value,
                volume_hm3=volume_value,
                capacity_hm3=capacity_hm3,
                level_m=level_value,
                record_dt=record_dt,
                basin="Tajo",
                province=_title_name(str(payload.get("provincia") or station.get("nombreprovincia") or ""))
                or None,
                source_url=APP_URL,
                raw={
                    "station": key,
                    "system": payload.get("zona") or station.get("nombresistema"),
                    "municipality": payload.get("municipio"),
                    "community": payload.get("comunidad") or station.get("nombrecomunidad"),
                    "signals": [
                        {
                            "tag": signal.get("tag"),
                            "name": signal.get("nombre"),
                            "type": signal.get("tiposenal"),
                            "unit": signal.get("unidad"),
                        }
                        for signal in signals
                        if isinstance(signal, dict)
                    ],
                },
            )

        return out

    async def _get_stations(self, session, *, include_auxiliary: bool) -> list[dict[str, Any]]:
        menu = await self._get_menu(session)
        realtime_url = _find_menu_link(menu, "Datos en tiempo real")
        data = await self._get_json(session, realtime_url)
        response = data.get("response") if isinstance(data, dict) else None
        cuenca = response.get("cuenca") if isinstance(response, dict) else None
        subbasins = cuenca.get("subcuencas") if isinstance(cuenca, dict) else None
        if not isinstance(subbasins, list):
            raise ValueError("Unexpected JSON structure from SAIH Tajo")

        by_code: dict[str, dict[str, Any]] = {}
        for subbasin in subbasins:
            for kind in subbasin.get("tipos", []) if isinstance(subbasin, dict) else []:
                if not isinstance(kind, dict) or kind.get("nombre_limpio") != "embalse":
                    continue
                for station in kind.get("estaciones", []):
                    if isinstance(station, dict) and station.get("codigo") and station.get("url"):
                        if not include_auxiliary and not _is_selectable_reservoir(station):
                            continue
                        by_code[str(station["codigo"])] = station
        return list(by_code.values())

    async def _get_menu(self, session) -> dict[str, Any]:
        async with async_timeout.timeout(45):
            resp = await session.get(APP_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp.raise_for_status()
            html = await resp.text()

        match = _WRAPPER_RE.search(html)
        if not match:
            raise ValueError("Could not find SAIH Tajo wrapper URL")

        wrapper = await self._get_json(session, match.group(1).replace("&amp;", "&"))
        response = wrapper.get("response") if isinstance(wrapper, dict) else None
        menu_url = response.get("urlmenu") if isinstance(response, dict) else None
        if not menu_url:
            raise ValueError("Could not find SAIH Tajo menu URL")

        menu = await self._get_json(session, menu_url)
        response = menu.get("response") if isinstance(menu, dict) else None
        if not isinstance(response, dict):
            raise ValueError("Unexpected SAIH Tajo menu response")
        return response

    async def _get_json(self, session, url: str) -> dict[str, Any]:
        full_url = url if url.startswith("http") else f"{BASE_URL}/{url.lstrip('/')}"
        async with async_timeout.timeout(45):
            resp = await session.get(full_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            resp.raise_for_status()
            return await resp.json(content_type=None)


def _find_menu_link(menu: dict[str, Any], label: str) -> str:
    for item in menu.get("items", []):
        if not isinstance(item, dict):
            continue
        if item.get("name") == label and item.get("link"):
            return str(item["link"])
        for child in item.get("items2", []):
            if isinstance(child, dict) and child.get("name") == label and child.get("link"):
                return str(child["link"])
    raise ValueError(f"Could not find SAIH Tajo menu link: {label}")


def _is_selectable_reservoir(station: dict[str, Any]) -> bool:
    """Return false for auxiliary hydraulic structures shown in the SAIH embalse layer."""
    name = str(station.get("nombre") or "").strip().casefold()
    return not name.startswith("azud ")


def _latest_signal(signals: list[Any], signal_type: str) -> tuple[float | None, datetime | None]:
    for signal in signals:
        if not isinstance(signal, dict) or signal.get("tiposenal") != signal_type:
            continue
        values = signal.get("valores")
        if not isinstance(values, list):
            return None, None
        latest_value = None
        latest_dt = None
        for item in values:
            if not isinstance(item, dict):
                continue
            dt = _parse_local_dt(item.get("tiempo"))
            value = _float(item.get("valor"))
            if value is not None and (latest_dt is None or (dt is not None and dt > latest_dt)):
                latest_value = value
                latest_dt = dt
        return latest_value, latest_dt
    return None, None


def _parse_local_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(str(value), "%d/%m/%Y %H:%M")
    except ValueError:
        return None
    return dt_util.as_utc(dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _title_name(name: str) -> str:
    small_words = {"de", "del", "la", "las", "los", "el", "y"}
    words = []
    for idx, word in enumerate(name.lower().split()):
        words.append(word if idx > 0 and word in small_words else word.capitalize())
    return " ".join(words)
