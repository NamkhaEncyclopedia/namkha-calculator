"""Tests for historical border maps: snapshot selection, point-in-country
lookup, and border stability around a year."""

import unittest

from namkha_calculator.historical_borders import (
    SNAPSHOT_YEARS,
    _point_in_ring,
    nearest_snapshot_year,
    polity_index,
    polity_name,
    snapshots_around,
)

# Verified against the bundled maps: Lviv was Polish between the wars and
# Soviet after WWII; Kyiv was never in interwar Poland.
LVIV = (49.84, 24.03)
WARSAW = (52.25, 21.0)
KYIV = (50.43, 30.52)
AMSTERDAM = (52.37, 4.90)
MID_ATLANTIC = (0.0, -30.0)


class TestSnapshotSelection(unittest.TestCase):
    def test_exact_snapshot_year_selected(self):
        self.assertEqual(nearest_snapshot_year(1938), 1938)

    def test_nearest_snapshot_selected(self):
        self.assertEqual(nearest_snapshot_year(1941), 1938)
        self.assertEqual(nearest_snapshot_year(1942), 1945)

    def test_tie_resolves_to_earlier_snapshot(self):
        self.assertEqual(nearest_snapshot_year(1934), 1930)

    def test_years_outside_range_limited(self):
        self.assertEqual(nearest_snapshot_year(1600), SNAPSHOT_YEARS[0])
        self.assertEqual(nearest_snapshot_year(1969), SNAPSHOT_YEARS[-1])

    def test_snapshots_around_between_maps(self):
        self.assertEqual(snapshots_around(1940), (1938, 1945))

    def test_snapshots_around_own_map_year(self):
        self.assertEqual(snapshots_around(1930), (1930, 1930))

    def test_snapshots_around_limited_at_both_ends(self):
        self.assertEqual(snapshots_around(1700), (1880, 1880))
        self.assertEqual(snapshots_around(1968), (1960, 1960))


class TestPointInRing(unittest.TestCase):
    SQUARE = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0))

    def test_point_inside(self):
        self.assertTrue(_point_in_ring(2.0, 2.0, self.SQUARE))

    def test_point_outside(self):
        self.assertFalse(_point_in_ring(5.0, 2.0, self.SQUARE))
        self.assertFalse(_point_in_ring(-1.0, 2.0, self.SQUARE))


class TestPolityLookup(unittest.TestCase):
    def test_interwar_lviv_is_polish(self):
        self.assertEqual(polity_name(*LVIV, 1930), "Poland")
        self.assertEqual(polity_name(*LVIV, 1938), "Poland")

    def test_postwar_lviv_is_soviet(self):
        self.assertEqual(polity_name(*LVIV, 1945), "USSR")

    def test_kyiv_never_in_interwar_poland(self):
        self.assertNotEqual(polity_name(*KYIV, 1930), "Poland")
        self.assertNotEqual(polity_name(*KYIV, 1938), "Poland")

    def test_amsterdam_stays_dutch(self):
        for year in SNAPSHOT_YEARS:
            with self.subTest(year=year):
                self.assertEqual(polity_name(*AMSTERDAM, year), "Netherlands")

    def test_same_country_shares_feature_index(self):
        self.assertEqual(polity_index(*LVIV, 1930), polity_index(*WARSAW, 1930))

    def test_different_countries_differ_in_feature_index(self):
        self.assertNotEqual(polity_index(*LVIV, 1938), polity_index(*KYIV, 1938))

    def test_open_sea_has_no_country(self):
        self.assertIsNone(polity_index(*MID_ATLANTIC, 1930))


if __name__ == "__main__":
    unittest.main()
