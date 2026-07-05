"""Guadiana basin reservoirs from Confederacion Hidrografica del Guadiana."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://www.chguadiana.es"
SOURCE_URL = f"{BASE_URL}/cuenca-hidrografica/situacion-hidrologica"
DETAIL_URL = f"{BASE_URL}/sites/default/files/dashboard/embalses_detalle.json"
HIGHLIGHTS_URL = f"{BASE_URL}/sites/default/files/dashboard/tabla_destacado.json"
NOTICES_URL = f"{BASE_URL}/sites/default/files/dashboard/avisos.json"
MITECO_SERVICE_URL = (
    "https://services-eu1.arcgis.com/RvnYk1PBUJ9rrAuT/arcgis/rest/services/"
    "Embalses_Mapa/FeatureServer/0/query"
)

_NOTICE_DATE_RE = re.compile(r"fecha\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})", re.IGNORECASE)

FALLBACK_RESERVOIRS: dict[str, str] = {
    "E1-01": "Peñarroya",
    "E1-02": "Vallehermoso",
    "E1-03": "Puente Navarro",
    "E1-05": "Gasset",
    "E1-06": "El Vicario",
    "E1-07": "La Cabezuela",
    "E1-08": "Vega Jabalón",
    "E1-09": "Torre de Abraham",
    "E1-10": "Campos del Paraíso",
    "E2-01": "Cíjara",
    "E2-03": "García de Sola",
    "E2-04": "Orellana",
    "E2-06": "La Serena",
    "E2-07": "Zújar",
    "E2-08": "Cancho de Fresno",
    "E2-09": "Ruecas",
    "E2-10": "Azud de Lavadero",
    "E2-11": "Sierra Brava",
    "E2-12": "Gargáligas",
    "E2-13": "Cubilar",
    "E2-15": "Los Molinos",
    "E2-16": "Alange",
    "E2-17": "Cornalbo",
    "E2-18": "Proserpina",
    "E2-19": "Montijo",
    "E2-20": "Hornotejero",
    "E2-21": "Boquerón",
    "E2-22": "Canchales",
    "E2-24": "Villar del Rey",
    "E2-28": "Tentudía",
    "E2-32": "Villalba de los Barros",
    "E2-33": "Alcollarín",
    "E2-34": "Búrdalo",
    "E3-01": "Chanza",
    "E3-10": "Andévalo",
}

MITECO_NAME_ALIASES: dict[str, str] = {
    "E1-02": "Pto. Vallehermoso",
    "E1-08": "Vega del Jabalón",
    "E1-09": "Torre de Abrahán",
    "E2-08": "Cancho del Fresno",
    "E2-20": "Horno Tejero",
    "E2-28": "Tentudia",
}


class GuadianaCHGProvider(BaseReservoirProvider):
    """Provider backed by CH Guadiana's hydrological dashboard JSON files."""

    id = "guadiana_chg"
    name = "CH Guadiana"
    source_url = SOURCE_URL
    allowed_update_intervals_hours = [6, 12, 24]
    default_update_interval_hours = 12

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        reservoirs: dict[str, dict[str, Any]]
        try:
            detail = await self._download_json(session, DETAIL_URL)
            reservoirs = _parse_detail(detail if isinstance(detail, list) else [])
        except Exception as err:  # noqa: BLE001
            self.logger.debug("Could not load Guadiana detail list, trying highlights: %s", err)
            try:
                highlights = await self._download_json(session, HIGHLIGHTS_URL)
                reservoirs = _parse_highlights_only(highlights if isinstance(highlights, list) else [])
            except Exception as highlight_err:  # noqa: BLE001
                self.logger.debug("Could not load Guadiana highlights list: %s", highlight_err)
                reservoirs = {}
        if not reservoirs:
            reservoirs = _fallback_reservoirs()
        return dict(sorted(((key, item["name"]) for key, item in reservoirs.items()), key=lambda kv: kv[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        reservoirs = await self._load_reservoirs(session)
        wanted = set(only_keys) if only_keys else None

        out: dict[str, ReservoirData] = {}
        for key, item in reservoirs.items():
            if wanted is not None and key not in wanted:
                continue

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=item["name"],
                percent=item.get("percent"),
                volume_hm3=item.get("volume_hm3"),
                capacity_hm3=item.get("capacity_hm3"),
                record_dt=item.get("record_dt"),
                basin="Guadiana",
                source_url=SOURCE_URL,
                raw={
                    "source_name": item.get("source_name") or "CH Guadiana",
                    "data_source": item.get("data_source"),
                    "date_text": item.get("date_text"),
                },
            )

        return out

    async def _load_reservoirs(self, session) -> dict[str, dict[str, Any]]:
        try:
            detail, highlights, notices = await self._download_all(session)
            reservoirs = _parse_detail(detail)
        except Exception as err:  # noqa: BLE001
            self.logger.debug("Could not load Guadiana detail data, trying highlights fallback: %s", err)
            reservoirs = _fallback_reservoirs()
            try:
                highlights = await self._download_json(session, HIGHLIGHTS_URL)
            except Exception as highlight_err:  # noqa: BLE001
                self.logger.debug("Could not load Guadiana highlights data: %s", highlight_err)
                highlights = []
            notices = []
        _merge_highlights(reservoirs, highlights, _notice_record_dt(notices))
        try:
            miteco_features = await self._download_miteco(session)
            _merge_miteco(reservoirs, miteco_features)
        except Exception as err:  # noqa: BLE001
            self.logger.debug("Could not load Guadiana MITECO fallback data: %s", err)
        return reservoirs

    async def _download_all(self, session) -> tuple[list[Any], list[Any], list[Any]]:
        detail = await self._download_json(session, DETAIL_URL)
        if not isinstance(detail, list):
            raise ValueError("Unexpected detail JSON structure from CH Guadiana dashboard")

        try:
            highlights = await self._download_json(session, HIGHLIGHTS_URL)
        except Exception as err:  # noqa: BLE001
            self.logger.debug("Could not load Guadiana daily highlights: %s", err)
            highlights = []
        if not isinstance(highlights, list):
            highlights = []

        try:
            notices = await self._download_json(session, NOTICES_URL)
        except Exception as err:  # noqa: BLE001
            self.logger.debug("Could not load Guadiana notices: %s", err)
            notices = []
        if not isinstance(notices, list):
            notices = []
        return detail, highlights, notices

    async def _download_json(self, session, url: str) -> Any:
        async with async_timeout.timeout(60):
            resp = await session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": SOURCE_URL,
                },
            )
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _download_miteco(self, session) -> list[dict[str, Any]]:
        params = {
            "f": "json",
            "where": "UPPER(ambito_nombre) LIKE '%GUADIANA%'",
            "outFields": "EMBALSE_ID,embalse_nombre,ambito_nombre,agua_total,agua_actual,Porcentaje_Reserva,fecha,Fecha_str",
            "returnGeometry": "false",
            "resultRecordCount": "2000",
        }
        async with async_timeout.timeout(45):
            resp = await session.get(
                MITECO_SERVICE_URL,
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            resp.raise_for_status()
            payload = await resp.json(content_type=None)

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("Unexpected JSON structure from MITECO Guadiana fallback")

        out: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            attrs = feature.get("attributes")
            if isinstance(attrs, dict):
                out.append(attrs)
        return out


def _parse_detail(detail: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in detail:
        if not isinstance(item, dict):
            continue
        code = _field(item, "codigo")
        if not isinstance(code, str) or not code.startswith("E"):
            continue
        features = item.get("features")
        if not isinstance(features, list) or not features:
            continue
        latest = features[-1]
        if not isinstance(latest, dict):
            continue

        volume_hm3 = _float(latest.get("V1.01.01"))
        capacity_hm3 = _float(latest.get("V1.02.01"))
        percent = (volume_hm3 / capacity_hm3) * 100.0 if volume_hm3 is not None and capacity_hm3 else None
        record_dt = _parse_date(latest.get("H1.01.01"))
        name = _text(item.get("presa"))
        if not name:
            continue

        out[code] = {
            "name": name,
            "volume_hm3": volume_hm3,
            "capacity_hm3": capacity_hm3,
            "percent": percent,
            "record_dt": record_dt,
            "date_text": latest.get("H1.01.01"),
            "data_source": "embalses_detalle",
            "source_name": "CH Guadiana",
        }
    return out


def _merge_highlights(
    reservoirs: dict[str, dict[str, Any]], highlights: list[Any], record_dt: datetime | None
) -> None:
    for block in highlights:
        if not isinstance(block, dict) or block.get("tipo") != "EMBALSES":
            continue
        features = block.get("features")
        if not isinstance(features, list):
            continue

        for item in features:
            if not isinstance(item, dict):
                continue
            code = _field(item, "codigo")
            if not isinstance(code, str) or code not in reservoirs:
                continue

            volume_hm3 = _field_float(item, "vol [hm")
            percent = _field_float(item, "vol [%]")
            capacity_hm3 = reservoirs[code].get("capacity_hm3")
            if capacity_hm3 is None and volume_hm3 is not None and percent and percent > 0:
                capacity_hm3 = volume_hm3 / (percent / 100.0)

            reservoirs[code].update(
                {
                    "name": _text(item.get("nombre")) or reservoirs[code]["name"],
                    "volume_hm3": volume_hm3,
                    "capacity_hm3": capacity_hm3,
                    "percent": percent,
                    "record_dt": record_dt or reservoirs[code].get("record_dt"),
                    "date_text": record_dt.date().isoformat() if record_dt else reservoirs[code].get("date_text"),
                    "data_source": "tabla_destacado",
                }
            )
        return


def _parse_highlights_only(highlights: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for block in highlights:
        if not isinstance(block, dict) or block.get("tipo") != "EMBALSES":
            continue
        features = block.get("features")
        if not isinstance(features, list):
            continue
        for item in features:
            if not isinstance(item, dict):
                continue
            code = _field(item, "codigo")
            name = _text(item.get("nombre"))
            if not isinstance(code, str) or not name:
                continue
            out[code] = {"name": name}
        return out
    return out


def _merge_miteco(reservoirs: dict[str, dict[str, Any]], features: list[dict[str, Any]]) -> None:
    by_name: dict[str, dict[str, Any]] = {}
    for attrs in features:
        name = _text(attrs.get("embalse_nombre"))
        if name:
            by_name[_normalize_name(name)] = attrs

    for code, item in reservoirs.items():
        lookup_name = MITECO_NAME_ALIASES.get(code, item.get("name"))
        attrs = by_name.get(_normalize_name(lookup_name))
        if not attrs:
            continue

        record_dt = _parse_arcgis_dt(attrs.get("fecha")) or _parse_miteco_date(attrs.get("Fecha_str"))
        current_dt = item.get("record_dt")
        should_update = (
            item.get("volume_hm3") is None
            or item.get("percent") is None
            or (record_dt is not None and (current_dt is None or record_dt > current_dt))
        )
        if not should_update:
            continue

        item.update(
            {
                "volume_hm3": _float(attrs.get("agua_actual")),
                "capacity_hm3": _float(attrs.get("agua_total")),
                "percent": _float(attrs.get("Porcentaje_Reserva")),
                "record_dt": record_dt or current_dt,
                "date_text": attrs.get("Fecha_str") or item.get("date_text"),
                "data_source": "miteco_guadiana",
                "source_name": "MITECO Guadiana",
            }
        )


def _fallback_reservoirs() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "name": name,
            "data_source": "fallback_list",
            "source_name": "CH Guadiana",
        }
        for key, name in FALLBACK_RESERVOIRS.items()
    }


def _notice_record_dt(notices: list[Any]) -> datetime | None:
    for item in notices:
        if not isinstance(item, dict):
            continue
        message = _text(item.get("mensaje"))
        if not message:
            continue
        match = _NOTICE_DATE_RE.search(message)
        if match:
            return _parse_date(match.group(1))
    return None


def _parse_date(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt_util.as_utc(dt.replace(hour=8, tzinfo=dt_util.DEFAULT_TIME_ZONE))
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


def _field(item: dict[str, Any], normalized_name: str) -> Any:
    for key, value in item.items():
        if _normalize_key(key) == normalized_name:
            return value
    return None


def _field_float(item: dict[str, Any], key_prefix: str) -> float | None:
    normalized_prefix = _normalize_key(key_prefix)
    for key, value in item.items():
        if _normalize_key(key).startswith(normalized_prefix):
            return _float(value)
    return None


def _normalize_key(value: Any) -> str:
    text = str(value).casefold()
    replacements = {
        "ó": "o",
        "ò": "o",
        "á": "a",
        "é": "e",
        "í": "i",
        "ú": "u",
        "³": "3",
        "ł": "3",
        "ã³": "o",
        "â³": "3",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _normalize_name(value: Any) -> str:
    text = _normalize_key(value)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


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
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
