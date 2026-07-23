"""Timezone handling across the full ephemeris range (1550-2599): full tzdb
history, LMT-era birth-longitude mean time, future DST projection,
location-derived timezones, and the guess/certainty notes."""

import unittest
from datetime import date, datetime, timedelta, tzinfo

from namkha_calculator import calendar
from namkha_calculator.astrology import Gender, Subject
from namkha_calculator.astronomy import (
    Location,
    TimezoneDerivation,
    _mean_solar_timezone,
    _parse_iso6709,
    _parse_zone_tab,
    _zone_tab_rows,
    fixed_offset,
    is_ambiguous_local_time,
    is_longitude_based_timezone,
    is_nonexistent_local_time,
    resolve_local_time,
    uses_local_mean_time,
    zone,
)
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha


def _subject(birth: datetime, location: Location, tz=None) -> Subject:
    return Subject(
        gender=Gender.MALE,
        birth_datetime=birth,
        birth_location=location,
        birth_timezone=tz,
    )


def _solar(longitude: float) -> timedelta:
    return timedelta(seconds=round(longitude * 240))


class FallBackAtDawnZone(tzinfo):
    """Synthetic zone whose only transition is a fall-back from +01:00 to
    +00:00 at 03:00 local on 2018-05-13, making 02:00-03:00 ambiguous.
    """

    SUMMER = timedelta(hours=1)
    WINTER = timedelta(0)
    TRANSITION_UTC = datetime(2018, 5, 13, 2, 0)

    def utcoffset(self, aware_dt):
        if aware_dt is None:
            return self.WINTER
        wall = aware_dt.replace(tzinfo=None)
        if wall < self.TRANSITION_UTC + self.WINTER:
            return self.SUMMER
        if wall >= self.TRANSITION_UTC + self.SUMMER:
            return self.WINTER
        return self.WINTER if aware_dt.fold else self.SUMMER

    def dst(self, aware_dt):
        return self.utcoffset(aware_dt) - self.WINTER

    def tzname(self, aware_dt):
        return "SUM" if self.dst(aware_dt) else "STD"


class AlwaysAmbiguousZone(tzinfo):
    """Synthetic zone where every wall time occurs twice: the earlier reading
    is +01:00, the later one +00:00, and converting from UTC always lands on
    the later reading. The earlier reading of a valid time thus never survives
    shift_past_clock_gap - checking only that reading would wrongly call every time
    skipped."""

    def utcoffset(self, aware_dt):
        if aware_dt is None or aware_dt.fold:
            return timedelta(0)
        return timedelta(hours=1)

    def dst(self, aware_dt):
        return timedelta(0)

    def tzname(self, aware_dt):
        return "AMB"

    def fromutc(self, aware_dt):
        return aware_dt.replace(fold=1)


MANILA = Location(14.5995, 120.9842)
SITKA = Location(57.0531, -135.33)
OSLO = Location(59.9139, 10.7522)
ROME = Location(41.9028, 12.4964)


class TestTzdbHistory(unittest.TestCase):
    def test_manila_1880_is_on_asian_date_side(self):
        """The Philippines crossed the dateline in 1845; pytz reported the
        colonial -15:56 for all of 1845-1901 (a full day off)."""
        subject = _subject(datetime(1880, 6, 15, 12, 0), MANILA, zone("Asia/Manila"))
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(), _solar(MANILA.longitude)
        )

    def test_sitka_1880_is_on_american_date_side(self):
        """Alaska crossed the dateline with the 1867 purchase; pytz reported
        the Russian-era +14:59 until 1901."""
        subject = _subject(datetime(1880, 6, 15, 12, 0), SITKA, zone("America/Sitka"))
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(), _solar(SITKA.longitude)
        )


