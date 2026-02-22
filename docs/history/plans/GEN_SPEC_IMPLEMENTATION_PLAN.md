# GEN/SPEC Constitution Implementation Plan

**Date**: 2026-02-01
**Goal**: Full constitution compliance - clean system with no legacy, no compat

---

## Overview

This plan addresses all violations identified in `GEN_SPEC_CONSTITUTION_REVIEW.md`. The primary focus is eliminating manual join/split operations and establishing a single execution choke point for spec→gen conversion.

---

## Phase 1: Eliminate Manual Join/Split (P0 - Critical)

**Constitution Reference**: §3.1 (Conversion API Law)

### Task 1.1: Fix src/qmatsuite/calculation/verification.py

**Location**: Line 102

**Before**:
```python
if "_" in step_type_str:
    step_type_gen = step_type_str.split("_", 1)[1]
else:
    step_type_gen = step_type_str
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from
step_type_gen = gen_from(step_type_str)
```

---

### Task 1.2: Fix src/qmatsuite/calculation/runner.py

**Location**: Lines 78-82

**Before**:
```python
if is_spec(step_type_spec):
    parts = step_type_spec.split("_", 1)
    if len(parts) == 2:
        engine_prefix, gen_type = parts
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from, prefix_from
if is_spec(step_type_spec):
    engine_prefix = prefix_from(step_type_spec)
    gen_type = gen_from(step_type_spec)
```

---

### Task 1.3: Fix src/qmatsuite/engines/pyscf/chain.py

**Location**: Line 27

**Before**:
```python
step_type_gen = gen_from(step_type_spec)
engine_prefix = step_type_spec.split("_", 1)[0] if "_" in step_type_spec else "pyscf"
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from, prefix_from, is_spec
step_type_gen = gen_from(step_type_spec)
engine_prefix = prefix_from(step_type_spec) if is_spec(step_type_spec) else "pyscf"
```

---

### Task 1.4: Fix src/qmatsuite/daemon/compat.py

**Location**: Line 737

**Before**:
```python
step["name"] = step.get("step_type_gen", step.get("step_type_spec", "").split("_", 1)[-1])
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from
spec_val = step.get("step_type_spec", "")
step["name"] = step.get("step_type_gen", gen_from(spec_val) if spec_val else "")
```

---

### Task 1.5: Fix src/qmatsuite/api/_mapping/dto_mapping.py

**Location**: Line 383

**Before**:
```python
if step_type_spec and "_" in step_type_spec:
    engine = step_type_spec.split("_")[0]
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import prefix_from, is_spec
if step_type_spec and is_spec(step_type_spec):
    engine = prefix_from(step_type_spec)
```

---

### Task 1.6: Fix src/qmatsuite/api/service.py

**Location**: Line 6966

**Before**:
```python
elif "_" in machine_step_type:
    engine_family = machine_step_type.split("_", 1)[0]
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import prefix_from, is_spec
elif is_spec(machine_step_type):
    engine_family = prefix_from(machine_step_type)
```

---

### Task 1.7: Fix src/qmatsuite/execution/reference_resolver.py

**Location**: Lines 61-65

**Before**:
```python
if is_spec(step_type_str):
    parts = step_type_str.split("_", 1)
    if len(parts) == 2:
        engine_prefix, gen_type = parts
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from, prefix_from
if is_spec(step_type_str):
    engine_prefix = prefix_from(step_type_str)
    gen_type = gen_from(step_type_str)
```

---

### Task 1.8: Fix src/qmatsuite/execution/vasp_staging.py

**Location**: Lines 57-60

**Before**:
```python
if is_spec(step_type_str):
    parts = step_type_str.split("_", 1)
    if len(parts) == 2:
        engine_prefix, gen_type = parts
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from, prefix_from
if is_spec(step_type_str):
    engine_prefix = prefix_from(step_type_str)
    gen_type = gen_from(step_type_str)
```

---

### Task 1.9: Fix src/qmatsuite/drivers/vasp/staging.py

