import pickle
import unittest
from datetime import datetime, timedelta, timezone, tzinfo

from namkha_calculator.astrology import Animal, Element, Gender, Subject
from namkha_calculator.astronomy import (
    OFFSET_AHEAD_SOLAR_LIMIT_HOURS,
    OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    Location,
    fixed_offset,
    offset_solar_gap_hours,
    zone,
)
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha

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
        birth_timezone=tz if tz is not None else zone(_TZ),
        birth_location=location if location is not None else Location(_LAT, _LON),
        name=None,
    )


class TestOffsetSolarGapBounds(unittest.TestCase):
    """The gap between the standard-time clock offset and the longitude's mean
    solar time must stay within (-OFFSET_BEHIND_SOLAR_LIMIT_HOURS,
    +OFFSET_AHEAD_SOLAR_LIMIT_HOURS); a bigger gap is a data-entry error. The
    behind bound is tighter because a clock behind the sun pulls dawn toward
    clock midnight. All historical zones fit inside the bounds."""

    def test_far_behind_rejected(self):
        """0 deg longitude keeps solar ~ UTC, but the clock is UTC-4: 4 h behind."""
        with self.assertRaisesRegex(ValueError, "behind"):
            _subject(tz=fixed_offset(timedelta(hours=-4)), location=Location(45.0, 0.0))

    def test_far_ahead_rejected(self):
        """0 deg longitude on a UTC+4 clock: 4 h ahead, over the +3.5 h bound."""
        with self.assertRaisesRegex(ValueError, "ahead"):
            _subject(tz=fixed_offset(timedelta(hours=4)), location=Location(45.0, 0.0))

    def test_moderately_behind_accepted(self):
        """1.5 h behind solar is within bounds (rare but plausible data entry)."""
        subject = _subject(
            tz=fixed_offset(timedelta(hours=-1, minutes=-30)),
            location=Location(45.0, 0.0),
        )
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(), timedelta(hours=-1.5)
        )

    def test_matched_offset_accepted(self):
        """Stuttgart on Europe/Berlin: offset tracks longitude (~1 h apart)."""
        subject = _subject(tz=zone("Europe/Berlin"), location=Location(48.7758, 9.1829))
        self.assertIsInstance(subject, Subject)

    def test_real_wide_zone_accepted(self):
        """Urumqi on Beijing time (UTC+8, ~2.2 h ahead of local solar): the widest
        kind of real mismatch, well inside the ahead bound."""
        subject = _subject(
            tz=zone("Asia/Shanghai"), location=Location(43.8256, 87.6168)
        )
        self.assertIsInstance(subject, Subject)

    def test_worst_real_behind_zone_within_solar_gap_bound(self):
        """Danmarkshavn 1916-1996 ran UTC-3 at longitude -18.7: ~1.76 h behind
        solar, the deepest behind-solar offset any real zone ever used, so
        OFFSET_BEHIND_SOLAR_LIMIT_HOURS must exceed it. Its latitude (76.8 N)
        skips the Subject-level check, so pin the gap itself against the
        bound."""
        location = Location(76.7667, -18.6667)
        subject = _subject(
            datetime(1950, 1, 15, 12, 0),
            tz=zone("America/Danmarkshavn"),
            location=location,
        )
        gap = offset_solar_gap_hours(subject.local_birth_datetime, location)
        self.assertGreater(gap, OFFSET_BEHIND_SOLAR_LIMIT_HOURS)
        self.assertLess(gap, 0)

    def test_high_latitude_skips_gap_check(self):
        """Amundsen-Scott (South Pole) runs on New Zealand time - a solar gap
        far over the bound, irrelevant above LATITUDE_LIMIT (fixed-hour day
        start). Construction must succeed although the gap is out of bounds."""
        location = Location(-89.9, 0.0)
        subject = _subject(tz=zone("Pacific/Auckland"), location=location)
        gap = offset_solar_gap_hours(subject.local_birth_datetime, location)
        self.assertGreater(abs(gap), OFFSET_AHEAD_SOLAR_LIMIT_HOURS)

    def test_day_off_offset_rejected(self):
        """+22 h at longitude -30 wraps to a near-zero solar gap, so only the
        real-timezone offset range check can catch this day-off typo (+22
        entered for -2)."""
        with self.assertRaisesRegex(ValueError, "outside the real-timezone range"):
            _subject(
                tz=fixed_offset(timedelta(hours=22)), location=Location(45.0, -30.0)
            )

    def test_extreme_real_offsets_within_offset_range(self):
        """The widest offsets any real zone uses: modern civil UTC+14 (Line
        Islands) and UTC-12 (Baker Island), plus the historical date-side
        extreme UTC-15:56 at Manila's longitude (= +8:04 - 24 h, so its solar
        gap is ~0). Each at its own longitude, so UTC_OFFSET_MIN/MAX_HOURS must
        accept them all."""
        cases = (
            (timedelta(hours=14), Location(1.87, -157.43)),
            (timedelta(hours=-12), Location(1.87, -176.48)),
            (timedelta(hours=-15, minutes=-56), Location(14.6, 121.0)),
        )
        for offset, location in cases:
            with self.subTest(offset=offset, longitude=location.longitude):
                subject = _subject(tz=fixed_offset(offset), location=location)
                self.assertEqual(subject.local_birth_datetime.utcoffset(), offset)

    def test_historical_dst_on_wide_zone_accepted(self):
        """Kashgar, summer 1988: China DST put the clock at UTC+9, ~3.9 h ahead of
        local solar - over the bound if DST counted. The gap is measured against
        standard time (UTC+8, ~2.9 h), so this legal birth is accepted."""
        subject = _subject(
            datetime(1988, 7, 1, 12, 0),
            tz=zone("Asia/Shanghai"),
            location=Location(39.4704, 75.9898),
        )
        self.assertEqual(subject.local_birth_datetime.dst(), timedelta(hours=1))