class TestBirthLongitudeMeanTime(unittest.TestCase):
    """In the tzdb LMT era the offset comes from
    astronomy._birth_longitude_mean_time: the birth longitude's own mean solar
    time (the accurate sub-24h sun time), plus any whole-day offset the zone
    carried from sitting on the far side of the Date Line (pre-1845 Manila:
    +8:04 - 24h = -15:56), so the birth keeps its historical calendar date."""

    def test_manila_1700_keeps_american_date_side(self):
        subject = _subject(datetime(1700, 6, 15, 12, 0), MANILA, zone("Asia/Manila"))
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(),
            _solar(MANILA.longitude) - timedelta(hours=24),
        )

    def test_oslo_1700_uses_birth_longitude_not_reference_city(self):
        """Post-2021 tzdb merges Oslo into Berlin (+0:53:28); the birth
        longitude gives Oslo's own +0:43:01."""
        subject = _subject(datetime(1700, 6, 15, 12, 0), OSLO, zone("Europe/Oslo"))
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(), _solar(OSLO.longitude)
        )

    def test_lmt_era_detected(self):
        self.assertTrue(
            uses_local_mean_time(datetime(1700, 6, 15, 12, 0), zone("Europe/Rome"))
        )

    def test_standard_era_not_lmt(self):
        self.assertFalse(
            uses_local_mean_time(datetime(1985, 6, 15, 12, 0), zone("Europe/Rome"))
        )

    def test_juneau_1860_calculates(self):
        """LMT-era Alaska."""
        juneau = Location(58.3005, -134.4201)
        subject = _subject(datetime(1860, 6, 15, 12, 0), juneau, zone("America/Juneau"))
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertTrue(result.harmonized_aspects)


class TestHistoricalSkippedDate(unittest.TestCase):

    def test_skipped_birth_date_raises_clearly(self):
        subject = _subject(datetime(1844, 12, 31, 10, 0), MANILA, zone("Asia/Manila"))
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_predawn_after_skipped_date_steps_back_past_it(self):
        t = datetime(1845, 1, 1, 3, 0, tzinfo=zone("Asia/Manila"))
        self.assertEqual(calendar.tibetan_day_date(t, MANILA), date(1844, 12, 30))


class TestFutureDstProjection(unittest.TestCase):

    def test_rome_2039_summer_gets_dst(self):
        subject = _subject(datetime(2039, 7, 1, 12, 0), ROME, zone("Europe/Rome"))
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=2))

    def test_post_2037_fall_back_still_ambiguous(self):
        # Last Sunday of October 2040 is the 28th; 02:30 occurs twice - zoneinfo
        # projects the transition
        self.assertTrue(
            is_ambiguous_local_time(datetime(2040, 10, 28, 2, 30), zone("Europe/Rome"))
        )


