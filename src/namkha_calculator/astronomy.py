import datetime as dt
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pytz

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
OFFSET_BEHIND_SOLAR_LIMIT_HOURS = 2.5
OFFSET_AHEAD_SOLAR_LIMIT_HOURS = 3.5

# Real time zones span UTC-12 (Baker Island) to UTC+14 (Line Islands). An
# offset outside this range is a data-entry error; without this bound the
# mod-24 gap wrap below would let a day-off offset (e.g. +22 for -2) pass
# the solar check as a near-zero gap.
UTC_OFFSET_MIN_HOURS = -12
UTC_OFFSET_MAX_HOURS = 14


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: str | None = None

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude must be in [-90, 90], got {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude must be in [-180, 180], got {self.longitude}")


@runtime_checkable
class PytzTimezone(Protocol):
    """pytz-style tzinfo: exposes localize/normalize, unlike stdlib tzinfo."""

    def localize(
        self, value: dt.datetime, /, is_dst: bool | None = ...
    ) -> dt.datetime: ...
    def normalize(self, value: dt.datetime, /) -> dt.datetime: ...


def fixed_offset(offset: dt.timedelta) -> PytzTimezone:
    """Timezone with an arbitrary constant UTC offset, without a timezone name."""
    return pytz.FixedOffset(round(offset.total_seconds() / 60))


def localize_standard(naive_dt: dt.datetime, tz: PytzTimezone) -> dt.datetime:
    """Naive wall-clock time resolved with the standard-time reading.

    The single point of the resolution for ambiguous and non-existent
    local times; calculation_notes.local_time_dst_note flags affected times.

    All library code must localize naive datetimes through this function.
    The only allowed direct tz.localize call is the is_dst=None probe in
    local_time_dst_note. Enforced by tests/test_localization_policy.py.
    """
    return tz.localize(naive_dt, is_dst=False)


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
