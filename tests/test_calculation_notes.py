import unittest
from datetime import datetime, timedelta, timezone

from namkha_calculator.astrology import Gender, Subject
from namkha_calculator.astronomy import Location, zone
from namkha_calculator.calculation_notes import (
    GREGORIAN_REFORM_DATE,
    CalculationNote,
    gregorian_adoption_date,
    local_mean_time_note,
    local_time_dst_note,
    period_boundary_note,
    pre_gregorian_note,
)
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha

# Stuttgart; Losar times calculated from the calendar code (Europe/Berlin, CET):
#   official      Losar (Tibetan year 2151) = 2024-02-10 07:07:39
#   astrological  Losar (Tibetan year 2151) = 2023-12-13 07:30:40
_TZ = "Europe/Berlin"
_LAT, _LON = 48.7758, 9.1829


def _subject(
    birth: str | datetime = "15.06.1985 12:00",
    tz=None,
    location: Location | None = None,
    on_summer_time: bool | None = None,
) -> Subject:
    if isinstance(birth, str):
        birth = datetime.strptime(birth, "%d.%m.%Y %H:%M")
    return Subject(
        gender=Gender.MALE,
        birth_datetime=birth,
        birth_timezone=tz if tz is not None else zone(_TZ),
        birth_location=location if location is not None else Location(_LAT, _LON),
        on_summer_time=on_summer_time,
        name=None,
    )


def _notes(subject, method):
    result = calculate_namkha(NamkhaType.YEAR, subject, method)
    return {item.note for item in result.calculation_notes}


class TestPeriodBoundaryNote(unittest.TestCase):
    def test_official_near_boundary_emits_note(self):
        # 07:05 is ~2.5 min before the official Losar at 07:07:39
        notes = _notes(_subject("10.02.2024 07:05"), CalculationMethod.CNNR)
        self.assertIn(CalculationNote.PERIOD_BOUNDARY, notes)

    def test_official_away_from_boundary_no_note(self):
        # 06:55 is ~12.5 min before the official Losar
        notes = _notes(_subject("10.02.2024 06:55"), CalculationMethod.CNNR)
        self.assertNotIn(CalculationNote.PERIOD_BOUNDARY, notes)

    def test_classic_near_boundary_emits_note(self):
        # 07:33 is ~2.5 min after the astrological Losar at 07:30:40
        notes = _notes(_subject("13.12.2023 07:33"), CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.PERIOD_BOUNDARY, notes)

    def test_classic_away_from_boundary_no_note(self):
        # 07:45 is ~14 min after the astrological Losar
        notes = _notes(_subject("13.12.2023 07:45"), CalculationMethod.CLASSIC)
        self.assertNotIn(CalculationNote.PERIOD_BOUNDARY, notes)


class TestPeriodBoundaryNoteUnit(unittest.TestCase):
    def test_boundary_compared_in_utc_across_offsets(self):
        # Birth 13:00+01:00 is 12:00 UTC; boundary is 12:02 UTC. They are 2 min
        # apart in real time (within the 5 min threshold -> note fires), but
        # 58 min apart by wall clock. The note firing proves the comparison
        # converts to UTC first instead of subtracting the wall-clock times.
        birth = datetime(2024, 6, 15, 13, 0, tzinfo=timezone(timedelta(hours=1)))
        boundary = datetime(2024, 6, 15, 12, 2, tzinfo=timezone.utc)
        notes = period_boundary_note(birth, (boundary,))
        self.assertEqual(
            {item.note for item in notes}, {CalculationNote.PERIOD_BOUNDARY}
        )


class TestLocalTimeDstNote(unittest.TestCase):
    # Europe/Berlin 2024: spring-forward gap 31.03 02:00->03:00,
    # autumn fall-back overlap 27.10 03:00->02:00.
    _TZ = zone("Europe/Berlin")

    def _dst_notes(self, dt_str, occurrence_specified=False):
        naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        return {
            item.note
            for item in local_time_dst_note(naive, self._TZ, occurrence_specified)
        }

    def test_ambiguous_time_in_autumn_overlap(self):
        self.assertIn(
            CalculationNote.AMBIGUOUS_LOCAL_TIME, self._dst_notes("27.10.2024 02:30")
        )

    def test_ambiguous_time_resolved_when_specified(self):
        notes = self._dst_notes("27.10.2024 02:30", occurrence_specified=True)
        self.assertIn(CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED, notes)
        self.assertNotIn(CalculationNote.AMBIGUOUS_LOCAL_TIME, notes)

    def test_normal_time_no_note(self):
        self.assertEqual(self._dst_notes("15.06.2024 12:00"), set())

    def test_lmt_era_no_note(self):
        # Before Europe/Berlin's 1893 switch to standard time the offset is
        # longitude-based (LMT), so clock changes cannot arise.
        self.assertEqual(self._dst_notes("15.06.1850 02:30"), set())


