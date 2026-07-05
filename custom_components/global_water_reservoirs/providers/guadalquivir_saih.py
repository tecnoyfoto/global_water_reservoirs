"""Guadalquivir basin reservoirs from SAIH Guadalquivir."""

from __future__ import annotations

from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://www.chguadalquivir.es/saih"
SOURCE_URL = f"{BASE_URL}/EmbalMapa.aspx"
RESGUARDO_URL = f"{BASE_URL}/ResguardoEmbalses.aspx"
PAGES = ("EmbalGR.aspx", "EmbalCO.aspx", "EmbalJA.aspx", "EmbalSE.aspx")

_UPDATED_RE = re.compile(r"Actualizados:\s*([0-9]{2}/[0-9]{2}/[0-9]{4}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})")
_TABLE_RE = re.compile(r"<table[^>]+id=\"[^\"]*_(E\d+)_tabla\"[\s\S]*?</table>", re.IGNORECASE)
_CAPTION_RE = re.compile(r"<caption[^>]*>([\s\S]*?)</caption>", re.IGNORECASE)
_ROW_RE = re.compile(r"<tr[\s\S]*?</tr>", re.IGNORECASE)


class GuadalquivirSAIHProvider(BaseReservoirProvider):
    """Provider backed by SAIH Guadalquivir current reservoir pages."""

    id = "guadalquivir_saih"
    name = "SAIH Guadalquivir"
    source_url = SOURCE_URL
    allowed_update_intervals_hours = [1, 2, 6, 12, 24]
    default_update_interval_hours = 2

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        reservoirs = await self._load_reservoirs(session)
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

            volume_hm3 = item.get("volume_hm3")
            capacity_hm3 = item.get("capacity_hm3")
            percent = item.get("percent")
            if percent is None and volume_hm3 is not None and capacity_hm3:
                percent = (volume_hm3 / capacity_hm3) * 100.0

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=item["name"],
                percent=percent,
                volume_hm3=volume_hm3,
                capacity_hm3=capacity_hm3,
                level_m=item.get("level_m"),
                record_dt=item.get("record_dt"),
                basin="Guadalquivir",
                source_url=item.get("source_url") or SOURCE_URL,
                raw={
                    "station": key,
                    "page": item.get("page"),
                    "outflow_m3_s": item.get("outflow_m3_s"),
                    "source_name": "SAIH Guadalquivir",
                },
            )

        return out

    async def _load_reservoirs(self, session) -> dict[str, dict[str, Any]]:
        pages = await self._load_current_pages(session)
        resguardo = await self._load_resguardo(session)

        reservoirs: dict[str, dict[str, Any]] = {}
        for page, html in pages.items():
            record_dt = _parse_updated(html)
            for code, item in _parse_current_page(html).items():
                item["page"] = page
                item["record_dt"] = record_dt
                item["source_url"] = f"{BASE_URL}/{page}"
                if code in resguardo:
                    item.update({k: v for k, v in resguardo[code].items() if k != "name" and v is not None})
                reservoirs[code] = item

        for code, item in resguardo.items():
            reservoirs.setdefault(
                code,
                {
                    **item,
                    "page": "ResguardoEmbalses.aspx",
                    "source_url": RESGUARDO_URL,
                    "record_dt": item.get("record_dt"),
                },
            )
        return reservoirs

    async def _load_current_pages(self, session) -> dict[str, str]:
        out: dict[str, str] = {}
        for page in PAGES:
            out[page] = await self._get_text(session, f"{BASE_URL}/{page}")
        return out

    async def _load_resguardo(self, session) -> dict[str, dict[str, Any]]:
        html = await self._get_text(session, RESGUARDO_URL)
        return _parse_resguardo(html, _parse_updated(html))

    async def _get_text(self, session, url: str) -> str:
        async with async_timeout.timeout(45):
            resp = await session.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp.raise_for_status()
            return await resp.text()


def _parse_current_page(html: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for table_match in _TABLE_RE.finditer(html):
        code = table_match.group(1)
        table = table_match.group(0)
        caption_match = _CAPTION_RE.search(table)
        if not caption_match:
            continue
        name = _clean_text(caption_match.group(1))
        if name.startswith(code):
            name = name[len(code) :].strip()

        item: dict[str, Any] = {"name": _expand_name(name)}
        for row in _ROW_RE.findall(table):
            text = _clean_text(row)
            if "Volumen" in text:
                item["volume_hm3"] = _first_float(text)
            elif "Caudal" in text:
                item["outflow_m3_s"] = _first_float(text)
        out[code] = item
    return out


def _parse_resguardo(html: str, record_dt: datetime | None) -> dict[str, dict[str, Any]]:
    parser = _TableParser()
    parser.feed(html)

    out: dict[str, dict[str, Any]] = {}
    for row in parser.rows:
        if len(row) < 5:
            continue
        match = re.match(r"^(E\d+)\s+(.+)$", row[0])
        if not match:
            continue
        code = match.group(1)
        out[code] = {
            "name": _expand_name(match.group(2)),
            "capacity_hm3": _float(row[1]),
            "level_m": _float(row[2]),
            "volume_hm3": _float(row[3]),
            "percent": _float(row[4]),
            "record_dt": record_dt,
        }
    return out


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._in_cell = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"}:
            self._in_cell = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            self._row.append(_clean_text("".join(self._buffer)))
            self._in_cell = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)


def _parse_updated(html: str) -> datetime | None:
    match = _UPDATED_RE.search(html)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None
    return dt_util.as_utc(dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(value))
    return " ".join(text.replace("ł", "3").split())


def _first_float(value: str) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", value)
    return _float(match.group(0)) if match else None


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


def _expand_name(name: str) -> str:
    replacements = {
        "Fco. Abellán": "Francisco Abellán",
        "Puebla de Cazalla": "La Puebla de Cazalla",
        "Melonares": "Los Melonares",
        "Torre del Águila": "La Torre del Águila",
        "Gergal": "El Gergal",
        "Contraemb. Bermejales": "Contraembalse Bermejales",
    }
    return replacements.get(name, name)
