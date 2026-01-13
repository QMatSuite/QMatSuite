# ORCA Integration Specification

**Version**: 1.0
**Date**: 2026-01-13
**Status**: Implemented (MVP)
**Test Coverage**: 67 tests (48 unit + 19 integration)

---

## 1. Overview

### 1.1 Goal

Integrate ORCA as a molecular quantum chemistry engine in QMatSuite:
- Enable molecular calculations (HF, DFT, TDDFT)
- Support ORCA's strong-chain execution model
- Provide property parsing from ORCA output files

### 1.2 ORCA Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Execution Model** | External binary (subprocess) |
| **License** | Free for academic use (requires registration) |
| **System Kind** | Molecular only (no periodic boundary conditions) |
| **Chain Model** | Strong-chain (one ORCA job per chain, no `$new_job`) |

### 1.3 Key Design Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Strong-chain execution | ORCA's compound job (`$new_job`) is fragile; single-job chains are more reliable |
| D2 | No JSON property output | ORCA doesn't support JSON output; parse `.property.txt` files |
| D3 | Keyword fusion | SCF + TD fused into single input file with combined keywords |
| D4 | Chain-atomic execution | All steps in a chain succeed or fail together |

---

## 2. Architecture

### 2.1 Module Structure

```
src/quantumvitas/
├── core/engines/
│   └── orca_resolver.py       # ORCA binary path resolution
├── engine/
│   ├── orca_engine.py         # ORCAEngine implementation
│   └── qc_engine_base.py      # QCChain and chain detection
└── engines/orca/
    ├── __init__.py
    ├── property_parser.py     # .property.txt parser
    └── input_compiler.py      # ORCA input file generator
```

### 2.2 Execution Flow

```
[QCChain] → [ORCAInputCompiler] → [.inp file]
                                       ↓
                               [ORCA binary]
                                       ↓
                            [.out, .gbw, .property.txt]
                                       ↓
                           [PropertyParser] → [StepResult]
```

### 2.3 Chain Detection

Chains are identified by SCF-root steps:

```python
SCF_ROOT_TYPES = {"scf", "hf"}  # Steps that start new chains

@dataclass
class QCChain:
    scf_root: Step          # Root SCF/HF step
    downstream: List[Step]  # Dependent steps (TD, MP2, etc.)
    key: str                # Chain identifier (e.g., "chain01_scf_td")
```

**Example chains:**
- `[scf]` → `chain01_scf`
- `[scf, td]` → `chain01_scf_td`
- `[hf, td]` → `chain01_hf_td`

---

## 3. Step Types

### 3.1 ORCA_SCF

DFT or HF single-point calculation.

