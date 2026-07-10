import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique
from functools import cached_property

from .astronomy import (
    LATITUDE_LIMIT,
    OFFSET_AHEAD_SOLAR_LIMIT_HOURS,
    OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    UTC_OFFSET_MAX_HOURS,
    UTC_OFFSET_MIN_HOURS,
    Location,
    PytzTimezone,
    localize_standard,
    offset_solar_gap_hours,
    standard_offset_hours,
)


# Declaration order of Element and Animal is the astrological cycle order;
# calendar.py derives its lookup tables from it.
@unique
class Element(str, Enum):
    WOOD = "Wood"
    FIRE = "Fire"
    EARTH = "Earth"
    METAL = "Metal"
    WATER = "Water"


@unique
class Animal(str, Enum):
    MOUSE = "Mouse"
    OX = "Ox"
    TIGER = "Tiger"
    HARE = "Hare"
    DRAGON = "Dragon"
    SNAKE = "Snake"
    HORSE = "Horse"
    SHEEP = "Sheep"
    MONKEY = "Monkey"
    BIRD = "Bird"
    DOG = "Dog"
    BOAR = "Boar"


@unique
class Gender(Enum):
    MALE = auto()
    FEMALE = auto()


@dataclass(frozen=True)
class Subject:
    gender: Gender
    birth_datetime: dt.datetime  # naive local time
    birth_timezone: PytzTimezone
    birth_location: Location
    name: str | None

    def __post_init__(self) -> None:
        if self.birth_datetime.tzinfo is not None:
            raise TypeError("birth_datetime must be naive (no tzinfo)")
        if not isinstance(self.birth_timezone, PytzTimezone):
            raise TypeError(
                "birth_timezone must be a pytz timezone or a fixed offset "
                "(use fixed_offset(...) for an arbitrary UTC offset)"
            )
        offset_h = standard_offset_hours(self.local_birth_datetime)
        if not UTC_OFFSET_MIN_HOURS <= offset_h <= UTC_OFFSET_MAX_HOURS:
            raise ValueError(
                f"birth_timezone UTC offset {offset_h:+.1f} h is outside the "
                f"real-timezone range [{UTC_OFFSET_MIN_HOURS:+d}, "
                f"{UTC_OFFSET_MAX_HOURS:+d}] h; check the UTC offset"
            )
        # At or above LATITUDE_LIMIT the day start is a fixed local hour,
        # so solar time is irrelevant there.
        if abs(self.birth_location.latitude) >= LATITUDE_LIMIT:
            return
        gap = offset_solar_gap_hours(self.local_birth_datetime, self.birth_location)
        if (
            not -OFFSET_BEHIND_SOLAR_LIMIT_HOURS
            <= gap
            <= OFFSET_AHEAD_SOLAR_LIMIT_HOURS
        ):
            direction = "behind" if gap < 0 else "ahead of"
            raise ValueError(
                "birth_timezone offset is inconsistent with birth_location longitude "
                f"(clock {abs(gap):.1f} h {direction} local mean solar time; allowed "
                f"{-OFFSET_BEHIND_SOLAR_LIMIT_HOURS:+.1f} to "
                f"{OFFSET_AHEAD_SOLAR_LIMIT_HOURS:+.1f} h); "
                "check the location and UTC offset"
            )

    @cached_property
    def local_birth_datetime(self) -> dt.datetime:
        return localize_standard(self.birth_datetime, self.birth_timezone)
