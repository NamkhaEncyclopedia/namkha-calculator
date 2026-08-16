<img src="https://raw.githubusercontent.com/NamkhaEncyclopedia/namkha-calculator/main/logo.webp" alt="Namkha Calculator logo" width="150" height="150" />

# Namkha Calculator

---

[![PyPI version](https://img.shields.io/pypi/v/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![Python versions](https://img.shields.io/pypi/pyversions/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![License: GPL-3.0-or-later](https://img.shields.io/pypi/l/namkha-calculator)](https://github.com/NamkhaEncyclopedia/namkha-calculator/blob/main/LICENSE)
[![Development Status](https://img.shields.io/pypi/status/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![Tests](https://github.com/NamkhaEncyclopedia/namkha-calculator/actions/workflows/tests.yml/badge.svg?event=push)](https://github.com/NamkhaEncyclopedia/namkha-calculator/actions/workflows/tests.yml)

Python library for calculating [Namkha thread-cross](https://en.wikipedia.org/wiki/Namkha) color schemes in the tradition of [Chögyal Namkhai Norbu Rinpoche](https://en.wikipedia.org/wiki/Namkhai_Norbu), with all the methods covered in the source text.[^1] Classical Tibetan astrology calculations were added for cases where the source refers to them for complete instructions.[^2]

## Table of contents

- [Development status](#development-status)
- [Usage](#usage)
  - [Key types](#key-types)
    - [User input](#user-input)
    - [Timezone handling](#timezone-handling)
    - [Input validation and errors](#input-validation-and-errors)
    - [Result](#result)
  - [Calculation notes](#calculation-notes)
    - [Latitude "trimming"](#latitude-trimming)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [References](#references)

## Development status
> [!WARNING]
> The project is in an alpha stage – all calculations should be checked manually when making a real Namkha.

### TODO

- [x] Year Namkha calculation (CNNR and Classic)
- [x] Birth-time edge-case warnings
- [ ] [WIP] Automatic historical timezone detection from coordinates
- [ ] Month Namkha calculation
- [ ] Day Namkha calculation
- [ ] Hour Namkha calculation
- [ ] More pre-calculated test cases
- [ ] Further investigation into the high-latitude regions problem

## Usage

```python
from datetime import datetime

import namkha_calculator as nc
from namkha_calculator.zone_derivation import resolve_timezone

birth_datetime = datetime(1985, 3, 15, 14, 30)  # naive local time
birth_location = nc.Location(latitude=52.52, longitude=13.40, name="Berlin")

# Work out the timezone once, before calculating.
resolved_timezone = resolve_timezone(birth_location, birth_datetime)

# Notes that follow from the birth details alone, known before any calculation.
for note in nc.input_notes(resolved_timezone, birth_location, birth_datetime):
    print(f"[{note.note_type.name}] {note.message}")

subject = nc.Subject(
    name="John Doe",
    gender=nc.Gender.MALE,
    birth_datetime=birth_datetime,
    birth_location=birth_location,
    resolved_timezone=resolved_timezone,
)

result = nc.calculate_namkha(
    namkha_type=nc.NamkhaType.YEAR,
    subject=subject,
    method=nc.CalculationMethod.CLASSIC,  # or CalculationMethod.CNNR
)

for aspect in result.harmonized_aspects:
    threads = ", ".join(e.value for e in aspect.harmonization_seq)
    conflict = " (conflicted)" if aspect.is_conflicted else ""
    print(f"{aspect.name.name}: center={aspect.center.value}, threads=[{threads}]{conflict}")

for note in result.calculation_notes:
    print(f"[{note.note_type.name}] {note.message}")
```

### Key types

#### User input
**`Subject`** – birth data for one person (or another entity with a known birth/creation time, e.g. a company).

All fields are keyword-only.

| Field               | Type               | Notes                                                                         |
|---------------------|--------------------|-------------------------------------------------------------------------------|
| `gender`            | `Gender`           | `MALE` or `FEMALE`                                                            |
| `birth_datetime`    | `datetime`         | 'naive' (no tzinfo) local time, Gregorian calendar                            |
| `birth_location`    | `Location`         | latitude/longitude in decimal degrees, optional place name                    |
| `resolved_timezone` | `ResolvedTimezone` | the timezone worked out for this place and date; see below                    |
| `name`              | `str` (optional)   | optional subject name                                                         |

`Subject` doesn't work a timezone out for itself. Call `resolve_timezone` first and pass what it returns, as the example above does.

**`ResolvedTimezone`** – the timezone a calculation runs on, frozen with the birth details it was worked out for.

| Field                     | Type                  | Notes                                                                 |
|---------------------------|-----------------------|-----------------------------------------------------------------------|
| `key`                     | `str or None`         | IANA zone key, or `None` for a bare offset                            |
| `offset_seconds`          | `int or None`         | the offset, or `None` for a named zone                                |
| `provenance`              | `TimezoneProvenance`  | `LOCATION_DERIVED`, `USER_ZONE` or `USER_OFFSET`                      |
| `derivation`              | `TimezoneDerivation`  | `CERTAIN`, `ESTIMATED` or `BORDERS_UNCERTAIN`                         |
| `is_longitude_based`      | `bool`                | the offset comes from the longitude, not from civil timezone rules    |
| `on_summer_time`          | `bool or None`        | which reading of an ambiguous fall-back hour applies                  |
| `gregorian_adoption_date` | `date`                | when the birth region adopted the Gregorian calendar                  |

Three more fields, `for_latitude`, `for_longitude` and `for_birth_date`, record the birth details this timezone belongs to; `assert_binds(location, birth_datetime)` compares them and raises `StaleTimezoneError` when they differ. `Subject` calls it, so a timezone worked out for another place or date can never reach a calculation. `modern_zone_key` holds the zone covering the coordinates today, which for a pre-1970 birth can differ from `key`.

`tzinfo` rebuilds the timezone itself from `key` or `offset_seconds`. The value is a plain dataclass otherwise, so it is hashable and picklable.

#### Timezone handling

The timezone is worked out once, by `resolve_timezone`, before any calculation. It lives in `namkha_calculator.zone_derivation` and is deliberately not re-exported at the package root: the coordinate lookups and the historical maps below are expensive, and keeping the import explicit is what keeps them off the calculation path.

```python
from namkha_calculator.zone_derivation import resolve_timezone

resolve_timezone(location, birth_datetime, *, zone_key=None, offset=None, on_summer_time=None)
```

Timezone data is bundled with the package: an IANA tzdb zoneinfo tree compiled with the *backzone* file, so results are identical on every operating system, and zones that tzdb merged away for post-1970 equivalence keep their own real pre-1970 histories (an Amsterdam birth in summer 1935 gets the true Dutch +1:19:32, not the +1:00 of the Brussels zone; wartime Stockholm keeps Sweden's DST-free clocks, not Berlin's ect.). The birth timezone is resolved as follows:

- **`zone_key` or `offset` given** – that timezone is used, and the result is `CERTAIN`. Pass at most one of the two. `zone_key` is an IANA key from the bundled data, and `nc.zone_keys()` lists every one of them; `offset` is a `timedelta`, for a birth time known only as a bare UTC offset. Either is checked against the birthplace first, because a wrongly given timezone can belong nowhere near it.
- **Neither given, birth from 1970 on** – the IANA zone covering the coordinates. This is a certain derivation: tzdb guarantees zone histories from 1970, so even zones that changed later for political reasons resolve to the correct historical rules.
- **Neither given, birth before 1970** – tzdb only guarantees each zone's history that far back for its *reference city*, and modern zone borders must not be projected into the past. The birthplace is looked up in bundled historical world maps (1880–1960, from [historical-basemaps](https://github.com/aourednik/historical-basemaps)): if the covering zone's reference city belonged to the same country as the birthplace in the birth year, that zone applies; otherwise the zone of the nearest reference city *within the birth-year country* applies. The `TIMEZONE_ESTIMATED` caution is attached, or `TIMEZONE_BORDERS_UNCERTAIN` when the maps around the birth year disagree (see [Calculation notes](#calculation-notes)). *This case is still work in progress.*
- **Neither given, open water or outside every timezone** – on open water, the nautical `Etc/GMT±N` zone for the longitude; where the coordinates match no timezone at all, the longitude's mean solar time. Both get the `TIMEZONE_ESTIMATED` caution and the `LOCAL_MEAN_TIME` notice.

Whichever zone applies – derived or given – a birth before standard time in that zone (the tzdb "LMT" era, roughly pre-1880s–1912 depending on country) uses the *mean solar time of the birth longitude itself*, which is more accurate than any zone's reference-city approximation. The `LOCAL_MEAN_TIME` notice is attached. In that case `key` still names the zone, so `nc.timezone_label(resolved_timezone, birth_datetime)` gives the name to show a reader: the zone key, `"mean solar time"` when the offset came from the longitude, or `None` when only a bare offset was given.

`on_summer_time` says which reading of an ambiguous fall-back hour applies. It is kept only when the birth time really falls in a repeated hour; anywhere else it decided nothing and is dropped.

Birth dates are proleptic Gregorian; a Julian-calendar source date must be converted first (see the `PRE_GREGORIAN_DATE` caution under [Calculation notes](#calculation-notes)).

#### Input validation and errors

Every timezone failure is a `TimezoneError`, which subclasses `ValueError`, so callers can tell the failures apart without matching on message text.

`resolve_timezone` checks a `zone_key` or an `offset` against the birth place coordinates before returning, and raises instead of resolving to something the place contradicts:

- A fixed offset must lie within the range real timezones have used, *UTC−16* to *UTC+16*, or `TimezoneOffsetOutOfRangeError` – an offset outside it is a data-entry error. The range is that wide because zones that counted dates across the Date Line carry solar offsets shifted by a whole day (pre-1845 Manila ran -15:56). Named zones are not checked: their offsets come from real tzdb data.
- The timezone must be consistent with the location's longitude, or `TimezoneLocationMismatchError`: the (standard-time) clock may run at most *2.5 h behind* or *3.5 h ahead* of the longitude's mean solar time. Every historical timezone fits these bounds; the behind bound is tighter because a clock behind the sun pulls dawn towards clock midnight. This check is skipped at latitudes of 60° and above, where we consider the day start is a fixed local hour and solar time is irrelevant (see [Latitude "trimming"](#latitude-trimming)).

A derived timezone matches its location by construction, so neither check runs for one.

`Subject` validates its input at construction and raises instead of computing from inconsistent data:

- `birth_datetime` must be naive – `TypeError` otherwise (the timezone belongs in `resolved_timezone`).
- `resolved_timezone` must be a `ResolvedTimezone`; a bare `tzinfo` is rejected with `TypeError`.
- The resolved timezone must have been worked out for this birth place and date - `StaleTimezoneError` otherwise. Only the date is compared, not the time of day: the time of day cannot change which timezone applied.

`calculate_namkha` raises `ValueError` – never degrades silently – when:

- the birth instant never existed in its timezone (a time skipped by a spring-forward clock change, or a whole date removed by a dateline change, e.g. 2011-12-30 in Samoa);
- the birth year falls outside the supported range, 1551–2598 (limited by the bundled ephemeris);
- an extreme behind-the-sun fixed offset at 56–60° latitude lands on the rare date (~1 per year) whose dawn drifts across clock midnight onto a neighboring date – no real timezone can trigger this.

**`Location`** – `latitude`, `longitude`, optional `name`.

**`NamkhaType`** – `YEAR`, `MONTH`, `DAY`, `HOUR`.

**`CalculationMethod`** – `CNNR` (Chögyal Namkhai Norbu Rinpoche's tradition) or `CLASSIC` ("classical" Tibetan astrology tradition). Only `YEAR` accepts `CNNR`; all other types use `CLASSIC`.

#### Result
**`NamkhaCalculationResult`**

| Field                | Type                              | Description                      |
|----------------------|-----------------------------------|----------------------------------|
| `harmonized_aspects` | `tuple[HarmonizedAspect, ...]`    | eight aspects in order           |
| `mewa_numbers`       | `dict[Aspect, int]`               | mewa number for each mewa aspect |
| `calculation_notes`  | `tuple[CalculationNoteItem, ...]` | notices or cautions              |

**`HarmonizedAspect`**

| Field               | Type                  | Description                                                   |
|---------------------|-----------------------|---------------------------------------------------------------|
| `name`              | `Aspect`              | `LIFE`, `BODY`, `CAPACITY`, `FORTUNE`, `MEWA_*`               |
| `center`            | `Element`             | center element                                                |
| `harmonization_seq` | `tuple[Element, ...]` | harmonization sequence: remaining thread colors outward       |
| `is_conflicted`     | `bool or None`        | `None` for `LIFE`; `True` when conflict harmonization applied |

### Calculation notes

`result.calculation_notes` carries every note. All but `PERIOD_BOUNDARY` follow from the birth details alone, and `input_notes(resolved_timezone, location, birth_datetime)` returns those without running a calculation. `PERIOD_BOUNDARY` needs the calculation itself, so only the result has it.

`PERIOD_BOUNDARY` (caution) is attached when the birth time falls within 5 minutes of a calculation-period boundary (for `YEAR`, the Tibetan year start/end). That close to a boundary the result can flip to the neighboring period, so the birth time must be precise.

`HIGH_LATITUDE` (notice) is attached when `abs(latitude) >= 60.0`. Above this limit the library falls back to a fixed 5:00 AM day-start instead of civil twilight, which affects birth period boundary detection.

`AMBIGUOUS_LOCAL_TIME` (caution) is attached when the naive birth time falls in a fall-back clock change and so occurs twice; the standard-time reading is used unless `resolve_timezone`'s `on_summer_time` argument says which reading is correct (then `AMBIGUOUS_LOCAL_TIME_RESOLVED`, a notice, is attached instead). A birth instant that never existed in the timezone – a time skipped by a spring-forward clock change, or a whole date removed by a dateline jump – is rejected with a `ValueError` rather than noted.

`TIMEZONE_ESTIMATED` (caution) is attached when no timezone was given and it could not be derived from the location and date with certainty (pre-1970 birth, or birth on open water); the best historically recorded regional time was used.

`TIMEZONE_BORDERS_UNCERTAIN` (caution) replaces `TIMEZONE_ESTIMATED` – the two are mutually exclusive – when the historical map snapshots on either side of a pre-1970 birth year disagree about which country held the birthplace, so even the country whose time applied is uncertain. Short-lived changes between two maps (e.g. the 1939–1941 Soviet occupation of eastern Poland, which decreed Moscow time) are invisible to the maps and cannot be resolved automatically by any open dataset we know of. Right now the remedy is research: establish the birthplace's legal time from historical sources (the [World Historical Gazetteer](https://whgazetteer.org/) is a good starting point for a place's administrative history) and pass it to `resolve_timezone` as `zone_key`.

`LOCAL_MEAN_TIME` (notice) is attached when the birth clock time was read from the longitude rather than from civil timezone rules: a birth before standard time in its region, on open water, or outside every timezone.

`PRE_GREGORIAN_DATE` (caution) is attached to births before the Gregorian calendar was adopted at the birth place (15 October 1582 at the earliest, as late as the 1920s in some regions), as a reminder that a Julian-calendar source date must be converted to Gregorian.

#### Latitude "trimming"

In the Tibetan calendar a new day begins at dawn, not at midnight. The library defines dawn as the start of *civil twilight* – the moment the sky first starts to brighten before sunrise (in traditional texts, when one can see the lines on the palm of their hand). This boundary decides which Tibetan hour (and therefore Tibetan day, month, etc.) a given birth time belongs to.

Closer to the poles (i.e. at higher latitudes) this breaks down. For long parts of the year there is no dawn: the midnight sun in summer, when the sky never fully darkens, and the polar night in winter, when it never properly brightens. On those dates civil twilight does not start (or does not end), so there is no dawn to anchor the day to and the astronomical lookup returns nothing.

As far as we know, Tibetan astrologers have not agreed on a solution to this problem. For now the library does the following: it "trims" the usable latitude range at *60° north/south*. Below that limit it uses the real civil-twilight dawn. At or above it, it falls back to a fixed *5:00 AM local time* (a convention also found in Tibetan tradition) as the day-start and attaches the `HIGH_LATITUDE` notice. This issue is a subject of further research.

## Contributing

Issues, PRs and questions are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

[GPL-3.0-or-later](LICENSE). The package bundles:

- historical world border maps from [aourednik/historical-basemaps](https://github.com/aourednik/historical-basemaps) (GPL-3.0) – bundling them is why this project is GPL rather than MIT;
- an IANA [tzdb](https://www.iana.org/time-zones) zoneinfo tree compiled with backzone data (public domain);
- a filtered JPL DE440 ephemeris (public domain).

Timezone boundary lookups use [timezonefinder](https://github.com/jannikmi/timezonefinder) (MIT), whose boundary data derives from [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) (ODbL).

## Acknowledgments

<img src="https://raw.githubusercontent.com/NamkhaEncyclopedia/namkha-calculator/main/WhiteAThigle.webp" alt="White A Thigle" width="150" height="150" />

***Whatever wisdom this contains belongs to the Tibetan astrological traditions and their holders; whatever faults it contains are our own.***


We thank everyone who supported the Namkha Calculator project financially – your help means a great deal to us, and it sustained us through a lot of obstacles.

We would also like to express our gratitude to:
Migmar Tsering, Maria Rita Leti, Adriano Clemente, Alexander Khosmo and Tatiana Ulyanova for their guidance on Tibetan astrology; and to the Gakyil of Merigar East – Oana Marcu and Krisztina Balla for their invaluable help in providing indispensable educational materials.

## References

[^1]: C.N. Norbu. Namkha: Harmonizing the Energy of the Elements. Shang Shung Publications, 2022.

[^2]: C.N. Norbu. Key for Consulting the Tibetan Calendar. Shang Shung Publications, 2014; M. Tsering. Jung-We Kyil-Khor – Mandala of Astrological Elements. Dynamic Space of the Elements ETS, 2020.
