import re
import unittest
from datetime import datetime

from namkha_calculator import phugpa_calendar as pc
from namkha_calculator.astrology import Animal, Element


class TestPhugpaCalendar(unittest.TestCase):
    def test_year_characteristics(self):
        test_year = pc.Year(
            tibetan_year_number=127 + 2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=3,
        )
        test_date = datetime(year=2024, month=6, day=1)

        self.assertEqual(test_year, pc.year_characteristics(test_date))

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
                test_date = datetime(year=test_western_year, month=6, day=1)
                test_year_characterisitcs = pc.year_characteristics(test_date)
                with open(f"tests/data/Henning/pl_{test_western_year}.txt") as file:
                    file.readline()
                    match = re.match(RE_HENNING_YEAR, file.readline())
                    self.assertEqual(
                        test_year_characterisitcs.element, Element(ELEMENT_NAMES_MAP[match.group(1)])
                    )
                    self.assertEqual(
                        test_year_characterisitcs.animal, Animal(ANIMAL_NAMES_MAP[match.group(2)])
                    )
