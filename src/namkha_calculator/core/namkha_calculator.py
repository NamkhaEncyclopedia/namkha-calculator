"""
Main Calculation Module
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique, auto

from .harmonizer import Aspect, AspectName
from .astronomy import Location
from .calculation_notes import CalculationNoteItem

@unique
class CalculationMethod(Enum):
    RINPOCHE = auto()
    CLASSIC = auto()


@unique
class NamkhaType(Enum):
    YEAR = auto()
    MONTH = auto()
    DAY = auto()
    HOUR = auto()


@unique
class Gender(Enum):
    MALE = auto()
    FEMALE = auto()


@dataclass
class Subject:
    name: str
    gender: Gender
    birth_datetime: datetime
    birth_location: Location


@dataclass
class NamkhaCalculationResult:
    subject: Subject
    calculation_method: CalculationMethod
    namkha_type: NamkhaType
    harmonized_aspects: tuple[Aspect, ...]
    mewa_numbers: dict[AspectName, int]
    calculation_notes: tuple[CalculationNoteItem, ...]


def calculate_namkha(
    namkha_type: NamkhaType, subject: Subject
) -> NamkhaCalculationResult:
    ...