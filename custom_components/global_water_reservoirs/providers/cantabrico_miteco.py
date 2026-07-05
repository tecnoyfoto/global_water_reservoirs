"""Cantabrian basin reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class CantabricoMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to Cantabrico."""

    id = "cantabrico_miteco"
    name = "MITECO Cantábrico"
    where = "UPPER(ambito_nombre) LIKE '%CANT%'"
    basin_name = "Cantábrico"
    source_name = "MITECO Cantábrico"
    include_basin_in_list_name = True
    use_feature_basin = True
    name_fixes = {
        "Ańarbe": "Añarbe",
        "Barca, La": "La Barca",
        "Cohilla, La": "La Cohilla",
    }
