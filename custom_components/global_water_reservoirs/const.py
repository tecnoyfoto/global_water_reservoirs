"""Constants for Global Water Reservoirs."""

from __future__ import annotations

DOMAIN = "global_water_reservoirs"

CONF_COUNTRY = "country"
CONF_PROVIDER = "provider"
CONF_RESERVOIRS = "reservoirs"
CONF_UPDATE_INTERVAL_HOURS = "update_interval_hours"

DEFAULT_UPDATE_INTERVAL_HOURS = 12

# Country ids (ISO-ish)
COUNTRY_ES = "ES"
COUNTRY_US = "US"

# Provider ids (scoped per country)
PROVIDER_CANTABRICO = "cantabrico_miteco"
PROVIDER_CATALONIA = "catalonia_transparencia"
PROVIDER_DUERO = "duero_chd"
PROVIDER_EBRO = "ebro_saih"
PROVIDER_GALICIA_COSTA = "galicia_costa_miteco"
PROVIDER_GUADALETE_BARBATE = "guadalete_barbate_miteco"
PROVIDER_GUADIANA = "guadiana_chg"
PROVIDER_GUADALQUIVIR = "guadalquivir_saih"
PROVIDER_JUCAR = "jucar_saih"
PROVIDER_MEDITERRANEA_ANDALUZA = "mediterranea_andaluza_miteco"
PROVIDER_MINO_SIL = "mino_sil_miteco"
PROVIDER_MITECO = "miteco_boletin"
PROVIDER_PAIS_VASCO_INTERNAS = "pais_vasco_internas_miteco"
PROVIDER_SEGURA = "segura_chs"
PROVIDER_TAJO = "tajo_saih"
PROVIDER_TINTO_ODIEL_PIEDRAS = "tinto_odiel_piedras_miteco"
PROVIDER_USBR_RISE = "usbr_rise_reservoir_conditions"

# Base (English) labels (used when no localization is available)
SUPPORTED_COUNTRIES: dict[str, str] = {
    COUNTRY_ES: "Spain",
    COUNTRY_US: "United States",
}

# Localized labels for dropdowns (base language is English, with full Spanish/Catalan labels).
LOCALIZED_COUNTRY_LABELS: dict[str, dict[str, str]] = {
    "en": {
        COUNTRY_ES: "Spain",
        COUNTRY_US: "United States",
    },
    "es": {
        COUNTRY_ES: "España",
        COUNTRY_US: "Estados Unidos",
    },
    "ca": {
        COUNTRY_ES: "Espanya",
        COUNTRY_US: "Estats Units",
    },
}

