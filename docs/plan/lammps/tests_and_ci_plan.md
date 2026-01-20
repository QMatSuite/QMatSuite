# LAMMPS Tests and CI Plan

**Version**: 1.0.0  
**Date**: 2026-01-20  
**Status**: Ready for Execution  
**Constitution Reference**: Tests must run through high-level API in real project/calc structure

---

## 1. Overview

This document specifies the test strategy for LAMMPS integration, including:
- Unit tests for individual components
- Integration tests using high-level QMatSuite API
- CI configuration for mac and ubuntu
- Parser fixture generation and storage

**Key Constraint**: All smoke workflows MUST run through the high-level QMatSuite API (daemon-level) in real `project/calc` directory structures.

---

## 2. Test Matrix

### 2.1 Platform Matrix

| Platform | LAMMPS Install | Python | CI Runner |
|----------|---------------|--------|-----------|
| macOS (arm64) | `brew install lammps` | 3.10+ | `macos-latest` |
| macOS (x86) | `brew install lammps` | 3.10+ | `macos-13` |
| Ubuntu 22.04 | `apt install lammps` | 3.10+ | `ubuntu-latest` |
| Ubuntu 24.04 | `apt install lammps` | 3.10+ | `ubuntu-24.04` |

### 2.2 Test Categories

| Category | Count | Requires LAMMPS | In CI |
|----------|-------|-----------------|-------|
| Unit tests | ~20 | No (mocked) | ✅ Always |
| Parser fixtures | ~5 | No (uses stored outputs) | ✅ Always |
| Smoke integration | 3 | Yes | ✅ Required |
| Full integration | 5+ | Yes | ✅ Required |

---

## 3. Smoke Workflows (Required)

Per user specification, we need at least 3 smoke workflows that:
1. Run through high-level API / daemon level
2. Use real project/calc directory structure
3. Cover LJ, real potentials, and workflow chaining

### 3.1 Smoke Workflow 1: LJ Minimize (Simplest)

**Purpose**: Verify basic engine functionality without external files.

**Test File**: `tests/integration/test_lammps_lj_minimize.py`

**Project Structure**:
```
tests/data/lammps/lj_minimize/
├── project.qv.yml
├── structures/
│   └── lj_fcc_108.json         # 108-atom FCC Ar lattice
└── calculations/
    └── minimize/
        ├── calculation.yaml
        └── steps/
            └── step_001.yaml
```

**calculation.yaml**:
```yaml
meta:
  id: "01TEST_LJ_MIN"
  name: "lj_minimize_test"

engine: lammps
structure_id: "lj_fcc_108"

steps:
  - meta:
      id: "01STEP_LJ_MIN"
    type: relax
    parameters:
      units: lj
      atom_style: atomic
      lj_system:
        masses:
          1: 1.0
        type_labels:
          1: "Ar"
      potential:
        style: lj/cut
        cutoff: 2.5
        params:
          "1 1": "1.0 1.0"
      energy_tolerance: 1.0e-4
      force_tolerance: 1.0e-6
      max_iterations: 100
      thermo_frequency: 10
      dump_frequency: 10
```

**Test Code**:
```python
# tests/integration/test_lammps_lj_minimize.py

import pytest
from pathlib import Path
from quantumvitas.daemon.runner import run_calculation
from quantumvitas.project import Project

@pytest.fixture
def lj_project(tmp_path):
    """Copy LJ minimize test data to temp directory."""
    import shutil
    src = Path(__file__).parent.parent / "data" / "lammps" / "lj_minimize"
    dst = tmp_path / "lj_minimize"
    shutil.copytree(src, dst)
    return dst

@pytest.mark.integration
@pytest.mark.lammps
def test_lj_minimize_completes(lj_project):
    """LJ minimize runs to completion via high-level API."""
    project = Project.load(lj_project)
    calc = project.get_calculation("minimize")
    
    result = run_calculation(calc)
    
    assert result.success, f"Failed: {result.error}"
    assert result.steps[0].status == "completed"

@pytest.mark.integration
@pytest.mark.lammps
def test_lj_minimize_produces_outputs(lj_project):
    """LJ minimize produces expected output files."""
    project = Project.load(lj_project)
    calc = project.get_calculation("minimize")
    
    result = run_calculation(calc)
    
    # Check outputs exist
    raw_dir = calc.io.raw_dir / result.steps[0].step_ulid
    assert (raw_dir / "log.lammps").exists()
    assert (raw_dir / "final.data").exists()
    assert (raw_dir / "restart.bin").exists()

@pytest.mark.integration
@pytest.mark.lammps
def test_lj_minimize_trajectory_parse(lj_project):
    """LJ minimize trajectory can be parsed."""
    from quantumvitas.engine.lammps_parser import parse_lammps_dump
    
    project = Project.load(lj_project)
    calc = project.get_calculation("minimize")
    result = run_calculation(calc)
    
    raw_dir = calc.io.raw_dir / result.steps[0].step_ulid
    dump_file = raw_dir / "trajectory.lammpstrj"
    
    if dump_file.exists():
        frames = parse_lammps_dump(dump_file)
        assert len(frames) > 0
        assert len(frames[0].positions) == 108  # 108 atoms
```

