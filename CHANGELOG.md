# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Month Namkha, through `calculate_namkha(NamkhaType.MONTH, subject)`. Only the
  Classic method is supported, as for every type other than the year. The
  Tibetan month of birth is resolved from the birth instant the same way the
  year is: the month starts at the first dawn of its first day, so a birth
  before that dawn belongs to the month before. A birth in a leap month gets
  the number, element, animal and mewa of the regular month it precedes.
- The month element and animal follow Janson's Phugpa formulas and are checked
  against every month header in Henning's output over 1800-2598.
- The month mewa steps back by one each month, pinned by a single anchor,
  `MONTH_MEWA_ANCHOR`: the Tiger month opening a Tiger astrological year has
  mewa 2. No Phugpa source prints a month mewa, so the numbers are a
  reconstruction. It is built from Janson's Tsurphu formula, the reverse order,
  and the triplets given per month animal by the Vaidurya dkar po.
- `TibetanMonthAttributes` gained `is_leap_month`, so a caller can tell a leap
  month from the regular month that shares its number.

### Changed

- `calendar.from_month_count` and `calendar.to_month_count` are now
  `from_true_month_count` and `to_true_month_count`, after the "true month
  count" Janson and Henning both use for this number. The `month_count`
  arguments of the astronomical functions are renamed to match.
- `calculation_notes.timezone_derivation_note` takes a second argument,
  `pre_standard_time_era`. It suppresses the derivation caution for a birth
  before standard time.

### Removed

- `calendar.tibetan_to_julian`: nothing calls it.

### Fixed

- Both Losar functions calculated the first day of a month by adding a day to
  day 30 of the month before. That disagrees with full Henning's output in four
  months over 1800-2598. They now start from day 0 of the month itself, which is
  a safe abstraction described in Janson's paper.

- A birth before 1880 was attributed to the country that the oldest bundled
  border map, drawn for 1880, shows at the birthplace. No country is looked up
  before the first map any more; the zone covering the birthplace today is kept
  instead.

- A birth before standard time carried the `TIMEZONE_ESTIMATED` or
  `TIMEZONE_BORDERS_UNCERTAIN` caution, warning about a derived zone which never
  reached the result: in that era the offset comes from the birth longitude
  no matter which zone applies. Such a birth now gets the `LOCAL_MEAN_TIME` notice
  alone.

- tzdb has no clock data for some eras. It marks such an era with `-00` and stores an
  offset of 0. That 0 is a placeholder, not a real clock, and the library read it
  as one. 18 bundled zones have such an era, the last one ending in 2005. A birth
  there takes the birth longitude's mean solar time, as a birth before
  standard time does, and gets the `LOCAL_MEAN_TIME` notice. The
  `TIMEZONE_ESTIMATED` caution stays because the library reconstructed this clock.

## [0.1.0a5] - 2026-08-19

### Added

- `zone_keys()` lists every IANA zone key in the bundled tzdata, so callers
  building a zone picker no longer reach into private members.
- `ResolvedTimezone`, a resolved timezone with how sure it is, where it came
  from, and the place facts that would otherwise need a fresh coordinate
  lookup during the calculation. It records the birth details it was worked
  out for and refuses, through `assert_binds`, to be used with others.
- `zone_derivation.resolve_timezone()` produces one. It is deliberately not
  re-exported at the package root: importing it from `zone_derivation` is
  what keeps the calculation path clear of the derivation code. Its
  `on_summer_time` argument is dropped from the result unless the birth
  time actually falls in a repeated fall-back hour, so a stored answer
  always means an ambiguity was resolved, never a no-op.
- `TimezoneError` and its subclasses `StaleTimezoneError`,
  `TimezoneOffsetOutOfRangeError` and `TimezoneLocationMismatchError`. All are
  ValueErrors, so existing catchers keep working, but callers can now tell the
  failures apart without matching on message text.
- `input_notes(resolved_timezone, location, birth_datetime)` returns the notes
  that follow from the birth details alone, without running a calculation, so a
  caller can show them as soon as the timezone is resolved. Notes that need the
  calculation itself, such as `PERIOD_BOUNDARY`, are not included. It takes the birth location and calls
  `assert_binds`, so a timezone worked out for another place or date raises
  `StaleTimezoneError` instead of deciding the high-latitude note.
- `CalculationNoteType` is re-exported at the package root. It was already the
  type of `CalculationNoteItem.note_type`, so reading a note's severity meant
  importing from `calculation_notes` directly.
