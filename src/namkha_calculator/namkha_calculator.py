"""
Main Calculation Module
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from typing import Optional

from .harmonizer import Aspect, AspectName


@unique
class CalculationMethod(Enum):
    RINPOCHE = "Rinpoche"
    CLASSIC = "Classic"


@unique
class NamkhaType(Enum):
    YEAR = "Year"
    MONTH = "Month"
    DAY = "Day"
    HOUR = "Hour"


@unique
class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"


@dataclass
class Subject:
    name: str
    gender: Optional[Gender] = None
    birth_datetime: datetime
    birth_geolocation: ...


@dataclass
class NamkhaCalculationResult:
    subject: Subject
    calculation_method: CalculationMethod
    namkha_type: NamkhaType
    harmonized_aspects: tuple[Aspect, ...]
    mewa_numbers: dict[AspectName, int]


def calculate_namkha(
    namkha_type: NamkhaType, subject: Subject
) -> NamkhaCalculationResult:
    ...