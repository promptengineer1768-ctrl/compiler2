"""Updates routine_directory.json with linked symbol addresses.

The geoRAM placement tool creates the routine directory before assembly, so
normal-RAM routines start with dynamic addresses.  After ld65 links the image,
this tool reads the VICE-style label file and stamps concrete addresses for
symbols that are present in the production binary.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LABEL_RE = re.compile(r"^\s*al\s+([0-9A-Fa-f]{6})\s+\.(\S+)\s*$")


def load_labels(path: Path) -> dict[str, int]:
    """Loads ld65 ``-Ln`` labels into a name-to-address mapping."""
    labels: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LABEL_RE.match(line)
        if match:
            labels[match.group(2)] = int(match.group(1), 16)
    return labels


def main() -> None:
    """Updates the routine directory in place."""
    if len(sys.argv) != 3:
        print(
            "usage: update_routine_addresses.py build/compiler.lbl build/routine_directory.json",
            file=sys.stderr,
        )
        raise SystemExit(2)

    labels_path = Path(sys.argv[1])
    directory_path = Path(sys.argv[2])
    labels = load_labels(labels_path)
    data = json.loads(directory_path.read_text(encoding="utf-8"))

    updated = 0
    for name, routine in data.get("routines", {}).items():
        # A geoRAM entry address is relative to the $DE00 window. The same
        # symbol may also exist in the temporary RAM link used to obtain bytes;
        # that staging address must never replace the installed ABI address.
        if name in labels and routine.get("layer") != "georam":
            routine["address"] = f"${labels[name]:04X}"
            updated += 1

    routines = data.setdefault("routines", {})
    next_id = max((r.get("id", -1) for r in routines.values()), default=-1) + 1
    for name, address in sorted(labels.items()):
        if name in routines:
            continue
        routines[name] = {
            "id": next_id,
            "layer": "linked",
            "address": f"${address:04X}",
        }
        next_id += 1
        updated += 1

    directory_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {updated} routine address(es) from {labels_path}.")


if __name__ == "__main__":
    main()
