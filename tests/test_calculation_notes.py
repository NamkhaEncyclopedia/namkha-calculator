import unittest
from datetime import datetime, timedelta, timezone

import pytz

from namkha_calculator.astrology import Animal, Element, Gender, Subject
from namkha_calculator.astronomy import (
    OFFSET_AHEAD_SOLAR_LIMIT_HOURS,
    OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    Location,
    fixed_offset,
    offset_solar_gap_hours,
)
from namkha_calculator.calculation_notes import (
    CalculationNote,
    local_time_dst_note,
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
) -> Subject:
    if isinstance(birth, str):
        birth = datetime.strptime(birth, "%d.%m.%Y %H:%M")
    return Subject(
        gender=Gender.MALE,
        birth_datetime=birth,
        birth_timezone=tz if tz is not None else pytz.timezone(_TZ),
        birth_location=location if location is not None else Location(_LAT, _LON),
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


class TestLocalTimeDstNote(unittest.TestCase):
    # Europe/Berlin 2024: spring-forward gap 31.03 02:00->03:00,
    # autumn fall-back overlap 27.10 03:00->02:00.
    _TZ = pytz.timezone("Europe/Berlin")

    def _dst_notes(self, dt_str):
        naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        return {item.note for item in local_time_dst_note(naive, self._TZ)}

    def test_nonexistent_time_in_spring_gap(self):
        self.assertIn(
            CalculationNote.NONEXISTENT_LOCAL_TIME, self._dst_notes("31.03.2024 02:30")
        )

    def test_ambiguous_time_in_autumn_overlap(self):
        self.assertIn(
            CalculationNote.AMBIGUOUS_LOCAL_TIME, self._dst_notes("27.10.2024 02:30")
        )

    def test_normal_time_no_note(self):
        self.assertEqual(self._dst_notes("15.06.2024 12:00"), set())


class TestDstNoteInResult(unittest.TestCase):
    def test_ambiguous_time_emits_note_in_result(self):
        notes = _notes(_subject("27.10.2024 02:30"), CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.AMBIGUOUS_LOCAL_TIME, notes)


class TestHighLatitudeNoteInResult(unittest.TestCase):
    def test_high_latitude_emits_note(self):
        # Svalbard (78 N) is above the 60 deg limit, so the day start always
        # uses the fixed-hour fallback.
        svalbard = _subject(
            tz=pytz.timezone("Arctic/Longyearbyen"), location=Location(78.0, 15.0)
        )
        notes = _notes(svalbard, CalculationMethod.CLASSIC)
        self.assertIn(CalculationNote.HIGH_LATITUDE, notes)

    def test_normal_latitude_no_note(self):
        # Stuttgart (48.8 N) has a real dawn, so no fixed-hour fallback.
        notes = _notes(_subject("15.06.1985 12:00"), CalculationMethod.CLASSIC)
        self.assertNotIn(CalculationNote.HIGH_LATITUDE, notes)


class TestOffsetSolarGapBounds(unittest.TestCase):
    """The gap between the standard-time clock offset and the longitude's mean
    solar time must stay within (-OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    +OFFSET_AHEAD_SOLAR_LIMIT_HOURS); a bigger gap is a data-entry error. The
    behind bound is tighter because a clock behind the sun pulls dawn toward
    clock midnight. All historical zones fit inside the bounds."""

    def test_far_behind_rejected(self):
        # 0 deg longitude keeps solar ~ UTC, but the clock is UTC-4: 4 h behind.
        with self.assertRaisesRegex(ValueError, "behind"):
            _subject(tz=fixed_offset(timedelta(hours=-4)), location=Location(45.0, 0.0))

    def test_far_ahead_rejected(self):
        # 0 deg longitude on a UTC+4 clock: 4 h ahead, over the +3.5 h bound.
        with self.assertRaisesRegex(ValueError, "ahead"):
            _subject(tz=fixed_offset(timedelta(hours=4)), location=Location(45.0, 0.0))

    def test_moderately_behind_accepted(self):
        # 1.5 h behind solar is within bounds (rare but plausible data entry).
        subject = _subject(
            tz=fixed_offset(timedelta(hours=-1, minutes=-30)),
            location=Location(45.0, 0.0),
        )
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(), timedelta(hours=-1.5)
        )

    def test_matched_offset_accepted(self):
        # Stuttgart on Europe/Berlin: offset tracks longitude (~1 h apart).
        subject = _subject(
            tz=pytz.timezone("Europe/Berlin"), location=Location(48.7758, 9.1829)
        )
        self.assertIsInstance(subject, Subject)

    def test_real_wide_zone_accepted(self):
        # Urumqi on Beijing time (UTC+8, ~2.2 h ahead of local solar): the widest
        # kind of real mismatch, well inside the ahead bound.
        subject = _subject(
            tz=pytz.timezone("Asia/Shanghai"), location=Location(43.8256, 87.6168)
        )
        self.assertIsInstance(subject, Subject)

    def test_worst_real_behind_zone_within_bound(self):
        # Danmarkshavn 1916-1996 ran UTC-3 at longitude -18.7: ~1.76 h behind
        # solar, the deepest behind-solar offset any real zone ever used. Its
        # latitude (76.8 N) skips the Subject-level check, so pin the gap
        # itself against the bound.
        location = Location(76.7667, -18.6667)
        subject = _subject(
            datetime(1950, 1, 15, 12, 0),
            tz=pytz.timezone("America/Danmarkshavn"),
            location=location,
        )
        gap = offset_solar_gap_hours(subject.local_birth_datetime, location)
        self.assertGreater(gap, -OFFSET_BEHIND_SOLAR_LIMIT_HOURS)
        self.assertLess(gap, 0)

    def test_high_latitude_skips_gap_check(self):
        # Amundsen-Scott (South Pole) runs on New Zealand time - a solar gap
        # far over the bound, irrelevant above LATITUDE_LIMIT (fixed-hour day
        # start). Construction must succeed although the gap is out of bounds.
        location = Location(-89.9, 0.0)
        subject = _subject(tz=pytz.timezone("Pacific/Auckland"), location=location)
        gap = offset_solar_gap_hours(subject.local_birth_datetime, location)
        self.assertGreater(abs(gap), OFFSET_AHEAD_SOLAR_LIMIT_HOURS)

    def test_day_off_offset_rejected(self):
        # +22 h at longitude -30 wraps to a near-zero solar gap, so only the
        # real-timezone offset range check can catch this day-off typo (+22
        # entered for -2).
        with self.assertRaisesRegex(ValueError, "outside the real-timezone range"):
            _subject(
                tz=fixed_offset(timedelta(hours=22)), location=Location(45.0, -30.0)
            )

    def test_extreme_real_offsets_accepted(self):
        # The widest offsets any real zone uses: UTC+14 (Line Islands) and
        # UTC-12 (Baker Island), each at its own longitude.
        for hours, longitude in ((14, -157.43), (-12, -176.48)):
            with self.subTest(hours=hours):
                subject = _subject(
                    tz=fixed_offset(timedelta(hours=hours)),
                    location=Location(1.87, longitude),
                )
                self.assertEqual(
                    subject.local_birth_datetime.utcoffset(), timedelta(hours=hours)
                )

    def test_historical_dst_on_wide_zone_accepted(self):
        # Kashgar, summer 1988: China DST put the clock at UTC+9, ~3.9 h ahead of
        # local solar - over the bound if DST counted. The gap is measured against
        # standard time (UTC+8, ~2.9 h), so this legal birth is accepted.
        subject = _subject(
            datetime(1988, 7, 1, 12, 0),
            tz=pytz.timezone("Asia/Shanghai"),
            location=Location(39.4704, 75.9898),
        )
        self.assertEqual(subject.local_birth_datetime.dst(), timedelta(hours=1))


