"""Add @pytest.mark.callable_coverage decorators to test functions.

For each production routine, find test functions that exercise it and add
the decorator with the correct executor. Idempotent.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES_FILES = [
    ROOT / "build" / "production_entries.json",
    ROOT / "build" / "test_entries.json",
]
TEST_DIR = ROOT / "tests" / "unit"

# Executors recognized by test_harness.py, in priority order
EXECUTORS = [
    ("execute", {"_call", "_execute", "_run_paged", "_invoke",
                  "_run_xip", "_execute_xip_no_args"}),
    ("execute_rts", {"execute_rts", "execute", "_execute_routine"}),
]


def load_routine_names() -> set[str]:
    names: set[str] = set()
    for path in ENTRIES_FILES:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                n = item.get("name", "")
                                if n:
                                    names.add(n)
    return names


def detect_executor(func_source: str) -> str | None:
    """Detect which executor the test function uses.

    Returns None if no executor pattern is found (function doesn't call any).
    Priority: check specific helpers first, then general patterns.
    """
    import re
    # Check for wrapper helpers first (they use emu.execute internally)
    wrapper_patterns = [r'\b_call\b', r'\b_execute\b', r'\b_run_paged\b',
                        r'\b_invoke\b', r'\b_run_xip\b', r'\b_execute_xip_no_args\b',
                        r'\b_returns\b']
    for pattern in wrapper_patterns:
        if re.search(pattern, func_source):
            return "execute"
    # Check for direct execute_rts / execute calls
    rts_patterns = [r'\bexecute_rts\b', r'\b_execute_routine\b']
    for pattern in rts_patterns:
        if re.search(pattern, func_source):
            return "execute_rts"
    # Bare "execute" as a method call (emu.execute) → treat as execute_rts
    if re.search(r'\.execute\b', func_source) or re.search(r'\bexecute\s*\(', func_source):
        return "execute_rts"
    return None


def process_file(test_file: Path, routine_names: set[str]) -> int:
    """Add decorators to one test file. Returns count added."""
    try:
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return 0

    lines = source.splitlines(keepends=True)
    insertions: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        func_start = node.lineno
        func_end = node.end_lineno or node.lineno
        func_lines = source.splitlines()[func_start - 1:func_end]
        func_source = "\n".join(func_lines)

        # Find which routines this function exercises
        executor = detect_executor(func_source)
        for name in sorted(routine_names):
            if f'"{name}"' not in func_source and f"'{name}'" not in func_source:
                continue

            # Must actually call an executor to be valid coverage
            if not executor:
                continue

            # Check if already decorated
            already = False
            for i in range(max(0, func_start - 10), func_start - 1):
                line = lines[i] if i < len(lines) else ""
                if f'@pytest.mark.callable_coverage("{name}"' in line:
                    already = True
                    break
            if already:
                continue

            # Detect indentation from the def line
            def_line = lines[func_start - 1] if func_start - 1 < len(lines) else ""
            indent = len(def_line) - len(def_line.lstrip())
            spaces = " " * indent
            decorator = f'{spaces}@pytest.mark.callable_coverage("{name}", executor="{executor}")\n'
            insertions.append((func_start - 1, decorator))

    if not insertions:
        return 0

    # Apply insertions in reverse order
    for idx, dec in sorted(insertions, key=lambda x: x[0], reverse=True):
        # idx is 0-indexed line of the def statement
        # Walk backwards to find first decorator for this function
        insert_at = idx
        while insert_at > 0 and lines[insert_at - 1].strip().startswith("@"):
            insert_at -= 1
        lines.insert(insert_at, dec)

    test_file.write_text("".join(lines), encoding="utf-8")
    return len(insertions)


def main() -> None:
    routine_names = load_routine_names()
    print(f"Loaded {len(routine_names)} routine names")

    total_added = 0
    files_modified = 0

    for test_file in sorted(TEST_DIR.glob("test_*.py")):
        added = process_file(test_file, routine_names)
        if added > 0:
            total_added += added
            files_modified += 1
            print(f"  {test_file.name}: +{added} decorators")

    print(f"\nTotal: +{total_added} decorators across {files_modified} files")


if __name__ == "__main__":
    main()
