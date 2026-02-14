# Analysis Pipeline Playbook

**READ THIS ENTIRE SECTION BEFORE WRITING ANY CODE.**

---

## MANDATORY PREREQUISITES (read every time)

### 1. Environment

```bash
# Always activate venv first
source .venv/bin/activate

# Full test suite — ALWAYS use parallel
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Single-file targeted test (parallel optional)
python -m pytest tests/drivers/<engine>/test_<engine>_<type>_parser.py -v --tb=short
```

Never use `-x -q --tb=line` for full suite runs. The parallel flags are mandatory — the test suite is large and serial execution is unacceptably slow.

### 2. Engine Binaries — Find the Real Engine

Before writing ANY parser, you MUST locate the real engine binary and use it to generate test fixtures. Engines are installed at:

| Location | Engines |
|----------|---------|
| `<repo>/.qmatsuite/engines/vasp/vasp.6.5.0/bin/` | VASP (`vasp_std`) |
| `<repo>/.qmatsuite/engines/qe/q-e-qe-7.5/bin/` | QE (`pw.x`, `bands.x`, `dos.x`, `projwfc.x`, `neb.x`, ...), Wannier90 (`wannier90.x`) |
| `<repo>/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/` | ORCA (`orca`) |
| `<repo>/.qmatsuite/engines/abinit/10.4.7/bin/` | ABINIT (`abinit`) |
| `<repo>/.qmatsuite/engines/gaussian/gaussian09/g09/` | Gaussian (`g09`) |
| `<repo>/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/` | QMCPACK (`qmcpack`) |
| `<repo>/.qmatsuite/engines/yambo/yambo-5.3.0/bin/` | Yambo (`yambo`) |
| `/opt/homebrew/bin/` | LAMMPS (`lmp_serial`), CP2K (`cp2k.psmp`) |
| `/opt/homebrew/Caskroom/miniforge/base/bin/` | Siesta (`siesta`), xTB (`xtb`), Psi4 (`psi4`) |
| `.venv/` (pip) | GPAW (`import gpaw`, v25.7.0), PySCF (`import pyscf`, v2.12.0) |

All 15 registered engines are available locally. `<repo>` = QMatSuite repository root.

**HARD RULE: If you cannot find the real engine binary, STOP and ask the user.** Do NOT fall back to inventing/synthesizing artifacts. Every test fixture must come from a real engine run or from existing curated golden examples.

### 3. Existing Resources (check before running new calculations)

Before running a new calculation, check if golden examples already exist:

| Resource | Path | Content |
|----------|------|---------|
| Golden examples | `docs/engines/<engine>/` | Curated samples, recipes, SOURCES.md |
| Research corpus | `.tmp/engine_research/<engine>/` | Raw downloads, web crawls, normalized samples, real runs |
| Existing fixtures | `tests/data/analysis_<engine>_<type>/` | Committed test data from prior work |
| Curated input samples | `tests/inputformat/samples/<engine>/` | Input files for various calculation types |

If curated golden examples already exist in `docs/engines/<engine>/` with the output files you need, you do NOT need to run the engine again. Copy the relevant artifacts to `tests/data/`.

### 4. Test Data Provenance — NEVER Synthesize

**HARD RULE: All test fixtures must be real engine output.** Not synthetic. Not hand-crafted. Not "plausible-looking" data you wrote by hand.

- Run the real engine to produce output files
- Trim/minimize real output for file size (e.g., fewer k-points, smaller grid, short MD)
- Copy real output to `tests/data/analysis_<engine>_<type>/`
- Never reference `.tmp/` in test code — gate test `test_no_tmp_corpus_in_runtime` enforces this
- Document fixture provenance in test file docstring: `"""Tests for <engine> <type> parser using real <engine> fixture output."""`

### 5. Provider API — Use EvidenceBundle

All NEW providers MUST use the `EvidenceBundle` API (not ad-hoc keyword arguments):

```python
def parse(self, evidence: EvidenceBundle) -> AnalysisObject:
```

The QE trajectory parser has an older signature (`raw_dir, calc_dir, **kwargs`) — this is a known debt, not a pattern to follow.

---

## How the Pipeline Works

### The Triangle Pattern

```
Driver declares            Parser registered in          Orchestrator dispatches
ANALYSIS_CAPABILITIES  ->  @register_parser registry  -> run_post_run_analysis()
     |                           |                              |
  driver.py              parsers/<type>.py              orchestrator.py (DO NOT MODIFY)
```