class TestSkippedDateBirth(unittest.TestCase):
    def test_samoa_skipped_date_raises_clearly(self):
        # Samoa skipped 2011-12-30 crossing the dateline; a birth entered on that
        # date must fail with a clear error, not a raw skyfield one.
        subject = _subject(
            datetime(2011, 12, 30, 10, 0),
            tz=pytz.timezone("Pacific/Apia"),
            location=Location(-13.8333, -171.7667),
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_high_latitude_birth_skips_date_check(self):
        # At/above LATITUDE_LIMIT the day starts at a fixed hour; the birth-date
        # check must not run there (dawn/dateline cases can't arise) and
        # calculation proceeds even on a date the below-limit path would reject.
        subject = _subject(
            datetime(2011, 12, 30, 10, 0),
            tz=pytz.timezone("Pacific/Apia"),
            location=Location(65.0, 10.0),
        )
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertIsNotNone(result.harmonized_aspects)


class TestFixedOffsetSubject(unittest.TestCase):
    def test_subject_accepts_fixed_offset_and_calculates(self):
        subject = _subject(
            tz=fixed_offset(timedelta(hours=5, minutes=30)),
            location=Location(27.7, 85.3),
        )
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertIsInstance(result.birth_element, Element)
        self.assertIsInstance(result.birth_animal, Animal)

    def test_stdlib_timezone_rejected(self):
        # datetime.timezone lacks .localize, so it must be rejected.
        with self.assertRaises(TypeError):
            _subject(tz=timezone(timedelta(hours=2)), location=Location(27.7, 85.3))


if __name__ == "__main__":
    unittest.main()
