"""
Warnings and implications that may occur in the calculation.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique

import pytz

from .astronomy import PytzTimezone

# Birth time closer than this to a period boundary triggers a PERIOD_BOUNDARY note.
PERIOD_BOUNDARY_THRESHOLD = dt.timedelta(minutes=5)


@unique
class CalculationNoteType(Enum):
    NOTICE = auto()
    CAUTION = auto()


@unique
class CalculationNote(Enum):
    HIGH_LATITUDE = auto()
    PERIOD_BOUNDARY = auto()
    AMBIGUOUS_LOCAL_TIME = auto()
    NONEXISTENT_LOCAL_TIME = auto()


@dataclass(frozen=True)
class CalculationNoteItem:
    note: CalculationNote
    note_type: CalculationNoteType
    message: str
    doc: str = ""


CALCULATION_NOTES = {
    CalculationNote.HIGH_LATITUDE: CalculationNoteItem(
        note=CalculationNote.HIGH_LATITUDE,
        note_type=CalculationNoteType.NOTICE,
        message="High latitude: default sunrise/sunset times are used.",
    ),
    CalculationNote.PERIOD_BOUNDARY: CalculationNoteItem(
        note=CalculationNote.PERIOD_BOUNDARY,
        note_type=CalculationNoteType.CAUTION,
        message="Birth time very close to a period boundary; be sure that it is precise enough.",
    ),
    CalculationNote.AMBIGUOUS_LOCAL_TIME: CalculationNoteItem(
        note=CalculationNote.AMBIGUOUS_LOCAL_TIME,
        note_type=CalculationNoteType.CAUTION,
        message="Local birth time is ambiguous due to a daylight-saving change; "
        "the standard-time reading was used.",
    ),
    CalculationNote.NONEXISTENT_LOCAL_TIME: CalculationNoteItem(
        note=CalculationNote.NONEXISTENT_LOCAL_TIME,
        note_type=CalculationNoteType.CAUTION,
        message="Local birth time falls in a daylight-saving gap and does not exist; "
        "the standard-time reading was used.",
    ),
}


def local_time_dst_note(
    birth_datetime: dt.datetime, tz: PytzTimezone
) -> tuple[CalculationNoteItem, ...]:
    """Caution if the naive local birth time is ambiguous or non-existent on a DST transition.

    The calculation itself resolves such times with ``is_dst=False``; this only flags them.
    """
    try:
        tz.localize(birth_datetime, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        return (CALCULATION_NOTES[CalculationNote.AMBIGUOUS_LOCAL_TIME],)
    except pytz.exceptions.NonExistentTimeError:
        return (CALCULATION_NOTES[CalculationNote.NONEXISTENT_LOCAL_TIME],)
    return ()


def period_boundary_note(
    birth_dt: dt.datetime, boundaries: tuple[dt.datetime, ...]
) -> tuple[CalculationNoteItem, ...]:
    """Caution note if birth_dt is within the threshold of any period boundary.

    All datetimes must be tz-aware; mixing naive/aware would break the subtraction.
    Everything is normalized to UTC before comparison.
    """
    if birth_dt.tzinfo is None:
        raise ValueError("birth_dt must be tz-aware")
    if any(b.tzinfo is None for b in boundaries):
        raise ValueError("boundaries must be tz-aware")
    birth_utc = birth_dt.astimezone(dt.timezone.utc)
    if any(
        abs(birth_utc - b.astimezone(dt.timezone.utc)) <= PERIOD_BOUNDARY_THRESHOLD
        for b in boundaries
    ):
        return (CALCULATION_NOTES[CalculationNote.PERIOD_BOUNDARY],)
    return ()
