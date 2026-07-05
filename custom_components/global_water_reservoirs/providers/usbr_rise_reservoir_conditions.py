"""USBR Reservoir Conditions provider (RISE).

Goals
- Self-maintaining reservoir list: scraped from the public Reservoir Conditions page
  which includes RISE location IDs.
- Consistent units: convert acre-feet to hm³ (same unit used by the other providers).

Important notes
- RISE endpoints are JSON:API and require: Accept: application/vnd.api+json
- Capacity is often static; we cache it per location to avoid repeated calls.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any

from aiohttp import ClientSession

from .base import BaseReservoirProvider, ReservoirData


_RESERVOIR_CONDITIONS_URL = "https://data.usbr.gov/visualizations/reservoir-conditions/"
_RISE_API_RESULT_URL = "https://data.usbr.gov/rise/api/result"
_RISE_API_LOCATION_URL = "https://data.usbr.gov/rise/api/location"

# Parameter id observed in Reclamation's public example for Reservoir Conditions (storage).
_STORAGE_PARAMETER_ID = 3

_ACCEPT_JSONAPI = {"Accept": "application/vnd.api+json"}

# Unit conversions
_ACRE_FOOT_TO_HM3 = 1233.48184 / 1_000_000  # m³ to hm³

# Limit concurrency to be gentle on the public API
_MAX_CONCURRENT_REQUESTS = 8

# Some USBR pages may return a reduced HTML payload when there's no User-Agent.
# Using a browser-like UA improves reliability of the reservoir list scraping.
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_LOCATION_LINK_RE = re.compile(r"""href=["'][^"']*/(?:rise/api/)?location/(\d+)[^"']*["']""", re.I)

# Official RISE reservoirs listed on the public Reservoir Conditions page. This
# keeps the HA selector useful if the documentation table layout changes or the
# page is temporarily unavailable.
_KNOWN_RISE_RESERVOIRS: dict[str, str] = {
    "275": "Bighorn/Yellowtail",
    "1533": "Blue Mesa",
    "281": "Boysen",
    "269": "Buffalo Bill",
    "287": "Calamus/Virginia Smith",
    "295": "Canyon Ferry",
    "288": "Carter",
    "291": "Choke Canyon",
    "294": "Clark Canyon",
    "323": "Elephant Butte",
    "1535": "Flaming Gorge",
    "334": "Folsom",
    "337": "Fresno",
    "342": "Gibson",
    "345": "Glendo",
    "353": "Green Mountain",
    "357": "Guernsey",
    "369": "Horsetooth",
    "379": "Jamestown",
    "390": "Keith Sebelius/Norton",
    "388": "Keyhole",
    "391": "Kirwin",
    "396": "Lake Elwell/Tiber Dam",
    "351": "Lake Granby",
    "3515": "Lake Havasu/Parker Dam",
    "3514": "Lake Mead/Hoover Dam",
    "3513": "Lake Mohave/Davis",
    "393": "Lake Powell",
    "475": "Lake Sherburne",
    "402": "Lake Tschida/Heart Butte",
    "408": "McGee Creek",
    "410": "McPhee",
    "413": "Millerton",
    "423": "Navajo",
    "3204": "New Melones",
    "433": "Pathfinder",
    "445": "Pueblo",
    "467": "Seminoe",
    "476": "Shadehill",
    "471": "Shasta",
    "3203": "Trinity",
    "504": "Waconda/Glen Elder",
    "509": "Whiskeytown",
}


def _html_to_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return unescape(s).strip()


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        v = value.strip().replace(",", "")
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


