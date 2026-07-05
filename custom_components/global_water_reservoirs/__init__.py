"""Global Water Reservoirs integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_COUNTRY,
    CONF_PROVIDER,
    CONF_RESERVOIRS,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    COUNTRY_ES,
    COUNTRY_US,
    LOCALIZED_COUNTRY_LABELS,
    LOCALIZED_PROVIDER_LABELS,
    PLATFORMS,
    PROVIDER_CANTABRICO,
    PROVIDER_CATALONIA,
    PROVIDER_DUERO,
    PROVIDER_EBRO,
    PROVIDER_GALICIA_COSTA,
    PROVIDER_GUADALETE_BARBATE,
    PROVIDER_GUADIANA,
    PROVIDER_GUADALQUIVIR,
    PROVIDER_JUCAR,
    PROVIDER_MEDITERRANEA_ANDALUZA,
    PROVIDER_MINO_SIL,
    PROVIDER_MITECO,
    PROVIDER_PAIS_VASCO_INTERNAS,
    PROVIDER_SEGURA,
    PROVIDER_TAJO,
    PROVIDER_TINTO_ODIEL_PIEDRAS,
    PROVIDER_USBR_RISE,
    SUPPORTED_COUNTRIES,
    SUPPORTED_PROVIDERS_BY_COUNTRY,
)
from .coordinator import GlobalWaterReservoirsDataUpdateCoordinator
from .providers.cantabrico_miteco import CantabricoMitecoProvider
from .providers.catalonia_transparencia import CatalunyaTransparenciaProvider
from .providers.duero_chd import DueroCHDProvider
from .providers.ebro_saih import EbroSAIHProvider
from .providers.galicia_costa_miteco import GaliciaCostaMitecoProvider
from .providers.guadalete_barbate_miteco import GuadaleteBarbateMitecoProvider
from .providers.guadiana_chg import GuadianaCHGProvider
from .providers.guadalquivir_saih import GuadalquivirSAIHProvider
from .providers.jucar_saih import JucarSAIHProvider
from .providers.mediterranea_andaluza_miteco import MediterraneaAndaluzaMitecoProvider
from .providers.mino_sil_miteco import MinoSilMitecoProvider
from .providers.miteco_boletin import MitecoBoletinProvider
from .providers.pais_vasco_internas_miteco import PaisVascoInternasMitecoProvider
from .providers.segura_chs import SeguraCHSProvider
from .providers.tajo_saih import TajoSAIHProvider
from .providers.tinto_odiel_piedras_miteco import TintoOdielPiedrasMitecoProvider
from .providers.usbr_rise_reservoir_conditions import USBRRISEReservoirConditionsProvider


def _get_provider(country_id: str, provider_id: str):
    if country_id == COUNTRY_ES:
        if provider_id == PROVIDER_CANTABRICO:
            return CantabricoMitecoProvider()
        if provider_id == PROVIDER_CATALONIA:
            return CatalunyaTransparenciaProvider()
        if provider_id == PROVIDER_DUERO:
            return DueroCHDProvider()
        if provider_id == PROVIDER_EBRO:
            return EbroSAIHProvider()
        if provider_id == PROVIDER_GALICIA_COSTA:
            return GaliciaCostaMitecoProvider()
        if provider_id == PROVIDER_GUADALETE_BARBATE:
            return GuadaleteBarbateMitecoProvider()
        if provider_id == PROVIDER_GUADIANA:
            return GuadianaCHGProvider()
        if provider_id == PROVIDER_GUADALQUIVIR:
            return GuadalquivirSAIHProvider()
        if provider_id == PROVIDER_JUCAR:
            return JucarSAIHProvider()
        if provider_id == PROVIDER_MEDITERRANEA_ANDALUZA:
            return MediterraneaAndaluzaMitecoProvider()
        if provider_id == PROVIDER_MINO_SIL:
            return MinoSilMitecoProvider()
        if provider_id == PROVIDER_MITECO:
            return MitecoBoletinProvider()
        if provider_id == PROVIDER_PAIS_VASCO_INTERNAS:
            return PaisVascoInternasMitecoProvider()
        if provider_id == PROVIDER_SEGURA:
            return SeguraCHSProvider()
        if provider_id == PROVIDER_TAJO:
            return TajoSAIHProvider()
        if provider_id == PROVIDER_TINTO_ODIEL_PIEDRAS:
            return TintoOdielPiedrasMitecoProvider()

    if country_id == COUNTRY_US:
        if provider_id == PROVIDER_USBR_RISE:
            return USBRRISEReservoirConditionsProvider()

    raise ValueError(f"Unsupported provider: {country_id}:{provider_id}")


def _get_selected_reservoirs(entry: ConfigEntry) -> list[str]:
    reservoirs = entry.options.get(CONF_RESERVOIRS)
    if reservoirs is None:
        reservoirs = entry.data.get(CONF_RESERVOIRS, [])
    return list(reservoirs)


def _get_update_interval_hours(entry: ConfigEntry) -> int:
    hours = entry.options.get(CONF_UPDATE_INTERVAL_HOURS)
    if hours is None:
        hours = entry.data.get(CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS)
    try:
        return int(hours)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL_HOURS


def _lang_code(hass: HomeAssistant) -> str:
    lang = getattr(hass.config, "language", None) or "en"
    return lang.split("-")[0].lower()


def _entry_title(hass: HomeAssistant, country_id: str, provider_id: str) -> str:
    lang = _lang_code(hass)
    country = LOCALIZED_COUNTRY_LABELS.get(lang, {}).get(
        country_id, SUPPORTED_COUNTRIES.get(country_id, country_id)
    )
    provider = (
        LOCALIZED_PROVIDER_LABELS.get(lang, {})
        .get(country_id, {})
        .get(provider_id, SUPPORTED_PROVIDERS_BY_COUNTRY.get(country_id, {}).get(provider_id, provider_id))
    )
    return f"{country} - {provider}"


def _repair_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Repair old entry metadata created by early development builds."""
    country_id = entry.data.get(CONF_COUNTRY)
    provider_id = entry.data.get(CONF_PROVIDER)

    data = dict(entry.data)
    options = dict(entry.options)
    changed = False

    # Early fallback mislabeled location 1533 as Lake Powell. The official RISE
    # location for Lake Powell is 393; 1533 is Blue Mesa.
    if country_id == COUNTRY_US and provider_id == PROVIDER_USBR_RISE:
        if data.get(CONF_RESERVOIRS) == ["1533"] and CONF_RESERVOIRS not in options:
            data[CONF_RESERVOIRS] = ["393"]
            changed = True
        if options.get(CONF_RESERVOIRS) == ["1533"]:
            options[CONF_RESERVOIRS] = ["393"]
            changed = True

    title = _entry_title(hass, country_id, provider_id)
    if entry.title != title:
        changed = True

    if changed:
        hass.config_entries.async_update_entry(entry, title=title, data=data, options=options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Global Water Reservoirs from a config entry."""

    country_id = entry.data.get(CONF_COUNTRY)
    provider_id = entry.data.get(CONF_PROVIDER)

    _repair_config_entry(hass, entry)

    provider = _get_provider(country_id, provider_id)

    session = aiohttp_client.async_get_clientsession(hass)

    coordinator = GlobalWaterReservoirsDataUpdateCoordinator(
        hass=hass,
        session=session,
        provider=provider,
        selected_reservoir_keys=_get_selected_reservoirs(entry),
        update_interval=timedelta(hours=_get_update_interval_hours(entry)),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "provider": provider,
        "country": country_id,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