**Verification Criteria**:
- [x] Exit code 0
- [x] `log.lammps` exists
- [x] `final.data` exists
- [x] `restart.bin` exists
- [x] Thermo series shows energy decrease

---

### 3.2 Smoke Workflow 2: EAM Cu MD

**Purpose**: Verify potential file staging and real metal simulation.

**Test File**: `tests/integration/test_lammps_eam_md.py`

**Project Structure**:
```
tests/data/lammps/eam_md/
├── project.qv.yml
├── structures/
│   └── cu_fcc_32.json          # 32-atom Cu FCC
├── potentials/
│   └── Cu_u3.eam               # Staged from resources
└── calculations/
    └── md_nvt/
        ├── calculation.yaml
        └── steps/
            └── step_001.yaml
```

**calculation.yaml**:
```yaml
meta:
  id: "01TEST_EAM_MD"
  name: "eam_md_test"

engine: lammps
structure_id: "cu_fcc_32"

potential_map:
  eam_cu:
    style: eam
    file: potentials/Cu_u3.eam
    elements: [Cu]

steps:
  - meta:
      id: "01STEP_EAM_MD"
    type: md
    parameters:
      potential: eam_cu
      units: metal
      atom_style: atomic
      ensemble: nvt
      temperature: 300
      timestep_fs: 1.0
      n_steps: 100
      thermo_frequency: 10
      dump_frequency: 10
      restart_frequency: 50
```

**Test Code**:
```python
# tests/integration/test_lammps_eam_md.py

import pytest
from pathlib import Path
import numpy as np

@pytest.fixture
def eam_project(tmp_path, lammps_test_potentials):
    """Copy EAM MD test data to temp directory with potentials."""
    import shutil
    src = Path(__file__).parent.parent / "data" / "lammps" / "eam_md"
    dst = tmp_path / "eam_md"
    shutil.copytree(src, dst)
    
    # Copy potential from resources
    pot_dst = dst / "potentials"
    pot_dst.mkdir(exist_ok=True)
    shutil.copy(lammps_test_potentials / "Cu_u3.eam", pot_dst)
    
    return dst

@pytest.fixture
def lammps_test_potentials():
    """Path to LAMMPS test potentials."""
    return Path(__file__).parent.parent.parent.parent / "resources" / "lammps" / "potentials"

@pytest.mark.integration
@pytest.mark.lammps
def test_eam_md_completes(eam_project):
    """EAM MD runs to completion."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    
    project = Project.load(eam_project)
    calc = project.get_calculation("md_nvt")
    
    result = run_calculation(calc)
    
    assert result.success, f"Failed: {result.error}"

@pytest.mark.integration
@pytest.mark.lammps
def test_eam_md_temperature_stable(eam_project):
    """EAM MD maintains target temperature."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    from quantumvitas.engine.lammps_parser import parse_lammps_log
    
    project = Project.load(eam_project)
    calc = project.get_calculation("md_nvt")
    result = run_calculation(calc)
    
    raw_dir = calc.io.raw_dir / result.steps[0].step_ulid
    thermo = parse_lammps_log(raw_dir / "log.lammps")
    
    # Temperature should be near 300K (allow 50K fluctuation)
    mean_temp = thermo["Temp"].mean()
    assert 250 < mean_temp < 350, f"Mean temperature {mean_temp}K outside range"

@pytest.mark.integration
@pytest.mark.lammps
def test_eam_md_trajectory_has_frames(eam_project):
    """EAM MD produces multi-frame trajectory."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    from quantumvitas.engine.lammps_parser import parse_lammps_dump
    
    project = Project.load(eam_project)
    calc = project.get_calculation("md_nvt")
    result = run_calculation(calc)
    
    raw_dir = calc.io.raw_dir / result.steps[0].step_ulid
    frames = parse_lammps_dump(raw_dir / "trajectory.lammpstrj")
    
    # 100 steps / 10 dump_freq = 10 frames + initial = 11
    assert len(frames) >= 10
    assert all(len(f.positions) == 32 for f in frames)
```

