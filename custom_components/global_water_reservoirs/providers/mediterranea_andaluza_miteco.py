"""Cuenca Mediterranea Andaluza reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class MediterraneaAndaluzaMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to CMA."""

    id = "mediterranea_andaluza_miteco"
    name = "MITECO Mediterránea Andaluza"
    where = "UPPER(ambito_nombre) LIKE '%MEDITERR%'"
    basin_name = "Cuenca Mediterránea Andaluza"
    source_name = "MITECO Cuenca Mediterránea Andaluza"
    name_fixes = {
        "Vińuela, La": "La Viñuela",
    }
