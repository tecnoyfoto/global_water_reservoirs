"""Miño-Sil basin reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class MinoSilMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to Miño-Sil."""

    id = "mino_sil_miteco"
    name = "MITECO Miño-Sil"
    where = "UPPER(ambito_nombre) LIKE '%MIÑO%' OR UPPER(ambito_nombre) LIKE '%MINO%' OR UPPER(ambito_nombre) LIKE '%SIL%'"
    basin_name = "Miño - Sil"
    source_name = "MITECO Miño-Sil"
    name_fixes = {
        "Campañana, La": "La Campañana",
        "Conchas, Las": "Las Conchas",
        "Peares, Os": "Os Peares",
        "Portas, Las": "Las Portas",
        "Rozas, Las": "Las Rozas",
        "San. Estevo": "San Estevo",
    }
