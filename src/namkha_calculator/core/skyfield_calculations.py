"""
Calculations of twilights and julian dates for 'calendar' module using Skyfield
"""

import datetime as dt
import os
from typing import TYPE_CHECKING

import pytz
from skyfield import almanac
from skyfield.api import Loader, wgs84

if TYPE_CHECKING:
    from .astrology import Location


_sf_loader = None
_sf_timescale = None
_sf_ephemeris = None


def _get_loader():
    global _sf_loader
    if _sf_loader is None:
        _sf_loader = Loader(
            str(os.path.dirname(os.path.abspath(__file__))), verbose=False
        )
    return _sf_loader


def _get_timescale():
    global _sf_timescale
    if _sf_timescale is None:
        _sf_timescale = _get_loader().timescale()
    return _sf_timescale


def _get_ephemeris():
    global _sf_ephemeris
    if _sf_ephemeris is None:
        _sf_ephemeris = _get_loader()("de440_filtered.bsp")
    return _sf_ephemeris


def jd_to_datetime(jd: float) -> dt.datetime:
    return _get_timescale().tt_jd(jd).utc_datetime()


def civil_twilight_boundaries(
    date: dt.date, pytz_tz: pytz.BaseTzInfo, location: "Location"
) -> list[dt.datetime]:
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
    return boundaries
