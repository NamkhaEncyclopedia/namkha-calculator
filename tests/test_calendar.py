import re
import unittest
from datetime import date, datetime, timedelta, tzinfo
from functools import lru_cache
from typing import NamedTuple

from hypothesis import given, settings
from hypothesis import strategies as st

from namkha_calculator.tz import (
    HIGH_LATITUDE_DAY_START_HOUR,
    Location,
    fixed_offset,
    zone,
)
from namkha_calculator import calendar
from namkha_calculator.astrology import Animal, Element
from namkha_calculator.skyfield_calculations import (
    date_to_jd,
    ephemeris_date_range,
    jd_to_datetime,
    morning_civil_twilight,
)

TEST_PLACES = {
    "Bamako": Location(12.65225, -7.98170),  # UTC+0
    "Namgyalgar": Location(-26.91445, 152.89483),
    "Merigar West": Location(42.84905, 11.54506),
    "Tsegyalgar West": Location(23.49032, -109.78180),
}

_RE_HENNING_YEAR = r"New Year: \d+, ([A-Z][a-z]*)-[a-z]*-([A-Z][a-z]*)"
_ELEMENT_NAMES_MAP = {
    "Iron": "Metal",
    "Water": "Water",
    "Wood": "Wood",
    "Fire": "Fire",
    "Earth": "Earth",
}
_ANIMAL_NAMES_MAP = {
    "Mouse": "Mouse",
    "Ox": "Ox",
    "Tiger": "Tiger",
    "Rabbit": "Hare",
    "Dragon": "Dragon",
    "Snake": "Snake",
    "Horse": "Horse",
    "Sheep": "Sheep",
    "Monkey": "Monkey",
    "Bird": "Bird",
    "Dog": "Dog",
    "Pig": "Boar",
}


def _parse_henning_header(western_year: int) -> tuple[Element, Animal]:
    with open(f"tests/data/Henning/pl_{western_year}.txt") as f:
        f.readline()
        match = re.match(_RE_HENNING_YEAR, f.readline())
    return (
        Element(_ELEMENT_NAMES_MAP[match.group(1)]),
        Animal(_ANIMAL_NAMES_MAP[match.group(2)]),
    )


# Months 1 to 12. A leap month repeats a number, so no year has a month 13.
MONTH_NUMBERS = range(1, 13)

_RE_HENNING_MONTH = re.compile(
    r"^Tibetan Lunar Month: (\d+)(?: \((Intercalary|Delayed)\))? - "
    r"([A-Z][a-z]*)-[a-z]*-([A-Z][a-z]*)$",
    re.MULTILINE,
)
# A day line starts with the lunar day number and a colon. An omitted day is
# written with a period instead and carries no Western date.
_RE_HENNING_DAY = re.compile(r"^\d+: .+; (\d+ \w+ \d{4})$", re.MULTILINE)


def _month_attributes_at_noon(
    day: date, tz: tzinfo, location: Location
) -> calendar.TibetanMonthAttributes:
    return calendar.classic_month_attributes(
        datetime(day.year, day.month, day.day, 12, 0, tzinfo=tz), location
    )


class HenningMonth(NamedTuple):
    number: int
    is_leap: bool
    element: Element
    animal: Animal
    first_date: date
    last_date: date


@lru_cache(maxsize=None)
def _parse_henning_months(western_year: int) -> list[HenningMonth]:
    """All month sections of one Henning output file, in the order they were printed.

    A leap month comes first and is marked (Intercalary); the regular month of
    the same number follows and is marked (Delayed).
    """
    with open(f"tests/data/Henning/pl_{western_year}.txt") as f:
        content = f.read()
    headers = list(_RE_HENNING_MONTH.finditer(content))
    months = []
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        days = _RE_HENNING_DAY.findall(content[header.end() : end])
        months.append(
            HenningMonth(
                number=int(header.group(1)),
                is_leap=header.group(2) == "Intercalary",
                element=Element(_ELEMENT_NAMES_MAP[header.group(3)]),
                animal=Animal(_ANIMAL_NAMES_MAP[header.group(4)]),
                first_date=datetime.strptime(days[0], "%d %b %Y").date(),
                last_date=datetime.strptime(days[-1], "%d %b %Y").date(),
            )
        )
    return months


