"""Fetch the bundled historical border maps from aourednik/historical-basemaps.

Downloads every world border snapshot the dataset provides for the
standard-time era 1880-1960 at a pinned commit; outside that window
snapshots cannot affect results (earlier births resolve through longitude
mean time, births from 1970 on through the certain modern polygon). The
GeoJSON files are committed to src/namkha_calculator/basemaps/ and drive
pre-1970 polity attribution in historical_borders.py.

The data is GPL-3.0; bundling it is why this project is GPL-3.0-or-later.
Rerun after bumping SOURCE_COMMIT.
"""

import urllib.request
from pathlib import Path

SOURCE_REPO = "https://github.com/aourednik/historical-basemaps"
SOURCE_COMMIT = "62d8f1a03a71f2d3ff17f2d166f7553f256bce68"

SNAPSHOT_YEARS = (1880, 1900, 1914, 1920, 1930, 1938, 1945, 1960)

_RAW_URL = (
    "https://raw.githubusercontent.com/aourednik/historical-basemaps"
    f"/{SOURCE_COMMIT}/geojson/world_{{year}}.geojson"
)

_PACKAGE_BASEMAPS = (
    Path(__file__).resolve().parent.parent / "src" / "namkha_calculator" / "basemaps"
)


def main() -> None:
    _PACKAGE_BASEMAPS.mkdir(exist_ok=True)
    for year in SNAPSHOT_YEARS:
        url = _RAW_URL.format(year=year)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, _PACKAGE_BASEMAPS / f"world_{year}.geojson")
    (_PACKAGE_BASEMAPS / "SOURCE").write_text(
        f"{SOURCE_REPO} @ {SOURCE_COMMIT}\nLicence: GPL-3.0\n"
    )
    print(f"{len(SNAPSHOT_YEARS)} snapshots installed into {_PACKAGE_BASEMAPS}")


if __name__ == "__main__":
    main()
