"""Timezone data and value types shared by zone derivation and Namkha calculation.

Everything here is cheap to import: the bundled tzdata tree, the zone.tab
tables, and the plain types. The heavy location work - the timezone polygon
search and the historical border maps - lives in
namkha_calculator.zone_derivation, which nothing on the calculation path may
import.
"""

import datetime as dt
import importlib.resources
import math
import re
from dataclasses import dataclass
from enum import Enum, auto, unique
from functools import cached_property, lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import StaleTimezoneError

DATA_PACKAGE = "namkha_calculator"

LATITUDE_LIMIT = 60.0
HIGH_LATITUDE_DAY_START_HOUR = 5

# How far coordinates may drift and still count as the same place. Floats that
# have been through text or a database come back a fraction out; a millionth of
# a degree is about 10 cm, well above that noise and far below any timezone
# boundary.
_COORDINATE_TOLERANCE_DEGREES = 1e-6

_MEAN_SOLAR_TZNAME = "mean solar time"


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


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: str | None = None

    def __post_init__(self) -> None:
        """Reject coordinates outside the valid ranges."""
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
    resource = importlib.resources.files(DATA_PACKAGE).joinpath(
        "tzdata", *key.split("/")
    )
    try:
        with resource.open("rb") as file:
            return _KeyedZoneInfo.from_file(file, key=key)
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        if not importlib.resources.files(DATA_PACKAGE).joinpath("tzdata").is_dir():
            raise RuntimeError(
                "bundled tzdata is missing from this namkha-calculator"
                " installation; reinstall the package"
            ) from None
        raise ZoneInfoNotFoundError(f"no IANA timezone found for key {key!r}") from None


def _mean_solar_timezone(longitude: float) -> dt.timezone:
    """Fixed-offset timezone at the longitude's mean solar time."""
    return dt.timezone(dt.timedelta(seconds=round(longitude * 240)), _MEAN_SOLAR_TZNAME)


def fixed_offset(offset: dt.timedelta) -> dt.timezone:
    """Timezone with an arbitrary constant UTC offset, without a timezone name."""
    return dt.timezone(dt.timedelta(minutes=round(offset.total_seconds() / 60)))


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
            importlib.resources.files(DATA_PACKAGE)
            .joinpath("tzdata", "zone.tab")
            .read_text("utf-8")
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "bundled tzdata/zone.tab is missing from this namkha-calculator"
            " installation; reinstall the package"
        ) from error
    return _parse_zone_tab(table)


@lru_cache(maxsize=None)
def _zone_country_codes() -> dict[str, str]:
    """Zone key to ISO 3166 country code, from zone.tab."""
    return {key: country for country, _, key in _zone_tab_rows()}


def zone_country(key: str) -> str | None:
    """ISO 3166 country code of a zone key; None for a countryless zone."""
    return _zone_country_codes().get(key)


def zone_keys() -> tuple[str, ...]:
    """Every IANA zone key the bundled tzdata lists, in zone.tab order."""
    return tuple(key for _, _, key in _zone_tab_rows())


@unique
class TimezoneProvenance(Enum):
    """Where a resolved timezone came from.

    LOCATION_DERIVED: worked out from the coordinates and the birth date.
    USER_ZONE: an IANA zone the user named.
    USER_OFFSET: a UTC offset the user provided.
    """

    LOCATION_DERIVED = auto()
    USER_ZONE = auto()
    USER_OFFSET = auto()


@dataclass(frozen=True, kw_only=True)
class ResolvedTimezone:
    """A settled timezone: which one, how sure, and the place facts the
    calculation would otherwise have to look up again.

    zone_derivation.derive_timezone builds one; Subject holds it. It lives here
    with its readers because the calculation path may not import the code that
    builds it. Fields are plain values, so it stays hashable and picklable.

    Deriving and using are separate steps, so they can drift: it records the
    birth details it was derived for, and assert_binds checks them.
    """

    key: str | None
    offset_seconds: int | None
    provenance: TimezoneProvenance
    derivation: TimezoneDerivation
    is_longitude_based: bool
    on_summer_time: bool | None

    for_latitude: float
    for_longitude: float
    for_birth_date: dt.date

    modern_zone_key: str | None
    gregorian_adoption_date: dt.date

    def __post_init__(self) -> None:
        """A timezone is either a named zone or an offset, never both or neither."""
        if (self.key is None) == (self.offset_seconds is None):
            raise ValueError("exactly one of key and offset_seconds must be set")

    @cached_property
    def tzinfo(self) -> dt.tzinfo:
        """The timezone itself, rebuilt from the stored key or offset."""
        if self.key is not None:
            return zone(self.key)
        offset = dt.timedelta(seconds=self.offset_seconds or 0)
        if self.is_longitude_based:
            # A mean solar offset is a whole number of seconds, not of minutes,
            # so fixed_offset would round it and move the birth by up to 30 s.
            return dt.timezone(offset, _MEAN_SOLAR_TZNAME)
        return fixed_offset(offset)

    def assert_binds(self, location: Location, birth_datetime: dt.datetime) -> None:
        """Raise unless the birth details still match the ones this was derived
        for. Coordinates are compared with a small tolerance. The time of day is
        not compared at all, since only the date can change which timezone
        applied."""
        if (
            not math.isclose(
                location.latitude,
                self.for_latitude,
                abs_tol=_COORDINATE_TOLERANCE_DEGREES,
            )
            or not math.isclose(
                location.longitude,
                self.for_longitude,
                abs_tol=_COORDINATE_TOLERANCE_DEGREES,
            )
            or birth_datetime.date() != self.for_birth_date
        ):
            raise StaleTimezoneError(
                "resolved timezone was derived for "
                f"({self.for_latitude}, {self.for_longitude}) on "
                f"{self.for_birth_date}, but the birth is at "
                f"({location.latitude}, {location.longitude}) on "
                f"{birth_datetime.date()}; derive it again"
            )
