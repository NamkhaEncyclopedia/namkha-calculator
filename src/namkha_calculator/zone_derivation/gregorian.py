"""When the Gregorian calendar took effect at a given place.

A birth date earlier than this is likely to have been recorded in the Julian
or another local calendar, which the caller warns about. The answer needs the
same location lookup as the timezone, so it belongs on this side of the
boundary rather than with the notes it feeds.
"""

import datetime as dt

from ..tz import Location, zone_country
from .lookup import location_zone_key

# First day of the Gregorian calendar at the original 1582 reform; the cutoff
# for countries absent from the adoption table and for locations without a
# country (open water, unmatched coordinates).
GREGORIAN_REFORM_DATE = dt.date(1582, 10, 15)

# Date each country finished switching to the Gregorian calendar, by ISO 3166
# country code, for those that switched after the 1582 reform. If a country
# switched region by region, we use the last region's date, and round an
# unclear date up to the next 1 January. So the caution may fire too early
# during a country's switch, but never too late. Dates are keyed by the modern
# country, so a region that stayed on the Julian calendar under a past empire
# (e.g. Russian-ruled Poland, Julian until 1918) while its modern country
# switched earlier may still slip through.
GREGORIAN_ADOPTION_DATES = {
    "AT": dt.date(1584, 1, 1),
    "CZ": dt.date(1585, 1, 1),
    "HU": dt.date(1587, 11, 1),
    "DE": dt.date(1700, 3, 1),
    "DK": dt.date(1700, 3, 1),
    "NO": dt.date(1700, 3, 1),
    "FO": dt.date(1700, 3, 1),  # Faroe Islands, under Denmark-Norway
    "GL": dt.date(1700, 3, 1),  # Greenland, under Denmark
    "SJ": dt.date(1700, 3, 1),  # Svalbard and Jan Mayen, under Norway
    "IS": dt.date(1700, 11, 28),
    "NL": dt.date(1701, 7, 12),
    "GB": dt.date(1752, 9, 14),
    "IE": dt.date(1752, 9, 14),
    "IM": dt.date(1752, 9, 14),
    "JE": dt.date(1752, 9, 14),
    "GG": dt.date(1752, 9, 14),
    "US": dt.date(1752, 9, 14),
    "CA": dt.date(1752, 9, 14),
    "SE": dt.date(1753, 3, 1),
    "FI": dt.date(1753, 3, 1),
    "AX": dt.date(1753, 3, 1),  # Aland Islands, under Sweden
    "CH": dt.date(1813, 1, 1),
    "JP": dt.date(1873, 1, 1),
    "EG": dt.date(1876, 1, 1),
    "TH": dt.date(1889, 4, 1),
    "KR": dt.date(1896, 1, 1),
    "KP": dt.date(1896, 1, 1),
    "TW": dt.date(1896, 1, 1),
    "AL": dt.date(1913, 1, 1),
    "BG": dt.date(1916, 4, 14),
    "RU": dt.date(1918, 2, 14),
    "UA": dt.date(1918, 2, 14),
    "BY": dt.date(1918, 2, 14),
    "EE": dt.date(1918, 2, 14),
    "LV": dt.date(1918, 2, 14),
    "LT": dt.date(1918, 2, 14),
    "GE": dt.date(1918, 2, 14),
    "AM": dt.date(1918, 2, 14),
    "AZ": dt.date(1918, 2, 14),
    "KZ": dt.date(1918, 2, 14),
    "KG": dt.date(1918, 2, 14),
    "TJ": dt.date(1918, 2, 14),
    "TM": dt.date(1918, 2, 14),
    "UZ": dt.date(1918, 2, 14),
    "RS": dt.date(1919, 1, 28),
    "ME": dt.date(1919, 1, 28),
    "MK": dt.date(1919, 1, 28),
    "BA": dt.date(1919, 1, 28),
    "RO": dt.date(1919, 4, 14),
    "MD": dt.date(1919, 4, 14),
    "GR": dt.date(1923, 3, 1),
    "TR": dt.date(1926, 1, 1),
    "CN": dt.date(1929, 1, 1),
}

# Zone-level overrides where one zone's calendar history differs from the
# rest of its country: Alaska stayed Julian until the 1867 US purchase.
GREGORIAN_ADOPTION_DATES_BY_ZONE = {
    "America/Adak": dt.date(1867, 10, 18),
    "America/Anchorage": dt.date(1867, 10, 18),
    "America/Juneau": dt.date(1867, 10, 18),
    "America/Metlakatla": dt.date(1867, 10, 18),
    "America/Nome": dt.date(1867, 10, 18),
    "America/Sitka": dt.date(1867, 10, 18),
    "America/Yakutat": dt.date(1867, 10, 18),
}


def gregorian_adoption_date(location: Location) -> dt.date:
    """First Gregorian date at the location; the 1582 reform date if unknown."""
    key = location_zone_key(location)
    if key is None:
        return GREGORIAN_REFORM_DATE
    if key in GREGORIAN_ADOPTION_DATES_BY_ZONE:
        return GREGORIAN_ADOPTION_DATES_BY_ZONE[key]
    country = zone_country(key)
    if country in GREGORIAN_ADOPTION_DATES:
        return GREGORIAN_ADOPTION_DATES[country]
    return GREGORIAN_REFORM_DATE
