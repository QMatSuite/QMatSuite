# ORCA Execution MVP: Test-Driven Implementation Plan

**Date**: 2026-01-13
**Status**: COMPLETE
**Scope**: ORCA engine MVP with SCF + TD support

**Final Test Results**:
- ORCA Unit Tests: 66 passed
- ORCA Integration Tests: 18 passed (not skipped)
- PySCF Phase3C Tests: 5 passed (regression fixed)
- **Total: 89 tests passed**

---

## Hotfix: PySCF Regression + ORCA Integration Audit

**Date**: 2026-01-13 (Hotfix Phase)
**Priority**: CRITICAL - Must complete before marking ORCA MVP as done

### PySCF MP2 Regression Fix
- [x] Reproduce PySCF MP2 test failure locally (installed PySCF 2.11.0)
- [x] Identify root cause in chain_execution.py MP2 energy extraction (line 342: float(mp2_corr) fails with arrays)
- [x] Fix MP2 correlation energy extraction to handle numpy arrays/scalars (added robust extraction code)
- [x] Verify test_t4_runstep_mp2_chain_execution passes
- [x] Run PySCF Phase3C integration tests to ensure no other regressions (5/5 passed)

### ORCA Integration Audit (Non-Skipped Execution)
- [x] Update ORCA integration test fixtures to use resolver (not env var only)
- [x] Run ORCA binary sanity check manually (bundled ORCA detected at .qmatsuite/engines/orca/)
- [x] Run ORCA integration tests with bundled binary (must not skip)
- [x] Save full pytest output to docs/plans/_logs/orca_integration_20260113_1800.txt
- [x] Update this plan with test results and log reference
- [x] Verify all 18 ORCA integration tests pass (not skip) - **18/18 PASSED in 9.15s**

### Final Verification
- [x] PySCF regression test passes (5/5 PySCF Phase3C tests passed)
- [x] ORCA integration tests run and pass (not skip) (18/18 ORCA integration tests passed)
- [x] Update plan status to COMPLETE with final test counts

---

## Work Tracking Checklist

### Preflight Checks
- [x] Preflight: Activate venv and confirm python/pytest use repo venv
- [x] Preflight: Run a QUICK pytest smoke subset (confirm baseline green)
- [x] Preflight: ORCA sanity run (bundled ORCA water.inp test)

### Phase 0: Manual ORCA Sanity
- [x] Phase 0: Create test input file and run ORCA manually
- [x] Phase 0: Verify outputs (water.out, water.gbw, water.property.txt)

### Phase 1: Property Parser
- [x] Phase 1.1: Create test fixtures directory
- [x] Phase 1.2: Write property parser tests (TDD)
- [x] Phase 1.3: Implement property parser
- [x] Phase 1.4: Add TDDFT property parsing

### Phase 2: Chain Detection
- [x] Phase 2.1: Write chain detection tests (TDD)
- [x] Phase 2.2: Implement QCChain and chain detection

### Phase 3: Input Compiler
- [x] Phase 3.1: Write input compiler tests (TDD)
- [x] Phase 3.2: Implement ORCA input compiler

### Phase 4: ORCA Engine Core
- [x] Phase 4.1: Write ORCA engine tests
- [x] Phase 4.2: Implement ORCA path resolver
- [x] Phase 4.3: Implement ORCA engine

### Phase 5: Integration Tests
- [x] Phase 5.1: Create integration test directory
- [x] Phase 5.2: Write integration tests
- [x] Phase 5.3: Run integration tests with bundled ORCA (10 passed)

### Phase 6: Step Type Registration
- [x] Phase 6.1: Add ORCA step types to registry
- [x] Phase 6.2: Add ORCA materialization
- [x] Phase 6.3: Test registration

### Phase 7: Engine Registration
- [x] Phase 7.1: Update engine registry with ORCA
- [x] Phase 7.2: Test engine registration

### System Integration Tests
- [x] Add system-level integration test via engine API
- [x] Verify chain folder outputs under calc/raw/chains
- [x] Verify manifest-like tracking (chain-level done)
- [x] Verify energy/TDDFT extraction pipeline (8 tests passed)

---

## Overview

This document provides a **step-by-step, test-driven implementation plan** for ORCA engine MVP. Each step ends with:
- Exact files to edit/create
- Exact functions/classes to add/change
- Exact pytest command(s) to run
- What tests should pass / new tests to add

**Test Philosophy**:
- TDD where possible: write test first, then implementation
- Run `pytest` continuously during implementation
- Unit tests require NO ORCA binary
- Integration tests require bundled ORCA (gated by env var)

---

## Prerequisites

### Bundled ORCA Location
```
/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
```

### Environment Variable for Integration Tests
```bash
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
```

### Test Markers
```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (require ORCA binary)",
    "orca: marks tests specific to ORCA engine",
]
```

---

## Phase 0: ORCA Sanity Check (Manual)

**Goal**: Verify bundled ORCA works before writing any code.

### Step 0.1: Create Test Input File

**Action**: Manually create a minimal ORCA input file.

```bash
mkdir -p /tmp/orca_sanity
cd /tmp/orca_sanity
```

Create `water.inp`:
```
# QMatSuite ORCA sanity test
! HF def2-SVP

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

### Step 0.2: Run ORCA Manually

```bash
cd /tmp/orca_sanity
/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca water.inp > water.out 2>&1
```

### Step 0.3: Verify Outputs

**Check**:
```bash
# Should exist:
ls -la water.out water.gbw water.property.txt

# Check for success:
grep "FINAL SINGLE POINT ENERGY" water.out

