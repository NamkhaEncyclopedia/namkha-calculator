import unittest
from datetime import datetime

import pytz

from namkha_calculator.astrology import Gender, Subject
from namkha_calculator.astronomy import Location
from namkha_calculator.calculation_notes import (
    CalculationNote,
)
from namkha_calculator.methods import CalculationMethod
from namkha_calculator.namkha_calculator import NamkhaType, calculate_namkha

# Stuttgart; Losar times calculated from the calendar code (Europe/Berlin, CET):
#   official      Losar (Tibetan year 2151) = 2024-02-10 07:07:39
#   astrological  Losar (Tibetan year 2151) = 2023-12-13 07:30:40
_TZ = "Europe/Berlin"
_LAT, _LON = 48.7758, 9.1829


def _subject(dt_str: str) -> Subject:
    return Subject(
        gender=Gender.MALE,
        birth_datetime=datetime.strptime(dt_str, "%d.%m.%Y %H:%M"),
        birth_timezone=pytz.timezone(_TZ),
        birth_location=Location(_LAT, _LON),
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


if __name__ == "__main__":
    unittest.main()
