"""Deprecated: moved to zone_derivation.historical_borders.

Kept only so this commit moves code without touching any caller; it goes away
next.
"""

from .zone_derivation.historical_borders import (
    SNAPSHOT_YEARS,
    _parse_snapshot,
    _point_in_ring,
    _snapshot_features,
    nearest_snapshot_year,
    polity_index,
    polity_name,
    snapshots_around,
)

__all__ = [
    "SNAPSHOT_YEARS",
    "_parse_snapshot",
    "_point_in_ring",
    "_snapshot_features",
    "nearest_snapshot_year",
    "polity_index",
    "polity_name",
    "snapshots_around",
]
