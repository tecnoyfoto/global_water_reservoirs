"""Spanish reservoirs from MITECO weekly hydrological bulletin."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import async_timeout

from .base import BaseReservoirProvider, ReservoirData

SERVICE_URL = (
    "https://services-eu1.arcgis.com/RvnYk1PBUJ9rrAuT/arcgis/rest/services/"
    "Embalses_Mapa/FeatureServer/0/query"
)
SOURCE_URL = "https://miteco.maps.arcgis.com/apps/dashboards/912dfee767264e3884f7aea8eb1e0673"

OUT_FIELDS = ",".join(
    [
        "EMBALSE_ID",
        "embalse_nombre",
        "ambito_nombre",
        "agua_total",
        "agua_actual",
        "Porcentaje_Reserva",
        "fecha",
        "Fecha_str",
        "Uso",
        "Variacion_Reserva",
        "Variacion_Porcentaje",
        "boletin_anyo",
        "boletin_num",
    ]
)


class MitecoBoletinProvider(BaseReservoirProvider):
    """Provider backed by MITECO's latest weekly reservoir map layer."""

    id = "miteco_boletin"
    name = "MITECO Boletín Hidrológico"
    source_url = SOURCE_URL
    allowed_update_intervals_hours = [12, 24]
    default_update_interval_hours = 24

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        features = await self._download(session)
        out: dict[str, str] = {}
        for attrs in features:
            key = _key(attrs)
            name = _name(attrs)
            basin = _text(attrs.get("ambito_nombre"))
            if key and name:
                out[key] = f"{name} - {basin}" if basin else name
        return dict(sorted(out.items(), key=lambda kv: kv[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        features = await self._download(session)
        wanted = set(only_keys) if only_keys else None

        out: dict[str, ReservoirData] = {}
        for attrs in features:
            key = _key(attrs)
            if not key:
                continue
            if wanted is not None and key not in wanted:
                continue

            name = _name(attrs)
            if not name:
                continue

            basin = _text(attrs.get("ambito_nombre"))
            capacity_hm3 = _float(attrs.get("agua_total"))
            volume_hm3 = _float(attrs.get("agua_actual"))
            percent = _float(attrs.get("Porcentaje_Reserva"))
            record_dt = _parse_arcgis_dt(attrs.get("fecha"))

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=name,
                percent=percent,
                volume_hm3=volume_hm3,
                capacity_hm3=capacity_hm3,
                record_dt=record_dt,
                basin=basin,
                source_url=SOURCE_URL,
                raw={
                    "source": "MITECO Boletín Hidrológico",
                    "usage": attrs.get("Uso"),
                    "date_text": attrs.get("Fecha_str"),
                    "bulletin_year": attrs.get("boletin_anyo"),
                    "bulletin_number": attrs.get("boletin_num"),
                    "variation_volume_hm3": attrs.get("Variacion_Reserva"),
                    "variation_percent": attrs.get("Variacion_Porcentaje"),
                },
            )

        return out

    async def _download(self, session) -> list[dict[str, Any]]:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": OUT_FIELDS,
            "returnGeometry": "false",
            "resultRecordCount": "2000",
        }
        async with async_timeout.timeout(45):
            resp = await session.get(
                SERVICE_URL,
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            resp.raise_for_status()
            payload = await resp.json(content_type=None)

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("Unexpected JSON structure from MITECO ArcGIS service")

        out: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            attrs = feature.get("attributes")
            if isinstance(attrs, dict):
                out.append(attrs)
        return out


def _key(attrs: dict[str, Any]) -> str | None:
    value = attrs.get("EMBALSE_ID")
    if value is None:
        return None
    return f"miteco-{value}"


def _name(attrs: dict[str, Any]) -> str | None:
    return _text(attrs.get("embalse_nombre"))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _parse_arcgis_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        timestamp = float(value) / 1000.0
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
