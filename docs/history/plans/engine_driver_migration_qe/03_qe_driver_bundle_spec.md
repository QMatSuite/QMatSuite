# QE Driver Bundle Specification

> This document specifies the target structure and design for the QE DriverBundle after migration.

## Target Directory Structure

```
src/qmatsuite/drivers/qe/
├── __init__.py                 # Driver registration + public exports
├── driver.py                   # QEDriver class (BaseEngineDriver)
├── step_types.py               # QE step type specifications
├── handler.py                  # qe_step_handler (moved from execution/)
├── recipe.py                   # QERecipe (moved from execution/)
├── engine/
│   ├── __init__.py
│   ├── qe_engine.py            # QuantumEspressoEngine (from core/engines/qe.py)
│   ├── qe_calculation.py       # QECalculationRunner (from core/engines/)
│   ├── qe_installation.py      # QEInstallation (from core/engines/)
│   ├── qe_resolver.py          # Two-state resolver (from core/engines/)
│   ├── qe_binary_locator.py    # Binary locator (from core/engines/)
│   ├── qe_diagnostics.py       # Diagnostics (from core/engines/)
│   └── qe_pseudopotentials.py  # PseudoManager (from core/engines/)
├── io/
│   ├── __init__.py
│   ├── model.py                # QEModule, QECardType, etc. (from io/model.py)
│   ├── parser.py               # QEInputParser (from io/parser/)
│   ├── generator.py            # QEInputGenerator (from io/generator/)
│   └── structure_io.py         # structure_from_qe_input (from io/)
├── ir/
│   ├── __init__.py
│   └── mapping.py              # IR↔QE mapping (from ir/backends/qe/)
├── parsers/
│   ├── __init__.py
│   └── trajectory.py           # QETrajectoryParser (from parsers/qe/)
├── data/
│   ├── __init__.py
│   └── qe_metadata.py          # QE metadata (from data/)
└── presets/
    ├── __init__.py
    └── qe_presets.py           # QE-specific preset logic (if any)
```

---

## Core Components

### 1. `drivers/qe/__init__.py`

```python
"""QE Driver Bundle.

Quantum ESPRESSO engine driver with complete I/O, IR mapping, and execution support.
"""

from qmatsuite.core.driver_registry import DriverRegistry

from .driver import QEDriver

# Register driver on import
DriverRegistry.register(QEDriver())

# Public exports (backward compatibility)
from .io.model import QEModule, QECardType, QENamelist, QECard, QEInput
from .io.parser import QEInputParser
from .io.generator import QEInputGenerator
from .io.structure_io import structure_from_qe_input
from .engine.qe_engine import QuantumEspressoEngine
from .recipe import QERecipe
from .handler import qe_step_handler

__all__ = [
    "QEDriver",
    "QEModule",
    "QECardType",
    "QENamelist",
    "QECard",
    "QEInput",
    "QEInputParser",
    "QEInputGenerator",
    "structure_from_qe_input",
    "QuantumEspressoEngine",
    "QERecipe",
    "qe_step_handler",
]
```

### 2. `drivers/qe/driver.py`

```python
"""QE Driver implementation."""

from qmatsuite.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy

from .step_types import QE_STEP_TYPE_SPECS


class QEDriver(BaseEngineDriver):
    """Quantum ESPRESSO driver bundle.

    Provides:
    - Step type specifications for all QE calculation types
    - Handler for step execution
    - Recipe for JobGraph materialization
    - Materialization map for GEN_* → qe_* type conversion
    - WorkdirPolicy.SHARED for shared outdir model
    """

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO"

    @property
    def driver_api_version(self) -> str:
        return "2.0.0"  # Bumped from shim's 1.0.0

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return QE step type specifications."""
        return QE_STEP_TYPE_SPECS

    def get_handler(self):
        """Return QE step handler."""
        from .handler import qe_step_handler
        return qe_step_handler

    def get_recipe_class(self):
        """Return QE recipe class."""
        from .recipe import QERecipe
        return QERecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return GEN_* to qe_* materialization mappings."""
        return {
            "GEN_SCF": "qe_scf",
            "GEN_RELAX": "qe_relax",
            "GEN_BANDS": "qe_bands_pw",
            "GEN_DOS": "qe_dos",
            "GEN_NSCF": "qe_nscf",
            "GEN_PH": "qe_ph",
            "GEN_MD": "qe_md",
        }

    def get_workdir_policy(self) -> WorkdirPolicy:
        """QE uses shared outdir model."""
        return WorkdirPolicy.SHARED

    def get_default_structure_kind(self) -> str:
        """QE defaults to periodic structures."""
        return "periodic"

    def get_supported_presets(self) -> list[str]:
        """QE supports these preset dimensions."""
        return ["precision", "magnetism", "occupations_scheme", "convergence"]
```

