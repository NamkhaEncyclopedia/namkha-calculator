import unittest

from hypothesis import given
import hypothesis.strategies as st

from namkha_calculator.core.astrology import Element
from namkha_calculator.core.harmonizer import harmonize_aspects

_element = st.sampled_from(list(Element))


class TestHarmonizeAspectsProperties(unittest.TestCase):
    @given(
        _element, _element, _element, _element, _element, _element, _element, _element
    )
    def test_harmonization_seq_length(
        self,
        life,
        body,
        capacity,
        fortune,
        mewa_life,
        mewa_body,
        mewa_capacity,
        mewa_fortune,
    ):
        aspects = harmonize_aspects(
            life,
            body,
            capacity,
            fortune,
            mewa_life,
            mewa_body,
            mewa_capacity,
            mewa_fortune,
        )
        for aspect in aspects:
            self.assertGreaterEqual(len(aspect.harmonization_seq), 4)
            self.assertLessEqual(len(aspect.harmonization_seq), 6)

    @given(
        _element, _element, _element, _element, _element, _element, _element, _element
    )
    def test_last_item_same_for_all_aspects(
        self,
        life,
        body,
        capacity,
        fortune,
        mewa_life,
        mewa_body,
        mewa_capacity,
        mewa_fortune,
    ):
        aspects = harmonize_aspects(
            life,
            body,
            capacity,
            fortune,
            mewa_life,
            mewa_body,
            mewa_capacity,
            mewa_fortune,
        )
        last_items = {aspect.harmonization_seq[-1] for aspect in aspects}
        self.assertEqual(len(last_items), 1)

    @given(
        _element, _element, _element, _element, _element, _element, _element, _element
    )
    def test_center_not_equal_to_first_seq_item(
        self,
        life,
        body,
        capacity,
        fortune,
        mewa_life,
        mewa_body,
        mewa_capacity,
        mewa_fortune,
    ):
        aspects = harmonize_aspects(
            life,
            body,
            capacity,
            fortune,
            mewa_life,
            mewa_body,
            mewa_capacity,
            mewa_fortune,
        )
        for aspect in aspects:
            self.assertNotEqual(aspect.center, aspect.harmonization_seq[0])

    @given(
        _element, _element, _element, _element, _element, _element, _element, _element
    )
    def test_no_consecutive_duplicates_in_seq(
        self,
        life,
        body,
        capacity,
        fortune,
        mewa_life,
        mewa_body,
        mewa_capacity,
        mewa_fortune,
    ):
        aspects = harmonize_aspects(
            life,
            body,
            capacity,
            fortune,
            mewa_life,
            mewa_body,
            mewa_capacity,
            mewa_fortune,
        )
        for aspect in aspects:
            seq = aspect.harmonization_seq
            for a, b in zip(seq, seq[1:]):
                self.assertNotEqual(a, b)
