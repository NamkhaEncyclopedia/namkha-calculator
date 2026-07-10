import unittest
from datetime import datetime

import pytz

from namkha_calculator.astrology import Gender, Subject
from namkha_calculator.astronomy import Location
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


if __name__ == "__main__":
    unittest.main()
