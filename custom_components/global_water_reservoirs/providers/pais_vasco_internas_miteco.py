"""Internal Basque Country reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class PaisVascoInternasMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to internal Basque basins."""

    id = "pais_vasco_internas_miteco"
    name = "MITECO País Vasco"
    where = "UPPER(ambito_nombre) LIKE '%VASCO%'"
    basin_name = "Cuencas Internas del País Vasco"
    source_name = "MITECO Cuencas Internas del País Vasco"
