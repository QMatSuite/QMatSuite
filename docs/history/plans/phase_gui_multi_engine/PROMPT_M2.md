# M2: Remove Silent QE Fallbacks

## Scope

Eliminate all 10 locations where code silently defaults to `"qe"` when engine_family is unknown. Replace with hard errors or explicit UNDECIDED handling. Write a gate test to prevent regression.

## Prerequisites

M0 and M1 must be complete.

## Exact File List

### Modify

1. `src/qmatsuite/api/service.py` (5 locations: lines ~3182, ~3825, ~3921, ~6244, ~7267)
2. `src/qmatsuite/core/models.py` (1 location: line ~359)
3. `src/qmatsuite/core/templates.py` (1 location: line ~399)
4. `src/qmatsuite/frontends/cli/app.py` (1 location: line ~848)
5. `src/qmatsuite/cli/main.py` (2 locations: lines ~1289, ~1291)
6. `src/qmatsuite/workflow/templates.py` (1 location: line ~486)

### Create

7. `tests/gates/test_no_qe_fallback.py`

## Do NOT Touch

- `src/qmatsuite/drivers/` (driver code legitimately references "qe")
- `src/qmatsuite/daemon/server.py` (QE RPCs still exist, removed in M8)
- GUI files
- Demo files (already fixed in M1)
- `src/qmatsuite/core/driver_registry.py`

## Exact Instructions

### Step 1: Fix service.py (5 locations)

**Location F1 (~line 3182)**:
Find: `engine = step_spec.engine if step_spec else "qe"`
Replace with:
```python
if step_spec is None:
    from qmatsuite.workflow.step_type_convert import prefix_from
    engine = prefix_from(step_type_spec)
else:
    engine = step_spec.engine
```

**Location F2 (~line 3825)**:
Find: `engine_family = getattr(calc_model, 'engine_family', None) or "qe"`
Replace with:
```python
engine_family = getattr(calc_model, 'engine_family', None)
if engine_family is None:
    raise ValueError(
        f"Cannot add step '{step_type_gen}' to calculation without engine_family. "
        "Set engine_family on the calculation first."
    )
```

**Location F3 (~line 3921)**:
Find: `engine = step_spec.engine if step_spec else "qe"`
Replace with same pattern as F1:
```python
if step_spec is None:
    from qmatsuite.workflow.step_type_convert import prefix_from
    engine = prefix_from(step_type_spec)
else:
    engine = step_spec.engine
```

**Location F4 (~line 6244)**:
Find: `engine_family = "pyscf" if structure_kind == "molecule" else "qe"`
Replace with:
```python
# engine_family may be None (UNDECIDED state per Law EF1).
# Caller must provide engine_family; do not infer.
pass  # engine_family stays as-is (None or provided value)
```
Remove the entire `if engine_family is None:` block that sets this default.

**Location F5 (~line 7267)**:
Find: `def resolve_step_type_spec(step_type_gen: str, engine_family: str = "qe") -> str:`
Replace with:
```python
def resolve_step_type_spec(step_type_gen: str, engine_family: str) -> str:
```
Remove the default `= "qe"`. Then find all callers of `resolve_step_type_spec` and ensure they pass `engine_family` explicitly.

### Step 2: Fix models.py (~line 359)

Find the block where `engine_family = "qe"` is set as final default.
Replace with:
```python
# engine_family may remain None (UNDECIDED state per Law EF1)
```
Allow engine_family to stay None. Do NOT set a default.

### Step 3: Fix templates.py (~line 399)

Find: `calculation_data["engine_family"] = "qe"`
Replace with:
```python
if "engine_family" not in calculation_data or calculation_data.get("engine_family") is None:
    raise ValueError("engine_family is required for template instantiation")
```

### Step 4: Fix cli/app.py (~line 848)

Find: `engine_family = "qe"`
Replace with:
```python
engine_family = None  # Will be set by user or inferred from context
```
Ensure the CLI flow handles None engine_family gracefully (raises helpful error if needed for base-step operations).

### Step 5: Fix cli/main.py (~lines 1289, 1291)

