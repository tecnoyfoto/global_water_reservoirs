"""Cuenca del Duero reservoirs from CHD open data portal."""

from __future__ import annotations

import asyncio
import ssl
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import async_timeout
from aiohttp import ClientConnectorCertificateError, ClientError

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

# Public JSON distribution (CKAN resource download)
DATA_URL = (
    "https://datos.chduero.es/dataset/f2eebe21-10eb-4b04-bf5b-71578dc3562c/"
    "resource/9b642c38-59b8-4ab0-8abd-6580ed64d261/download/estado_embalses.json"
)
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 30
FNMT_INTERMEDIATE_CA = (
    Path(__file__).parent / "certs" / "fnmt_ac_componentes_informaticos.pem"
)


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """Return a verified TLS context with the valid FNMT intermediate CA."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=FNMT_INTERMEDIATE_CA)
    return context


class DueroCHDProvider(BaseReservoirProvider):
    id = "duero_chd"
    name = "Cuenca del Duero"
    source_url = DATA_URL
    allowed_update_intervals_hours = [6, 12, 24]
    default_update_interval_hours = 12

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__()
        self._hass = hass

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
        ssl_context = await self._hass.async_add_executor_job(_ssl_context)

        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                async with async_timeout.timeout(DOWNLOAD_TIMEOUT_SECONDS):
                    async with session.get(
                        DATA_URL,
                        headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json",
                        },
                        ssl=ssl_context,
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json(content_type=None)

                # Most CKAN resources are arrays; tolerate dict-wrapped payloads.
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    # Common patterns: {"result": [...]}, {"data": [...]}
                    for key in ("result", "data", "records"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
                raise ValueError("Unexpected JSON structure from CHD")
            except ClientConnectorCertificateError:
                raise
            except (ClientError, TimeoutError, ValueError) as err:
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise
                self.logger.warning(
                    "CHD request failed on attempt %s/%s (%s: %s); retrying",
                    attempt,
                    DOWNLOAD_ATTEMPTS,
                    type(err).__name__,
                    err,
                )
                await asyncio.sleep(attempt)

        raise RuntimeError("CHD request retry loop exited unexpectedly")


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    text = str(v).strip()
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
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