class TestSummerTimeDisambiguation(unittest.TestCase):
    """A fall-back hour occurs twice; on_summer_time selects the summer or
    winter occurrence by its UTC offset (summer = higher), not by dst()."""

    # Berlin 2023-10-29: fall-back 03:00 -> 02:00, so 02:30 occurs twice.
    BERLIN = Location(52.52, 13.405)
    BERLIN_AMBIGUOUS = datetime(2023, 10, 29, 2, 30)
    # Dublin fall-back is 02:00 -> 01:00; tzdb models winter GMT as negative DST.
    DUBLIN = Location(53.35, -6.26)
    DUBLIN_AMBIGUOUS = datetime(2023, 10, 29, 1, 30)

    def _offset(self, location, tz_key, naive, on_summer_time):
        subject = Subject(
            gender=Gender.MALE,
            birth_datetime=naive,
            birth_location=location,
            birth_timezone=zone(tz_key),
            on_summer_time=on_summer_time,
        )
        return subject.local_birth_datetime.utcoffset()

    def test_berlin_pre_fallback_reading(self):
        self.assertEqual(
            self._offset(self.BERLIN, "Europe/Berlin", self.BERLIN_AMBIGUOUS, True),
            timedelta(hours=2),
        )

    def test_berlin_post_fallback_reading(self):
        self.assertEqual(
            self._offset(self.BERLIN, "Europe/Berlin", self.BERLIN_AMBIGUOUS, False),
            timedelta(hours=1),
        )

    def test_berlin_guess_is_lower_offset(self):
        self.assertEqual(
            self._offset(self.BERLIN, "Europe/Berlin", self.BERLIN_AMBIGUOUS, None),
            timedelta(hours=1),
        )

    def test_dublin_reversed_dst_resolves_by_offset(self):
        # Same True -> higher, False -> lower pattern as Berlin, though tzdb
        # gives Dublin's summer IST dst() == 0 and its winter GMT dst() == -1h.
        self.assertEqual(
            self._offset(self.DUBLIN, "Europe/Dublin", self.DUBLIN_AMBIGUOUS, True),
            timedelta(hours=1),
        )
        self.assertEqual(
            self._offset(self.DUBLIN, "Europe/Dublin", self.DUBLIN_AMBIGUOUS, False),
            timedelta(0),
        )

    def test_fall_back_occurrence_flips_tibetan_day_across_dawn(self):
        # Dawn at 59.5N is 01:11 UTC, which the zone's summer offset reads as
        # 02:11 local - inside its fall-back hour. The summer reading of 02:05
        # is 01:05 UTC (pre-dawn, still 05-12); the winter one is 02:05 UTC
        # (past dawn, 05-13).
        loc = Location(59.5, 20.0)
        tz = FallBackAtDawnZone()
        naive = datetime(2018, 5, 13, 2, 5)
        earlier = resolve_local_time(naive, tz, loc, on_summer_time=True)
        later = resolve_local_time(naive, tz, loc, on_summer_time=False)
        self.assertEqual(calendar.tibetan_day_date(earlier, loc), date(2018, 5, 12))
        self.assertEqual(calendar.tibetan_day_date(later, loc), date(2018, 5, 13))


class TestSkippedTimeDetection(unittest.TestCase):
    """A time is skipped only when neither of its readings survives
    normalization; a time whose later reading is valid exists."""

    def test_time_with_valid_later_reading_exists(self):
        self.assertFalse(
            is_nonexistent_local_time(
                datetime(2000, 6, 1, 12, 0), AlwaysAmbiguousZone()
            )
        )

    def test_time_with_valid_later_reading_is_ambiguous(self):
        self.assertTrue(
            is_ambiguous_local_time(datetime(2000, 6, 1, 12, 0), AlwaysAmbiguousZone())
        )

    def test_spring_forward_gap_still_skipped(self):
        self.assertTrue(
            is_nonexistent_local_time(
                datetime(2024, 3, 31, 2, 30), zone("Europe/Berlin")
            )
        )


class TestLongitudeBasedTimezone(unittest.TestCase):
    """A location-derived nautical or mean-solar timezone IS longitude-based;
    an explicit fixed offset the user chose IS NOT."""

    def test_open_water_birth_is_longitude_based(self):
        subject = Subject(
            gender=Gender.MALE,
            birth_datetime=datetime(1700, 6, 15, 12, 0),
            birth_location=Location(10.0, -150.0),  # mid-Pacific -> nautical Etc
        )
        self.assertTrue(subject.timezone_is_longitude_based)

    def test_explicit_fixed_offset_is_not_longitude_based(self):
        subject = _subject(
            datetime(1700, 6, 15, 12, 0),
            location=Location(27.7, 85.3),
            tz=fixed_offset(timedelta(hours=5, minutes=30)),
        )
        self.assertFalse(subject.timezone_is_longitude_based)

    def test_classifier_accepts_derived_mean_solar_offset(self):
        self.assertTrue(is_longitude_based_timezone(_mean_solar_timezone(85.3)))

    def test_classifier_accepts_nautical_zone(self):
        self.assertTrue(is_longitude_based_timezone(zone("Etc/GMT-8")))

    def test_classifier_rejects_explicit_fixed_offset(self):
        self.assertFalse(
            is_longitude_based_timezone(fixed_offset(timedelta(hours=5, minutes=30)))
        )

    def test_classifier_rejects_geographic_zone(self):
        self.assertFalse(is_longitude_based_timezone(zone("Asia/Kathmandu")))