class TestDstNoteInResult(unittest.TestCase):
    def test_ambiguous_time_emits_note_in_result(self):
        notes = _notes(_subject("27.10.2024 02:30"), CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.AMBIGUOUS_LOCAL_TIME, notes)

    def test_ambiguous_time_resolved_in_result_when_on_summer_time_set(self):
        # on_summer_time pins the repeated fall-back hour, turning the caution
        # into the resolved notice through the full pipeline.
        subject = _subject("27.10.2024 02:30", on_summer_time=True)
        notes = _notes(subject, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED, notes)
        self.assertNotIn(CalculationNote.AMBIGUOUS_LOCAL_TIME, notes)


class TestPreGregorianNote(unittest.TestCase):
    # Rome, before/after the Gregorian reform of 15 October 1582.
    _ROME = Location(41.9028, 12.4964)

    def test_pre_reform_birth_emits_note(self):
        subject = _subject(
            datetime(1580, 6, 15, 12, 0),
            tz=zone("Europe/Rome"),
            location=self._ROME,
        )
        self.assertIn(
            CalculationNote.PRE_GREGORIAN_DATE,
            _notes(subject, CalculationMethod.CLASSIC),
        )

    def test_post_reform_birth_no_note(self):
        subject = _subject(
            datetime(1583, 6, 15, 12, 0),
            tz=zone("Europe/Rome"),
            location=self._ROME,
        )
        self.assertNotIn(
            CalculationNote.PRE_GREGORIAN_DATE,
            _notes(subject, CalculationMethod.CLASSIC),
        )


class TestRegionalGregorianAdoption(unittest.TestCase):
    """Adoption-date cutoffs per birth region; boundaries via pre_gregorian_note directly."""

    _MOSCOW = Location(55.7558, 37.6173)
    _LONDON = Location(51.5074, -0.1278)
    _TOKYO = Location(35.6762, 139.6503)
    _ATHENS = Location(37.9838, 23.7275)
    _SITKA = Location(57.0531, -135.33)
    _ROME = Location(41.9028, 12.4964)
    _FAROE = Location(62.01, -6.77)
    _ALAND = Location(60.10, 19.93)
    # Open South Pacific, far from any zone.tab country.
    _OCEAN = Location(-48.87, -123.39)

    # (label, location, birth_datetime, expect_note)
    _CASES = (
        ("russia_pre_1918", _MOSCOW, datetime(1917, 6, 15, 12, 0), True),
        ("russia_post_1918", _MOSCOW, datetime(1918, 2, 14, 12, 0), False),
        ("britain_pre_1752", _LONDON, datetime(1751, 6, 15, 12, 0), True),
        ("britain_post_1752", _LONDON, datetime(1752, 9, 14, 12, 0), False),
        ("japan_pre_1873", _TOKYO, datetime(1872, 6, 15, 12, 0), True),
        ("japan_post_1873", _TOKYO, datetime(1873, 1, 1, 12, 0), False),
        ("greece_pre_1923", _ATHENS, datetime(1923, 2, 15, 12, 0), True),
        # Sitka was Russian and Julian until the 1867 purchase, unlike the
        # rest of the US which follows Britain's 1752 switch (zone override).
        ("alaska_zone_override", _SITKA, datetime(1867, 6, 15, 12, 0), True),
        # Faroe Islands (country FO) followed Denmark's 1700 switch, not the
        # 1582 default its distinct country code would otherwise fall back to.
        ("faroe_pre_1700", _FAROE, datetime(1690, 6, 15, 12, 0), True),
        # Aland (country AX) followed Sweden's 1753 switch, not the 1582 default.
        ("aland_pre_1753", _ALAND, datetime(1752, 6, 15, 12, 0), True),
        # Italy adopted at the 1582 reform, so a 1700 birth is not pre-Gregorian
        # even though it precedes the late adopters above.
        ("italy_between_reform_and_late", _ROME, datetime(1700, 6, 15, 12, 0), False),
    )

    def test_adoption_cutoffs(self):
        for label, location, birth, expect_note in self._CASES:
            with self.subTest(label):
                notes = pre_gregorian_note(birth, location)
                emitted = {item.note for item in notes}
                if expect_note:
                    self.assertEqual(emitted, {CalculationNote.PRE_GREGORIAN_DATE})
                else:
                    self.assertEqual(notes, ())

    def test_ocean_falls_back_to_reform_date(self):
        self.assertEqual(gregorian_adoption_date(self._OCEAN), GREGORIAN_REFORM_DATE)


