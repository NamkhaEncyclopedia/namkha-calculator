"""Policy: naive local times are resolved only via astronomy.localize_standard."""

import ast
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent / "src" / "namkha_calculator"

# (file relative to package, enclosing function) allowed to call tz.localize
# directly. Every entry needs a justification here.
ALLOWED_LOCALIZE_SITES = {
    # The single resolution point the policy protects.
    ("astronomy.py", "localize_standard"),
    # is_dst=None probe: detects ambiguous/non-existent times, resolves nothing.
    ("calculation_notes.py", "local_time_dst_note"),
}


def _direct_localize_calls(tree: ast.Module) -> list[tuple[str | None, int]]:
    """All .localize(...) call sites as (enclosing function name, line)."""
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    function_defs = (ast.FunctionDef, ast.AsyncFunctionDef)
    calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "localize"
        ):
            scope = node
            while scope in parents and not isinstance(scope, function_defs):
                scope = parents[scope]
            name = scope.name if isinstance(scope, function_defs) else None
            calls.append((name, node.lineno))
    return calls


class TestLocalizationPolicy(unittest.TestCase):
    def test_localize_called_only_at_allowed_sites(self):
        violations = []
        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            rel = path.relative_to(PACKAGE_DIR).as_posix()
            tree = ast.parse(path.read_text(), filename=str(path))
            for func_name, lineno in _direct_localize_calls(tree):
                if (rel, func_name) not in ALLOWED_LOCALIZE_SITES:
                    violations.append(f"{rel}:{lineno} in {func_name or '<module>'}")
        self.assertEqual(
            [],
            violations,
            "direct tz.localize call(s) bypass localize_standard: "
            f"{violations}; use localize_standard, or extend "
            "ALLOWED_LOCALIZE_SITES with a justification",
        )

    def test_allowed_sites_still_exist(self):
        present = set()
        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            rel = path.relative_to(PACKAGE_DIR).as_posix()
            tree = ast.parse(path.read_text(), filename=str(path))
            present |= {(rel, name) for name, _ in _direct_localize_calls(tree)}
        self.assertEqual(
            set(),
            ALLOWED_LOCALIZE_SITES - present,
            "stale ALLOWED_LOCALIZE_SITES entries; remove them",
        )


if __name__ == "__main__":
    unittest.main()
