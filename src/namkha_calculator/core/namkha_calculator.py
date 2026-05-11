"""
Main Calculation Module
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique, auto

from .harmonizer import HarmonizedAspect, AspectName
from .astronomy import Location
from .calculation_notes import CalculationNoteItem

@unique
class CalculationMethod(Enum):
    CNNR = auto()
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
    harmonized_aspects: tuple[HarmonizedAspect, ...]
    mewa_numbers: dict[AspectName, int]
    calculation_notes: tuple[CalculationNoteItem, ...]


def calculate_namkha(
    namkha_type: NamkhaType, subject: Subject
) -> NamkhaCalculationResult:
    dispatch = {
        NamkhaType.YEAR: _calc_year,
        NamkhaType.MONTH: _calc_month,
        NamkhaType.DAY: _calc_day,
        NamkhaType.HOUR: _calc_hour,
    }
    return dispatch[namkha_type](subject)


def _calc_year(subject: Subject) -> NamkhaCalculationResult:
    raise NotImplementedError


def _calc_month(subject: Subject) -> NamkhaCalculationResult:
    raise NotImplementedError


def _calc_day(subject: Subject) -> NamkhaCalculationResult:
    raise NotImplementedError


def _calc_hour(subject: Subject) -> NamkhaCalculationResult:
    raise NotImplementedError