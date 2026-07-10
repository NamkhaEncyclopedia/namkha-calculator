import re
import unittest
from datetime import date, datetime, timedelta

import pytz
from hypothesis import given, settings
from hypothesis import strategies as st

from namkha_calculator.astronomy import (
    HIGH_LATITUDE_DAY_START_HOUR,
    Location,
    fixed_offset,
)
from namkha_calculator import calendar
from namkha_calculator.astrology import Animal, Element
from namkha_calculator.skyfield_calculations import (
    ephemeris_date_range,
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


class TestPhugpaCalendarBasic(unittest.TestCase):
    def test_year_attributes(self):
        test_year = calendar.TibetanYearAttributes(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=0,
            boundaries=(),
        )
        test_date = datetime(year=2024, month=6, day=1, tzinfo=pytz.timezone("UTC"))
        result_year = calendar.official_year_attributes(
            test_date, TEST_PLACES["Bamako"]
        )

        self.assertEqual(test_year.tibetan_year_number, result_year.tibetan_year_number)
        self.assertEqual(test_year.animal, result_year.animal)
        self.assertEqual(test_year.element, result_year.element)

    def test_year_attributes_before_losar(self):
        # Jan 5, 2000 is before Losar (~Feb 5, 2000), so belongs to Tibetan year 2126 (= western 1999)
        test_date = datetime(year=2000, month=1, day=5, tzinfo=pytz.timezone("UTC"))
        result = calendar.official_year_attributes(test_date, TEST_PLACES["Bamako"])

        self.assertEqual(result.tibetan_year_number, 2126)  # 1999 + 127
        self.assertEqual(result.animal, Animal.HARE)
        self.assertEqual(result.element, Element.EARTH)
        self.assertEqual(
            result.mewa_number, calendar.year_mewa(1999)
        )  # not year_mewa(2000)

    def test_astrological_losar_against_henning(self):
        tz = pytz.timezone("Etc/GMT+0")
        location = TEST_PLACES["Bamako"]

        for western_year in range(1800, 2599):
            with self.subTest(western_year=western_year):
                tibetan_year = western_year + 127

                with open(f"tests/data/Henning/pl_{western_year}.txt") as f:
                    content = f.read()

                m11 = re.search(r"Tibetan Lunar Month: 11\b", content)
                after = content[m11.end() :]
                next_month = re.search(r"Tibetan Lunar Month:", after)
                month11_section = after[: next_month.start()] if next_month else after
                if re.search(r"^1\. Omitted:", month11_section, re.MULTILINE):
                    day_match = re.search(
                        r"^2: .+; (\d+ \w+ \d{4})", month11_section, re.MULTILINE
                    )
                else:
                    day_match = re.search(
                        r"^1: .+; (\d+ \w+ \d{4})", month11_section, re.MULTILINE
                    )
                henning_date = datetime.strptime(day_match.group(1), "%d %b %Y").date()

                result = calendar.astrological_losar(tibetan_year + 1, tz, location)
                self.assertEqual(result.date(), henning_date)

    def test_year_element_animal_against_henning(self):
        for test_western_year in range(1800, 2599):
            with self.subTest(western_year=test_western_year):
                test_date = datetime(
                    year=test_western_year,
                    month=6,
                    day=1,
                    tzinfo=pytz.timezone("UTC"),
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
        "Bamako": pytz.timezone("Etc/GMT+0").localize(datetime(2024, 2, 10, 6, 34, 3)),
        "Namgyalgar": pytz.timezone("Australia/Brisbane").localize(
            datetime(2024, 2, 10, 5, 3, 58)
        ),
        "Merigar West": pytz.timezone("Europe/Rome").localize(
            datetime(2024, 2, 10, 6, 49, 17)
        ),
        "Tsegyalgar West": pytz.timezone("America/Mazatlan").localize(
            datetime(2024, 2, 10, 6, 31, 55)
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
        t = pytz.timezone("Europe/Madrid").localize(datetime(2024, 2, 10, 0, 30))
        self.assertEqual(calendar.tibetan_day_date(t, self.MADRID), date(2024, 2, 9))

    def test_afternoon_is_same_day(self):
        t = pytz.timezone("Europe/Madrid").localize(datetime(2024, 2, 10, 13, 0))
        self.assertEqual(calendar.tibetan_day_date(t, self.MADRID), date(2024, 2, 10))

    def test_far_west_of_timezone_predawn_is_previous_day(self):
        # 01:00 Beijing time in Urumqi is deep pre-dawn (dawn ~09:00 local clock).
        t = pytz.timezone("Asia/Shanghai").localize(datetime(2024, 2, 10, 1, 0))
        self.assertEqual(calendar.tibetan_day_date(t, self.URUMQI), date(2024, 2, 9))


class TestDayStartFallback(unittest.TestCase):
    def test_polar_day_has_no_dawn_and_falls_back(self):
        # Svalbard at the solstice: sun never drops to -6 deg, so there is no
        # dawn. The lookup returns None instead of raising, and day_start uses
        # the fixed hour.
        place = Location(78.0, 15.0)
        tz = pytz.timezone("Arctic/Longyearbyen")
        d = date(2024, 6, 21)
        self.assertIsNone(morning_civil_twilight(d, tz, place))
        ds = calendar.day_start(d, tz, place)
        self.assertTrue(ds.is_fallback)
        self.assertEqual(ds.at.hour, HIGH_LATITUDE_DAY_START_HOUR)

    def test_high_latitude_summer_below_limit_does_not_raise(self):
        # ~59 N in summer has a brief dip below -6 deg, so a real dawn exists and
        # day_start must resolve it without raising (the old two-boundary search
        # asserted exactly two crossings and could fail here).
        place = Location(59.33, 18.07)  # Stockholm
        tz = pytz.timezone("Europe/Stockholm")
        ds = calendar.day_start(date(2024, 6, 21), tz, place)
        self.assertIsInstance(ds.at, datetime)
        self.assertFalse(ds.is_fallback)

    def test_spring_forward_gap_at_fallback_hour_shifts_past_gap(self):
        # Asia/Baku on 1996-03-31: clocks jumped 05:00 -> 06:00, so 05:00 local
        # does not exist. HIGH_LATITUDE_DAY_START_HOUR = 5 lands exactly in that
        # gap. normalize() must push the result to 06:00 without raising.
        place = Location(65.0, 50.0)  # above LATITUDE_LIMIT -> fixed fallback
        tz = pytz.timezone("Asia/Baku")
        d = date(1996, 3, 31)
        ds = calendar.day_start(d, tz, place)
        self.assertTrue(ds.is_fallback)
        self.assertEqual(ds.at.hour, 6)  # shifted past the 05:00-06:00 gap


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
        self.assertFalse(ds.is_fallback)
        self.assertIsInstance(ds.at, datetime)
        self.assertEqual(ds.at.hour, 19)  # ~19:35 local, hours past the 14 h window

    def test_membership_flips_across_decoupled_dawn(self):
        before = self.TZ.localize(datetime(2024, 6, 21, 10, 0))  # before ~19:35 dawn
        after = self.TZ.localize(datetime(2024, 6, 21, 20, 0))  # after dawn
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

    def test_neighbouring_dates_still_find_real_dawn(self):
        for d in (date(2024, 7, 21), date(2024, 7, 23)):
            with self.subTest(date=d):
                ds = calendar.day_start(d, self.TZ, self.LOC)
                self.assertFalse(ds.is_fallback)

    def test_predawn_after_miss_date_skips_to_real_dawn_date(self):
        # 2024-07-23 00:00:30 lies between the 07-21 23:59:49 dawn and the
        # 07-23 00:00:59 one, so its Tibetan day began on 07-21 - not on the
        # dawnless 07-22, which never starts a Tibetan day.
        t = self.TZ.localize(datetime(2024, 7, 23, 0, 0, 30))
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
        tz = pytz.timezone("Pacific/Apia")
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
