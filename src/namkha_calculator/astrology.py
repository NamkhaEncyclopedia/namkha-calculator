import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique
from functools import cached_property

from .localization import localize_naive_time
from .tz import Location, ResolvedTimezone, TimezoneDerivation


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
    resolved_timezone: ResolvedTimezone
    name: str | None = None

    def __post_init__(self) -> None:
        """Reject an aware birth time and anything but a ResolvedTimezone
        (TypeError) or a resolved timezone worked out for a different place
        or date (StaleTimezoneError).
        """
        if self.birth_datetime.tzinfo is not None:
            raise TypeError("birth_datetime must be naive (no tzinfo)")
        if not isinstance(self.resolved_timezone, ResolvedTimezone):
            raise TypeError(
                "resolved_timezone must be a ResolvedTimezone, not a timezone "
                "object; build one with "
                "namkha_calculator.zone_derivation.resolve_timezone(...)"
            )
        self.resolved_timezone.assert_binds(self.birth_location, self.birth_datetime)

    @property
    def effective_timezone(self) -> dt.tzinfo:
        """Timezone used in calculation."""
        return self.resolved_timezone.tzinfo

    @property
    def timezone_derivation(self) -> TimezoneDerivation:
        """How sure that timezone is."""
        return self.resolved_timezone.derivation

    @property
    def timezone_is_longitude_based(self) -> bool:
        """Whether the timezone approximates local time from longitude alone
        (nautical or mean-solar), not from civil timezone rules."""
        return self.resolved_timezone.is_longitude_based

    @cached_property
    def local_birth_datetime(self) -> dt.datetime:
        """Birth time with the timezone attached."""
        return localize_naive_time(
            self.birth_datetime,
            self.effective_timezone,
            self.birth_location,
            on_summer_time=self.resolved_timezone.on_summer_time,
        )
