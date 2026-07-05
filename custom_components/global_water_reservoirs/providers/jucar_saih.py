"""Jucar basin reservoirs from SAIH Jucar."""

from __future__ import annotations

from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

import async_timeout

from homeassistant.util import dt as dt_util

from .base import BaseReservoirProvider, ReservoirData

BASE_URL = "https://saih.chj.es"
SOURCE_URL = f"{BASE_URL}/embalses"


class JucarSAIHProvider(BaseReservoirProvider):
    """Provider backed by SAIH Jucar's current reservoir table."""

    id = "jucar_saih"
    name = "SAIH Júcar"
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

            out[key] = ReservoirData(
                key=key,
                unique_id=key.lower(),
                name=item["name"],
                percent=item.get("percent"),
                volume_hm3=item.get("volume_hm3"),
                capacity_hm3=item.get("capacity_hm3"),
                level_m=item.get("level_m"),
                record_dt=item.get("record_dt"),
                basin=item.get("basin") or "Júcar",
                source_url=item.get("source_url") or SOURCE_URL,
                raw={
                    "station": key,
                    "source_name": "SAIH Júcar",
                    "inflow_m3_s": item.get("inflow_m3_s"),
                    "outflow_m3_s": item.get("outflow_m3_s"),
                    "spillway_level_m": item.get("spillway_level_m"),
                },
            )

        return out

    async def _load_reservoirs(self, session) -> dict[str, dict[str, Any]]:
        html = await self._get_text(session, SOURCE_URL)
        return _parse_reservoirs(html)

    async def _get_text(self, session, url: str) -> str:
        async with async_timeout.timeout(45):
            resp = await session.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp.raise_for_status()
            return await resp.text()


def _parse_reservoirs(html: str) -> dict[str, dict[str, Any]]:
    parser = _ReservoirTableParser()
    parser.feed(html)

    out: dict[str, dict[str, Any]] = {}
    for row in parser.rows:
        cells = row["cells"]
        if len(cells) < 9 or cells[0].upper() == "EMBALSE":
            continue

        key = _key_from_links(row["links"]) or _slug(cells[0])
        source_url = f"{BASE_URL}/embalses/{key}" if key.isdigit() else SOURCE_URL
        out[key] = {
            "name": _clean_name(cells[0]),
            "volume_hm3": _float(cells[1]),
            "record_dt": _parse_record_dt(cells[2]),
            "capacity_hm3": _float(cells[3]),
            "level_m": _float(cells[4]),
            "spillway_level_m": _float(cells[5]),
            "inflow_m3_s": _float(cells[6]),
            "outflow_m3_s": _float(cells[7]),
            "percent": _float(cells[8]),
            "basin": row.get("section"),
            "source_url": source_url,
        }
    return out


class _ReservoirTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self._in_desktop = False
        self._desktop_depth = 0
        self._section: str | None = None
        self._row_classes = ""
        self._row: list[str] | None = None
        self._links: list[str] = []
        self._in_cell = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag == "div" and attrs_dict.get("id") == "contenidoDesktop":
            self._in_desktop = True
            self._desktop_depth = 1
            return

        if not self._in_desktop:
            return

        if tag == "div":
            self._desktop_depth += 1
        elif tag == "tr":
            self._row_classes = attrs_dict.get("class", "")
            self._row = []
            self._links = []
        elif tag in {"td", "th"} and self._row is not None:
            self._in_cell = True
            self._buffer = []
        elif tag == "a" and self._row is not None:
            href = attrs_dict.get("href")
            if href:
                self._links.append(href)

    def handle_data(self, data: str) -> None:
        if self._in_desktop and self._in_cell:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_desktop:
            return

        if tag in {"td", "th"} and self._in_cell and self._row is not None:
            self._row.append(_clean_text("".join(self._buffer)))
            self._in_cell = False
            return

        if tag == "tr" and self._row is not None:
            if "table-section" in self._row_classes:
                self._section = self._row[0] if self._row else None
            elif "table-summary" not in self._row_classes and self._row:
                self.rows.append({"section": self._section, "cells": self._row, "links": list(self._links)})
            self._row = None
            self._links = []
            self._row_classes = ""
            return

        if tag == "div":
            self._desktop_depth -= 1
            if self._desktop_depth <= 0:
                self._in_desktop = False


def _key_from_links(links: list[str]) -> str | None:
    for link in links:
        match = re.search(r"/embalses/(\d+)(?:$|[/?#])", link)
        if match:
            return match.group(1)
    return None


def _parse_record_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(value.strip(), "%d-%m-%Y %H:%M")
    except ValueError:
        return None
    return dt_util.as_utc(dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))


def _clean_name(value: str) -> str:
    text = _clean_text(value)
    for prefix in ("EMBALSE DE ", "EMBALSE DEL ", "EMBALSE "):
        if text.upper().startswith(prefix):
            text = text[len(prefix) :]
            break
    return _title_name(text)


def _title_name(name: str) -> str:
    small_words = {"de", "del", "la", "las", "los", "el", "y"}
    words = []
    for idx, word in enumerate(name.lower().split()):
        if idx > 0 and word in small_words:
            words.append(word)
        elif word.startswith("l'") and len(word) > 2:
            words.append("L'" + word[2:].capitalize())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(".", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _slug(value: str) -> str:
    text = _clean_name(value).casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "reservoir"
