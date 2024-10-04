"""
Calculations of twilights and julian dates for 'calendar' module using Skyfield
"""

import os
import datetime as dt
from typing import NamedTuple

from skyfield import almanac
from skyfield.api import Loader, wgs84


class Location(NamedTuple):
    latitude: float
    longitude: float


sf_load = Loader(str(os.path.dirname(os.path.abspath(__file__))), verbose=False)

SF_TIMESCALE = sf_load.timescale()
SF_EPHEMERIS = sf_load("de440.bsp")


def jd_to_datetime(jd: float) -> dt.datetime:
    return SF_TIMESCALE.tt_jd(jd).utc_datetime()


def civil_twilight_boundaries(
    date_: dt.date, location: Location
) -> tuple[dt.datetime, dt.datetime]:
    topos = wgs84.latlon(location.latitude, location.longitude)
    search_func = almanac.dark_twilight_day(SF_EPHEMERIS, topos)
    midnight = dt.datetime.combine(date_, dt.time(0, 0, 0)).astimezone(dt.timezone.utc)
    noon = midnight + dt.timedelta(days=1)
    events = almanac.find_discrete(
        SF_TIMESCALE.from_datetime(midnight),
        SF_TIMESCALE.from_datetime(noon),
        search_func,
    )
    boundaries = []
    boundary_code = 3
    for time, code in zip(*events):
        if code == boundary_code:
            boundaries.append(time.utc_datetime())
            boundary_code = 2
    assert len(boundaries) == 2
    return tuple(boundaries)