### 3. `drivers/qe/step_types.py`

```python
"""QE step type specifications."""

from qmatsuite.core.driver_protocol import StepTypeSpec


QE_STEP_TYPE_SPECS: list[StepTypeSpec] = [
    # pw.x step types
    StepTypeSpec(
        id="qe_scf",
        engine="qe",
        executable="pw.x",
        description="QE SCF calculation",
        public_type="scf",
        requires_structure=True,
        produces_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_relax",
        engine="qe",
        executable="pw.x",
        description="QE relaxation",
        public_type="relax",
        requires_structure=True,
        is_structure_transform=True,
    ),
    StepTypeSpec(
        id="qe_vc_relax",
        engine="qe",
        executable="pw.x",
        description="QE variable-cell relaxation",
        public_type="vc-relax",
        requires_structure=True,
        is_structure_transform=True,
    ),
    StepTypeSpec(
        id="qe_nscf",
        engine="qe",
        executable="pw.x",
        description="QE non-self-consistent calculation",
        public_type="nscf",
        requires_structure=True,
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_bands_pw",
        engine="qe",
        executable="pw.x",
        description="QE band structure (pw.x)",
        public_type="bands_pw",
        requires_structure=True,
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_md",
        engine="qe",
        executable="pw.x",
        description="QE molecular dynamics",
        public_type="md",
        requires_structure=True,
    ),
    StepTypeSpec(
        id="qe_vc_md",
        engine="qe",
        executable="pw.x",
        description="QE variable-cell molecular dynamics",
        public_type="vc-md",
        requires_structure=True,
    ),

    # Post-processing executables
    StepTypeSpec(
        id="qe_dos",
        engine="qe",
        executable="dos.x",
        description="QE density of states",
        public_type="dos",
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_bands",
        engine="qe",
        executable="bands.x",
        description="QE band structure post-processing",
        public_type="bands",
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_pdos",
        engine="qe",
        executable="projwfc.x",
        description="QE projected density of states",
        public_type="pdos",
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_pp",
        engine="qe",
        executable="pp.x",
        description="QE post-processing",
        public_type="pp",
        requires_charge_density=True,
    ),

    # Phonon executables
    StepTypeSpec(
        id="qe_ph",
        engine="qe",
        executable="ph.x",
        description="QE phonon calculation",
        public_type="ph",
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_q2r",
        engine="qe",
        executable="q2r.x",
        description="QE q2r transformation",
        public_type="q2r",
    ),
    StepTypeSpec(
        id="qe_matdyn",
        engine="qe",
        executable="matdyn.x",
        description="QE matdyn calculation",
        public_type="matdyn",
    ),
    StepTypeSpec(
        id="qe_dynmat",
        engine="qe",
        executable="dynmat.x",
        description="QE dynmat calculation",
        public_type="dynmat",
    ),

    # Other executables
    StepTypeSpec(
        id="qe_plotband",
        engine="qe",
        executable="plotband.x",
        description="QE band plotting",
        public_type="plotband",
    ),
    StepTypeSpec(
        id="qe_hp",
        engine="qe",
        executable="hp.x",
        description="QE Hubbard parameters",
        public_type="hp",
        requires_charge_density=True,
    ),
    StepTypeSpec(
        id="qe_pw2wannier90",
        engine="qe",
        executable="pw2wannier90.x",
        description="QE to Wannier90 interface",
        public_type="pw2wannier90",
        requires_charge_density=True,
    ),

    # Escape hatch
    StepTypeSpec(
        id="qe_custom",
        engine="qe",
        executable="pw.x",
        description="Custom QE step type",
        public_type="custom",
        requires_structure=True,
    ),

    # W90 preprocessing (runs within QE context but uses wannier90.x)
    # NOTE: This could move to W90 driver after migration
    StepTypeSpec(
        id="w90_preproc",
        engine="qe",  # Keep as QE for now (backward compat)
        executable="wannier90.x",
        description="Wannier90 preprocessing",
        public_type="w90_preproc",
        requires_structure=True,
    ),
]
```

---

## Migration Contracts

### Contract 1: Public API Preservation
```python
# These imports must continue to work after migration:
from qmatsuite.io import QEModule, QECardType, QEInput
from qmatsuite.io import QEInputParser, QEInputGenerator
from qmatsuite.io import structure_from_qe_input

# Achieved via re-exports in io/__init__.py:
from qmatsuite.drivers.qe.io.model import QEModule, QECardType, ...
```

### Contract 2: DriverRegistry Integration
```python
# All QE operations must go through DriverRegistry:
from qmatsuite.core.driver_registry import DriverRegistry

# Get handler for step type
handler = DriverRegistry.get_handler("qe_scf")

# Get recipe for engine
recipe_class = DriverRegistry.get_recipe_class("qe")

# Materialize step type
machine_type = DriverRegistry.materialize_step_type("qe", "GEN_SCF")
# Returns: "qe_scf"
```

