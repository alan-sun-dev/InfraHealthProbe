"""Local CSV inventory provider."""

from __future__ import annotations

import csv
from pathlib import Path

from .core import Target, normalize_target, validate_target


def load_csv_inventory(path: str | Path) -> list[Target]:
    """Load targets from a CSV file.

    Multi-value fields (Ports, Urls) use semicolon separator.

    Args:
        path: Path to CSV file.

    Returns:
        List of validated Target objects.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If any target fails validation.
    """
    path = Path(path)
    targets = []

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            target = normalize_target(row)
            errors = validate_target(target)
            if errors:
                raise ValueError(f"Row #{i + 1} ({row.get('TargetId', '?')}): {'; '.join(errors)}")
            targets.append(target)

    return targets
