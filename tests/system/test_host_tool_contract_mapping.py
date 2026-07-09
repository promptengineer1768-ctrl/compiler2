"""Contracts for the Section 7 host-tool test coverage map."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SKELETON = ROOT / "SKELETON.md"
TEST_PLAN = ROOT / "TESTS.md"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "tools"


def _section(text: str, start: str, end: str) -> str:
    """Return text between two Markdown headings."""
    return text.split(start, 1)[1].split(end, 1)[0]


@pytest.mark.system
@pytest.mark.static
def test_every_section_7_function_has_one_coverage_row() -> None:
    """Every normative tool function maps to exactly one owning test row."""
    skeleton = _section(
        SKELETON.read_text(encoding="utf-8"),
        "## 7. Build System Python Tools",
        "## 8. Generated Artifacts Summary",
    )
    function_names = re.findall(r"^\| `([a-z][a-z0-9_]*)` \|", skeleton, re.MULTILINE)
    assert function_names

    plan = _section(
        TEST_PLAN.read_text(encoding="utf-8"),
        "### Section 7 Function Coverage Map",
        "## Functional Tests",
    )
    mapped_names = re.findall(
        r"^\| `[a-z0-9_]+\.([a-z][a-z0-9_]*)` \|",
        plan,
        re.MULTILINE,
    )
    assert sorted(mapped_names) == sorted(function_names)


@pytest.mark.system
@pytest.mark.static
def test_every_mapped_tool_function_is_callable() -> None:
    """The normative function map cannot point at missing implementations."""
    plan = _section(
        TEST_PLAN.read_text(encoding="utf-8"),
        "### Section 7 Function Coverage Map",
        "## Functional Tests",
    )
    contracts = re.findall(
        r"^\| `([a-z0-9_]+)\.([a-z][a-z0-9_]*)` \|",
        plan,
        re.MULTILINE,
    )
    missing = []
    for module_name, function_name in contracts:
        module = importlib.import_module(module_name)
        if not callable(getattr(module, function_name, None)):
            missing.append(f"{module_name}.{function_name}")
    assert missing == []


@pytest.mark.system
@pytest.mark.static
def test_tool_fixture_contract_defines_every_owner_directory() -> None:
    """The fixture README defines one location for every Section 7 tool."""
    readme = (FIXTURE_ROOT / "README.md").read_text(encoding="utf-8")
    expected = {
        "zp_alloc",
        "georam_pages",
        "generate_contracts",
        "linker_config",
        "extract_segments",
        "prepare_compressor_segments",
        "package_d64",
        "validate_build",
        "test_harness",
        "generate_reference",
    }
    declared = set(re.findall(r"^  ([a-z][a-z0-9_]*)/$", readme, re.MULTILINE))
    assert declared == expected
    normalized = " ".join(readme.split())
    assert "must not ignore ordering, addresses, sizes" in normalized
