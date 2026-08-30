"""
Mewa Aspect calculation tables and classes shared between multiple Namkha types.
"""

from typing import NamedTuple
from ..astrology import Element

MEWA_TO_ELEMENT = {
    1: Element.METAL,
    2: Element.WATER,
    3: Element.WATER,
    4: Element.WOOD,
    5: Element.EARTH,
    6: Element.METAL,
    7: Element.FIRE,
    8: Element.METAL,
    9: Element.FIRE,
}

BODY_MEWA_TO_LIFE_CAPACITY_MEWA = {
    1: (7, 4),
    2: (8, 5),
    3: (9, 6),
    4: (1, 7),
    5: (2, 8),
    6: (3, 9),
    7: (4, 1),
    8: (5, 2),
    9: (6, 3),
}


class MewaAspect(int):
    """Mewa number 1-9. `.element` derives the associated Element via MEWA_TO_ELEMENT."""

    @property
    def element(self) -> Element:  # pyrefly: ignore
        return MEWA_TO_ELEMENT[self]


class MewaResult(NamedTuple):
    life: MewaAspect
    body: MewaAspect
    capacity: MewaAspect
    fortune: MewaAspect


def mewa_result_classic(body_mewa: int, fortune: MewaAspect) -> MewaResult:
    """Mewa aspects of a birth period for the Classic method.

    BODY_MEWA_TO_LIFE_CAPACITY_MEWA gives life and capacity in that order,
    which is the order Classic uses. The CNNR method reads the same pair the
    other way round, so it does not use this.

    Fortune is the fortune mewa of the birth year for every Namkha type. The
    caller passes it in, because aspects.year works it out and imports this
    module.
    """
    life_mewa, capacity_mewa = BODY_MEWA_TO_LIFE_CAPACITY_MEWA[body_mewa]
    return MewaResult(
        life=MewaAspect(life_mewa),
        body=MewaAspect(body_mewa),
        capacity=MewaAspect(capacity_mewa),
        fortune=fortune,
    )
