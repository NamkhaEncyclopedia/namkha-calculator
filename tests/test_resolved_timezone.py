"""ResolvedTimezone as a value: what it accepts, what it rebuilds, and how it
notices that the birth details moved on."""

import datetime as dt
import pickle
import unittest

from namkha_calculator.tz import (
    Location,
    ResolvedTimezone,
    TimezoneDerivation,
    TimezoneProvenance,
    _MEAN_SOLAR_TZNAME,
)
from namkha_calculator.tz.errors import StaleTimezoneError

BERLIN = Location(latitude=52.52, longitude=13.405)
BIRTH_DATE = dt.date(1985, 6, 15)


def _resolved(**overrides) -> ResolvedTimezone:
    """A named-zone resolution, with fields replaced as a test needs."""
    fields = {
        "key": "Europe/Berlin",
        "offset_seconds": None,
        "provenance": TimezoneProvenance.LOCATION_DERIVED,
        "derivation": TimezoneDerivation.CERTAIN,
        "is_longitude_based": False,
        "on_summer_time": None,
        "for_latitude": BERLIN.latitude,
        "for_longitude": BERLIN.longitude,
        "for_birth_date": BIRTH_DATE,
        "modern_zone_key": "Europe/Berlin",
        "gregorian_adoption_date": dt.date(1700, 3, 1),
    }
    fields.update(overrides)
    return ResolvedTimezone(**fields)


class TestConstruction(unittest.TestCase):
    def test_needs_either_a_key_or_an_offset(self):
        with self.assertRaises(ValueError):
            _resolved(key=None, offset_seconds=None)

    def test_rejects_both_a_key_and_an_offset(self):
        with self.assertRaises(ValueError):
            _resolved(key="Europe/Berlin", offset_seconds=3600)

    def test_is_frozen(self):
        with self.assertRaises(Exception):
            _resolved().key = "Europe/Rome"  # type: ignore[misc]


class TestRebuiltTimezone(unittest.TestCase):
    def test_named_zone_comes_from_the_bundled_tzdata(self):
        tz = _resolved().tzinfo
        self.assertEqual(getattr(tz, "key", None), "Europe/Berlin")

    def test_user_provided_offset_rebuilds_to_the_same_offset(self):
        tz = _resolved(
            key=None,
            offset_seconds=20700,  # +5:45, Kathmandu
            provenance=TimezoneProvenance.USER_OFFSET,
        ).tzinfo
        self.assertEqual(tz.utcoffset(None), dt.timedelta(seconds=20700))

    def test_mean_solar_offset_keeps_its_seconds(self):
        """A longitude-based offset is a whole number of seconds, not of
        minutes. Rebuilding it through fixed_offset would round it away."""
        resolved = _resolved(
            key=None,
            offset_seconds=9725,  # 40.52 deg E, not a whole minute
            is_longitude_based=True,
            derivation=TimezoneDerivation.ESTIMATED,
        )
        self.assertEqual(resolved.tzinfo.utcoffset(None), dt.timedelta(seconds=9725))

    def test_mean_solar_offset_keeps_its_name(self):
        """The name is what tells a reader the offset came from longitude
        rather than from a clock someone kept."""
        resolved = _resolved(
            key=None,
            offset_seconds=9725,
            is_longitude_based=True,
            derivation=TimezoneDerivation.ESTIMATED,
        )
        self.assertEqual(resolved.tzinfo.tzname(None), _MEAN_SOLAR_TZNAME)


class TestUsableAsACacheKey(unittest.TestCase):
    def test_equal_values_are_equal_and_hash_alike(self):
        self.assertEqual(_resolved(), _resolved())
        self.assertEqual(hash(_resolved()), hash(_resolved()))

    def test_a_differing_field_makes_a_different_key(self):
        self.assertNotEqual(_resolved(), _resolved(on_summer_time=True))

    def test_survives_pickling_after_the_timezone_was_built(self):
        resolved = _resolved()
        self.assertIsNotNone(resolved.tzinfo)
        restored = pickle.loads(pickle.dumps(resolved))
        self.assertEqual(restored, resolved)
        self.assertEqual(restored.tzinfo, resolved.tzinfo)


class TestBinding(unittest.TestCase):
    def test_accepts_the_details_it_was_derived_for(self):
        _resolved().assert_binds(BERLIN, dt.datetime(1985, 6, 15, 12, 0))

    def test_ignores_the_time_of_day(self):
        """Only the date can change which timezone applied, so a different
        hour on the same date is not stale."""
        _resolved().assert_binds(BERLIN, dt.datetime(1985, 6, 15, 23, 59))

    def test_rejects_a_moved_birth_date(self):
        with self.assertRaises(StaleTimezoneError):
            _resolved().assert_binds(BERLIN, dt.datetime(1985, 6, 16, 12, 0))

    def test_rejects_a_moved_birthplace(self):
        rome = Location(latitude=41.9028, longitude=12.4964)
        with self.assertRaises(StaleTimezoneError):
            _resolved().assert_binds(rome, dt.datetime(1985, 6, 15, 12, 0))

    def test_tolerates_float_roundtrip_noise_in_the_coordinates(self):
        """A JSON/DB roundtrip can perturb a float in its last bit or so;
        that is not a moved birthplace."""
        noisy = Location(
            latitude=BERLIN.latitude + 1e-9, longitude=BERLIN.longitude - 1e-9
        )
        _resolved().assert_binds(noisy, dt.datetime(1985, 6, 15, 12, 0))

    def test_rejects_a_birthplace_shifted_beyond_the_tolerance(self):
        shifted = Location(latitude=BERLIN.latitude + 0.01, longitude=BERLIN.longitude)
        with self.assertRaises(StaleTimezoneError):
            _resolved().assert_binds(shifted, dt.datetime(1985, 6, 15, 12, 0))

    def test_ignores_the_place_name(self):
        """The name is a label the caller gave; only the coordinates decide
        which timezone applied."""
        renamed = Location(
            latitude=BERLIN.latitude, longitude=BERLIN.longitude, name="Berlin"
        )
        _resolved().assert_binds(renamed, dt.datetime(1985, 6, 15, 12, 0))


if __name__ == "__main__":
    unittest.main()
