"""Tinto, Odiel y Piedras reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class TintoOdielPiedrasMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to TOP."""

    id = "tinto_odiel_piedras_miteco"
    name = "MITECO Tinto-Odiel-Piedras"
    where = "UPPER(ambito_nombre) LIKE '%TINTO%' OR UPPER(ambito_nombre) LIKE '%ODIEL%' OR UPPER(ambito_nombre) LIKE '%PIEDRAS%'"
    basin_name = "Tinto, Odiel y Piedras"
    source_name = "MITECO Tinto, Odiel y Piedras"
