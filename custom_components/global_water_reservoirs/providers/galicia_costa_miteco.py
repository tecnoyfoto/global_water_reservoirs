"""Galicia Costa reservoirs from MITECO reservoir map layer."""

from __future__ import annotations

from .miteco_basin import MitecoBasinProvider


class GaliciaCostaMitecoProvider(MitecoBasinProvider):
    """Provider backed by MITECO's reservoir map layer, filtered to Galicia Costa."""

    id = "galicia_costa_miteco"
    name = "MITECO Galicia Costa"
    where = "UPPER(ambito_nombre) = 'GALICIA COSTA'"
    basin_name = "Galicia Costa"
    source_name = "MITECO Galicia Costa"
    name_fixes = {
        "Barrie de la Maza": "Barrié de la Maza",
        "Forcadas, As": "As Forcadas",
        "Ribeira, A": "A Ribeira",
        "Sta Uxia": "Santa Uxía",
    }
