"""DataUpdateCoordinator for Global Water Reservoirs."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .providers.base import BaseReservoirProvider, ReservoirData


class GlobalWaterReservoirsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ReservoirData]]):
    """Coordinator that fetches & normalizes reservoirs from a provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        provider: BaseReservoirProvider,
        selected_reservoir_keys: list[str],
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=provider.logger,
            name=f"{provider.name}",
            update_interval=update_interval,
        )
        self._session = session
        self.provider = provider
        self.selected_reservoir_keys = selected_reservoir_keys

    async def _async_update_data(self) -> dict[str, ReservoirData]:
        try:
            data = await self.provider.async_fetch_reservoirs(
                session=self._session,
                only_keys=self.selected_reservoir_keys or None,
            )
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err
        return data