class TestLocalMeanTimeNote(unittest.TestCase):
    _ROME = zone("Europe/Rome")

    def _lmt_notes(self, birth, longitude_based=False):
        return {
            item.note
            for item in local_mean_time_note(birth, self._ROME, longitude_based)
        }

    def test_lmt_era_emits_notice(self):
        self.assertIn(
            CalculationNote.LOCAL_MEAN_TIME,
            self._lmt_notes(datetime(1700, 6, 15, 12, 0)),
        )

    def test_standard_era_no_notice(self):
        self.assertEqual(self._lmt_notes(datetime(1985, 6, 15, 12, 0)), set())

    def test_longitude_based_flag_emits_notice(self):
        # The flag (a location-derived nautical/mean-solar zone) triggers the
        # notice on its own, independent of the era.
        self.assertIn(
            CalculationNote.LOCAL_MEAN_TIME,
            self._lmt_notes(datetime(1985, 6, 15, 12, 0), longitude_based=True),
        )


class TestLocalMeanTimeNoteInResult(unittest.TestCase):
    def test_lmt_era_emits_note_in_result(self):
        subject = _subject(
            datetime(1700, 6, 15, 12, 0),
            tz=zone("Europe/Rome"),
            location=Location(41.9028, 12.4964),
        )
        notes = _notes(subject, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.LOCAL_MEAN_TIME, notes)


class TestTimezoneDerivationNotes(unittest.TestCase):
    def test_estimated_timezone_emits_caution(self):
        # Open-ocean birth: no civil zone, so the derivation is an estimate.
        subject = Subject(
            gender=Gender.MALE,
            birth_datetime=datetime(1990, 6, 15, 12, 0),
            birth_location=Location(10.0, -150.0),
            name=None,
        )
        notes = _notes(subject, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.TIMEZONE_ESTIMATED, notes)
        self.assertNotIn(CalculationNote.TIMEZONE_BORDERS_UNCERTAIN, notes)

    def test_borders_uncertain_emits_only_that_caution(self):
        # Lviv 1940 lies between maps that disagree about its country; the
        # two timezone cautions are mutually exclusive.
        subject = Subject(
            gender=Gender.MALE,
            birth_datetime=datetime(1940, 6, 15, 12, 0),
            birth_location=Location(49.8397, 24.0297),
            name=None,
        )
        notes = _notes(subject, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.TIMEZONE_BORDERS_UNCERTAIN, notes)
        self.assertNotIn(CalculationNote.TIMEZONE_ESTIMATED, notes)

    def test_explicit_timezone_no_caution(self):
        notes = _notes(_subject("15.06.1985 12:00"), CalculationMethod.CLASSIC)
        self.assertNotIn(CalculationNote.TIMEZONE_ESTIMATED, notes)
        self.assertNotIn(CalculationNote.TIMEZONE_BORDERS_UNCERTAIN, notes)


class TestHighLatitudeNoteInResult(unittest.TestCase):
    def test_high_latitude_emits_note(self):
        # Svalbard (78 N) is above the 60 deg limit, so the day start always
        # uses the fixed-hour fallback.
        svalbard = _subject(
            tz=zone("Arctic/Longyearbyen"), location=Location(78.0, 15.0)
        )
        notes = _notes(svalbard, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.HIGH_LATITUDE, notes)

    def test_normal_latitude_no_note(self):
        # Stuttgart (48.8 N) has a real dawn, so no fixed-hour fallback.
        notes = _notes(_subject("15.06.1985 12:00"), CalculationMethod.CLASSIC)
        self.assertNotIn(CalculationNote.HIGH_LATITUDE, notes)


if __name__ == "__main__":
    unittest.main()