**Location**: Lines 57-60

**Before**:
```python
if is_spec(step_type_str):
    parts = step_type_str.split("_", 1)
    if len(parts) == 2:
        engine_prefix, gen_type = parts
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import gen_from, prefix_from
if is_spec(step_type_str):
    engine_prefix = prefix_from(step_type_str)
    gen_type = gen_from(step_type_str)
```

---

## Phase 2: Add Gate for Manual Join/Split Detection (P0)

**Constitution Reference**: §13 (Gate: No Manual Join/Split)

### Task 2.1: Create tests/gates/test_no_manual_join_split.py

```python
"""
Gate: No Manual Join/Split

Constitution §3.1: All step type conversions MUST use canonical functions:
- spec_from(prefix, gen) for join
- gen_from(spec) for split (returns gen)
- prefix_from(spec) for split (returns prefix)

FORBIDDEN in runtime code:
- .split("_", 1) for step type parsing
- f"{prefix}_{gen}" for step type construction (outside step_type_convert.py)
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories to scan
SCAN_DIRS = [
    REPO_ROOT / "src",
]

# Files to skip (canonical implementation and tests)
ALLOWLIST_PATTERNS = [
    "src/qmatsuite/workflow/step_type_convert.py",  # Canonical implementation
    "src/qmatsuite/_vault/*",  # Legacy archive
    "tests/*",  # Tests may contain examples
]

def is_allowlisted(path: Path) -> bool:
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scan_for_manual_split(file_path: Path) -> List[Tuple[int, str]]:
    """Scan file for manual .split("_") calls in step type context."""
    violations = []
    try:
        content = file_path.read_text()
        lines = content.split('\n')

        # Pattern: .split("_" followed by ) or ,
        pattern = r'\.split\s*\(\s*["\']_'

        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                # Check if it's in step_type context
                if any(ctx in line.lower() for ctx in ['step_type', 'spec', 'gen_type', 'engine_prefix']):
                    violations.append((i, line.strip()))

    except Exception:
        pass

    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan all files for violations."""
    all_violations = []

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for file_path in scan_dir.rglob("*.py"):
            if is_allowlisted(file_path):
                continue

            violations = scan_for_manual_split(file_path)
            for line_num, line in violations:
                all_violations.append((file_path, line_num, line))

    return all_violations


class TestNoManualJoinSplit:
    """Gate: No manual join/split operations for step types."""

    def test_no_manual_split_for_step_types(self):
        """All step type parsing must use canonical functions."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== GATE: NO MANUAL JOIN/SPLIT VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for path, line_num, line in violations:
                rel_path = path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line_num} - {line}\n"
            report += "\n=== FIX: Use gen_from(), prefix_from() from step_type_convert.py ===\n"
            pytest.fail(report)
```

---

## Phase 3: Fix Tool Scripts (P1)

### Task 3.1: Update tools/generate_wannier90_demo.py comments

**Locations**: Lines 9, 11, 190

**Before**:
```python
# - w90_preproc step (wannier90.x -pp)
# - w90_run step (wannier90.x)
# w90_preproc and w90_run are already SPEC format
```

**After**:
```python
# - w90_wannierprep step (wannier90.x -pp)
# - w90_wannier step (wannier90.x)
# w90_wannierprep and w90_wannier are already SPEC format
```

### Task 3.2: Remove hardcoded mapping in tools/generate_wannier90_demo.py

**Location**: Lines 186-192

**Before**:
```python
gen_to_spec = {
    "scf": "qe_scf",
    "nscf": "qe_nscf",
    "pw2wannier90": "qe_pw2wannier90",
}
machine_type = gen_to_spec.get(step_type, step_type)
```

**After**:
```python
from qmatsuite.workflow.step_type_convert import spec_from, is_spec
if is_spec(step_type):
    machine_type = step_type  # Already SPEC
else:
    # Derive SPEC from GEN using engine prefix
    engine_prefix = "qe" if step_type in ("scf", "nscf", "pw2wannier") else "w90"
    machine_type = spec_from(engine_prefix, step_type)
```

