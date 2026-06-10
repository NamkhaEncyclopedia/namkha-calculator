from dataclasses import dataclass

LATITUDE_LIMIT = 60.0
HIGH_LATITUDE_DAY_START_HOUR = 5


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: str | None = None

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude must be in [-90, 90], got {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude must be in [-180, 180], got {self.longitude}")
