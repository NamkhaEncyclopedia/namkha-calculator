"""Build the bundled timezone data from a pinned IANA tzdb release.

Compiles the release with zic, restoring backzone pre-1970 histories for
every zone listed in zone.tab (PACKRATDATA/PACKRATLIST) – the default tzdb
build replaces those histories with a post-1970-equivalent neighbour's.
The output tree is committed to src/namkha_calculator/tzdata/ and is the
only timezone data the package uses at runtime.

Requires make, cc, and zic. Rerun after bumping TZDB_VERSION.
"""

import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

TZDB_VERSION = "2026b"

_RELEASES = "https://data.iana.org/time-zones/releases"
_ARCHIVE_URLS = (
    f"{_RELEASES}/tzdata{TZDB_VERSION}.tar.gz",
    f"{_RELEASES}/tzcode{TZDB_VERSION}.tar.gz",
)

_PACKAGE_TZDATA = (
    Path(__file__).resolve().parent.parent / "src" / "namkha_calculator" / "tzdata"
)

# Build artefacts and zonenow.tab not needed at runtime; zone.tab is kept.
_EXCLUDED = ("leapseconds", "tzdata.zi", "zonenow.tab")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        source = tmp / "source"
        for url in _ARCHIVE_URLS:
            archive = tmp / url.rsplit("/", 1)[1]
            print(f"downloading {url}")
            urllib.request.urlretrieve(url, archive)
            with tarfile.open(archive) as tar:
                tar.extractall(source, filter="data")
        print("compiling with zic (backzone data for zone.tab zones)")
        subprocess.run(
            [
                "make",
                "VERSION_DEPS=",
                f"TOPDIR={tmp / 'dest'}",
                "PACKRATDATA=backzone",
                "PACKRATLIST=zone.tab",
                "ZFLAGS=-b slim",
                "install",
            ],
            cwd=source,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        built = tmp / "dest" / "usr" / "share" / "zoneinfo"
        if _PACKAGE_TZDATA.exists():
            shutil.rmtree(_PACKAGE_TZDATA)
        shutil.copytree(
            built, _PACKAGE_TZDATA, ignore=shutil.ignore_patterns(*_EXCLUDED)
        )
        (_PACKAGE_TZDATA / "TZDB_VERSION").write_text(f"{TZDB_VERSION}\n")
    print(f"tzdb {TZDB_VERSION} installed into {_PACKAGE_TZDATA}")


if __name__ == "__main__":
    main()
