import re
import unittest
from datetime import datetime, timezone

from namkha_calculator import calendar
from namkha_calculator.astrology import Animal, Element


class TestPhugpaCalendarBasic(unittest.TestCase):
    def test_year_attributes(self):
        test_year = calendar.TibetanYearAttributes(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=0,
        )
        test_date = datetime(year=2024, month=6, day=1, tzinfo=timezone.utc)

        self.assertEqual(test_year, calendar.year_attributes(test_date))

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
        for test_western_year in range(1800, 2601):
            with self.subTest(western_year=test_western_year):
                test_date = datetime(year=test_western_year, month=6, day=1, tzinfo=timezone.utc)
                test_year_attributes = calendar.year_attributes(test_date)
                with open(f"tests/data/Henning/pl_{test_western_year}.txt") as file:
                    file.readline()
                    match = re.match(RE_HENNING_YEAR, file.readline())
                    self.assertEqual(
                        test_year_attributes.element, Element(ELEMENT_NAMES_MAP[match.group(1)])
                    )
                    self.assertEqual(
                        test_year_attributes.animal, Animal(ANIMAL_NAMES_MAP[match.group(2)])
                    )

class TestPhugpaCalendarCornerCases(unittest.TestCase):
    def test_year_element_animal_on_day_before_losar(self):
        test_date_time = datetime(year=2025, month=2, day=27, hour=12, minute=0, second=0, tzinfo=timezone.utc)
        test_year_attributes = calendar.year_attributes(test_date_time)
        self.assertEqual( test_year_attributes.element, Element.WOOD)
        self.assertEqual( test_year_attributes.animal, Animal.DRAGON)
    
    def test_year_element_animal_one_minute_before_losar(self):
        test_date_time = datetime(year=2025, month=2, day=28, hour=6, minute=12, second=23, tzinfo=timezone.utc)
        test_location = calendar.Location(51.477811, -0.001475) # Greenwich observatory
        test_year_attributes = calendar.year_attributes(test_date_time, test_location)
        self.assertEqual( test_year_attributes.element, Element.WOOD)
        self.assertEqual( test_year_attributes.animal, Animal.DRAGON)