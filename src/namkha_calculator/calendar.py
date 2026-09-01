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
from functools import lru_cache
from typing import Protocol

from .astrology import Animal, Element
from .localization import localize_naive_time, shift_past_clock_gap
from .tz import HIGH_LATITUDE_DAY_START_HOUR, LATITUDE_LIMIT, Location
from .skyfield_calculations import (
    date_to_jd,
    ephemeris_date_range,
    jd_to_datetime,
    morning_civil_twilight,
)

# Margin (in years) kept inside the ephemeris coverage: the Losar calc reaches
# into adjacent years either side of the birth year, so the usable range is
# narrower than the raw ephemeris span (verified empirically at both ends).
# Note: calendar output is only validated against Henning from 1800 onward.
_YEAR_RANGE_MARGIN = 2

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

# Astrological order of the 12-animal and 5-element cycles
# (enum declaration order, see astrology.py).
ANIMAL_ORDER = tuple(Animal)
ELEMENT_ORDER = tuple(Element)

# Metreng (60-year) cycle constants
TIB_WESTERN_OFFSET = 127  # Tibetan year = Western year + 127
METRENG_CYCLE_LENGTH = 60
FIRST_METRENG_START_WESTERN = (
    1984  # current Metreng begins Western 1984, spans 1984–2043
)


@dataclass(kw_only=True)
class CalendarEntityAttributes:
    element: Element
    animal: Animal
    mewa_number: int
    boundaries: tuple[dt.datetime, ...]


@dataclass(kw_only=True)
class TibetanYearAttributes(CalendarEntityAttributes):
    tibetan_year_number: int


@dataclass(kw_only=True)
class TibetanMonthAttributes(CalendarEntityAttributes):
    tibetan_month_number: int
    is_leap_month: bool


@dataclass(kw_only=True)
class LunarDayAttributes(CalendarEntityAttributes):
    lunar_day_number: int


@dataclass(kw_only=True)
class TibetanHourAttributes(CalendarEntityAttributes):
    start: dt.datetime
    end: dt.datetime


def amod(x: int, n: int) -> int:
    """Same as %, but the result runs 1..n instead of 0..n-1."""
    return x % n or n


def mean_date(day: int, true_month_count: int) -> float:
    return true_month_count * M1 + day * M2 + M0


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


def moon_anomaly(day: int, true_month_count: int) -> float:
    return true_month_count * A1 + day * A2 + A0


def moon_equation(day: int, true_month_count: int) -> float:
    return moon_tab(28 * moon_anomaly(day, true_month_count))


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


def mean_sun(day: int, true_month_count: int) -> float:
    return true_month_count * S1 + day * S2 + S0


def sun_equation(day: int, true_month_count: int) -> float:
    return sun_tab(12.0 * (mean_sun(day, true_month_count) - 1.0 / 4))


def true_date(day: int, true_month_count: int) -> float:
    return (
        mean_date(day, true_month_count)
        + moon_equation(day, true_month_count) / 60
        - sun_equation(day, true_month_count) / 60
    )


def from_true_month_count(true_month_count: int) -> tuple[int, int, bool]:
    """
    Figures out the Tibetan year number, month number within the year, and whether
    this is a leap month, from a "true month count" number.  See Svante Janson,
    "Tibetan Calendar Mathematics", p.8 ff.
    Returns: (year, month, is_leap_month)
    """
    x = math.ceil(12 * S1 * true_month_count + ALPHA)
    month_number = amod(x, 12)
    year_number = (x - month_number) // 12 + Y0 + TIB_WESTERN_OFFSET
    is_leap_month = math.ceil(12 * S1 * (true_month_count + 1) + ALPHA) == x
    return year_number, month_number, is_leap_month


def to_true_month_count(
    year_number: int, month_number: int, is_leap_month: bool
) -> int:
    """
    This is the reverse of from_true_month_count(): from a Tibetan year, month number
    and leap month indicator, calculates the "true month count" based on the epoch.
    """
    year_number -= TIB_WESTERN_OFFSET
    leap_factor = 1 if is_leap_month else 0
    return math.floor(
        (12 * (year_number - Y0) + month_number - ALPHA - (1 - 12 * S1) * leap_factor)
        / (12 * S1)
    )


def month_first_julian_day(true_month_count: int) -> int:
    """Julian day the first day of a Tibetan month falls on.

    Day 0 is not a calendar day. Lunar days carry the numbers 1 to 30, and day
    0 names the start of the month itself. Janson, "Tibetan Calendar
    Mathematics", section "Astronomical functions", describes it: a hand
    calculation first works out the mean values for the start of the month,
    which is day 0, then moves forward to the day it wants. Day 1 follows day
    0, so the month starts one day after day 0. This holds when lunar day 1 is
    omitted, and when day 30 of the month before is omitted.
    """
    return 1 + math.floor(true_date(0, true_month_count))


