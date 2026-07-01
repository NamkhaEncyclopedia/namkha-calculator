import re
import unittest
from datetime import date, datetime, timedelta

import pytz
from hypothesis import given, settings
from hypothesis import strategies as st

from namkha_calculator.astronomy import HIGH_LATITUDE_DAY_START_HOUR, Location
from namkha_calculator import calendar
from namkha_calculator.astrology import Animal, Element
from namkha_calculator.skyfield_calculations import morning_civil_twilight

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
        self.assertTrue(ds.is_fixed)
        self.assertEqual(ds.at.hour, HIGH_LATITUDE_DAY_START_HOUR)

    def test_high_latitude_summer_below_limit_does_not_raise(self):
        # ~59 N in summer has a brief dip below -6 deg, so a real dawn exists and
        # day_start must resolve it without raising (the old two-boundary search
        # asserted exactly two crossings and could fail here).
        place = Location(59.33, 18.07)  # Stockholm
        tz = pytz.timezone("Europe/Stockholm")
        ds = calendar.day_start(date(2024, 6, 21), tz, place)
        self.assertIsInstance(ds.at, datetime)
        self.assertFalse(ds.is_fixed)

    def test_spring_forward_gap_at_fallback_hour_shifts_past_gap(self):
        # Asia/Baku on 1996-03-31: clocks jumped 05:00 -> 06:00, so 05:00 local
        # does not exist. HIGH_LATITUDE_DAY_START_HOUR = 5 lands exactly in that
        # gap. normalize() must push the result to 06:00 without raising.
        place = Location(65.0, 50.0)  # above LATITUDE_LIMIT -> fixed fallback
        tz = pytz.timezone("Asia/Baku")
        d = date(1996, 3, 31)
        ds = calendar.day_start(d, tz, place)
        self.assertTrue(ds.is_fixed)
        self.assertEqual(ds.at.hour, 6)  # shifted past the 05:00-06:00 gap
