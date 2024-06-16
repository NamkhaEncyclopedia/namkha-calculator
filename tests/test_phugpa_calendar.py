import unittest
from datetime import datetime

from namkha_calculator.astrology import Animal, Element
from namkha_calculator import phugpa_calendar as pc


class TestPhugpaCalendar(unittest.TestCase):
    def test_year_characteristics(self):
        test_year = pc.Year(
            tibetan_year_number=127+2024,
            animal=Animal.DRAGON,
            element=Element.WOOD,
            mewa_number=3,
        )
        test_date = datetime(year=2024, month=6, day=1)

        self.assertEqual(test_year, pc.year_characteristics(test_date))