You only write the driver capability declaration and the parser. The orchestrator handles dispatch automatically.

### Data Flow

```
Engine Run Completes
    |
    v
driver.ANALYSIS_CAPABILITIES  -- declares what this engine can analyze
    |
    v
orchestrator: enumerate_all_matches(capabilities, ordered_done_steps)
    |               ↑ Domain A: DONE steps only (incl. reused-skipped; provenance)
    |               ↑ Domain B: full SSOT step list (UI, GEN-first, step-scoped)
    v
list[AnalysisInstance]  -- multiple matches per object_type allowed
    |
    v  (for each instance)
get_parser(engine, object_type)  -- from @register_parser registry
    |
    v
provider.can_parse(raw_dir) -> bool
    |                           (False → MISSING_EVIDENCE)
    v
provider.parse(evidence: EvidenceBundle) -> AnalysisObject
    |                           (exception → PARSER_ERROR)
    v
analysis_object.to_primitives() -> CanonicalPrimitiveBundle  (→ OK)
    |
    v
CAS storage + SQLite linkage (automatic, keyed by step_ulids)
```

See `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` §5.3–§5.9 for matching domains, multi-match rules, result states, GEN-first semantics, engine effective-sequence selection (§5.4.9), and reused-skipped step inclusion.

### Registration Chain

For `@register_parser` to fire, the import chain must be complete:

```
drivers/<engine>/__init__.py
    imports: from . import parsers
        -> parsers/__init__.py
            imports: from .<type> import <Engine><Type>Provider
                -> @register_parser("<engine>", "<type>") fires
```

---

## Recipe A: Extend an Existing AnalysisObject to a New Engine

This is the most common task — e.g., adding trajectory support for CP2K when `Trajectory` already exists. Follow VASP trajectory as the template.

### Step 1: Research the Engine Output Format

1. Check `docs/engines/<engine>/` for existing curated examples and format documentation
2. Check `.tmp/engine_research/<engine>/` for prior research (normalized samples, real runs)
3. Check `tests/inputformat/samples/<engine>/` for relevant input files
4. Search the web for "<engine> <output_file> format specification"
5. Read the engine manual for output file documentation

**Record your research** in `.tmp/engine_research/<engine>/WORKLOG.md` (append-only).

### Step 2: Generate Real Test Fixtures

