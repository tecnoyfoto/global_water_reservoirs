"""Shared helpers for MITECO basin providers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

import async_timeout

from homeassistant.util import dt as dt_util

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


class MitecoBasinProvider(BaseReservoirProvider):
    """Base provider for MITECO reservoir map layer subsets."""

    source_url = SOURCE_URL
    allowed_update_intervals_hours = [12, 24]
    default_update_interval_hours = 12

    where: ClassVar[str]
    basin_name: ClassVar[str]
    source_name: ClassVar[str]
    name_fixes: ClassVar[dict[str, str]] = {}
    include_basin_in_list_name: ClassVar[bool] = False
    use_feature_basin: ClassVar[bool] = False

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        features = await self._download(session)
        out: dict[str, str] = {}
        for attrs in features:
            key = _key(attrs)
            name = self._name(attrs)
            basin = _text(attrs.get("ambito_nombre"))
            if key and name:
                out[key] = f"{name} - {basin}" if self.include_basin_in_list_name and basin else name
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

            name = self._name(attrs)
            if not name:
                continue

            record_dt = _parse_arcgis_dt(attrs.get("fecha")) or _parse_miteco_date(
                attrs.get("Fecha_str")
            )
            basin = _text(attrs.get("ambito_nombre")) if self.use_feature_basin else self.basin_name

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=name,
                percent=_float(attrs.get("Porcentaje_Reserva")),
                volume_hm3=_float(attrs.get("agua_actual")),
                capacity_hm3=_float(attrs.get("agua_total")),
                record_dt=record_dt,
                basin=basin or self.basin_name,
                source_url=SOURCE_URL,
                raw={
                    "source": self.source_name,
                    "ambito_nombre": attrs.get("ambito_nombre"),
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
            "where": self.where,
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
            raise ValueError(f"Unexpected JSON structure from {self.source_name} service")

        out: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            attrs = feature.get("attributes")
            if isinstance(attrs, dict):
                out.append(attrs)
        return out

    def _name(self, attrs: dict[str, Any]) -> str | None:
        name = _text(attrs.get("embalse_nombre"))
        if not name:
            return None
        return self.name_fixes.get(name, name)


def _key(attrs: dict[str, Any]) -> str | None:
    value = attrs.get("EMBALSE_ID")
    if value is None:
        return None
    return str(value)


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
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
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


def _parse_miteco_date(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%d%m%Y", "%Y%m%d"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt_util.as_utc(dt.replace(hour=8, tzinfo=dt_util.DEFAULT_TIME_ZONE))
    return None