def true_month_count_from_julian_day(jd: int) -> int:
    """True month count of the Tibetan month that contains a Julian day.

    Janson, "Tibetan Calendar Mathematics", section "Further calculations",
    gives the method: estimate the count, then check the neighboring months.
    The estimate uses mean_date: true_month_count * M1 + day * M2 + M0. It
    gives every month the same length, and true_date corrects it. At the start
    of a month the day part is zero, so solving mean_date for the count gives
    the estimate below.
    """
    true_month_count = round((jd - M0) / M1)
    while month_first_julian_day(true_month_count) > jd:
        true_month_count -= 1
    while month_first_julian_day(true_month_count + 1) <= jd:
        true_month_count += 1
    return true_month_count


class LosarFn(Protocol):
    """Calculates Losar (Tibetan New Year) datetime for a given Tibetan year."""

    def __call__(
        self, year_number: int, tz: dt.tzinfo, location: Location
    ) -> dt.datetime: ...


@lru_cache(maxsize=None)
def supported_year_range() -> tuple[int, int]:
    """Western birth-year range derived from the bundled ephemeris coverage."""
    start, end = ephemeris_date_range()
    return start.year + _YEAR_RANGE_MARGIN, end.year - _YEAR_RANGE_MARGIN


def day_start(date: dt.date, tz: dt.tzinfo, location: Location) -> dt.datetime:
    """Start of the Tibetan day (dawn) for a local date, in the local timezone.

    Real dawn mapped to the start of morning civil twilight. Falls back to a fixed
    local hour at or above LATITUDE_LIMIT.

    The result's tzinfo is the given tz, or, before the location adopted
    standard time, a fixed offset at the location's mean solar time. Convert
    to UTC before comparing with other datetimes.

    Below the limit raises ValueError when the date has no dawn of its own - a
    clock running far enough behind the location's mean solar time drifts dawn
    across clock midnight, skipping ~1 date/year. No real IANA zone does this.
    """
    if abs(location.latitude) < LATITUDE_LIMIT:
        dawn = morning_civil_twilight(date, tz, location)
        if dawn is None:
            raise ValueError(
                f"no dawn on {date}: timezone offset is too far behind the "
                "location's mean solar time"
            )
        local_tz = localize_naive_time(
            dt.datetime.combine(date, dt.time(0, 0, 0)), tz, location
        ).tzinfo
        return dawn.astimezone(local_tz)

    naive_dt = dt.datetime.combine(date, dt.time(HIGH_LATITUDE_DAY_START_HOUR, 0, 0))
    return shift_past_clock_gap(localize_naive_time(naive_dt, tz, location))


def tibetan_day_date(date_time: dt.datetime, location: Location) -> dt.date:
    """Western date of the Tibetan day containing date_time (tz-aware).

    A Tibetan day runs from dawn to dawn, so an instant before a dawn belongs
    to the day that began at the previous dawn. That dawn usually falls on
    the previous Western date, but in rare cases can lie further back when the date in
    between has no dawn of its own (skipped by a timezone offset change, or
    dawn drifted across clock midnight).
    """
    tz = date_time.tzinfo
    if tz is None:
        raise TypeError("date_time must be timezone-aware")
    local_date = date_time.date()
    day_start_at = day_start(local_date, tz, location)
    # Convert both to UTC before comparing. Two datetimes with the same tzinfo
    # compare by wall clock, ignoring fold (PEP 495), so an ambiguous fall-back
    # hour would compare equal to its earlier reading and be misplaced.
    if date_time.astimezone(dt.timezone.utc) >= day_start_at.astimezone(
        dt.timezone.utc
    ):
        return local_date
    candidate = local_date - dt.timedelta(days=1)
    for _ in range(3):
        try:
            day_start(candidate, tz, location)
            return candidate
        except ValueError:
            candidate -= dt.timedelta(days=1)
    raise ValueError(f"no Tibetan day start found within 3 days before {local_date}")


def official_losar(year_number: int, tz: dt.tzinfo, location: Location) -> dt.datetime:
    """
    Calculates the Western datetime for official Losar (Tibetan New Year)
    which starts on the first day of the month of Dragon
    for a given Tibetan year number (e.g. 2137) at a given location and timezone.
    Considers the start of civil twilight at the location to be the start of the day.
    Above LATITUDE_LIMIT uses a fixed start time instead.
    """
    # The month after month 12 is month 1, or leap month 1 when the year has one.
    jd = month_first_julian_day(
        to_true_month_count(year_number - 1, 12, is_leap_month=False) + 1
    )
    losar_date = jd_to_datetime(jd).date()
    return day_start(losar_date, tz, location)