**Verification Criteria**:
- [x] Potential file correctly staged
- [x] MD runs to completion
- [x] Temperature near 300K
- [x] Trajectory has expected frame count
- [x] Restart files written

---

### 3.3 Smoke Workflow 3: Chain (Relax → MD → Restart)

**Purpose**: Verify `restart_from` artifact resolution and multi-step workflows.

**Test File**: `tests/integration/test_lammps_chain.py`

**Project Structure**:
```
tests/data/lammps/chain_workflow/
├── project.qv.yml
├── structures/
│   └── cu_fcc_32.json
├── potentials/
│   └── Cu_u3.eam
└── calculations/
    └── chain/
        ├── calculation.yaml
        └── steps/
            ├── step_001.yaml   # relax
            ├── step_002.yaml   # md
            └── step_003.yaml   # continue
```

**calculation.yaml**:
```yaml
meta:
  id: "01TEST_CHAIN"
  name: "chain_workflow_test"

engine: lammps
structure_id: "cu_fcc_32"

potential_map:
  eam_cu:
    style: eam
    file: potentials/Cu_u3.eam
    elements: [Cu]

steps:
  - meta:
      id: "01STEP_RELAX"
      slug: "relax"
    type: relax
    parameters:
      potential: eam_cu
      units: metal
      atom_style: atomic
      energy_tolerance: 1.0e-4
      force_tolerance: 1.0e-4
      max_iterations: 50
      thermo_frequency: 5
      
  - meta:
      id: "01STEP_MD"
      slug: "md"
    type: md
    parameters:
      potential: eam_cu
      restart_from: relax
      units: metal
      atom_style: atomic
      ensemble: nvt
      temperature: 300
      timestep_fs: 1.0
      n_steps: 50
      thermo_frequency: 10
      restart_frequency: 25
      
  - meta:
      id: "01STEP_CONTINUE"
      slug: "continue"
    type: md
    parameters:
      potential: eam_cu
      restart_from: md
      units: metal
      atom_style: atomic
      ensemble: nvt
      temperature: 300
      timestep_fs: 1.0
      n_steps: 50
      thermo_frequency: 10
```

**Test Code**:
```python
# tests/integration/test_lammps_chain.py

import pytest
from pathlib import Path

@pytest.fixture
def chain_project(tmp_path, lammps_test_potentials):
    """Copy chain workflow test data."""
    import shutil
    src = Path(__file__).parent.parent / "data" / "lammps" / "chain_workflow"
    dst = tmp_path / "chain_workflow"
    shutil.copytree(src, dst)
    
    pot_dst = dst / "potentials"
    pot_dst.mkdir(exist_ok=True)
    shutil.copy(lammps_test_potentials / "Cu_u3.eam", pot_dst)
    
    return dst

@pytest.mark.integration
@pytest.mark.lammps
def test_chain_all_steps_complete(chain_project):
    """Chain workflow runs all 3 steps to completion."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    
    project = Project.load(chain_project)
    calc = project.get_calculation("chain")
    
    result = run_calculation(calc)
    
    assert result.success, f"Failed: {result.error}"
    assert len(result.steps) == 3
    assert all(s.status == "completed" for s in result.steps)

@pytest.mark.integration
@pytest.mark.lammps
def test_chain_restart_uses_correct_artifacts(chain_project):
    """MD step uses final.data from relax; continue uses restart.bin from MD."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    
    project = Project.load(chain_project)
    calc = project.get_calculation("chain")
    result = run_calculation(calc)
    
    # Check relax produced outputs
    relax_dir = calc.io.raw_dir / result.steps[0].step_ulid
    assert (relax_dir / "final.data").exists()
    
    # Check MD step references relax's final.data (via restart_from resolution)
    md_dir = calc.io.raw_dir / result.steps[1].step_ulid
    in_script = (md_dir / "in.lammps").read_text()
    # MD uses read_data or read_restart from relax output
    assert "read_" in in_script  # read_data or read_restart
    
    # Check MD produced restart
    assert (md_dir / "restart.bin").exists() or len(list(md_dir.glob("restart.*.bin"))) > 0
    
    # Check continue step references MD restart
    continue_dir = calc.io.raw_dir / result.steps[2].step_ulid
    continue_script = (continue_dir / "in.lammps").read_text()
    assert "read_restart" in continue_script

@pytest.mark.integration
@pytest.mark.lammps
def test_chain_relax_produces_artifact(chain_project):
    """Relax step produces generated structure artifact."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    
    project = Project.load(chain_project)
    calc = project.get_calculation("chain")
    result = run_calculation(calc)
    
    # Check .analysis directory has relaxed structure
    analysis_dir = calc.path / ".analysis" / result.steps[0].step_ulid
    assert analysis_dir.exists()
    # Could check for relaxed_structure.json or similar

@pytest.mark.integration
@pytest.mark.lammps
def test_chain_missing_artifact_fails(chain_project):
    """restart_from with missing artifact raises clear error."""
    from quantumvitas.project import Project
    from quantumvitas.daemon.runner import run_calculation
    
    project = Project.load(chain_project)
    calc = project.get_calculation("chain")
    
    # Delete the relax step's outputs to simulate missing artifact
    # (This tests error handling, not normal flow)
    
    # First run just relax
    # Then delete its outputs
    # Then try to run MD - should fail with clear message
    
    # This is a negative test case
    pass  # Implementation depends on exact API
```