# Check property file:
head -50 water.property.txt
```

**Expected**: Files exist, energy printed, no errors.

### Step 0.4: Document Environment Requirements

If any `LD_LIBRARY_PATH` or `DYLD_LIBRARY_PATH` issues occur, document them here.

**Checkpoint 0**: Manual ORCA execution works. Proceed to Phase 1.

---

## Phase 1: Test Infrastructure + Property Parser

**Goal**: Set up test infrastructure and implement property.txt parser (TDD).

### Step 1.1: Create Test Fixtures Directory

**Files to create**:
```
tests/fixtures/orca/
  __init__.py
  water_scf.property.txt      # Sample SCF property file
  water_scf_td.property.txt   # Sample SCF+TD property file
  water_scf.out               # Sample ORCA output
```

**Action**: Copy the property.txt from Step 0.3 to fixtures.

```bash
mkdir -p tests/fixtures/orca
cp /tmp/orca_sanity/water.property.txt tests/fixtures/orca/water_scf.property.txt
cp /tmp/orca_sanity/water.out tests/fixtures/orca/water_scf.out
```

### Step 1.2: Write Property Parser Tests (TDD - Test First)

**File to create**: `tests/unit/orca/test_property_parser.py`

```python
"""Unit tests for ORCA property.txt parser."""
import pytest
from pathlib import Path

# Will import after implementation
# from quantumvitas.engines.orca.property_parser import parse_orca_property_txt


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "orca"


class TestPropertyParser:
    """Tests for property.txt parsing."""

    def test_parse_scf_energy(self):
        """Parse SCF energy from property file."""
        from quantumvitas.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "SCF_Energy" in result or "Total_Energy" in result
        energy = result.get("SCF_Energy") or result.get("Total_Energy")
        assert isinstance(energy, float)
        assert energy < 0  # Energy should be negative

    def test_parse_property_txt_string(self):
        """Parse property content from string."""
        from quantumvitas.engines.orca.property_parser import parse_property_txt_string

        content = '''
$SCF_Energy
 Geometry_Index                                    0
 Prop_Index                                        1
-76.02657856
$End
'''
        result = parse_property_txt_string(content)

        assert "SCF_Energy" in result
        assert abs(result["SCF_Energy"] - (-76.02657856)) < 1e-6

    def test_parse_array_property(self):
        """Parse array-type property (like orbital energies)."""
        from quantumvitas.engines.orca.property_parser import parse_property_txt_string

        content = '''
$Orbital_Energies
 Geometry_Index                                    0
 Prop_Index                                        1
 Number_of_Orbitals                                5
  -20.5234  -1.3456  -0.5678  0.1234  0.5678
$End
'''
        result = parse_property_txt_string(content)

        assert "Orbital_Energies" in result
        assert len(result["Orbital_Energies"]) == 5

    def test_missing_file_raises(self):
        """Missing file should raise FileNotFoundError."""
        from quantumvitas.engines.orca.property_parser import parse_orca_property_txt

        with pytest.raises(FileNotFoundError):
            parse_orca_property_txt(Path("/nonexistent/file.property.txt"))

    def test_empty_file_returns_empty_dict(self):
        """Empty file should return empty dict."""
        from quantumvitas.engines.orca.property_parser import parse_property_txt_string

        result = parse_property_txt_string("")
        assert result == {}
```

**Pytest command** (expect failures - tests written before implementation):
```bash
pytest tests/unit/orca/test_property_parser.py -v
# Expected: ImportError or failures (implementation not yet written)
```

### Step 1.3: Implement Property Parser

**Files to create**:
```
src/quantumvitas/engines/orca/__init__.py
src/quantumvitas/engines/orca/property_parser.py
```

**File**: `src/quantumvitas/engines/orca/__init__.py`
```python
"""ORCA engine module."""
```

**File**: `src/quantumvitas/engines/orca/property_parser.py`
```python
"""Parser for ORCA .property.txt files."""
import re
from pathlib import Path
from typing import Any, Dict, List, Union


# Regex to match property blocks: $PropertyName ... $End
PROPERTY_BLOCK_RE = re.compile(
    r'\$(\w+)\s*\n(.*?)\$End',
    re.DOTALL | re.IGNORECASE
)

# Regex to match numeric values (including scientific notation)
FLOAT_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')


