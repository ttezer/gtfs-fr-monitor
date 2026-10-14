"""Normalization of the licence codes published by transport.data.gouv.fr (data-model §7).

Codes seen (2026-10-13): "lov2" (Licence Ouverte 2.0), "odc-odbl", "fr-lo", "mobility-licence",
"notspecified". Only the first two have an SPDX identifier; the others stay unmapped.
"""

from __future__ import annotations

_KNOWN = {
    "lov2": "etalab-2.0",
    "odc-odbl": "ODbL-1.0",
}


def normalize_license(raw: str | None) -> str | None:
    """Map a raw value to a license id, or None when it is unknown or ambiguous."""
    if not isinstance(raw, str):
        return None
    return _KNOWN.get(" ".join(raw.split()))
