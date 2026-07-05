"""Config flow for Global Water Reservoirs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY as HA_CONF_COUNTRY
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import _get_provider
from .const import (
    CONF_COUNTRY,
    CONF_PROVIDER,
    CONF_RESERVOIRS,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    LOCALIZED_COUNTRY_LABELS,
    LOCALIZED_PROVIDER_LABELS,
    SUPPORTED_COUNTRIES,
    SUPPORTED_PROVIDERS_BY_COUNTRY,
)


def _lang_code(hass) -> str:
    """Return Home Assistant UI language as a short code (e.g. 'es', 'en')."""
    lang = getattr(hass.config, "language", None) or "en"
    return lang.split("-")[0].lower()


def _country_label(hass, country_id: str) -> str:
    lang = _lang_code(hass)
    return LOCALIZED_COUNTRY_LABELS.get(lang, {}).get(country_id, SUPPORTED_COUNTRIES.get(country_id, country_id))


def _provider_label(hass, country_id: str, provider_id: str) -> str:
    lang = _lang_code(hass)
    return (
        LOCALIZED_PROVIDER_LABELS.get(lang, {})
        .get(country_id, {})
        .get(provider_id, SUPPORTED_PROVIDERS_BY_COUNTRY.get(country_id, {}).get(provider_id, provider_id))
    )


def _entry_title(hass, country_id: str, provider_id: str) -> str:
    return f"{_country_label(hass, country_id)} - {_provider_label(hass, country_id, provider_id)}"


def _get_current_reservoirs(entry: config_entries.ConfigEntry) -> list[str]:
    reservoirs = entry.options.get(CONF_RESERVOIRS)
    if reservoirs is None:
        reservoirs = entry.data.get(CONF_RESERVOIRS, [])
    return list(reservoirs)


def _get_current_update_interval(entry: config_entries.ConfigEntry) -> Any:
    return entry.options.get(
        CONF_UPDATE_INTERVAL_HOURS,
        entry.data.get(CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS),
    )


class GlobalWaterReservoirsConfigFlow(config_entries.ConfigFlow, domain="global_water_reservoirs"):
    """Handle a config flow for Global Water Reservoirs."""

    VERSION = 1

    def __init__(self) -> None:
        self._country_id: str | None = None
        self._provider_id: str | None = None
        self._reservoirs_index: dict[str, str] | None = None
        self._existing_entry: config_entries.ConfigEntry | None = None

    def _find_existing_entry(self) -> config_entries.ConfigEntry | None:
        assert self._country_id is not None
        assert self._provider_id is not None
        unique_id = f"{self._country_id}:{self._provider_id}"

        for entry in self._async_current_entries():
            if entry.unique_id == unique_id:
                return entry
            if (
                entry.domain == DOMAIN
                and entry.data.get(CONF_COUNTRY) == self._country_id
                and entry.data.get(CONF_PROVIDER) == self._provider_id
            ):
                return entry
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._country_id = user_input[CONF_COUNTRY]
            return await self.async_step_provider()

        # Build localized country dropdown
        options = [
            SelectOptionDict(value=cid, label=_country_label(self.hass, cid))
            for cid in SUPPORTED_COUNTRIES.keys()
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_provider(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        assert self._country_id is not None

        providers = SUPPORTED_PROVIDERS_BY_COUNTRY.get(self._country_id, {})
        if not providers:
            return self.async_abort(reason="no_providers")

        if user_input is not None:
            self._provider_id = user_input[CONF_PROVIDER]
            await self.async_set_unique_id(f"{self._country_id}:{self._provider_id}")
            self._existing_entry = self._find_existing_entry()
            return await self.async_step_reservoirs()

        options = [
            SelectOptionDict(value=pid, label=_provider_label(self.hass, self._country_id, pid))
            for pid in providers.keys()
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_PROVIDER): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="provider", data_schema=schema, errors=errors)

    async def async_step_reservoirs(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        assert self._country_id is not None
        assert self._provider_id is not None

        provider = _get_provider(self._country_id, self._provider_id)
        allowed_intervals = getattr(provider, "allowed_update_intervals_hours", [DEFAULT_UPDATE_INTERVAL_HOURS])

        session = aiohttp_client.async_get_clientsession(self.hass)

        if self._reservoirs_index is None:
            try:
                self._reservoirs_index = await provider.async_list_reservoirs(session)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
                self._reservoirs_index = {}

        if user_input is not None and not errors:
            selected = list(user_input.get(CONF_RESERVOIRS, []))
            if not selected:
                errors["base"] = "no_reservoirs_selected"

            try:
                update_hours = int(user_input.get(CONF_UPDATE_INTERVAL_HOURS, provider.default_update_interval_hours))
            except (TypeError, ValueError):
                update_hours = provider.default_update_interval_hours
            if update_hours not in allowed_intervals:
                update_hours = provider.default_update_interval_hours

            if not errors:
                title = _entry_title(self.hass, self._country_id, self._provider_id)
                if self._existing_entry:
                    options = {
                        **self._existing_entry.options,
                        CONF_RESERVOIRS: selected,
                        CONF_UPDATE_INTERVAL_HOURS: update_hours,
                    }
                    self.hass.config_entries.async_update_entry(
                        self._existing_entry,
                        title=title,
                        options=options,
                    )
                    await self.hass.config_entries.async_reload(self._existing_entry.entry_id)
                    return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_COUNTRY: self._country_id,
                        CONF_PROVIDER: self._provider_id,
                        CONF_RESERVOIRS: selected,
                        CONF_UPDATE_INTERVAL_HOURS: update_hours,
                    },
                )

        reservoirs_dict = self._reservoirs_index or {}
        current_selected: list[str] = []
        current_update = provider.default_update_interval_hours

        if self._existing_entry:
            current_selected = _get_current_reservoirs(self._existing_entry)
            current_update = _get_current_update_interval(self._existing_entry)
            if reservoirs_dict:
                current_selected = [key for key in current_selected if key in reservoirs_dict]

            try:
                current_update = int(current_update)
            except (TypeError, ValueError):
                current_update = provider.default_update_interval_hours
            if current_update not in allowed_intervals:
                current_update = provider.default_update_interval_hours

        schema = vol.Schema(
            {
                vol.Required(CONF_RESERVOIRS, default=current_selected): cv.multi_select(reservoirs_dict),
                vol.Required(
                    CONF_UPDATE_INTERVAL_HOURS,
                    default=current_update,
                ): vol.In(allowed_intervals),
            }
        )
        return self.async_show_form(step_id="reservoirs", data_schema=schema, errors=errors)

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GlobalWaterReservoirsOptionsFlowHandler(config_entry)


class GlobalWaterReservoirsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Global Water Reservoirs."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Home Assistant instantiates OptionsFlow with a config entry, but the
        # base class may reserve config_entry. We keep our own reference.
        self._config_entry = config_entry
        self._reservoirs_index: dict[str, str] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        country_id = self._config_entry.data.get(CONF_COUNTRY)
        provider_id = self._config_entry.data.get(CONF_PROVIDER)
        provider = _get_provider(country_id, provider_id)

        allowed_intervals = getattr(provider, "allowed_update_intervals_hours", [DEFAULT_UPDATE_INTERVAL_HOURS])

        session = aiohttp_client.async_get_clientsession(self.hass)
        if self._reservoirs_index is None:
            try:
                self._reservoirs_index = await provider.async_list_reservoirs(session)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
                self._reservoirs_index = {}

        if user_input is not None and not errors:
            selected = list(user_input.get(CONF_RESERVOIRS, []))
            if not selected:
                errors["base"] = "no_reservoirs_selected"

            try:
                update_hours = int(user_input.get(CONF_UPDATE_INTERVAL_HOURS, provider.default_update_interval_hours))
            except (TypeError, ValueError):
                update_hours = provider.default_update_interval_hours
            if update_hours not in allowed_intervals:
                update_hours = provider.default_update_interval_hours

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_RESERVOIRS: selected,
                        CONF_UPDATE_INTERVAL_HOURS: update_hours,
                    },
                )

        current_selected = list(
            self._config_entry.options.get(
                CONF_RESERVOIRS, self._config_entry.data.get(CONF_RESERVOIRS, [])
            )
        )
        current_update = self._config_entry.options.get(
            CONF_UPDATE_INTERVAL_HOURS,
            self._config_entry.data.get(CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS),
        )

        reservoirs_dict = self._reservoirs_index or {}

        if reservoirs_dict:
            current_selected = [k for k in current_selected if k in reservoirs_dict]
        else:
            current_selected = []

        try:
            current_update = int(current_update)
        except (TypeError, ValueError):
            current_update = provider.default_update_interval_hours

        schema = vol.Schema(
            {
                vol.Required(CONF_RESERVOIRS, default=current_selected): cv.multi_select(reservoirs_dict),
                vol.Required(CONF_UPDATE_INTERVAL_HOURS, default=current_update): vol.In(allowed_intervals),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
