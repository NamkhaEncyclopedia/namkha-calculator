"""These tests read the package's own source code and check three rules:

1. Only localize_naive_time and its listed helpers may call
   replace(tzinfo=...), so ambiguous, skipped and LMT-era times are localized
   in one place.
2. Only tz.zone may construct ZoneInfo objects, so every zone comes
   from the bundled tzdata package, never the OS database.
3. No module outside zone_derivation may import zone_derivation, directly or
   through any chain of imports. Deriving a timezone is expensive and happens
   once, before the calculation; a module that can reach the derivation code
   can repeat it.

The first two rules have an allowlist of the (file, function) call sites
permitted to break them. To allow a new site, add an entry with a
justification; test_allowed_sites_still_exist fails if an entry goes stale.
The third has no allowlist: nothing outside zone_derivation needs it, and
resolve_timezone is deliberately absent from the package's __init__."""

import ast
import unittest
from pathlib import Path

import grimp

PACKAGE_DIR = Path(__file__).parent.parent / "src" / "namkha_calculator"
PACKAGE_NAME = "namkha_calculator"

# The subpackage that works out which timezone applied at a birth.
DERIVATION_PACKAGE = f"{PACKAGE_NAME}.zone_derivation"

# (file relative to package, enclosing function) allowed to attach a tzinfo
# via datetime.replace(tzinfo=...). Every entry needs a justification here.
ALLOWED_TZINFO_ATTACH_SITES = {
    # The helpers of localize_naive_time, the single localization point the
    # policy protects: its repeated-hour chooser and its pre-standard-time
    # branch.
    ("localization.py", "_choose_repeated_hour"),
    ("localization.py", "_birth_longitude_mean_time"),
    # Fold probes: detect ambiguous/non-existent times, localize nothing.
    ("localization.py", "is_ambiguous_local_time"),
    ("localization.py", "is_nonexistent_local_time"),
}

# (file, function) allowed to construct ZoneInfo objects. Everything else must
# use tz.zone, which loads from the bundled tzdata package instead of
# the OS timezone database.
ALLOWED_ZONEINFO_SITES = {
    ("tz/__init__.py", "zone"),
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


def _import_graph() -> grimp.ImportGraph:
    """The package's import graph, built by grimp from the source on disk.

    cache_dir=None turns grimp's cache off: the policy must read the code as it
    is now, and a cache directory in the repository would be one more thing to
    ignore.
    """
    return grimp.build_graph(PACKAGE_NAME, cache_dir=None)


def _display(module: str) -> str:
    """Readable name for a failure message: the package prefix every module
    shares is dropped, and the package's own __init__.py is named after it."""
    return (
        module.removeprefix(f"{PACKAGE_NAME}.")
        if module != PACKAGE_NAME
        else "__init__"
    )


def _paths_into_derivation() -> list[str]:
    """One import chain per module outside zone_derivation that can reach it.

    Each module is reported with the shortest chain that gets there, and the
    shortest chains come first.
    """
    graph = _import_graph()
    targets = sorted(
        module
        for module in graph.modules
        if module == DERIVATION_PACKAGE or module.startswith(f"{DERIVATION_PACKAGE}.")
    )
    found = []
    # as_package=True counts reaching any module inside zone_derivation, and
    # leaves out zone_derivation's own modules, which may import each other.
    for module in graph.find_downstream_modules(DERIVATION_PACKAGE, as_package=True):
        chains = [
            chain
            for target in targets
            if (chain := graph.find_shortest_chain(module, target)) is not None
        ]
        found.append(" -> ".join(map(_display, min(chains, key=len))))
    return sorted(found, key=lambda chain: (chain.count("->"), chain))


class TestLocalizationPolicy(unittest.TestCase):
    def test_tzinfo_attached_only_at_allowed_sites(self):
        outside = _violations(_attaches_tzinfo, ALLOWED_TZINFO_ATTACH_SITES)
        self.assertEqual(
            [],
            outside,
            "replace(tzinfo=...) bypasses localize_naive_time: "
            f"{outside}; use localize_naive_time, or extend "
            "ALLOWED_TZINFO_ATTACH_SITES with a justification",
        )

    def test_zoneinfo_constructed_only_at_allowed_sites(self):
        outside = _violations(_constructs_zoneinfo, ALLOWED_ZONEINFO_SITES)
        self.assertEqual(
            [],
            outside,
            "direct ZoneInfo construction bypasses the bundled tzdata: "
            f"{outside}; use tz.zone, or extend "
            "ALLOWED_ZONEINFO_SITES with a justification",
        )

    def test_derivation_is_unreachable_from_the_calculation_path(self):
        into_derivation = _paths_into_derivation()
        self.assertEqual(
            [],
            into_derivation,
            "these modules can reach zone_derivation and so could derive a "
            f"timezone again during a calculation: {into_derivation}; take the "
            "value from the ResolvedTimezone the caller already resolved",
        )

    def test_the_import_graph_sees_the_package(self):
        """A guard for the rule above: an empty or shallow graph would pass it
        no matter what the code imports."""
        graph = _import_graph()

        def imports(module: str) -> set[str]:
            return graph.find_modules_directly_imported_by(f"{PACKAGE_NAME}.{module}")

        self.assertIn(
            f"{PACKAGE_NAME}.tz", imports("astrology"), "`from .tz` not resolved"
        )
        self.assertIn(
            f"{PACKAGE_NAME}.astrology",
            imports("aspects.year"),
            "`from ..astrology` not resolved",
        )
        self.assertIn(
            f"{PACKAGE_NAME}.tz",
            imports("zone_derivation.lookup"),
            "`from ..tz` not resolved",
        )
        self.assertIn(
            f"{PACKAGE_NAME}.tz.errors",
            imports("zone_derivation"),
            "`from ..tz.errors` not resolved to the submodule",
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