class TestPhugpaCalendarBasic(unittest.TestCase):
    def test_year_attributes(self):
        test_year = calendar.TibetanYearAttributes(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=0,
            boundaries=(),
        )
        test_date = datetime(year=2024, month=6, day=1, tzinfo=zone("UTC"))
        result_year = calendar.official_year_attributes(
            test_date, TEST_PLACES["Bamako"]
        )

        self.assertEqual(test_year.tibetan_year_number, result_year.tibetan_year_number)
        self.assertEqual(test_year.animal, result_year.animal)
        self.assertEqual(test_year.element, result_year.element)

    def test_year_attributes_before_losar(self):
        # Jan 5, 2000 is before Losar (~Feb 5, 2000), so belongs to Tibetan year 2126 (= western 1999)
        test_date = datetime(year=2000, month=1, day=5, tzinfo=zone("UTC"))
        result = calendar.official_year_attributes(test_date, TEST_PLACES["Bamako"])

        self.assertEqual(result.tibetan_year_number, 2126)  # 1999 + 127
        self.assertEqual(result.animal, Animal.HARE)
        self.assertEqual(result.element, Element.EARTH)
        self.assertEqual(
            result.mewa_number, calendar.year_mewa(1999)
        )  # not year_mewa(2000)

    def test_astrological_losar_against_henning(self):
        tz = zone("Etc/GMT+0")
        location = TEST_PLACES["Bamako"]

        for western_year in range(1800, 2599):
            with self.subTest(western_year=western_year):
                tibetan_year = western_year + 127
                # The first month 11 printed, which is the leap one when the
                # year has it - the same month astrological_losar starts from.
                month11 = next(
                    month
                    for month in _parse_henning_months(western_year)
                    if month.number == 11
                )
                result = calendar.astrological_losar(tibetan_year + 1, tz, location)
                self.assertEqual(result.date(), month11.first_date)

    def test_year_element_animal_against_henning(self):
        for test_western_year in range(1800, 2599):
            with self.subTest(western_year=test_western_year):
                test_date = datetime(
                    year=test_western_year,
                    month=6,
                    day=1,
                    tzinfo=zone("UTC"),
                )
                test_year_attributes = calendar.official_year_attributes(
                    test_date, TEST_PLACES["Bamako"]
                )
                element, animal = _parse_henning_header(test_western_year)
                self.assertEqual(test_year_attributes.element, element)
                self.assertEqual(test_year_attributes.animal, animal)

    def test_order_tables_match_astrological_cycle(self):
        self.assertEqual(
            calendar.ANIMAL_ORDER,
            (
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
            ),
        )
        self.assertEqual(
            calendar.ELEMENT_ORDER,
            (Element.WOOD, Element.FIRE, Element.EARTH, Element.METAL, Element.WATER),
        )


class TestNearestPreviousYearWithAnimal(unittest.TestCase):
    @given(
        western_year=st.integers(min_value=1800, max_value=1979),
        offset=st.integers(min_value=1, max_value=11),
    )
    @settings(max_examples=180)
    def test_against_henning(self, western_year, offset):
        _, animal = _parse_henning_header(western_year)
        tib_year = western_year + 127
        self.assertEqual(
            calendar.nearest_previous_year_with_animal(tib_year + offset, animal),
            tib_year,
        )


