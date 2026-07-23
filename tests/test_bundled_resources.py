"""Missing bundled data files (tzdata, basemaps) raise clear
broken-installation errors, while ordinary bad lookups keep their
usual exception types."""

import unittest
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

from namkha_calculator.astronomy import _zone_tab_rows, zone
from namkha_calculator.historical_borders import _parse_snapshot, _snapshot_features
from namkha_calculator.skyfield_calculations import _get_ephemeris


class MissingResourceTree:
    """Stands in for importlib.resources.files() when the bundled data
    was not packaged: every path is absent."""

    def joinpath(self, *_parts):
        return self

    def is_dir(self):
        return False

    def open(self, *_args, **_kwargs):
        raise FileNotFoundError("missing bundled resource")

    def read_text(self, *_args, **_kwargs):
        raise FileNotFoundError("missing bundled resource")


def missing_resources():
    return mock.patch("importlib.resources.files", return_value=MissingResourceTree())


class TestMissingBundledData(unittest.TestCase):
    def setUp(self):
        zone.cache_clear()
        _zone_tab_rows.cache_clear()
        _snapshot_features.cache_clear()

    def test_missing_tzdata_tree_raises_runtime_error(self):
        with missing_resources():
            with self.assertRaisesRegex(RuntimeError, "reinstall"):
                zone("Europe/Berlin")

    def test_missing_zone_tab_raises_runtime_error(self):
        with missing_resources():
            with self.assertRaisesRegex(RuntimeError, "reinstall"):
                _zone_tab_rows()

    def test_missing_basemap_raises_runtime_error(self):
        with missing_resources():
            with self.assertRaisesRegex(RuntimeError, "reinstall"):
                _snapshot_features(1930)

    def test_missing_ephemeris_raises_runtime_error(self):
        _get_ephemeris.cache_clear()
        with mock.patch("os.path.isfile", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "reinstall"):
                _get_ephemeris()


class TestCorruptBasemap(unittest.TestCase):
    def test_invalid_json_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            _parse_snapshot("{truncated", "world_1930.geojson")

    def test_missing_feature_list_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "no feature list"):
            _parse_snapshot('{"type": "FeatureCollection"}', "world_1930.geojson")

    def test_empty_feature_list_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "no countries"):
            _parse_snapshot('{"features": []}', "world_1930.geojson")


class TestIntactBundledData(unittest.TestCase):
    def test_unknown_zone_key_raises_zone_not_found(self):
        with self.assertRaises(ZoneInfoNotFoundError):
            zone("No/Such/Zone")

    def test_unknown_snapshot_year_raises_value_error(self):
        with self.assertRaises(ValueError):
            _snapshot_features(1901)
