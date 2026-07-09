"""Shared fixtures for tool tests.

Provides comparison utilities that ignore timestamps and host-specific paths
when validating generated outputs.
"""

import re
from typing import Optional, Set


def normalize_line_endings(content: str) -> str:
    """Normalize line endings to LF for cross-platform comparison.

    Args:
        content: File content string.

    Returns:
        Content with consistent LF line endings.
    """
    return content.replace("\r\n", "\n").replace("\r", "\n")


def strip_timestamps(content: str) -> str:
    """Remove timestamp patterns that vary between runs.

    Args:
        content: File content string.

    Returns:
        Content with timestamps replaced by placeholders.
    """
    # ISO 8601 timestamps
    content = re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        "<TIMESTAMP>",
        content,
    )
    # Unix timestamps (10-digit)
    content = re.sub(r"\b\d{10}\b", "<TIMESTAMP>", content)
    return content


def strip_host_paths(content: str) -> str:
    """Remove host-specific file paths.

    Args:
        content: File content string.

    Returns:
        Content with paths replaced by placeholders.
    """
    # Windows paths
    content = re.sub(
        r"[A-Z]:\\[^:\n]+",
        "<PATH>",
        content,
    )
    # Unix paths
    content = re.sub(
        r"/home/[^:\n]+",
        "<PATH>",
        content,
    )
    content = re.sub(
        r"/Users/[^:\n]+",
        "<PATH>",
        content,
    )
    return content


def normalize_for_comparison(content: str) -> str:
    """Apply all normalizations for deterministic comparison.

    Args:
        content: File content string.

    Returns:
        Normalized content suitable for comparison.
    """
    content = normalize_line_endings(content)
    content = strip_timestamps(content)
    content = strip_host_paths(content)
    return content


def assert_files_equal(
    actual_path: str,
    expected_path: str,
    ignore_timestamps: bool = True,
    ignore_paths: bool = True,
) -> None:
    """Assert two files are equal after normalization.

    Args:
        actual_path: Path to actual generated file.
        expected_path: Path to expected reference file.
        ignore_timestamps: Whether to strip timestamps before comparison.
        ignore_paths: Whether to strip host paths before comparison.

    Raises:
        AssertionError: If files differ after normalization.
    """
    with open(actual_path, "r", encoding="utf-8") as f:
        actual = f.read()

    with open(expected_path, "r", encoding="utf-8") as f:
        expected = f.read()

    if ignore_timestamps:
        actual = strip_timestamps(actual)
        expected = strip_timestamps(expected)

    if ignore_paths:
        actual = strip_host_paths(actual)
        expected = strip_host_paths(expected)

    actual = normalize_line_endings(actual)
    expected = normalize_line_endings(expected)

    assert (
        actual == expected
    ), f"Files differ:\nActual: {actual_path}\nExpected: {expected_path}"


def collect_stable_lines(
    content: str, exclude_patterns: Optional[Set[str]] = None
) -> str:
    """Extract only stable, deterministic lines from generated content.

    Args:
        content: File content string.
        exclude_patterns: Regex patterns to exclude (e.g., timestamps, paths).

    Returns:
        Filtered content with only stable lines.
    """
    if exclude_patterns is None:
        exclude_patterns = {
            r"<TIMESTAMP>",
            r"<PATH>",
            r"fingerprint",
        }

    lines = content.split("\n")
    stable_lines = []
    for line in lines:
        if not any(re.search(pattern, line) for pattern in exclude_patterns):
            stable_lines.append(line)

    return "\n".join(stable_lines)
