"""
Warnings and implications that may occur in the calculation.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique

from .localization import is_ambiguous_local_time, uses_local_mean_time
from .tz import LATITUDE_LIMIT, Location, ResolvedTimezone, TimezoneDerivation

# Temporary: the Gregorian tables moved to zone_derivation because they need
# the same location lookup as the timezone. Nothing on the calculation path may
# import zone_derivation, so this goes away once the resolved timezone carries
# the adoption date with it.
from .zone_derivation.gregorian import gregorian_adoption_date

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
    AMBIGUOUS_LOCAL_TIME_RESOLVED = auto()
    LOCAL_MEAN_TIME = auto()
    PRE_GREGORIAN_DATE = auto()
    TIMEZONE_ESTIMATED = auto()
    TIMEZONE_BORDERS_UNCERTAIN = auto()


TIMEZONE_DERIVATION_NOTES = {
    TimezoneDerivation.ESTIMATED: CalculationNote.TIMEZONE_ESTIMATED,
    TimezoneDerivation.BORDERS_UNCERTAIN: CalculationNote.TIMEZONE_BORDERS_UNCERTAIN,
}


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
        message="Local birth time is ambiguous due to a clock change and was "
        "guessed as the later (standard-time) reading; set on_summer_time to say "
        "which reading is correct, as it can shift the hour.",
    ),
    CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED: CalculationNoteItem(
        note=CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED,
        note_type=CalculationNoteType.NOTICE,
        message="Local birth time was ambiguous due to a clock change; resolved "
        "using the on_summer_time value you provided.",
    ),
    CalculationNote.LOCAL_MEAN_TIME: CalculationNoteItem(
        note=CalculationNote.LOCAL_MEAN_TIME,
        note_type=CalculationNoteType.NOTICE,
        message="The birth time was read as local mean solar time at the birth "
        "longitude, not as a standard clock time. This applies when the birth "
        "predates standard time in this region, or falls over open water or "
        "outside any timezone.",
    ),
    CalculationNote.PRE_GREGORIAN_DATE: CalculationNoteItem(
        note=CalculationNote.PRE_GREGORIAN_DATE,
        note_type=CalculationNoteType.CAUTION,
        message="Birth date precedes the adoption of the Gregorian calendar "
        "at the birth place; if the source record uses the Julian or another "
        "local calendar, convert the date to Gregorian first.",
    ),
    CalculationNote.TIMEZONE_ESTIMATED: CalculationNoteItem(
        note=CalculationNote.TIMEZONE_ESTIMATED,
        note_type=CalculationNoteType.CAUTION,
        message="The timezone could not be determined with certainty from the "
        "birth location and date; the best historically recorded regional "
        "time was used. Set birth_timezone if the local legal time is known.",
    ),
    CalculationNote.TIMEZONE_BORDERS_UNCERTAIN: CalculationNoteItem(
        note=CalculationNote.TIMEZONE_BORDERS_UNCERTAIN,
        note_type=CalculationNoteType.CAUTION,
        message="Borders around the birth place changed close to the birth "
        "year, so even the country whose time applied is uncertain; the best "
        "historically recorded regional time was used. Set birth_timezone if "
        "the local legal time is known.",
    ),
}


def timezone_derivation_note(
    derivation: TimezoneDerivation,
) -> tuple[CalculationNoteItem, ...]:
    """Caution matching how sure the timezone derivation is; nothing when
    certain."""
    note = TIMEZONE_DERIVATION_NOTES.get(derivation)
    return () if note is None else (CALCULATION_NOTES[note],)


def local_time_dst_note(
    birth_datetime: dt.datetime, tz: dt.tzinfo, occurrence_specified: bool
) -> tuple[CalculationNoteItem, ...]:
    """Flag a birth time made ambiguous by a fall-back clock change.

    An ambiguous time gives a NOTICE when the user pinned it (occurrence_specified)
    and a CAUTION otherwise. A non-existent time (skipped by a spring-forward gap)
    is rejected earlier in the public path, not flagged here. The
    pre-standard-time (LMT) era needs no special case: it is a zone's first
    era, so it holds no clock changes of its own, and the fall-back that ends
    it is a real clock change worth flagging.
    """
    if is_ambiguous_local_time(birth_datetime, tz):
        note = (
            CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED
            if occurrence_specified
            else CalculationNote.AMBIGUOUS_LOCAL_TIME
        )
        return (CALCULATION_NOTES[note],)
    return ()


def local_mean_time_note(
    birth_datetime: dt.datetime, tz: dt.tzinfo, longitude_based: bool = False
) -> tuple[CalculationNoteItem, ...]:
    """Notice when the birth offset is longitude-based rather than a civil
    standard clock: the pre-standard-time (LMT) era, or a location-derived
    nautical/mean-solar zone (longitude_based)."""
    if longitude_based or uses_local_mean_time(birth_datetime, tz):
        return (CALCULATION_NOTES[CalculationNote.LOCAL_MEAN_TIME],)
    return ()


def pre_gregorian_note(
    birth_datetime: dt.datetime, location: Location
) -> tuple[CalculationNoteItem, ...]:
    """Caution when the birth date precedes the Gregorian calendar at the birth place."""
    if birth_datetime.date() < gregorian_adoption_date(location):
        return (CALCULATION_NOTES[CalculationNote.PRE_GREGORIAN_DATE],)
    return ()


def input_notes(
    resolved_timezone: ResolvedTimezone, birth_datetime: dt.datetime
) -> tuple[CalculationNoteItem, ...]:
    """Notes that follow from the birth details alone.

    These are known as soon as the timezone is settled. A form can show them
    while the user is still entering data. Notes that need the calculation
    itself are not here.

    birth_datetime is the naive local time, as entered.
    """
    notes: list[CalculationNoteItem] = []
    if abs(resolved_timezone.for_latitude) >= LATITUDE_LIMIT:
        notes.append(CALCULATION_NOTES[CalculationNote.HIGH_LATITUDE])
    notes.extend(timezone_derivation_note(resolved_timezone.derivation))
    tz = resolved_timezone.tzinfo
    notes.extend(
        local_time_dst_note(
            birth_datetime, tz, resolved_timezone.on_summer_time is not None
        )
    )
    notes.extend(
        local_mean_time_note(birth_datetime, tz, resolved_timezone.is_longitude_based)
    )
    # The adoption date travels with the resolved timezone, so this does not
    # repeat pre_gregorian_note's location lookup.
    if birth_datetime.date() < resolved_timezone.gregorian_adoption_date:
        notes.append(CALCULATION_NOTES[CalculationNote.PRE_GREGORIAN_DATE])
    return tuple(notes)


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