def parse_orca_property_txt(path: Path) -> Dict[str, Any]:
    """
    Parse ORCA .property.txt file.

    Args:
        path: Path to .property.txt file

    Returns:
        Dictionary of property_name -> value

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Property file not found: {path}")

    content = path.read_text()
    return parse_property_txt_string(content)


def parse_property_txt_string(content: str) -> Dict[str, Any]:
    """
    Parse property.txt content from string.

    Args:
        content: Property file content

    Returns:
        Dictionary of property_name -> value
    """
    if not content.strip():
        return {}

    properties: Dict[str, Any] = {}

    for match in PROPERTY_BLOCK_RE.finditer(content):
        prop_name = match.group(1)
        block_content = match.group(2)

        value = _parse_block_content(block_content)
        if value is not None:
            properties[prop_name] = value

    return properties


def _parse_block_content(content: str) -> Union[float, List[float], str, None]:
    """
    Parse the content of a property block.

    Handles:
    - Single float values
    - Arrays of floats
    - String values
    """
    lines = content.strip().split('\n')

    # Skip metadata lines (Geometry_Index, Prop_Index, etc.)
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip lines that look like metadata (contain keywords)
        if any(kw in stripped for kw in ['Geometry_Index', 'Prop_Index', 'Number_of']):
            continue
        data_lines.append(stripped)

    if not data_lines:
        return None

    # Try to parse as numbers
    all_numbers: List[float] = []
    for line in data_lines:
        numbers = FLOAT_RE.findall(line)
        all_numbers.extend(float(n) for n in numbers)

    if len(all_numbers) == 1:
        return all_numbers[0]
    elif len(all_numbers) > 1:
        return all_numbers
    else:
        # Return as string if no numbers found
        return '\n'.join(data_lines) if data_lines else None
```

**Pytest command** (tests should now pass):
```bash
pytest tests/unit/orca/test_property_parser.py -v
# Expected: All tests pass
```

**Checkpoint 1.3**: Property parser implemented and tests pass.

### Step 1.4: Add TDDFT Property Parsing

**Update fixture**: Add a TDDFT property file (run ORCA with TDDFT or create manually).

For now, create synthetic fixture `tests/fixtures/orca/water_scf_td.property.txt`:
```
$SCF_Energy
 Geometry_Index                                    0
 Prop_Index                                        1
-76.02657856
$End

$TDDFT_Excitation_Energies
 Geometry_Index                                    0
 Prop_Index                                        1
 Number_of_Roots                                   3
  0.31245  0.37891  0.42156
$End

$TDDFT_Oscillator_Strengths
 Geometry_Index                                    0
 Prop_Index                                        1
 Number_of_Roots                                   3
  0.0234  0.0567  0.0123
$End
```

**Add test**: `tests/unit/orca/test_property_parser.py`
```python
def test_parse_tddft_excitations(self):
    """Parse TDDFT excitation energies."""
    from quantumvitas.engines.orca.property_parser import parse_orca_property_txt

    result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")

    assert "TDDFT_Excitation_Energies" in result
    assert len(result["TDDFT_Excitation_Energies"]) == 3

def test_parse_tddft_oscillator_strengths(self):
    """Parse TDDFT oscillator strengths."""
    from quantumvitas.engines.orca.property_parser import parse_orca_property_txt

    result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")

    assert "TDDFT_Oscillator_Strengths" in result
    assert len(result["TDDFT_Oscillator_Strengths"]) == 3
```

**Pytest command**:
```bash
pytest tests/unit/orca/test_property_parser.py -v
# Expected: All tests pass
```

**Checkpoint 1**: Property parser complete with SCF and TDDFT support.

---

## Phase 2: Chain Detection and Key Derivation

**Goal**: Implement chain detection (identify SCF roots) and chain key derivation.

### Step 2.1: Write Chain Detection Tests (TDD)

**File to create**: `tests/unit/orca/test_chain_detection.py`

```python
"""Unit tests for QC chain detection."""
import pytest
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str


class TestChainDetection:
    """Tests for chain detection logic."""

    def test_single_scf_forms_one_chain(self):
        """Single SCF step forms one chain."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [MockStep(id="s1", public_type="scf", step_type="orca_scf")]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"
        assert len(chains[0].downstream) == 0

    def test_scf_td_forms_one_chain(self):
        """SCF + TD forms one chain with TD as downstream."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"
        assert len(chains[0].downstream) == 1
        assert chains[0].downstream[0].id == "s2"

    def test_two_scf_forms_two_chains(self):
        """Two SCF steps form two separate chains."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
            MockStep(id="s3", public_type="scf", step_type="orca_scf"),
            MockStep(id="s4", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 2
        assert chains[0].scf_root.id == "s1"
        assert chains[1].scf_root.id == "s3"

    def test_hf_also_starts_chain(self):
        """HF step also starts a new chain (like SCF)."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="hf", step_type="orca_hf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"

    def test_chain_key_derivation(self):
        """Chain key derived from step types."""
        from quantumvitas.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[MockStep(id="s2", public_type="td", step_type="orca_td")],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf_td"

    def test_chain_key_scf_only(self):
        """Chain key for SCF-only chain."""
        from quantumvitas.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf"

    def test_chain_key_collision_resolution(self):
        """Multiple chains with same structure get unique keys."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
            MockStep(id="s3", public_type="scf", step_type="orca_scf"),
            MockStep(id="s4", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert chains[0].key == "chain01_scf_td"
        assert chains[1].key == "chain02_scf_td"


class TestPartialChain:
    """Tests for partial chain extraction (for Run Step)."""

    def test_partial_chain_to_target(self):
        """Extract partial chain from SCF root to target."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[
                MockStep(id="s2", public_type="td", step_type="orca_td"),
                MockStep(id="s3", public_type="freq", step_type="orca_freq"),
            ],
            key="chain01_scf_td_freq",
        )

        partial = chain.to_partial_chain(target_step_id="s2")

        assert partial.scf_root.id == "s1"
        assert len(partial.downstream) == 1
        assert partial.downstream[0].id == "s2"

    def test_partial_chain_to_scf_root(self):
        """Partial chain to SCF root includes only SCF."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[MockStep(id="s2", public_type="td", step_type="orca_td")],
            key="chain01_scf_td",
        )

        partial = chain.to_partial_chain(target_step_id="s1")

        assert partial.scf_root.id == "s1"
        assert len(partial.downstream) == 0

    def test_partial_chain_invalid_target_raises(self):
        """Invalid target step raises ValueError."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[],
            key="chain01_scf",
        )

        with pytest.raises(ValueError):
            chain.to_partial_chain(target_step_id="nonexistent")
```

**Pytest command** (expect failures):
```bash
pytest tests/unit/orca/test_chain_detection.py -v
# Expected: ImportError (implementation not yet written)
```

### Step 2.2: Implement QCChain and Chain Detection

**File to create**: `src/quantumvitas/engine/qc_engine_base.py`

```python
"""Generalized QC engine base with chain detection."""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, Sequence


class StepLike(Protocol):
    """Protocol for step-like objects."""
    id: str
    public_type: str
    step_type: str


# Step types that start a new chain (SCF roots)
SCF_ROOT_TYPES = {"scf", "hf"}


@dataclass
class QCChain:
    """
    Represents a dependency chain rooted at an SCF step.

    All downstream steps depend on the SCF root's wavefunction.
    """
    scf_root: Any  # StepLike
    downstream: List[Any] = field(default_factory=list)  # List[StepLike]
    key: str = ""

    @property
    def all_steps(self) -> List[Any]:
        """Return all steps in chain order."""
        return [self.scf_root] + self.downstream

    def to_partial_chain(self, target_step_id: str) -> "QCChain":
        """
        Extract partial chain from SCF root to target step (inclusive).

        Args:
            target_step_id: ID of target step

        Returns:
            New QCChain containing only steps up to target

        Raises:
            ValueError: If target not in chain
        """
        # Check if target is SCF root
        if self.scf_root.id == target_step_id:
            return QCChain(
                scf_root=self.scf_root,
                downstream=[],
                key=self.key,
            )

        # Find target in downstream
        partial_downstream = []
        found = False
        for step in self.downstream:
            partial_downstream.append(step)
            if step.id == target_step_id:
                found = True
                break

        if not found:
            raise ValueError(f"Step {target_step_id} not found in chain {self.key}")

        return QCChain(
            scf_root=self.scf_root,
            downstream=partial_downstream,
            key=self.key,
        )


def detect_chains(steps: Sequence[Any]) -> List[QCChain]:
    """
    Detect chains from a sequence of steps.

    Chains are separated by SCF/HF root steps. Each chain starts with
    an SCF root and includes all subsequent steps until the next SCF root.

    Args:
        steps: Sequence of step-like objects

    Returns:
        List of QCChain objects with keys assigned
    """
    if not steps:
        return []

    chains: List[QCChain] = []
    current_chain: Optional[QCChain] = None

    for step in steps:
        if step.public_type in SCF_ROOT_TYPES:
            # Start a new chain
            if current_chain is not None:
                chains.append(current_chain)
            current_chain = QCChain(scf_root=step, downstream=[])
        else:
            # Add to current chain (if exists)
            if current_chain is not None:
                current_chain.downstream.append(step)
            # else: orphan step before first SCF (error case, ignore for now)

    # Don't forget the last chain
    if current_chain is not None:
        chains.append(current_chain)

    # Assign keys to all chains
    for i, chain in enumerate(chains):
        chain.key = derive_chain_key(chain, chain_index=i + 1)

    return chains


def derive_chain_key(chain: QCChain, chain_index: int) -> str:
    """
    Derive human-readable chain key from step sequence.

    Format: chain{NN}_{step1}_{step2}_...

    Examples:
        [scf] -> "chain01_scf"
        [scf, td] -> "chain01_scf_td"
        [hf, mp2] -> "chain01_hf_mp2"

    Args:
        chain: QCChain object
        chain_index: 1-based index for this chain

    Returns:
        Chain key string
    """
    step_types = [chain.scf_root.public_type]
    step_types.extend(step.public_type for step in chain.downstream)

    base_key = "_".join(step_types)
    return f"chain{chain_index:02d}_{base_key}"
```

**Pytest command**:
```bash
pytest tests/unit/orca/test_chain_detection.py -v
# Expected: All tests pass
```

**Checkpoint 2**: Chain detection and key derivation complete.

---

## Phase 3: ORCA Input Compiler

**Goal**: Implement single-job ORCA input generation (no $new_job).

### Step 3.1: Write Input Compiler Tests (TDD)

**File to create**: `tests/unit/orca/test_input_compiler.py`

```python
"""Unit tests for ORCA input compiler."""
import pytest
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str
    parameters: Dict[str, Any]


@dataclass
class MockMolecule:
    """Mock molecule for testing."""
    atoms: str = """O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200"""
    charge: int = 0
    multiplicity: int = 1


class TestORCAInputCompiler:
    """Tests for ORCA input file generation."""

    def test_scf_only_input(self):
        """Generate input for SCF-only chain."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "! B3LYP def2-SVP" in input_text
        assert "* xyz 0 1" in input_text
        assert "O   0.000000" in input_text
        assert "$new_job" not in input_text  # NO multi-job

    def test_scf_td_fusion(self):
        """Generate fused input for SCF + TD chain."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 5, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "! B3LYP def2-SVP" in input_text
        assert "%tddft" in input_text
        assert "NRoots 5" in input_text
        assert "TDA true" in input_text
        assert "* xyz 0 1" in input_text
        assert "$new_job" not in input_text  # NO multi-job

    def test_hf_input(self):
        """Generate input for HF calculation."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        hf_step = MockStep(
            id="s1",
            public_type="hf",
            step_type="orca_hf",
            parameters={"basis": "def2-TZVP"},
        )
        chain = QCChain(scf_root=hf_step, downstream=[], key="chain01_hf")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "! HF def2-TZVP" in input_text
        assert "* xyz 0 1" in input_text

    def test_tightscf_added(self):
        """TightSCF should be added for reliable convergence."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "TightSCF" in input_text

    def test_noautostart_when_fresh(self):
        """NoAutoStart keyword added when fresh=True."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule(), fresh=True)

        assert "NoAutoStart" in input_text

    def test_pal_block_with_nprocs(self):
        """Parallelism block added when nprocs specified."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP", "nprocs": 4},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "%pal nprocs 4 end" in input_text

    def test_chain_comment_header(self):
        """Input should have chain key in comment."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "# Chain: chain01_scf" in input_text
