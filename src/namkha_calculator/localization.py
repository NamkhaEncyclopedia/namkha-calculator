"""Attaching a timezone to a naive local time.

A naive datetime is only what the clock showed; attaching a timezone turns it
into a real point in time. That is not a plain substitution: when clocks go
back, one clock reading covers two different moments; when they go forward,
some readings never happened at all.

Choosing *which* timezone applied is a separate job, done once when the birth
details are entered. It lives in zone_derivation, which nothing here may
import.

Every naive datetime the calculation touches goes through here, not only the
birth time: the dawn search localises both ends of a local day, and day_start
localises a fixed morning hour. Any of them can fall in a repeated or skipped
hour, so each is resolved on its own.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from .tz import _MEAN_SOLAR_TZNAME, Location, _mean_solar_timezone

_DAY = dt.timedelta(hours=24)
_UTC = dt.timezone.utc


def _resolve_repeated_hour(
    naive_dt: dt.datetime, tz: dt.tzinfo, *, on_summer_time: bool | None = None
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
    *,
    on_summer_time: bool | None = None,
) -> dt.datetime:
    """Attach the timezone to a naive local time: resolve a repeated fall-back
    hour, then substitute mean solar time in a zone's pre-standard-time era.

    on_summer_time is consulted only when the time is genuinely ambiguous. A
    skipped time reads differently under the two folds as well, but it never
    happened, so neither reading is correct; it always keeps the pre-gap one.

    The library's single localisation point, enforced by
    tests/test_localization_policy.py.
    """
    resolved = on_summer_time if is_ambiguous_local_time(naive_dt, tz) else None
    localized = _resolve_repeated_hour(naive_dt, tz, on_summer_time=resolved)
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
