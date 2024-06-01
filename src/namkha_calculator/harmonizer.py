"""
Harmonizer
"""

from dataclasses import dataclass
from enum import unique, Enum
from typing import Optional


@unique
class Element(Enum, str):
    WATER = "Water"
    WOOD = "Wood"
    FIRE = "Fire"
    EARTH = "Earth"
    METAL = "Metal"


@dataclass
class ElementItem:
    mother: Element
    son: Element


@unique
class AspectName(Enum, str):
    LIFE = "life"
    BODY = "body"
    CAPACITY = "capacity"
    FORTUNE = "fortune"
    MEWA_LIFE = "mewa_life"
    MEWA_BODY = "mewa_body"
    MEWA_CAPACITY = "mewa_capacity"
    MEWA_FORTUNE = "mewa_fortune"


@dataclass
class Aspect:
    name: AspectName
    center: Element
    harmonization_seq: tuple[Element, ...]
    is_conflicted: bool
    has_deep_water: Optional[bool] = None


ELEMENTS_CIRCLE = {
    Element.WATER: ElementItem(mother=Element.METAL, son=Element.WOOD),
    Element.WOOD: ElementItem(mother=Element.WATER, son=Element.FIRE),
    Element.FIRE: ElementItem(mother=Element.WOOD, son=Element.EARTH),
    Element.EARTH: ElementItem(mother=Element.FIRE, son=Element.METAL),
    Element.METAL: ElementItem(mother=Element.EARTH, son=Element.WATER),
}


def __get_son(element: Element) -> Element:
    return ELEMENTS_CIRCLE[element].son


def __get_mother(element: Element) -> Element:
    return ELEMENTS_CIRCLE[element].mother


def __circle_forwards(start_element: Element) -> list[Element]:
    result = [start_element]
    for _ in range(4):
        result.append(__get_son(result[-1]))
    return result


def __circle_backwards(start_element: Element) -> list[Element]:
    result = [start_element]
    for _ in range(4):
        result.append(__get_mother(result[-1]))
    return result


def __shortest_path(first_element: Element, second_element: Element) -> list[Element]:
    fwd = __circle_forwards(first_element)
    fwd = fwd[: fwd.index(second_element) + 1]
    rev = __circle_backwards(first_element)
    rev = rev[: rev.index(second_element) + 1]
    return fwd[1:] if len(fwd) < len(rev) else rev[1:]


def __get_edge_element(center_element: Element) -> Element:
    return ELEMENTS_CIRCLE[center_element].mother


def __are_in_conflict(first_element: Element, second_element: Element) -> bool:
    if (
        first_element in [__get_son(second_element), __get_mother(second_element)]
        or first_element == second_element
    ):
        return False
    return True


def harmonize_aspects(
    life: Element,
    body: Element,
    capacity: Element,
    fortune: Element,
    mewa_life: Element,
    mewa_body: Element,
    mewa_capacity: Element,
    mewa_fortune: Element,
) -> tuple[Aspect, ...]:
    """
    Calculates the harmonization sequence for each aspect based on the given elements.

    Args:
        life (Element): The element representing life.
        body (Element): The element representing body.
        capacity (Element): The element representing capacity.
        fortune (Element): The element representing fortune.
        mewa_life (Element): The element representing mewa life.
        mewa_body (Element): The element representing mewa body.
        mewa_capacity (Element): The element representing mewa capacity.
        mewa_fortune (Element): The element representing mewa fortune.

    Returns:
        tuple[Aspect, ...]: A tuple of Aspect objects representing the harmonization sequence for each aspect.

    Raises:
        None

    """
    edge_element = __get_edge_element(life)
    result = []

    life_seq = __circle_forwards(start_element=life)
    result.append(
        Aspect(name=AspectName.LIFE, center=life, harmonization_seq=tuple(life_seq[1:]))
    )

    for element, name, harmonize_to in zip(
        [body, capacity, fortune, mewa_life, mewa_body, mewa_capacity, mewa_fortune],
        list(AspectName)[1:],
        [life] * 4 + [mewa_life] * 3,
    ):
        is_conflicted = False

        if __are_in_conflict(element, harmonize_to):
            is_conflicted = True
            stripes = __circle_backwards(element)
            if stripes[-1] == edge_element:
                stripes.extend([__get_mother(edge_element), edge_element])
            else:
                stripes.extend(
                    __shortest_path(
                        first_element=stripes[-1], second_element=edge_element
                    )
                )
        else:
            stripes = __circle_forwards(element)
            if stripes[-1] != edge_element:
                stripes.extend(
                    __shortest_path(
                        first_element=stripes[-1], second_element=edge_element
                    )
                )

        result.append(
            Aspect(
                name=name,
                center=stripes.pop(0),
                harmonization_seq=tuple(stripes),
                is_conflicted=is_conflicted,
            )
        )

    return tuple(result)
