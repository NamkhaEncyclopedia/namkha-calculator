<img src="https://raw.githubusercontent.com/NamkhaEncyclopedia/namkha-calculator/main/logo.webp" alt="Namkha Calculator logo" width="150" height="150" />

# Namkha Calculator

---

[![PyPI version](https://img.shields.io/pypi/v/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![Python versions](https://img.shields.io/pypi/pyversions/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![License: GPL-3.0-or-later](https://img.shields.io/pypi/l/namkha-calculator)](https://github.com/NamkhaEncyclopedia/namkha-calculator/blob/main/LICENSE)
[![Development Status](https://img.shields.io/pypi/status/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![Tests](https://github.com/NamkhaEncyclopedia/namkha-calculator/actions/workflows/tests.yml/badge.svg?event=push)](https://github.com/NamkhaEncyclopedia/namkha-calculator/actions/workflows/tests.yml)

Python library for calculating [Namkha thread-cross](https://en.wikipedia.org/wiki/Namkha) color schemes in the tradition of [Chögyal Namkhai Norbu Rinpoche](https://en.wikipedia.org/wiki/Namkhai_Norbu), with all the methods covered in the source text.[^1] Classical Tibetan astrology calculations were added for cases where the source refers to them for complete instructions.[^2]

This library is the engine behind the [Namkha Webapp](https://github.com/NamkhaEncyclopedia/namkha-webapp/), which provides a user-friendly interface and renders the results as a PDF.

## Table of contents

- [Development status](#development-status)
- [Usage](#usage)
  - [API reference](#api-reference)
    - [Functions](#functions)
    - [Input](#input)
    - [Timezone resolution](#timezone-resolution)
    - [Errors](#errors)
    - [Result](#result)
  - [Namkha types](#namkha-types)
    - [Month Namkha](#month-namkha)
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
- [x] Month Namkha calculation
- [ ] Day Namkha calculation
- [ ] Hour Namkha calculation
- [ ] More pre-calculated test cases
- [ ] Further investigation into the high-latitude regions problem

## Acknowledgments

<img src="https://raw.githubusercontent.com/NamkhaEncyclopedia/namkha-calculator/main/WhiteAThigle.webp" alt="White A in a Thigle" width="150" height="150" />

***Whatever wisdom this contains belongs to the Tibetan astrological traditions and their holders; whatever faults it contains are our own.***

We thank everyone who supported the Namkha Calculator project financially, on GoFundMe and through direct donations. Your help means a great deal to us, and it carried us through many obstacles!

We would also like to express our gratitude to:

- Migmar Tsering
- Maria Rita Leti
- Adriano Clemente
- Svante Janson
- Edward Henning
- Giovanni Totino, the director of Shang Shung Publications Italy
- Alexander Khosmo and Tatiana Ulyanova, for their guidance on Tibetan astrology
- the Gakyil of Merigar East – Oana Marcu and Krisztina Balla, for providing indispensable educational materials
- Karma Teleg Dondrup (tibastro.be)
- Sven Vandermeeren, Olli Hartikainen and everyone who supported us in the most challenging moments.

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
    namkha_type=nc.NamkhaType.YEAR,  # or NamkhaType.MONTH
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

### API reference

Everything here is available as `nc.<name>` after `import namkha_calculator as nc`. The one exception is `resolve_timezone`, which comes from `namkha_calculator.zone_derivation`.

#### Functions

| Call                                                                                | Returns                           | Purpose                                                                                                 |
|-------------------------------------------------------------------------------------|-----------------------------------|---------------------------------------------------------------------------------------------------------|
| `resolve_timezone(location, birth_datetime, *, zone_key=None, offset=None, on_summer_time=None)` | `ResolvedTimezone`                | Works out which timezone applied at the birth. Call it before you build a `Subject`.                    |
| `calculate_namkha(namkha_type, subject, method=CalculationMethod.CLASSIC)`           | `NamkhaCalculationResult`         | Calculates the Namkha.                                                                                    |
| `input_notes(resolved_timezone, location, birth_datetime)`                           | `tuple[CalculationNoteItem, ...]` | Notes that follow from the birth details alone, without running a calculation.                            |
| `timezone_label(resolved_timezone, birth_datetime)`                                  | `str or None`                     | The timezone name to show a reader. See [Timezone resolution](#timezone-resolution).                      |
| `zone_keys()`                                                                        | `tuple[str, ...]`                 | Every IANA zone key you may pass as `zone_key`.                                                           |
| `zone(key)`                                                                          | `ZoneInfo`                        | A timezone from the bundled data.                                                                         |
| `fixed_offset(offset)`                                                               | `datetime.timezone`               | A timezone with a constant UTC offset, built from a `timedelta`.                                          |

#### Input

**`Location`** – `latitude` and `longitude` in decimal degrees, plus an optional `name`.

**`Gender`** – `MALE` or `FEMALE`.

**`NamkhaType`** – `YEAR`, `MONTH`, `DAY` or `HOUR`. See [Namkha types](#namkha-types) for which of them the library calculates.

**`CalculationMethod`** – `CNNR` (Chögyal Namkhai Norbu Rinpoche's terma) or `CLASSIC` (classical Tibetan astrology). Only `YEAR` accepts `CNNR`.

**`Subject`** – birth data for one person, or for another entity with a known creation time, e.g. a company.

All fields are keyword-only.

| Field               | Type               | Notes                                                                         |
|---------------------|--------------------|-------------------------------------------------------------------------------|
| `gender`            | `Gender`           | `MALE` or `FEMALE`                                                            |
| `birth_datetime`    | `datetime`         | 'naive' (no tzinfo) local time, Gregorian calendar                            |
| `birth_location`    | `Location`         | latitude/longitude in decimal degrees, optional place name                    |
| `resolved_timezone` | `ResolvedTimezone` | the timezone worked out for this place and date; see below                    |
| `name`              | `str` (optional)   | subject name                                                                  |

`Subject` does not work a timezone out for itself. Call `resolve_timezone` first and pass what it returns, as the example above does.

`Subject` also has four read-only properties, all based on the resolved timezone:

| Property                      | Type                 | Notes                                                        |
|-------------------------------|----------------------|--------------------------------------------------------------|
| `effective_timezone`          | `tzinfo`             | the timezone the calculation runs on                         |
| `local_birth_datetime`        | `datetime`           | `birth_datetime` with that timezone attached                 |
| `timezone_derivation`         | `TimezoneDerivation` | how sure that timezone is                                    |
| `timezone_is_longitude_based` | `bool`               | the offset comes from the longitude, not from timezone rules |

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

Three more fields record the birth details this timezone belongs to: `for_latitude`, `for_longitude` and `for_birth_date`. `assert_binds(location, birth_datetime)` compares them and raises `StaleTimezoneError` when they differ. `Subject` and `input_notes` both call it, so a timezone worked out for another place or date can never reach a calculation.

`modern_zone_key` holds the zone covering the coordinates today. For a birth before 1970 that can differ from `key`. `tzinfo` rebuilds the timezone itself from `key` or `offset_seconds`. Every other field is a plain value, so the whole object stays hashable and picklable.

#### Timezone resolution

Call `resolve_timezone` once, before any calculation, and pass its result to `Subject` and to `input_notes`. It is the only place the timezone is worked out, and the only place that reads the coordinates.

It sits in its own module, apart from `nc`, because it does expensive map data calls, which the rest of the calculation never needs:

```python
from namkha_calculator.zone_derivation import resolve_timezone
```

Timezone data is bundled with the package, so results are the same on every operating system, and every zone keeps its own real history from before 1970.

How the birth timezone is worked out:

- **You provide `zone_key` or `offset`** – that timezone applies, and `derivation` is `CERTAIN`. Pass only one of the two. `zone_key` is an IANA key from the bundled data, and `nc.zone_keys()` lists every one of them; `offset` is a `timedelta`, for a birth time known only as a UTC offset. The library checks either one against the birthplace first, because a wrong timezone can belong nowhere near it.
- **You provide neither, birth from 1970 on** – the zone covering the coordinates, again `CERTAIN`. Zone histories are guaranteed that far back, so a zone that later split for political or other reasons still gives the right rules.
- **You provide neither, birth between 1880 and 1970** – standard time was still being introduced then, and the borders of modern time zones must not be projected back into that period. The library looks the birthplace up in bundled historical world maps (1880–1960, from [historical-basemaps](https://github.com/aourednik/historical-basemaps)) and takes the zone that belonged to the same country in the birth year. The answer is an estimate and carries the `TIMEZONE_ESTIMATED` caution, or `TIMEZONE_BORDERS_UNCERTAIN` when the maps around the birth year disagree (see [Calculation notes](#calculation-notes)). If standard time had not reached that region yet, no caution follows: the clock then comes from the longitude, not from the zone. *This case is still work in progress.*
- **You provide neither, birth before 1880** – the oldest map is drawn for 1880 and says nothing about earlier borders, so no country is looked up. The zone covering the coordinates today is kept. What the clock showed at the birth comes from that zone's own history, and for these dates that is the mean solar time of the birth longitude, with the `LOCAL_MEAN_TIME` notice. No caution follows, because the zone did not decide the clock.
- **You provide neither, open water or a point in no timezone** – the nautical `Etc/GMT±N` zone for the longitude, or, where no timezone matches at all, the longitude's mean solar time. Both are estimates.

Each country introduced standard time on its own date, up to 1912. Until that date, whatever zone applies, the birth runs on the *mean solar time of the birth longitude* and gets the `LOCAL_MEAN_TIME` notice. This overrides a `zone_key` you provide as well, because no zone was in use yet.

The zone key is then not the name the clock carried, so ask `nc.timezone_label(resolved_timezone, birth_datetime)` for the name you show a reader. It returns `"mean solar time"` when the offset came from the longitude, `None` when you provided a bare offset, which is then the whole answer, and the zone key in every other case.

`on_summer_time` says which reading of an ambiguous fall-back hour applies. It is kept only when the birth time really falls in a repeated hour; anywhere else it decided nothing and is dropped.

Birth dates are proleptic Gregorian; a Julian-calendar source date must be converted first (see the `PRE_GREGORIAN_DATE` caution under [Calculation notes](#calculation-notes)).

#### Errors

Bad input raises. Nothing is quietly replaced by a second-best answer.

| Error                           | Raised by             | When                                                                                                                                                                                     |
|---------------------------------|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ValueError`                    | `Location`            | Latitude is outside [-90, 90], or longitude outside [-180, 180].                                                                                                                           |
| `ValueError`                    | `resolve_timezone`    | You provided both `zone_key` and `offset`. Pass one or neither.                                                                                                                            |
| `ZoneInfoNotFoundError`         | `resolve_timezone`    | The `zone_key` you provided is not in the bundled data. `nc.zone_keys()` lists the keys.                                                                                                   |
| `TimezoneOffsetOutOfRangeError` | `resolve_timezone`    | The `offset` you provided lies outside UTC−16 to UTC+16. Every clock ever kept fits in that range, so anything beyond it is a data-entry error. A `zone_key` is not checked this way.       |
| `TimezoneLocationMismatchError` | `resolve_timezone`    | The timezone you provided is too far from the birth longitude's mean solar time: more than 2.5 h behind it, or 3.5 h ahead. Not checked from 60° latitude on (see [Latitude "trimming"](#latitude-trimming)). |
| `TypeError`                     | `Subject`             | `birth_datetime` carries a timezone, or `resolved_timezone` is not a `ResolvedTimezone`.                                                                                                   |
| `StaleTimezoneError`            | `Subject`, `input_notes` | The resolved timezone was worked out for another place or another date.                                                                                                                 |
| `ValueError`                    | `calculate_namkha`    | The birth instant never existed in its timezone, or the birth year is outside 1551–2598, the range of the bundled ephemeris.                                                                |
| `NotImplementedError`           | `calculate_namkha`    | `namkha_type` is `DAY` or `HOUR`. See [Namkha types](#namkha-types).                                                                                                                       |

The three timezone errors share the base class `TimezoneError`, which is itself a `ValueError`. The two timezone checks run only on a timezone you provided. A timezone the library derives already matches the location.

#### Result
**`NamkhaCalculationResult`**

| Field                | Type                              | Description                               |
|----------------------|-----------------------------------|-------------------------------------------|
| `subject`            | `Subject`                         | the input this result was calculated from |
| `calculation_method` | `CalculationMethod`               | the method used                           |
| `namkha_type`        | `NamkhaType`                      | the type calculated                       |
| `birth_element`      | `Element`                         | element of the birth period               |
| `birth_animal`       | `Animal`                          | animal of the birth period                |
| `birth_mewa`         | `int`                             | mewa number of the birth period           |
| `harmonized_aspects` | `tuple[HarmonizedAspect, ...]`    | eight aspects in order                    |
| `mewa_numbers`       | `dict[Aspect, int]`               | mewa number per mewa aspect; see below    |
| `calculation_notes`  | `tuple[CalculationNoteItem, ...]` | notices or cautions                       |

Every field is filled on every result.

The three `birth_*` fields describe the *birth period*, which is the period the requested `NamkhaType` names: the birth year for `YEAR`, the birth month for `MONTH`. The field names keep the `birth_` prefix for every type.

`mewa_numbers` holds four keys: `MEWA_LIFE`, `MEWA_BODY`, `MEWA_CAPACITY` and `MEWA_FORTUNE`. Each value is an `int` that also carries `.element`, the `Element` that mewa number stands for.

**`HarmonizedAspect`**

| Field               | Type                  | Description                                                   |
|---------------------|-----------------------|---------------------------------------------------------------|
| `name`              | `Aspect`              | `LIFE`, `BODY`, `CAPACITY`, `FORTUNE`, `MEWA_*`               |
| `center`            | `Element`             | center element                                                |
| `harmonization_seq` | `tuple[Element, ...]` | harmonization sequence: remaining thread colors outward       |
| `is_conflicted`     | `bool or None`        | `None` for `LIFE`; `True` when conflict harmonization applied |

**`CalculationNoteItem`**

| Field       | Type                  | Description                                              |
|-------------|-----------------------|----------------------------------------------------------|
| `note`      | `CalculationNote`     | which note this is, e.g. `HIGH_LATITUDE`                 |
| `note_type` | `CalculationNoteType` | `NOTICE` or `CAUTION`                                    |
| `message`   | `str`                 | one line describing the note                             |
| `doc`       | `str`                 | longer text; empty on every library note                 |

`note` is the one to branch on. `message` is written for a developer reading a log; an application showing notes to a reader is expected to supply its own wording per `note`.

**`Element`** and **`Animal`** are `str` enums, so a value is its canonical name in English: `Wood`, `Fire`, `Earth`, `Metal`, `Water`, and `Mouse`, `Ox`, `Tiger`, `Hare`, `Dragon`, `Snake`, `Horse`, `Sheep`, `Monkey`, `Bird`, `Dog`, `Boar`.

### Namkha types

The library calculates `YEAR` and `MONTH`. `DAY` and `HOUR` are already in `NamkhaType`, but `calculate_namkha` raises `NotImplementedError` for them.

`YEAR` accepts both methods, `CNNR` and `CLASSIC`. Every other type accepts `CLASSIC` alone and raises `ValueError` for `CNNR`.

#### Month Namkha

The Tibetan month of birth is resolved from the birth instant, the same way the year is. A Tibetan month begins at the dawn that begins its first day, so a birth before that dawn belongs to the month before. A birth close to that dawn, or to the one that begins the next month, gets the `PERIOD_BOUNDARY` caution (see [Calculation notes](#calculation-notes)).

A birth in a leap month gets the number, element, animal and mewa of the regular month it precedes.

The month element and animal follow the Phugpa formulas Janson gives (see [^3], section E.2: Attributes for months, under "Animals" and "Elements"). The library checks them against every month header in Henning's output over the years 1800–2598.

The month mewa steps back by one each month, across the year boundary too. It is pinned by a single anchor: the Tiger month opening a Tiger astrological year has mewa 2.

No Phugpa source prints a month mewa, so **these numbers are a reconstruction**. They come from two sources: Janson's Tsurphu formula (see [^3], section E.2: Attributes for months, under "Numbers"), the reverse order, and the triples the Vaidurya dkar po gives per month animal (see [^1], section 10: THE NAMKHA FOR HARMONIZING THE ELEMENTS OF THE MONTH OF BIRTH).

### Calculation notes

`result.calculation_notes` carries every note. All but `PERIOD_BOUNDARY` follow from the birth details alone, and `input_notes(resolved_timezone, location, birth_datetime)` returns those without running a calculation. `PERIOD_BOUNDARY` needs the calculation itself, so only the result has it.

`PERIOD_BOUNDARY` (caution) is attached when the birth time falls within 5 minutes of a calculation-period boundary: for `YEAR`, the Tibetan year start/end; for `MONTH`, the dawn that begins the month and the dawn that begins the next. That close to a boundary the result can flip to the neighboring period, so the birth time must be precise.

`HIGH_LATITUDE` (notice) is attached when `abs(latitude) >= 60.0`. Above this limit the library falls back to a fixed 5:00 AM day-start instead of civil twilight, which affects birth period boundary detection.

`AMBIGUOUS_LOCAL_TIME` (caution) is attached when the clocks went back and the naive birth time therefore happened twice that day. The library reads it as standard (non-DST) time. Pass `on_summer_time` to `resolve_timezone` to choose the other reading; the note then becomes a notice: `AMBIGUOUS_LOCAL_TIME_RESOLVED`.

The opposite case is an error: a time the clocks skipped going forward, or a whole date dropped by a dateline jump. A birth time that never happened at all is rejected with a `ValueError`.

`TIMEZONE_ESTIMATED` (caution) is attached when no timezone was given and it could not be derived from the location and date with certainty (pre-1970 birth, or birth on open water); the best historically recorded regional time was used.

There is one exception. For the dates where time standartization has not reached the birth region, the offset is read from the birth longitude instead of from the zone. The zone then has no effect on the result, so the caution is left out and the birth carries `LOCAL_MEAN_TIME` alone.

`TIMEZONE_BORDERS_UNCERTAIN` (caution) is attached instead of `TIMEZONE_ESTIMATED`. A birth never gets both.

The historical maps are snapshots at fixed years. When the snapshot before the birth year and the one after it put the birthplace in different countries, the library cannot tell which country held it at the moment of birth. Each country implies its own clocks, so an uncertain country means an uncertain zone.

Borders that changed and changed back between two snapshots are invisible to the maps, and no open dataset we know of can fill that gap. The Soviet occupation of eastern Poland from 1939 to 1941, which imposed Moscow time, is one such case.

To settle it, look up the birthplace's legal time in historical sources and pass it to `resolve_timezone` as `zone_key`. The [World Historical Gazetteer](https://whgazetteer.org/) is a good place to start: it tracks which state a place belonged to over time.

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

## References

[^1]: C.N. Norbu. Namkha: Harmonizing the Energy of the Elements. Shang Shung Publications, 2022.

[^2]: C.N. Norbu. Key for Consulting the Tibetan Calendar. Shang Shung Publications, 2014; M. Tsering. Jung-We Kyil-Khor – Mandala of Astrological Elements. Dynamic Space of the Elements ETS, 2020.

[^3]: S. Janson. Tibetan calendar mathematics. Department of Mathematics, Uppsala University, 2007; revised 2014 ([arXiv:1401.6285](https://arxiv.org/abs/1401.6285)). The output for checking our implementation of Janson's formulas comes from Henning's calendar program ([kalacakra.org](http://kalacakra.org/calendar/os_tib.htm)); Janson's paper is based on Henning's book: E. Henning. Kālacakra and the Tibetan Calendar. American Institute of Buddhist Studies, New York, 2007.