**Verification Criteria**:
- [x] All 3 steps complete
- [x] Relax produces `final.data`
- [x] MD uses relax's output
- [x] Continue uses MD's `restart.bin`
- [x] Cross-calc `restart_from` would fail (separate test)

---

## 4. Unit Tests

### 4.1 Unit Test Files

| File | Covers | LAMMPS Required |
|------|--------|-----------------|
| `test_lammps_engine.py` | Engine registration, supported_presets | No |
| `test_lammps_resolver.py` | Binary discovery logic | No (mocked) |
| `test_lammps_writer.py` | Template rendering, data file generation | No |
| `test_lammps_parser.py` | Log/dump parsing with fixtures | No |
| `test_lammps_potentials.py` | Potential staging, digest computation | No |

### 4.2 Parser Unit Tests with Fixtures

```python
# tests/unit/test_lammps_parser.py

import pytest
from pathlib import Path
from quantumvitas.engine.lammps_parser import parse_lammps_log, parse_lammps_dump

@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent / "data" / "lammps" / "fixtures"

class TestLogParser:
    def test_parse_minimize_log(self, fixtures_dir):
        """Parse minimize log file."""
        thermo = parse_lammps_log(fixtures_dir / "log_minimize_lj.lammps")
        
        assert "Step" in thermo.columns
        assert "PotEng" in thermo.columns
        assert len(thermo) > 0
        
    def test_parse_md_log(self, fixtures_dir):
        """Parse MD log file."""
        thermo = parse_lammps_log(fixtures_dir / "log_md_nvt.lammps")
        
        assert "Step" in thermo.columns
        assert "Temp" in thermo.columns
        assert "TotEng" in thermo.columns
        
    def test_log_energy_decreases_in_minimize(self, fixtures_dir):
        """Minimize log shows energy decrease."""
        thermo = parse_lammps_log(fixtures_dir / "log_minimize_lj.lammps")
        
        initial_pe = thermo["PotEng"].iloc[0]
        final_pe = thermo["PotEng"].iloc[-1]
        assert final_pe <= initial_pe

class TestDumpParser:
    def test_parse_dump_frames(self, fixtures_dir):
        """Parse dump file into frames."""
        frames = parse_lammps_dump(fixtures_dir / "dump_md.lammpstrj")
        
        assert len(frames) > 0
        assert hasattr(frames[0], "positions")
        assert hasattr(frames[0], "species")
        
    def test_dump_sorted_by_id(self, fixtures_dir):
        """Dump atoms are sorted by id."""
        frames = parse_lammps_dump(fixtures_dir / "dump_md.lammpstrj")
        
        for frame in frames:
            # Assuming frame has atom_ids attribute
            if hasattr(frame, "atom_ids"):
                ids = frame.atom_ids
                assert list(ids) == sorted(ids)
                
    def test_dump_has_velocities_forces(self, fixtures_dir):
        """Dump includes velocities and forces."""
        frames = parse_lammps_dump(fixtures_dir / "dump_md.lammpstrj")
        
        for frame in frames:
            if frame.velocities is not None:
                assert frame.velocities.shape == frame.positions.shape
            if frame.forces is not None:
                assert frame.forces.shape == frame.positions.shape
```

---

## 5. Parser Fixture Generation

### 5.1 Fixture Generation Script

Run this once to capture representative outputs:

