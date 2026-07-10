from ..astrology import Animal, Element
from ..calendar import (
    TibetanYearAttributes,
    TIB_WESTERN_OFFSET,
    nearest_previous_year_with_animal,
    year_with_animal_and_element_in_metreng,
    year_mewa,
)
from .shared_mewa import MewaAspect, MewaResult, BODY_MEWA_TO_LIFE_CAPACITY_MEWA

CNNR_POINT_OF_FORTUNE = {
    Animal.TIGER: Animal.MONKEY,
    Animal.HORSE: Animal.MONKEY,
    Animal.DOG: Animal.MONKEY,
    Animal.MOUSE: Animal.TIGER,
    Animal.DRAGON: Animal.TIGER,
    Animal.MONKEY: Animal.TIGER,
    Animal.BIRD: Animal.BOAR,
    Animal.OX: Animal.BOAR,
    Animal.SNAKE: Animal.BOAR,
    Animal.BOAR: Animal.SNAKE,
    Animal.SHEEP: Animal.SNAKE,
    Animal.HARE: Animal.SNAKE,
}


CLASSIC_POINT_OF_FORTUNE = {
    Animal.TIGER: (Element.METAL, Animal.MONKEY),
    Animal.HORSE: (Element.METAL, Animal.MONKEY),
    Animal.DOG: (Element.METAL, Animal.MONKEY),
    Animal.BOAR: (Element.FIRE, Animal.SNAKE),
    Animal.SHEEP: (Element.FIRE, Animal.SNAKE),
    Animal.HARE: (Element.FIRE, Animal.SNAKE),
    Animal.BIRD: (Element.WATER, Animal.BOAR),
    Animal.OX: (Element.WATER, Animal.BOAR),
    Animal.SNAKE: (Element.WATER, Animal.BOAR),
    Animal.MOUSE: (Element.WOOD, Animal.TIGER),
    Animal.DRAGON: (Element.WOOD, Animal.TIGER),
    Animal.MONKEY: (Element.WOOD, Animal.TIGER),
}


def fortune_mewa_classic(year_attrs: TibetanYearAttributes) -> MewaAspect:
    element, animal = CLASSIC_POINT_OF_FORTUNE[year_attrs.animal]
    fortune_year = year_with_animal_and_element_in_metreng(
        animal, element, year_attrs.tibetan_year_number
    )
    body_mewa = year_mewa(fortune_year - TIB_WESTERN_OFFSET)
    life_mewa, _ = BODY_MEWA_TO_LIFE_CAPACITY_MEWA[body_mewa]
    return MewaAspect(life_mewa)


def fortune_mewa_cnnr(year_attrs: TibetanYearAttributes) -> MewaAspect:
    fortune_animal = CNNR_POINT_OF_FORTUNE[year_attrs.animal]
    fortune_year = nearest_previous_year_with_animal(
        year_attrs.tibetan_year_number, fortune_animal
    )
    return MewaAspect(year_mewa(fortune_year - TIB_WESTERN_OFFSET))


def calculate_mewas_cnnr(year_attrs: TibetanYearAttributes) -> MewaResult:
    # CNNR rule swaps the table's (life, capacity) order.
    capacity_mewa, life_mewa = BODY_MEWA_TO_LIFE_CAPACITY_MEWA[year_attrs.mewa_number]
    return MewaResult(
        life=MewaAspect(life_mewa),
        body=MewaAspect(year_attrs.mewa_number),
        capacity=MewaAspect(capacity_mewa),
        fortune=fortune_mewa_cnnr(year_attrs),
    )


def calculate_mewas_classic(year_attrs: TibetanYearAttributes) -> MewaResult:
    life_mewa, capacity_mewa = BODY_MEWA_TO_LIFE_CAPACITY_MEWA[year_attrs.mewa_number]
    return MewaResult(
        life=MewaAspect(life_mewa),
        body=MewaAspect(year_attrs.mewa_number),
        capacity=MewaAspect(capacity_mewa),
        fortune=fortune_mewa_classic(year_attrs),
    )
