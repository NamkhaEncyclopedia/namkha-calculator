from ..calendar import TibetanMonthAttributes, TibetanYearAttributes
from .shared_mewa import MewaResult, mewa_result_classic
from .year import fortune_mewa_classic


def calculate_mewas_classic(
    month_attrs: TibetanMonthAttributes, year_attrs: TibetanYearAttributes
) -> MewaResult:
    """Mewa aspects of a month.

    The month defines life, body and capacity. Fortune comes from the birth year.
    """
    return mewa_result_classic(
        month_attrs.mewa_number, fortune_mewa_classic(year_attrs)
    )
