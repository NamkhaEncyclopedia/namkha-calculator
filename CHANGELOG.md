# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `zone_keys()` lists every IANA zone key in the bundled tzdata, so callers
  building a zone picker no longer reach into private members.

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
