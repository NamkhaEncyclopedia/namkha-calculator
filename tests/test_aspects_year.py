import unittest

from hypothesis import given
import hypothesis.strategies as st

from namkha_calculator.core.astrology import Animal, Element
from namkha_calculator.core.calendar import (
    TibetanYearAttributes,
    TIB_WESTERN_OFFSET,
    year_mewa,
)
from namkha_calculator.core.aspects.year import fortune_mewa_cnnr, fortune_mewa_classic


def _make_attrs(animal: Animal, tib_year: int) -> TibetanYearAttributes:
    return TibetanYearAttributes(
        tibetan_year_number=tib_year,
        animal=animal,
        element=Element.EARTH,  # unused by fortune_mewa_cnnr
        mewa_number=year_mewa(tib_year - TIB_WESTERN_OFFSET),
    )


class TestCnnrFortuneMewa(unittest.TestCase):
    def test_dragon_year(self):
        self.assertEqual(fortune_mewa_cnnr(_make_attrs(Animal.DRAGON, 2151)), 5)

    def test_ox_year(self):
        self.assertEqual(fortune_mewa_cnnr(_make_attrs(Animal.OX, 2148)), 8)

    def test_tiger_year(self):
        self.assertEqual(fortune_mewa_cnnr(_make_attrs(Animal.TIGER, 2149)), 2)

    def test_boar_year(self):
        self.assertEqual(fortune_mewa_cnnr(_make_attrs(Animal.BOAR, 2146)), 5)

    # Only {2, 5, 8} (Water/Earth/Metal) are reachable — CNNR_POINT_OF_FORTUNE targets
    # only 4 animals whose tib-year numbers share fixed residues mod 9.
    @given(
        st.sampled_from(list(Animal)),
        st.integers(min_value=2000, max_value=3000),
    )
    def test_mewa_in_valid_range(self, animal: Animal, tib_year: int):
        self.assertIn(fortune_mewa_cnnr(_make_attrs(animal, tib_year)), {2, 5, 8})


class TestClassicFortuneMewa(unittest.TestCase):
    def test_dragon_year(self):
        self.assertEqual(fortune_mewa_classic(_make_attrs(Animal.DRAGON, 2151)), 8)

    def test_ox_year(self):
        self.assertEqual(fortune_mewa_classic(_make_attrs(Animal.OX, 2148)), 8)

    def test_tiger_year(self):
        self.assertEqual(fortune_mewa_classic(_make_attrs(Animal.TIGER, 2149)), 2)

    def test_boar_year(self):
        self.assertEqual(fortune_mewa_classic(_make_attrs(Animal.BOAR, 2146)), 5)

    @given(
        st.sampled_from(list(Animal)),
        st.integers(min_value=2000, max_value=3000),
    )
    def test_mewa_in_valid_range(self, animal: Animal, tib_year: int):
        self.assertIn(fortune_mewa_classic(_make_attrs(animal, tib_year)), {2, 5, 8})
