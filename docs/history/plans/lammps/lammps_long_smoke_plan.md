# LAMMPS Long Smoke Test Plan

> **Purpose**: Verify LAMMPS execution end-to-end using real LAMMPS binary, via high-level QMatSuite API (QMSService/daemon level), covering smoke workflows: LJ, EAM, chain (relax→md), and restart_from.

> **Audience**: Auto (automated execution agent) or developer running manual verification.

---

## 1. Pre-Run Checks (MUST execute before workflows)

### 1.1 Verify Python Environment

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version  # Expect: Python 3.10+

# Verify QMatSuite import
python -c "import qmatsuite; print(f'QMatSuite installed at: {qmatsuite.__file__}')"
```

### 1.2 Verify LAMMPS Binary Availability

```bash
# Check brew lammps installation
brew --prefix lammps
# Expected output: /opt/homebrew/opt/lammps (Apple Silicon) or /usr/local/opt/lammps (Intel)

# List lammps bin directory
ls -la "$(brew --prefix lammps)/bin/"
# Expected: should contain lmp or lmp_serial

# Verify LAMMPS version
"$(brew --prefix lammps)/bin/lmp" -h 2>&1 | head -n 5
# Expected: LAMMPS version header
```

### 1.3 Verify Internal LAMMPS Resolver

```bash
python -c "
from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin
path = resolve_lammps_bin()
print(f'Resolved LAMMPS binary: {path}')
"
# Expected: Should print path to lmp binary without error
```

---

## 2. Execution Entry Point

All workflows use the **QMSService API** (high-level project/calculation/step management), NOT direct LAMMPS invocation. This mirrors real GUI/daemon usage.

### API Pattern for Each Workflow:

```python
from qmatsuite.api import QMSService
from qmatsuite.calculation.calculation import Calculation
from qmatsuite.calculation.runner import CalculationRunner
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.project.model import Project

# 1. Create project
project_root = QMSService.init_project(target_dir, name="Test Project")

# 2. Import structure
struct_result = QMSService.import_structure(project_root, struct_file, name="Structure")

# 3. Create calculation
calc_result = QMSService.init_calculation(project_root, name="calc", structure_selector=struct_result.meta.id)

# 4. Create and configure steps
step = QMSService.init_step(project_root, calculation_selector=calc_id, step_type="relax")
QMSService.configure_step(project_root, calculation_selector=calc_id, step_selector=step.meta.id, parameters={...})

# 5. Run calculation
project = Project.open(project_root)
calculation = Calculation.from_yaml(calc_dir, project)
registry = create_default_registry(include_lammps=True)
runner = CalculationRunner(engine_registry=registry)
result = runner.run(calculation)
```

---

## 3. Smoke Workflows

### Workflow A: LJ Relax (units=lj, inline potential dict)

**Purpose**: Test simplest LAMMPS case with LJ pair potential (no external files).

**Structure**: 108-atom LJ FCC (from `tests/data/lammps/structures/lj_fcc_108.json`)

**Step Configuration**:
```python
parameters = {
    "potential": {
        "pair_style": "lj/cut 2.5",
        "pair_coeff": "* * 1.0 1.0",
    },
    "units": "lj",
    "atom_style": "atomic",
    "energy_tolerance": 1e-4,
    "force_tolerance": 1e-6,
    "thermo_frequency": 100,
    "dump_frequency": 500,
    "dump_trajectory": True,
}
```

**Size/Duration**: 108 atoms, ~1000 minimize iterations, < 30 seconds

**Verification Checkpoints**:
1. ✅ `raw/<step_ulid>/in.lammps` exists and contains `pair_style lj/cut 2.5`
2. ✅ `raw/<step_ulid>/structure.data` exists (LAMMPS data file)
3. ✅ `raw/<step_ulid>/log.lammps` exists and contains no `ERROR`
4. ✅ `raw/<step_ulid>/final.data` exists (minimized structure)
5. ✅ `raw/<step_ulid>/dump.lammpstrj` exists (trajectory)
6. ✅ If step_type is relax: `generated_structures/step_<ulid>/current.json` exists
7. ✅ Parser can read trajectory: `from qmatsuite.parsers.lammps import parse_lammps_log`

**Evidence to Collect**:
- `ls -la raw/<step_ulid>/`
- `head -50 raw/<step_ulid>/log.lammps`
- `tail -20 raw/<step_ulid>/log.lammps` (final energy)

---

### Workflow B: EAM MD (external potential, potential_map)

**Purpose**: Test external EAM potential file staging and MD execution.

**Structure**: 32-atom Cu FCC (from `tests/data/lammps/structures/cu_fcc_32.json`)

**Potential File**: `resources/lammps/potentials/Cu_u3.eam`

**calculation.yaml potential_map**:
```yaml
potential_map:
  eam_cu:
    style: eam
    file: potentials/Cu_u3.eam  # Relative to project root
    elements: ["Cu"]
    sha256: <compute at runtime>
