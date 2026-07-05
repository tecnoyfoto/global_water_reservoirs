"""Guadalete-Barbate reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class GuadaleteBarbateMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to Guadalete-Barbate."""

    id = "guadalete_barbate_miteco"
    name = "MITECO Guadalete-Barbate"
    where = "UPPER(ambito_nombre) LIKE '%GUADALETE%' OR UPPER(ambito_nombre) LIKE '%BARBATE%'"
    basin_name = "Guadalete-Barbate"
    source_name = "MITECO Guadalete-Barbate"
    name_fixes = {
        "Hurones, Los": "Los Hurones",
    }