def has_leap_month(year_number: int, month_number: int) -> bool:
    n = to_true_month_count(year_number, month_number, is_leap_month=True)
    y, m, is_leap = from_true_month_count(n)
    return y == year_number and m == month_number and is_leap


def astrological_losar(
    year_number: int, tz: dt.tzinfo, location: Location
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
    jd = month_first_julian_day(to_true_month_count(prev_year, 11, is_leap))
    losar_date = jd_to_datetime(jd).date()
    return day_start(losar_date, tz, location)


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
    return amod(1865 - western_year, 9)


def month_animal(month_number: int) -> Animal:
    """Animal of a Tibetan month. Month 1 is Dragon, month 11 Tiger, month 12 Hare."""
    return ANIMAL_ORDER[(month_number + 3) % 12]


def month_element(tibetan_year_number: int, month_number: int) -> Element:
    """Element of a Tibetan month.

    Janson, "Tibetan Calendar Mathematics", appendix "Further astrological
    calculations", subsection "Attributes for months", gives the formulas.

    Months 11 and 12 use their own formula, so a year can end with several
    months that share one element.
    """
    western_year = tibetan_year_number - TIB_WESTERN_OFFSET
    if month_number <= 10:
        # Janson: (ceil((Y-1)/2) + floor((M+1)/2)) amod 5.
        index = western_year // 2 + (month_number + 1) // 2
    else:
        # Janson: ceil(Y/2) amod 5.
        index = (western_year + 1) // 2
    return ELEMENT_ORDER[amod(index, 5) - 1]


# Where the month mewa numbers are pinned: mewa 2 belongs to the Tiger month
# that opens a Tiger astrological year, which in Phugpa numbering is month 11
# of the year before. Month 11 of Tibetan year 2148 opens Tiger year 2149, and
# 4 is the value that puts mewa 2 there: amod(4 - 3 * 2148 - 11, 9) is 2.
MONTH_MEWA_ANCHOR = 4


def month_mewa(tibetan_year_number: int, month_number: int) -> int:
    """Mewa number 1-9 of a Tibetan month.

    Every month steps the mewa back by one, across the year boundary too. Only
    the year and the month number enter the formula, so a leap month repeats
    the number of the regular month that follows it.

    Janson gives the Tsurphu month number as (3 - (12*Y + M)) amod 9, where Y
    is the Western year. Tsurphu month M+2 carries the animal of Phugpa month
    M, and the mewa belongs to the animal, so this is the same rule rewritten for
    Phugpa month numbers. Phugpa almanacs print no month mewa; these numbers
    always fall inside the triples the Vaidurya dkar po lists for each month
    animal.
    """
    return amod(MONTH_MEWA_ANCHOR - 3 * tibetan_year_number - month_number, 9)


def _year_attributes(
    date_time: dt.datetime, location: Location, losar_fn: LosarFn, initial_year: int
) -> TibetanYearAttributes:
    """
    Resolve the Tibetan year of date_time, its bounding Losar dates and attributes.
    """
    tz = date_time.tzinfo
    if tz is None:
        raise TypeError("date_time must be timezone-aware")
    losar = losar_fn(initial_year, tz, location)
    # Compare UTC instants, not wall clocks (see tibetan_day_date).
    if losar.astimezone(dt.timezone.utc) > date_time.astimezone(dt.timezone.utc):
        # born before this Losar -> previous year, which this Losar ends
        tibetan_year_number = initial_year - 1
        year_start = losar_fn(tibetan_year_number, tz, location)
        year_end = losar
    else:
        tibetan_year_number = initial_year
        year_start = losar
        year_end = losar_fn(initial_year + 1, tz, location)

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


def classic_month_attributes(
    date_time: dt.datetime,
    location: Location,
) -> TibetanMonthAttributes:
    """Resolve the Tibetan month of date_time, its bounding dawns and attributes.

    A Tibetan month starts at the dawn that starts its first day, so a birth
    before that dawn belongs to the month before.
    """
    tz = date_time.tzinfo
    if tz is None:
        raise TypeError("date_time must be timezone-aware")
    count = true_month_count_from_julian_day(
        date_to_jd(tibetan_day_date(date_time, location))
    )
    year_number, month_number, is_leap_month = from_true_month_count(count)
    month_start = jd_to_datetime(month_first_julian_day(count)).date()
    next_month_start = jd_to_datetime(month_first_julian_day(count + 1)).date()

    return TibetanMonthAttributes(
        tibetan_month_number=month_number,
        is_leap_month=is_leap_month,
        animal=month_animal(month_number),
        element=month_element(year_number, month_number),
        mewa_number=month_mewa(year_number, month_number),
        boundaries=(
            day_start(month_start, tz, location),
            day_start(next_month_start, tz, location),
        ),
    )
