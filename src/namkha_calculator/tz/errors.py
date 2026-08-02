class TimezoneError(ValueError):
    """Base for every timezone failure this package raises."""


class StaleTimezoneError(TimezoneError):
    """A resolved timezone does not match the birth details it was worked out
    for: the place or the date changed after it was settled."""


class TimezoneOffsetOutOfRangeError(TimezoneError):
    """A fixed UTC offset lies outside the range real timezones have used."""


class TimezoneLocationMismatchError(TimezoneError):
    """A timezone's clock is too far from the location's mean solar time for
    the two to belong together."""