```

**Step Configuration**:
```python
parameters = {
    "potential": "eam_cu",  # Reference to potential_map key
    "units": "metal",
    "atom_style": "atomic",
    "ensemble": "nvt",
    "temperature": 300,
    "n_steps": 1000,
    "timestep_fs": 1.0,
    "thermo_frequency": 100,
    "dump_frequency": 100,
    "dump_trajectory": True,
}
```

**Size/Duration**: 32 atoms, 1000 MD steps, < 30 seconds

**Verification Checkpoints**:
1. ✅ Potential file staged: `raw/<step_ulid>/potentials/Cu_u3.eam` exists
2. ✅ `in.lammps` contains correct `pair_style eam` and `pair_coeff * * potentials/Cu_u3.eam Cu`
3. ✅ `log.lammps` contains no `ERROR`
4. ✅ `dump.lammpstrj` contains multiple frames (n_steps / dump_frequency frames)
5. ✅ MD completed: `log.lammps` shows "Total wall time" or "Loop time"

**Evidence to Collect**:
- `ls -la raw/<step_ulid>/potentials/`
- `grep pair_style raw/<step_ulid>/in.lammps`
- `grep pair_coeff raw/<step_ulid>/in.lammps`
- `tail -30 raw/<step_ulid>/log.lammps`
- `wc -l raw/<step_ulid>/dump.lammpstrj`

---

### Workflow C: Chain (Relax → MD) with artifact connection

**Purpose**: Test chained workflow where MD uses structure from relax output.

**Structure**: 32-atom Cu FCC

**Potential**: EAM (same as Workflow B)

**Steps**:
1. **Step 1 (relax)**: Energy minimization
2. **Step 2 (md)**: NVT MD with `restart_from: <relax_step_id>`

**Step 2 Configuration**:
```python
parameters = {
    "potential": "eam_cu",
    "restart_from": relax_step_id,  # ULID of relax step
    "units": "metal",
    "atom_style": "atomic",
    "ensemble": "nvt",
    "temperature": 300,
    "n_steps": 500,
    "thermo_frequency": 100,
    "dump_frequency": 100,
    "dump_trajectory": True,
}
```

**Size/Duration**: 32 atoms, ~1000 minimize + 500 MD steps, < 60 seconds

**Verification Checkpoints**:
1. ✅ Relax step produces `final.data`
2. ✅ Relax step produces `generated_structures/step_<relax_ulid>/current.json`
3. ✅ MD step input uses relax's `final.data` (check `in.lammps` for `read_data ../relax_ulid/final.data` or similar)
4. ✅ MD step's initial structure matches relax output (atom count, cell dimensions)
5. ✅ Both steps complete without `ERROR` in logs

**Evidence to Collect**:
- `ls -la raw/<relax_ulid>/`
- `ls -la raw/<md_ulid>/`
- `cat raw/<md_ulid>/in.lammps | head -30` (verify read_data or restart source)
- Atom count from first frame of MD dump

---

### Workflow D: Restart_from (MD → MD restart)

**Purpose**: Test MD restart from binary restart file.

**Structure**: 32-atom Cu FCC

**Potential**: EAM

**Steps**:
1. **Step 1 (relax)**: Energy minimization
2. **Step 2 (md)**: First MD run (produces `restart.bin`)
3. **Step 3 (md)**: Restart from Step 2's restart file

**Step 3 Configuration**:
```python
parameters = {
    "potential": "eam_cu",
    "restart_from": md_step_id,  # ULID of first MD step
    "units": "metal",
    "atom_style": "atomic",
    "ensemble": "nvt",
    "temperature": 300,
    "n_steps": 500,
    "thermo_frequency": 100,
    "dump_frequency": 100,
    "dump_trajectory": True,
}
```

**Size/Duration**: 32 atoms, ~1000 minimize + 1000 MD steps total, < 90 seconds

**Verification Checkpoints**:
1. ✅ First MD produces `restart.bin` or `restart.final.bin`
2. ✅ Second MD's `in.lammps` contains `read_restart` command
3. ✅ Second MD log shows successful restart read (no error)
4. ✅ Second MD's initial timestep/step may continue from first MD or reset to 0 (document observed behavior)
5. ✅ All three steps complete without `ERROR`

**How to Verify Restart**:
```bash
# Check in.lammps for read_restart
grep -E "read_restart|read_data" raw/<step3_ulid>/in.lammps

