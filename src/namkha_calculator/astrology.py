import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique

import pytz

from .astronomy import Location


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


@dataclass
class Subject:
    gender: Gender
    birth_datetime: dt.datetime  # naive local time
    birth_timezone: pytz.BaseTzInfo
    birth_location: Location
    name: str | None

    def __post_init__(self) -> None:
        if self.birth_datetime.tzinfo is not None:
            raise TypeError("birth_datetime must be naive (no tzinfo)")
        if not isinstance(self.birth_timezone, pytz.BaseTzInfo):
            raise TypeError("birth_timezone must be a pytz timezone")

    @property
    def local_birth_datetime(self) -> dt.datetime:
        return self.birth_timezone.localize(self.birth_datetime, is_dst=False)