```

**Pytest command** (expect failures):
```bash
pytest tests/unit/orca/test_input_compiler.py -v
# Expected: ImportError
```

### Step 3.2: Implement ORCA Input Compiler

**File to create**: `src/quantumvitas/engines/orca/input_compiler.py`

```python
"""ORCA input file compiler - single-job fusion."""
from typing import Any, Dict, List, Optional, Protocol, Set


class MoleculeLike(Protocol):
    """Protocol for molecule-like objects."""
    atoms: str
    charge: int
    multiplicity: int


class ORCAInputCompiler:
    """
    Compiles a QCChain into a single ORCA input file.

    MVP: No $new_job, single job with fused keywords/blocks.
    """

    def compile(
        self,
        chain: Any,  # QCChain
        molecule: MoleculeLike,
        fresh: bool = False,
        nprocs: Optional[int] = None,
    ) -> str:
        """
        Compile chain to ORCA input string.

        Args:
            chain: QCChain to compile
            molecule: Molecule with atoms, charge, multiplicity
            fresh: If True, add NoAutoStart
            nprocs: Number of processors (overrides step params)

        Returns:
            ORCA input file content as string
        """
        keywords: Set[str] = set()
        blocks: Dict[str, str] = {}

        # Process SCF root
        scf_params = chain.scf_root.parameters
        self._process_scf_step(chain.scf_root, keywords, blocks)

        # Process downstream steps
        for step in chain.downstream:
            if step.public_type == "td":
                self._process_td_step(step, blocks)
            # Future: freq, nmr, mp2, etc.

        # Add common keywords
        keywords.add("TightSCF")
        if fresh:
            keywords.add("NoAutoStart")

        # Handle nprocs
        effective_nprocs = nprocs or scf_params.get("nprocs")
        if effective_nprocs:
            blocks["pal"] = f"nprocs {effective_nprocs}"

        # Format final input
        return self._format_input(
            chain_key=chain.key,
            keywords=keywords,
            blocks=blocks,
            molecule=molecule,
        )

    def _process_scf_step(
        self,
        step: Any,
        keywords: Set[str],
        blocks: Dict[str, str],
    ) -> None:
        """Process SCF/HF step parameters."""
        params = step.parameters

        # Method/functional
        if step.public_type == "hf":
            keywords.add("HF")
        else:
            functional = params.get("functional", "B3LYP")
            keywords.add(functional)

        # Basis set
        basis = params.get("basis", "def2-SVP")
        keywords.add(basis)

        # Additional SCF keywords
        if params.get("ri", False):
            keywords.add("RI")
        if params.get("rijcosx", False):
            keywords.add("RIJCOSX")

    def _process_td_step(
        self,
        step: Any,
        blocks: Dict[str, str],
    ) -> None:
        """Process TDDFT step parameters."""
        params = step.parameters

        lines = []
        nroots = params.get("nroots", 5)
        lines.append(f"  NRoots {nroots}")

        tda = params.get("tda", True)
        lines.append(f"  TDA {'true' if tda else 'false'}")

        if "triplets" in params:
            lines.append(f"  Triplets {'true' if params['triplets'] else 'false'}")

        blocks["tddft"] = "\n".join(lines)

    def _format_input(
        self,
        chain_key: str,
        keywords: Set[str],
        blocks: Dict[str, str],
        molecule: MoleculeLike,
    ) -> str:
        """Format final ORCA input string."""
        lines: List[str] = []

        # Header comment
        lines.append(f"# Chain: {chain_key}")
        lines.append("# Generated by QMatSuite")
        lines.append("")

        # Keywords line
        keyword_str = " ".join(sorted(keywords))
        lines.append(f"! {keyword_str}")
        lines.append("")

        # Blocks (except pal which is special)
        if "pal" in blocks:
            lines.append(f"%pal {blocks['pal']} end")
            lines.append("")

        for block_name, block_content in blocks.items():
            if block_name == "pal":
                continue
            lines.append(f"%{block_name}")
            lines.append(block_content)
            lines.append("end")
            lines.append("")

        # Coordinates
        lines.append(f"* xyz {molecule.charge} {molecule.multiplicity}")
        lines.append(molecule.atoms)
        lines.append("*")

        return "\n".join(lines)
