"""
Partial implementation of Tibetan Phugpa calendar based on
Svante Janson, "Tibetan Calendar Mathematics" adapted from
Perl library by Roger Espel
(see https://digitaltibetan.github.io/DigitalTibetan/docs/digital_tibetan_tools_calendar.html)
and this Python rewrite: https://github.com/forest-jiang/phugpa-cal
It is tested on Western year range 1800-2598 against the output of C program made by E. Henning,
the author of "Kalachakra and the Tibetan Calendar" book, which Janson's paper is based upon
(see http://kalacakra.org/calendar/os_tib.htm).
"""

import datetime as dt
import math
from dataclasses import dataclass
from typing import Protocol

import pytz

from .astrology import Animal, Element
from .astronomy import HIGH_LATITUDE_DAY_START_HOUR, LATITUDE_LIMIT, Location
from .skyfield_calculations import civil_twilight_boundaries, jd_to_datetime

# Calendrical constants: month calculations
S1 = 65 / 804
Y0 = 806
S0 = 743 / 804
P1 = 77 / 90
P0 = 139 / 180
ALPHA = 1 + 827 / 1005
BETA = 123

# Calendrical constants: day calculations
M1 = 167025 / 5656
M2 = M1 / 30
M0 = 2015501 + 4783 / 5656
S2 = S1 / 30
A1 = 253 / 3528
A2 = 1 / 28
# A2 = 1/28 + 1/105840 # not used see Janson, p. 17, bottom.
A0 = 475 / 3528

# Fixed tables
MOON_TAB = (0, 5, 10, 15, 19, 22, 24, 25)
SUN_TAB = (0, 6, 10, 11)

# Astrological order of the 12-animal and 5-element cycles.
ANIMAL_ORDER = (
    Animal.MOUSE,
    Animal.OX,
    Animal.TIGER,
    Animal.HARE,
    Animal.DRAGON,
    Animal.SNAKE,
    Animal.HORSE,
    Animal.SHEEP,
    Animal.MONKEY,
    Animal.BIRD,
    Animal.DOG,
    Animal.BOAR,
)
ELEMENT_ORDER = (
    Element.WOOD,
    Element.FIRE,
    Element.EARTH,
    Element.METAL,
    Element.WATER,
)
assert set(ANIMAL_ORDER) == set(Animal), "ANIMAL_ORDER must cover every Animal"
assert set(ELEMENT_ORDER) == set(Element), "ELEMENT_ORDER must cover every Element"

# Metreng (60-year) cycle constants
TIB_WESTERN_OFFSET = 127  # Tibetan year = Western year + 127
METRENG_CYCLE_LENGTH = 60
FIRST_METRENG_START_WESTERN = (
    1984  # current Metreng begins Western 1984, spans 1984–2043
)


@dataclass(kw_only=True)
class _CalendarEntityAttributes:
    element: Element
    animal: Animal
    mewa_number: int
    boundaries: tuple[dt.datetime, ...]


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


def mean_date(day: int, month_count: int) -> float:
    return month_count * M1 + day * M2 + M0


def moon_tab_int(i: int) -> int:
    i = i % 28
    if i <= 7:
        return MOON_TAB[i]
    if i <= 14:
        return MOON_TAB[14 - i]
    if i <= 21:
        return -MOON_TAB[i - 14]
    return -MOON_TAB[28 - i]


def moon_tab(i: float) -> float:
    u = moon_tab_int(int(math.ceil(i)))
    d = moon_tab_int(int(math.floor(i)))
    return d + (i - math.floor(i)) * (u - d)


def moon_anomaly(day: int, month_count: int) -> float:
    return month_count * A1 + day * A2 + A0


def moon_equation(day: int, month_count: int) -> float:
    return moon_tab(28 * moon_anomaly(day, month_count))


def sun_tab_int(i: int) -> int:
    i = i % 12
    if i <= 3:
        return SUN_TAB[i]
    if i <= 6:
        return SUN_TAB[6 - i]
    if i <= 9:
        return -SUN_TAB[i - 6]
    return -SUN_TAB[12 - i]


