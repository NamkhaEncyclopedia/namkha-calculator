# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `zone_keys()` lists every IANA zone key in the bundled tzdata, so callers
  building a zone picker no longer reach into private members.
- `ResolvedTimezone`, a settled timezone with how sure it is, where it came
  from, and the place facts that would otherwise need a fresh coordinate
  lookup during the calculation. It records the birth details it was worked
  out for and refuses, through `assert_binds`, to be used with others.
- `zone_derivation.derive_timezone()` produces one. It is deliberately not
  re-exported at the package root: importing it from `zone_derivation` is
  what keeps the calculation path clear of the derivation code. Its
  `on_summer_time` argument is dropped from the result unless the birth
  time actually falls in a repeated fall-back hour, so a stored answer
  always means an ambiguity was resolved, never a no-op.
- `TimezoneError` and its subclasses `StaleTimezoneError`,
  `TimezoneOffsetOutOfRangeError` and `TimezoneLocationMismatchError`. All are
  ValueErrors, so existing catchers keep working, but callers can now tell the
  failures apart without matching on message text.

Nothing consumes `ResolvedTimezone` yet; `Subject` is unchanged.

### Changed

- `astronomy` has been split into three modules, separating the choice of a
  timezone from its use: `tz` holds the bundled tzdata and the plain value
  types, `localization` attaches a timezone to a naive local time, and
  `zone_derivation` works out which timezone applied at a place and date.
  Deriving a timezone is expensive and belongs to the moment birth details are
  entered, not to the calculation; keeping the two apart is what lets a caller
  do it once, up front.
- `astronomy` and `historical_borders` still re-export everything from their
  new homes. Both are deprecated and will be removed in the next release.
