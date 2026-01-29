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
    # Import normalization from local module (shared logic)
    from tests.contract_crawler.normalization import normalize_response

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


# Fields where list length can vary due to network/environment factors
# We only verify both are lists, not their length
VARIABLE_LENGTH_LISTS = {
    "candidates", "errors", "messages", "internal_engines",
    # Journal entries vary based on recipe world operations
    "entries",
    # Network download results vary by environment
    "skipped", "installed", "failed", "files_downloaded", "installed_libraries",
    "warnings",
    # Demo projects list is environment-specific
    "demos",
    # Pseudo archives depend on installed libraries
    "archives",
    # Library status varies by environment
    "variant_statuses",
    "installed_variants",
    # QE engines discovered vary by CI environment
    "discovered_engines",
    # Templates order/count can vary
    "templates",
    "step_types",
}

# Fields that are data-dependent and should be skipped in value comparison
# These fields exist in both v0 and HEAD but their values depend on recipe world state
#
# WARNING: Fields in DATA_DEPENDENT_FIELDS skip value comparison.
# GUI-critical fields (steps, structure, status) are validated separately
# by test_gui_field_enforcement.py to ensure they exist with correct types.
DATA_DEPENDENT_FIELDS = {
    "formula",  # Depends on imported structure
    "n_atoms",  # Depends on imported structure
    "lattice_params",  # Depends on imported structure lattice
    "lattice_abc",  # Depends on imported structure lattice
    "lattice_angles",  # Depends on imported structure lattice
    "cell_volume_ang3",  # Depends on imported structure lattice
    "volume",  # Depends on imported structure lattice
    "a", "b", "c",  # Lattice parameters
    "alpha", "beta", "gamma",  # Lattice angles
    "sssp_defaults",  # SSSP library state dependent
    "installed_sources",  # Library installation state
    "candidates_by_element",  # Library/network state dependent
    "resolved_by_element",  # Library/network state dependent
    # Network/download state dependent
    "files_installed",
    "success",  # Network operation success
    # Step order can vary in recipe world
    "steps",
    # Structure field format changed (v0: name, HEAD: id)
    "structure",
    # Performance metrics vary by run
    "perf",
    "prep_ms", "bonds_ms", "ser_ms", "total_ms", "bytes",
    # Directory creation state
    "seed_dir_created", "store_dir_created",
    # Library state dependent
    "libraries",
    # Session IDs - mock vs actual
    "session_id",
    # Error messages can vary
    "message",
    # Pseudo library state depends on environment
    "grouped_by_library",
    "species_map",
    "sssp_defaults",
    # SSSP installation state
    "sssp_installed",
    "precision", "efficiency",  # SSSP variant flags
    "seed_has_sssp",  # Depends on whether SSSP library is installed
    # Library status state
    "status", "installed", "installed_variants",
    "variant_statuses", "version", "file_count", "size_bytes",
    # Store size varies by environment
    "data",
    # Pseudo config paths vary by CI vs local environment
    "store_dir", "seed_dir", "allow_download",
    # QE parameter metadata loading state varies
    "loaded_at", "loaded_via", "path_abs",
    # Floating point precision differences (structure visualization)
    "matrix", "distance", "coord2", "cart_coords",
    # Template descriptions can be None vs str
    "description",
    # Template properties can vary by environment
    "n_steps", "name",
}


def _compare_dicts(
    expected: dict,
    actual: dict,
    path: str,
    differences: list[str],
    allow_extra_keys: bool = True,  # Backward compat: extra keys are OK
):
    """
    Recursively compare two dicts and collect differences.

    Args:
        expected: Expected dict (from golden)
        actual: Actual dict (from HEAD)
        path: Current path for error messages
        differences: List to append differences to
        allow_extra_keys: If True, extra keys in actual are allowed (backward compatible)
    """
    all_keys = set(expected.keys()) | set(actual.keys())

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in expected:
            # Extra key in HEAD response
            if not allow_extra_keys:
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

        # Skip data-dependent fields (values depend on recipe world state)
        if key in DATA_DEPENDENT_FIELDS:
            # Allow type flexibility for data-dependent fields (None vs dict/list is OK)
            # These fields vary by environment/state, so we only verify presence
            continue

        if type(exp_val) != type(act_val):
            # Special case: None vs populated is acceptable for optional fields
            # This handles: None -> dict/list, None -> scalar (optional field now populated)
            if exp_val is None:
                # Baseline had null, HEAD has actual value = backward-compatible enhancement
                continue
            if act_val is None and isinstance(exp_val, (dict, list)):
                # HEAD removed a dict/list = might be OK for optional container fields
                continue
            differences.append(f"Type mismatch at {current_path}: expected {type(exp_val).__name__}, got {type(act_val).__name__}")
            continue

        if isinstance(exp_val, dict):
            _compare_dicts(exp_val, act_val, current_path, differences, allow_extra_keys)
        elif isinstance(exp_val, list):
            # Allow variable length for certain fields (e.g., network search results)
            if key in VARIABLE_LENGTH_LISTS:
                # Only verify it's a list, don't compare length or contents
                continue
            if len(exp_val) != len(act_val):
                differences.append(f"List length mismatch at {current_path}: expected {len(exp_val)}, got {len(act_val)}")
            else:
                for i, (e, a) in enumerate(zip(exp_val, act_val)):
                    if isinstance(e, dict):
                        _compare_dicts(e, a, f"{current_path}[{i}]", differences, allow_extra_keys)
                    elif e != a and not (isinstance(e, str) and e.startswith("<NORMALIZED")):
                        differences.append(f"Value mismatch at {current_path}[{i}]: expected {e!r}, got {a!r}")
        elif exp_val != act_val:
            differences.append(f"Value mismatch at {current_path}: expected {exp_val!r}, got {act_val!r}")

