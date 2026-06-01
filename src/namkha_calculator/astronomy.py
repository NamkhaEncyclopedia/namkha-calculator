from typing import NamedTuple

LATITUDE_LIMIT = 60.0
HIGH_LATITUDE_DAY_START_HOUR = 4


class Location(NamedTuple):
    latitude: float
    longitude: float
    name: str | None = None