# Check log for restart confirmation
grep -i "restart" raw/<step3_ulid>/log.lammps | head -5
```

**Evidence to Collect**:
- `ls -la raw/<md1_ulid>/restart*`
- `cat raw/<md2_ulid>/in.lammps | head -20`
- `grep -i restart raw/<md2_ulid>/log.lammps`

---

## 4. Time Budget and Scale

| Workflow | Atoms | Steps | Expected Duration |
|----------|-------|-------|-------------------|
| A (LJ relax) | 108 | ~1000 minimize | < 30s |
| B (EAM MD) | 32 | 1000 MD | < 30s |
| C (Chain) | 32 | ~1500 total | < 60s |
| D (Restart) | 32 | ~2000 total | < 90s |

**Total estimated time**: < 4 minutes for all workflows

---

## 5. Failure Evidence Collection

If any workflow fails, collect:

### 5.1 Essential Logs
```bash
# Check resolver path
python -c "from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin; print(resolve_lammps_bin())"

# LAMMPS version
$(brew --prefix lammps)/bin/lmp -h 2>&1 | head -5

# PATH environment
echo $PATH

# Working directory tree
ls -laR raw/
```

### 5.2 If Binary Not Found
```bash
# List resolver search paths
python -c "
from qmatsuite.core.engines.lammps_resolver import LAMMPS_BIN_SEARCH_PATHS
for p in LAMMPS_BIN_SEARCH_PATHS:
    print(p)
"

# Check common locations
ls -la /opt/homebrew/opt/lammps/bin/ 2>/dev/null || echo "Not found"
ls -la /usr/local/opt/lammps/bin/ 2>/dev/null || echo "Not found"
which lmp lmp_serial lmp_mpi 2>/dev/null || echo "Not in PATH"
```

### 5.3 If Execution Fails
```bash
# Full LAMMPS log
cat raw/<step_ulid>/log.lammps

# Input script
cat raw/<step_ulid>/in.lammps

# Data file header
head -50 raw/<step_ulid>/structure.data
```

---

## 6. Execution Script Location

A single runner script should be created at:

```
tools/run_lammps_long_smoke.py
```

**Script should**:
1. Run all 4 workflows in sequence
2. Print checkpoints as pass/fail
3. Collect evidence on failure
4. Return exit code 0 if all pass, non-zero otherwise

**Usage**:
```bash
source .venv/bin/activate
python tools/run_lammps_long_smoke.py --verbose
```

**Alternative pytest marker** (if integrated into test suite):
```bash
python -m pytest tests/integration/test_lammps_chain.py -v -m long --tb=short
```

---

## 7. Self-Check Items (Not Blocking)

These are noted for later review, not required for smoke test pass:

- [ ] MATERIALIZATION_MAP completeness: verify single test covers all step types
- [ ] potential_map digest consistency with inline dict fingerprint
- [ ] species_map gate: verify LAMMPS bypasses via correct dispatch (no conditional residue)

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-20 | Auto | Initial plan created |

