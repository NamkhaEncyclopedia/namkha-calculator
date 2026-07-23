"""Which country a place belonged to in a given year.

Modern timezone borders must not be projected into the past: for pre-1970
births the birthplace is matched against bundled historical world maps
(aourednik/historical-basemaps, GPL-3.0, fetched by tools/fetch_basemaps.py).
The maps cover 1880-1960, the standard-time era before tzdb's zone-wide
guarantee epoch; outside it the country makes no difference to the result.

Map borders are drawn coarsely: a point close to a border may resolve to
the wrong country. WIP.
"""

import importlib.resources
import json
from bisect import bisect_left
from functools import lru_cache

SNAPSHOT_YEARS = (1880, 1900, 1914, 1920, 1930, 1938, 1945, 1960)


def nearest_snapshot_year(year: int) -> int:
    """Year of the bundled map closest to the given year.

    When two maps years are equally close, the earlier one wins.
    """
    return min(SNAPSHOT_YEARS, key=lambda snapshot: abs(snapshot - year))


def snapshots_around(year: int) -> tuple[int, int]:
    """Years of the closest bundled maps on either side of the given year.

    A year that has its own map gets that map for both sides; a year before
    the first map or after the last one gets that end's map for both sides.
    """
    if year <= SNAPSHOT_YEARS[0]:
        return SNAPSHOT_YEARS[0], SNAPSHOT_YEARS[0]
    if year >= SNAPSHOT_YEARS[-1]:
        return SNAPSHOT_YEARS[-1], SNAPSHOT_YEARS[-1]
    position = bisect_left(SNAPSHOT_YEARS, year)
    if SNAPSHOT_YEARS[position] == year:
        return year, year
    return SNAPSHOT_YEARS[position - 1], SNAPSHOT_YEARS[position]


@lru_cache(maxsize=None)
def _snapshot_features(year: int) -> tuple:
    """One bundled map, read and parsed."""
    if year not in SNAPSHOT_YEARS:
        raise ValueError(f"no bundled border snapshot for year {year}")
    filename = f"world_{year}.geojson"
    try:
        text = (
            importlib.resources.files(__package__)
            .joinpath("basemaps", filename)
            .read_text("utf-8")
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            f"bundled basemaps/{filename} is missing from this"
            " namkha-calculator installation; reinstall the package"
        ) from error
    except UnicodeDecodeError as error:
        raise ValueError(f"corrupted basemap: {filename} is not valid UTF-8") from error
    return _parse_snapshot(text, filename)


def _parse_snapshot(text: str, filename: str) -> tuple:
    """(country name, polygons) pairs from one map's GeoJSON text.

    Each polygon is stored as (bounding box, outer ring, holes) so that
    point lookups can skip polygons whose box the point is outside of.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"corrupted basemap: {filename} is not valid JSON") from error
    feature_list = data.get("features") if isinstance(data, dict) else None
    if not isinstance(feature_list, list):
        raise ValueError(f"corrupted basemap: {filename} has no feature list")
    features = []
    for feature in feature_list:
        geometry = feature["geometry"]
        if geometry is None:
            continue
        if geometry["type"] == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geometry["type"] == "MultiPolygon":
            polygons = geometry["coordinates"]
        else:
            continue
        parts = []
        for rings in polygons:
            outer = tuple((point[0], point[1]) for point in rings[0])
            longitudes = [point[0] for point in outer]
            latitudes = [point[1] for point in outer]
            bbox = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))
            holes = tuple(
                tuple((point[0], point[1]) for point in ring) for ring in rings[1:]
            )
            parts.append((bbox, outer, holes))
        features.append((feature["properties"].get("NAME"), tuple(parts)))
    if not features:
        raise ValueError(f"corrupted basemap: {filename} contains no countries")
    return tuple(features)


def _point_in_ring(longitude: float, latitude: float, ring: tuple) -> bool:
    """Whether the point lies inside the ring (even-odd ray casting)."""
    inside = False
    last_lon, last_lat = ring[-1]
    for lon, lat in ring:
        if (lat > latitude) != (last_lat > latitude) and longitude < (
            last_lon - lon
        ) * (latitude - lat) / (last_lat - lat) + lon:
            inside = not inside
        last_lon, last_lat = lon, lat
    return inside


@lru_cache(maxsize=4096)
def polity_index(latitude: float, longitude: float, snapshot_year: int) -> int | None:
    """Index of the country containing the point in the given year's map.

    None when no country contains the point (open sea, unmapped area).
    Indices are only meaningful within one map.
    """
    for index, (_, parts) in enumerate(_snapshot_features(snapshot_year)):
        for (west, south, east, north), outer, holes in parts:
            if not (west <= longitude <= east and south <= latitude <= north):
                continue
            if _point_in_ring(longitude, latitude, outer) and not any(
                _point_in_ring(longitude, latitude, hole) for hole in holes
            ):
                return index
    return None


def polity_name(latitude: float, longitude: float, snapshot_year: int) -> str | None:
    """Name of the country containing the point in the given year's map,
    or None when no country contains it."""
    index = polity_index(latitude, longitude, snapshot_year)
    if index is None:
        return None
    return _snapshot_features(snapshot_year)[index][0]