```

**Pytest command**:
```bash
pytest tests/unit/orca/test_input_compiler.py -v
# Expected: All tests pass
```

**Checkpoint 3**: Input compiler complete with SCF + TD fusion.

---

## Phase 4: ORCA Engine Core

**Goal**: Implement ORCAEngine with path resolution and execution.

### Step 4.1: Write ORCA Engine Tests

**File to create**: `tests/unit/orca/test_orca_engine.py`

```python
"""Unit tests for ORCA engine (no binary required)."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestORCAEngine:
    """Tests for ORCA engine initialization and setup."""

    def test_engine_creation(self):
        """Engine can be created with explicit path."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            engine = ORCAEngine(orca_bin=Path("/fake/orca"))
            assert engine is not None

    def test_engine_probe_with_binary(self):
        """Engine probe returns True when binary exists."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="ORCA 6.1.1")
                engine = ORCAEngine(orca_bin=Path("/fake/orca"))
                available, version = engine.probe()
                assert available is True

    def test_command_building(self):
        """Test ORCA command construction."""
        from quantumvitas.engine.orca_engine import ORCAEngine

        with patch.object(Path, 'exists', return_value=True):
            engine = ORCAEngine(orca_bin=Path("/fake/orca"))
            cmd = engine._build_command(Path("/work/chain01_scf.inp"))

            assert cmd[0] == "/fake/orca"
            assert "chain01_scf.inp" in cmd[1]


class TestORCAPathResolution:
    """Tests for ORCA path resolution."""

    def test_bundled_path_found(self):
        """Bundled ORCA path is resolved correctly."""
        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin_dir

        # This test checks the actual bundled location
        try:
            path = resolve_orca_bin_dir()
            assert path.exists()
            assert (path / "orca").exists()
        except RuntimeError:
            pytest.skip("Bundled ORCA not available")

    def test_missing_orca_raises(self):
        """Missing ORCA raises RuntimeError."""
        from quantumvitas.core.engines.orca_resolver import _resolve_orca_at_path

        with pytest.raises(RuntimeError):
            _resolve_orca_at_path(Path("/nonexistent/path"))
```

**File to create**: `tests/unit/orca/__init__.py`
```python
"""ORCA unit tests."""
```

### Step 4.2: Implement ORCA Path Resolver

**File to create**: `src/quantumvitas/core/engines/orca_resolver.py`

```python
"""ORCA path resolution."""
from pathlib import Path
from typing import Optional


# MVP: Hardcoded bundled location
BUNDLED_ORCA_DIR = Path.home() / ".qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411"


def resolve_orca_bin_dir() -> Path:
    """
    Resolve ORCA binary directory.

    MVP: Return bundled location if exists.
    Future: Implement full two-state resolution like QE.

    Returns:
        Path to ORCA directory containing 'orca' executable

    Raises:
        RuntimeError: If ORCA not found
    """
    # Check bundled location
    if BUNDLED_ORCA_DIR.exists():
        orca_binary = BUNDLED_ORCA_DIR / "orca"
        if orca_binary.is_file():
            return BUNDLED_ORCA_DIR

    raise RuntimeError(
        f"ORCA not found at bundled location: {BUNDLED_ORCA_DIR}\n"
        "Ensure ORCA is installed or set QMATSUITE_ORCA_BIN environment variable."
    )


def _resolve_orca_at_path(path: Path) -> Path:
    """
    Verify ORCA exists at given path.

    Args:
        path: Directory to check

    Returns:
        Validated path

    Raises:
        RuntimeError: If ORCA not found at path
    """
    if not path.exists():
        raise RuntimeError(f"ORCA directory not found: {path}")

    orca_binary = path / "orca"
    if not orca_binary.is_file():
        raise RuntimeError(f"ORCA binary not found at: {orca_binary}")

    return path
```

### Step 4.3: Implement ORCA Engine

**File to create**: `src/quantumvitas/engine/orca_engine.py`

```python
"""ORCA quantum chemistry engine."""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import Engine, EngineConfig, StepResult


@dataclass
class ORCAEngineConfig(EngineConfig):
    """ORCA engine configuration."""
    orca_bin: Optional[Path] = None
    nprocs: int = 1


class ORCAEngine(Engine):
    """
    ORCA quantum chemistry engine.

    Executes ORCA as external process, compiles chains to single input files.
    """

    def __init__(self, orca_bin: Optional[Path] = None, config: Optional[ORCAEngineConfig] = None):
        """
        Initialize ORCA engine.

        Args:
            orca_bin: Path to ORCA binary directory (optional, auto-resolved)
            config: Engine configuration
        """
        self.config = config or ORCAEngineConfig()

        if orca_bin:
            self.orca_dir = orca_bin if orca_bin.is_dir() else orca_bin.parent
        elif self.config.orca_bin:
            self.orca_dir = self.config.orca_bin
        else:
            from quantumvitas.core.engines.orca_resolver import resolve_orca_bin_dir
            self.orca_dir = resolve_orca_bin_dir()

        self.orca_binary = self.orca_dir / "orca"

    def probe(self) -> Tuple[bool, str]:
        """
        Check if ORCA is available.

        Returns:
            (available, version_or_error)
        """
        if not self.orca_binary.exists():
            return False, f"ORCA binary not found at {self.orca_binary}"

        try:
            # ORCA prints version info with no args or with --version
            result = subprocess.run(
                [str(self.orca_binary), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # ORCA may return non-zero for --version, check output
            if "ORCA" in result.stdout or "ORCA" in result.stderr:
                version = self._extract_version(result.stdout + result.stderr)
                return True, version
            return True, "ORCA (version unknown)"
        except Exception as e:
            return False, str(e)

    def _extract_version(self, output: str) -> str:
        """Extract version from ORCA output."""
        for line in output.split('\n'):
            if 'Version' in line or 'ORCA' in line:
                return line.strip()
        return "ORCA"

    def _build_command(self, input_file: Path) -> List[str]:
        """Build ORCA command line."""
        return [str(self.orca_binary), str(input_file)]

    def run_chain(
        self,
        chain: Any,  # QCChain
        working_dir: Path,
        molecule: Any,
        fresh: bool = False,
    ) -> List[StepResult]:
        """
        Execute a chain as single ORCA job.

        Args:
            chain: QCChain to execute
            working_dir: Directory for I/O
            molecule: Molecule object
            fresh: Force fresh run (NoAutoStart)

        Returns:
            List of StepResult for each step in chain
        """
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engines.orca.property_parser import parse_orca_property_txt

        # 1. Compile chain to input
        compiler = ORCAInputCompiler()
        input_content = compiler.compile(
            chain,
            molecule,
            fresh=fresh,
            nprocs=self.config.nprocs,
        )

        # 2. Write input file
        input_file = working_dir / f"{chain.key}.inp"
        input_file.write_text(input_content)

        # 3. Execute ORCA
        output_file = working_dir / f"{chain.key}.out"
        cmd = self._build_command(input_file)

        env = os.environ.copy()
        # Ensure ORCA can find its helper binaries
        env["PATH"] = f"{self.orca_dir}:{env.get('PATH', '')}"

        try:
            with open(output_file, 'w') as out_f:
                result = subprocess.run(
                    cmd,
                    cwd=working_dir,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=3600,  # 1 hour timeout
                )
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            success = False
        except Exception as e:
            success = False

        # 4. Parse results
        property_file = working_dir / f"{chain.key}.property.txt"
        parsed_properties = {}
        if property_file.exists():
            try:
                parsed_properties = parse_orca_property_txt(property_file)
            except Exception:
                pass

        # 5. Build per-step results
        results = []
        for step in chain.all_steps:
            step_result = self._extract_step_result(
                step=step,
                chain_key=chain.key,
                success=success,
                properties=parsed_properties,
                working_dir=working_dir,
            )
            results.append(step_result)

        return results

    def _extract_step_result(
        self,
        step: Any,
        chain_key: str,
        success: bool,
        properties: Dict[str, Any],
        working_dir: Path,
    ) -> StepResult:
        """Extract results for a specific step from chain output."""
        metrics: Dict[str, Any] = {}

        if step.public_type in ("scf", "hf"):
            if "SCF_Energy" in properties:
                metrics["energy"] = properties["SCF_Energy"]
            elif "Total_Energy" in properties:
                metrics["energy"] = properties["Total_Energy"]

        elif step.public_type == "td":
            if "TDDFT_Excitation_Energies" in properties:
                metrics["excitation_energies"] = properties["TDDFT_Excitation_Energies"]
            if "TDDFT_Oscillator_Strengths" in properties:
                metrics["oscillator_strengths"] = properties["TDDFT_Oscillator_Strengths"]

        return StepResult(
            step_id=step.id,
            success=success,
            metrics=metrics,
            artifacts={
                "output": str(working_dir / f"{chain_key}.out"),
                "property": str(working_dir / f"{chain_key}.property.txt"),
            },
        )
```

**Pytest command**:
```bash
pytest tests/unit/orca/ -v
# Expected: All unit tests pass
```

**Checkpoint 4**: ORCA engine core complete.

---

## Phase 5: Integration Tests (With Bundled ORCA)

**Goal**: Verify actual ORCA execution works.

### Step 5.1: Create Integration Test Directory

```bash
mkdir -p tests/integration/orca
touch tests/integration/__init__.py
touch tests/integration/orca/__init__.py
```

### Step 5.2: Write Integration Tests

**File to create**: `tests/integration/orca/test_orca_execution.py`

```python
"""Integration tests for ORCA engine (require ORCA binary)."""
import os
import pytest
from dataclasses import dataclass
from pathlib import Path


ORCA_BIN = os.environ.get("QMATSUITE_ORCA_BIN")


@dataclass
class SimpleMolecule:
    """Simple molecule for testing."""
    atoms: str
    charge: int
    multiplicity: int


WATER = SimpleMolecule(
    atoms="""O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200""",
    charge=0,
    multiplicity=1,
)


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str
    parameters: dict


@pytest.fixture
def orca_engine():
    """Get ORCA engine if available."""
    if not ORCA_BIN:
        pytest.skip("QMATSUITE_ORCA_BIN not set")

    orca_path = Path(ORCA_BIN)
    if not orca_path.exists():
        pytest.skip(f"ORCA binary not found at {ORCA_BIN}")

    from quantumvitas.engine.orca_engine import ORCAEngine
    return ORCAEngine(orca_bin=orca_path.parent)


@pytest.mark.integration
@pytest.mark.orca
class TestORCAExecution:
    """Integration tests for ORCA execution."""

    def test_scf_execution(self, orca_engine, tmp_path):
        """Test basic SCF calculation."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},  # HF is faster
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert len(results) == 1
        assert results[0].success, f"SCF failed: check {tmp_path / 'chain01_scf.out'}"
        assert (tmp_path / "chain01_scf.out").exists()
        assert (tmp_path / "chain01_scf.gbw").exists()
        assert "energy" in results[0].metrics
        assert results[0].metrics["energy"] < 0  # Energy should be negative

    def test_scf_td_chain(self, orca_engine, tmp_path):
        """Test SCF + TDDFT chain."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert len(results) == 2
        assert results[0].success, f"SCF failed: check {tmp_path / 'chain01_scf_td.out'}"
        assert results[1].success, f"TD failed: check {tmp_path / 'chain01_scf_td.out'}"
        assert "energy" in results[0].metrics
        # TD results may or may not have excitation energies depending on property file
        assert (tmp_path / "chain01_scf_td.out").exists()

    def test_property_file_generated(self, orca_engine, tmp_path):
        """Verify property.txt is generated."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        orca_engine.run_chain(chain, tmp_path, WATER)

        property_file = tmp_path / "chain01_scf.property.txt"
        assert property_file.exists(), "Property file not generated"
        content = property_file.read_text()
        assert len(content) > 0, "Property file is empty"

    def test_fresh_run_uses_noautostart(self, orca_engine, tmp_path):
        """Verify fresh=True generates NoAutoStart."""
        from quantumvitas.engine.qc_engine_base import QCChain
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, WATER, fresh=True)

        assert "NoAutoStart" in input_text
