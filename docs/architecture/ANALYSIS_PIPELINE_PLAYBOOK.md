# Analysis Pipeline Playbook

How to add new AnalysisObjects and extend existing ones to new engines.

---

## Overview: The Triangle Pattern

Every analysis feature requires three coordinated pieces:

```
Demo Project  ←→  AnalysisObject + Provider  ←→  Provenance (CAS + SQLite)
     ↑                    ↑                              ↑
  resources/         drivers/<engine>/           .provenance/.cas/analysis/
  demo_projects/     parsers/<type>.py           provenance/schema.py
```

1. **Demo project** — a committed scaffold that exercises the calculation end-to-end
2. **AnalysisObject + Provider** — kernel-layer code that parses raw evidence into a canonical bundle
3. **Provenance** — CAS storage + SQLite linkage, handled automatically by the pipeline

You only write (1) and (2). The pipeline handles (3) automatically.

---

## Recipe A: Add a New AnalysisObject (e.g., DOS)

### Step 1: Define the AnalysisObject class

**File:** `src/quantumvitas/core/analysis/dos.py`

```python
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, RenderMeta

@dataclass
class DOS:
    meta: AnalysisObjectMeta
    energies: np.ndarray          # shape (n_points,)
    densities: np.ndarray         # shape (n_points,) or (n_spin, n_points)
    fermi_energy: float | None

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        series = [{"label": "Total DOS", "style": "line"}]
        return CanonicalPrimitiveBundle(
            bundle_kind="canonical",
            object_type="dos",
            provenance_meta=self.meta.to_provenance_meta(),
            arrays={
                "energies": self.energies.tolist(),
                "densities": self.densities.tolist(),
            },
            series=series,
            render_meta=RenderMeta(
                x_label="Energy (eV)",
                y_label="DOS (states/eV)",
                title="Density of States",
                markers=[],
            ),
        )
```

**Invariants enforced by gate tests:**
- `meta: AnalysisObjectMeta` field required (`test_analysis_object_meta_required`)
- `to_primitives()` must accept only `self` (`test_to_primitives_is_parameterless`)
- `to_primitives()` output must be deterministic (`test_canonical_bundle_deterministic`)
- `RenderMeta` must not contain provenance fields (`test_render_meta_no_provenance`)

### Step 2: Write the engine provider

**File:** `src/quantumvitas/drivers/qe/parsers/dos.py`

```python
from quantumvitas.parsers.registry import register_parser

@register_parser("qe", "dos")
class QEDOSProvider:
    engine = "qe"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "dos.dat").exists()

    def parse(self, raw_dir, calc_dir, *, run_ulid=None, step_ulids=None,
              gen_steps=None, calc_ulid=None, evidence_steps=None, **kw) -> DOS:
        # Parse dos.dat, build DOS object, return it
        ...
```

**Key requirements:**
- Decorator: `@register_parser("engine_name", "object_type")`
- `can_parse(raw_dir) -> bool` — fast existence check on evidence files
- `parse(raw_dir, calc_dir, **kwargs) -> AnalysisObject` — parse evidence, return domain object
- Provider must live in `drivers/<engine>/parsers/` directory

### Step 3: Declare the capability on the driver

**File:** `src/quantumvitas/drivers/qe/driver.py`

```python
ANALYSIS_CAPABILITIES = [
    AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=["*.bands.dat.gnu"]),
    AnalysisCapability(object_type="dos", gen_step_sequence=["dos"], evidence_files=["dos.dat"]),  # NEW
]
```

**Fields:**
- `object_type` — must match the `@register_parser` second argument
- `gen_step_sequence` — ordered GEN step names that produce the evidence (matched contiguously against run steps)
- `evidence_files` — informational; `can_parse()` is the actual gate

**Gate test:** `test_analysis_capability_declaration` verifies every `@register_parser` has a matching `ANALYSIS_CAPABILITIES` entry.

### Step 4: Write tests

**File:** `tests/drivers/qe/parsers/test_qe_dos.py`

Test the provider in isolation:
1. Place real evidence files in `tests/data/analysis_qe_dos/` (copy from `.tmp/` research, never reference `.tmp/` in tests)
2. Test `can_parse()` returns True/False correctly
3. Test `parse()` produces correct `DOS` object
4. Test `to_primitives()` produces valid `CanonicalPrimitiveBundle`

### Step 5: Create a demo project (if golden daemon test is needed)

**Directory:** `resources/demo_projects/qe_dos_demo/`

Follow the existing demo pattern from `si_bands_demo`. The demo must include:
- `project.qv.yml` with calculation definition
- Step YAML files referencing the correct `step_type_gen` and `step_type_spec`
- All necessary input files (pseudopotentials are resolved at runtime)

