from enum import unique, Enum, auto


@unique
class CalculationMethod(Enum):
    CNNR = auto()
    CLASSIC = auto()
    # DOUBLE = auto()
