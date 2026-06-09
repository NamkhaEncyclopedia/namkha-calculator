# Contributing

## Setup

```bash
poetry install --with dev
```

The ephemeris file `de440_filtered.bsp` must be present next to `skyfield_calculations.py` for astronomy calculations to work.

## Running tests

```bash
poetry run python -m unittest discover -s tests
```

When modifying Tibetan calendar math in `calendar.py`, the full calendar range matters – the test suite already covers 1800–2598 via Henning reference data, so run it in full.

## Code style

Python 3.12+. Formatting is enforced by pre-commit hooks – install them before committing:

```bash
pip install pre-commit
pre-commit install
```

Hooks run **black** (formatter, 88-char lines, double quotes) and **ruff** (linter, auto-fix enabled). Run manually with:

```bash
pre-commit run --all-files
```

**Imports**
- Use `X | None` instead of `Optional[X]`.
- Use local relative imports (`from ..astronomy import LATITUDE_LIMIT`).

**Types and data**
- `Element` and `Animal` are `str` enums – values are English names consistent with Namkhai Norbu tradition.
- `Subject.birth_datetime` must be naive; pass *Pytz* timezone separately as `birth_timezone`.
- New public types go in `core/__init__.py`.

## AI usage

LLM-generated code is accepted only after thorough line-by-line review by the developer. **Strictly no autonomous vibe-coding.**

No auto-generated commit messages and PR descriptions.
