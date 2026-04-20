"""
Calculations of twilights and julian dates for 'calendar' module using Skyfield
"""

import datetime as dt
import os
from typing import TYPE_CHECKING

from skyfield import almanac
from skyfield.api import Loader, wgs84
from skyfield.earthlib import refraction

if TYPE_CHECKING:
    from .astrology import Location


sf_load = Loader(str(os.path.dirname(os.path.abspath(__file__))), verbose=False)

SF_TIMESCALE = sf_load.timescale()
SF_EPHEMERIS = sf_load("de440_filtered.bsp")


def jd_to_datetime(jd: float) -> dt.datetime:
    return SF_TIMESCALE.tt_jd(jd).utc_datetime()


def civil_twilight_boundaries(
    date: dt.date, pytz_timezone, location: "Location"
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


def solar_midnight_noon(
    date: dt.date, pytz_timezone, location: "Location"
) -> dt.datetime:
    topos = wgs84.latlon(location.latitude, location.longitude)
    search_func = almanac.meridian_transits(SF_EPHEMERIS, SF_EPHEMERIS["Sun"], topos)

    naive_midnight = dt.datetime.combine(date, dt.time(0, 0, 0))
    midnight = pytz_timezone.localize(naive_midnight)
    next_midnight = midnight + dt.timedelta(days=1)

    times, codes = almanac.find_discrete(
        SF_TIMESCALE.from_datetime(midnight),
        SF_TIMESCALE.from_datetime(next_midnight),
        search_func,
    )

    times = times[codes == 1]
    assert len(times) == 1
    solar_noon = times[0].astimezone(pytz_timezone)

    times, codes = almanac.find_discrete(
        SF_TIMESCALE.from_datetime(solar_noon - dt.timedelta(days=1)),
        SF_TIMESCALE.from_datetime(solar_noon),
        search_func,
    )

    times = times[codes == 0]
    assert len(times) == 1
    solar_midnight = times[0].astimezone(pytz_timezone)

    return solar_midnight, solar_noon


def sun_declination(date_time: dt.datetime) -> float:
    earth, sun = SF_EPHEMERIS["earth"], SF_EPHEMERIS["Sun"]
    time = SF_TIMESCALE.from_datetime(date_time)
    return earth.at(time).observe(sun).apparent().radec("date")[1]


def _highest_lat(
    measuring_date_time: dt.date, pytz_timezone, location: "Location", sun_alt: float
) -> float:
    current_lat = location.latitude
    sun_dec = sun_declination(measuring_date_time).degrees

    match (current_lat, sun_dec):
        case (current_lat, sun_dec) if current_lat > 0 and sun_dec > 0:
            return 90.0 - sun_dec + sun_alt
        case (current_lat, sun_dec) if current_lat > 0 and sun_dec <= 0:
            return 90.0 + sun_dec + sun_alt
        case (current_lat, sun_dec) if current_lat < 0 and sun_dec > 0:
            return -90.0 + sun_dec - sun_alt
        case (current_lat, sun_dec) if current_lat < 0 and sun_dec <= 0:
            return -90.0 - sun_dec - sun_alt
        case _:
            raise ValueError("Latitude value cannot be zero.")


def highest_lat_night(date_: dt.date, pytz_timezone, location: "Location") -> float:
    solar_midnight, _ = solar_midnight_noon(date_, pytz_timezone, location)
    return _highest_lat(solar_midnight, pytz_timezone, location, -18.0)


def highest_lat_day(date_: dt.date, pytz_timezone, location: "Location") -> float:
    _, solar_noon = solar_midnight_noon(date_, pytz_timezone, location)
    return _highest_lat(
        solar_noon,
        pytz_timezone,
        location,
        float(refraction(0.0, temperature_C=15.0, pressure_mbar=1030.0)),
    )
