"""Golden fixture comparison utilities."""

import json
from pathlib import Path
from typing import Any


GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_0873ebf" / "daemon"


def load_golden(method_name: str) -> dict | None:
    """
    Load golden fixture for a method.

    Returns:
        Golden fixture dict, or None if not found.
    """
    golden_file = GOLDEN_DIR / f"{method_name}.json"
    if not golden_file.exists():
        return None

    with open(golden_file) as f:
        return json.load(f)


def compare_to_golden(
    method_name: str,
    response_data: dict,
) -> tuple[bool, list[str]]:
    """
    Compare response to golden fixture.

    Args:
        method_name: RPC method name
        response_data: Actual response data

    Returns:
        Tuple of (matches, list of differences)
    """
    # Import normalization from worktree_runner (shared logic)
    from tests.fixtures.golden_contracts.worktree_runner import normalize_response

    golden = load_golden(method_name)
    if golden is None:
        return False, [f"No golden fixture for {method_name}"]

    if not golden.get("success"):
        return False, [f"Golden fixture shows failure: {golden.get('error')}"]

    golden_response = golden["response"]
    actual_normalized = normalize_response(response_data)

    differences = []
    _compare_dicts(golden_response, actual_normalized, "", differences)

    return len(differences) == 0, differences


def _compare_dicts(
    expected: dict,
    actual: dict,
    path: str,
    differences: list[str],
):
    """
    Recursively compare two dicts and collect differences.
    """
    all_keys = set(expected.keys()) | set(actual.keys())

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in expected:
            differences.append(f"Extra key: {current_path}")
            continue

        if key not in actual:
            differences.append(f"Missing key: {current_path}")
            continue

        exp_val = expected[key]
        act_val = actual[key]

        # Skip normalized placeholders
        if isinstance(exp_val, str) and exp_val.startswith("<NORMALIZED"):
            continue

        if type(exp_val) != type(act_val):
            differences.append(f"Type mismatch at {current_path}: expected {type(exp_val).__name__}, got {type(act_val).__name__}")
            continue

        if isinstance(exp_val, dict):
            _compare_dicts(exp_val, act_val, current_path, differences)
        elif isinstance(exp_val, list):
            if len(exp_val) != len(act_val):
                differences.append(f"List length mismatch at {current_path}: expected {len(exp_val)}, got {len(act_val)}")
            else:
                for i, (e, a) in enumerate(zip(exp_val, act_val)):
                    if isinstance(e, dict):
                        _compare_dicts(e, a, f"{current_path}[{i}]", differences)
                    elif e != a and not (isinstance(e, str) and e.startswith("<NORMALIZED")):
                        differences.append(f"Value mismatch at {current_path}[{i}]: expected {e!r}, got {a!r}")
        elif exp_val != act_val:
            differences.append(f"Value mismatch at {current_path}: expected {exp_val!r}, got {act_val!r}")

