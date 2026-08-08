"""Checks on the birth details. Some happen when Subject is built, the rest
when the calculation runs.

Whether the timezone fits the birthplace is not checked here. That
happens when the timezone is derived, so those tests are in
test_zone_derivation.py."""

import pickle
import unittest
from datetime import datetime, timedelta

from namkha_calculator.astrology import Animal, Element, Gender, Subject
from namkha_calculator.tz import Location, zone
from namkha_calculator.tz.errors import StaleTimezoneError
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha
from namkha_calculator.zone_derivation import derive_timezone

_TZ_BERLIN = "Europe/Berlin"

_STUTTGART = Location(48.7758, 9.1829)
_SAMOA = Location(-13.8333, -171.7667)
# Generic point above LATITUDE_LIMIT, not a real place.
_HIGH_LATITUDE = Location(65.0, 10.0)
_ANCHORAGE = Location(61.2181, -149.9003)
_KATHMANDU = Location(27.7, 85.3)
_TOKYO = Location(35.6762, 139.6503)

_DEFAULT_BIRTH = datetime(1985, 6, 15, 12, 0)
_SAMOA_SKIPPED_DATE = datetime(2011, 12, 30, 10, 0)
_ANCHORAGE_DST_GAP = datetime(2024, 3, 10, 2, 30)  # spring-forward 02:00->03:00
_BERLIN_DST_GAP = datetime(2024, 3, 31, 2, 30)  # spring-forward 02:00->03:00


def _subject(
    birth: datetime = _DEFAULT_BIRTH,
    location: Location | None = None,
    zone_key: str | None = _TZ_BERLIN,
    offset: timedelta | None = None,
) -> Subject:
    location = location if location is not None else _STUTTGART
    return Subject(
        gender=Gender.MALE,
        birth_datetime=birth,
        birth_location=location,
        resolved_timezone=derive_timezone(
            location,
            birth,
            zone_key=None if offset is not None else zone_key,
            offset=offset,
        ),
        name=None,
    )


class TestSkippedDateBirth(unittest.TestCase):
    def test_samoa_skipped_date_raises_clearly(self):
        """Samoa skipped 2011-12-30 crossing the dateline; a birth entered on that
        date must fail with a clear error, not a raw skyfield one."""
        subject = _subject(
            _SAMOA_SKIPPED_DATE,
            zone_key="Pacific/Apia",
            location=_SAMOA,
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_high_latitude_dateline_skip_still_raises(self):
        """A date that never existed in the timezone is pure calendar arithmetic,
        independent of dawn, so it is rejected at every latitude - including
        at/above LATITUDE_LIMIT, where only the dawnless-date check is skipped."""
        subject = _subject(
            _SAMOA_SKIPPED_DATE,
            zone_key="Pacific/Apia",
            location=_HIGH_LATITUDE,
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_high_latitude_dst_gap_time_raises(self):
        """A wall-clock time skipped by a spring-forward gap never existed, so it
        is rejected even above LATITUDE_LIMIT. Anchorage (61.2 N) skipped
        2024-03-10 02:00->03:00, so 02:30 that day did not happen."""
        subject = _subject(
            _ANCHORAGE_DST_GAP,
            zone_key="America/Anchorage",
            location=_ANCHORAGE,
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

    def test_normal_latitude_dst_gap_time_raises(self):
        """The same spring-forward rejection at a normal latitude. Europe/Berlin
        skipped 2024-03-31 02:00->03:00, so 02:30 that day did not happen."""
        subject = _subject(_BERLIN_DST_GAP)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)


class TestFixedOffsetSubject(unittest.TestCase):
    def test_subject_accepts_fixed_offset_and_calculates(self):
        subject = _subject(offset=timedelta(hours=5, minutes=30), location=_KATHMANDU)
        result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)
        self.assertIsInstance(result.birth_element, Element)
        self.assertIsInstance(result.birth_animal, Animal)


class TestTimezoneMustBeResolved(unittest.TestCase):
    """Subject takes the settled timezone, never a timezone object. Passing one
    used to work, so the mistake needs a clear error rather than an
    AttributeError from somewhere inside."""

    def test_a_timezone_object_is_refused(self):
        with self.assertRaisesRegex(TypeError, "derive_timezone"):
            Subject(
                gender=Gender.MALE,
                birth_datetime=_DEFAULT_BIRTH,
                birth_location=_STUTTGART,
                resolved_timezone=zone(_TZ_BERLIN),  # type: ignore[arg-type]
            )

    def test_a_timezone_for_another_place_is_refused(self):
        """The timezone is derived before the calculation, so the birth details
        can change afterwards; a stale value would give the wrong zone."""
        resolved = derive_timezone(_STUTTGART, _DEFAULT_BIRTH, zone_key=_TZ_BERLIN)
        with self.assertRaises(StaleTimezoneError):
            Subject(
                gender=Gender.MALE,
                birth_datetime=_DEFAULT_BIRTH,
                birth_location=_TOKYO,
                resolved_timezone=resolved,
            )


class TestSubjectPicklable(unittest.TestCase):
    """zone() returns a picklable ZoneInfo subclass, so a resolved Subject
    survives pickle/deepcopy (needed for multiprocessing and disk caching).

    ResolvedTimezone.tzinfo is a cached_property, so a Subject that has been
    used already holds a rebuilt timezone and an untouched one does not. The
    two pickle different payloads, so both are covered here.
    """

    def test_untouched_subject_pickles(self):
        subject = _subject()
        restored = pickle.loads(pickle.dumps(subject))
        self.assertEqual(
            restored.local_birth_datetime.utcoffset(),
            subject.local_birth_datetime.utcoffset(),
        )

    def test_explicit_zone_subject_pickles(self):
        subject = _subject()
        _ = subject.local_birth_datetime
        restored = pickle.loads(pickle.dumps(subject))
        self.assertEqual(
            restored.local_birth_datetime.utcoffset(),
            subject.local_birth_datetime.utcoffset(),
        )

    def test_location_derived_subject_pickles(self):
        subject = _subject(zone_key=None)
        _ = subject.effective_timezone
        restored = pickle.loads(pickle.dumps(subject))
        self.assertEqual(
            str(restored.effective_timezone), str(subject.effective_timezone)
        )


if __name__ == "__main__":
    unittest.main()