class USBRRISEReservoirConditionsProvider(BaseReservoirProvider):
    """Provider for the USBR Reservoir Conditions dashboard."""

    id = "usbr_rise_reservoir_conditions"
    name = "USBR Reservoir Conditions (RISE)"
    source_url = _RESERVOIR_CONDITIONS_URL

    default_update_interval_hours = 12
    allowed_update_intervals_hours = [12, 24]

    _reservoirs_cache: dict[str, str] | None = None
    _reservoirs_cache_at: datetime | None = None

    _capacity_cache: dict[str, float] = {}
    _capacity_cache_at: dict[str, datetime] = {}

    async def async_list_reservoirs(self, session: ClientSession) -> dict[str, str]:
        # Cache for a day to avoid re-scraping too often.
        if self._reservoirs_cache and self._reservoirs_cache_at:
            if datetime.now(timezone.utc) - self._reservoirs_cache_at < timedelta(hours=24):
                return dict(self._reservoirs_cache)

        try:
            html = await self._fetch_text(session, _RESERVOIR_CONDITIONS_URL)
            reservoirs = self._extract_reservoirs_from_html(html)
        except Exception:  # noqa: BLE001
            self.logger.warning(
                "USBR RISE: couldn't load Reservoir Conditions page; using bundled reservoir list."
            )
            reservoirs = dict(_KNOWN_RISE_RESERVOIRS)

        if 0 < len(reservoirs) < 10:
            self.logger.warning(
                "USBR RISE: scraped only %s reservoirs; merging bundled reservoir list.",
                len(reservoirs),
            )
            reservoirs = {**_KNOWN_RISE_RESERVOIRS, **reservoirs}

        # Fallback: keep the official RISE reservoir list if scraping breaks.
        # If you only see a tiny list in HA, it usually means the page layout
        # changed and the scraper didn't find the documentation table.
        if not reservoirs:
            self.logger.warning(
                "USBR RISE: couldn't scrape reservoir list from Reservoir Conditions page; "
                "using bundled reservoir list."
            )
            reservoirs = dict(_KNOWN_RISE_RESERVOIRS)

        if not reservoirs:
            try:
                reservoirs = await self._list_reservoirs_via_rise_api(session)
            except Exception:  # noqa: BLE001
                reservoirs = {}

        if not reservoirs:
            self.logger.warning(
                "USBR RISE: results-based listing returned no items; trying location endpoint listing."
            )
            try:
                reservoirs = await self._list_reservoirs_via_rise_locations(session)
            except Exception:  # noqa: BLE001
                reservoirs = {}

        if not reservoirs:
            self.logger.warning("USBR RISE: API-based listing returned no reservoirs; using Lake Powell fallback.")
            reservoirs = {"393": "Lake Powell"}

        if len(reservoirs) > 1:
            # Keep this at debug level to avoid spamming normal logs.
            self.logger.debug("USBR RISE: built reservoir list with %s items", len(reservoirs))

        self._reservoirs_cache = dict(reservoirs)
        self._reservoirs_cache_at = datetime.now(timezone.utc)
        return dict(reservoirs)

    async def async_fetch_reservoirs(
        self, session: ClientSession, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        reservoirs = await self.async_list_reservoirs(session)
        if only_keys:
            wanted = set(only_keys)
            keys = [k for k in reservoirs.keys() if k in wanted]
        else:
            keys = list(reservoirs.keys())

        sem = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

        async def _worker(key: str) -> ReservoirData | None:
            async with sem:
                try:
                    return await self._fetch_one(session, key, reservoirs.get(key))
                except Exception:  # noqa: BLE001
                    return None

        results = await asyncio.gather(*(_worker(k) for k in keys))
        return {rd.key: rd for rd in results if rd is not None}

    async def _fetch_one(self, session: ClientSession, location_id: str, name_hint: str | None) -> ReservoirData | None:
        storage_af, record_dt = await self._fetch_latest_storage_acre_feet(session, location_id)
        capacity_af = await self._fetch_capacity_acre_feet(session, location_id)

        volume_hm3 = storage_af * _ACRE_FOOT_TO_HM3 if storage_af is not None else None
        capacity_hm3 = capacity_af * _ACRE_FOOT_TO_HM3 if capacity_af is not None else None

        percent = None
        if storage_af is not None and capacity_af:
            try:
                percent = (storage_af / capacity_af) * 100.0
            except ZeroDivisionError:
                percent = None

        name = name_hint or await self._resolve_reservoir_name(session, location_id)
        unique_id = self.stable_unique_id(f"usbr_location_{location_id}")

        return ReservoirData(
            key=location_id,
            unique_id=unique_id,
            name=name,
            percent=percent,
            volume_hm3=volume_hm3,
            capacity_hm3=capacity_hm3,
            level_m=None,
            record_dt=record_dt,
            source_url=f"https://data.usbr.gov/location/{location_id}",
            raw={
                "location_id": location_id,
                "storage_unit": "acre-ft",
                "capacity_unit": "acre-ft",
            },
        )

    async def _fetch_text(self, session: ClientSession, url: str) -> str:
        async with session.get(url, headers=_BROWSER_HEADERS, timeout=30) as resp:
            resp.raise_for_status()
            return await resp.text()

    def _extract_reservoirs_from_html(self, html: str) -> dict[str, str]:
        reservoirs: dict[str, str] = {}

        # 1) Most common layout: HTML table rows
        rows = re.findall(r"<tr[^>]*>.*?</tr>", html, flags=re.I | re.S)
        for row in rows:
            location_ids = _LOCATION_LINK_RE.findall(row)
            if not location_ids:
                continue
            location_id = location_ids[-1]

            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.I | re.S)
            if not cells:
                continue

            name = _html_to_text(cells[0])
            name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
            if name and location_id:
                reservoirs[location_id] = name

        # 2) Alternative layout: plain anchor links (table-less / div layout)
        if not reservoirs:
            for m in re.finditer(
                r"""<a[^>]+href=["'][^"']*/(?:rise/api/)?location/(\d+)[^"']*["'][^>]*>(.*?)</a>""",
                html,
                flags=re.I | re.S,
            ):
                location_id = m.group(1)
                name = _html_to_text(m.group(2))
                name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
                name = _KNOWN_RISE_RESERVOIRS.get(location_id, name)
                if name and location_id:
                    reservoirs[location_id] = name

        # 3) SPA / embedded data fallback: try to extract from JSON-like blobs
        if not reservoirs:
            # Try a few common key patterns seen in embedded datasets.
            patterns = [
                r'"locationId"\s*:\s*"?(?P<id>\d{2,6})"?[^\{\}\[\]]{0,250}?"name"\s*:\s*"(?P<name>[^"]{3,120})"',
                r'"locationId"\s*:\s*"?(?P<id>\d{2,6})"?[^\{\}\[\]]{0,250}?"locationName"\s*:\s*"(?P<name>[^"]{3,120})"',
                r'"id"\s*:\s*"?(?P<id>\d{2,6})"?[^\{\}\[\]]{0,250}?"name"\s*:\s*"(?P<name>[^"]{3,120})"',
            ]
            for pat in patterns:
                for jm in re.finditer(pat, html, flags=re.I):
                    loc_id = jm.group("id").strip()
                    name = jm.group("name").strip()
                    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
                    if len(name) >= 3:
                        reservoirs[loc_id] = name

        if not reservoirs:
            # plain-text fallback
            for m in re.finditer(r"(?P<name>[A-Za-z0-9 .,'/\-]+?)\s+Location\s+(?P<id>\d{2,6})", html):
                name = m.group("name").strip()
                loc_id = m.group("id").strip()
                if len(name) >= 3:
                    reservoirs[loc_id] = name

        return dict(sorted(reservoirs.items(), key=lambda kv: kv[1].lower()))

    async def _resolve_reservoir_name(self, session: ClientSession, location_id: str) -> str:
        if self._reservoirs_cache and location_id in self._reservoirs_cache:
            return self._reservoirs_cache[location_id]

        try:
            payload = await self._jsonapi_get(session, f"{_RISE_API_LOCATION_URL}/{location_id}")
            data = payload.get("data") or {}
            attrs = (data.get("attributes") or {}) if isinstance(data, dict) else {}
            for key in ("name", "locationName", "location_name", "siteName", "site_name"):
                if attrs.get(key):
                    return str(attrs[key])
        except Exception:  # noqa: BLE001
            pass

        return f"Location {location_id}"

    async def _fetch_latest_storage_acre_feet(self, session: ClientSession, location_id: str) -> tuple[float | None, datetime | None]:
        now = datetime.now(timezone.utc)
        after = (now - timedelta(days=14)).date().isoformat()
        before = (now + timedelta(days=1)).date().isoformat()

        params = {
            "locationId": location_id,
            "parameterId": str(_STORAGE_PARAMETER_ID),
            "dateTime[after]": after,
            "dateTime[before]": before,
            "catalogItem.isModeled": "false",
        }

        try:
            payload = await self._jsonapi_get(session, _RISE_API_RESULT_URL, params=params)
        except Exception:  # noqa: BLE001
            return None, None

        items = payload.get("data")
        if not items:
            return None, None

        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return None, None

        best_dt: datetime | None = None
        best_val: float | None = None

        for item in items:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            if not isinstance(attrs, dict):
                continue

            dt = _parse_dt(
                attrs.get("dateTime")
                or attrs.get("datetime")
                or attrs.get("date_time")
                or attrs.get("timestamp")
            )
            val = _parse_float(
                attrs.get("value")
                or attrs.get("valueNumeric")
                or attrs.get("value_numeric")
                or attrs.get("result")
            )
            if val is None:
                val = _parse_float(attrs.get("resultValue") or attrs.get("result_value"))

            if dt is None or val is None:
                continue

            if best_dt is None or dt > best_dt:
                best_dt = dt
                best_val = val

        return best_val, best_dt

    async def _fetch_capacity_acre_feet(self, session: ClientSession, location_id: str) -> float | None:
        # Capacity is static; cache it for 30 days.
        now = datetime.now(timezone.utc)
        cached_at = self._capacity_cache_at.get(location_id)
        if cached_at and (now - cached_at) < timedelta(days=30):
            return self._capacity_cache.get(location_id)

        try:
            payload = await self._jsonapi_get(session, f"{_RISE_API_LOCATION_URL}/{location_id}")
            data = payload.get("data") or {}
            attrs = (data.get("attributes") or {}) if isinstance(data, dict) else {}
            for key in (
                "maximumCapacity",
                "maxCapacity",
                "max_capacity",
                "capacity",
                "capacityAcreFeet",
                "capacity_acre_feet",
                "maxStorage",
                "max_storage",
            ):
                cap = _parse_float(attrs.get(key))
                if cap:
                    self._capacity_cache[location_id] = cap
                    self._capacity_cache_at[location_id] = now
                    return cap
        except Exception:  # noqa: BLE001
            return None

        return None

    async def _jsonapi_get(self, session: ClientSession, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        # Some RISE endpoints may occasionally return HTML (documentation) if the
        # server doesn't honor the Accept header. When that happens, retry using
        # the documented `_format=jsonapi` parameter.
        def _with_format(p: dict[str, Any] | None) -> dict[str, Any]:
            q = dict(p or {})
            q.setdefault("_format", "jsonapi")
            return q

        for attempt in range(2):
            qparams = params if attempt == 0 else _with_format(params)
            async with session.get(url, params=qparams, headers=_ACCEPT_JSONAPI, timeout=30) as resp:
                resp.raise_for_status()
                text = await resp.text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    if attempt == 0:
                        continue
                    raise
                if isinstance(data, dict):
                    return data
                # JSON:API responses are objects; if we got something else, treat as empty.
                return {}

        return {}

    async def _list_reservoirs_via_rise_locations(self, session: ClientSession) -> dict[str, str]:
        """List reservoir-like locations using the RISE /location collection.

        RISE docs mention pagination using `itemsPerPage` and `page` parameters.
        We fetch pages until we stop getting data.
        """

        reservoirs: dict[str, str] = {}
        items_per_page = 250

        # Hard safety cap to avoid infinite loops if the API misbehaves.
        for page in range(0, 200):
            params = {"itemsPerPage": str(items_per_page), "page": str(page)}
            payload = await self._jsonapi_get(session, _RISE_API_LOCATION_URL, params=params)
            data = payload.get("data") or []
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list) or not data:
                break

            for item in data:
                if not isinstance(item, dict):
                    continue
                attrs = item.get("attributes") or {}
                if not isinstance(attrs, dict):
                    attrs = {}

                loc_id = item.get("id") or attrs.get("id") or attrs.get("locationId") or attrs.get("location_id")
                if loc_id is None:
                    continue
                loc_id = str(loc_id).strip()

                name = (
                    attrs.get("name")
                    or attrs.get("locationName")
                    or attrs.get("location_name")
                    or attrs.get("siteName")
                    or attrs.get("site_name")
                )
                if not name:
                    continue
                name = str(name).strip()

                # Heuristic filter: keep locations that look like reservoirs.
                # Many reservoir locations include a maximum/capacity field.
                cap = None
                for key in (
                    "maximumCapacity",
                    "maxCapacity",
                    "max_capacity",
                    "capacity",
                    "capacityAcreFeet",
                    "capacity_acre_feet",
                    "maxStorage",
                    "max_storage",
                ):
                    cap = _parse_float(attrs.get(key))
                    if cap and cap > 0:
                        break

                loc_type = str(
                    attrs.get("locationType")
                    or attrs.get("location_type")
                    or attrs.get("type")
                    or attrs.get("featureType")
                    or attrs.get("feature_type")
                    or ""
                ).lower()

                is_reservoir = "reservoir" in loc_type or "lake" in loc_type

                if cap or is_reservoir:
                    reservoirs[loc_id] = name

            # If the API returns fewer than itemsPerPage, we're probably done.
            if len(data) < items_per_page:
                break

        return reservoirs

    async def _list_reservoirs_via_rise_api(self, session: ClientSession) -> dict[str, str]:
        """Fallback list builder based on recent storage results.

        This is less clean than /location because results may include non-reservoir
        stations. We still try to resolve names through /location/<id>.
        """

        now = datetime.now(timezone.utc)
        after = (now - timedelta(days=2)).date().isoformat()
        before = (now + timedelta(days=1)).date().isoformat()

        location_ids: set[str] = set()

        # Pull a few pages; we just need enough unique locations.
        for page in range(0, 10):
            params = {
                "parameterId": str(_STORAGE_PARAMETER_ID),
                "dateTime[after]": after,
                "dateTime[before]": before,
                "catalogItem.isModeled": "false",
                "itemsPerPage": "250",
                "page": str(page),
            }
            payload = await self._jsonapi_get(session, _RISE_API_RESULT_URL, params=params)
            data = payload.get("data") or []
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list) or not data:
                break

            for item in data:
                if not isinstance(item, dict):
                    continue
                attrs = item.get("attributes") or {}
                if isinstance(attrs, dict):
                    loc = attrs.get("locationId") or attrs.get("location_id")
                    if loc is not None:
                        location_ids.add(str(loc).strip())

                rel = item.get("relationships") or {}
                if isinstance(rel, dict):
                    loc_rel = rel.get("location") or {}
                    if isinstance(loc_rel, dict):
                        data_ref = loc_rel.get("data")
                        if isinstance(data_ref, dict) and data_ref.get("id") is not None:
                            location_ids.add(str(data_ref["id"]).strip())

            if len(data) < 250:
                break

        if not location_ids:
            return {}

        # Resolve names, but don't explode if some lookups fail.
        sem = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

        async def _resolve(loc_id: str) -> tuple[str, str] | None:
            async with sem:
                try:
                    name = await self._resolve_reservoir_name(session, loc_id)
                    return loc_id, name
                except Exception:  # noqa: BLE001
                    return None

        resolved = await asyncio.gather(*(_resolve(lid) for lid in sorted(location_ids)))
        return {k: v for kv in resolved if kv is not None for k, v in [kv]}
