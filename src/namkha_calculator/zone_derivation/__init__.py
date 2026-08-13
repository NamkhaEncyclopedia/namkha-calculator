"""Choosing which timezone applied at a place and date.

This is the expensive half of the timezone work: the polygon search, the
historical border maps, and the checks that a timezone someone supplied is
plausible for the location. It runs once, when the birth details are entered.

resolve_timezone is the way in. It returns a ResolvedTimezone whatever the
source: it records a zone or an offset the user chose, and calls
location_timezone to work one out only when the user chose neither.

The calculation path stays clear of this package. No module outside it may
import it, directly or through a chain of imports, and
tests/test_localization_policy.py checks that.
"""

import datetime as dt
import math
from collections.abc import Iterable
from functools import lru_cache
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..localization import (
    _choose_repeated_hour,
    is_ambiguous_local_time,
    is_longitude_based_timezone,
)
from ..tz import (
    LATITUDE_LIMIT,
    Location,
    ResolvedTimezone,
    TimezoneDerivation,
    TimezoneProvenance,
    _mean_solar_timezone,
    _parse_iso6709,
    _zone_tab_rows,
    fixed_offset,
    zone,
)
from ..tz.errors import TimezoneLocationMismatchError, TimezoneOffsetOutOfRangeError
from .gregorian import gregorian_adoption_date
from .historical_borders import (
    nearest_snapshot_year,
    polity_index,
    snapshots_around,
)
from .lookup import location_zone_key

__all__ = [
    "resolve_timezone",
    "gregorian_adoption_date",
    "location_timezone",
    "location_zone_key",
    "offset_solar_gap_hours",
    "standard_offset_hours",
    "validate_timezone_for_location",
]

# Allowed signed gap between a birth's standard-time clock offset and its
# longitude's mean solar time. Historical time zones stay within (-1.8, +3.1) h
# (behind: Danmarkshavn 1916-80; ahead: far-west Xinjiang on Beijing time); a
# larger gap means the offset and location don't match (a data-entry error).
# The behind bound is tighter because a clock behind the sun pulls dawn toward
# clock midnight; the residual dawnless-date case this can still produce at
# 56-60 deg latitude raises in calendar.day_start. DST is excluded from the gap
# (it only ever moves clocks ahead - the safe direction).
OFFSET_BEHIND_SOLAR_LIMIT_HOURS = -2.5
OFFSET_AHEAD_SOLAR_LIMIT_HOURS = 3.5

# Widest UTC offsets in tzdb history, date-side extremes included: a zone that
# counted dates across the Date Line carries a solar offset shifted by a whole
# day (Manila -15:56 = +8:04 - 24 h; Metlakatla +15:14 = -8:46 + 24 h). A fixed
# offset outside this range is a data-entry error; without this bound the mod-24
# gap would wrap and let a day-off offset (e.g. +22 for -2) pass the solar check
# as a near-zero gap. Only a fixed offset is checked against this bound (see
# Subject.__post_init__), never a named zone.
UTC_OFFSET_MIN_HOURS = -16
UTC_OFFSET_MAX_HOURS = 16

# tzdb guarantees a zone's history for its whole region only from 1970 on;
# earlier data describes the zone's reference city, so a coordinate-derived
# zone is an estimate for a pre-1970 birth.
TZDB_CERTAIN_SINCE = dt.date(1970, 1, 1)


class _ReferenceCity(NamedTuple):
    latitude: float
    longitude: float
    zone_key: str


@lru_cache(maxsize=None)
def _reference_cities() -> tuple[_ReferenceCity, ...]:
    """Every zone.tab reference city with its zone key."""
    cities: list[_ReferenceCity] = []
    for _, coords, key in _zone_tab_rows():
        latitude, longitude = _parse_iso6709(coords)
        cities.append(_ReferenceCity(latitude, longitude, key))
    return tuple(cities)


@lru_cache(maxsize=None)
def _reference_coordinates() -> dict[str, tuple[float, float]]:
    """Zone key to reference-city coordinates, from zone.tab."""
    return {
        key: (latitude, longitude) for latitude, longitude, key in _reference_cities()
    }


def _central_angle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle angle between two points, in radians."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    cosine = math.sin(phi1) * math.sin(phi2) + math.cos(phi1) * math.cos(
        phi2
    ) * math.cos(math.radians(lon2 - lon1))
    return math.acos(max(-1.0, min(1.0, cosine)))


def _nearest_city(
    location: Location, cities: Iterable[_ReferenceCity]
) -> _ReferenceCity:
    """The reference city nearest to the location."""
    return min(
        cities,
        key=lambda city: _central_angle(
            location.latitude, location.longitude, city.latitude, city.longitude
        ),
    )


