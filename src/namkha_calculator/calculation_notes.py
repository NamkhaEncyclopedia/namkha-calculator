"""
Warnings and implications that may occur in the calculation.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique

from .astronomy import (
    Location,
    TimezoneDerivation,
    is_ambiguous_local_time,
    location_zone_key,
    uses_local_mean_time,
    zone_country,
)

# Birth time closer than this to a period boundary triggers a PERIOD_BOUNDARY note.
PERIOD_BOUNDARY_THRESHOLD = dt.timedelta(minutes=5)

# First day of the Gregorian calendar at the original 1582 reform; the cutoff
# for countries absent from the adoption table and for locations without a
# country (open water, unmatched coordinates).
GREGORIAN_REFORM_DATE = dt.date(1582, 10, 15)

# Date each country finished switching to the Gregorian calendar, by ISO 3166
# country code, for those that switched after the 1582 reform. If a country
# switched region by region, we use the last region's date, and round an
# unclear date up to the next 1 January. So the caution may fire too early
# during a country's switch, but never too late. Dates are keyed by the modern
# country, so a region that stayed on the Julian calendar under a past empire
# (e.g. Russian-ruled Poland, Julian until 1918) while its modern country
# switched earlier may still slip through.
GREGORIAN_ADOPTION_DATES = {
    "AT": dt.date(1584, 1, 1),
    "CZ": dt.date(1585, 1, 1),
    "HU": dt.date(1587, 11, 1),
    "DE": dt.date(1700, 3, 1),
    "DK": dt.date(1700, 3, 1),
    "NO": dt.date(1700, 3, 1),
    "FO": dt.date(1700, 3, 1),  # Faroe Islands, under Denmark-Norway
    "GL": dt.date(1700, 3, 1),  # Greenland, under Denmark
    "SJ": dt.date(1700, 3, 1),  # Svalbard and Jan Mayen, under Norway
    "IS": dt.date(1700, 11, 28),
    "NL": dt.date(1701, 7, 12),
    "GB": dt.date(1752, 9, 14),
    "IE": dt.date(1752, 9, 14),
    "IM": dt.date(1752, 9, 14),
    "JE": dt.date(1752, 9, 14),
    "GG": dt.date(1752, 9, 14),
    "US": dt.date(1752, 9, 14),
    "CA": dt.date(1752, 9, 14),
    "SE": dt.date(1753, 3, 1),
    "FI": dt.date(1753, 3, 1),
    "AX": dt.date(1753, 3, 1),  # Aland Islands, under Sweden
    "CH": dt.date(1813, 1, 1),
    "JP": dt.date(1873, 1, 1),
    "EG": dt.date(1876, 1, 1),
    "TH": dt.date(1889, 4, 1),
    "KR": dt.date(1896, 1, 1),
    "KP": dt.date(1896, 1, 1),
    "TW": dt.date(1896, 1, 1),
    "AL": dt.date(1913, 1, 1),
    "BG": dt.date(1916, 4, 14),
    "RU": dt.date(1918, 2, 14),
    "UA": dt.date(1918, 2, 14),
    "BY": dt.date(1918, 2, 14),
    "EE": dt.date(1918, 2, 14),
    "LV": dt.date(1918, 2, 14),
    "LT": dt.date(1918, 2, 14),
    "GE": dt.date(1918, 2, 14),
    "AM": dt.date(1918, 2, 14),
    "AZ": dt.date(1918, 2, 14),
    "KZ": dt.date(1918, 2, 14),
    "KG": dt.date(1918, 2, 14),
    "TJ": dt.date(1918, 2, 14),
    "TM": dt.date(1918, 2, 14),
    "UZ": dt.date(1918, 2, 14),
    "RS": dt.date(1919, 1, 28),
    "ME": dt.date(1919, 1, 28),
    "MK": dt.date(1919, 1, 28),
    "BA": dt.date(1919, 1, 28),
    "RO": dt.date(1919, 4, 14),
    "MD": dt.date(1919, 4, 14),
    "GR": dt.date(1923, 3, 1),
    "TR": dt.date(1926, 1, 1),
    "CN": dt.date(1929, 1, 1),
}

# Zone-level overrides where one zone's calendar history differs from the
# rest of its country: Alaska stayed Julian until the 1867 US purchase.
GREGORIAN_ADOPTION_DATES_BY_ZONE = {
    "America/Adak": dt.date(1867, 10, 18),
    "America/Anchorage": dt.date(1867, 10, 18),
    "America/Juneau": dt.date(1867, 10, 18),
    "America/Metlakatla": dt.date(1867, 10, 18),
    "America/Nome": dt.date(1867, 10, 18),
    "America/Sitka": dt.date(1867, 10, 18),
    "America/Yakutat": dt.date(1867, 10, 18),
}


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


def gregorian_adoption_date(location: Location) -> dt.date:
    """First Gregorian date at the location; the 1582 reform date if unknown."""
    key = location_zone_key(location)
    if key is None:
        return GREGORIAN_REFORM_DATE
    if key in GREGORIAN_ADOPTION_DATES_BY_ZONE:
        return GREGORIAN_ADOPTION_DATES_BY_ZONE[key]
    country = zone_country(key)
    if country in GREGORIAN_ADOPTION_DATES:
        return GREGORIAN_ADOPTION_DATES[country]
    return GREGORIAN_REFORM_DATE


def pre_gregorian_note(
    birth_datetime: dt.datetime, location: Location
) -> tuple[CalculationNoteItem, ...]:
    """Caution when the birth date precedes the Gregorian calendar at the birth place."""
    if birth_datetime.date() < gregorian_adoption_date(location):
        return (CALCULATION_NOTES[CalculationNote.PRE_GREGORIAN_DATE],)
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
