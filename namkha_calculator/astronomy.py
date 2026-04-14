from typing import NamedTuple
import datetime as dt

from .skyfield_calculations import highest_lat_day, highest_lat_night

class Location(NamedTuple):
    latitude: float
    longitude: float


SAFE_LATITUDE = 49.0


def trim_latitude(
    location: Location, pytz_timezone, date_time: dt.datetime
) -> Location:
    """
    Due to uncertainty of how traditional Tibetan astrology handles
    hight latitudes this temporary solution is introduced:
    it trims the latitude to a range where astronomical day and night
    still occurs on a given date.

    TODO: Once we get more clarifications, this function should be reworked or removed.
    """
    if abs(location.latitude) > SAFE_LATITUDE:
        trimmed_latitude = min(
            highest_lat_day(
                date_=date_time.date(), pytz_timezone=pytz_timezone, location=location
            ),
            highest_lat_night(
                date_=date_time.date(), pytz_timezone=pytz_timezone, location=location
            ),
            key=abs,
        )
        # assert abs(trimmed_latitude) >= SAFE_LATITUDE
        return Location(
            latitude=trim_latitude,
            longitude=location.longitude,
        )
    return location