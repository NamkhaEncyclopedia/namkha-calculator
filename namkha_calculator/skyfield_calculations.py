"""
Calculations of twilights and julian dates for 'calendar' module using Skyfield
"""

import datetime as dt
import os

from skyfield import almanac
from skyfield.api import Loader, wgs84

from .astronomy import Location


sf_load = Loader(str(os.path.dirname(os.path.abspath(__file__))), verbose=False)

SF_TIMESCALE = sf_load.timescale()
SF_EPHEMERIS = sf_load("de440_filtered.bsp")


def jd_to_datetime(jd: float) -> dt.datetime:
    return SF_TIMESCALE.tt_jd(jd).utc_datetime()


def civil_twilight_boundaries(
    date: dt.date, pytz_timezone, location: Location
) -> list[dt.datetime, dt.datetime]:
    """
    Returns the start and end times of civil twilight
    for the given date and location in UTC.
    """
    topos = wgs84.latlon(location.latitude, location.longitude)
    search_func = almanac.dark_twilight_day(SF_EPHEMERIS, topos)

    naive_midnight = dt.datetime.combine(date, dt.time(0, 0, 0))
    midnight = pytz_timezone.localize(naive_midnight)

    next_midnight = midnight + dt.timedelta(days=1)
    events = almanac.find_discrete(
        SF_TIMESCALE.from_datetime(midnight),
        SF_TIMESCALE.from_datetime(next_midnight),
        search_func,
    )

    boundaries = []
    boundary_code = 3
    for time, code in zip(*events):
        if code == boundary_code:
            boundaries.append(time.utc_datetime())
            boundary_code = 2
    assert len(boundaries) == 2
    return boundaries
