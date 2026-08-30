"""
Integration tests for Month Namkha calculation.

Expected values are worked out by hand from the tables, and the month element,
animal and first date of every case are checked against the Henning output file
for that year. The harmonization sequences are not pinned here: they follow
from the eight center elements, and harmonize_aspects has its own tests.
"""

import unittest
from datetime import datetime

from namkha_calculator.astrology import Animal, Element, Gender, Subject
from namkha_calculator.calculation_notes import CalculationNote
from namkha_calculator.tz import Location
from namkha_calculator.calendar import supported_year_range
from namkha_calculator.harmonizer import Aspect
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha
from namkha_calculator.zone_derivation import resolve_timezone

E = Element

HOUSTON = ("America/Chicago", 29.7604, -95.3698)


def _subject(dt_str: str, tz_name: str, lat: float, lon: float) -> Subject:
    # Gender is unused by Month Namkha but required by Subject
    birth = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
    location = Location(lat, lon)
    return Subject(
        gender=Gender.MALE,
        birth_datetime=birth,
        birth_location=location,
        resolved_timezone=resolve_timezone(location, birth, zone_key=tz_name),
        name=None,
    )


def _centers(result):
    return {ha.name: ha.center for ha in result.harmonized_aspects}


class TestMonthClassicFireTiger(unittest.TestCase):
    """Afternoon of 25 Dec 1973 in Houston. pl_1973.txt gives month 11 of
    Tibetan year 2100 as Fire-male-Tiger starting that date, and it is the
    Tiger month opening the Tiger year 2101, so its mewa is the anchor value 2.

    Life WOOD from the Tiger; body FIRE from (Tiger, Fire); capacity is the
    month element FIRE; fortune METAL from the Tiger. Mewa 2 gives life 8 and
    capacity 5; fortune 8 comes from the year.
    """

    SUBJECT = _subject("25.12.1973 15:36", *HOUSTON)

    EXPECTED_CENTERS = {
        Aspect.LIFE: E.WOOD,
        Aspect.BODY: E.FIRE,
        Aspect.CAPACITY: E.FIRE,
        Aspect.FORTUNE: E.METAL,
        Aspect.MEWA_LIFE: E.METAL,
        Aspect.MEWA_BODY: E.WATER,
        Aspect.MEWA_CAPACITY: E.EARTH,
        Aspect.MEWA_FORTUNE: E.METAL,
    }
    EXPECTED_MEWAS = {
        Aspect.MEWA_LIFE: 8,
        Aspect.MEWA_BODY: 2,
        Aspect.MEWA_CAPACITY: 5,
        Aspect.MEWA_FORTUNE: 8,
    }

    def setUp(self):
        self.result = calculate_namkha(
            NamkhaType.MONTH, self.SUBJECT, CalculationMethod.CLASSIC
        )

    def test_birth_element_animal_and_mewa(self):
        self.assertEqual(
            (
                self.result.birth_element,
                self.result.birth_animal,
                self.result.birth_mewa,
            ),
            (Element.FIRE, Animal.TIGER, 2),
        )

    def test_aspect_centers(self):
        self.assertEqual(_centers(self.result), self.EXPECTED_CENTERS)

    def test_mewa_numbers(self):
        self.assertEqual(self.result.mewa_numbers, self.EXPECTED_MEWAS)


class TestMonthClassicLeapMonth(unittest.TestCase):
    """10 Apr 1924 in Houston falls in the leap month 3 of Tibetan year 2051,
    which pl_1924.txt marks (Intercalary) and gives as Iron-male-Horse starting
    5 Apr 1924. Iron is Metal here.

    Life FIRE from the Horse; body EARTH from (Horse, Metal); capacity is the
    month element METAL; fortune METAL from the Horse. Month mewa 4 gives life
    1 and capacity 7; fortune 5 comes from the Wood Mouse year 2051.
    """

    SUBJECT = _subject("10.04.1924 12:00", *HOUSTON)

    EXPECTED_CENTERS = {
        Aspect.LIFE: E.FIRE,
        Aspect.BODY: E.EARTH,
        Aspect.CAPACITY: E.METAL,
        Aspect.FORTUNE: E.METAL,
        Aspect.MEWA_LIFE: E.METAL,
        Aspect.MEWA_BODY: E.WOOD,
        Aspect.MEWA_CAPACITY: E.FIRE,
        Aspect.MEWA_FORTUNE: E.EARTH,
    }
    EXPECTED_MEWAS = {
        Aspect.MEWA_LIFE: 1,
        Aspect.MEWA_BODY: 4,
        Aspect.MEWA_CAPACITY: 7,
        Aspect.MEWA_FORTUNE: 5,
    }

    def setUp(self):
        self.result = calculate_namkha(
            NamkhaType.MONTH, self.SUBJECT, CalculationMethod.CLASSIC
        )

    def test_birth_element_animal_and_mewa(self):
        self.assertEqual(
            (
                self.result.birth_element,
                self.result.birth_animal,
                self.result.birth_mewa,
            ),
            (Element.METAL, Animal.HORSE, 4),
        )

    def test_aspect_centers(self):
        self.assertEqual(_centers(self.result), self.EXPECTED_CENTERS)

    def test_mewa_numbers(self):
        self.assertEqual(self.result.mewa_numbers, self.EXPECTED_MEWAS)


