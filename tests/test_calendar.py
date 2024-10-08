import re
import unittest
from datetime import datetime

from zoneinfo import ZoneInfo

from namkha_calculator import calendar
from namkha_calculator.astrology import Animal, Element

TEST_LOCATIONS = {
    "Bamako": (calendar.Location(12.65225, -7.98170), "Etc/GMT+0"),
    "Namgyalgar": (calendar.Location(-26.91445, 152.89483), "Australia/Brisbane"),
    "Merigar West": (calendar.Location(42.84905, 11.54506), "Europe/Rome"),
    "Tsegyalgar West": (calendar.Location(23.49032, -109.78180), "America/Mazatlan"),
}


class TestPhugpaCalendarBasic(unittest.TestCase):
    def test_year_attributes(self):
        test_year = calendar.TibetanYearAttributes(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=0,
        )
        test_date = datetime(
            year=2024, month=6, day=1, tzinfo=ZoneInfo(TEST_LOCATIONS["Bamako"][1])
        )
        result_year = calendar.year_attributes(test_date, TEST_LOCATIONS["Bamako"][0])

        # self.assertEqual(
        #     test_year, calendar.year_attributes(test_date, TEST_LOCATIONS["Bamako"][0])
        # )
        self.assertEqual(test_year.tibetan_year_number, result_year.tibetan_year_number)
        self.assertEqual(test_year.animal, result_year.animal)
        self.assertEqual(test_year.element, result_year.element)

    def test_year_element_animal_against_henning(self):
        RE_HENNING_YEAR = r"New Year: \d*, ([A-Z][a-z]*)-[a-z]*-([A-Z][a-z]*)"
        ELEMENT_NAMES_MAP = {
            "Iron": "Metal",
            "Water": "Water",
            "Wood": "Wood",
            "Fire": "Fire",
            "Earth": "Earth",
        }
        ANIMAL_NAMES_MAP = {
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
        for test_western_year in range(1800, 2600):
            with self.subTest(western_year=test_western_year):
                test_date = datetime(
                    year=test_western_year,
                    month=6,
                    day=1,
                    tzinfo=ZoneInfo(TEST_LOCATIONS["Bamako"][1]),
                )
                test_year_attributes = calendar.year_attributes(
                    test_date, TEST_LOCATIONS["Bamako"][0]
                )
                with open(f"tests/data/Henning/pl_{test_western_year}.txt") as file:
                    file.readline()
                    match = re.match(RE_HENNING_YEAR, file.readline())
                    self.assertEqual(
                        test_year_attributes.element,
                        Element(ELEMENT_NAMES_MAP[match.group(1)]),
                    )
                    self.assertEqual(
                        test_year_attributes.animal,
                        Animal(ANIMAL_NAMES_MAP[match.group(2)]),
                    )


class TestPhugpaCalendarCornerCases(unittest.TestCase):
    def test_year_element_animal_on_day_before_losar(self):
        test_date_time = datetime(
            year=2025,
            month=2,
            day=27,
            hour=12,
            minute=0,
            second=0,
            tzinfo=ZoneInfo(TEST_LOCATIONS["Bamako"][1]),
        )
        test_year_attributes = calendar.year_attributes(
            test_date_time, TEST_LOCATIONS["Bamako"][0]
        )
        self.assertEqual(test_year_attributes.element, Element.WOOD)
        self.assertEqual(test_year_attributes.animal, Animal.DRAGON)

    def test_year_element_animal_one_minute_before_losar(self):
        test_date_time = datetime(
            year=2025,
            month=2,
            day=28,
            hour=6,
            minute=12,
            second=23,
            tzinfo=ZoneInfo(TEST_LOCATIONS["Bamako"][1]),
        )
        test_year_attributes = calendar.year_attributes(
            test_date_time, TEST_LOCATIONS["Bamako"][0]
        )
        self.assertEqual(test_year_attributes.element, Element.WOOD)
        self.assertEqual(test_year_attributes.animal, Animal.DRAGON)