### Step 6: Verify

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Gate tests will automatically verify:
- Provider has matching capability declaration
- `to_primitives()` signature is correct
- No engine branching in orchestrator
- No disk cache in analysis core
- No `.tmp/` references in runtime code

---

## Recipe B: Extend an Existing AnalysisObject to a New Engine (e.g., ABINIT bands)

This is simpler because the AnalysisObject class already exists.

### Step 1: Write the provider

**File:** `src/quantumvitas/drivers/abinit/parsers/bands.py`

```python
@register_parser("abinit", "bands")
class ABINITBandsProvider:
    engine = "abinit"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "abinit_o_EBANDS.agr").exists()

    def parse(self, raw_dir, calc_dir, **kwargs) -> BandStructure:
        # Parse ABINIT band output, return BandStructure
        ...
```

### Step 2: Declare capability

**File:** `src/quantumvitas/drivers/abinit/driver.py`

```python
ANALYSIS_CAPABILITIES = [
    AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=["*_EBANDS.agr"]),
]
```

### Step 3: Prepare test data

1. Research ABINIT output format using `.tmp/engine_research/abinit/` and `docs/engines/abinit/`
2. Run a real ABINIT calculation or obtain real output files
3. Copy evidence files to `tests/data/analysis_abinit_bands/`
4. **Never reference `.tmp/` in test code** — always use `tests/data/`

### Step 4: Write tests and verify

Same pattern as Recipe A, Step 4-6.

---

## Reference: Existing Implementations

### QE Bands (reference implementation)

| Component | File |
|-----------|------|
| AnalysisObject | `src/quantumvitas/core/analysis/band_structure.py` |
| Provider | `src/quantumvitas/drivers/qe/parsers/bands.py` |
| Capability | `src/quantumvitas/drivers/qe/driver.py` → `ANALYSIS_CAPABILITIES` |
| Demo | `resources/demo_projects/si_bands_demo/` |
| Golden test | `tests/daemon/test_si_bands_golden_daemon.py` |
| Test data | QE golden test runs QE live (no static fixtures) |

### VASP Bands (second engine, extension pattern)

| Component | File |
|-----------|------|
| Provider | `src/quantumvitas/drivers/vasp/parsers/bands.py` |
| Capability | `src/quantumvitas/drivers/vasp/driver.py` → `ANALYSIS_CAPABILITIES` |
| Demo | `resources/demo_projects/si_bands_vasp_demo/` |
| Golden test | `tests/daemon/test_vasp_bands_golden_daemon.py` |
| Test data | `tests/data/analysis_vasp_bands/` (EIGENVAL, KPOINTS, POSCAR, vasprun.xml) |

---

## Research Workflow

When adding support for a new engine's output:

1. **Research** in `.tmp/engine_research/<engine>/` — download manuals, sample outputs, run calculations
2. **Document** in `docs/engines/<engine>/` — curated index, format notes, parser design
3. **Copy evidence** to `tests/data/analysis_<engine>_<type>/` for test fixtures
4. **Never reference `.tmp/`** in source code or tests — gate test `test_no_tmp_corpus_in_runtime` enforces this

---

## Pipeline Internals (for reference, not modification)

The following files are engine-agnostic and should NOT be modified when adding engines:

| File | Role |
|------|------|
| `src/quantumvitas/core/analysis/orchestrator.py` | Capability matching + provider dispatch |
| `src/quantumvitas/core/analysis/capability.py` | `AnalysisCapability` + `find_contiguous_match()` |
| `src/quantumvitas/core/analysis/bundles.py` | `CanonicalPrimitiveBundle` + `DerivedPrimitiveBundle` |
| `src/quantumvitas/core/analysis/cas_writer.py` | CAS blob write + SQLite row write |
| `src/quantumvitas/core/analysis/base.py` | `AnalysisObjectMeta` + `SourceFileStat` |
| `src/quantumvitas/api/service.py` | `_finalize_run_analysis_pipeline()` and API handlers |
| `src/quantumvitas/parsers/registry.py` | `@register_parser` decorator + `get_parser()` lookup |

---

## Acceptance Checklist

Before merging any analysis pipeline addition:

- [ ] Provider registered with `@register_parser(engine, object_type)`
- [ ] Driver declares matching `ANALYSIS_CAPABILITIES` entry
- [ ] `to_primitives()` produces deterministic `CanonicalPrimitiveBundle`
- [ ] Test data in `tests/data/` (not `.tmp/`)
- [ ] No engine branching in orchestrator or transforms
- [ ] No imports from `quantumvitas.drivers` in `core/analysis/` (except `parsers/registry.py`)
- [ ] Full test suite passes: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- [ ] Gate tests pass: `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short`
