from typing import Optional
from typing import NamedTuple


LATITUDE_LIMIT = 60.0

class Location(NamedTuple):
    latitude: float
    longitude: float
    name: Optional[str] = None