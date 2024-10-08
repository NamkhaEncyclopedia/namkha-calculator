""" """

import datetime as dt
import math
from dataclasses import dataclass

from .astrology import Animal, Element
from .skyfield_calculations import Location, civil_twilight_boundaries, jd_to_datetime

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

ELEMENT_TABLE = list(Element)
ANIMAL_TABLE = list(Animal)


@dataclass(kw_only=True)
class _CalendarEntityAttributes:
    element: Element
    animal: Animal
    mewa_number: int


@dataclass(kw_only=True)
class TibetanYearAttributes(_CalendarEntityAttributes):
    tibetan_year_number: int


@dataclass(kw_only=True)
class TibetanMonthAttributes(_CalendarEntityAttributes):
    tibetan_month_number: int


@dataclass(kw_only=True)
class LunarDayAttributes(_CalendarEntityAttributes):
    lunar_day_number: int


@dataclass(kw_only=True)
class TibetanHourAttributes(_CalendarEntityAttributes):
    start: dt.datetime
    end: dt.datetime


def mean_date(day, month_count):
    return month_count * M1 + day * M2 + M0


def moon_tab_int(i):
    i = i % 28
    if i <= 7:
        return MOON_TAB[i]
    if i <= 14:
        return MOON_TAB[14 - i]
    if i <= 21:
        return -MOON_TAB[i - 14]
    return -MOON_TAB[28 - i]


def moon_tab(i):
    u = moon_tab_int(int(math.ceil(i)))
    d = moon_tab_int(int(math.floor(i)))
    return d + (i - math.floor(i)) * (u - d)


def moon_anomaly(day, month_count):
    return month_count * A1 + day * A2 + A0


def moon_equation(day, month_count):
    return moon_tab(28 * moon_anomaly(day, month_count))


def sun_tab_int(i):
    i = i % 12
    if i <= 3:
        return SUN_TAB[i]
    if i <= 6:
        return SUN_TAB[6 - i]
    if i <= 9:
        return -SUN_TAB[i - 6]
    return -SUN_TAB[12 - i]


def sun_tab(i):
    """Sun tab, with linear interpolation."""
    u = sun_tab_int(int(math.ceil(i)))
    d = sun_tab_int(int(math.floor(i)))
    return d + (i - math.floor(i)) * (u - d)


def mean_sun(day, month_count):
    return month_count * S1 + day * S2 + S0


def sun_equation(day, month_count):
    return sun_tab(12.0 * (mean_sun(day, month_count) - 1.0 / 4))


def true_date(day: int, month_count: int) -> float:
    return (
        mean_date(day, month_count)
        + moon_equation(day, month_count) / 60
        - sun_equation(day, month_count) / 60
    )


def to_month_count(year_number: int, month_number: int, is_leap_month: bool) -> int:
    """
    This is the reverse of from_month_count(): from a Tibetan year, month number
    and leap month indicator, calculates the "month count" based on the epoch.
    """
    year_number -= 127  # the formulas on Svante's paper use western year numbers
    L = 1 if is_leap_month else 0
    return math.floor(
        (12 * (year_number - Y0) + month_number - ALPHA - (1 - 12 * S1) * L) / (12 * S1)
    )


def tibetan_to_julian(
    year_number: int, month_number: int, is_leap_month: bool, tibetan_day: int
) -> float:
    """
    Gives the Julian date for a Tibetan year, month number (leap or not) and
    Tibetan day.

    Does not check that the tibetan day actually exists:
    - If given the date of a skipped day, will return the same Julian date as the
    day before.
    - If given the date of a duplicate day, returns the Julian date of the second
    of the two.
    """
    n = to_month_count(year_number, month_number, is_leap_month)
    return math.floor(true_date(tibetan_day, n))


def official_losar(year_number: int, location: Location) -> dt.datetime:
    """
    Calculates the Western datetime for official Losar (Tibetan New Year)
    which starts on the first day of the month of Dragon
    for a given Tibetan year number (e.g. 2137) at a given location.
    Considers the start of civil twilight at the location to be the start of the day.
    """
    jd = 1 + tibetan_to_julian(
        year_number=year_number - 1,
        month_number=12,
        is_leap_month=False,
        tibetan_day=30,
    )
    loasar_date = jd_to_datetime(jd).date()
    return civil_twilight_boundaries(loasar_date, location)[0]


def year_mewa(western_year: int) -> int:
    return 9 - (western_year - 1865) % 9


def year_attributes(
    date_time: dt.datetime, location: Location
) -> TibetanYearAttributes:
    tibetan_year_number = date_time.year + 127
    if official_losar(tibetan_year_number, location) > date_time:
        tibetan_year_number -= 1
    animal = ANIMAL_TABLE[(tibetan_year_number + 1) % 12]
    element = ELEMENT_TABLE[int(((tibetan_year_number - 1) / 2) % 5)]
    return TibetanYearAttributes(
        tibetan_year_number=tibetan_year_number,
        animal=Animal(animal),
        element=Element(element),
        mewa_number=year_mewa(date_time.year),
    )