```python
"orca_scf": StepTypeSpec(
    id="scf",
    machine_type="orca_scf",
    engine="orca",
    executable="orca",
    description="ORCA DFT/HF single-point calculation",
    supports_incremental_skip=True,  # Via AutoStart
    consumes_state=None,
    produces_state="gbw",  # Wavefunction file
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `functional` | str | "B3LYP" | DFT functional |
| `basis` | str | "def2-SVP" | Basis set |
| `ri` | bool | False | Use RI approximation |
| `rijcosx` | bool | False | Use RIJCOSX approximation |
| `nprocs` | int | 1 | Number of parallel processes |

### 3.2 ORCA_HF

Explicit Hartree-Fock calculation.

```python
"orca_hf": StepTypeSpec(
    id="hf",
    machine_type="orca_hf",
    engine="orca",
    executable="orca",
    description="ORCA Hartree-Fock calculation",
    supports_incremental_skip=True,
    consumes_state=None,
    produces_state="gbw",
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `basis` | str | "def2-SVP" | Basis set |

### 3.3 ORCA_TD

TDDFT/CIS excited states calculation.

```python
"orca_td": StepTypeSpec(
    id="td",
    machine_type="orca_td",
    engine="orca",
    executable="orca",
    description="ORCA TDDFT/CIS excited states",
    supports_incremental_skip=False,
    consumes_state="gbw",
    produces_state=None,
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nroots` | int | 5 | Number of excited states |
| `tda` | bool | True | Use Tamm-Dancoff approximation |
| `triplets` | bool | False | Calculate triplet states |

---

## 4. Workflow Templates

### 4.1 Available Workflows

| Workflow ID | Steps | Description |
|-------------|-------|-------------|
| `scf` | `[scf]` | Single-point DFT/HF calculation |
| `scf_td` | `[scf, td]` | Ground state + excited states |

### 4.2 Materialization

Workflow templates use public step keys. Materialization converts them to ORCA-specific types:

```python
# MATERIALIZATION_MAP entries
("orca", "SCF"): "orca_scf",
("orca", "HF"): "orca_hf",
("orca", "TD"): "orca_td",
```

**Example:**
```python
# Workflow template
workflow = WorkflowTemplate(
    id="scf_td",
    step_sequence=("scf", "td"),  # Public keys
)

# Materialized for ORCA
machine_steps = ["orca_scf", "orca_td"]
```

---

## 5. Input Compilation

### 5.1 Keyword Fusion

The input compiler fuses all chain steps into a single ORCA input:

```python
class ORCAInputCompiler:
    def compile(self, chain: QCChain, molecule, fresh=False) -> str:
        # 1. Collect keywords from SCF root
        keywords = {functional, basis, "TightSCF"}

        # 2. Add blocks from downstream steps
        blocks = {}
        for step in chain.downstream:
            if step.type == "td":
                blocks["tddft"] = "NRoots 5\nTDA true"

        # 3. Generate single input file
        return format_input(keywords, blocks, molecule)
```

### 5.2 Example Inputs

**SCF Only:**
```
# Chain: chain01_scf
# Generated by QMatSuite

! B3LYP def2-SVP TightSCF

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

**SCF + TD:**
```
# Chain: chain01_scf_td
# Generated by QMatSuite

! B3LYP def2-SVP TightSCF

%tddft
  NRoots 5
  TDA true
end

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

---

## 6. Property Parsing

### 6.1 Property File Format

ORCA 6.x generates `.property.txt` files with typed values:

```
$SCF_Energy
 &Type Float
 &Dim 0
 &RowDim 0
 &ColDim 0
  Geometry_Index                                    0
  Prop_Index                                        1
  -76.026578563
$End

$CIS_Energies
 &Type FloatArray
 &Dim 1
 &RowDim 3
 &ColDim 0
  Geometry_Index                                    0
  Prop_Index                                        1
  0.3124516  0.3789123  0.4215678
$End
```

### 6.2 Parser API

```python
from quantumvitas.engines.orca.property_parser import (
    parse_orca_property_txt,
    get_energy,
    is_converged,
    get_tddft_excitations,
)

# Parse file
props = parse_orca_property_txt(Path("calc.property.txt"))

# Extract values
energy = get_energy(props)  # Total energy in Hartree
converged = is_converged(props)  # SCF convergence status
excitations = get_tddft_excitations(props)  # Excitation energies in eV
```

---

## 7. Engine Configuration

### 7.1 Path Resolution

ORCA binary is resolved in order:
1. `QMATSUITE_ORCA_BIN` environment variable
2. Repo-relative `.qmatsuite/engines/orca/` directory
3. User's `~/.qmatsuite/engines/orca/` directory

```python
from quantumvitas.core.engines.orca_resolver import resolve_orca_bin

orca_path = resolve_orca_bin()  # Returns Path to orca binary
```

### 7.2 Engine Registration

ORCA is automatically registered if available:

```python
from quantumvitas.engine.registry import create_default_registry

registry = create_default_registry()
if registry.has("orca"):
    engine = registry.get("orca")
    available, version = engine.probe()
```

---

## 8. Artifacts

### 8.1 Chain Artifacts

Each chain produces artifacts in its directory:

```
calc/raw/chains/chain01_scf_td/
├── chain01_scf_td.inp          # ORCA input file
├── chain01_scf_td.out          # ORCA output (stdout)
├── chain01_scf_td.property.txt # Property file (parsed)
├── chain01_scf_td.gbw          # Wavefunction (binary)
└── chain_manifest.json         # Execution metadata
```

### 8.2 Step Results

```python
@dataclass
class ORCAStepResult:
    step_id: str
    success: bool
    metrics: Dict[str, Any]  # energy, excitation_energies, etc.
    artifacts: Dict[str, str]  # Paths to output files
```

---

## 9. Testing

### 9.1 Test Structure

```
tests/
├── unit/orca/
│   ├── test_property_parser.py   # 14 tests
│   ├── test_chain_detection.py   # 14 tests
│   ├── test_input_compiler.py    # 11 tests
│   └── test_orca_engine.py       # 9 tests
├── integration/orca/
│   ├── test_orca_execution.py    # 10 tests
│   └── test_system_integration.py # 8 tests
└── fixtures/orca/
    ├── water_scf.property.txt
    ├── water_scf_td.property.txt
    └── water_scf.out
```

### 9.2 Running Tests

```bash
# Unit tests (no ORCA required)
pytest tests/unit/orca/ -v

# Integration tests (requires ORCA)
export QMATSUITE_ORCA_BIN=/path/to/orca
pytest tests/integration/orca/ -v -m integration

# All ORCA tests
pytest tests/unit/orca/ tests/integration/orca/ -v
```

---

## 10. Future Enhancements

| Feature | Priority | Description |
|---------|----------|-------------|
| ORCA_OPT | High | Geometry optimization |
| ORCA_FREQ | High | Frequency calculation (IR/Raman) |
| ORCA_MP2 | Medium | MP2 correlation energy |
| ORCA_CCSD | Low | Coupled cluster methods |
| Multi-job chains | Low | Support `$new_job` for complex workflows |

---

## Appendix A: ORCA Version Compatibility

| ORCA Version | Status | Notes |
|--------------|--------|-------|
| 6.0.x | Supported | Tested with 6.0.0 |
| 6.1.x | Supported | Primary development version |
| 5.x | Untested | May work with adjustments |

---

## Appendix B: Common Issues

### B.1 ORCA Not Found

```
RuntimeError: ORCA not found. Checked:
  - Environment variable QMATSUITE_ORCA_BIN (not set)
  - Bundled locations: ~/.qmatsuite/engines/orca
```

**Solution:** Set `QMATSUITE_ORCA_BIN` or install ORCA to bundled location.

### B.2 OpenMPI Issues

ORCA requires OpenMPI for parallel execution. Ensure `LD_LIBRARY_PATH` includes ORCA's lib directory:

```bash
export LD_LIBRARY_PATH=/path/to/orca/lib:$LD_LIBRARY_PATH
```

### B.3 Property File Empty

If `.property.txt` is empty or missing, check:
1. ORCA execution completed successfully (check `.out` file)
2. ORCA version is 6.x (older versions may not generate property files)
