"""resolve_timezone: settling a birth's timezone once, from the place and date
or from what the user named."""

import datetime as dt
import unittest

from namkha_calculator.localization import localize_naive_time
from namkha_calculator.tz import Location, TimezoneDerivation, TimezoneProvenance
from namkha_calculator.tz.errors import (
    TimezoneLocationMismatchError,
    TimezoneOffsetOutOfRangeError,
)
from namkha_calculator.zone_derivation import (
    OFFSET_AHEAD_SOLAR_LIMIT_HOURS,
    OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    _reference_coordinates,
    _zone_key_within_birth_country,
    resolve_timezone,
    offset_solar_gap_hours,
)
from namkha_calculator.zone_derivation.historical_borders import polity_index

BERLIN = Location(latitude=52.52, longitude=13.405)
LVIV = Location(latitude=49.8397, longitude=24.0297)
AARHUS = Location(latitude=56.16, longitude=10.20)
KATHMANDU = Location(latitude=27.7172, longitude=85.3240)
PACIFIC = Location(latitude=0.0, longitude=-140.0)
KANTON = Location(latitude=-2.8, longitude=-171.7)


class TestDerivedFromLocation(unittest.TestCase):
    def test_modern_birth_is_certain(self):
        resolved = resolve_timezone(BERLIN, dt.datetime(1985, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Berlin")
        self.assertIs(resolved.derivation, TimezoneDerivation.CERTAIN)
        self.assertIs(resolved.provenance, TimezoneProvenance.LOCATION_DERIVED)

    def test_pre_1970_birth_is_an_estimate(self):
        resolved = resolve_timezone(BERLIN, dt.datetime(1935, 6, 15, 12, 0))
        self.assertIs(resolved.derivation, TimezoneDerivation.ESTIMATED)

    def test_moving_borders_are_reported_as_such(self):
        """Lviv changed hands around 1940, so even the country is a guess."""
        resolved = resolve_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Warsaw")
        self.assertIs(resolved.derivation, TimezoneDerivation.BORDERS_UNCERTAIN)

    def test_open_water_is_longitude_based(self):
        resolved = resolve_timezone(PACIFIC, dt.datetime(1900, 1, 1, 12, 0))
        self.assertTrue(resolved.is_longitude_based)


class TestHistoricalBorders(unittest.TestCase):
    """A pre-1970 birth gets the time kept by the country that held the place
    in the birth year, not by the country holding it today."""

    def test_lviv_returns_to_soviet_time_after_the_war(self):
        resolved = resolve_timezone(LVIV, dt.datetime(1950, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Kyiv")
        self.assertIs(resolved.derivation, TimezoneDerivation.ESTIMATED)

    def test_lviv_is_on_polish_time_between_the_wars(self):
        resolved = resolve_timezone(LVIV, dt.datetime(1930, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Warsaw")
        self.assertIs(resolved.derivation, TimezoneDerivation.ESTIMATED)

    def test_a_renamed_country_is_not_a_border_change(self):
        """Strasbourg is French today but was German in 1916, so the birth gets
        Berlin's clock rather than Paris's. The maps either side of that year
        name the country 'German Empire' and 'Germany'; both still give Berlin,
        so the rename must not read as the border moving."""
        resolved = resolve_timezone(
            Location(latitude=48.5734, longitude=7.7521), dt.datetime(1916, 7, 1, 12, 0)
        )
        self.assertEqual(resolved.key, "Europe/Berlin")
        self.assertEqual(resolved.modern_zone_key, "Europe/Paris")
        self.assertIs(resolved.derivation, TimezoneDerivation.ESTIMATED)

    def test_a_country_that_never_moved_keeps_its_exact_zone(self):
        """Colorado 1950: the reference city of the polygon zone (Denver) was
        in the same country, so the geographically exact zone stands."""
        resolved = resolve_timezone(
            Location(latitude=39.74, longitude=-104.99), dt.datetime(1950, 6, 15, 12, 0)
        )
        self.assertEqual(resolved.key, "America/Denver")

    def test_a_dutch_birth_keeps_the_dutch_zone(self):
        """Amsterdam was Dutch in 1935, and Europe/Amsterdam is itself a Dutch
        zone. There is nothing to swap, so the birth keeps it.

        What that zone does to the birth time is checked in
        test_timezone_handling.
        """
        resolved = resolve_timezone(
            Location(latitude=52.37, longitude=4.90), dt.datetime(1935, 6, 15, 12, 0)
        )
        self.assertEqual(resolved.key, "Europe/Amsterdam")

    def test_mainland_denmark_keeps_danish_time(self):
        resolved = resolve_timezone(AARHUS, dt.datetime(1938, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Copenhagen")

    def test_a_reference_city_the_map_cannot_place_is_kept(self):
        """Copenhagen's zone.tab coordinates lie on a coast, and the 1938
        snapshot places them in no country. A city the map cannot place has not
        been placed abroad, so it does not rule out the modern zone."""
        copenhagen = _reference_coordinates()["Europe/Copenhagen"]
        self.assertIsNone(polity_index(*copenhagen, 1938))
        self.assertIsNotNone(polity_index(AARHUS.latitude, AARHUS.longitude, 1938))
        self.assertEqual(
            _zone_key_within_birth_country(AARHUS, "Europe/Copenhagen", 1938),
            "Europe/Copenhagen",
        )


class TestNamedByTheUser(unittest.TestCase):
    def test_a_chosen_zone_is_certain(self):
        resolved = resolve_timezone(
            KATHMANDU, dt.datetime(1985, 6, 15, 12, 0), zone_key="Asia/Kathmandu"
        )
        self.assertEqual(resolved.key, "Asia/Kathmandu")
        self.assertIs(resolved.provenance, TimezoneProvenance.USER_ZONE)
        self.assertIs(resolved.derivation, TimezoneDerivation.CERTAIN)

    def test_a_user_provided_offset_is_kept_as_an_offset(self):
        resolved = resolve_timezone(
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
        resolved = resolve_timezone(
            PACIFIC, dt.datetime(1900, 1, 1, 12, 0), offset=dt.timedelta(hours=-9)
        )
        self.assertFalse(resolved.is_longitude_based)

    def test_zone_and_offset_together_are_refused(self):
        with self.assertRaises(ValueError):
            resolve_timezone(
                KATHMANDU,
                dt.datetime(1985, 6, 15, 12, 0),
                zone_key="Asia/Kathmandu",
                offset=dt.timedelta(hours=5, minutes=45),
            )

    def test_summer_time_answer_is_carried_through(self):
        resolved = resolve_timezone(
            BERLIN, dt.datetime(1985, 9, 29, 2, 30), on_summer_time=True
        )
        self.assertTrue(resolved.on_summer_time)

    def test_summer_time_answer_is_dropped_outside_a_repeated_hour(self):
        """A birth time with no repeated hour to resolve never records an
        answer, even if one was passed - it would misread as an ambiguity
        that got resolved."""
        resolved = resolve_timezone(
            BERLIN, dt.datetime(1985, 6, 15, 12, 0), on_summer_time=True
        )
        self.assertIsNone(resolved.on_summer_time)

    def test_summer_time_answer_is_dropped_for_a_fixed_offset(self):
        """A fixed offset never has a repeated hour to disambiguate."""
        resolved = resolve_timezone(
            KATHMANDU,
            dt.datetime(1985, 6, 15, 12, 0),
            offset=dt.timedelta(hours=5, minutes=45),
            on_summer_time=True,
        )
        self.assertIsNone(resolved.on_summer_time)


class TestSuppliedTimezoneIsChecked(unittest.TestCase):
    def test_impossible_offset_is_refused(self):
        with self.assertRaises(TimezoneOffsetOutOfRangeError):
            resolve_timezone(
                BERLIN, dt.datetime(1985, 6, 15, 12, 0), offset=dt.timedelta(hours=22)
            )

    def test_offset_far_from_the_birthplace_is_refused(self):
        with self.assertRaises(TimezoneLocationMismatchError):
            resolve_timezone(
                BERLIN, dt.datetime(1985, 6, 15, 12, 0), offset=dt.timedelta(hours=-4)
            )

    def test_a_derived_timezone_is_not_checked(self):
        """One zone, one place, one date, two answers: refused when the caller
        names it, kept when the library works it out."""
        birth = dt.datetime(1930, 6, 15, 12, 0)
        self.assertEqual(resolve_timezone(KANTON, birth).key, "Pacific/Kanton")
        with self.assertRaises(TimezoneLocationMismatchError):
            resolve_timezone(KANTON, birth, zone_key="Pacific/Kanton")


class TestSolarGapBounds(unittest.TestCase):
    """A timezone someone provided is compared against mean solar time at the
    birth longitude. The gap must stay between OFFSET_BEHIND_SOLAR_LIMIT_HOURS
    and OFFSET_AHEAD_SOLAR_LIMIT_HOURS; anything wider is a data-entry error.
    The behind bound is the tighter one, because a clock behind the sun pulls
    dawn toward clock midnight. Every real zone fits inside both."""

    BIRTH = dt.datetime(1985, 6, 15, 12, 0)
    GREENWICH = Location(latitude=45.0, longitude=0.0)

    def test_far_behind_is_refused(self):
        """At 0 deg longitude solar time is about UTC, so a UTC-4 clock is 4 h
        behind."""
        with self.assertRaisesRegex(ValueError, "behind"):
            resolve_timezone(self.GREENWICH, self.BIRTH, offset=dt.timedelta(hours=-4))

    def test_far_ahead_is_refused(self):
        """The same place on a UTC+4 clock: 4 h ahead, over the +3.5 h bound."""
        with self.assertRaisesRegex(ValueError, "ahead"):
            resolve_timezone(self.GREENWICH, self.BIRTH, offset=dt.timedelta(hours=4))

    def test_moderately_behind_is_accepted(self):
        """1.5 h behind solar is rare but plausible, so it stays allowed."""
        resolved = resolve_timezone(
            self.GREENWICH, self.BIRTH, offset=dt.timedelta(hours=-1, minutes=-30)
        )
        self.assertEqual(resolved.offset_seconds, -5400)

    def test_a_real_wide_zone_is_accepted(self):
        """Urumqi keeps Beijing time, UTC+8 against about 5.8 h of solar time.
        That is the widest mismatch a real clock makes, and it must pass."""
        resolved = resolve_timezone(
            Location(latitude=43.8256, longitude=87.6168),
            self.BIRTH,
            zone_key="Asia/Shanghai",
        )
        self.assertEqual(resolved.key, "Asia/Shanghai")

    def test_the_worst_real_behind_zone_fits_the_bound(self):
        """Danmarkshavn ran UTC-3 at longitude -18.7 from 1916 to 1996: about
        1.76 h behind solar, the deepest any real zone ever went. Its latitude
        skips the check, so the bound is compared against the gap itself."""
        location = Location(latitude=76.7667, longitude=-18.6667)
        birth = dt.datetime(1950, 1, 15, 12, 0)
        resolved = resolve_timezone(location, birth, zone_key="America/Danmarkshavn")
        gap = offset_solar_gap_hours(
            localize_naive_time(birth, resolved.tzinfo, location), location
        )
        self.assertLess(gap, 0)
        self.assertGreater(gap, OFFSET_BEHIND_SOLAR_LIMIT_HOURS)

    def test_a_high_latitude_birth_skips_the_check(self):
        """The South Pole station runs on New Zealand time, a gap far over the
        bound. Above LATITUDE_LIMIT the day starts at a fixed hour, so the gap
        stops mattering and the check is not made."""
        location = Location(latitude=-89.9, longitude=0.0)
        resolved = resolve_timezone(location, self.BIRTH, zone_key="Pacific/Auckland")
        gap = offset_solar_gap_hours(
            localize_naive_time(self.BIRTH, resolved.tzinfo, location), location
        )
        self.assertGreater(abs(gap), OFFSET_AHEAD_SOLAR_LIMIT_HOURS)

    def test_a_day_off_offset_is_refused(self):
        """+22 h at longitude -30 wraps round to almost no solar gap, so only
        the offset range catches this typo for -2."""
        with self.assertRaisesRegex(ValueError, "outside the real-timezone range"):
            resolve_timezone(
                Location(latitude=45.0, longitude=-30.0),
                self.BIRTH,
                offset=dt.timedelta(hours=22),
            )

    def test_the_widest_real_offsets_are_accepted(self):
        """UTC+14 in the Line Islands and UTC-12 at Baker Island are the widest
        civil offsets, and UTC-15:56 at Manila's longitude the widest
        historical one. Each is given at its own longitude, so the offset range
        has to admit all three."""
        cases = (
            (dt.timedelta(hours=14), Location(latitude=1.87, longitude=-157.43)),
            (dt.timedelta(hours=-12), Location(latitude=1.87, longitude=-176.48)),
            (
                dt.timedelta(hours=-15, minutes=-56),
                Location(latitude=14.6, longitude=121.0),
            ),
        )
        for offset, location in cases:
            with self.subTest(offset=offset, longitude=location.longitude):
                resolved = resolve_timezone(location, self.BIRTH, offset=offset)
                self.assertEqual(resolved.offset_seconds, offset.total_seconds())

    def test_summer_time_does_not_count_toward_the_gap(self):
        """Kashgar in summer 1988 sat on China's DST clock, UTC+9, about 3.9 h
        ahead of solar - over the bound if DST counted. The gap is measured
        against standard time, so the birth is accepted."""
        resolved = resolve_timezone(
            Location(latitude=39.4704, longitude=75.9898),
            dt.datetime(1988, 7, 1, 12, 0),
            zone_key="Asia/Shanghai",
        )
        self.assertEqual(resolved.key, "Asia/Shanghai")


class TestPreStandardTimeEra(unittest.TestCase):
    """Before standard time a zone's offset is its city's own solar time. The
    check uses that raw offset, not the birth longitude's mean solar time,
    which would recompute the offset and hide a mismatched zone."""

    ROME = Location(latitude=41.9028, longitude=12.4964)
    MANILA = Location(latitude=14.5995, longitude=120.9842)
    BIRTH = dt.datetime(1700, 6, 15, 12, 0)

    def test_a_zone_from_the_wrong_side_of_the_world_is_refused(self):
        with self.assertRaises(TimezoneLocationMismatchError):
            resolve_timezone(self.ROME, self.BIRTH, zone_key="Asia/Manila")

    def test_the_zone_of_the_birthplace_is_accepted(self):
        resolved = resolve_timezone(self.MANILA, self.BIRTH, zone_key="Asia/Manila")
        self.assertEqual(resolved.key, "Asia/Manila")


class TestPlaceFactsAreResolvedHere(unittest.TestCase):
    def test_modern_zone_is_recorded_alongside_the_historical_one(self):
        """For a pre-1970 birth the two differ, which is what explains an
        unexpected zone to whoever asks about it later."""
        resolved = resolve_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.key, "Europe/Warsaw")
        self.assertEqual(resolved.modern_zone_key, "Europe/Kyiv")

    def test_gregorian_adoption_date_is_recorded(self):
        resolved = resolve_timezone(LVIV, dt.datetime(1940, 6, 15, 12, 0))
        self.assertEqual(resolved.gregorian_adoption_date, dt.date(1918, 2, 14))

    def test_birth_details_are_recorded_for_the_binding(self):
        resolved = resolve_timezone(BERLIN, dt.datetime(1985, 6, 15, 12, 0))
        self.assertEqual(resolved.for_latitude, BERLIN.latitude)
        self.assertEqual(resolved.for_longitude, BERLIN.longitude)
        self.assertEqual(resolved.for_birth_date, dt.date(1985, 6, 15))


if __name__ == "__main__":
    unittest.main()
