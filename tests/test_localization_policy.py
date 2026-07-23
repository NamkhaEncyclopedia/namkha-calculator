"""These tests read the package's own source code and check two rules:

1. Only resolve_local_time and its listed helpers may call
   replace(tzinfo=...), so ambiguous, skipped and LMT-era times are resolved
   in one place.
2. Only astronomy.zone may construct ZoneInfo objects, so every zone comes
   from the bundled tzdata package, never the OS database.

Each rule has an allowlist of the (file, function) call sites permitted to
break it. To allow a new site, add an entry with a justification;
test_allowed_sites_still_exist fails if an entry goes stale."""

import ast
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent / "src" / "namkha_calculator"

# (file relative to package, enclosing function) allowed to attach a tzinfo
# via datetime.replace(tzinfo=...). Every entry needs a justification here.
ALLOWED_TZINFO_ATTACH_SITES = {
    # The helpers of resolve_local_time, the single resolution point the
    # policy protects: its repeated-hour chooser and its pre-standard-time
    # branch.
    ("astronomy.py", "_resolve_repeated_hour"),
    ("astronomy.py", "_birth_longitude_mean_time"),
    # Fold probes: detect ambiguous/non-existent times, resolve nothing.
    ("astronomy.py", "is_ambiguous_local_time"),
    ("astronomy.py", "is_nonexistent_local_time"),
}

# (file, function) allowed to construct ZoneInfo objects. Everything else must
# use astronomy.zone, which loads from the bundled tzdata package instead of
# the OS timezone database.
ALLOWED_ZONEINFO_SITES = {
    ("astronomy.py", "zone"),
}


def _enclosing_function(node: ast.AST, parents: dict) -> str | None:
    """Name of the innermost function containing the node, None at module level."""
    function_defs = (ast.FunctionDef, ast.AsyncFunctionDef)
    scope = node
    while scope in parents and not isinstance(scope, function_defs):
        scope = parents[scope]
    return scope.name if isinstance(scope, function_defs) else None


def _call_sites(tree: ast.Module, is_match) -> list[tuple[str | None, int]]:
    """(enclosing function, line) of every Call node matching the predicate."""
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    return [
        (_enclosing_function(node, parents), node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and is_match(node)
    ]


def _attaches_tzinfo(call: ast.Call) -> bool:
    """Whether the call is a datetime.replace(..., tzinfo=...)."""
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "replace"
        and any(keyword.arg == "tzinfo" for keyword in call.keywords)
    )


# ZoneInfo and its bundled-data subclass (astronomy._KeyedZoneInfo).
_ZONEINFO_NAMES = {"ZoneInfo", "_KeyedZoneInfo"}


def _constructs_zoneinfo(call: ast.Call) -> bool:
    """Whether the call constructs a ZoneInfo, e.g. ZoneInfo(...) or
    _KeyedZoneInfo.from_file(...)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in _ZONEINFO_NAMES
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in _ZONEINFO_NAMES
    )


def _found_sites(is_match) -> list[tuple[str, str | None, int]]:
    """Every matching call in the package, as (file, enclosing function, line)."""
    found = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = path.relative_to(PACKAGE_DIR).as_posix()
        tree = ast.parse(path.read_text(), filename=str(path))
        for func_name, lineno in _call_sites(tree, is_match):
            found.append((rel, func_name, lineno))
    return found


def _violations(is_match, allowed_sites: set) -> list[str]:
    """Matching call sites that are not on the allowlist."""
    return [
        f"{rel}:{lineno} in {func_name or '<module>'}"
        for rel, func_name, lineno in _found_sites(is_match)
        if (rel, func_name) not in allowed_sites
    ]


def _present_sites(is_match) -> set:
    """The (file, function) sites where matching calls actually occur."""
    return {(rel, func_name) for rel, func_name, _ in _found_sites(is_match)}


class TestLocalizationPolicy(unittest.TestCase):
    def test_tzinfo_attached_only_at_allowed_sites(self):
        outside = _violations(_attaches_tzinfo, ALLOWED_TZINFO_ATTACH_SITES)
        self.assertEqual(
            [],
            outside,
            "replace(tzinfo=...) bypasses resolve_local_time: "
            f"{outside}; use resolve_local_time, or extend "
            "ALLOWED_TZINFO_ATTACH_SITES with a justification",
        )

    def test_zoneinfo_constructed_only_at_allowed_sites(self):
        outside = _violations(_constructs_zoneinfo, ALLOWED_ZONEINFO_SITES)
        self.assertEqual(
            [],
            outside,
            "direct ZoneInfo construction bypasses the bundled tzdata: "
            f"{outside}; use astronomy.zone, or extend "
            "ALLOWED_ZONEINFO_SITES with a justification",
        )

    def test_allowed_sites_still_exist(self):
        tzinfo_present = _present_sites(_attaches_tzinfo)
        zoneinfo_present = _present_sites(_constructs_zoneinfo)
        stale = (ALLOWED_TZINFO_ATTACH_SITES - tzinfo_present) | (
            ALLOWED_ZONEINFO_SITES - zoneinfo_present
        )
        self.assertEqual(set(), stale, "stale allowlist entries; remove them")


if __name__ == "__main__":
    unittest.main()
