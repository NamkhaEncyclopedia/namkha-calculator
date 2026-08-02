"""derive_timezone: settling a birth's timezone once, from the place and date
or from what the user named."""

import datetime as dt
import unittest

from namkha_calculator.tz import Location, TimezoneDerivation, TimezoneProvenance
from namkha_calculator.tz.errors import (
    TimezoneLocationMismatchError,
    TimezoneOffsetOutOfRangeError,
)
from namkha_calculator.zone_derivation import derive_timezone

BERLIN = Location(latitude=52.52, longitude=13.405)
LVIV = Location(latitude=49.8397, longitude=24.0297)
KATHMANDU = Location(latitude=27.7172, longitude=85.3240)
PACIFIC = Location(latitude=0.0, longitude=-140.0)


class TestDerivedFromLocation(unittest.TestCase):
    def test_modern_birth_is_certain(self):
        resolved = derive_timezone(BERLIN, dt.datetime(1985, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Berlin")
        self.assertIs(resolved.derivation, TimezoneDerivation.CERTAIN)
        self.assertIs(resolved.provenance, TimezoneProvenance.LOCATION_DERIVED)

    def test_pre_1970_birth_is_an_estimate(self):
        resolved = derive_timezone(BERLIN, dt.datetime(1935, 6, 15, 12, 0))
        self.assertIs(resolved.derivation, TimezoneDerivation.ESTIMATED)

    def test_moving_borders_are_reported_as_such(self):
        """Lviv changed hands around 1940, so even the country is a guess."""
        resolved = derive_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Warsaw")
        self.assertIs(resolved.derivation, TimezoneDerivation.BORDERS_UNCERTAIN)

    def test_open_water_is_longitude_based(self):
        resolved = derive_timezone(PACIFIC, dt.datetime(1900, 1, 1, 12, 0))
        self.assertTrue(resolved.is_longitude_based)


class TestNamedByTheUser(unittest.TestCase):
    def test_a_chosen_zone_is_certain(self):
        resolved = derive_timezone(
            KATHMANDU, dt.datetime(1985, 6, 15, 12, 0), zone_key="Asia/Kathmandu"
        )
        self.assertEqual(resolved.key, "Asia/Kathmandu")
        self.assertIs(resolved.provenance, TimezoneProvenance.USER_ZONE)
        self.assertIs(resolved.derivation, TimezoneDerivation.CERTAIN)

    def test_a_user_provided_offset_is_kept_as_an_offset(self):
        resolved = derive_timezone(
            KATHMANDU,
            dt.datetime(1985, 6, 15, 12, 0),
            offset=dt.timedelta(hours=5, minutes=45),
        )
        self.assertIsNone(resolved.key)
        self.assertEqual(resolved.offset_seconds, 20700)
        self.assertIs(resolved.provenance, TimezoneProvenance.USER_OFFSET)

    def test_a_user_provided_offset_is_never_longitude_based(self):
        """An offset someone provided is a clock they meant, even where a derived
        one at the same place would have come from longitude."""
        resolved = derive_timezone(
            PACIFIC, dt.datetime(1900, 1, 1, 12, 0), offset=dt.timedelta(hours=-9)
        )
        self.assertFalse(resolved.is_longitude_based)

    def test_zone_and_offset_together_are_refused(self):
        with self.assertRaises(ValueError):
            derive_timezone(
                KATHMANDU,
                dt.datetime(1985, 6, 15, 12, 0),
                zone_key="Asia/Kathmandu",
                offset=dt.timedelta(hours=5, minutes=45),
            )

    def test_summer_time_answer_is_carried_through(self):
        resolved = derive_timezone(
            BERLIN, dt.datetime(1985, 9, 29, 2, 30), on_summer_time=True
        )
        self.assertTrue(resolved.on_summer_time)

    def test_summer_time_answer_is_dropped_outside_a_repeated_hour(self):
        """A birth time with no repeated hour to resolve never records an
        answer, even if one was passed - it would misread as an ambiguity
        that got resolved."""
        resolved = derive_timezone(
            BERLIN, dt.datetime(1985, 6, 15, 12, 0), on_summer_time=True
        )
        self.assertIsNone(resolved.on_summer_time)

    def test_summer_time_answer_is_dropped_for_a_fixed_offset(self):
        """A fixed offset never has a repeated hour to disambiguate."""
        resolved = derive_timezone(
            KATHMANDU,
            dt.datetime(1985, 6, 15, 12, 0),
            offset=dt.timedelta(hours=5, minutes=45),
            on_summer_time=True,
        )
        self.assertIsNone(resolved.on_summer_time)


class TestSuppliedTimezoneIsChecked(unittest.TestCase):
    def test_impossible_offset_is_refused(self):
        with self.assertRaises(TimezoneOffsetOutOfRangeError):
            derive_timezone(
                BERLIN, dt.datetime(1985, 6, 15, 12, 0), offset=dt.timedelta(hours=22)
            )

    def test_offset_far_from_the_birthplace_is_refused(self):
        with self.assertRaises(TimezoneLocationMismatchError):
            derive_timezone(
                BERLIN, dt.datetime(1985, 6, 15, 12, 0), offset=dt.timedelta(hours=-4)
            )

    def test_a_derived_timezone_is_not_checked(self):
        """It came from the place, so it agrees with it by construction - and
        a nautical zone would fail the solar check that a typed one gets."""
        derive_timezone(PACIFIC, dt.datetime(1900, 1, 1, 12, 0))


class TestPlaceFactsAreSettledHere(unittest.TestCase):
    def test_modern_zone_is_recorded_alongside_the_historical_one(self):
        """For a pre-1970 birth the two differ, which is what explains an
        unexpected zone to whoever asks about it later."""
        resolved = derive_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Warsaw")
        self.assertEqual(resolved.modern_zone_key, "Europe/Kyiv")

    def test_gregorian_adoption_date_is_recorded(self):
        resolved = derive_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.gregorian_adoption_date, dt.date(1918, 2, 14))

    def test_birth_details_are_recorded_for_the_binding(self):
        resolved = derive_timezone(BERLIN, dt.datetime(1985, 6, 15, 12, 0))
        self.assertEqual(resolved.for_latitude, BERLIN.latitude)
        self.assertEqual(resolved.for_longitude, BERLIN.longitude)
        self.assertEqual(resolved.for_birth_date, dt.date(1985, 6, 15))


if __name__ == "__main__":
    unittest.main()