class TestBundledTzdataDeterminism(unittest.TestCase):
    def test_zone_reads_bundled_backzone_data(self):
        """zone() loads the bundled backzone-compiled tree: Oslo must show its
        own LMT (+0:43), not the merged Berlin LMT (+0:53:28) that a default
        tzdb build (and the pip tzdata package) would give."""
        aware = datetime(1700, 6, 15, 12, 0, tzinfo=zone("Europe/Oslo"))
        self.assertEqual(aware.utcoffset(), timedelta(minutes=43))

    def test_merged_zone_keeps_own_prewar_history(self):
        """Stockholm 1943 stays on CET: Sweden had no wartime DST, unlike the
        Berlin zone it is merged into by a default tzdb build."""
        aware = datetime(1943, 7, 1, 12, 0, tzinfo=zone("Europe/Stockholm"))
        self.assertEqual(aware.utcoffset(), timedelta(hours=1))


class TestZoneTabParsing(unittest.TestCase):
    def test_valid_coordinate_pair_parsed(self):
        latitude, longitude = _parse_iso6709("+4852+00220")
        self.assertAlmostEqual(latitude, 48.8667, places=4)
        self.assertAlmostEqual(longitude, 2.3333, places=4)

    def test_malformed_coordinates_rejected(self):
        """A corrupted zone.tab line must raise, not silently misparse."""
        for coords in (
            "",
            "+4852",
            "4852+00220",
            "+4x52+00220",
            "+4+00220",
            "4852N00220E",
            "+4852N+00220E",
            "48.85N 2.35E",
        ):
            with self.subTest(coords=coords):
                with self.assertRaisesRegex(ValueError, "ISO 6709"):
                    _parse_iso6709(coords)

    def test_tab_separated_row_parsed(self):
        rows = _parse_zone_tab("FR\t+4852+00220\tEurope/Paris\tcomment text")
        self.assertEqual(rows, (("FR", "+4852+00220", "Europe/Paris"),))

    def test_space_separated_row_parsed(self):
        rows = _parse_zone_tab("FR +4852+00220 Europe/Paris")
        self.assertEqual(rows, (("FR", "+4852+00220", "Europe/Paris"),))

    def test_comments_blanks_and_crlf_skipped(self):
        table = "# header\r\n\r\n  \r\nFR\t+4852+00220\tEurope/Paris\r\n"
        rows = _parse_zone_tab(table)
        self.assertEqual(rows, (("FR", "+4852+00220", "Europe/Paris"),))

    def test_truncated_line_raises_clearly(self):
        """A short zone.tab line must raise, not crash on unpacking."""
        with self.assertRaisesRegex(ValueError, "corrupted tzdata"):
            _parse_zone_tab("FR\t+4852+00220")

    def test_empty_table_raises_clearly(self):
        """A zone.tab with no entries at all is corruption, not an empty result."""
        with self.assertRaisesRegex(ValueError, "corrupted tzdata"):
            _parse_zone_tab("# comments only\n")

    def test_bundled_zone_tab_parses(self):
        rows = _zone_tab_rows()
        self.assertIn(("FR", "+4852+00220", "Europe/Paris"), rows)