LOCALIZED_PROVIDER_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        COUNTRY_ES: {
            PROVIDER_CANTABRICO: "Cantabrian Basin",
            PROVIDER_CATALONIA: "Catalunya",
            PROVIDER_DUERO: "Duero Basin",
            PROVIDER_EBRO: "Ebro Basin",
            PROVIDER_GALICIA_COSTA: "Galicia Costa",
            PROVIDER_GUADALETE_BARBATE: "Guadalete-Barbate Basin",
            PROVIDER_GUADIANA: "Guadiana Basin",
            PROVIDER_GUADALQUIVIR: "Guadalquivir Basin",
            PROVIDER_JUCAR: "Júcar Basin",
            PROVIDER_MEDITERRANEA_ANDALUZA: "Mediterranean Andalusian Basin",
            PROVIDER_MINO_SIL: "Miño-Sil Basin",
            PROVIDER_MITECO: "Spain fallback (MITECO weekly)",
            PROVIDER_PAIS_VASCO_INTERNAS: "Internal Basque Basins",
            PROVIDER_SEGURA: "Segura Basin",
            PROVIDER_TAJO: "Tajo Basin",
            PROVIDER_TINTO_ODIEL_PIEDRAS: "Tinto-Odiel-Piedras Basin",
        },
        COUNTRY_US: {
            PROVIDER_USBR_RISE: "USBR / RISE",
        },
    },
    "es": {
        COUNTRY_ES: {
            PROVIDER_CANTABRICO: "Cuenca del Cantábrico",
            PROVIDER_CATALONIA: "Cataluña",
            PROVIDER_DUERO: "Cuenca del Duero",
            PROVIDER_EBRO: "Cuenca del Ebro",
            PROVIDER_GALICIA_COSTA: "Galicia Costa",
            PROVIDER_GUADALETE_BARBATE: "Cuenca Guadalete-Barbate",
            PROVIDER_GUADIANA: "Cuenca del Guadiana",
            PROVIDER_GUADALQUIVIR: "Cuenca del Guadalquivir",
            PROVIDER_JUCAR: "Cuenca del Júcar",
            PROVIDER_MEDITERRANEA_ANDALUZA: "Cuenca Mediterránea Andaluza",
            PROVIDER_MINO_SIL: "Cuenca del Miño-Sil",
            PROVIDER_MITECO: "España respaldo (MITECO semanal)",
            PROVIDER_PAIS_VASCO_INTERNAS: "Cuencas Internas del País Vasco",
            PROVIDER_SEGURA: "Cuenca del Segura",
            PROVIDER_TAJO: "Cuenca del Tajo",
            PROVIDER_TINTO_ODIEL_PIEDRAS: "Cuenca Tinto, Odiel y Piedras",
        },
        COUNTRY_US: {
            PROVIDER_USBR_RISE: "USBR / RISE",
        },
    },
    "ca": {
        COUNTRY_ES: {
            PROVIDER_CANTABRICO: "Conca del Cantàbric",
            PROVIDER_CATALONIA: "Catalunya",
            PROVIDER_DUERO: "Conca del Duero",
            PROVIDER_EBRO: "Conca de l'Ebre",
            PROVIDER_GALICIA_COSTA: "Galicia Costa",
            PROVIDER_GUADALETE_BARBATE: "Conca Guadalete-Barbate",
            PROVIDER_GUADIANA: "Conca del Guadiana",
            PROVIDER_GUADALQUIVIR: "Conca del Guadalquivir",
            PROVIDER_JUCAR: "Conca del Xúquer",
            PROVIDER_MEDITERRANEA_ANDALUZA: "Conca Mediterrània Andalusa",
            PROVIDER_MINO_SIL: "Conca del Miño-Sil",
            PROVIDER_MITECO: "Espanya reserva (MITECO setmanal)",
            PROVIDER_PAIS_VASCO_INTERNAS: "Conques internes del País Basc",
            PROVIDER_SEGURA: "Conca del Segura",
            PROVIDER_TAJO: "Conca del Tajo",
            PROVIDER_TINTO_ODIEL_PIEDRAS: "Conca Tinto, Odiel i Piedras",
        },
        COUNTRY_US: {
            PROVIDER_USBR_RISE: "USBR / RISE",
        },
    },
}

SUPPORTED_PROVIDERS_BY_COUNTRY: dict[str, dict[str, str]] = {
    COUNTRY_ES: {
        PROVIDER_CANTABRICO: "Cantabrian Basin",
        PROVIDER_CATALONIA: "Catalunya",
        PROVIDER_DUERO: "Duero Basin",
        PROVIDER_EBRO: "Ebro Basin",
        PROVIDER_GALICIA_COSTA: "Galicia Costa",
        PROVIDER_GUADALETE_BARBATE: "Guadalete-Barbate Basin",
        PROVIDER_GUADIANA: "Guadiana Basin",
        PROVIDER_GUADALQUIVIR: "Guadalquivir Basin",
        PROVIDER_JUCAR: "Júcar Basin",
        PROVIDER_MEDITERRANEA_ANDALUZA: "Mediterranean Andalusian Basin",
        PROVIDER_MINO_SIL: "Miño-Sil Basin",
        PROVIDER_PAIS_VASCO_INTERNAS: "Internal Basque Basins",
        PROVIDER_SEGURA: "Segura Basin",
        PROVIDER_TAJO: "Tajo Basin",
        PROVIDER_TINTO_ODIEL_PIEDRAS: "Tinto-Odiel-Piedras Basin",
        PROVIDER_MITECO: "Spain fallback (MITECO weekly)",
    },
    COUNTRY_US: {
        PROVIDER_USBR_RISE: "USBR / RISE",
    },
}

PLATFORMS = ["sensor"]