```

### Step 5.3: Run Integration Tests

**Local execution with bundled ORCA**:
```bash
# Set environment variable
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca

# Run integration tests only
pytest tests/integration/orca/ -v -m integration

# Run all tests (unit + integration)
pytest tests/ -v
```

**CI execution (no ORCA)**:
```bash
# Integration tests auto-skip when QMATSUITE_ORCA_BIN not set
pytest tests/ -v
# Expected: Unit tests pass, integration tests skip
```

**Checkpoint 5**: Integration tests pass with bundled ORCA.

---

## Phase 6: Step Type Registration

**Goal**: Register ORCA step types in StepTypeRegistry.

### Step 6.1: Add ORCA Step Types

**File to modify**: `src/quantumvitas/workflow/registry.py`

Add to `_STEP_TYPES` dictionary:

```python
# ORCA step types
"orca_scf": StepTypeSpec(
    machine_type="orca_scf",
    public_type="scf",
    engine="orca",
    executable="orca",
    description="ORCA DFT SCF calculation",
    supports_incremental_skip=True,  # Via AutoStart
    consumes_state=None,
    produces_state="gbw",
),
"orca_hf": StepTypeSpec(
    machine_type="orca_hf",
    public_type="hf",
    engine="orca",
    executable="orca",
    description="ORCA Hartree-Fock calculation",
    supports_incremental_skip=True,
    consumes_state=None,
    produces_state="gbw",
),
"orca_td": StepTypeSpec(
    machine_type="orca_td",
    public_type="td",
    engine="orca",
    executable="orca",
    description="ORCA TDDFT excited states",
    supports_incremental_skip=False,
    consumes_state="gbw",
    produces_state=None,
),
```

### Step 6.2: Add ORCA Materialization

**File to modify**: `src/quantumvitas/workflow/generalized_steps.py`

Add to `MATERIALIZATION_MAP`:

```python
("orca", GeneralizedStep.SCF): "orca_scf",
("orca", GeneralizedStep.HF): "orca_hf",
("orca", GeneralizedStep.TD): "orca_td",
```

### Step 6.3: Test Registration

**Pytest command**:
```bash
pytest tests/unit/workflow/test_registry.py -v -k "orca"
# If no specific tests exist, run all registry tests
pytest tests/unit/workflow/test_registry.py -v
```

**Checkpoint 6**: ORCA step types registered.

---

## Phase 7: Engine Registration

**Goal**: Register ORCAEngine in EngineRegistry.

### Step 7.1: Update Engine Registry

**File to modify**: `src/quantumvitas/engine/registry.py`

Add ORCA to `create_default_registry()`:

```python
def create_default_registry() -> EngineRegistry:
    """Create registry with all default engines."""
    registry = EngineRegistry()

    # ... existing engines ...

    # ORCA
    try:
        from quantumvitas.engine.orca_engine import ORCAEngine
        registry.register("orca", ORCAEngine)
    except ImportError:
        pass

    return registry
