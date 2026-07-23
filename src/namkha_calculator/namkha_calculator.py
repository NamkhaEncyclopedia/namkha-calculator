"""Tibetan Namkha thread-cross calculation.

Main entry point::

    result = calculate_namkha(NamkhaType.YEAR, subject, CalculationMethod.CLASSIC)

``result.harmonized_aspects`` – sequence of harmonized :class:`HarmonizedAspect` objects
describing thread colors. ``result.mewa_numbers`` – mewa number for each aspect.

Only ``NamkhaType.YEAR`` supports multiple :class:`CalculationMethod` values;
all other types accept only ``CLASSIC`` and raise ``ValueError`` otherwise.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto, unique
from typing import Callable

from .methods import CalculationMethod
from .astrology import Animal, Element, Subject
from .aspects.shared_birth import BODY_ELEMENT, FORTUNE_ELEMENT, LIFE_ELEMENT
from .aspects.shared_mewa import MewaResult
from .aspects.year import calculate_mewas_cnnr, calculate_mewas_classic
from .calculation_notes import (
    CALCULATION_NOTES,
    CalculationNote,
    CalculationNoteItem,
    local_mean_time_note,
    local_time_dst_note,
    period_boundary_note,
    pre_gregorian_note,
    timezone_derivation_note,
)
from .astronomy import (
    LATITUDE_LIMIT,
    is_nonexistent_local_time,
    uses_local_mean_time,
)
from .calendar import (
    TibetanYearAttributes,
    classic_year_attributes,
    day_start,
    official_year_attributes,
    supported_year_range,
)
from .harmonizer import Aspect, HarmonizedAspect, harmonize_aspects


@unique
class NamkhaType(Enum):
    YEAR = auto()
    MONTH = auto()
    DAY = auto()
    HOUR = auto()


@dataclass
class NamkhaCalculationResult:
    subject: Subject
    calculation_method: CalculationMethod
    namkha_type: NamkhaType
    birth_element: Element
    birth_animal: Animal
    birth_mewa: int
    harmonized_aspects: tuple[HarmonizedAspect, ...]
    mewa_numbers: dict[Aspect, int]
    calculation_notes: tuple[CalculationNoteItem, ...]


@dataclass(frozen=True)
class _CalcResult:
    birth_element: Element
    birth_animal: Animal
    birth_mewa: int
    harmonized_aspects: tuple[HarmonizedAspect, ...]
    mewa_numbers: dict[Aspect, int]
    notes: tuple[CalculationNoteItem, ...]


def calculate_namkha(
    namkha_type: NamkhaType,
    subject: Subject,
    method: CalculationMethod = CalculationMethod.CLASSIC,
) -> NamkhaCalculationResult:
    calc_fn = _DISPATCH.get((namkha_type, method))
    if calc_fn is None:
        if (
            namkha_type is not NamkhaType.YEAR
            and method is not CalculationMethod.CLASSIC
        ):
            raise ValueError(
                f"{namkha_type.name} Namkha supports only the CLASSIC calculation method"
            )
        raise ValueError(
            f"Unsupported method {method.name!r} for {namkha_type.name} Namkha"
        )

    _validate_subject(subject)
    subject_notes = _collect_subject_notes(subject)
    calculation = calc_fn(subject)

    return NamkhaCalculationResult(
        subject=subject,
        calculation_method=method,
        namkha_type=namkha_type,
        birth_element=calculation.birth_element,
        birth_animal=calculation.birth_animal,
        birth_mewa=calculation.birth_mewa,
        harmonized_aspects=calculation.harmonized_aspects,
        mewa_numbers=calculation.mewa_numbers,
        calculation_notes=subject_notes + calculation.notes,
    )


def _validate_subject(subject: Subject) -> None:
    """Reject birth periods outside ephemeris coverage, birth instants that never
    existed in the timezone (a spring-forward clock gap or a dateline-jumped date;
    checked at every latitude), and - below LATITUDE_LIMIT - dawnless birth dates
    (a clock far behind mean solar time drifting dawn past midnight).
    """
    local_dt = subject.local_birth_datetime
    tz = subject.effective_timezone

    year_min, year_max = supported_year_range()
    utc_year = local_dt.astimezone(dt.timezone.utc).year
    if not year_min <= utc_year <= year_max:
        raise ValueError(
            f"birth year {subject.birth_datetime.year} (UTC year {utc_year}) "
            f"is outside the supported range "
            f"[{year_min}, {year_max}] (limited by the bundled ephemeris)"
        )

    if not uses_local_mean_time(
        subject.birth_datetime, tz
    ) and is_nonexistent_local_time(subject.birth_datetime, tz):
        raise ValueError(
            f"local birth date/time {subject.birth_datetime} does not exist in "
            f"{tz}: it was skipped by a clock change or a dateline jump; correct "
            "the birth date or time"
        )

    day_start(local_dt.date(), tz, subject.birth_location)


def _collect_subject_notes(subject: Subject) -> tuple[CalculationNoteItem, ...]:
    """Notes that depend only on the subject's location and local time."""
    notes: list[CalculationNoteItem] = []
    if abs(subject.birth_location.latitude) >= LATITUDE_LIMIT:
        notes.append(CALCULATION_NOTES[CalculationNote.HIGH_LATITUDE])
    notes.extend(timezone_derivation_note(subject.timezone_derivation))
    notes.extend(
        local_time_dst_note(
            subject.birth_datetime,
            subject.effective_timezone,
            subject.on_summer_time is not None,
        )
    )
    notes.extend(
        local_mean_time_note(
            subject.birth_datetime,
            subject.effective_timezone,
            subject.timezone_is_longitude_based,
        )
    )
    notes.extend(pre_gregorian_note(subject.birth_datetime, subject.birth_location))
    return tuple(notes)


