"""
Integration tests for Year Namkha calculation.
Reference data from manual verification against known birth cases.
"""

import unittest
from datetime import datetime

import pytz

from namkha_calculator.core.astrology import Element, Gender, Subject
from namkha_calculator.core.astronomy import Location
from namkha_calculator.core.harmonizer import Aspect
from namkha_calculator.core.methods import CalculationMethod
from namkha_calculator.core.namkha_calculator import NamkhaType, calculate_namkha

E = Element


def _subject(dt_str: str, tz_name: str, lat: float, lon: float) -> Subject:
    tz = pytz.timezone(tz_name)
    dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
    # Gender is unused by Year Namkha but required by Subject
    return Subject(
        gender=Gender.MALE,
        local_birth_datetime=tz.localize(dt),
        birth_location=Location(lat, lon),
        name=None,
    )


def _aspect_map(result):
    return {
        ha.name: (ha.center, ha.harmonization_seq) for ha in result.harmonized_aspects
    }


class TestYearClassicWoodTiger(unittest.TestCase):
    """Classic method, Wood Tiger year. All birth cases should yield identical aspects."""

    _BIRTHS = [
        ("25.12.1973 15:36", "America/Chicago", 29.7604, -95.3698, "Houston TX"),
        ("25.12.1973 05:35", "America/Anchorage", 71.2906, -156.7887, "Utqiagvik AK"),
        ("14.12.1974 01:17", "Australia/Brisbane", -27.4698, 153.0251, "Brisbane QLD"),
        ("14.12.1974 03:08", "Europe/Oslo", 70.3745, 31.1105, "Vardø Norway"),
        ("21.06.1974 11:12", "Europe/Berlin", 48.7758, 9.1829, "Stuttgart Germany"),
    ]

    # center element, harmonization sequence
    _EXPECTED_ASPECTS = {
        Aspect.LIFE: (E.WOOD, (E.FIRE, E.EARTH, E.METAL, E.WATER)),
        Aspect.BODY: (E.WATER, (E.WOOD, E.FIRE, E.EARTH, E.METAL, E.WATER)),
        Aspect.CAPACITY: (E.WOOD, (E.FIRE, E.EARTH, E.METAL, E.WATER)),
        Aspect.FORTUNE: (E.METAL, (E.EARTH, E.FIRE, E.WOOD, E.WATER, E.METAL, E.WATER)),
        Aspect.MEWA_LIFE: (E.EARTH, (E.FIRE, E.WOOD, E.WATER, E.METAL, E.WATER)),
        Aspect.MEWA_BODY: (
            E.METAL,
            (E.WATER, E.WOOD, E.FIRE, E.EARTH, E.METAL, E.WATER),
        ),
        Aspect.MEWA_CAPACITY: (E.WATER, (E.METAL, E.EARTH, E.FIRE, E.WOOD, E.WATER)),
        Aspect.MEWA_FORTUNE: (
            E.METAL,
            (E.WATER, E.WOOD, E.FIRE, E.EARTH, E.METAL, E.WATER),
        ),
    }

    _EXPECTED_MEWAS = {
        Aspect.MEWA_LIFE: 5,
        Aspect.MEWA_BODY: 8,
        Aspect.MEWA_CAPACITY: 2,
        Aspect.MEWA_FORTUNE: 8,
    }

    def test_aspects_and_mewas(self):
        for dt_str, tz, lat, lon, label in self._BIRTHS:
            with self.subTest(case=label):
                subject = _subject(dt_str, tz, lat, lon)
                result = calculate_namkha(
                    NamkhaType.YEAR, subject, CalculationMethod.CLASSIC
                )
                aspects = _aspect_map(result)

                for asp, (exp_center, exp_seq) in self._EXPECTED_ASPECTS.items():
                    self.assertEqual(
                        aspects[asp][0], exp_center, f"{label} {asp.name} center"
                    )
                    self.assertEqual(
                        aspects[asp][1], exp_seq, f"{label} {asp.name} seq"
                    )

                for asp, exp_num in self._EXPECTED_MEWAS.items():
                    self.assertEqual(
                        result.mewa_numbers[asp], exp_num, f"{label} {asp.name} number"
                    )


class TestYearCnnrFireMonkey(unittest.TestCase):
    """CNNR method, Fire Monkey year. All birth cases should yield identical aspects."""

    _BIRTHS = [
        ("12.02.1956 11:18", "Africa/Casablanca", 30.4278, -9.5981, "Agadir Morocco"),
        ("12.02.1956 09:45", "Europe/Oslo", 70.6635, 23.6821, "Hammerfest Norway"),
        ("02.03.1957 04:45", "Asia/Shanghai", 31.2304, 121.4737, "Shanghai China"),
        ("02.03.1957 03:35", "Asia/Krasnoyarsk", 69.3536, 88.1895, "Norilsk Russia"),
        (
            "21.06.1956 17:33",
            "Africa/Addis_Ababa",
            9.0300,
            38.7400,
            "Addis Ababa Ethiopia",
        ),
    ]

    # center element, harmonization sequence
    _EXPECTED_ASPECTS = {
        Aspect.LIFE: (E.METAL, (E.WATER, E.WOOD, E.FIRE, E.EARTH)),
        Aspect.BODY: (E.FIRE, (E.WOOD, E.WATER, E.METAL, E.EARTH, E.FIRE, E.EARTH)),
        Aspect.CAPACITY: (E.FIRE, (E.WOOD, E.WATER, E.METAL, E.EARTH, E.FIRE, E.EARTH)),
        Aspect.FORTUNE: (E.WOOD, (E.WATER, E.METAL, E.EARTH, E.FIRE, E.EARTH)),
        Aspect.MEWA_LIFE: (E.WATER, (E.WOOD, E.FIRE, E.EARTH, E.METAL, E.EARTH)),
        Aspect.MEWA_BODY: (E.METAL, (E.WATER, E.WOOD, E.FIRE, E.EARTH)),
        Aspect.MEWA_CAPACITY: (E.EARTH, (E.FIRE, E.WOOD, E.WATER, E.METAL, E.EARTH)),
        Aspect.MEWA_FORTUNE: (E.EARTH, (E.FIRE, E.WOOD, E.WATER, E.METAL, E.EARTH)),
    }

    _EXPECTED_MEWAS = {
        Aspect.MEWA_LIFE: 2,
        Aspect.MEWA_BODY: 8,
        Aspect.MEWA_CAPACITY: 5,
        Aspect.MEWA_FORTUNE: 5,
    }

    def test_aspects_and_mewas(self):
        for dt_str, tz, lat, lon, label in self._BIRTHS:
            with self.subTest(case=label):
                subject = _subject(dt_str, tz, lat, lon)
                result = calculate_namkha(
                    NamkhaType.YEAR, subject, CalculationMethod.CNNR
                )
                aspects = _aspect_map(result)

                for asp, (exp_center, exp_seq) in self._EXPECTED_ASPECTS.items():
                    self.assertEqual(
                        aspects[asp][0], exp_center, f"{label} {asp.name} center"
                    )
                    self.assertEqual(
                        aspects[asp][1], exp_seq, f"{label} {asp.name} seq"
                    )

                for asp, exp_num in self._EXPECTED_MEWAS.items():
                    self.assertEqual(
                        result.mewa_numbers[asp], exp_num, f"{label} {asp.name} number"
                    )
