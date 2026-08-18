# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  calculation used, or returns `None` when the user gave a plain UTC offset and
  the offset is the whole answer. It answers a question `str(tzinfo)` could not:
  a birth before its zone's standard time began keeps that zone's key while the
  calculation runs on the birth longitude's mean solar time, so the key names a
  zone that did not produce the offset in use. The label shares its test for
  that with the `LOCAL_MEAN_TIME` note, so the two never disagree.

### Changed

- **Breaking:** `Subject` takes a `resolved_timezone` instead of
  `birth_timezone` and `on_summer_time`. Build one with
  `zone_derivation.resolve_timezone(location, birth_datetime)`, passing
  `zone_key=`, `offset=` or `on_summer_time=` where they used to go on
  `Subject`. Omitting the timezone no longer derives it: `Subject` never
  derives anything now, so a caller who leaves it out gets a `TypeError` for
  the missing argument rather than a silent coordinate lookup mid-calculation.

  There is no compatibility shim, and one is not possible. A `ResolvedTimezone`
  carries facts only the derivation knows – the birthplace's Gregorian adoption
  date among them – so a shim accepting `birth_timezone=` could fill them in
  only by importing the derivation code into the calculation path, which is the
  separation this release exists to make. Substituting defaults instead would
  quietly change which births get a `PRE_GREGORIAN_DATE` caution.

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

### Security

- `zone()` takes only keys made of letters, digits, underscore, plus, minus and
  `/`, and raises `ZoneInfoNotFoundError` for anything else. The key becomes a
  path under the bundled tzdata, so a key holding `..` opened a file outside
  that tree. Nothing was read back to the caller, but the error told apart a
  path that exists from one that does not. Callers passing real IANA keys see
  no change.
