from types import MappingProxyType # Immutable Dicts

from .astrology import Animal, Element

# Birth Period Animal -> Life Element
life_element = MappingProxyType(
    {
        Animal.MOUSE: Element.WATER,
        Animal.OX: Element.EARTH,
        Animal.TIGER: Element.WOOD,
        Animal.HARE: Element.WOOD,
        Animal.DRAGON: Element.EARTH,
        Animal.SNAKE: Element.FIRE,
        Animal.HORSE: Element.FIRE,
        Animal.SHEEP: Element.EARTH,
        Animal.MONKEY: Element.METAL,
        Animal.BIRD: Element.METAL,
        Animal.DOG: Element.EARTH,
        Animal.BOAR: Element.WATER,
    }
)

# (Birth Period Elmennt, Birth Period Animal) -> Body Element
body_element = MappingProxyType(
    {
        (Animal.MOUSE, Element.WOOD): Element.METAL,
        (Animal.OX, Element.WOOD): Element.METAL,
        (Animal.HORSE, Element.WOOD): Element.METAL,
        (Animal.SHEEP, Element.WOOD): Element.METAL,
        (Animal.TIGER, Element.WATER): Element.METAL,
        (Animal.HARE, Element.WATER): Element.METAL,
        (Animal.BIRD, Element.WATER): Element.METAL,
        (Animal.MONKEY, Element.WATER): Element.METAL,
        (Animal.DOG, Element.METAL): Element.METAL,
        (Animal.BOAR, Element.METAL): Element.METAL,
        (Animal.DRAGON, Element.METAL): Element.METAL,
        (Animal.SNAKE, Element.METAL): Element.METAL,
        (Animal.MOUSE, Element.WATER): Element.WOOD,
        (Animal.OX, Element.WATER): Element.WOOD,
        (Animal.HORSE, Element.WATER): Element.WOOD,
        (Animal.SHEEP, Element.WATER): Element.WOOD,
        (Animal.TIGER, Element.METAL): Element.WOOD,
        (Animal.HARE, Element.METAL): Element.WOOD,
        (Animal.BIRD, Element.METAL): Element.WOOD,
        (Animal.MONKEY, Element.METAL): Element.WOOD,
        (Animal.DOG, Element.EARTH): Element.WOOD,
        (Animal.BOAR, Element.EARTH): Element.WOOD,
        (Animal.DRAGON, Element.EARTH): Element.WOOD,
        (Animal.SNAKE, Element.EARTH): Element.WOOD,
        (Animal.MOUSE, Element.FIRE): Element.WATER,
        (Animal.OX, Element.FIRE): Element.WATER,
        (Animal.HORSE, Element.FIRE): Element.WATER,
        (Animal.SHEEP, Element.FIRE): Element.WATER,
        (Animal.TIGER, Element.WOOD): Element.WATER,
        (Animal.HARE, Element.WOOD): Element.WATER,
        (Animal.BIRD, Element.WOOD): Element.WATER,
        (Animal.MONKEY, Element.WOOD): Element.WATER,
        (Animal.DOG, Element.WATER): Element.WATER,
        (Animal.BOAR, Element.WATER): Element.WATER,
        (Animal.DRAGON, Element.WATER): Element.WATER,
        (Animal.SNAKE, Element.WATER): Element.WATER,
        (Animal.MOUSE, Element.METAL): Element.EARTH,
        (Animal.OX, Element.METAL): Element.EARTH,
        (Animal.HORSE, Element.METAL): Element.EARTH,
        (Animal.SHEEP, Element.METAL): Element.EARTH,
        (Animal.TIGER, Element.EARTH): Element.EARTH,
        (Animal.HARE, Element.EARTH): Element.EARTH,
        (Animal.BIRD, Element.EARTH): Element.EARTH,
        (Animal.MONKEY, Element.EARTH): Element.EARTH,
        (Animal.DOG, Element.FIRE): Element.EARTH,
        (Animal.BOAR, Element.FIRE): Element.EARTH,
        (Animal.DRAGON, Element.FIRE): Element.EARTH,
        (Animal.SNAKE, Element.FIRE): Element.EARTH,
        (Animal.MOUSE, Element.EARTH): Element.FIRE,
        (Animal.OX, Element.EARTH): Element.FIRE,
        (Animal.HORSE, Element.EARTH): Element.FIRE,
        (Animal.SHEEP, Element.EARTH): Element.FIRE,
        (Animal.TIGER, Element.FIRE): Element.FIRE,
        (Animal.HARE, Element.FIRE): Element.FIRE,
        (Animal.BIRD, Element.FIRE): Element.FIRE,
        (Animal.MONKEY, Element.FIRE): Element.FIRE,
        (Animal.DOG, Element.WOOD): Element.FIRE,
        (Animal.BOAR, Element.WOOD): Element.FIRE,
        (Animal.DRAGON, Element.WOOD): Element.FIRE,
        (Animal.SNAKE, Element.WOOD): Element.FIRE,
    }
)

# Birth Period Animal -> Fortune Element
fortune_element = MappingProxyType(
    {
        Animal.TIGER: Element.METAL,
        Animal.HORSE: Element.METAL,
        Animal.DOG: Element.METAL,
        Animal.MOUSE: Element.WOOD,
        Animal.DRAGON: Element.WOOD,
        Animal.MONKEY: Element.WOOD,
        Animal.BIRD: Element.WATER,
        Animal.OX: Element.WATER,
        Animal.SNAKE: Element.WATER,
        Animal.BOAR: Element.FIRE,
        Animal.SHEEP: Element.FIRE,
        Animal.HARE: Element.FIRE,
    }
)