Find: `engine_family = "qe"` and `engine_family = calculation_data.get("engine_family", "qe")`
Replace with:
```python
engine_family = calculation_data.get("engine_family") if calculation_data else None
```

### Step 6: Fix workflow/templates.py (~line 486)

Find: `engine_family = "qe"` (the fallback when engine_family is None)
Replace with:
```python
if engine_family is None:
    raise ValueError(
        "engine_family is required for workflow instantiation. "
        "Set engine_family on the calculation before instantiating a workflow."
    )
```

### Step 7: Write gate test

Create `tests/gates/test_no_qe_fallback.py`:

```python
"""
Gate: Law EF4 — No Silent QE Fallbacks.

No code outside drivers/qe/ may default engine_family to "qe".
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SCAN_DIRS = [REPO_ROOT / "src" / "qmatsuite"]

# Patterns that indicate a silent QE default
FALLBACK_PATTERNS = [
    (r'or\s+"qe"', 'or "qe"'),
    (r"or\s+'qe'", "or 'qe'"),
    (r'else\s+"qe"', 'else "qe"'),
    (r"else\s+'qe'", "else 'qe'"),
    (r'engine_family:\s*str\s*=\s*"qe"', 'engine_family default "qe"'),
    (r"engine_family:\s*str\s*=\s*'qe'", "engine_family default 'qe'"),
    (r'=\s*"qe"\s*#.*[Dd]efault', '= "qe" # default'),
]

SKIP_DIRS = {"drivers", "_vault", "__pycache__", ".venv"}


def _should_scan(path: Path) -> bool:
    parts = path.parts
    return not any(skip in parts for skip in SKIP_DIRS)


def test_no_silent_qe_fallbacks():
    """No silent QE defaults outside drivers/."""
    violations = []

    for scan_dir in SCAN_DIRS:
        for py_file in scan_dir.rglob("*.py"):
            if not _should_scan(py_file):
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            for lineno, line in enumerate(text.splitlines(), 1):
                # Skip comments
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue

                for pattern, description in FALLBACK_PATTERNS:
                    if re.search(pattern, line):
                        rel = py_file.relative_to(REPO_ROOT)
                        violations.append(f"  {rel}:{lineno}  {description}: {line.strip()}")

    assert not violations, (
        f"EF4 violation — silent QE fallbacks found ({len(violations)}):\n"
        + "\n".join(violations[:50])
    )
```

## Invariants to Preserve

- step.yaml stores ONLY step_type_spec (no changes to YAML schema)
- Existing tests that create calculations must be updated to pass engine_family
- UNDECIDED state (engine_family=None) is legal for calculation creation
- Workflow instantiation still requires DECIDED state
- Driver code in drivers/qe/ may legitimately use "qe" string

## Verifiers

```bash
# 1. Gate test passes
source .venv/bin/activate && python -m pytest tests/gates/test_no_qe_fallback.py -v

# 2. Manual verification
grep -rn 'or "qe"' src/qmatsuite/ --include="*.py" | grep -v drivers/ | grep -v _vault/
# Expected: empty

grep -rn 'else "qe"' src/qmatsuite/ --include="*.py" | grep -v drivers/ | grep -v _vault/
# Expected: empty

# 3. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT remove QE fallbacks from `drivers/qe/` (those are legitimate)
- Do NOT modify daemon/server.py QE RPC handlers (that's M8)
- Do NOT modify GUI files
- Do NOT change step_type_spec format or YAML schema
- Do NOT add engine_family inference logic (the whole point is to NOT infer)
- Do NOT introduce a new default engine (like defaulting to VASP instead)

## Expected Failure Modes

1. **Test failures from callers that relied on defaults**: Many tests create calculations without passing engine_family. They will break. You must update those tests to pass `engine_family="qe"` (or whatever engine they test).
2. **CLI commands that assumed QE**: The CLI may break for users who don't specify --engine. Consider adding a `--engine` flag with no default and a helpful error message.
3. **Template instantiation failures**: Workflow templates that don't pass engine_family. Trace the call chain and ensure engine_family flows through.
