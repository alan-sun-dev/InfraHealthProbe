"""Local JSON inventory provider."""

from __future__ import annotations

import json
from pathlib import Path

from .core import Target, normalize_target, validate_target


def load_json_inventory(path: str | Path) -> list[Target]:
    """Load targets from a JSON file.

    Expected format: JSON array of target objects.

    Args:
        path: Path to JSON file.

    Returns:
        List of validated Target objects.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If any target fails validation.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw_list = json.load(f)

    if not isinstance(raw_list, list):
        raise ValueError(f"Expected JSON array in {path}, got {type(raw_list).__name__}")

    targets = []
    for i, raw in enumerate(raw_list):
        target = normalize_target(raw)
        errors = validate_target(target)
        if errors:
            raise ValueError(f"Target #{i} ({raw.get('TargetId', '?')}): {'; '.join(errors)}")
        targets.append(target)

    return targets