class TestSkippedDateBirth(unittest.TestCase):
    def test_samoa_skipped_date_raises_clearly(self):
        """Samoa skipped 2011-12-30 crossing the dateline; a birth entered on that
        date must fail with a clear error, not a raw skyfield one."""
        subject = _subject(
            datetime(2011, 12, 30, 10, 0),
            tz=zone("Pacific/Apia"),
            location=Location(-13.8333, -171.7667),
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_high_latitude_dateline_skip_still_raises(self):
        """A date that never existed in the timezone is pure calendar arithmetic,
        independent of dawn, so it is rejected at every latitude - including
        at/above LATITUDE_LIMIT, where only the dawnless-date check is skipped."""
        subject = _subject(
            datetime(2011, 12, 30, 10, 0),
            tz=zone("Pacific/Apia"),
            location=Location(65.0, 10.0),
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_high_latitude_dst_gap_time_raises(self):
        """A wall-clock time skipped by a spring-forward gap never existed, so it
        is rejected even above LATITUDE_LIMIT. Anchorage (61.2 N) skipped
        2024-03-10 02:00->03:00, so 02:30 that day did not happen."""
        subject = _subject(
            datetime(2024, 3, 10, 2, 30),
            tz=zone("America/Anchorage"),
            location=Location(61.2181, -149.9003),
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_normal_latitude_dst_gap_time_raises(self):
        """The same spring-forward rejection at a normal latitude. Europe/Berlin
        skipped 2024-03-31 02:00->03:00, so 02:30 that day did not happen."""
        subject = _subject(datetime(2024, 3, 31, 2, 30))
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)


class TestFixedOffsetSubject(unittest.TestCase):
    def test_subject_accepts_fixed_offset_and_calculates(self):
        subject = _subject(
            tz=fixed_offset(timedelta(hours=5, minutes=30)),
            location=Location(27.7, 85.3),
        )
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertIsInstance(result.birth_element, Element)
        self.assertIsInstance(result.birth_animal, Animal)

    def test_stdlib_timezone_accepted(self):
        """datetime.timezone is the supported fixed-offset input type."""
        subject = _subject(
            tz=timezone(timedelta(hours=5, minutes=45)), location=Location(27.7, 85.3)
        )
        self.assertEqual(
            subject.local_birth_datetime.utcoffset(),
            timedelta(hours=5, minutes=45),
        )

    def test_foreign_tzinfo_rejected(self):
        """Only ZoneInfo and datetime.timezone are supported timezone types."""

        class LegacyTz(tzinfo):
            """Stand-in for a non-supported tzinfo implementation (e.g. pytz)."""

        with self.assertRaises(TypeError):
            _subject(tz=LegacyTz(), location=Location(27.7, 85.3))


class TestLmtEraValidation(unittest.TestCase):
    """Pre-standard-time births are validated against the raw zone offset, not
    astronomy._birth_longitude_mean_time (which recomputes the offset from the
    birth longitude and so would mask a mismatched timezone)."""

    ROME = Location(41.9028, 12.4964)
    MANILA = Location(14.5995, 120.9842)

    def test_lmt_era_mismatched_zone_rejected(self):
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            _subject(
                datetime(1700, 6, 15, 12, 0),
                tz=zone("Asia/Manila"),
                location=self.ROME,
            )

    def test_lmt_era_matching_zone_accepted(self):
        subject = _subject(
            datetime(1700, 6, 15, 12, 0),
            tz=zone("Asia/Manila"),
            location=self.MANILA,
        )
        self.assertIsInstance(subject, Subject)

    def test_hand_built_lmt_named_offset_keeps_its_offset(self):
        """A fixed offset labeled 'LMT' must not trigger
        astronomy._birth_longitude_mean_time (only real tzdb zones may) nor
        bypass validation: -2 h at Berlin is far behind local solar."""
        with self.assertRaisesRegex(ValueError, "behind"):
            _subject(
                datetime(1900, 6, 15, 12, 0),
                tz=timezone(timedelta(hours=-2), "LMT"),
                location=Location(52.52, 13.405),
            )


class TestSubjectPicklable(unittest.TestCase):
    """zone() returns a picklable ZoneInfo subclass, so a resolved Subject
    survives pickle/deepcopy (needed for multiprocessing and disk caching)."""

    def test_explicit_zone_subject_pickles(self):
        subject = _subject(tz=zone("Europe/Berlin"))
        _ = subject.local_birth_datetime
        restored = pickle.loads(pickle.dumps(subject))
        self.assertEqual(
            restored.local_birth_datetime.utcoffset(),
            subject.local_birth_datetime.utcoffset(),
        )

    def test_location_derived_subject_pickles(self):
        subject = Subject(
            gender=Gender.MALE,
            birth_datetime=datetime(1985, 6, 15, 12, 0),
            birth_location=Location(_LAT, _LON),
        )
        _ = subject.effective_timezone
        restored = pickle.loads(pickle.dumps(subject))
        self.assertEqual(
            str(restored.effective_timezone), str(subject.effective_timezone)
        )


if __name__ == "__main__":
    unittest.main()
