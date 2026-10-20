"""Ordered scoring rules for Number of Tries, stored as one JSON config line."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class AttemptRule:
    label: str
    attempts: int
    attempt_numbers: tuple[int, ...]
    sort: str


def parse_attempt_rules(value: str) -> tuple[AttemptRule, ...]:
    """Validate the complete rule list; empty lists retain the legacy format."""
    try:
        data = json.loads(value or "[]")
    except (ValueError, TypeError) as exc:
        raise ValueError("Attempt rules must be a valid JSON array.") from exc
    if not isinstance(data, list):
        raise ValueError("Attempt rules must be a JSON array.")
    return tuple(_parse_rule(item, i + 1) for i, item in enumerate(data))


def _parse_rule(item: object, position: int) -> AttemptRule:
    prefix = f"Attempt rule {position}: "
    if not isinstance(item, dict) or set(item) != {
        "label",
        "attempts",
        "attempt_numbers",
        "sort",
    }:
        raise ValueError(prefix + "expected label, attempts, attempt_numbers and sort.")
    label, count = item["label"], item["attempts"]
    numbers, direction = item["attempt_numbers"], item["sort"]
    if not isinstance(label, str):
        raise ValueError(prefix + "label must be text.")
    if type(count) is not int or count < 1:
        raise ValueError(prefix + "attempts must be a positive integer.")
    if (
        not isinstance(numbers, list)
        or not numbers
        or any(type(n) is not int or n < 1 for n in numbers)
        or len(set(numbers)) != len(numbers)
    ):
        raise ValueError(prefix + "attempt_numbers must be unique positive integers.")
    if count > len(numbers):
        raise ValueError(prefix + "attempts exceeds the number of eligible attempts.")
    if direction not in ("asc", "desc"):
        raise ValueError(prefix + "sort must be asc or desc.")
    return AttemptRule(label, count, tuple(numbers), direction)


def rules_json(rules: tuple[AttemptRule, ...]) -> str:
    """Serialize without physical line breaks, including line breaks in labels."""
    return json.dumps(
        [
            {
                "label": r.label,
                "attempts": r.attempts,
                "attempt_numbers": list(r.attempt_numbers),
                "sort": r.sort,
            }
            for r in rules
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
