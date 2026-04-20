"""
This tests a temporary solution to handle high latitudes.
See the docstring of `asteronomy.trim_latitude` for details.
"""

import unittest
import datetime as dt

import pytz

from namkha_calculator.core import astronomy
from namkha_calculator.core.skyfield_calculations import civil_twilight_boundaries

TEST_PLACES = {
    "Svalbard": astronomy.Location(78.22, 15.65),
    "Tolhuin": astronomy.Location(-54.50, -67.20),
}

TEST_TIMEZONES = {
    "Svalbard": pytz.timezone("Arctic/Longyearbyen"),
    "Tolhuin": pytz.timezone("America/Argentina/Ushuaia"),
}

SUMMER_SOLSTICE_2024 = pytz.timezone("UTC").localize(dt.datetime(2024, 6, 20, 20, 51))
WINTER_SOLSTICE_2024 = pytz.timezone("UTC").localize(dt.datetime(2024, 12, 21, 9, 20))


class TestLatitudeTrimming(unittest.TestCase):
    def test_same_twilight_boundaries_for_initial_and_trimmed_location_north(self):
        trimmed_location_summer_solstice = astronomy.trim_latitude(
            TEST_PLACES["Svalbard"], TEST_TIMEZONES["Svalbard"], SUMMER_SOLSTICE_2024
        )
        trimmed_location_winter_solstice = astronomy.trim_latitude(
            TEST_PLACES["Svalbard"], TEST_TIMEZONES["Svalbard"], WINTER_SOLSTICE_2024
        )

        self.assertEqual(
            civil_twilight_boundaries(
                SUMMER_SOLSTICE_2024,
                TEST_TIMEZONES["Svalbard"],
                TEST_PLACES["Svalbard"],
            ),
            civil_twilight_boundaries(
                SUMMER_SOLSTICE_2024,
                TEST_TIMEZONES["Svalbard"],
                trimmed_location_summer_solstice,
            ),
        )

        self.assertEqual(
            civil_twilight_boundaries(
                WINTER_SOLSTICE_2024,
                TEST_TIMEZONES["Svalbard"],
                TEST_PLACES["Svalbard"],
            ),
            civil_twilight_boundaries(
                WINTER_SOLSTICE_2024,
                TEST_TIMEZONES["Svalbard"],
                trimmed_location_winter_solstice,
            ),
        )
