from enum import Enum, auto, unique


@unique
class CalculationMethod(Enum):
    CNNR = auto()
    CLASSIC = auto()
