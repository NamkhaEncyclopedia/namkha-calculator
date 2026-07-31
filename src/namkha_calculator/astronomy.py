"""Deprecated: astronomy.py has been split into three modules.

Kept only so this commit moves code without touching any caller. The pieces
now live in tz (bundled data and value types), localization (attaching a
timezone to a naive time), and zone_derivation (choosing which timezone
applied). Import from those directly; this module goes away next.
"""

from .localization import (
    is_ambiguous_local_time,
    is_longitude_based_timezone,
    is_nonexistent_local_time,
    resolve_local_time,
    shift_past_clock_gap,
    uses_local_mean_time,
)
from .tz import (
    HIGH_LATITUDE_DAY_START_HOUR,
    LATITUDE_LIMIT,
    Location,
    TimezoneDerivation,
    _mean_solar_timezone,
    _parse_iso6709,
    _parse_zone_tab,
    _zone_tab_rows,
    fixed_offset,
    zone,
    zone_country,
)
from .zone_derivation import (
    OFFSET_AHEAD_SOLAR_LIMIT_HOURS,
    OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    TZDB_CERTAIN_SINCE,
    UTC_OFFSET_MAX_HOURS,
    UTC_OFFSET_MIN_HOURS,
    location_timezone,
    location_zone_key,
    offset_solar_gap_hours,
    standard_offset_hours,
    validate_timezone_for_location,
)

__all__ = [
    "HIGH_LATITUDE_DAY_START_HOUR",
    "LATITUDE_LIMIT",
    "OFFSET_AHEAD_SOLAR_LIMIT_HOURS",
    "OFFSET_BEHIND_SOLAR_LIMIT_HOURS",
    "TZDB_CERTAIN_SINCE",
    "UTC_OFFSET_MAX_HOURS",
    "UTC_OFFSET_MIN_HOURS",
    "Location",
    "TimezoneDerivation",
    "_mean_solar_timezone",
    "_parse_iso6709",
    "_parse_zone_tab",
    "_zone_tab_rows",
    "fixed_offset",
    "is_ambiguous_local_time",
    "is_longitude_based_timezone",
    "is_nonexistent_local_time",
    "location_timezone",
    "location_zone_key",
    "offset_solar_gap_hours",
    "resolve_local_time",
    "shift_past_clock_gap",
    "standard_offset_hours",
    "uses_local_mean_time",
    "validate_timezone_for_location",
    "zone",
    "zone_country",
]
