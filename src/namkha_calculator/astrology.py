import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique
from functools import cached_property
from zoneinfo import ZoneInfo

from .astronomy import (
    Location,
    TimezoneDerivation,
    is_longitude_based_timezone,
    resolve_local_time,
    location_timezone,
    validate_timezone_for_location,
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


@dataclass(frozen=True, kw_only=True)
class Subject:
    gender: Gender
    birth_datetime: dt.datetime  # naive local time
    birth_location: Location
    birth_timezone: dt.tzinfo | None = None  # None -> derive from the location
    on_summer_time: bool | None = None  # pin a repeated fall-back hour; None -> guess
    name: str | None = None

    def __post_init__(self) -> None:
        """Reject aware birth times, unsupported timezone types, and timezones
        inconsistent with the birth location. An absence of timezone is exempt:
        it will be derived from the location itself with a level of certainty."""
        if self.birth_datetime.tzinfo is not None:
            raise TypeError("birth_datetime must be naive (no tzinfo)")
        if self.birth_timezone is None:
            return
        if not isinstance(self.birth_timezone, (ZoneInfo, dt.timezone)):
            raise TypeError(
                "birth_timezone must be a zoneinfo.ZoneInfo (use "
                "namkha_calculator.zone(key) for OS-independent data), a fixed "
                "offset (use fixed_offset(...)), or None to derive it"
                "from the birth location"
            )
        validate_timezone_for_location(
            self.birth_datetime, self.birth_timezone, self.birth_location
        )

    @cached_property
    def _located_timezone(self) -> tuple[dt.tzinfo, TimezoneDerivation]:
        """Timezone derived from the birth location, with how sure it is."""
        return location_timezone(self.birth_location, self.birth_datetime)

    @cached_property
    def effective_timezone(self) -> dt.tzinfo:
        """Timezone used in calculation: the given one, or the located one."""
        if self.birth_timezone is not None:
            return self.birth_timezone
        return self._located_timezone[0]

    @cached_property
    def timezone_derivation(self) -> TimezoneDerivation:
        """How sure the effective timezone is: an explicit birth_timezone is
        CERTAIN, a located one as sure as its derivation (see
        location_timezone)."""
        if self.birth_timezone is not None:
            return TimezoneDerivation.CERTAIN
        return self._located_timezone[1]

    @cached_property
    def timezone_is_longitude_based(self) -> bool:
        """Whether a derived timezone approximates local time from longitude
        alone (nautical or mean-solar), not from civil timezone rules."""
        return self.birth_timezone is None and is_longitude_based_timezone(
            self.effective_timezone
        )

    @cached_property
    def local_birth_datetime(self) -> dt.datetime:
        """Birth time with the effective timezone attached."""
        return resolve_local_time(
            self.birth_datetime,
            self.effective_timezone,
            self.birth_location,
            on_summer_time=self.on_summer_time,
        )
