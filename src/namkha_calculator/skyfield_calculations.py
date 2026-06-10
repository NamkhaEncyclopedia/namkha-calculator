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
    from .astrology import Location


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


def civil_twilight_boundaries(
    date: dt.date, pytz_tz: pytz.BaseTzInfo, location: "Location"
) -> tuple[dt.datetime, dt.datetime]:
    """
    Returns the start and end times of civil twilight
    for the given date and location in UTC.
    """
    topos = wgs84.latlon(location.latitude, location.longitude)
    search_func = almanac.dark_twilight_day(_get_ephemeris(), topos)

    midnight = pytz_tz.localize(dt.datetime.combine(date, dt.time(0, 0, 0)))
    next_midnight = midnight + dt.timedelta(days=1)
    events = almanac.find_discrete(
        _get_timescale().from_datetime(midnight),
        _get_timescale().from_datetime(next_midnight),
        search_func,
    )

    # almanac.dark_twilight_day codes the new state after each transition:
    # 0 night, 1 astronomical, 2 nautical, 3 civil, 4 day. Civil twilight spans
    # the sun being between 0 and -6 deg. We want its two -6 deg crossings:
    # morning = entering civil (code 3), evening = leaving civil back into nautical
    # (code 2). Match them in order, switching the target after the morning one.
    # See also: https://rhodesmill.org/skyfield/almanac.html#twilight
    boundaries = []
    boundary_code = 3
    for time, code in zip(*events):
        if code == boundary_code:
            boundaries.append(time.utc_datetime())
            boundary_code = 2
    if len(boundaries) != 2:
        raise ValueError(
            f"Expected 2 civil-twilight boundaries for {date} at "
            f"lat={location.latitude:.2f}, got {len(boundaries)}. "
            "Location may be within polar day/night on this date."
        )
    return boundaries[0], boundaries[1]
