""" """

from datetime import datetime
from dataclasses import dataclass
from .astrology import Animal, Element


@dataclass(kw_only=True)
class _CalendarEntity:
    element: Element
    animal: Animal
    mewa_number: int


@dataclass(kw_only=True)
class Year(_CalendarEntity):
    tibetan_year_number: int


@dataclass(kw_only=True)
class Month(_CalendarEntity):
    tibetan_month_number: int


@dataclass(kw_only=True)
class LunarDay(_CalendarEntity):
    lunar_day_number: int


@dataclass(kw_only=True)
class TibetanHour(_CalendarEntity):
    start: datetime
    end: datetime


def year_characteristics(date: datetime) -> Year:
    return Year(
            tibetan_year_number=127+2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=3,
        )


# calendrical constants: month calculations
S1 = 65 / 804
Y0 = 806
S0 = 743 / 804
P1 = 77 / 90
P0 = 139 / 180
ALPHA = 1 + 827 / 1005
BETA = 123

# calendrical constants: day calculations
M1 = 167025 / 5656
M2 = M1 / 30
M0 = 2015501 + 4783 / 5656
S2 = S1 / 30
A1 = 253 / 3528
A2 = 1 / 28
# A2 = 1/28 + 1/105840 # not used see Janson, p. 17, bottom.
A0 = 475 / 3528

# fixed tables
MOON_TAB = (0, 5, 10, 15, 19, 22, 24, 25)
SUN_TAB = (0, 6, 10, 11)

WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

# use constant    YEAR_ELEMENTS    => qw/Wood Fire Earth Iron Water/
# use constant    YEAR_ANIMALS    => qw/Mouse Ox Tiger Rabbit Dragon Snake Horse Sheep Monkey Bird Dog Pig/
ELEMENT_TABLE = list(Element)
ANIMAL_TABLE = list(Animal)