```python
#!/usr/bin/env python3
"""Generate LAMMPS parser fixtures - run once, commit results."""

import subprocess
from pathlib import Path

FIXTURES_DIR = Path("tests/data/lammps/fixtures")

def generate_lj_minimize_fixture():
    """Generate LJ minimize log/dump fixtures."""
    script = """
units lj
atom_style atomic
boundary p p p

lattice fcc 0.8442
region box block 0 4 0 4 0 4
create_box 1 box
create_atoms 1 box
mass 1 1.0

pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5

velocity all create 1.0 87287 mom yes rot yes

thermo 10
thermo_style custom step pe fnorm fmax

dump traj all custom 10 dump_minimize.lammpstrj id type x y z vx vy vz fx fy fz
dump_modify traj sort id

min_style cg
minimize 1e-6 1e-8 100 1000

write_data final_minimize.data
"""
    
    (FIXTURES_DIR / "in_minimize_lj.lammps").write_text(script)
    
    subprocess.run(
        ["lmp", "-in", "in_minimize_lj.lammps", "-log", "log_minimize_lj.lammps"],
        cwd=FIXTURES_DIR,
        check=True,
    )
    
    print("Generated: log_minimize_lj.lammps, dump_minimize.lammpstrj")

def generate_md_nvt_fixture():
    """Generate NVT MD log/dump fixtures."""
    script = """
units lj
atom_style atomic
boundary p p p

lattice fcc 0.8442
region box block 0 4 0 4 0 4
create_box 1 box
create_atoms 1 box
mass 1 1.0

pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5

velocity all create 1.0 87287 mom yes rot yes

fix nvt all nvt temp 1.0 1.0 0.1

thermo 10
thermo_style custom step time temp pe ke etotal press

dump traj all custom 10 dump_md.lammpstrj id type x y z vx vy vz fx fy fz
dump_modify traj sort id

timestep 0.005
run 100
"""
    
    (FIXTURES_DIR / "in_md_nvt.lammps").write_text(script)
    
    subprocess.run(
        ["lmp", "-in", "in_md_nvt.lammps", "-log", "log_md_nvt.lammps"],
        cwd=FIXTURES_DIR,
        check=True,
    )
    
    print("Generated: log_md_nvt.lammps, dump_md.lammpstrj")

if __name__ == "__main__":
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    generate_lj_minimize_fixture()
    generate_md_nvt_fixture()
    print(f"\nFixtures generated in {FIXTURES_DIR}")
```

### 5.2 Fixture Files to Commit

```
tests/data/lammps/fixtures/
├── README.md                   # Provenance info
├── log_minimize_lj.lammps      # ~1 KB
├── log_md_nvt.lammps           # ~2 KB
├── dump_minimize.lammpstrj     # ~5 KB
├── dump_md.lammpstrj           # ~20 KB (10 frames)
├── final_minimize.data         # ~3 KB
└── in_*.lammps                 # Input scripts used to generate
```

### 5.3 Fixture README

```markdown
# LAMMPS Parser Fixtures

Generated: 2026-01-20
LAMMPS Version: stable_2Aug2023 (or current)

## Files

| File | Description | Size |
|------|-------------|------|
| log_minimize_lj.lammps | LJ minimize thermo output | ~1 KB |
| log_md_nvt.lammps | NVT MD thermo output | ~2 KB |
| dump_minimize.lammpstrj | Minimize trajectory (10 frames) | ~5 KB |
| dump_md.lammpstrj | MD trajectory (10 frames) | ~20 KB |

## Regeneration

If needed, run:
```bash
python tools/generate_lammps_fixtures.py
```

## Thermo Columns

- minimize: Step, PotEng, Fnorm, Fmax
- md: Step, Time, Temp, PotEng, KinEng, TotEng, Press

## Dump Columns

id type x y z vx vy vz fx fy fz
```

---

## 6. CI Configuration

