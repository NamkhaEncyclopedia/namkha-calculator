from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto, unique

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
    local_birth_datetime: datetime
    birth_location: Location
    name: str | None
