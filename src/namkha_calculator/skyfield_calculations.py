"""
Calculations of twilights and julian date conversion for `calendar` module
"""

import datetime as dt
import os
from functools import lru_cache
from typing import TYPE_CHECKING

import pytz
from skyfield import almanac
from skyfield.api import Loader, wgs84

if TYPE_CHECKING:
    from .astronomy import Location


@lru_cache(maxsize=None)
def _get_loader():
    return Loader(str(os.path.dirname(os.path.abspath(__file__))), verbose=False)


@lru_cache(maxsize=None)
def _get_timescale():
    return _get_loader().timescale()


@lru_cache(maxsize=None)
def _get_ephemeris():
    return _get_loader()("de440_filtered.bsp")


def jd_to_datetime(jd: float) -> dt.datetime:
    return _get_timescale().tt_jd(jd).utc_datetime()


@lru_cache(maxsize=None)
def ephemeris_date_range() -> tuple[dt.datetime, dt.datetime]:
    """UTC dates the bundled ephemeris covers (intersection of all segments)."""
    segments = _get_ephemeris().spk.segments
    if not segments:
        raise ValueError("Ephemeris contains no segments; cannot determine date range")
    start_jd = max(seg.start_jd for seg in segments)
    end_jd = min(seg.end_jd for seg in segments)
    if start_jd > end_jd:
        raise ValueError(
            f"Ephemeris segments have no common coverage "
            f"(latest start {start_jd} > earliest end {end_jd})"
        )
    ts = _get_timescale()
    return ts.tt_jd(start_jd).utc_datetime(), ts.tt_jd(end_jd).utc_datetime()


@lru_cache(maxsize=2048)
def morning_civil_twilight(
    date: dt.date, pytz_tz: pytz.BaseTzInfo, location: "Location"
) -> dt.datetime | None:
    """
    Start of morning civil twilight (dawn) on a local date, returned in UTC.

    Searches the morning window [local midnight, +14h] and returns the rising
    crossing into civil twilight (the sun passing -6 deg upward). Returns None
    when no such crossing exists that date, so the caller can fall back to a fixed start.

    The return value is always UTC.
    """
    topos = wgs84.latlon(location.latitude, location.longitude)
    search_func = almanac.dark_twilight_day(_get_ephemeris(), topos)

    midnight = pytz_tz.localize(dt.datetime.combine(date, dt.time(0, 0, 0)))
    window_end = midnight + dt.timedelta(hours=14)
    ts = _get_timescale()
    times, codes = almanac.find_discrete(
        ts.from_datetime(midnight), ts.from_datetime(window_end), search_func
    )

    # dark_twilight_day codes the state after each transition: 0 night,
    # 1 astronomical, 2 nautical, 3 civil, 4 day. The Tibetan day starts at the
    # rising edge of civil twilight: the first transition reaching civil (code 3)
    # from a darker state (previous code < 3). A 4 -> 3 drop is evening dusk, not
    # dawn. See https://rhodesmill.org/skyfield/almanac.html#twilight
    previous_code = search_func(ts.from_datetime(midnight)).item()
    for time, code in zip(times, codes):
        if code == 3 and previous_code < 3:
            return time.utc_datetime()
        previous_code = code
    return None