@st.composite
def _year_and_metreng_ref(draw):
    western_year = draw(st.integers(min_value=1800, max_value=2598))
    metreng_start = 1984 + 60 * ((western_year - 1984) // 60)
    ref_western = draw(
        st.integers(min_value=metreng_start, max_value=metreng_start + 59)
    )
    return western_year, ref_western


class TestYearWithAnimalAndElementInMetreng(unittest.TestCase):
    @given(_year_and_metreng_ref())
    @settings(max_examples=200)
    def test_against_henning(self, args):
        western_year, ref_western = args
        element, animal = _parse_henning_header(western_year)
        self.assertEqual(
            calendar.year_with_animal_and_element_in_metreng(
                animal, element, ref_western + 127
            ),
            western_year + 127,
        )


class TestYearWithAnimalAndElementInMetrengEdgeCases(unittest.TestCase):
    def _assert_year(self, animal, element, ref_tib, expected_tib):
        self.assertEqual(
            calendar.year_with_animal_and_element_in_metreng(animal, element, ref_tib),
            expected_tib,
        )

    def test_ref_at_metreng_start_target_is_ref(self):
        # 1984 = Wood-Mouse, start of current Metreng; ref == target
        self._assert_year(Animal.MOUSE, Element.WOOD, 2111, 2111)

    def test_ref_at_metreng_end_target_is_ref(self):
        # 2043 = Water-Boar, end of current Metreng; ref == target
        self._assert_year(Animal.BOAR, Element.WATER, 2170, 2170)

    def test_ref_at_previous_metreng_start_target_is_ref(self):
        # 1924 = Wood-Mouse, start of previous Metreng; must not return 2111
        self._assert_year(Animal.MOUSE, Element.WOOD, 2051, 2051)

    def test_ref_at_previous_metreng_end_target_is_ref(self):
        # 1983 = Water-Boar, end of previous Metreng; must not return 2170
        self._assert_year(Animal.BOAR, Element.WATER, 2110, 2110)

    def test_ref_at_metreng_start_target_at_end(self):
        # ref=1984, target=Water-Boar which falls at 2043 in the same Metreng
        self._assert_year(Animal.BOAR, Element.WATER, 2111, 2170)

    def test_ref_at_metreng_end_target_at_start(self):
        # ref=2043, target=Wood-Mouse which falls at 1984 in the same Metreng
        self._assert_year(Animal.MOUSE, Element.WOOD, 2170, 2111)


class TestPhugpaCalendarCornerCases(unittest.TestCase):
    TEST_TWILIGHTS = {
        "Bamako": datetime(2024, 2, 10, 6, 34, 3, tzinfo=zone("Etc/GMT+0")),
        "Namgyalgar": datetime(
            2024, 2, 10, 5, 3, 58, tzinfo=zone("Australia/Brisbane")
        ),
        "Merigar West": datetime(2024, 2, 10, 6, 49, 17, tzinfo=zone("Europe/Rome")),
        "Tsegyalgar West": datetime(
            2024, 2, 10, 6, 31, 55, tzinfo=zone("America/Mazatlan")
        ),
    }

    def test_year_element_animal_one_minute_before_losar(self):
        for place_name, place_location in TEST_PLACES.items():
            with self.subTest(place_name=place_name):
                test_date_time = self.TEST_TWILIGHTS[place_name] - timedelta(minutes=1)
                year_attributes = calendar.official_year_attributes(
                    test_date_time, place_location
                )
                self.assertEqual(year_attributes.element, Element.WATER)
                self.assertEqual(year_attributes.animal, Animal.HARE)

    def test_year_element_animal_one_minute_after_losar(self):
        for place_name, place_location in TEST_PLACES.items():
            with self.subTest(place_name=place_name):
                test_date_time = self.TEST_TWILIGHTS[place_name] + timedelta(minutes=1)
                year_attributes = calendar.official_year_attributes(
                    test_date_time, place_location
                )
                self.assertEqual(year_attributes.element, Element.WOOD)
                self.assertEqual(year_attributes.animal, Animal.DRAGON)


class TestTibetanDayMembership(unittest.TestCase):
    """A Tibetan day runs dawn-to-dawn: a pre-dawn instant belongs to the
    previous Western date. These cases pin the membership to a timestamp
    comparison in the local frame - a solar-midnight / hour-angle method would
    misclassify pre-dawn births in timezones offset from local solar time."""

    MADRID = Location(40.4168, -3.7038)
    # Urumqi runs on Beijing time (UTC+8) though ~2 h ahead of local solar time.
    URUMQI = Location(43.8256, 87.6168)

    def test_offset_timezone_predawn_is_previous_day(self):
        # 00:30 local sits between civil midnight and solar midnight (~01:29),
        # hours before dawn (~07:20). Tibetan day is the previous date.
        t = datetime(2024, 2, 10, 0, 30, tzinfo=zone("Europe/Madrid"))
        self.assertEqual(calendar.tibetan_day_date(t, self.MADRID), date(2024, 2, 9))

    def test_afternoon_is_same_day(self):
        t = datetime(2024, 2, 10, 13, 0, tzinfo=zone("Europe/Madrid"))
        self.assertEqual(calendar.tibetan_day_date(t, self.MADRID), date(2024, 2, 10))

    def test_far_west_of_timezone_predawn_is_previous_day(self):
        # 01:00 Beijing time in Urumqi is deep pre-dawn (dawn ~09:00 local clock).
        t = datetime(2024, 2, 10, 1, 0, tzinfo=zone("Asia/Shanghai"))
        self.assertEqual(calendar.tibetan_day_date(t, self.URUMQI), date(2024, 2, 9))


class TestDayStartFallback(unittest.TestCase):
    def test_polar_day_has_no_dawn_and_falls_back(self):
        # Svalbard at the solstice: sun never drops to -6 deg, so there is no
        # dawn. The lookup returns None instead of raising, and day_start uses
        # the fixed hour.
        place = Location(78.0, 15.0)
        tz = zone("Arctic/Longyearbyen")
        d = date(2024, 6, 21)
        self.assertIsNone(morning_civil_twilight(d, tz, place))
        ds = calendar.day_start(d, tz, place)
        self.assertEqual(ds.hour, HIGH_LATITUDE_DAY_START_HOUR)

    def test_high_latitude_summer_below_limit_does_not_raise(self):
        # ~59 N in summer has a brief dip below -6 deg, so a real dawn exists and
        # day_start must resolve it without raising (the old two-boundary search
        # asserted exactly two crossings and could fail here).
        place = Location(59.33, 18.07)  # Stockholm
        tz = zone("Europe/Stockholm")
        ds = calendar.day_start(date(2024, 6, 21), tz, place)
        self.assertEqual(ds, morning_civil_twilight(date(2024, 6, 21), tz, place))

    def test_spring_forward_gap_at_fallback_hour_shifts_past_gap(self):
        # Asia/Baku on 1996-03-31: clocks jumped 05:00 -> 06:00, so 05:00 local
        # does not exist. HIGH_LATITUDE_DAY_START_HOUR = 5 lands exactly in that
        # gap. shift_past_clock_gap() must push the result to 06:00 without raising.
        place = Location(65.0, 50.0)  # above LATITUDE_LIMIT -> fixed fallback
        tz = zone("Asia/Baku")
        d = date(1996, 3, 31)
        ds = calendar.day_start(d, tz, place)
        self.assertEqual(ds.hour, 6)  # shifted past the 05:00-06:00 gap


class TestDecoupledOffsetDawn(unittest.TestCase):
    """Here the clock is decoupled from the sun: the manual offset is +12 but the
    longitude gives solar time ~UTC-2, so dawn falls around 19:35 on the local
    clock. Even then day_start must find that real dawn (not the fixed-hour
    fallback), and the Tibetan day must still change exactly at it."""

    # Equator, longitude -30 (solar ~ UTC-2) on clock offset +12: dawn ~19:35 local.
    LOC = Location(0.0, -30.0)
    TZ = fixed_offset(timedelta(hours=12))
    DATE = date(2024, 6, 21)

    def test_real_dawn_found_not_fixed_fallback(self):
        ds = calendar.day_start(self.DATE, self.TZ, self.LOC)
        self.assertEqual(ds, morning_civil_twilight(self.DATE, self.TZ, self.LOC))
        self.assertEqual(ds.hour, 19)  # ~19:35 local, hours past the 14 h window

    def test_membership_flips_across_decoupled_dawn(self):
        before = datetime(2024, 6, 21, 10, 0, tzinfo=self.TZ)  # before ~19:35 dawn
        after = datetime(2024, 6, 21, 20, 0, tzinfo=self.TZ)  # after dawn
        self.assertEqual(calendar.tibetan_day_date(before, self.LOC), date(2024, 6, 20))
        self.assertEqual(calendar.tibetan_day_date(after, self.LOC), date(2024, 6, 21))


class TestDecoupledOffsetMissRaises(unittest.TestCase):
    """An arbitrary fixed offset far enough behind the location's mean solar time pushes dawn
    across clock midnight on ~1 date/year, so that local date has no dawn of its
    own while its neighbors still do. Below LATITUDE_LIMIT, day_start must raise
    a clear ValueError for such a date instead of falling back to the fixed hour.
    No real IANA zone produces this; it needs an artificial fixed offset."""

    # 45N: dawn is 2024-07-21 23:59:49UTC-04:00, then 2024-07-23 00:00:59UTC-04:00 -
    # 2024-07-22 has no dawn of its own. Verified directly against
    # morning_civil_twilight (not mocked).
    LOC = Location(45.0, 0.0)
    TZ = fixed_offset(timedelta(hours=-4))
    MISS_DATE = date(2024, 7, 22)

    def test_search_miss_raises(self):
        self.assertIsNone(morning_civil_twilight(self.MISS_DATE, self.TZ, self.LOC))
        with self.assertRaisesRegex(ValueError, "no dawn"):
            calendar.day_start(self.MISS_DATE, self.TZ, self.LOC)

    def test_neighboring_dates_still_find_real_dawn(self):
        for d in (date(2024, 7, 21), date(2024, 7, 23)):
            with self.subTest(date=d):
                ds = calendar.day_start(d, self.TZ, self.LOC)
                self.assertEqual(ds, morning_civil_twilight(d, self.TZ, self.LOC))

    def test_predawn_after_miss_date_skips_to_real_dawn_date(self):
        # 2024-07-23 00:00:30 lies between the 07-21 23:59:49 dawn and the
        # 07-23 00:00:59 one, so its Tibetan day began on 07-21 - not on the
        # dawnless 07-22, which never starts a Tibetan day.
        t = datetime(2024, 7, 23, 0, 0, 30, tzinfo=self.TZ)
        self.assertEqual(calendar.tibetan_day_date(t, self.LOC), date(2024, 7, 21))

    def test_subject_passable_offset_can_still_miss(self):
        # 59N with a clock only 1.5 h behind solar (within the Subject bounds):
        # midsummer dawn sits at clock midnight, so the miss is still reachable
        # for accepted input and must surface as the same clear error.
        loc = Location(59.0, 0.0)
        tz = fixed_offset(timedelta(hours=-1, minutes=-30))
        with self.assertRaisesRegex(ValueError, "no dawn"):
            calendar.day_start(date(2024, 6, 30), tz, loc)


class TestSkippedDateRaises(unittest.TestCase):
    def test_samoa_dateline_jump_date_raises(self):
        # Samoa skipped 2011-12-30 when it crossed the dateline: the local date
        # has zero duration, so the dawn lookup must reject it clearly instead
        # of leaking skyfield internals.
        tz = zone("Pacific/Apia")
        loc = Location(-13.8333, -171.7667)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            morning_civil_twilight(date(2011, 12, 30), tz, loc)
        for d in (date(2011, 12, 29), date(2011, 12, 31)):
            with self.subTest(date=d):
                self.assertIsNotNone(morning_civil_twilight(d, tz, loc))


class TestFixedOffsetPeriodBoundary(unittest.TestCase):
    """Even with a fixed-offset timezone (no named IANA zone), the Tibetan year
    boundary is still the real computed dawn of Losar day: a birth one minute
    before that dawn falls in the previous Tibetan year, one minute after it in
    the new one."""

    LOC = Location(12.65225, -7.98170)  # Bamako
    TZ = fixed_offset(timedelta(hours=1))

    def test_year_flips_across_fixed_offset_losar(self):
        tibetan_year = 2024 + calendar.TIB_WESTERN_OFFSET  # Losar falls in Feb 2024
        losar = calendar.official_losar(tibetan_year, self.TZ, self.LOC)
        before = calendar.official_year_attributes(
            losar - timedelta(minutes=1), self.LOC
        )
        after = calendar.official_year_attributes(
            losar + timedelta(minutes=1), self.LOC
        )
        self.assertEqual(before.tibetan_year_number, tibetan_year - 1)
        self.assertEqual(after.tibetan_year_number, tibetan_year)


class TestNaiveDatetimeRejected(unittest.TestCase):
    """Calendar entry points require a timezone-aware datetime; a naive one
    must raise TypeError instead of failing deeper in the call chain."""

    LOC = Location(12.65225, -7.98170)  # Bamako
    NAIVE = datetime(2024, 2, 10, 13, 0)

    def test_tibetan_day_date_rejects_naive(self):
        with self.assertRaises(TypeError):
            calendar.tibetan_day_date(self.NAIVE, self.LOC)

    def test_official_year_attributes_rejects_naive(self):
        with self.assertRaises(TypeError):
            calendar.official_year_attributes(self.NAIVE, self.LOC)

    def test_classic_year_attributes_rejects_naive(self):
        with self.assertRaises(TypeError):
            calendar.classic_year_attributes(self.NAIVE, self.LOC)

    def test_classic_month_attributes_rejects_naive(self):
        with self.assertRaises(TypeError):
            calendar.classic_month_attributes(self.NAIVE, self.LOC)


class TestEphemerisEdgeStability(unittest.TestCase):
    """Across the whole supported range the dawn lookup must never raise for any
    offset; a date outside the ephemeris coverage must raise a clear ValueError
    rather than degrade silently."""

    LOC = Location(0.0, -30.0)

    def test_supported_extremes_never_raise(self):
        year_min, year_max = calendar.supported_year_range()
        for year in (year_min, year_max):
            for d in (date(year, 1, 1), date(year, 12, 31)):
                for minutes in (14 * 60, -14 * 60, 1439, -1439):
                    with self.subTest(date=d, minutes=minutes):
                        # Must not raise; None or a datetime are both acceptable.
                        morning_civil_twilight(
                            d, fixed_offset(timedelta(minutes=minutes)), self.LOC
                        )

    def test_out_of_coverage_date_raises_valueerror(self):
        eph_start, eph_end = ephemeris_date_range()
        tz = fixed_offset(timedelta(hours=2))
        for d in (
            eph_start.date() - timedelta(days=5),
            eph_end.date() + timedelta(days=5),
        ):
            with self.subTest(date=d):
                with self.assertRaises(ValueError):
                    morning_civil_twilight(d, tz, self.LOC)


class TestJulianDayDateRoundTrip(unittest.TestCase):
    """date_to_jd is the inverse of jd_to_datetime for whole Julian days."""

    @given(
        st.integers(
            min_value=date_to_jd(date(1800, 1, 1)),
            max_value=date_to_jd(date(2599, 1, 1)),
        )
    )
    @settings(max_examples=200)
    def test_round_trip(self, jd):
        self.assertEqual(date_to_jd(jd_to_datetime(jd).date()), jd)


class TestMonthAgainstHenning(unittest.TestCase):
    """Every month of every Henning output file. The files are read once; the checks
    themselves are Julian day arithmetic, so the whole range stays fast."""

    @classmethod
    def setUpClass(cls):
        cls.months = [
            (western_year + 127, month)
            for western_year in range(1800, 2599)
            for month in _parse_henning_months(western_year)
        ]

    def _month_subtest(self, tibetan_year, month):
        return self.subTest(
            tibetan_year=tibetan_year, month=month.number, leap=month.is_leap
        )

    def _count(self, tibetan_year, month):
        return calendar.to_true_month_count(tibetan_year, month.number, month.is_leap)

    def test_element(self):
        for tibetan_year, month in self.months:
            with self._month_subtest(tibetan_year, month):
                self.assertEqual(
                    calendar.month_element(tibetan_year, month.number), month.element
                )

    def test_animal(self):
        for tibetan_year, month in self.months:
            with self._month_subtest(tibetan_year, month):
                self.assertEqual(calendar.month_animal(month.number), month.animal)

    def test_leap_month_flag(self):
        for tibetan_year, month in self.months:
            with self._month_subtest(tibetan_year, month):
                self.assertEqual(
                    calendar.from_true_month_count(self._count(tibetan_year, month)),
                    (tibetan_year, month.number, month.is_leap),
                )

    def test_first_day(self):
        for tibetan_year, month in self.months:
            with self._month_subtest(tibetan_year, month):
                self.assertEqual(
                    calendar.month_first_julian_day(self._count(tibetan_year, month)),
                    date_to_jd(month.first_date),
                )

    def test_first_and_last_day_belong_to_the_month(self):
        for tibetan_year, month in self.months:
            count = self._count(tibetan_year, month)
            for day in (month.first_date, month.last_date):
                with self._month_subtest(tibetan_year, month):
                    self.assertEqual(
                        calendar.true_month_count_from_julian_day(date_to_jd(day)),
                        count,
                    )


class TestOfficialLosarAgainstHenning(unittest.TestCase):
    """Official Losar starts the first month of the year, so it falls on the
    first day of the first month section - leap month 1 when the year has one."""

    def test_official_losar_dates(self):
        tz = zone("Etc/GMT+0")
        location = TEST_PLACES["Bamako"]
        for western_year in range(1800, 2599):
            with self.subTest(western_year=western_year):
                first_month = _parse_henning_months(western_year)[0]
                losar = calendar.official_losar(western_year + 127, tz, location)
                self.assertEqual(losar.date(), first_month.first_date)


class TestMonthElement(unittest.TestCase):
    """Months 11 and 12 have their own formula, so a year can end with several
    months on one element. Tibetan 2387 (Western 2260) has Water from month 9
    to month 12, which every header in pl_2260.txt confirms."""

    def test_month_8_still_ends_the_metal_pair(self):
        self.assertEqual(calendar.month_element(2387, 8), Element.METAL)

    def test_year_ends_on_four_water_months(self):
        for month_number in (9, 10, 11, 12):
            with self.subTest(month=month_number):
                self.assertEqual(
                    calendar.month_element(2387, month_number), Element.WATER
                )


class TestMonthMewaAnchor(unittest.TestCase):
    """No Phugpa source prints a month mewa, so one anchor carries the whole
    sequence: the Tiger month opening a Tiger astrological year has mewa 2.
    Tibetan year 2149 is the Water Tiger year (Western 2022), and in Phugpa
    numbering its Tiger month is month 11 of 2148. These three are the only absolute
    values; every other mewa test is relative to them."""

    def test_tiger_month(self):
        self.assertEqual(calendar.month_mewa(2148, 11), 2)

    def test_hare_month(self):
        self.assertEqual(calendar.month_mewa(2148, 12), 1)

    def test_dragon_month(self):
        self.assertEqual(calendar.month_mewa(2149, 1), 9)


class TestMonthMewaSequence(unittest.TestCase):
    """Shape of the sequence, independent of where it is anchored."""

    YEARS = range(2100, 2160)

    def test_steps_back_by_one_inside_a_year(self):
        # Each month is compared with the next one, so the last pair is 11 and 12.
        for month_number in list(MONTH_NUMBERS)[:-1]:
            with self.subTest(month=month_number):
                self.assertEqual(
                    calendar.month_mewa(2149, month_number + 1),
                    calendar.amod(calendar.month_mewa(2149, month_number) - 1, 9),
                )

    def test_steps_back_by_one_across_the_year_boundary(self):
        for tibetan_year in self.YEARS:
            with self.subTest(tibetan_year=tibetan_year):
                self.assertEqual(
                    calendar.month_mewa(tibetan_year + 1, 1),
                    calendar.amod(calendar.month_mewa(tibetan_year, 12) - 1, 9),
                )

    def test_repeats_every_three_years(self):
        for tibetan_year in self.YEARS:
            for month_number in MONTH_NUMBERS:
                with self.subTest(tibetan_year=tibetan_year, month=month_number):
                    self.assertEqual(
                        calendar.month_mewa(tibetan_year + 3, month_number),
                        calendar.month_mewa(tibetan_year, month_number),
                    )

    def test_mewa_stays_in_the_triple_of_the_month_animal(self):
        # Vaidurya dkar po allows three mewas per month animal.
        triples = {
            Animal.TIGER: {2, 5, 8},
            Animal.SNAKE: {2, 5, 8},
            Animal.MONKEY: {2, 5, 8},
            Animal.BOAR: {2, 5, 8},
            Animal.HARE: {1, 4, 7},
            Animal.HORSE: {1, 4, 7},
            Animal.BIRD: {1, 4, 7},
            Animal.MOUSE: {1, 4, 7},
            Animal.DRAGON: {3, 6, 9},
            Animal.SHEEP: {3, 6, 9},
            Animal.DOG: {3, 6, 9},
            Animal.OX: {3, 6, 9},
        }
        for tibetan_year in range(1927, 2726):
            for month_number in MONTH_NUMBERS:
                with self.subTest(tibetan_year=tibetan_year, month=month_number):
                    self.assertIn(
                        calendar.month_mewa(tibetan_year, month_number),
                        triples[calendar.month_animal(month_number)],
                    )


class TestClassicMonthAttributes(unittest.TestCase):
    """Resolving the Tibetan month of a birth instant. These call the dawn
    lookup, so they use fixed cases instead of a sweep."""

    LOC = TEST_PLACES["Bamako"]
    TZ = zone("Etc/GMT+0")
    # Month 11 of Tibetan year 2100 begins on 25 Dec 1973 (pl_1973.txt).
    MONTH_11_FIRST_DATE = date(1973, 12, 25)

    def test_boundaries_contain_the_birth_instant(self):
        birth = datetime(1973, 12, 30, 12, 0, tzinfo=self.TZ)
        start, end = calendar.classic_month_attributes(birth, self.LOC).boundaries
        self.assertLessEqual(start, birth)
        self.assertLess(birth, end)

    def _month_start_dawn(self) -> datetime:
        return calendar.day_start(self.MONTH_11_FIRST_DATE, self.TZ, self.LOC)

    def test_month_one_minute_before_month_start_dawn(self):
        # Already the month's first Western date, but the month has not begun.
        birth = self._month_start_dawn() - timedelta(minutes=1)
        attributes = calendar.classic_month_attributes(birth, self.LOC)
        self.assertEqual(attributes.tibetan_month_number, 10)

    def test_month_one_minute_after_month_start_dawn(self):
        birth = self._month_start_dawn() + timedelta(minutes=1)
        attributes = calendar.classic_month_attributes(birth, self.LOC)
        self.assertEqual(attributes.tibetan_month_number, 11)

    def test_boundaries_start_at_month_start_dawn(self):
        birth = self._month_start_dawn() + timedelta(minutes=1)
        attributes = calendar.classic_month_attributes(birth, self.LOC)
        self.assertEqual(attributes.boundaries[0], self._month_start_dawn())

    def test_consecutive_months_are_contiguous(self):
        first = _month_attributes_at_noon(date(1973, 12, 30), self.TZ, self.LOC)
        second = calendar.classic_month_attributes(
            first.boundaries[1] + timedelta(minutes=1), self.LOC
        )
        self.assertEqual(first.boundaries[1], second.boundaries[0])

    def test_supported_range_extremes_calculate(self):
        year_min, year_max = calendar.supported_year_range()
        for year in (year_min, year_max):
            with self.subTest(year=year):
                # Must not raise.
                _month_attributes_at_noon(date(year, 6, 15), self.TZ, self.LOC)


class TestLeapMonthAttributes(unittest.TestCase):
    """A leap month keeps the number, element, animal and mewa of the regular
    month it precedes, so only is_leap_month separates them. Tibetan year 2051
    has a leap month 3 starting 5 Apr 1924, followed by the regular month 3 on
    4 May 1924 (pl_1924.txt)."""

    LOC = TEST_PLACES["Bamako"]
    TZ = zone("Etc/GMT+0")
    SHARED_ATTRIBUTES = ("tibetan_month_number", "element", "animal", "mewa_number")

    def setUp(self):
        self.leap = _month_attributes_at_noon(date(1924, 4, 10), self.TZ, self.LOC)
        self.regular = _month_attributes_at_noon(date(1924, 5, 10), self.TZ, self.LOC)

    def test_leap_month_is_flagged(self):
        self.assertTrue(self.leap.is_leap_month)

    def test_regular_month_is_not_flagged(self):
        self.assertFalse(self.regular.is_leap_month)

    def test_leap_month_matches_the_regular_month(self):
        for attribute in self.SHARED_ATTRIBUTES:
            with self.subTest(attribute=attribute):
                self.assertEqual(
                    getattr(self.leap, attribute), getattr(self.regular, attribute)
                )
