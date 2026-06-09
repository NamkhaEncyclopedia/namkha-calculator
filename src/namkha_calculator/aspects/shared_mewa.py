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
