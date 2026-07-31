"""The timezone polygon search.

Kept apart from the rest of the package so the timezonefinder import
has exactly one home, and so both the derivation itself and the
Gregorian tables can use it without importing each other.
"""

from functools import lru_cache

from ..tz import Location


@lru_cache(maxsize=None)
def _timezone_finder():
    """Shared TimezoneFinder instance, created on first use."""
    from timezonefinder import TimezoneFinder

    return TimezoneFinder()


@lru_cache(maxsize=2048)
def location_zone_key(location: Location) -> str | None:
    """IANA key of the geographic zone covering the location, if any."""
    return _timezone_finder().timezone_at(lng=location.longitude, lat=location.latitude)