class TestMonthBeforeDawnOnTheFirstDate(unittest.TestCase):
    """00:30 on 25 Dec 1973 in Houston, hours before that morning's dawn. The
    Tibetan day is still 24 Dec, so the birth belongs to month 10 of Tibetan
    year 2100 (Wood-female-Ox in pl_1973.txt), not to month 11 that begins at
    the dawn of 25 Dec. The birth also falls before the astrological Losar that
    same dawn starts, so its year is 2100, the Water Ox.

    Life EARTH from the Ox; body METAL from (Ox, Wood); capacity is the month
    element WOOD; fortune WATER from the Ox. Month mewa 3 gives life 9 and
    capacity 6; fortune 5 comes from the year.
    """

    SUBJECT = _subject("25.12.1973 00:30", *HOUSTON)

    EXPECTED_CENTERS = {
        Aspect.LIFE: E.EARTH,
        Aspect.BODY: E.METAL,
        Aspect.CAPACITY: E.WOOD,
        Aspect.FORTUNE: E.WATER,
        Aspect.MEWA_LIFE: E.FIRE,
        Aspect.MEWA_BODY: E.WATER,
        Aspect.MEWA_CAPACITY: E.METAL,
        Aspect.MEWA_FORTUNE: E.EARTH,
    }
    EXPECTED_MEWAS = {
        Aspect.MEWA_LIFE: 9,
        Aspect.MEWA_BODY: 3,
        Aspect.MEWA_CAPACITY: 6,
        Aspect.MEWA_FORTUNE: 5,
    }

    def setUp(self):
        self.result = calculate_namkha(
            NamkhaType.MONTH, self.SUBJECT, CalculationMethod.CLASSIC
        )

    def test_birth_element_animal_and_mewa(self):
        self.assertEqual(
            (
                self.result.birth_element,
                self.result.birth_animal,
                self.result.birth_mewa,
            ),
            (Element.WOOD, Animal.OX, 3),
        )

    def test_aspect_centers(self):
        self.assertEqual(_centers(self.result), self.EXPECTED_CENTERS)

    def test_mewa_numbers(self):
        self.assertEqual(self.result.mewa_numbers, self.EXPECTED_MEWAS)


class TestMonthStartBoundaryNote(unittest.TestCase):
    """A birth within minutes of the dawn that starts the month gets the
    period boundary caution, because a small error in the birth time would put
    it in the month before."""

    def _notes(self, dt_str: str) -> set:
        result = calculate_namkha(
            NamkhaType.MONTH, _subject(dt_str, *HOUSTON), CalculationMethod.CLASSIC
        )
        return {item.note for item in result.calculation_notes}

    def test_birth_just_after_the_month_start_is_flagged(self):
        # Month 11 of Tibetan year 2100 starts at the 25 Dec 1973 dawn, 06:48 local.
        self.assertIn(CalculationNote.PERIOD_BOUNDARY, self._notes("25.12.1973 06:53"))

    def test_birth_hours_into_the_month_is_not_flagged(self):
        self.assertNotIn(
            CalculationNote.PERIOD_BOUNDARY, self._notes("25.12.1973 15:36")
        )


class TestMonthMethodAndRange(unittest.TestCase):
    """Month Namkha takes only the Classic method, and covers the same birth
    years as the rest of the library."""

    # Bamako on UTC-1. An Etc/GMT name in POSIX counts hours west of Greenwich as
    # positive, so its sign is the other way round from a UTC offset.
    PLACE = ("Etc/GMT+1", 12.65225, -7.98170)

    def test_cnnr_is_rejected(self):
        subject = _subject("25.12.1973 15:36", *HOUSTON)
        with self.assertRaisesRegex(ValueError, "supports only the CLASSIC"):
            calculate_namkha(NamkhaType.MONTH, subject, CalculationMethod.CNNR)

    def test_extreme_years_calculate(self):
        for year in supported_year_range():
            with self.subTest(year=year):
                subject = _subject(f"15.06.{year} 12:00", *self.PLACE)
                result = calculate_namkha(
                    NamkhaType.MONTH, subject, CalculationMethod.CLASSIC
                )
                self.assertIsInstance(result.birth_element, Element)

    def test_years_outside_range_rejected(self):
        year_min, year_max = supported_year_range()
        for year in (year_min - 1, year_max + 1):
            with self.subTest(year=year):
                subject = _subject(f"15.06.{year} 12:00", *self.PLACE)
                with self.assertRaisesRegex(ValueError, "outside the supported range"):
                    calculate_namkha(
                        NamkhaType.MONTH, subject, CalculationMethod.CLASSIC
                    )