```

### Step 7.2: Test Engine Registration

```bash
pytest tests/unit/engine/test_registry.py -v
```

**Checkpoint 7**: ORCA engine registered.

---

## Summary: Test Commands

### Run All Unit Tests (No ORCA Required)
```bash
pytest tests/unit/ -v
```

### Run ORCA-Specific Unit Tests
```bash
pytest tests/unit/orca/ -v
```

### Run Integration Tests (Requires ORCA)
```bash
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
pytest tests/integration/orca/ -v -m integration
```

### Run All Tests
```bash
pytest tests/ -v
```

### Continuous Testing During Development
```bash
# Watch mode (if using pytest-watch)
ptw tests/unit/orca/

# Or manual continuous run
while true; do pytest tests/unit/orca/ -v --tb=short; sleep 5; done
```

---

## Checkpoints Summary

| Phase | Checkpoint | Verification |
|-------|------------|--------------|
| 0 | Manual ORCA works | `./orca water.inp` succeeds |
| 1 | Property parser | `pytest tests/unit/orca/test_property_parser.py` |
| 2 | Chain detection | `pytest tests/unit/orca/test_chain_detection.py` |
| 3 | Input compiler | `pytest tests/unit/orca/test_input_compiler.py` |
| 4 | ORCA engine core | `pytest tests/unit/orca/` |
| 5 | Integration tests | `pytest tests/integration/orca/ -m integration` |
| 6 | Step registration | `pytest tests/unit/workflow/test_registry.py` |
| 7 | Engine registration | `pytest tests/unit/engine/test_registry.py` |

---

## Files Created/Modified Summary

### New Files
```
src/quantumvitas/engines/orca/__init__.py
src/quantumvitas/engines/orca/property_parser.py
src/quantumvitas/engines/orca/input_compiler.py
src/quantumvitas/engine/qc_engine_base.py
src/quantumvitas/engine/orca_engine.py
src/quantumvitas/core/engines/orca_resolver.py
tests/unit/orca/__init__.py
tests/unit/orca/test_property_parser.py
tests/unit/orca/test_chain_detection.py
tests/unit/orca/test_input_compiler.py
tests/unit/orca/test_orca_engine.py
tests/integration/orca/__init__.py
tests/integration/orca/test_orca_execution.py
tests/fixtures/orca/water_scf.property.txt
tests/fixtures/orca/water_scf_td.property.txt
tests/fixtures/orca/water_scf.out
```

### Modified Files
```
src/quantumvitas/workflow/registry.py          # Add ORCA step types
src/quantumvitas/workflow/generalized_steps.py # Add ORCA materialization
src/quantumvitas/engine/registry.py            # Add ORCA engine
```
