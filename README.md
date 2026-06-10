<div style="text-align: center;">
  <img src="https://raw.githubusercontent.com/NamkhaEncyclopedia/namkha-calculator/main/logo.webp" alt="Namkha Calculator logo" width="150" height="150" />
</div>

# Namkha Calculator

[![PyPI version](https://img.shields.io/pypi/v/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![Python versions](https://img.shields.io/pypi/pyversions/namkha-calculator)](https://pypi.org/project/namkha-calculator/)
[![License: MIT](https://img.shields.io/pypi/l/namkha-calculator)](https://github.com/NamkhaEncyclopedia/namkha-calculator/blob/main/LICENSE)
[![Development Status](https://img.shields.io/pypi/status/namkha-calculator)](https://pypi.org/project/namkha-calculator/)

Python library for calculating [Namkha thread-cross](https://en.wikipedia.org/wiki/Namkha) color schemes in the tradition of [Chögyal Namkhai Norbu Rinpoche](https://en.wikipedia.org/wiki/Namkhai_Norbu), with all the methods covered in the source text.[^1] Classical Tibetan astrology calculations were added for cases where the source refers to them for complete instructions.[^2]

## Development status
> [!WARNING]
> The project is in an alpha stage – all calculations should be checked manually when making a real Namkha.

### TODO

- [x] Year Namkha calculation (CNNR and Classic)
- [x] Birth-time edge-case warnings
- [ ] Month Namkha calculation
- [ ] Day Namkha calculation
- [ ] Hour Namkha calculation
- [ ] Automatic historical timezone detection from coordinates
- [ ] More pre-calculated test cases
- [ ] Further investigation into the high-latitude regions problem

## Usage

```python
from datetime import datetime

import pytz

import namkha_calculator as nc

subject = nc.Subject(
    name="John Doe",
    gender=nc.Gender.MALE,
    birth_datetime=datetime(1985, 3, 15, 14, 30),  # naive local time
    birth_timezone=pytz.timezone("Europe/Berlin"),
    birth_location=nc.Location(latitude=52.52, longitude=13.40, name="Berlin"),
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
**`Subject`** – birth data for one person or any other appropriate entity.

| Field            | Type              | Notes                                                      |
|------------------|-------------------|------------------------------------------------------------|
| `gender`         | `Gender`          | `MALE` or `FEMALE`                                         |
| `birth_datetime` | `datetime`        | 'naive' (no tzinfo) local time                             |
| `birth_timezone` | `pytz.BaseTzInfo` | use `pytz.timezone(...)`                                   |
| `birth_location` | `Location`        | latitude/longitude in decimal degrees, optional place name |
| `name`           | `str or None`     | optional subject name                                      |

**`Location`** – `NamedTuple(latitude, longitude, name=None)`.

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

`HIGH_LATITUDE` (notice) is attached when `abs(latitude) >= 60.0`. Above this limit the library falls back to a fixed 5:00 AM day-start instead of civil twilight, which affects birth period boundary detection.

#### Latitude "trimming"

In the Tibetan calendar a new day begins at dawn, not at midnight. The library defines dawn as the start of *civil twilight* – the moment the sky first starts to brighten before sunrise (in traditional texts, when one can see the lines on the palm of their hand). This boundary decides which Tibetan hour (and therefore Tibetan day, month, etc.) a given birth time belongs to.

Closer to the poles (i.e. at higher latitudes) this breaks down. For long parts of the year there is no dawn: the midnight sun in summer, when the sky never fully darkens, and the polar night in winter, when it never properly brightens. On those dates civil twilight does not start (or does not end), so there is no dawn to anchor the day to and the astronomical lookup returns nothing.

As far as we know, there is no unified solution to this problem among Tibetan astrologers today. Considering different suggestions, for now we decided on the following method: the library "trims" the usable latitude range at *60° north/south*. Below that limit it uses the real civil-twilight dawn. At or above it, it falls back to a fixed *5:00 AM local time* (also can be found in Tibetan traditions) as the day-start and attaches the `HIGH_LATITUDE` notice.

## Contributing

Issues, PRs and questions are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Acknowledgments

*Whatever wisdom this contains belongs to the Tibetan astrological traditions and their holders; whatever faults it contains are our own.*

We thank everyone who supported the Namkha Calculator project financially – your help means a great deal to us, and it sustained us through a lot of obstacles.

We would also like to express our gratitude to:
Migmar Tsering, Maria Rita Leti, Adriano Clemente, Alexander Khosmo and Tatiana Ulyanova for their guidance on Tibetan astrology; and to the Gakyil of Merigar East – Oana Marcu and Krisztina Balla for their invaluable help in providing indispensable educational materials.

## References

[^1]: C.N. Norbu. Namkha: Harmonizing the Energy of the Elements. Shang Shung Publications, 2022.

[^2]: C.N. Norbu. Key for Consulting the Tibetan Calendar. Shang Shung Publications, 2014. M. Tsering. Jung-We Kyil-Khor – Mandala of Astrological Elements. Dynamic Space of the Elements ETS, 2020
