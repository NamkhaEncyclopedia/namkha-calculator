from enum import Enum, unique


@unique
class Element(Enum, str):
    WATER = "Water"
    WOOD = "Wood"
    FIRE = "Fire"
    EARTH = "Earth"
    METAL = "Metal"


@unique
class Animal(Enum, str):
    MOUSE = "Mouse"
    OX = "Ox"
    TIGER = "Tiger"
    HARE = "Hare"
    DRAGON = "Dragon"
    SNAKE = "Snake"
    HORSE = "Horse"
    SHEEP = "Sheep"
    MONKEY = "Monkey"
    BIRD = "Bird"
    DOG = "Dog"
    BOAR = "Boar"