def sun_tab(i: float) -> float:
    """Sun tab, with linear interpolation."""
    u = sun_tab_int(int(math.ceil(i)))
    d = sun_tab_int(int(math.floor(i)))
    return d + (i - math.floor(i)) * (u - d)


def mean_sun(day: int, month_count: int) -> float:
    return month_count * S1 + day * S2 + S0


def sun_equation(day: int, month_count: int) -> float:
    return sun_tab(12.0 * (mean_sun(day, month_count) - 1.0 / 4))


def true_date(day: int, month_count: int) -> float:
    return (
        mean_date(day, month_count)
        + moon_equation(day, month_count) / 60
        - sun_equation(day, month_count) / 60
    )


def from_month_count(month_count: int) -> tuple[int, int, bool]:
    """
    Figures out the Tibetan year number, month number within the year, and whether
    this is a leap month, from a "month count" number.  See Svante Janson,
    "Tibetan Calendar Mathematics", p.8 ff.
    Returns: (year, month, is_leap_month)
    """
    x = math.ceil(12 * S1 * month_count + ALPHA)
    month_number = (x - 1) % 12 + 1
    year_number = (x - month_number) // 12 + Y0 + TIB_WESTERN_OFFSET
    is_leap_month = math.ceil(12 * S1 * (month_count + 1) + ALPHA) == x
    return year_number, month_number, is_leap_month


def to_month_count(year_number: int, month_number: int, is_leap_month: bool) -> int:
    """
    This is the reverse of from_month_count(): from a Tibetan year, month number
    and leap month indicator, calculates the "month count" based on the epoch.
    """
    year_number -= TIB_WESTERN_OFFSET
    leap_factor = 1 if is_leap_month else 0
    return math.floor(
        (12 * (year_number - Y0) + month_number - ALPHA - (1 - 12 * S1) * leap_factor)
        / (12 * S1)
    )


def tibetan_to_julian(
    year_number: int, month_number: int, is_leap_month: bool, tibetan_day: int
) -> float:
    """
    Gives the Julian date for a Tibetan year, month number (leap or not) and
    Tibetan day.

    Does not check that the Tibetan day actually exists:
    - If given the date of a skipped day, will return the same Julian date as the
    day before.
    - If given the date of a duplicate day, returns the Julian date of the second
    of the two.
    """
    n = to_month_count(year_number, month_number, is_leap_month)
    return math.floor(true_date(tibetan_day, n))


class LosarFn(Protocol):
    """Calculates Losar (Tibetan New Year) datetime for a given Tibetan year."""

    def __call__(
        self, year_number: int, pytz_tz: pytz.BaseTzInfo, location: Location
    ) -> dt.datetime: ...


def official_losar(
    year_number: int, pytz_tz: pytz.BaseTzInfo, location: Location
) -> dt.datetime:
    """
    Calculates the Western datetime for official Losar (Tibetan New Year)
    which starts on the first day of the month of Dragon
    for a given Tibetan year number (e.g. 2137) at a given location and timezone.
    Considers the start of civil twilight at the location to be the start of the day.
    Above LATITUDE_LIMIT uses a fixed start time instead.
    """
    jd = 1 + tibetan_to_julian(
        year_number=year_number - 1,
        month_number=12,
        is_leap_month=False,
        tibetan_day=30,
    )
    losar_date = jd_to_datetime(jd).date()
    if abs(location.latitude) >= LATITUDE_LIMIT:
        return pytz_tz.localize(
            dt.datetime.combine(losar_date, dt.time(HIGH_LATITUDE_DAY_START_HOUR, 0, 0))
        )
    return civil_twilight_boundaries(losar_date, pytz_tz, location)[0]


def has_leap_month(year_number: int, month_number: int) -> bool:
    n = to_month_count(year_number, month_number, is_leap_month=True)
    y, m, is_leap = from_month_count(n)
    return y == year_number and m == month_number and is_leap


