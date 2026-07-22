"""Generate @pytest.mark.callable_coverage decorators for unit tests.

Scans tests/unit/test_*.py files, finds string literals matching production
entry names from build/production_entries.json, detects the executor helper
pattern used in each function, and adds the appropriate decorator.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ENTRIES_PATH = ROOT / "build" / "production_entries.json"
TEST_ENTRIES_PATH = ROOT / "build" / "test_entries.json"
TESTS_DIR = ROOT / "tests" / "unit"

# Patterns: (function_name_regex_or_exact, takes_string_arg)
# These are helper functions whose string argument is a production entry name.
CALL_HELPER_NAMES = {
    "_load_symbol_address",
    "_symbol_address",
    "_zp_address",
    "_returns",
    "_call",
    "_execute",
    "_run",
    "execute",
}

# Direct executor calls on emu instances (attribute access)
EMU_EXECUTORS = {"execute", "execute_rts"}


def load_production_names() -> set[str]:
    """Load all entry names from production and test manifests."""
    names: set[str] = set()
    for path, key in (
        (PRODUCTION_ENTRIES_PATH, "production_entries"),
        (TEST_ENTRIES_PATH, "test_entries"),
    ):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            names.update(str(entry["name"]) for entry in data.get(key, []))
    return names


def extract_string_arg(node: ast.expr) -> str | None:
    """Extract a string constant from an AST expression.

    Handles direct string constants and nested calls like
    _symbol_address("name") or _load_symbol_address("name").
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Handle nested: _symbol_address("name"), _load_symbol_address("name")
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in CALL_HELPER_NAMES:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value
    return None


def _is_execution_helper_call(call_node: ast.Call) -> bool:
    """Return True if a Call node is a direct execution helper invocation.

    Execution helpers are: _returns, _call, _execute, _run, _execute_routine.
    These are the functions whose string argument names a production entry.
    """
    func = call_node.func
    if isinstance(func, ast.Name) and func.id in {
        "_returns", "_call", "_execute", "_run", "_execute_routine",
    }:
        return True
    return False


def _is_emu_execute_call(call_node: ast.Call) -> bool:
    """Return True if a Call node is emu.execute(...) or emu.execute_rts(...)."""
    func = call_node.func
    if isinstance(func, ast.Attribute) and func.attr in EMU_EXECUTORS:
        if isinstance(func.value, ast.Name) and func.value.id in {"emu", "e"}:
            return True
    return False


def find_production_names_in_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    production_names: set[str],
) -> set[str]:
    """Find production entry names referenced in a test function body.

    Only matches names that appear as arguments to execution helpers
    (e.g. _execute_routine(emu, "name")) or as direct string arguments
    to emu.execute("name").  Does NOT match names inside
    _load_symbol_address("name") or _symbol_address("name") since those
    only look up addresses.
    """
    found: set[str] = set()

    for child in ast.walk(func_node):
        if not isinstance(child, ast.Call):
            continue

        # Pattern 1: _execute_routine(emu, "name"), _returns("name"), etc.
        if _is_execution_helper_call(child):
            for arg in child.args:
                name = extract_string_arg(arg)
                if name and name in production_names:
                    found.add(name)

        # Pattern 2: emu.execute(_symbol_address("name"), ...) - NOT matched
        # because _symbol_address is an address lookup, not execution.
        # Pattern 3: emu.execute("name", ...) - direct string arg
        if _is_emu_execute_call(child):
            for arg in child.args:
                name = extract_string_arg(arg)
                if name and name in production_names:
                    found.add(name)

    # Pattern 4: @pytest.mark.parametrize decorators with tuples of names
    for decorator in func_node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "parametrize"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "mark"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "pytest"
        ):
            continue
        for arg in decorator.args + [kw.value for kw in decorator.keywords]:
            for node in ast.walk(arg):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in production_names:
                        found.add(node.value)

    return found


def detect_executor(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Detect which executor helper the function body calls.

    Returns the executor name, or None if no callable execution pattern is found.
    """
    for child in ast.walk(func_node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            if func.id in EMU_EXECUTORS:
                return func.id
            if func.id in {"_returns", "_call", "_execute", "_run", "_execute_routine"}:
                return "execute_rts" if func.id == "_execute_routine" else func.id
        if isinstance(func, ast.Attribute):
            if func.attr in EMU_EXECUTORS:
                return func.attr
            if isinstance(func.value, ast.Name) and func.value.id in {"emu", "e"}:
                if func.attr == "execute":
                    return "execute"
                if func.attr == "execute_rts":
                    return "execute_rts"
    return None


def has_callable_coverage_decorator(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function already has a @pytest.mark.callable_coverage decorator."""
    for decorator in func_node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "callable_coverage"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "mark"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "pytest"
        ):
            return True
    return False


