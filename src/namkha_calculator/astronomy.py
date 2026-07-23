import datetime as dt
import importlib.resources
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto, unique
from functools import lru_cache
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .historical_borders import nearest_snapshot_year, polity_index, snapshots_around

LATITUDE_LIMIT = 60.0
HIGH_LATITUDE_DAY_START_HOUR = 5

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


@unique
class TimezoneDerivation(Enum):
    """How sure a location-derived timezone is.

    CERTAIN: modern polygon zone for a birth from TZDB_CERTAIN_SINCE on.
    ESTIMATED: best historically recorded regional time, or a longitude-based
    fallback (nautical zone, mean solar time).
    BORDERS_UNCERTAIN: like ESTIMATED, but borders around the birthplace
    moved close to the birth year, so even the country attribution is
    uncertain.
    """

    CERTAIN = auto()
    ESTIMATED = auto()
    BORDERS_UNCERTAIN = auto()


_DAY = dt.timedelta(hours=24)
_UTC = dt.timezone.utc

_MEAN_SOLAR_TZNAME = "mean solar time"


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: str | None = None

    def __post_init__(self) -> None:
        """Reject coordinates outside the valid Earth ranges."""
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude must be in [-90, 90], got {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude must be in [-180, 180], got {self.longitude}")


class _KeyedZoneInfo(ZoneInfo):
    """A ZoneInfo that pickles by key. ZoneInfo.from_file instances otherwise
    cannot be pickled; this reloads from the bundled tzdata via zone()."""

    def __reduce__(self):
        return zone, (self.key,)


@lru_cache(maxsize=None)
def zone(key: str) -> ZoneInfo:
    """IANA timezone loaded from the bundled zoneinfo tree.

    Preferred over plain ZoneInfo(key): results do not depend on the
    operating system's timezone database version or build options. The
    bundled tree (built by tools/build_tzdata.py) includes backzone data,
    so zones merged by the default tzdb build keep their own real pre-1970
    histories (e.g. Europe/Amsterdam, Europe/Stockholm).
    """
    resource = importlib.resources.files(__package__).joinpath(
        "tzdata", *key.split("/")
    )
    try:
        with resource.open("rb") as file:
            return _KeyedZoneInfo.from_file(file, key=key)
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        if not importlib.resources.files(__package__).joinpath("tzdata").is_dir():
            raise RuntimeError(
                "bundled tzdata is missing from this namkha-calculator"
                " installation; reinstall the package"
            ) from None
        raise ZoneInfoNotFoundError(f"no IANA timezone found for key {key!r}") from None


@lru_cache(maxsize=None)
def _timezone_finder():
    """Shared TimezoneFinder instance, created on first use."""
    from timezonefinder import TimezoneFinder

    return TimezoneFinder()


def _mean_solar_timezone(longitude: float) -> dt.timezone:
    """Fixed-offset timezone at the longitude's mean solar time."""
    return dt.timezone(dt.timedelta(seconds=round(longitude * 240)), _MEAN_SOLAR_TZNAME)


# Signed latitude then longitude, degrees+minutes with optional seconds:
# +-DDMM[SS]+-DDDMM[SS].
_ISO6709_PATTERN = re.compile(r"([+-]\d{4}(?:\d{2})?)([+-]\d{5}(?:\d{2})?)")


def _parse_iso6709(coords: str) -> tuple[float, float]:
    """Latitude and longitude in degrees from a zone.tab ISO 6709 coordinate pair."""
    match = _ISO6709_PATTERN.fullmatch(coords)
    if match is None:
        raise ValueError(f"malformed ISO 6709 coordinates: {coords!r}")

    def to_degrees(value: str, degree_digits: int) -> float:
        sign = -1.0 if value[0] == "-" else 1.0
        degrees = int(value[1 : 1 + degree_digits])
        minutes = int(value[1 + degree_digits : 3 + degree_digits])
        seconds = int(value[3 + degree_digits :] or 0)
        return sign * (degrees + minutes / 60 + seconds / 3600)

    return to_degrees(match.group(1), 2), to_degrees(match.group(2), 3)


def _parse_zone_tab(table: str) -> tuple[tuple[str, str, str], ...]:
    """(country code, ISO 6709 coordinates, zone key) rows from zone.tab text."""
    rows: list[tuple[str, str, str]] = []
    for line in table.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 3:
            raise ValueError(
                f"corrupted tzdata: zone.tab line has {len(fields)} fields,"
                f" expected at least 3: {line!r}"
            )
        country, coords, key = fields[:3]
        rows.append((country, coords, key))
    if not rows:
        raise ValueError("corrupted tzdata: zone.tab contains no zone entries")
    return tuple(rows)


@lru_cache(maxsize=None)
def _zone_tab_rows() -> tuple[tuple[str, str, str], ...]:
    """(country code, ISO 6709 coordinates, zone key) rows from the bundled zone.tab."""
    try:
        table = (
            importlib.resources.files(__package__)
            .joinpath("tzdata", "zone.tab")
            .read_text("utf-8")
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "bundled tzdata/zone.tab is missing from this namkha-calculator"
            " installation; reinstall the package"
        ) from error
    return _parse_zone_tab(table)


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
def _zone_country_codes() -> dict[str, str]:
    """Zone key to ISO 3166 country code, from zone.tab."""
    return {key: country for country, _, key in _zone_tab_rows()}


@lru_cache(maxsize=2048)
def location_zone_key(location: Location) -> str | None:
    """IANA key of the geographic zone covering the location, if any."""
    return _timezone_finder().timezone_at(lng=location.longitude, lat=location.latitude)


def zone_country(key: str) -> str | None:
    """ISO 3166 country code of a zone key; None for a countryless zone."""
    return _zone_country_codes().get(key)


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


@lru_cache(maxsize=None)
def _reference_coordinates() -> dict[str, tuple[float, float]]:
    """Zone key to reference-city coordinates, from zone.tab."""
    return {
        key: (latitude, longitude) for latitude, longitude, key in _reference_cities()
    }


def _zone_key_within_birth_country(
    location: Location, modern_key: str, snapshot: int
) -> str:
    """Zone key for the birthplace, chosen within the country that held it
    on the given border map.

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

    The zone is derived under both border maps around the birth year. When
    they agree the derivation is an ordinary estimate; when they disagree
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
) -> tuple[dt.tzinfo, TimezoneDerivation]:
    """Timezone for the coordinates at the birth moment, and how sure it is.

    A geographic IANA zone covering the point derives the timezone with
    certainty for births from TZDB_CERTAIN_SINCE on: any later divergence
    forces a distinct tzdb zone, so the modern polygon is also the correct
    historical one back to that epoch. An earlier birth is an estimate
    chosen within the country that held the birthplace in the birth year
    (see _historical_timezone), marked BORDERS_UNCERTAIN when borders moved
    around the birthplace close to the birth year. Open water gets the
    nautical Etc/GMT zone, and a point with no zone match at all gets the
    longitude's mean solar time; both are estimates.
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


def fixed_offset(offset: dt.timedelta) -> dt.timezone:
    """Timezone with an arbitrary constant UTC offset, without a timezone name."""
    return dt.timezone(dt.timedelta(minutes=round(offset.total_seconds() / 60)))


def _resolve_repeated_hour(
    naive_dt: dt.datetime, tz: dt.tzinfo, on_summer_time: bool | None = None
) -> dt.datetime:
    """Attach the timezone, choosing which reading of a repeated fall-back
    hour applies.

    In a fall-back hour the wall-clock time maps to two instants; summer time is
    the earlier one, with the higher offset. on_summer_time=True picks it, False
    or None the later (lower-offset) reading. Chosen by offset, not dst(), so
    reversed-DST zones resolve correctly.

    Requires a PEP 495 tzinfo (zoneinfo.ZoneInfo or datetime.timezone - the only
    kinds Subject accepts); pre-PEP 495 classes like pytz ignore fold and would
    misresolve clock changes.
    """
    first = naive_dt.replace(tzinfo=tz, fold=0)
    second = naive_dt.replace(tzinfo=tz, fold=1)
    if first.utcoffset() == second.utcoffset():
        return first
    if on_summer_time:
        return max((first, second), key=lambda d: d.utcoffset())  # type: ignore[arg-type, return-value]
    return min((first, second), key=lambda d: d.utcoffset())  # type: ignore[arg-type, return-value]


def uses_local_mean_time(naive_dt: dt.datetime, tz: dt.tzinfo) -> bool:
    """Whether the instant falls in the timezone's pre-standard-time era."""
    return _resolve_repeated_hour(naive_dt, tz).tzname() == "LMT"


def is_longitude_based_timezone(tz: dt.tzinfo) -> bool:
    """Whether tz derives its offset from longitude alone - a nautical Etc/GMT
    zone or a derived mean-solar offset - rather than from civil timezone
    rules. A fixed offset the user passed deliberately is not longitude-based.
    """
    if isinstance(tz, ZoneInfo):
        return (tz.key or "").startswith("Etc/")
    return isinstance(tz, dt.timezone) and tz.tzname(None) == _MEAN_SOLAR_TZNAME


def resolve_local_time(
    naive_dt: dt.datetime,
    tz: dt.tzinfo,
    location: Location,
    on_summer_time: bool | None = None,
) -> dt.datetime:
    """Attach the timezone to a naive local time.

    A fall-back hour resolves to on_summer_time (True: earlier occurrence,
    False or None: later); it is ignored for non-ambiguous times. Before a
    tzdb zone's standard-time era ("LMT") the offset becomes the birth
    longitude's own mean solar time, kept on the zone's historical date side.

    The library's single localization point, enforced by
    tests/test_localization_policy.py.
    """
    resolved = on_summer_time if is_ambiguous_local_time(naive_dt, tz) else None
    localized = _resolve_repeated_hour(naive_dt, tz, resolved)
    if not isinstance(tz, ZoneInfo) or localized.tzname() != "LMT":
        return localized
    return _birth_longitude_mean_time(naive_dt, localized, location)


def _birth_longitude_mean_time(
    naive_dt: dt.datetime, zone_lmt: dt.datetime, location: Location
) -> dt.datetime:
    """Attach the mean solar time of the birth longitude to a pre-standard-time
    birth, instead of the timezone's "LMT" offset.

    Before standard time every place kept its own sun time, so the birth
    longitude is more accurate than the zone's reference city. Only the
    time-of-day part of the offset is replaced; a whole-day part, present where
    the zone counted dates across the Date Line (pre-1845 Manila, -15:56 =
    +8:04 - 24 h), is kept so the birth stays on its historical calendar date.
    """
    solar = _mean_solar_timezone(location.longitude)
    days_apart = round((zone_lmt.utcoffset() - solar.utcoffset(None)) / _DAY)  # type: ignore[operator]
    date_side_solar = dt.timezone(solar.utcoffset(None) + days_apart * _DAY)
    return naive_dt.replace(tzinfo=date_side_solar)


def shift_past_clock_gap(aware_dt: dt.datetime) -> dt.datetime:
    """Shift a non-existent wall-clock time past its clock gap; no-op otherwise."""
    return aware_dt.astimezone(_UTC).astimezone(aware_dt.tzinfo)


def is_ambiguous_local_time(naive_dt: dt.datetime, tz: dt.tzinfo) -> bool:
    """Whether the wall-clock time occurs twice (clock set back over it)."""
    folds_differ = (
        naive_dt.replace(tzinfo=tz, fold=0).utcoffset()
        != naive_dt.replace(tzinfo=tz, fold=1).utcoffset()
    )
    return folds_differ and not is_nonexistent_local_time(naive_dt, tz)


def is_nonexistent_local_time(naive_dt: dt.datetime, tz: dt.tzinfo) -> bool:
    """Whether the wall-clock time was skipped (clock set forward over it)."""
    earlier = naive_dt.replace(tzinfo=tz, fold=0)
    later = naive_dt.replace(tzinfo=tz, fold=1)
    earlier_exists = shift_past_clock_gap(earlier).replace(tzinfo=None) == naive_dt
    later_exists = shift_past_clock_gap(later).replace(tzinfo=None) == naive_dt
    return not earlier_exists and not later_exists


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

    Checks the zone's raw reading: in the LMT era resolve_local_time substitutes
    the birth longitude's mean solar time, whose solar gap is ~0 by construction
    and would mask a bogus offset. The solar-gap check is skipped at or above
    LATITUDE_LIMIT, where the day start is a fixed local hour and solar time
    is irrelevant.
    """
    raw_local = _resolve_repeated_hour(naive_dt, tz)
    if isinstance(tz, dt.timezone):
        offset_h = standard_offset_hours(raw_local)
        if not UTC_OFFSET_MIN_HOURS <= offset_h <= UTC_OFFSET_MAX_HOURS:
            raise ValueError(
                f"birth_timezone UTC offset {offset_h:+.1f} h is outside the "
                f"real-timezone range [{UTC_OFFSET_MIN_HOURS:+d}, "
                f"{UTC_OFFSET_MAX_HOURS:+d}] h; check the UTC offset"
            )
    if abs(location.latitude) >= LATITUDE_LIMIT:
        return
    gap = offset_solar_gap_hours(raw_local, location)
    if not OFFSET_BEHIND_SOLAR_LIMIT_HOURS <= gap <= OFFSET_AHEAD_SOLAR_LIMIT_HOURS:
        direction = "behind" if gap < 0 else "ahead of"
        raise ValueError(
            "birth_timezone offset is inconsistent with birth_location longitude "
            f"(clock {abs(gap):.1f} h {direction} local mean solar time; allowed "
            f"{OFFSET_BEHIND_SOLAR_LIMIT_HOURS:+.1f} to "
            f"{OFFSET_AHEAD_SOLAR_LIMIT_HOURS:+.1f} h); "
            "check the location and UTC offset"
        )