- `timezone_label(resolved_timezone, birth_datetime)` names the timezone a
  calculation used. It returns `None` when the user gave a plain UTC offset, so
  the offset is the whole answer.

  The name is not always the resolved zone key. The key says which zone covers
  the birth place, and that stays true. The offset is a different matter: before
  the place kept standard time, the calculation does not use the zone's clock at
  all. It uses the mean solar time of the birth longitude, because every town
  then ran on its own sun. An 1849 Arkhangelsk birth resolves to `Europe/Moscow`
  and runs on Arkhangelsk sun time, twelve minutes ahead of Moscow's. Showing
  the key there would name a zone that did not produce the offset in use, so the
  label reports mean solar time instead.

  The label decides this with the same test as the `LOCAL_MEAN_TIME` note, so
  the two never disagree.

### Changed

- **Breaking:** `Subject` takes a `resolved_timezone` instead of
  `birth_timezone` and `on_summer_time`. Build one with
  `zone_derivation.resolve_timezone(location, birth_datetime)`, passing
  `zone_key=`, `offset=` or `on_summer_time=` where they used to go on
  `Subject`. Omitting the timezone no longer derives it: `Subject` never
  derives anything now, so a caller who leaves it out gets a `TypeError` for
  the missing argument rather than a silent coordinate lookup mid-calculation.

  `Subject.effective_timezone`, `timezone_derivation` and
  `timezone_is_longitude_based` still read the same; they now come straight
  off the resolved value. A timezone worked out for a different place or date is
  refused with `StaleTimezoneError`, and passing a timezone object where the
  resolved value belongs raises `TypeError`.

  The four note messages that told the reader to set `birth_timezone` or
  `on_summer_time` now point at `zone_derivation.resolve_timezone` and its
  `zone_key`, `offset` and `on_summer_time` arguments. Code matching on the
  message text has to change; the note identities are the same.

- `timezonefinder` is pinned to `>=8.2.4,<9.0.0`, from `>=6.5`. The polygon
  lookup this package uses works on 6.x as well, but 8.2.4 is the only version
  the tests run against, and its boundary data decides which zone a coordinate
  gets. The upper bound keeps a major release from changing that answer without
  anyone noticing.
- `calculation_notes.pre_gregorian_note` takes the birth region's Gregorian
  adoption date, as `gregorian_adoption_date`, instead of a `Location`. It no
  longer looks the date up; the resolved timezone already carries it. The
  parameter is named after the field and the lookup function it comes from, so
  a call passing a date that was not looked up for the birth place reads as
  wrong at the call site.
- `astronomy` has been split into three modules, separating the choice of a
  timezone from its use: `tz` holds the bundled tzdata and the plain value
  types, `localization` attaches a timezone to a naive local time, and
  `zone_derivation` works out which timezone applied at a place and date.
  Deriving a timezone is expensive and belongs to the moment birth details are
  entered, not to the calculation; keeping the two apart is what lets a caller
  do it once, up front.
- **Breaking:** the `astronomy` and `historical_borders` modules are gone, with
  no deprecation period. `import namkha_calculator.astronomy` now fails.
  Nothing public was lost: everything it held is importable from `tz`,
  `localization` or `zone_derivation`, and the names re-exported at the package
  root are unchanged. Only code reaching into the module paths directly is
  affected.

### Fixed

- A pre-1970 birth no longer loses its own zone because the border map cannot
  place that zone's reference city. Many reference cities sit on a coast, where
  the `zone.tab` coordinate falls just outside the coarse snapshot polygons, and
  the map returning nothing for one counted as the city lying abroad. The zone
  was then dropped and the nearest reference city in the birth country won
  instead. Mainland Denmark from 1935 to 1952 is the plainest case: Aarhus,
  Aalborg and Esbjerg derived `America/Scoresbysund` at UTC-2, a Greenland
  clock, rather than `Europe/Copenhagen` at UTC+1. Greenland is Danish, so its
  zones were candidates once the Danish one was gone.

  The change reaches further than Denmark. Measured over a land grid, it moves
  1648 place-and-snapshot combinations across 73 zone pairs, and every one of
  them returns the birth to the zone its own coordinates fall in:
  `Africa/El_Aaiun` back to `Africa/Algiers`, `Asia/Pontianak` back to
  `Asia/Jakarta`, `America/Kentucky/Monticello` back to `America/New_York`. A
  zone whose reference city the map *does* place in another country is still
  swapped as before, so an interwar Lviv birth keeps `Europe/Warsaw`.

### Security

- `zone()` takes only keys made of letters, digits, underscore, plus, minus and
  `/`, and raises `ZoneInfoNotFoundError` for anything else. The key becomes a
  path under the bundled tzdata, so a key holding `..` opened a file outside
  that tree. Nothing was read back to the caller, but the error told apart a
  path that exists from one that does not. Callers passing real IANA keys see
  no change.