def _closest_reference_zone(location: Location) -> ZoneInfo:
    """Zone whose zone.tab reference city is nearest to the location."""
    return zone(_nearest_city(location, _reference_cities()).zone_key)


def _zone_key_within_birth_country(
    location: Location, modern_key: str, snapshot: int
) -> str:
    """Zone key for the birthplace, chosen within the country that held it
    on the given border map snapshot.

    The modern polygon zone is kept when its reference city belonged to the
    same country as the birthplace; otherwise the zone of the nearest
    reference city within that country applies, so the birth never gets
    another country's time history. Without a usable country match (open
    sea, unmapped area, a country holding no reference city) the modern
    polygon zone is kept.
    """
    birth_country = polity_index(location.latitude, location.longitude, snapshot)
    if birth_country is None:
        return modern_key
    reference = _reference_coordinates().get(modern_key)
    if reference is not None and polity_index(*reference, snapshot) == birth_country:
        return modern_key
    candidates = [
        city
        for city in _reference_cities()
        if polity_index(city.latitude, city.longitude, snapshot) == birth_country
    ]
    if not candidates:
        return modern_key
    return _nearest_city(location, candidates).zone_key


def _historical_timezone(
    location: Location, modern_key: str, year: int
) -> tuple[ZoneInfo, TimezoneDerivation]:
    """Zone for a pre-1970 birth, chosen within the birth-year country.

    The zone is derived under both border map snapshots around the birth year.
    When they agree the derivation is an ordinary estimate; when they disagree
    the borders moved close to the birth year, the nearer map's zone is
    used, and the derivation says BORDERS_UNCERTAIN. Comparing derived
    zones, not country names, keeps a mere renaming between maps (German
    Empire vs Germany) from counting as a border change.
    """
    earlier, later = snapshots_around(year)
    earlier_key = _zone_key_within_birth_country(location, modern_key, earlier)
    later_key = _zone_key_within_birth_country(location, modern_key, later)
    if earlier_key == later_key:
        return zone(earlier_key), TimezoneDerivation.ESTIMATED
    nearest_key = earlier_key if nearest_snapshot_year(year) == earlier else later_key
    return zone(nearest_key), TimezoneDerivation.BORDERS_UNCERTAIN


def location_timezone(
    location: Location, birth_datetime: dt.datetime
) -> tuple[ZoneInfo | dt.timezone, TimezoneDerivation]:
    """Timezone for the coordinates at the birth moment, and how sure it is.

    A geographic IANA zone covering the point derives the timezone with
    certainty for births from TZDB_CERTAIN_SINCE on: any later divergence
    forces a distinct tzdb zone, so the modern polygon is also the correct
    historical one back to that epoch. An earlier birth is an estimate
    chosen within the country that held the birthplace in the birth year
    (see _historical_timezone). Open water gets the nautical Etc/GMT zone,
    and a point with no zone match at all gets the longitude's mean solar time;
    both are estimates.
    """
    key = location_zone_key(location)
    if key is None:
        return _mean_solar_timezone(location.longitude), TimezoneDerivation.ESTIMATED
    try:
        if key.startswith("Etc/"):
            return zone(key), TimezoneDerivation.ESTIMATED
        if birth_datetime.date() < TZDB_CERTAIN_SINCE:
            return _historical_timezone(location, key, birth_datetime.year)
        return zone(key), TimezoneDerivation.CERTAIN
    except ZoneInfoNotFoundError:
        # timezonefinder returned a key the bundled tzdata lacks (version skew):
        # fall back to a nearby real zone, else the longitude's mean solar time.
        try:
            return _closest_reference_zone(location), TimezoneDerivation.ESTIMATED
        except ZoneInfoNotFoundError:
            return (
                _mean_solar_timezone(location.longitude),
                TimezoneDerivation.ESTIMATED,
            )


