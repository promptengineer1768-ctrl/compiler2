"""Prepare an isolated, empty output directory for a production build."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def prepare_clean_output(project_root: Path, output_dir: Path) -> Path:
    """Remove and recreate one explicitly scoped build-output directory.

    Args:
        project_root: Repository root that bounds deletion.
        output_dir: Build output directory, relative to the root or absolute.

    Returns:
        The resolved, empty output directory.

    Raises:
        ValueError: If the requested directory is not a strict child of root.
    """
    root = project_root.resolve()
    target = (
        (root / output_dir).resolve()
        if not output_dir.is_absolute()
        else output_dir.resolve()
    )
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"build output must be inside project root: {target}"
        ) from error
    if target == root:
        raise ValueError("refusing to clean the project root")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "obj").mkdir()
    (target / "listings").mkdir()
    return target


def main() -> None:
    """Run the guarded build-output cleanup command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = prepare_clean_output(args.project_root, args.output_dir)
    print(f"Prepared clean build output: {target}")


if __name__ == "__main__":
    main()