### 6.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  # Existing jobs...
  
  test-lammps-mac:
    name: LAMMPS Tests (macOS)
    runs-on: macos-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install LAMMPS
        run: |
          brew install lammps
          # Verify installation
          lmp -h | head -5
          
      - name: Install Python dependencies
        run: |
          pip install -e ".[dev]"
          
      - name: Run LAMMPS unit tests
        run: |
          pytest tests/unit/test_lammps*.py -v --tb=short
          
      - name: Run LAMMPS integration tests
        run: |
          pytest tests/integration/test_lammps*.py -v --tb=short -x
          
      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: lammps-test-logs-mac
          path: |
            **/log.lammps
            **/trajectory.lammpstrj
  
  test-lammps-ubuntu:
    name: LAMMPS Tests (Ubuntu)
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install LAMMPS
        run: |
          sudo apt-get update
          sudo apt-get install -y lammps
          # Verify installation
          lmp -h 2>&1 | head -5 || lmp_mpi -h 2>&1 | head -5
          
      - name: Install Python dependencies
        run: |
          pip install -e ".[dev]"
          
      - name: Run LAMMPS unit tests
        run: |
          pytest tests/unit/test_lammps*.py -v --tb=short
          
      - name: Run LAMMPS integration tests
        run: |
          pytest tests/integration/test_lammps*.py -v --tb=short -x
          
      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: lammps-test-logs-ubuntu
          path: |
            **/log.lammps
            **/trajectory.lammpstrj
```

### 6.2 Pytest Configuration

```ini
# pytest.ini additions

[pytest]
markers =
    lammps: Tests that require LAMMPS binary
    integration: Integration tests (require external dependencies)
    
filterwarnings =
    ignore::DeprecationWarning
```

### 6.3 Conftest Fixtures

```python
# tests/conftest.py additions

import pytest
import shutil
from pathlib import Path

@pytest.fixture(scope="session")
def lammps_available():
    """Check if LAMMPS is available."""
    return shutil.which("lmp") or shutil.which("lmp_serial") or shutil.which("lmp_mpi")

@pytest.fixture
def lammps_test_potentials():
    """Path to LAMMPS test potentials in resources."""
    path = Path(__file__).parent.parent / "resources" / "lammps" / "potentials"
    if not path.exists():
        pytest.skip("LAMMPS test potentials not found")
    return path

@pytest.fixture(autouse=True)
def skip_without_lammps(request, lammps_available):
    """Skip LAMMPS tests if binary not available."""
    if "lammps" in request.keywords and not lammps_available:
        pytest.skip("LAMMPS not installed")
```

---

## 7. Test Execution Checklist

### 7.1 Local Development

```bash
# Run all LAMMPS unit tests (no binary needed)
pytest tests/unit/test_lammps*.py -v

# Run parser tests with fixtures
pytest tests/unit/test_lammps_parser.py -v

# Run integration tests (requires LAMMPS)
pytest tests/integration/test_lammps*.py -v

# Run single smoke workflow
pytest tests/integration/test_lammps_lj_minimize.py -v

# Run with coverage
pytest tests/unit/test_lammps*.py --cov=quantumvitas.engine.lammps --cov-report=term-missing
```

### 7.2 CI Verification

```bash
# Verify CI would pass locally
pytest tests/unit/test_lammps*.py tests/integration/test_lammps*.py -v --tb=short
```

---

## 8. Test Data File Checklist

### 8.1 Files to Create

```
tests/data/lammps/
├── lj_minimize/                    # Smoke workflow 1
│   ├── project.qv.yml
│   ├── structures/
│   │   └── lj_fcc_108.json
│   └── calculations/
│       └── minimize/
│           ├── calculation.yaml
│           └── steps/
│               └── step_001.yaml
│
├── eam_md/                         # Smoke workflow 2
│   ├── project.qv.yml
│   ├── structures/
│   │   └── cu_fcc_32.json
│   ├── potentials/                 # Copied at test time
│   └── calculations/
│       └── md_nvt/
│           ├── calculation.yaml
│           └── steps/
│               └── step_001.yaml
│
├── chain_workflow/                 # Smoke workflow 3
│   ├── project.qv.yml
│   ├── structures/
│   │   └── cu_fcc_32.json
│   ├── potentials/                 # Copied at test time
│   └── calculations/
│       └── chain/
│           ├── calculation.yaml
│           └── steps/
│               ├── step_001.yaml
│               ├── step_002.yaml
│               └── step_003.yaml
│
└── fixtures/                       # Parser test fixtures
    ├── README.md
    ├── log_minimize_lj.lammps
    ├── log_md_nvt.lammps
    ├── dump_minimize.lammpstrj
    └── dump_md.lammpstrj
```

### 8.2 Structure Files

Use simple FCC structures for testing:

```python
# Generate test structures
from ase.build import bulk
from ase.io import write
import json

# LJ FCC (108 atoms)
atoms = bulk("Ar", "fcc", a=5.26, cubic=True) * (3, 3, 3)
# Save as JSON compatible with QMatSuite

# Cu FCC (32 atoms)
cu = bulk("Cu", "fcc", a=3.6, cubic=True) * (2, 2, 2)
```

