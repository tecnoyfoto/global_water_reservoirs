"""Ebro basin reservoirs from SAIH Ebro."""

from __future__ import annotations

import asyncio
import re
import ssl
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import async_timeout
from aiohttp import ClientConnectorCertificateError, ClientError

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://home.saihebro.com"
SERVER_CONFIG_URL = f"{BASE_URL}/api/common/getServerConfig"
MAP_DATA_URL = f"{BASE_URL}/api/mapa/getDatosMapa"
DAILY_VOLUMES_URL = f"{BASE_URL}/api/principal/getVolumenesEmbalsados"
STATIONS_URL = f"{BASE_URL}/api/datos-graficas/getEstaciones"
SIGNALS_URL = f"{BASE_URL}/api/datos-graficas/getSenalesConfig"
CURRENT_VALUES_URL = f"{BASE_URL}/api/ficha/procesarTablaValoresActuales"

MAP_SLUG = "mapa-embalses-HG-toda-la-cuenca"
FALLBACK_MAP_SLUGS = (
    MAP_SLUG,
    "mapa-embalses-H1-alto-ebro-mi",
    "mapa-embalses-H2-semi-alta-miranda",
    "mapa-embalses-H3-aragon-irati",
    "mapa-embalses-H4-medio-ebro-mi",
    "mapa-embalses-H5-gallego",
    "mapa-embalses-H6-bajo-cinca",
    "mapa-embalses-H7-segre",
    "mapa-embalses-H8-bajo-ebro",
    "mapa-embalses-H9-guadalope-martin",
    "mapa-embalses-H10-bajo-jalon",
    "mapa-embalses-H11-semi-alta-logrono",
    "mapa-embalses-H12-arga",
    "mapa-embalses-H13-nogueras",
    "mapa-embalses-H15-alto-ebro-md",
    "mapa-embalses-H16-alto-aragon",
    "mapa-embalses-H17-alto-cinca",
    "mapa-embalses-H18-esera",
    "mapa-embalses-H19-huerva-aguas-vivas",
    "mapa-embalses-H20-alto-jalon",
    "mapa-embalses-H21-medio-ebro-md",
)

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 15
DISCOVERY_CONCURRENCY = 4
CATALOG_TTL_SECONDS = 24 * 60 * 60
DIRECT_DISCOVERY_MAX_AGE = timedelta(days=7)
RESERVOIR_SIGNAL_TYPES = {"NEMBA", "VEMBA", "PORCE"}
FNMT_INTERMEDIATE_CA = (
    Path(__file__).parent / "certs" / "fnmt_ac_componentes_informaticos.pem"
)


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """Return a verified TLS context with SAIH Ebro's omitted intermediate CA."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=FNMT_INTERMEDIATE_CA)
    return context


class EbroSAIHProvider(BaseReservoirProvider):
    """Provide the complete public SAIH Ebro reservoir catalogue."""

    id = "ebro_saih"
    name = "SAIH Ebro"
    source_url = f"{BASE_URL}/tiempo-real/estacion-embalses-E001-ebro"
    allowed_update_intervals_hours = [1, 2, 6, 12, 24]
    default_update_interval_hours = 2

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__()
        self._hass = hass
        self._catalog: dict[str, str] = {}
        self._key_sources: dict[str, tuple[str, str]] = {}
        self._catalog_loaded_at: float | None = None

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        """Return every reservoir with usable public SAIH Ebro data."""
        await self._discover(session)
        return dict(sorted(self._catalog.items(), key=lambda item: item[1].lower()))

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        """Fetch selected reservoirs without reloading the complete catalogue."""
        wanted = set(only_keys) if only_keys else None

        if not self._catalog_is_fresh():
            discovered = await self._discover(session)
            return _filter_reservoirs(discovered, wanted)

        selected = wanted or set(self._catalog)
        unknown = selected.difference(self._key_sources)
        if unknown:
            discovered = await self._discover(session, force=True)
            return _filter_reservoirs(discovered, wanted)

        map_slugs = {
            source_id
            for key, (source_type, source_id) in self._key_sources.items()
            if key in selected and source_type == "map"
        }
        daily_keys = {
            key
            for key, (source_type, _source_id) in self._key_sources.items()
            if key in selected and source_type == "daily"
        }
        direct_keys = {
            key
            for key, (source_type, _source_id) in self._key_sources.items()
            if key in selected and source_type == "direct"
        }

        ssl_context = await self._hass.async_add_executor_job(_ssl_context)
        out: dict[str, ReservoirData] = {}

        if map_slugs:
            map_payloads = await self._download_maps(
                session, sorted(map_slugs), ssl_context
            )
            for slug, payload in map_payloads:
                for reservoir in _parse_map_payload(payload, slug).values():
                    if reservoir.key in selected and reservoir.key not in out:
                        out[reservoir.key] = reservoir

        if daily_keys:
            payload = await self._request_json(
                session, DAILY_VOLUMES_URL, ssl_context=ssl_context
            )
            daily = _parse_daily_payload(payload)
            for key in daily_keys:
                if key in daily:
                    out[key] = daily[key]

        if direct_keys:
            direct = await self._download_direct_reservoirs(
                session,
                {key: self._catalog[key] for key in direct_keys},
                ssl_context,
            )
            out.update(direct)

        return out

    def _catalog_is_fresh(self) -> bool:
        return (
            self._catalog_loaded_at is not None
            and time.monotonic() - self._catalog_loaded_at < CATALOG_TTL_SECONDS
        )

    async def _discover(
        self, session, *, force: bool = False
    ) -> dict[str, ReservoirData]:
        if self._catalog_is_fresh() and not force:
            return {}

        ssl_context = await self._hass.async_add_executor_job(_ssl_context)
        map_slugs = await self._download_map_slugs(session, ssl_context)
        map_payloads = await self._download_maps(session, map_slugs, ssl_context)

        reservoirs: dict[str, ReservoirData] = {}
        key_sources: dict[str, tuple[str, str]] = {}

        # The general map comes first. Keeping the first occurrence preserves
        # the existing names and IDs while regional maps add the missing dams.
        for slug, payload in map_payloads:
            for key, reservoir in _parse_map_payload(payload, slug).items():
                if key not in reservoirs:
                    reservoirs[key] = reservoir
                    key_sources[key] = ("map", slug)

        daily_payload = await self._request_json(
            session, DAILY_VOLUMES_URL, ssl_context=ssl_context
        )
        for key, reservoir in _parse_daily_payload(daily_payload).items():
            if key not in reservoirs:
                reservoirs[key] = reservoir
                key_sources[key] = ("daily", key)

        direct_candidates = await self._find_direct_only_candidates(
            session, set(reservoirs), ssl_context
        )
        direct_reservoirs = await self._download_direct_reservoirs(
            session, direct_candidates, ssl_context
        )
        now = datetime.now(timezone.utc)
        for key, reservoir in direct_reservoirs.items():
            if reservoir.record_dt is None:
                continue
            if now - reservoir.record_dt > DIRECT_DISCOVERY_MAX_AGE:
                self.logger.debug(
                    "Ignoring stale SAIH Ebro station %s last updated at %s",
                    key,
                    reservoir.record_dt,
                )
                continue
            reservoirs[key] = reservoir
            key_sources[key] = ("direct", key)

        self._catalog = {key: item.name for key, item in reservoirs.items()}
        self._key_sources = key_sources
        self._catalog_loaded_at = time.monotonic()
        self.logger.debug(
            "Discovered %s usable SAIH Ebro reservoirs", len(self._catalog)
        )
        return reservoirs

    async def _download_map_slugs(
        self, session, ssl_context: ssl.SSLContext
    ) -> list[str]:
        try:
            payload = await self._request_json(
                session, SERVER_CONFIG_URL, ssl_context=ssl_context
            )
            cache = (
                payload.get("CACHE_SLUG_MAPAS")
                if isinstance(payload, dict)
                else None
            )
            entries = cache.get("embalses") if isinstance(cache, dict) else None
            slugs = []
            if isinstance(entries, list):
                for entry in entries:
                    slug = str(entry).split("|", 1)[-1].strip()
                    if slug and slug not in slugs:
                        slugs.append(slug)
            if not slugs:
                raise ValueError("No reservoir maps in SAIH Ebro configuration")
            return slugs
        except ClientConnectorCertificateError:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            self.logger.warning(
                "Could not discover SAIH Ebro maps (%s: %s); using known map list",
                type(err).__name__,
                err,
            )
            return list(FALLBACK_MAP_SLUGS)

    async def _download_maps(
        self,
        session,
        slugs: list[str],
        ssl_context: ssl.SSLContext,
    ) -> list[tuple[str, Any]]:
        semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)

        async def _worker(slug: str) -> tuple[str, Any]:
            async with semaphore:
                payload = await self._request_json(
                    session,
                    MAP_DATA_URL,
                    params={"slug": slug},
                    ssl_context=ssl_context,
                )
                return slug, payload

        return list(await asyncio.gather(*(_worker(slug) for slug in slugs)))

    async def _find_direct_only_candidates(
        self,
        session,
        known_keys: set[str],
        ssl_context: ssl.SSLContext,
    ) -> dict[str, str]:
        stations_payload = await self._request_json(
            session,
            STATIONS_URL,
            params={"tipoConsolidado": "quinceminutal", "tiposSenal": ""},
            ssl_context=ssl_context,
        )
        station_names = _parse_reservoir_stations(stations_payload)
        station_ids = sorted(station_names)
        if not station_ids:
            return {}

        signals_payload = await self._request_json(
            session,
            SIGNALS_URL,
            params={
                "tipoConsolidado": "quinceminutal",
                "estaciones": ",".join(station_ids),
            },
            ssl_context=ssl_context,
        )
        signal_stations = _parse_reservoir_signal_stations(signals_payload)
        return {
            key: name
            for key, name in station_names.items()
            if key not in known_keys and key in signal_stations
        }

    async def _download_direct_reservoirs(
        self,
        session,
        stations: dict[str, str],
        ssl_context: ssl.SSLContext,
    ) -> dict[str, ReservoirData]:
        semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)

        async def _worker(key: str, name: str) -> ReservoirData | None:
            async with semaphore:
                payload = await self._request_json(
                    session,
                    CURRENT_VALUES_URL,
                    params={"estacion": key},
                    ssl_context=ssl_context,
                )
                return _parse_direct_payload(key, name, payload)

        results = await asyncio.gather(
            *(_worker(key, name) for key, name in stations.items())
        )
        return {item.key: item for item in results if item is not None}

    async def _request_json(
        self,
        session,
        url: str,
        *,
        ssl_context: ssl.SSLContext,
        params: dict[str, str] | None = None,
    ) -> Any:
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                async with async_timeout.timeout(DOWNLOAD_TIMEOUT_SECONDS):
                    async with session.get(
                        url,
                        params=params,
                        headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json",
                        },
                        ssl=ssl_context,
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.json(content_type=None)
            except ClientConnectorCertificateError:
                raise
            except (ClientError, TimeoutError, ValueError) as err:
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise
                self.logger.warning(
                    "SAIH Ebro request failed on attempt %s/%s (%s: %s); retrying",
                    attempt,
                    DOWNLOAD_ATTEMPTS,
                    type(err).__name__,
                    err,
                )
                await asyncio.sleep(attempt)

        raise RuntimeError("SAIH Ebro request failed")


def _filter_reservoirs(
    reservoirs: dict[str, ReservoirData], wanted: set[str] | None
) -> dict[str, ReservoirData]:
    if wanted is None:
        return reservoirs
    return {key: item for key, item in reservoirs.items() if key in wanted}


def _parse_map_payload(payload: Any, slug: str) -> dict[str, ReservoirData]:
    data = payload.get("DATOS") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("Unexpected map JSON structure from SAIH Ebro")

    out: dict[str, ReservoirData] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        if str(item.get("TIPO_ESTACION_SLUG") or "").lower() != "embalses":
            continue
        key = _station_key(item)
        name = _station_name(item)
        if not key or not name:
            continue

        tags = item.get("TAGS") if isinstance(item.get("TAGS"), list) else []
        level_m = _find_tag_value(tags, "NEMBA")
        volume_hm3 = _find_tag_value(tags, "VEMBA")
        percent = _find_tag_value(tags, "PORCE")
        capacity_hm3 = _capacity(volume_hm3, percent)
        station_slug = str(item.get("LR_NOMBRE_CORTO_SLUG") or "").strip()

        out[key] = ReservoirData(
            key=key,
            unique_id=key.lower(),
            name=name,
            percent=percent,
            volume_hm3=volume_hm3,
            capacity_hm3=capacity_hm3,
            level_m=level_m,
            record_dt=_latest_record_dt(tags)
            or _parse_local_dt(item.get("ULTIMA_FECHA")),
            basin="Ebro",
            source_url=_station_url(key, station_slug or name),
            raw={
                "station": key,
                "map_slug": slug,
                "source_type": "regional_map",
                "source_name": item.get("LR_NOMBRE_CORTO"),
                "tags": tags,
            },
        )
    return out


def _parse_daily_payload(payload: Any) -> dict[str, ReservoirData]:
    volumes = payload.get("volumenes") if isinstance(payload, dict) else None
    if not isinstance(volumes, dict):
        raise ValueError("Unexpected daily JSON structure from SAIH Ebro")

    out: dict[str, ReservoirData] = {}
    for key, item in volumes.items():
        if not re.fullmatch(r"E\d{3}", str(key)) or not isinstance(item, dict):
            continue
        name_value = item.get("zona")
        if not name_value:
            continue
        values = item.get("data")
        current = values[1] if isinstance(values, list) and len(values) > 1 else None
        if not isinstance(current, dict):
            continue

        volume_hm3 = _parse_float(current.get("volumen"))
        percent = _parse_float(current.get("y"))
        if volume_hm3 is None and percent is None:
            continue
        name = _title_name(_strip_reservoir_prefix(str(name_value).strip()))
        out[str(key)] = ReservoirData(
            key=str(key),
            unique_id=str(key).lower(),
            name=name,
            percent=percent,
            volume_hm3=volume_hm3,
            capacity_hm3=_capacity(volume_hm3, percent),
            record_dt=_parse_daily_dt(item.get("fechaAnsi") or item.get("fecha")),
            basin="Ebro",
            source_url=_station_url(str(key), name),
            raw={
                "station": str(key),
                "source_type": "daily_volumes",
                "daily": item,
            },
        )
    return out


def _parse_reservoir_stations(payload: Any) -> dict[str, str]:
    if not isinstance(payload, list):
        raise ValueError("Unexpected station catalogue from SAIH Ebro")

    out: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        if not re.fullmatch(r"E\d{3}", key):
            continue
        label = text.split(" - ", 1)[-1].strip()
        if not label.lower().startswith("embalse"):
            continue
        name = _strip_reservoir_prefix(label)
        out[key] = _title_name(name or label)
    return out


def _parse_reservoir_signal_stations(payload: Any) -> set[str]:
    if not isinstance(payload, list):
        raise ValueError("Unexpected signal catalogue from SAIH Ebro")

    out: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        signal_type = str(data.get("LS_TIPO_SENAL") or "").upper()
        station = str(data.get("LS_REMOTA_TXT") or "").strip()
        if (
            signal_type in RESERVOIR_SIGNAL_TYPES
            and re.fullmatch(r"E\d{3}", station)
        ):
            out.add(station)
    return out


def _parse_direct_payload(
    key: str, name: str, payload: Any
) -> ReservoirData | None:
    html = payload.get("VALORES_ACTUALES") if isinstance(payload, dict) else None
    if not isinstance(html, str):
        raise ValueError("Unexpected current-values response from SAIH Ebro")

    values: dict[str, float] = {}
    dates: list[datetime] = []
    for row in re.findall(r"<tr\b.*?</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        signal_match = re.search(
            r"grafica-senal-[^'\"]*?(NEMBA|VEMBA|PORCE)",
            row,
            flags=re.IGNORECASE,
        )
        value_match = re.search(
            r"aria-label=['\"]Valor\s+([^'\"]+)", row, flags=re.IGNORECASE
        )
        if signal_match is None or value_match is None:
            continue
        number_match = re.search(r"[-+]?\d[\d.,]*", value_match.group(1))
        value = _parse_float(number_match.group(0) if number_match else None)
        if value is None:
            continue
        values[signal_match.group(1).upper()] = value

        date_match = re.search(
            r"aria-label=['\"]Fecha\s+([^'\"]+)", row, flags=re.IGNORECASE
        )
        if date_match is not None:
            record_dt = _parse_local_dt(date_match.group(1).strip())
            if record_dt is not None:
                dates.append(record_dt)

    if not values:
        return None

    level_m = values.get("NEMBA")
    volume_hm3 = values.get("VEMBA")
    percent = values.get("PORCE")
    return ReservoirData(
        key=key,
        unique_id=key.lower(),
        name=name,
        percent=percent,
        volume_hm3=volume_hm3,
        capacity_hm3=_capacity(volume_hm3, percent),
        level_m=level_m,
        record_dt=max(dates) if dates else None,
        basin="Ebro",
        source_url=_station_url(key, name),
        raw={
            "station": key,
            "source_type": "station_current_values",
            "signals": sorted(values),
        },
    )


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
    for index, word in enumerate(name.lower().split()):
        words.append(word if index > 0 and word in small_words else word.capitalize())
    return " ".join(words)


def _strip_reservoir_prefix(name: str) -> str:
    return re.sub(
        r"^embalse(?:\s+(?:de las|de los|de la|del|de|la|el))?\s+",
        "",
        name,
        flags=re.IGNORECASE,
    )


def _station_url(key: str, name_or_slug: str) -> str:
    slug = _slugify(name_or_slug)
    return f"{BASE_URL}/tiempo-real/estacion-embalses-{key}-{slug}"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_tag_value(tags: list[Any], signal_type: str) -> float | None:
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if str(tag.get("LS_TIPO_SENAL") or "").upper() == signal_type:
            return _parse_float(
                tag.get("VALOR") or tag.get("VALOR_QM") or tag.get("LS_VALOR_QM")
            )
    return None


def _capacity(volume_hm3: float | None, percent: float | None) -> float | None:
    if volume_hm3 is None or percent is None or percent <= 0:
        return None
    return volume_hm3 / (percent / 100.0)


def _latest_record_dt(tags: list[Any]) -> datetime | None:
    dates = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        parsed = _parse_local_dt(tag.get("ULTIMA_FECHA"))
        if parsed is not None:
            dates.append(parsed)
    return max(dates) if dates else None


def _parse_daily_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return _as_utc(parsed)
        except ValueError:
            continue
    return _parse_local_dt(value)


def _parse_local_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    parsed = dt_util.parse_datetime(text)
    if parsed is None:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(value)
