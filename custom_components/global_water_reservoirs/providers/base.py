"""Provider base classes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import hashlib
import logging


@dataclass(slots=True)
class ReservoirData:
    """Normalized reservoir data."""

    key: str  # provider-scoped key, used as dict key
    unique_id: str  # stable id for HA unique_id / device ids
    name: str

    percent: float | None = None
    volume_hm3: float | None = None
    capacity_hm3: float | None = None
    level_m: float | None = None
    record_dt: datetime | None = None  # timezone-aware datetime

    basin: str | None = None
    province: str | None = None
    source_url: str | None = None

    raw: dict[str, Any] | None = None


class BaseReservoirProvider:
    """Base class for reservoir providers."""

    id: str
    name: str
    allowed_update_intervals_hours: list[int]
    default_update_interval_hours: int
    source_url: str | None = None

    logger: logging.Logger

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"custom_components.global_water_reservoirs.{self.id}")

    async def async_list_reservoirs(self, session) -> dict[str, str]:
        """Return {key: name} list for config flow selection."""
        raise NotImplementedError

    async def async_fetch_reservoirs(
        self, session, only_keys: list[str] | None = None
    ) -> dict[str, ReservoirData]:
        """Fetch & normalize reservoirs, optionally filtering by keys."""
        raise NotImplementedError

    @staticmethod
    def stable_unique_id(seed: str, *, prefix: str = "") -> str:
        digest = hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
        if prefix:
            return f"{prefix}-{digest}"
        return digest