---

## Phase 4: Centralize Execution Choke Point (P2)

**Constitution Reference**: §4.3

### Current Problem

Multiple files perform spec→gen conversion independently:
- `calculation/runner.py`
- `execution/reference_resolver.py`
- `execution/vasp_staging.py`
- `drivers/vasp/staging.py`

### Solution Design

Create a single `StepTypeUnpacker` utility that all execution code uses:

**New file**: `src/qmatsuite/execution/step_type_unpack.py`

```python
"""
Single choke point for spec→(prefix, gen) unpacking in execution layer.

Constitution §4.3: Runner/dispatch performs exactly ONE spec→(prefix, gen) "unpack"
at a SINGLE choke point before recipe lookup.
"""

from dataclasses import dataclass
from typing import Tuple

from qmatsuite.workflow.step_type_convert import gen_from, prefix_from, is_spec


@dataclass(frozen=True)
class UnpackedStepType:
    """Result of unpacking a SPEC step type."""
    spec: str
    prefix: str
    gen: str


def unpack_step_type(step_type_spec: str) -> UnpackedStepType:
    """
    Unpack SPEC step type to (prefix, gen).

    This is the ONLY permitted place where spec→gen conversion happens
    in the execution layer.

    Args:
        step_type_spec: SPEC step type (e.g., "qe_scf", "vasp_relax")

    Returns:
        UnpackedStepType with spec, prefix, and gen

    Raises:
        ValueError: If step_type_spec is not valid SPEC format
    """
    if not is_spec(step_type_spec):
        raise ValueError(
            f"Expected SPEC format (with underscore), got: '{step_type_spec}'. "
            f"Use step_type_spec from step.yaml, not step_type_gen."
        )

    return UnpackedStepType(
        spec=step_type_spec,
        prefix=prefix_from(step_type_spec),
        gen=gen_from(step_type_spec),
    )
```

### Migration

All files currently doing manual unpacking should import and use `unpack_step_type()`:

```python
from qmatsuite.execution.step_type_unpack import unpack_step_type

unpacked = unpack_step_type(step_type_spec)
engine_prefix = unpacked.prefix
gen_type = unpacked.gen
```

---

## Execution Checklist

### Phase 1 Tasks (Do First)
- [ ] Task 1.1: Fix calculation/verification.py
- [ ] Task 1.2: Fix calculation/runner.py
- [ ] Task 1.3: Fix engines/pyscf/chain.py
- [ ] Task 1.4: Fix daemon/compat.py
- [ ] Task 1.5: Fix api/_mapping/dto_mapping.py
- [ ] Task 1.6: Fix api/service.py
- [ ] Task 1.7: Fix execution/reference_resolver.py
- [ ] Task 1.8: Fix execution/vasp_staging.py
- [ ] Task 1.9: Fix drivers/vasp/staging.py

### Phase 2 Tasks
- [ ] Task 2.1: Create test_no_manual_join_split.py gate

### Phase 3 Tasks
- [ ] Task 3.1: Update generate_wannier90_demo.py comments
- [ ] Task 3.2: Remove hardcoded mapping in generate_wannier90_demo.py

### Phase 4 Tasks (Optional - Future)
- [ ] Create step_type_unpack.py
- [ ] Migrate all execution files to use unpack_step_type()

---

## Verification

After each phase, run:

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

All tests must pass, including:
- `tests/gates/test_no_manual_join_split.py` (new gate)
- `tests/gates/test_step_type_constitution.py`
- `tests/gates/test_step_type_declared_sets.py`
- `tests/gates/test_step_type_cross_assignment.py`

---

## Success Criteria

The implementation is complete when:

1. **Zero manual split operations** in src/ for step types
2. **Gate test passes** for no manual join/split
3. **All existing tests pass**
4. **No deprecated comments** referencing w90_preproc/w90_run
5. **No hardcoded mapping tables** outside canonical locations

---

**End of Implementation Plan**