def astrological_losar(
    year_number: int, pytz_tz: pytz.BaseTzInfo, location: Location
) -> dt.datetime:
    """
    Calculates the Western datetime for astrological Losar (Tibetan New Year)
    which starts on the first day of the month of Tiger
    for a given Tibetan year number (e.g. 2137) at a given location and timezone.
    Considers the start of civil twilight at the location to be the start of the day.
    Above LATITUDE_LIMIT uses a fixed start time instead.
    """
    prev_year = year_number - 1
    is_leap = has_leap_month(prev_year, 11)
    month_count = to_month_count(prev_year, 11, is_leap)
    jd_last_prev = math.floor(true_date(30, month_count - 1))
    jd1 = math.floor(true_date(1, month_count))

    if jd1 == jd_last_prev:
        jd = math.floor(true_date(2, month_count))
    elif jd1 - jd_last_prev == 2:
        jd = jd1 - 1
    else:
        jd = jd1

    losar_date = jd_to_datetime(jd).date()
    if abs(location.latitude) >= LATITUDE_LIMIT:
        return pytz_tz.localize(
            dt.datetime.combine(losar_date, dt.time(HIGH_LATITUDE_DAY_START_HOUR, 0, 0))
        )
    return civil_twilight_boundaries(losar_date, pytz_tz, location)[0]


def year_with_animal_and_element_in_metreng(
    animal: Animal, element: Element, reference_year: int
) -> int:
    """
    Find the Tibetan year in the same Metreng (60-year cycle, epoch western 1984)
    as reference_year that has the given Animal and Element.
    """
    western_ref = reference_year - TIB_WESTERN_OFFSET
    cycle_no = (western_ref - FIRST_METRENG_START_WESTERN) // METRENG_CYCLE_LENGTH
    cycle_start_tib = (
        FIRST_METRENG_START_WESTERN
        + TIB_WESTERN_OFFSET
        + METRENG_CYCLE_LENGTH * cycle_no
    )

    for offset in range(60):
        year = cycle_start_tib + offset
        if (
            ANIMAL_ORDER[(year + 1) % 12] == animal
            and ELEMENT_ORDER[((year - 1) // 2) % 5] == element
        ):
            return year

    # unreachable: LCM(animal=12, element_pair=10)=60, so each combo appears once per cycle
    raise ValueError(f"No year with {animal}/{element} in Metreng cycle {cycle_no}")


def nearest_previous_year_with_animal(year_number: int, animal: Animal) -> int:
    """Return largest Tibetan year number less than year_number with given Animal."""
    target_idx = ANIMAL_ORDER.index(animal)
    current_idx = (year_number + 1) % 12
    offset = (current_idx - target_idx) % 12
    return year_number - offset


def year_mewa(western_year: int) -> int:
    return 9 - (western_year - 1865) % 9


def _year_attributes(
    date_time: dt.datetime, location: Location, losar_fn: LosarFn, initial_year: int
) -> TibetanYearAttributes:
    """
    Resolve the Tibetan year of date_time, its bounding Losar dates and attributes.
    """
    losar = losar_fn(initial_year, date_time.tzinfo, location)
    if losar > date_time:
        # born before this Losar -> previous year, which this Losar ends
        tibetan_year_number = initial_year - 1
        year_start = losar_fn(tibetan_year_number, date_time.tzinfo, location)
        year_end = losar
    else:
        tibetan_year_number = initial_year
        year_start = losar
        year_end = losar_fn(initial_year + 1, date_time.tzinfo, location)

    return TibetanYearAttributes(
        tibetan_year_number=tibetan_year_number,
        animal=ANIMAL_ORDER[(tibetan_year_number + 1) % 12],
        element=ELEMENT_ORDER[((tibetan_year_number - 1) // 2) % 5],
        mewa_number=year_mewa(tibetan_year_number - TIB_WESTERN_OFFSET),
        boundaries=(year_start, year_end),
    )


def official_year_attributes(
    date_time: dt.datetime,
    location: Location,
    losar_fn: LosarFn = official_losar,
) -> TibetanYearAttributes:
    return _year_attributes(
        date_time, location, losar_fn, date_time.year + TIB_WESTERN_OFFSET
    )


def classic_year_attributes(
    date_time: dt.datetime,
    location: Location,
) -> TibetanYearAttributes:
    """Year attributes for Classic method. Astrological year starts earlier than official."""
    return _year_attributes(
        date_time, location, astrological_losar, date_time.year + TIB_WESTERN_OFFSET + 1
    )