1. Find the engine binary (see [Engine Binaries](#2-engine-binaries--find-the-real-engine) above)
2. **If golden examples already exist** in `docs/engines/<engine>/` with needed output files, copy from there
3. **Otherwise**, run a minimal real calculation:
   - Use the smallest system that exercises the feature (e.g., 2-atom Si for relax, LJ melt for LAMMPS MD)
   - Use minimal parameters (few steps, small grid, few k-points)
   - Goal: real output, small file size (< 200KB total per fixture directory)
4. Copy output files to `tests/data/analysis_<engine>_<type>/`
5. **If you cannot find the engine binary and no golden examples exist: STOP and ask the user**

**Material system convention:** Use Silicon (Si) for periodic engines, water (H2O) for molecular engines, LJ argon for classical MD. This keeps fixtures consistent across engines.

### Step 3: Write the Provider

**File:** `src/quantumvitas/drivers/<engine>/parsers/<type>.py`

Follow the VASP template structure:

```python
"""<Engine> <type> analysis provider."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.<domain_model> import <AnalysisObject>
from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)


def parse_<engine>_<format>(path: Path) -> dict:
    """Standalone parse function (reusable, no class state)."""
    # Parse the engine output file into a raw dict
    # This function should be stdlib + numpy only
    ...


@register_parser("<engine>", "<type>")
class <Engine><Type>Provider:
    """<Engine> <type> analysis provider."""

    engine = "<engine>"
    object_type = "<type>"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the raw directory contains parseable output."""
        return (raw_dir / "<primary_file>").exists()

    def parse(self, evidence: EvidenceBundle) -> <AnalysisObject>:
        """Parse engine output into canonical analysis object."""
        raw_dir = evidence.primary_raw_dir
        source_files = []
        warnings = []

        # 1. Parse primary file
        primary_path = raw_dir / "<primary_file>"
        source_files.append(SourceFileStat.from_path(primary_path, evidence.calc_dir))
        parsed = parse_<engine>_<format>(primary_path)

        # 2. Optional: parse fallback / auxiliary files

        # 3. Build domain objects (Frame, BandStructure, DOS, etc.)
        #    - Convert units at parse time (Ha->eV, Bohr->A, etc.)
        #    - Convert coordinates at parse time (frac->Cart, etc.)

        # 4. Build metadata
        meta = AnalysisObjectMeta.create(
            object_type="<type>",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="<engine>_<type>",
            parser_version="1.0",
            warnings=warnings,
        )

        # 5. Return canonical object
        return <AnalysisObject>(meta=meta, ...)
```

**Key architectural rules:**
- **Standalone parse functions** separate from the provider class (reusable, testable in isolation)
- **Primary + fallback** file strategy (e.g., vasprun.xml primary, XDATCAR fallback)
- **Unit conversion at parse time** — all canonical objects use eV, Angstrom, GPa
- **Coordinate conversion at parse time** — all positions as Cartesian Angstrom
- **No engine imports in core/analysis/** — provider lives in drivers/<engine>/parsers/
- **Memory management** — use iterparse for XML, line-by-line for text, lazy for binary

### Step 4: Wire the Registration

**Edit:** `src/quantumvitas/drivers/<engine>/parsers/__init__.py`

```python
from .<type> import <Engine><Type>Provider  # triggers @register_parser
```

**Verify:** `src/quantumvitas/drivers/<engine>/__init__.py` must have `from . import parsers`.

### Step 5: Declare ANALYSIS_CAPABILITIES

**Edit:** `src/quantumvitas/drivers/<engine>/driver.py`

```python
from quantumvitas.core.analysis.capability import AnalysisCapability

class <Engine>Driver(BaseEngineDriver):
    ANALYSIS_CAPABILITIES = [
        # ... existing capabilities ...
        AnalysisCapability(
            object_type="<type>",
            gen_step_sequence=["<gen_step>"],
            evidence_files=["<primary_file>"],
        ),
    ]
```

**One-Provider-Multiple-Trigger pattern:** If the same parser handles multiple gen_steps (e.g., convergence for scf/relax/md, trajectory for relax/md), add multiple `AnalysisCapability` entries pointing to the same `object_type`.

### Step 6: Write Tests

**File:** `tests/drivers/<engine>/test_<engine>_<type>_parser.py`

Follow the 7-test template used by ALL existing parsers:

```python
"""Tests for <engine> <type> parser using real <engine> fixture output."""
from pathlib import Path
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.<engine>.parsers.<type> import <Engine><Type>Provider

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_<engine>_<type>"

def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["<gen_step>"],
        engine_name="<engine>",
        evidence_steps=[],
    )

# 1. can_parse positive
def test_can_parse_true():
    provider = <Engine><Type>Provider()
    assert provider.can_parse(FIXTURE_DIR)

# 2. can_parse negative
def test_can_parse_false(tmp_path):
    provider = <Engine><Type>Provider()
    assert not provider.can_parse(tmp_path)

# 3. parse returns correct type
def test_parse_returns_<type>():
    provider = <Engine><Type>Provider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, <AnalysisObject>)
    assert result.meta.object_type == "<type>"
    assert result.meta.engine_name == "<engine>"

# 4. Shape / dimension tests
def test_<type>_shapes():
    ...  # array shapes, frame counts, etc.

# 5. Physics validation
def test_<type>_physics():
    ...  # energy ranges, monotonicity, non-negativity, etc.

# 6. to_primitives produces valid bundle
def test_to_primitives_valid():
    provider = <Engine><Type>Provider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "<type>"

# 7. SHA determinism
def test_sha_deterministic():
    provider = <Engine><Type>Provider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
```

**Additional test patterns by object type:**

| Object Type | Extra Tests |
|-------------|------------|
| **bands** | k-distance monotonicity, high-sym labels, reciprocal space, fermi energy, PROCAR/fatbands if applicable |
| **dos** | energy range spans Fermi, non-negative DOS, spin-polarized shape, PDOS shapes/labels if applicable |
| **convergence** | algorithm detection, converged flag, ionic/SCF step counts |
| **trajectory** | frame count, position shapes, energy per frame, forces present, fallback path, trajectory type detection |
| **field3d** | grid shape, field kind, primitive-by-reference (no grid_data in bundle) |

### Step 7: Verify

```bash
# Targeted test
source .venv/bin/activate && python -m pytest tests/drivers/<engine>/test_<engine>_<type>_parser.py -v --tb=short

# Gate tests
python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short

# Full suite (MANDATORY before commit)
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Recipe B: Add a New AnalysisObject (Rare)

Only needed when the domain object class doesn't exist yet (e.g., adding `Trajectory` for the first time). Follow the same steps as Recipe A, but first:

### Step 0: Define the AnalysisObject Class

**File:** `src/quantumvitas/core/analysis/<type>/model.py`

Requirements:
- `meta: AnalysisObjectMeta` field (enforced by gate test)
- `to_primitives(self) -> CanonicalPrimitiveBundle` method (parameterless, enforced by gate test)
- `to_dict()` / `from_dict()` for JSON round-trip
- Deterministic `to_primitives()` output (enforced by gate test)

Then proceed with Recipe A for the first engine (use VASP as template if periodic, ORCA if molecular).

---

## Template: VASP Analysis Pipeline (Reference Implementation)

VASP is the most complete engine with 6 registered parsers. Use it as the gold standard.

### VASP Parser Inventory

| Parser | File | Registration | Evidence |
|--------|------|-------------|----------|
| scf_digest | `parsers/output.py` | `@register_parser("vasp", "scf_digest")` | vasprun.xml / OUTCAR |
| bands | `parsers/bands.py` | `@register_parser("vasp", "bands")` | EIGENVAL + KPOINTS + POSCAR |
| dos | `parsers/dos.py` | `@register_parser("vasp", "dos")` | DOSCAR + POSCAR |
| convergence | `parsers/convergence.py` | `@register_parser("vasp", "convergence")` | OSZICAR |
| trajectory | `parsers/trajectory.py` | `@register_parser("vasp", "trajectory")` | vasprun.xml / XDATCAR+OSZICAR |
| field3d | `parsers/field3d.py` | `@register_parser("vasp", "field3d")` | CHGCAR / LOCPOT / ELFCAR |

### VASP ANALYSIS_CAPABILITIES

```python
ANALYSIS_CAPABILITIES = [
    AnalysisCapability(object_type="bands",       gen_step_sequence=["bandspw"], evidence_files=["EIGENVAL"]),
    AnalysisCapability(object_type="dos",          gen_step_sequence=["dos"],     evidence_files=["DOSCAR"]),
    AnalysisCapability(object_type="convergence",  gen_step_sequence=["scf"],     evidence_files=["OSZICAR"]),
    AnalysisCapability(object_type="convergence",  gen_step_sequence=["relax"],   evidence_files=["OSZICAR"]),
    AnalysisCapability(object_type="convergence",  gen_step_sequence=["md"],      evidence_files=["OSZICAR"]),
    AnalysisCapability(object_type="trajectory",   gen_step_sequence=["relax"],   evidence_files=["vasprun.xml"]),
    AnalysisCapability(object_type="trajectory",   gen_step_sequence=["md"],      evidence_files=["vasprun.xml"]),
    AnalysisCapability(object_type="field3d",      gen_step_sequence=["scf"],     evidence_files=["CHGCAR"]),
]
```

### VASP Test Data Inventory

| Directory | Type | Files | Origin |
|-----------|------|-------|--------|
| `tests/data/analysis_vasp_bands/` | bands | EIGENVAL, KPOINTS, POSCAR, vasprun.xml | Real VASP 6.5.0 Si 200-kpt |
| `tests/data/analysis_vasp_bands_procar/` | fatbands | PROCAR, EIGENVAL, KPOINTS, POSCAR, vasprun.xml | Real VASP Si LORBIT=11 |
| `tests/data/analysis_vasp_dos/` | dos+pdos | DOSCAR, DOSCAR_spin, DOSCAR_pdos, POSCAR, POSCAR_tio2, vasprun.xml | Real VASP Si + Fe + TiO2 |
| `tests/data/analysis_vasp_convergence/` | convergence | OSZICAR, OSZICAR_md | Real VASP Si relax + MD |
| `tests/data/analysis_vasp_trajectory/` | trajectory | vasprun.xml, XDATCAR, OSZICAR | Real VASP Si 3-step relax |
| `tests/data/analysis_vasp_field3d/` | field3d | CHGCAR, LOCPOT | Real VASP Si 4x4x4 minimal |

### VASP Trajectory Parser — Detailed Template

The trajectory parser (`parsers/trajectory.py`, 300 lines) demonstrates all key patterns:

1. **Standalone parse functions:**
   - `parse_vasprun_trajectory(path) -> dict` — iterparse streaming XML
   - `parse_xdatcar(path) -> dict` — text line-by-line fallback
   - `_parse_oszicar_energies(path) -> List[float]` — auxiliary

2. **Primary/fallback pattern:**
   - Primary: `vasprun.xml` (full data: positions + cell + energy + forces + stress)
   - Fallback: `XDATCAR` + `OSZICAR` (positions + energies only)

3. **Memory management:**
   - `ET.iterparse(path, events=("end",))` with `elem.clear()` per `<calculation>`
   - Size warning: `_SIZE_WARN_THRESHOLD = 100MB`

4. **Coordinate conversion at parse time:**
   - `frac_coords @ lattice` -> Cartesian Angstrom

5. **Trajectory type detection:**
   - `"md" in gen_step` -> type="md", else type="relax"

---

## Multi-Engine Expansion Pattern (Proven Process)

This section documents the proven process used to expand bands/DOS from VASP-only to 6 engines, and then fatbands/PDOS across 5 engines.

### Phase 1: First Engine (VASP — most complex)

1. Built the full pipeline: AnalysisObject + Provider + ANALYSIS_CAPABILITIES + tests
2. Wrote standalone parse functions for each VASP output format
3. Generated fixtures from real VASP runs (used `.qmatsuite/engines/vasp/`)
4. Added gate tests enforcing the pattern

### Phase 2: Expand to 5 More Engines (QE, ABINIT, Siesta, CP2K, GPAW)

1. For each engine, ran real calculations using locally installed binaries
2. Copied output to `tests/data/analysis_<engine>_<type>/`
3. Wrote providers reusing existing low-level parsers where available
4. Wired registration + capability declarations
5. Added parametrized gate tests: `test_bands_dos_parser_matrix` (12 cells)
6. Result: +98 tests, 9 new provider files, 9 new fixture directories

### Phase 3: Fatbands + PDOS (Feature Depth)

1. Added PROCAR fatbands (VASP) and projwfc_up fatbands (QE)
2. Added PDOS: VASP (DOSCAR), QE (projwfc.x pdos), ABINIT (_DOS_AT), Siesta (PDOS.xml), CP2K (per-kind .pdos)
3. Documented NOT SUPPORTED verdicts with concrete technical justifications
4. Result: +20 tests, all cells DONE or NOT SUPPORTED (no "defer" remaining)

### Key Lessons Learned

1. **Always check existing parsers first.** Many engines already have low-level parse functions in `drivers/<engine>/parser.py` (e.g., Siesta's `parse_eig_file()`, `parse_mde_file()`). Wrap them rather than rewriting.

2. **Unit conversion tables are critical.** Document conversions at the top of each parser:
   - ABINIT: Ha->eV (27.211386), Bohr->A (0.529177), Ha/Bohr->eV/A (51.422067)
   - QE: Ry->eV (13.605693), Bohr->A (0.529177)
   - CP2K: a.u.->eV for PDOS
   - VASP, GPAW, Siesta, LAMMPS: already in eV/A (mostly)

3. **One-Provider-Multiple-Trigger pattern.** Convergence has 3 capability entries (scf/relax/md) all routing to the same provider. Trajectory has 2 (relax/md). The provider detects the specific type from `evidence.gen_steps`.

4. **Fixture generation from real engines is the bottleneck.** Parser writing is fast once you have the fixture. Plan fixture generation first.

5. **Trim fixtures aggressively.** Real vasprun.xml can be GB-sized. Use minimal systems (2-atom Si, 3 ionic steps, 4x4x4 grid). Keep total fixture directory < 200KB.

6. **POSCAR/structure files enrich PDOS/fatbands.** Many parsers read POSCAR (VASP), nscf.out (QE), or output file to get atom labels for PDOS. Test both with and without the structure file.

7. **NOT SUPPORTED needs concrete justification.** When an engine cannot support a feature, document exactly why (e.g., "ABINIT fatbands require FATBANDS.nc which needs netCDF4 dependency not in project").

8. **Gate tests catch wiring errors.** The parametrized `test_bands_dos_parser_matrix` gate test immediately catches missing registrations or capability declarations. Add equivalent gate tests for new object types.

9. **Parse signature must be EvidenceBundle.** All new providers use `parse(self, evidence: EvidenceBundle)`. The old `parse(self, raw_dir, calc_dir, **kwargs)` pattern (seen in QE trajectory) is technical debt.

---

## Pipeline Internals (DO NOT MODIFY)

These files are engine-agnostic and must NOT be modified when adding engine support:

| File | Role |
|------|------|
| `src/quantumvitas/core/analysis/orchestrator.py` | Multi-match enumeration + provider dispatch (see Spec §5.4, §5.9) |
| `src/quantumvitas/core/analysis/capability.py` | `AnalysisCapability` + `find_contiguous_match()` + `enumerate_all_matches()` |
| `src/quantumvitas/core/analysis/bundles.py` | `CanonicalPrimitiveBundle` + `DerivedPrimitiveBundle` |
| `src/quantumvitas/core/analysis/cas_writer.py` | CAS blob write + SQLite row write |
| `src/quantumvitas/core/analysis/base.py` | `AnalysisObjectMeta` + `SourceFileStat` |
| `src/quantumvitas/core/analysis/evidence.py` | `EvidenceBundle` (8 fields) |
| `src/quantumvitas/api/service.py` | `_finalize_run_analysis_pipeline()` and API handlers |
| `src/quantumvitas/parsers/registry.py` | `@register_parser` decorator + `get_parser()` lookup |

---

## Current Engine x Analysis Matrix

### Complete (DONE or NOT SUPPORTED)

| Engine | bands | dos | PDOS | fatbands | convergence | trajectory | field3d |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **VASP** | DONE | DONE | DONE | DONE | DONE | DONE | DONE |
| **QE** | DONE | DONE | DONE | DONE | -- | PARTIAL | -- |
| **ABINIT** | DONE | DONE | DONE | N/S | -- | -- | -- |
| **Siesta** | DONE | DONE | DONE | N/S | -- | -- | -- |
| **CP2K** | DONE | DONE | DONE | N/S | -- | -- | -- |
| **GPAW** | DONE | DONE | N/S | N/S | -- | -- | -- |

Legend: DONE = implemented, PARTIAL = partially working, N/S = not supported (documented), -- = not yet implemented

### Not Applicable

ORCA, Gaussian, Psi4, PySCF, xTB, LAMMPS, QMCPACK, Wannier90, Yambo: no periodic band structure / DOS (molecular, classical, or postprocessing engines).

---

## Acceptance Checklist

Before merging any analysis pipeline addition:

- [ ] **Real fixtures only** — all test data from real engine runs, not synthesized
- [ ] Provider registered with `@register_parser(engine, object_type)`
- [ ] Provider uses `EvidenceBundle` API (not ad-hoc kwargs)
- [ ] Driver declares matching `ANALYSIS_CAPABILITIES` entry
- [ ] Registration chain wired: `parsers/__init__.py` imports the provider class
- [ ] `to_primitives()` produces deterministic `CanonicalPrimitiveBundle`
- [ ] Test data in `tests/data/analysis_<engine>_<type>/` (not `.tmp/`)
- [ ] Test file docstring documents fixture provenance
- [ ] 7-test template: can_parse+/-, parse returns type, shapes, physics, to_primitives, SHA
- [ ] No engine branching in orchestrator or transforms
- [ ] No imports from `quantumvitas.drivers` in `core/analysis/`
- [ ] Full test suite passes: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- [ ] Gate tests pass: `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short`

---

## Quick Reference: File Locations

| What | Where |
|------|-------|
| Provider code | `src/quantumvitas/drivers/<engine>/parsers/<type>.py` |
| Provider __init__ | `src/quantumvitas/drivers/<engine>/parsers/__init__.py` |
| Driver capabilities | `src/quantumvitas/drivers/<engine>/driver.py` |
| Test file | `tests/drivers/<engine>/test_<engine>_<type>_parser.py` |
| Test fixtures | `tests/data/analysis_<engine>_<type>/` |
| Domain model | `src/quantumvitas/core/analysis/<type>/model.py` |
| Gate tests | `tests/gates/test_analysis_invariants.py` |
| Parser registry | `src/quantumvitas/parsers/registry.py` |
| Orchestrator | `src/quantumvitas/core/analysis/orchestrator.py` |
| Design docs | `docs/design/` |
| Engine docs | `docs/engines/<engine>/` |
| Research corpus | `.tmp/engine_research/<engine>/` |