### Contract 3: Workdir Policy
```python
# QE uses shared outdir model (WorkdirPolicy.SHARED)
# All jobs share same calc/raw/ directory
# Scratch files go to calc/raw/outdir/
```

### Contract 4: IR Mapping
```python
# IR compilation must produce identical QE input
from qmatsuite.drivers.qe.ir.mapping import ir_to_qe_param

# This must work exactly as before:
qe_module, qe_section, qe_key, qe_value = ir_to_qe_param("ecutwfc", 50.0)
# Returns: ("pw", "SYSTEM", "ecutwfc", 50.0)
```

---

## Managed Runtime Parameters

### Parameters Managed by QE Driver (not user-configurable in step.yaml)

| Parameter | Location | Value | Reason |
|-----------|----------|-------|--------|
| `prefix` | CONTROL | `"qms"` or `calc_slug` | Workspace isolation |
| `outdir` | CONTROL | `"./outdir"` | Constitution §F |
| `pseudo_dir` | CONTROL | `"./pseudo"` or project pseudo | Pseudo resolution |
| `wfcdir` | CONTROL | `"./outdir"` | With outdir |
| `tmp_dir` | CONTROL | `"./outdir"` | With outdir |

### User-Configurable Parameters

All other parameters can be set in step.yaml and are not overwritten:
- `ecutwfc`, `ecutrho` - Energy cutoffs
- `nspin`, `noncolin`, `lspinorb` - Magnetism
- `occupations`, `smearing`, `degauss` - Occupations
- `calculation` - Calculation type (implicit from step_type)
- etc.

---

## Testing Requirements

### Unit Tests
- `test_qe_driver.py` - Driver registration, step type lookup
- `test_qe_step_types.py` - Step type spec validation
- `test_qe_handler.py` - Handler execution (mocked engine)
- `test_qe_recipe.py` - JobGraph materialization
- `test_qe_io_model.py` - QE I/O models
- `test_qe_ir_mapping.py` - IR↔QE mapping

### Integration Tests
- `test_qe_scf_e2e.py` - Full SCF calculation
- `test_qe_relax_e2e.py` - Relax with artifact generation
- `test_qe_bands_e2e.py` - Bands workflow (SCF → NSCF → bands)
- `test_qe_phonon_e2e.py` - Phonon workflow (SCF → PH → Q2R → MATDYN)
- `test_qe_w90_e2e.py` - Wannier90 workflow (SCF → NSCF → W90)

### Backward Compatibility Tests
- Existing test files must pass without modification
- Import paths must continue to work
- Legacy calculation.yaml files must execute correctly

---

## File Movement Summary

| Source | Destination |
|--------|-------------|
| `drivers/qe_shim/__init__.py` | DELETE (replaced by driver.py) |
| `core/engines/qe.py` | `drivers/qe/engine/qe_engine.py` |
| `core/engines/qe_calculation.py` | `drivers/qe/engine/qe_calculation.py` |
| `core/engines/qe_installation.py` | `drivers/qe/engine/qe_installation.py` |
| `core/engines/qe_resolver.py` | `drivers/qe/engine/qe_resolver.py` |
| `core/engines/qe_binary_locator.py` | `drivers/qe/engine/qe_binary_locator.py` |
| `core/engines/qe_diagnostics.py` | `drivers/qe/engine/qe_diagnostics.py` |
| `core/engines/qe_pseudopotentials.py` | `drivers/qe/engine/qe_pseudopotentials.py` |
| `engine/qe_engine.py` | `drivers/qe/engine/qe_wrapper.py` |
| `execution/handlers.py` (qe handler) | `drivers/qe/handler.py` |
| `execution/recipes.py` (QERecipe) | `drivers/qe/recipe.py` |
| `io/model.py` | `drivers/qe/io/model.py` |
| `io/parser/qe_parser.py` | `drivers/qe/io/parser.py` |
| `io/generator/qe_generator.py` | `drivers/qe/io/generator.py` |
| `io/structure_io.py` (QE parts) | `drivers/qe/io/structure_io.py` |
| `ir/backends/qe/mapping.py` | `drivers/qe/ir/mapping.py` |
| `parsers/qe/trajectory.py` | `drivers/qe/parsers/trajectory.py` |
| `data/qe_metadata.py` | `drivers/qe/data/qe_metadata.py` |

---

## Deprecation Timeline

### Phase 1 (Immediate)
- Create driver bundle at new location
- Update DriverRegistry to use new locations
- Add re-exports for backward compatibility

### Phase 2 (Warning Period)
- Add deprecation warnings for direct imports from old locations
- Document new import paths

### Phase 3 (Removal)
- Delete old file locations
- Remove deprecation shims
- Finalize all imports to new paths
