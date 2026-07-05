"""Segura basin reservoirs from Confederacion Hidrografica del Segura."""

from __future__ import annotations

from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

SOURCE_URL = "https://www.chsegura.es/es/cuenca/redes-de-control/estadisticas-hidrologicas/estado-de-embalses/"

_DATE_RE = re.compile(r"a fecha\s+([0-9]{2}/[0-9]{2}/[0-9]{4})", re.IGNORECASE)


class SeguraCHSProvider(BaseReservoirProvider):
    """Provider backed by CH Segura's daily reservoir status page."""

    id = "segura_chs"
    name = "CH Segura"
    source_url = SOURCE_URL
    allowed_update_intervals_hours = [6, 12, 24]
    default_update_interval_hours = 12

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

            out[key] = ReservoirData(
                key=key,
                unique_id=key,
                name=item["name"],
                percent=item.get("percent"),
                volume_hm3=item.get("volume_hm3"),
                capacity_hm3=item.get("capacity_hm3"),
                record_dt=item.get("record_dt"),
                basin="Segura",
                source_url=SOURCE_URL,
                raw={
                    "source_name": "CH Segura",
                    "date_text": item.get("date_text"),
                },
            )

        return out

    async def _load_reservoirs(self, session) -> dict[str, dict[str, Any]]:
        html = await self._get_text(session, SOURCE_URL)
        record_dt, date_text = _parse_record_dt(html)
        return _parse_reservoirs(html, record_dt, date_text)

    async def _get_text(self, session, url: str) -> str:
        async with async_timeout.timeout(45):
            resp = await session.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp.raise_for_status()
            return await resp.text()


def _parse_reservoirs(
    html: str, record_dt: datetime | None, date_text: str | None
) -> dict[str, dict[str, Any]]:
    parser = _ReservoirTableParser()
    parser.feed(html)

    out: dict[str, dict[str, Any]] = {}
    for row in parser.rows:
        if len(row) < 4:
            continue
        name = _clean_text(row[0])
        if not name or name.casefold().startswith("resto de embalses"):
            continue
        capacity_hm3 = _float(row[1])
        volume_hm3 = _float(row[2])
        percent = _float(row[3])

        key = _slug(name)
        out[key] = {
            "name": name,
            "capacity_hm3": capacity_hm3,
            "volume_hm3": volume_hm3,
            "percent": percent,
            "record_dt": record_dt,
            "date_text": date_text,
        }
    return out


class _ReservoirTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_target_table = False
        self._table_depth = 0
        self._in_body = False
        self._row: list[str] | None = None
        self._in_cell = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "n0":
            self._in_target_table = True
            self._table_depth = 1
            return

        if not self._in_target_table:
            return

        if tag == "table":
            self._table_depth += 1
        elif tag == "tbody":
            self._in_body = True
        elif tag == "tr" and self._in_body:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._in_cell = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_target_table:
            return

        if tag in {"td", "th"} and self._in_cell and self._row is not None:
            self._row.append(_clean_text("".join(self._buffer)))
            self._in_cell = False
            return

        if tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            return

        if tag == "tbody":
            self._in_body = False
            return

        if tag == "table":
            self._table_depth -= 1
            if self._table_depth <= 0:
                self._in_target_table = False


def _parse_record_dt(html: str) -> tuple[datetime | None, str | None]:
    match = _DATE_RE.search(_clean_text(html))
    if not match:
        return None, None
    date_text = match.group(1)
    try:
        dt = datetime.strptime(date_text, "%d/%m/%Y")
    except ValueError:
        return None, date_text
    return dt_util.as_utc(dt.replace(hour=8, tzinfo=dt_util.DEFAULT_TIME_ZONE)), date_text


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(value))
    return " ".join(text.replace("\xa0", " ").split())


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _slug(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "reservoir"