def ensure_import_pytest_in_lines(lines: list[str]) -> None:
    """Ensure 'import pytest' is present in the lines list (mutates in place)."""
    for line in lines:
        stripped = line.strip()
        if stripped == "import pytest" or stripped.startswith("from pytest"):
            return
    last_import_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import_idx = i
    lines.insert(last_import_idx + 1, "import pytest")


def build_decorator_lines(
    names: list[str],
    executor: str,
    indent: str = "    ",
) -> list[str]:
    """Build decorator lines for callable_coverage markers."""
    lines = []
    for name in sorted(names):
        lines.append(f'{indent}@pytest.mark.callable_coverage("{name}", executor="{executor}")')
    return lines


def process_file(
    path: Path,
    production_names: set[str],
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Process a single test file and add callable_coverage decorators.

    Returns mapping from function name to list of coverage names added.
    """
    raw = path.read_bytes()
    # Strip BOM if present
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    source = raw.decode("utf-8")
    tree = ast.parse(source, filename=str(path))

    # Collect all functions and their coverage names
    func_coverage: dict[str, list[str]] = {}
    functions_to_annotate: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, list[str]]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if has_callable_coverage_decorator(node):
            # Already has decorator - skip but record existing
            existing = []
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "callable_coverage"
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    existing.append(decorator.args[0].value)
            if existing:
                func_coverage[node.name] = existing
            continue

        names_found = find_production_names_in_function(node, production_names)
        if not names_found:
            continue

        executor = detect_executor(node)
        if executor is None:
            continue
        func_coverage[node.name] = sorted(names_found)
        functions_to_annotate.append((node, sorted(names_found), executor))

    if not functions_to_annotate or dry_run:
        return func_coverage

    # Detect line ending style and split accordingly
    line_ending = "\r\n" if "\r\n" in source else "\n"
    lines = source.split(line_ending)
    # Process in reverse order to preserve line numbers
    for func_node, names, executor in reversed(functions_to_annotate):
        # Find the line number of the first decorator or the def line
        if func_node.decorator_list:
            insert_before_line = func_node.decorator_list[0].lineno - 1
        else:
            insert_before_line = func_node.lineno - 1

        # Detect actual indentation from the function/first decorator line
        target_line = lines[func_node.decorator_list[0].lineno - 1] if func_node.decorator_list else lines[func_node.lineno - 1]
        indent = ""
        for ch in target_line:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break

        # Build decorator block
        decorator_lines = build_decorator_lines(names, executor, indent=indent)
        for i, dline in enumerate(decorator_lines):
            lines.insert(insert_before_line + i, dline)

    ensure_import_pytest_in_lines(lines)
    new_source = line_ending.join(lines)
    path.write_bytes(new_source.encode("utf-8"))
    return func_coverage


def main() -> None:
    """Run the decorator generation across all unit test files."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate @pytest.mark.callable_coverage decorators for unit tests."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without modifying files.",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Process specific test files instead of all unit tests.",
    )
    args = parser.parse_args()

    production_names = load_production_names()
    print(f"Loaded {len(production_names)} production entry names.")

    if args.files:
        test_files = [ROOT / f for f in args.files]
    else:
        test_files = sorted(TESTS_DIR.glob("test_*.py"))

    total_names_covered: set[str] = set()
    total_functions = 0

    for path in test_files:
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        func_coverage = process_file(path, production_names, dry_run=args.dry_run)
        if func_coverage:
            added = 0
            for fname, names in func_coverage.items():
                total_names_covered.update(names)
                added += len(names)
            total_functions += len(func_coverage)
            action = "Would annotate" if args.dry_run else "Annotated"
            print(f"  {action} {path.name}: {len(func_coverage)} functions, {added} coverage names")

    uncovered = production_names - total_names_covered
    print(f"\nTotal functions annotated: {total_functions}")
    print(f"Production names covered: {len(total_names_covered)}/{len(production_names)}")
    if uncovered:
        print(f"Uncovered production names ({len(uncovered)}):")
        for name in sorted(uncovered):
            print(f"  - {name}")


if __name__ == "__main__":
    main()