class TestLocationDerivedTimezone(unittest.TestCase):
    """birth_timezone=None is the expected default: derived from coordinates,
    with a derivation grade saying how sure the result is."""

    def test_modern_land_birth_is_certain(self):
        subject = _subject(datetime(2000, 6, 15, 12, 0), ROME)
        self.assertEqual(
            getattr(subject.effective_timezone, "key", None), "Europe/Rome"
        )
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.CERTAIN)

    def test_pre_1970_land_birth_is_estimated(self):
        subject = _subject(datetime(1950, 6, 15, 12, 0), ROME)
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.ESTIMATED)

    def test_open_ocean_birth_is_estimated_and_calculates(self):
        subject = _subject(datetime(1990, 6, 15, 12, 0), Location(10.0, -150.0))
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.ESTIMATED)
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=-10))

    def test_south_pole_birth_calculates(self):
        subject = _subject(datetime(2000, 6, 15, 12, 0), Location(-90.0, 0.0))
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertTrue(result.harmonized_aspects)

    def test_explicit_timezone_is_certain(self):
        subject = _subject(datetime(1950, 6, 15, 12, 0), ROME, zone("Europe/Rome"))
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.CERTAIN)


class TestHistoricalBorderTimezone(unittest.TestCase):
    """A pre-1970 birth gets the time history of the country that held the
    birthplace in the birth year, never of today's map alone."""

    LVIV = Location(49.8397, 24.0297)

    def test_interwar_lviv_gets_polish_time(self):
        subject = _subject(datetime(1930, 6, 15, 12, 0), self.LVIV)
        self.assertEqual(
            getattr(subject.effective_timezone, "key", None), "Europe/Warsaw"
        )
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.ESTIMATED)
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=1))

    def test_postwar_lviv_gets_soviet_time(self):
        subject = _subject(datetime(1950, 6, 15, 12, 0), self.LVIV)
        self.assertEqual(
            getattr(subject.effective_timezone, "key", None), "Europe/Kyiv"
        )
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.ESTIMATED)
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=3))

    def test_wartime_lviv_flagged_borders_uncertain(self):
        """Lviv changed hands between the 1938 and 1945 maps, and its true
        1940 legal time (Moscow time, decreed after the 1939 Soviet
        annexation) is invisible to both - that's because currently used open data
        falls short. WIP.
        """
        subject = _subject(datetime(1940, 6, 15, 12, 0), self.LVIV)
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.BORDERS_UNCERTAIN)

    def test_wartime_lviv_explicit_timezone_overrides(self):
        """The documented remedy for a borders-uncertain birth: the caller
        supplies the researched legal time."""
        subject = _subject(
            datetime(1940, 6, 15, 12, 0), self.LVIV, zone("Europe/Moscow")
        )
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.CERTAIN)
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=3))

    def test_renamed_country_is_not_a_border_change(self):
        """Strasbourg 1916: the maps around the year call the country
        'German Empire' and 'Germany'; a rename must not flag uncertainty,
        and the birth gets German time including the 1916 DST."""
        subject = _subject(datetime(1916, 7, 1, 12, 0), Location(48.5734, 7.7521))
        self.assertIs(subject.timezone_derivation, TimezoneDerivation.ESTIMATED)
        self.assertEqual(subject.local_birth_datetime.utcoffset(), timedelta(hours=2))

    def test_stable_country_keeps_polygon_zone(self):
        """Colorado 1950: the USA polygon zone's reference city (Denver) is in
        the same country, so the geographically exact zone is kept."""
        subject = _subject(datetime(1950, 6, 15, 12, 0), Location(39.74, -104.99))
        self.assertEqual(
            getattr(subject.effective_timezone, "key", None), "America/Denver"
        )

    def test_merged_zone_history_applies_to_pre_1970_birth(self):
        """Amsterdam 1935: the birth must get the real Dutch +1:19:32 summer
        offset, not the +1:00 of the Brussels zone that a default tzdb build
        merges Amsterdam into."""
        subject = _subject(datetime(1935, 6, 15, 12, 0), Location(52.37, 4.90))
        self.assertEqual(
            getattr(subject.effective_timezone, "key", None), "Europe/Amsterdam"
        )
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(),
            timedelta(hours=1, minutes=19, seconds=32),
        )


if __name__ == "__main__":
    unittest.main()
