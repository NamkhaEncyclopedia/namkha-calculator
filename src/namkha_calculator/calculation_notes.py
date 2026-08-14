"""
Implications and warnings that may occur in the calculation.

Three parts:

Vocabulary. CalculationNote names each condition, CalculationNoteType grades it
as a notice or a caution, and CALCULATION_NOTES holds the text.

Note builders. One function per condition, each returning a tuple so callers can
join the results. input_notes gathers the conditions that follow from the birth
details alone, so a form can show them before any calculation runs.
period_boundary_note needs the result, so it stays outside input_notes.

Timezone label. timezone_label names the timezone on a birth line. It recognizes
mean solar time with the same check as the LOCAL_MEAN_TIME note, so the label
and the note never disagree.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique

from .localization import is_ambiguous_local_time, uses_local_mean_time
from .tz import (
    LATITUDE_LIMIT,
    _MEAN_SOLAR_TZNAME,
    Location,
    ResolvedTimezone,
    TimezoneDerivation,
)

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
        "guessed as the later (standard-time) reading; pass on_summer_time to "
        "zone_derivation.resolve_timezone to say which reading is correct, as it "
        "can shift the hour.",
    ),
    CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED: CalculationNoteItem(
        note=CalculationNote.AMBIGUOUS_LOCAL_TIME_RESOLVED,
        note_type=CalculationNoteType.NOTICE,
        message="Local birth time was ambiguous due to a clock change; resolved "
        "using the on_summer_time value given to zone_derivation.resolve_timezone.",
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
        "time was used. If the local legal time is known, pass it to "
        "zone_derivation.resolve_timezone as zone_key or offset.",
    ),
    CalculationNote.TIMEZONE_BORDERS_UNCERTAIN: CalculationNoteItem(
        note=CalculationNote.TIMEZONE_BORDERS_UNCERTAIN,
        note_type=CalculationNoteType.CAUTION,
        message="Borders around the birth place changed close to the birth "
        "year, so even the country whose time applied is uncertain; the best "
        "historically recorded regional time was used. If the local legal time "
        "is known, pass it to zone_derivation.resolve_timezone as zone_key or "
        "offset.",
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


def is_mean_solar_birth(
    birth_datetime: dt.datetime, tz: dt.tzinfo, longitude_based: bool
) -> bool:
    """Whether the birth offset comes from longitude alone, not from a civil clock.

    Either the derived timezone is a nautical or mean solar one, which
    longitude_based records, or the birth falls in the zone's pre-standard-time
    era. Only the first is visible in a ResolvedTimezone, so the birth date is
    needed as well.

    local_mean_time_note and timezone_label both call this, so the note and the
    label always agree.
    """
    return longitude_based or uses_local_mean_time(birth_datetime, tz)


def local_mean_time_note(
    birth_datetime: dt.datetime, tz: dt.tzinfo, longitude_based: bool
) -> tuple[CalculationNoteItem, ...]:
    """Notice when the birth offset comes from longitude alone rather than from
    a civil standard clock."""
    if is_mean_solar_birth(birth_datetime, tz, longitude_based):
        return (CALCULATION_NOTES[CalculationNote.LOCAL_MEAN_TIME],)
    return ()


def timezone_label(
    resolved_timezone: ResolvedTimezone, birth_datetime: dt.datetime
) -> str | None:
    """Name for the timezone, or None when it has no name.

    None means the user gave a plain UTC offset, so the offset is the whole
    answer and a caller shows it alone.

    Mean solar time is checked before the key, because the key can name a zone
    that did not produce the offset in use: an 1849 Arkhangelsk birth resolves to
    Europe/Moscow but runs on Arkhangelsk mean solar time.
    """
    if is_mean_solar_birth(
        birth_datetime,
        resolved_timezone.tzinfo,
        resolved_timezone.is_longitude_based,
    ):
        return _MEAN_SOLAR_TZNAME
    return resolved_timezone.key


def pre_gregorian_note(
    birth_datetime: dt.datetime, adoption_date: dt.date
) -> tuple[CalculationNoteItem, ...]:
    """Caution when the birth date precedes the Gregorian calendar at the birth
    place.

    adoption_date must be the date looked up for the birth place, not one cutoff
    used for every place: pass ResolvedTimezone.gregorian_adoption_date, or
    zone_derivation.gregorian_adoption_date(location) when there is no resolved
    timezone at hand. It is looked up while the timezone is derived and travels
    with it, so this never looks up the birth place itself.
    """
    if birth_datetime.date() < adoption_date:
        return (CALCULATION_NOTES[CalculationNote.PRE_GREGORIAN_DATE],)
    return ()


def input_notes(
    resolved_timezone: ResolvedTimezone,
    location: Location,
    birth_datetime: dt.datetime,
) -> tuple[CalculationNoteItem, ...]:
    """Notes that follow from the birth details alone.

    These are known as soon as the timezone is resolved. A form can show them
    while the user is still entering data. Notes that need the calculation
    itself are not here.

    birth_datetime is the naive local time, as entered.

    The timezone must be the one worked out for this location and date. A
    mismatch raises StaleTimezoneError: forms call this without a Subject, so
    nothing else compares the two.
    """
    resolved_timezone.assert_binds(location, birth_datetime)
    notes: list[CalculationNoteItem] = []
    if abs(location.latitude) >= LATITUDE_LIMIT:
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
    notes.extend(
        pre_gregorian_note(birth_datetime, resolved_timezone.gregorian_adoption_date)
    )
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