def _calc_year_cnnr(subject: Subject) -> _CalcResult:
    year_attrs = official_year_attributes(
        subject.local_birth_datetime, subject.birth_location
    )
    return _build_year_result(subject, year_attrs, calculate_mewas_cnnr(year_attrs))


def _calc_year_classic(subject: Subject) -> _CalcResult:
    year_attrs = classic_year_attributes(
        subject.local_birth_datetime, subject.birth_location
    )
    return _build_year_result(subject, year_attrs, calculate_mewas_classic(year_attrs))


def _build_year_result(
    subject: Subject, year_attrs: TibetanYearAttributes, mewas: MewaResult
) -> _CalcResult:
    harmonized = harmonize_aspects(
        life=LIFE_ELEMENT[year_attrs.animal],
        body=BODY_ELEMENT[(year_attrs.animal, year_attrs.element)],
        capacity=year_attrs.element,
        fortune=FORTUNE_ELEMENT[year_attrs.animal],
        mewa_life=mewas.life.element,
        mewa_body=mewas.body.element,
        mewa_capacity=mewas.capacity.element,
        mewa_fortune=mewas.fortune.element,
    )
    return _CalcResult(
        birth_element=year_attrs.element,
        birth_animal=year_attrs.animal,
        birth_mewa=year_attrs.mewa_number,
        harmonized_aspects=harmonized,
        mewa_numbers={
            Aspect.MEWA_LIFE: mewas.life,
            Aspect.MEWA_BODY: mewas.body,
            Aspect.MEWA_CAPACITY: mewas.capacity,
            Aspect.MEWA_FORTUNE: mewas.fortune,
        },
        notes=period_boundary_note(subject.local_birth_datetime, year_attrs.boundaries),
    )


def _calc_month(subject: Subject) -> _CalcResult:
    raise NotImplementedError("MONTH Namkha calculation is not implemented yet")


def _calc_day(subject: Subject) -> _CalcResult:
    raise NotImplementedError("DAY Namkha calculation is not implemented yet")


def _calc_hour(subject: Subject) -> _CalcResult:
    raise NotImplementedError("HOUR Namkha calculation is not implemented yet")


_DISPATCH: dict[
    tuple[NamkhaType, CalculationMethod], Callable[[Subject], _CalcResult]
] = {
    (NamkhaType.YEAR, CalculationMethod.CNNR): _calc_year_cnnr,
    (NamkhaType.YEAR, CalculationMethod.CLASSIC): _calc_year_classic,
    (NamkhaType.MONTH, CalculationMethod.CLASSIC): _calc_month,
    (NamkhaType.DAY, CalculationMethod.CLASSIC): _calc_day,
    (NamkhaType.HOUR, CalculationMethod.CLASSIC): _calc_hour,
}
