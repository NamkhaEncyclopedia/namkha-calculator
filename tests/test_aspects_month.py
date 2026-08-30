import unittest

from namkha_calculator.astrology import Animal, Element
from namkha_calculator.calendar import (
    TIB_WESTERN_OFFSET,
    TibetanMonthAttributes,
    TibetanYearAttributes,
    year_mewa,
)
from namkha_calculator.aspects.month import calculate_mewas_classic


def _month_attrs(mewa_number: int) -> TibetanMonthAttributes:
    # Only mewa_number is read here.
    return TibetanMonthAttributes(
        tibetan_month_number=11,
        is_leap_month=False,
        animal=Animal.TIGER,
        element=Element.FIRE,
        mewa_number=mewa_number,
        boundaries=(),
    )


def _year_attrs(animal: Animal, tib_year: int) -> TibetanYearAttributes:
    return TibetanYearAttributes(
        tibetan_year_number=tib_year,
        animal=animal,
        element=Element.EARTH,
        mewa_number=year_mewa(tib_year - TIB_WESTERN_OFFSET),
        boundaries=(),
    )


class TestMonthMewasClassic(unittest.TestCase):
    """Month mewa 3 in the Wood Tiger year 2101, whose own mewa is 8. The two
    differ, so each aspect shows which one it came from."""

    MONTH = _month_attrs(3)
    YEAR = _year_attrs(Animal.TIGER, 2101)

    def setUp(self):
        self.mewas = calculate_mewas_classic(self.MONTH, self.YEAR)

    def test_body_is_the_month_mewa(self):
        self.assertEqual(self.mewas.body, 3)

    def test_life_and_capacity_are_in_classic_order(self):
        # BODY_MEWA_TO_LIFE_CAPACITY_MEWA[3] is (9, 6); CNNR would swap them.
        self.assertEqual((self.mewas.life, self.mewas.capacity), (9, 6))

    def test_fortune_is_the_year_fortune_mewa(self):
        # Tiger year -> Metal Monkey year 2107 (Western 1980), year mewa 2,
        # whose life mewa is 8.
        self.assertEqual(self.mewas.fortune, 8)