def resolve_timezone(
    location: Location,
    birth_datetime: dt.datetime,
    *,
    zone_key: str | None = None,
    offset: dt.timedelta | None = None,
    on_summer_time: bool | None = None,
) -> ResolvedTimezone:
    """Work out which timezone applied at a birth.

    With neither zone_key nor offset, the timezone comes from the coordinates
    and the birth date, along with how sure that answer is. Either argument
    names the timezone instead. That is always certain, but it is checked
    against the birthplace first, because a wrongly given offset can belong
    nowhere near it.

    The place lookups happen here, so the calculation never repeats them.
    """
    if zone_key is not None and offset is not None:
        raise ValueError("pass zone_key or offset, not both")

    if zone_key is not None:
        tz: ZoneInfo | dt.timezone = zone(zone_key)
        provenance = TimezoneProvenance.USER_ZONE
        derivation = TimezoneDerivation.CERTAIN
    elif offset is not None:
        tz = fixed_offset(offset)
        provenance = TimezoneProvenance.USER_OFFSET
        derivation = TimezoneDerivation.CERTAIN
    else:
        tz, derivation = location_timezone(location, birth_datetime)
        provenance = TimezoneProvenance.LOCATION_DERIVED

    # A derived timezone corresponds to its location by construction;
    # only user-supplied one could be incorrect.
    if provenance is not TimezoneProvenance.LOCATION_DERIVED:
        validate_timezone_for_location(birth_datetime, tz, location)

    if isinstance(tz, ZoneInfo):
        key, offset_seconds = tz.key, None
    else:
        key, offset_seconds = None, round(tz.utcoffset(None).total_seconds())

    return ResolvedTimezone(
        key=key,
        offset_seconds=offset_seconds,
        provenance=provenance,
        derivation=derivation,
        # A nautical or mean-solar zone counts as longitude-based only when we
        # chose it; the same offset typed by hand is a deliberate clock time.
        is_longitude_based=(
            provenance is TimezoneProvenance.LOCATION_DERIVED
            and is_longitude_based_timezone(tz)
        ),
        # A summer-time answer is kept only when the birth time really falls in
        # a repeated fall-back hour; anywhere else it resolved nothing.
        on_summer_time=(
            on_summer_time if is_ambiguous_local_time(birth_datetime, tz) else None
        ),
        for_latitude=location.latitude,
        for_longitude=location.longitude,
        for_birth_date=birth_datetime.date(),
        modern_zone_key=location_zone_key(location),
        gregorian_adoption_date=gregorian_adoption_date(location),
    )


def standard_offset_hours(local_dt: dt.datetime) -> float:
    """UTC offset of the clock's standard time, in hours (DST stripped)."""
    utc_offset = local_dt.utcoffset()
    if utc_offset is None:
        raise ValueError("local_dt must be timezone-aware")
    dst_offset = local_dt.dst() or dt.timedelta(0)
    return (utc_offset - dst_offset).total_seconds() / 3600


def offset_solar_gap_hours(local_dt: dt.datetime, location: Location) -> float:
    """Signed gap between a birth's standard-time clock and local mean solar time.

    Negative means the clock runs behind the sun.
    """
    offset_h = standard_offset_hours(local_dt)
    solar_h = location.longitude / 15
    return ((offset_h - solar_h + 12) % 24) - 12


def validate_timezone_for_location(
    naive_dt: dt.datetime, tz: dt.tzinfo, location: Location
) -> None:
    """Reject a fixed offset outside the real-timezone range, and any timezone
    whose clock is too far from the location's mean solar time.

    Checks the zone's raw reading: in the LMT era localize_naive_time substitutes
    the birth longitude's mean solar time, whose solar gap is ~0 by construction
    and would mask a bogus offset. The solar-gap check is skipped at or above
    LATITUDE_LIMIT, where the day start is a fixed local hour and solar time
    is irrelevant.
    """
    raw_local = _choose_repeated_hour(naive_dt, tz)
    if isinstance(tz, dt.timezone):
        offset_h = standard_offset_hours(raw_local)
        if not UTC_OFFSET_MIN_HOURS <= offset_h <= UTC_OFFSET_MAX_HOURS:
            raise TimezoneOffsetOutOfRangeError(
                f"birth_timezone UTC offset {offset_h:+.1f} h is outside the "
                f"real-timezone range [{UTC_OFFSET_MIN_HOURS:+d}, "
                f"{UTC_OFFSET_MAX_HOURS:+d}] h; check the UTC offset"
            )
    if abs(location.latitude) >= LATITUDE_LIMIT:
        return
    gap = offset_solar_gap_hours(raw_local, location)
    if not OFFSET_BEHIND_SOLAR_LIMIT_HOURS <= gap <= OFFSET_AHEAD_SOLAR_LIMIT_HOURS:
        direction = "behind" if gap < 0 else "ahead of"
        raise TimezoneLocationMismatchError(
            "birth_timezone offset is inconsistent with birth_location longitude "
            f"(clock {abs(gap):.1f} h {direction} local mean solar time; allowed "
            f"{OFFSET_BEHIND_SOLAR_LIMIT_HOURS:+.1f} to "
            f"{OFFSET_AHEAD_SOLAR_LIMIT_HOURS:+.1f} h); "
            "check the location and UTC offset"
        )
