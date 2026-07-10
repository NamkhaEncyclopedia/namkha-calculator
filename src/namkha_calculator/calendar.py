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
from .astronomy import (
    HIGH_LATITUDE_DAY_START_HOUR,
    LATITUDE_LIMIT,
    Location,
    PytzTimezone,
    localize_standard,
)
from .skyfield_calculations import (
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
        self, year_number: int, pytz_tz: PytzTimezone, location: Location
    ) -> dt.datetime: ...


@lru_cache(maxsize=None)
def supported_year_range() -> tuple[int, int]:
    """Western birth-year range derived from the bundled ephemeris coverage."""
    start, end = ephemeris_date_range()
    return start.year + _YEAR_RANGE_MARGIN, end.year - _YEAR_RANGE_MARGIN


@dataclass(frozen=True)
class DayStart:
    """Resolved start of a Tibetan day, with where it came from."""

    at: dt.datetime
    is_fallback: bool  # fallback fixed hour (True) vs real civil-twilight dawn (False)


def day_start(date: dt.date, pytz_tz: PytzTimezone, location: Location) -> DayStart:
    """Start of the Tibetan day (dawn) for a local date.

    Real dawn mapped to the start of morning civil twilight. Falls back to a fixed
    local hour at or above LATITUDE_LIMIT.

    Below the limit raises ValueError when the date has no dawn of its own - a
    clock running far enough behind the location's mean solar time drifts dawn
    across clock midnight, skipping ~1 date/year. No real IANA zone does this.
    """
    if abs(location.latitude) < LATITUDE_LIMIT:
        dawn = morning_civil_twilight(date, pytz_tz, location)
        if dawn is None:
            raise ValueError(
                f"no dawn on {date}: timezone offset is too far behind the "
                "location's mean solar time"
            )
        return DayStart(dawn.astimezone(pytz_tz), is_fallback=False)

    naive_dt = dt.datetime.combine(date, dt.time(HIGH_LATITUDE_DAY_START_HOUR, 0, 0))
    # normalize() shifts non-existent wall-clock times (DST spring-forward) past the gap.
    fallback_at = pytz_tz.normalize(localize_standard(naive_dt, pytz_tz))
    return DayStart(fallback_at, is_fallback=True)


def tibetan_day_date(date_time: dt.datetime, location: Location) -> dt.date:
    """Western date of the Tibetan day containing date_time (tz-aware).

    A Tibetan day runs from dawn to dawn, so an instant before a dawn belongs
    to the day that began at the previous dawn. That dawn usually falls on
    the previous Western date, but in rare cases can lie further back when the date in
    between has no dawn of its own (skipped by a timezone offset change, or
    dawn drifted across clock midnight).
    """
    local_date = date_time.date()
    if date_time >= day_start(local_date, date_time.tzinfo, location).at:
        return local_date
    candidate = local_date - dt.timedelta(days=1)
    for _ in range(3):
        try:
            day_start(candidate, date_time.tzinfo, location)
            return candidate
        except ValueError:
            candidate -= dt.timedelta(days=1)
    raise ValueError(f"no Tibetan day start found within 3 days before {local_date}")


def official_losar(
    year_number: int, pytz_tz: PytzTimezone, location: Location
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
    return day_start(losar_date, pytz_tz, location).at


def has_leap_month(year_number: int, month_number: int) -> bool:
    n = to_month_count(year_number, month_number, is_leap_month=True)
    y, m, is_leap = from_month_count(n)
    return y == year_number and m == month_number and is_leap


def astrological_losar(
    year_number: int, pytz_tz: PytzTimezone, location: Location
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
    return day_start(losar_date, pytz_tz, location).at


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
