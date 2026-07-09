"""Fixture-backed execution tests for all shared E2E mode runners."""

from __future__ import annotations

import pytest

from tests.e2e.mode_runner import get_runner_for_mode
from tests.e2e.reference_fixtures import load_reference


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("mode", "fixture_id"),
    [
        ("immediate", "basicv2-immediate-PRINT"),
        ("program", "basicv2-program-FOR"),
        ("compile", "basicv2-program-GOTO"),
    ],
)
def test_mode_runner_applies_versioned_observation(mode: str, fixture_id: str) -> None:
    """Immediate, program, and compile modes evaluate their stock fixture."""
    fixture = load_reference("basicv2", fixture_id)
    case = {
        "profile": "basicv2",
        "mode": mode,
        "fixture_id": fixture_id,
        "vice_pending": False,
        "expected_result": fixture["normalized_result"],
    }
    result = get_runner_for_mode(mode).run_case(case)
    assert result["passed"] is True
    assert result["actual"] == fixture["normalized_result"]


@pytest.mark.e2e
def test_pending_fixture_is_not_reported_as_a_pass() -> None:
    """A missing observation stays pending and cannot inflate pass counts."""
    result = get_runner_for_mode("immediate").run_case(
        {"profile": "basicv2", "mode": "immediate", "vice_pending": True}
    )
    assert result["passed"] is None
    assert "pending" in str(result["actual"]).lower()
