import re
import unittest
from datetime import datetime, timedelta

import pytz
from hypothesis import given, settings
from hypothesis import strategies as st

from namkha_calculator.core.astronomy import Location
from namkha_calculator.core import calendar
from namkha_calculator.core.astrology import Animal, Element


TEST_PLACES = {
    "Bamako": Location(12.65225, -7.98170),  # UTC+0
    "Namgyalgar": Location(-26.91445, 152.89483),
    "Merigar West": Location(42.84905, 11.54506),
    "Tsegyalgar West": Location(23.49032, -109.78180),
}

_RE_HENNING_YEAR = r"New Year: \d+, ([A-Z][a-z]*)-[a-z]*-([A-Z][a-z]*)"
_ELEMENT_NAMES_MAP = {
    "Iron": "Metal", "Water": "Water", "Wood": "Wood", "Fire": "Fire", "Earth": "Earth",
}
_ANIMAL_NAMES_MAP = {
    "Mouse": "Mouse", "Ox": "Ox", "Tiger": "Tiger", "Rabbit": "Hare",
    "Dragon": "Dragon", "Snake": "Snake", "Horse": "Horse", "Sheep": "Sheep",
    "Monkey": "Monkey", "Bird": "Bird", "Dog": "Dog", "Pig": "Boar",
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
        )
        test_date = datetime(year=2024, month=6, day=1, tzinfo=pytz.timezone("UTC"))
        result_year = calendar.year_attributes(test_date, TEST_PLACES["Bamako"])

        self.assertEqual(test_year.tibetan_year_number, result_year.tibetan_year_number)
        self.assertEqual(test_year.animal, result_year.animal)
        self.assertEqual(test_year.element, result_year.element)

    def test_year_attributes_before_losar(self):
        # Jan 5, 2000 is before Losar (~Feb 5, 2000), so belongs to Tibetan year 2126 (= western 1999)
        test_date = datetime(year=2000, month=1, day=5, tzinfo=pytz.timezone("UTC"))
        result = calendar.year_attributes(test_date, TEST_PLACES["Bamako"])

        self.assertEqual(result.tibetan_year_number, 2126)  # 1999 + 127
        self.assertEqual(result.animal, Animal.HARE)
        self.assertEqual(result.element, Element.EARTH)
        self.assertEqual(result.mewa_number, calendar.year_mewa(1999))  # not year_mewa(2000)

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
                test_year_attributes = calendar.year_attributes(
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
    ref_western = draw(st.integers(min_value=metreng_start, max_value=metreng_start + 59))
    return western_year, ref_western


class TestYearWithAnimalAndElementInMetreng(unittest.TestCase):
    @given(_year_and_metreng_ref())
    @settings(max_examples=200)
    def test_against_henning(self, args):
        western_year, ref_western = args
        element, animal = _parse_henning_header(western_year)
        self.assertEqual(
            calendar.year_with_animal_and_element_in_metreng(animal, element, ref_western + 127),
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
                year_attributes = calendar.year_attributes(
                    test_date_time, place_location
                )
                self.assertEqual(year_attributes.element, Element.WATER)
                self.assertEqual(year_attributes.animal, Animal.HARE)

    def test_year_element_animal_one_minute_after_losar(self):
        for place_name, place_location in TEST_PLACES.items():
            with self.subTest(place_name=place_name):
                test_date_time = self.TEST_TWILIGHTS[place_name] + timedelta(minutes=1)
                year_attributes = calendar.year_attributes(
                    test_date_time, place_location
                )
        self.assertEqual(year_attributes.element, Element.WOOD)
        self.assertEqual(year_attributes.animal, Animal.DRAGON)
