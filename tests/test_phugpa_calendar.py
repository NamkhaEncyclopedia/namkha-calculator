import re
import unittest
from datetime import datetime, timezone

from namkha_calculator import phugpa_calendar as pc
from namkha_calculator.astrology import Animal, Element


class TestPhugpaCalendarBasic(unittest.TestCase):
    def test_year_attributes(self):
        test_year = pc.TibetanYear(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=0,
        )
        test_date = datetime(year=2024, month=6, day=1, tzinfo=timezone.utc)

        self.assertEqual(test_year, pc.year_attributes(test_date))

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
        for test_western_year in range(1800, 2801):
            with self.subTest(western_year=test_western_year):
                test_date = datetime(year=test_western_year, month=6, day=1, tzinfo=timezone.utc)
                test_year_characterisitcs = pc.year_attributes(test_date)
                with open(f"tests/data/Henning/pl_{test_western_year}.txt") as file:
                    file.readline()
                    match = re.match(RE_HENNING_YEAR, file.readline())
                    self.assertEqual(
                        test_year_characterisitcs.element, Element(ELEMENT_NAMES_MAP[match.group(1)])
                    )
                    self.assertEqual(
                        test_year_characterisitcs.animal, Animal(ANIMAL_NAMES_MAP[match.group(2)])
                    )

class TestPhugpaCalendarCornerCases(unittest.TestCase):
    def test_year_element_animal_on_day_before_losar(self):
        test_date = datetime(year=2025, month=2, day=27, hour=12, minute=0, second=0, tzinfo=timezone.utc)
        test_year_characterisitcs = pc.year_attributes(test_date)
        self.assertEqual( test_year_characterisitcs.element, Element.WOOD)
        self.assertEqual( test_year_characterisitcs.animal, Animal.DRAGON)