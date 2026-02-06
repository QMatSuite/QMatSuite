# B1 Engine Playbook: Taking an Engine to QE-Depth

**Status**: ACTIVE (binding SOP)
**Version**: 1.0
**Date**: 2026-02-05
**Authority**: Derived from VASP Phase B1 execution (first engine completed to QE-depth after QE itself)

---

## 0. Purpose

This document is the standardized operating procedure for bringing any QMatSuite engine driver to "QE-depth" — the level of maturity where it has a comprehensive parameter metadata catalog, robust bidirectional I/O (parse + write), a curated case library with roundtrip tests, output digest parsing, and optional real-execution verification.

**"B1 complete" means**: an engineer or agent unfamiliar with the engine could run any supported workflow type using only the driver's I/O stack, validate the outputs programmatically, and trust the parameter metadata catalog for input validation. No black boxes.

**Scope**: This playbook covers the driver-level work only. It does NOT cover kernel integration, runner changes, or public API surface — those are separate phases. All B1 work touches only `src/quantumvitas/drivers/<engine>/` and `tests/`.

---

## 1. Hard Rules

These rules are non-negotiable. Violating any of them is a blocking defect.

### 1.1 Process Rules

| # | Rule |
|---|------|
| P1 | **Plan first.** Every engine B1 MUST begin with a written plan at `docs/engines/<engine>/PHASE_B1_PLAN.md` BEFORE any code is written. The plan must include: baseline test count, file layout, step dependency graph, and acceptance criteria. |
| P2 | **Worklog is continuous.** A worklog at `docs/engines/<engine>/PHASE_B1_WORKLOG.md` MUST be created at the start and updated after EVERY step completes — not retroactively at the end. Each entry: step name, what was done, test count, pass/fail. |
| P3 | **Tests stay green.** Run the full suite after every step: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`. Zero failures at every checkpoint. Record the count in the worklog. |
| P4 | **No kernel modifications.** B1 work MUST NOT modify `runner.py`, `executor.py`, `driver_registry.py`, `driver_protocol.py`, or any file outside `drivers/<engine>/`, `tests/`, and `docs/`. The sole exception is `parsers/registry.py` (for `@register_parser`). |
| P5 | **Leaf-package imports only.** New modules in `data/`, `io/`, `parsers/`, `engine/` MUST use stdlib only (no kernel imports). `parsers/*.py` may import from `quantumvitas.parsers.registry`. Nothing else. |

### 1.2 Repository Layout Rules

| # | Rule |
|---|------|
| R1 | **Raw research goes in `.tmp/`.** All downloaded docs, mirrored web pages, PDFs, zips, extracted repos, raw runs, and intermediate analysis MUST live under `.tmp/engine_research/<engine>/`. This directory is `.gitignore`d but MUST be preserved locally for iteration. |
| R2 | **Committable docs go in `docs/engines/`.** Plans, worklogs, source lists, and design notes MUST live under `docs/engines/<engine>/`. These are committed to the repo. |
| R3 | **No hidden directories.** Work artifacts MUST NEVER go in `.claude/`, `/tmp/`, home directories, or any location outside the repo tree. If it matters, it's in the repo — either committed or in `.tmp/`. |
| R4 | **Test samples go in `tests/`.** Curated input samples for parametrized tests go in `tests/inputformat/samples/<engine>/` (following existing convention). |

### 1.3 Standard Directory Layout

```
# Committed (docs/engines/<engine>/)
docs/engines/<engine>/
  PHASE_B1_PLAN.md            # Implementation plan (REQUIRED)
  PHASE_B1_WORKLOG.md         # Continuous worklog (REQUIRED)
  SOURCES.md                  # All research sources with URLs + dates (REQUIRED)

# Committed (src/quantumvitas/drivers/<engine>/)
src/quantumvitas/drivers/<engine>/
  data/
    __init__.py
    <engine>_tags.json          # Parameter metadata catalog
    <engine>_metadata.py        # Access layer
  io/
    <format>.py                 # Parse + write functions (pure stdlib)
    __init__.py
  parsers/
    __init__.py
    output.py                   # Output digest parser (@register_parser)
  engine/
    __init__.py
    <engine>_runner.py          # Dev-only execution wrapper (optional)
    <engine>_<resource>.py      # Resource staging (e.g., potcar, pseudo)

# Committed (tests/)
tests/drivers/<engine>/
  conftest.py                   # Shared fixtures (binary/resource availability)
  test_<engine>_metadata.py
  test_<engine>_corpus.py
  test_<engine>_output.py
  test_<engine>_execution.py
tests/inputformat/samples/<engine>/
  <case_name>/                  # One directory per curated case
    <input_files>
    case.yaml                   # Case metadata
    ref_values.yaml             # Optional reference output values

# NOT committed (.tmp/)
.tmp/engine_research/<engine>/
  SOURCES.md                    # Duplicated here for offline reference
  WORKLOG.md                    # Research-phase worklog
  raw_web/                      # Mirrored documentation pages
  raw_pdfs/                     # Downloaded manuals, tutorials
  raw_zips/                     # Source archives, example bundles
  extracted/                    # Unpacked repos, example collections
  metadata/                     # Intermediate metadata analysis
  metadata_seed/                # Draft catalogs before promotion
  normalized/                   # Cleaned/standardized examples
  runs/                         # Test execution outputs
```

---

## 2. Phases

### Phase 0: Research Corpus Collection

**Goal**: Exhaust all available documentation, tutorials, example inputs, and community resources. Mirror everything locally for offline iteration.

**Attitude**: Be greedy. Download everything. It is far cheaper to collect too much than to discover a gap mid-implementation.

#### Checklist

- [ ] Create `.tmp/engine_research/<engine>/` with standard subdirectories
- [ ] Create `docs/engines/<engine>/SOURCES.md` documenting every source URL, download date, and what it covers
- [ ] Mirror official documentation to `raw_web/` (full site crawl if available)
- [ ] Download manuals/tutorials (PDF) to `raw_pdfs/`
- [ ] Clone community repos (example generators, automation tools, tutorials) to `extracted/`
- [ ] Collect real-world input files from testsuite, tutorials, and community repos
- [ ] Create `CORPUS_INDEX.md` in `.tmp/engine_research/<engine>/` inventorying everything collected
- [ ] Update `.tmp/engine_research/<engine>/WORKLOG.md`

#### Acceptance Criteria
- `raw_web/` has mirrored official docs (or a documented reason why not)
- `raw_pdfs/` has at least the primary manual
- `extracted/` has at least one community example collection
- `SOURCES.md` in `docs/engines/<engine>/` lists every URL with date
- No research artifacts stored outside `.tmp/engine_research/<engine>/`

#### Where Things Live
| Artifact | Location |
|----------|----------|
| Mirrored docs, PDFs, repos | `.tmp/engine_research/<engine>/raw_*/`, `extracted/` |
| Source inventory | `docs/engines/<engine>/SOURCES.md` (committed) |
| Corpus index | `.tmp/engine_research/<engine>/CORPUS_INDEX.md` |

---

### Phase 1: Parameter Metadata Catalog

**Goal**: Create a comprehensive, machine-readable catalog of all input parameters/keywords supported by the engine. This is the foundation for input validation, documentation, and IDE support.

#### Checklist

- [ ] Create `docs/engines/<engine>/PHASE_B1_PLAN.md` with full implementation plan
- [ ] Create `docs/engines/<engine>/PHASE_B1_WORKLOG.md` (update after EVERY step from here on)
- [ ] Record baseline test count in worklog
- [ ] Survey all parameters/keywords from official docs (use corpus from Phase 0)
- [ ] Design JSON schema appropriate for this engine's input format
- [ ] Create `drivers/<engine>/data/__init__.py`
- [ ] Create `drivers/<engine>/data/<engine>_tags.json` (or `<engine>_keywords.json`)
- [ ] Write validation tests: JSON loads, minimum count, required fields, no duplicates
- [ ] Run full test suite, record count in worklog

#### Minimum Tag/Keyword Count by Engine Type
| Engine Type | Examples | Minimum Tags |
|-------------|----------|-------------|
| Major DFT code | VASP, QE, ABINIT, CP2K, Siesta | 150+ |
| Quantum chemistry | ORCA, Gaussian, Psi4, PySCF | 100+ |
| Classical MD | LAMMPS | 100+ (commands/keywords) |
| Specialized | Wannier90, xTB, GPAW, QMCPACK, Yambo | 50+ |

#### JSON Schema Template
```json
{
  "schema_version": 1,
  "engine": "<engine>",
  "engine_version": "<version>",
  "doc_url": "<official docs URL>",
  "tags": {
    "<TAG_NAME>": {
      "name": "<TAG_NAME>",
      "type": "<type>",
      "default": "<default or null>",
      "category": "<category>",
      "description": "<one-line description>",
      "see_also": [],
      "status": "active"
    }
  }
}
```

Adapt the schema to the engine's input format. VASP uses flat INCAR tags. ORCA uses keyword-line + block parameters. LAMMPS uses commands. The schema must match the engine's native structure.

#### Acceptance Criteria
- JSON loads without error
- Tag count meets minimum for engine type
- Every tag has: name, type, category, description (at minimum)
- No duplicate tag names
- Tests pass

---

### Phase 2: Metadata Access Layer

**Goal**: Provide a Python API for querying the parameter catalog. All access to the JSON catalog goes through this module — no direct JSON loading elsewhere.

#### Checklist

- [ ] Create `drivers/<engine>/data/<engine>_metadata.py`
- [ ] Implement: `safe_load_metadata()`, `get_tag_info()`, `list_tags()`, `list_categories()`, `validate_params()`
- [ ] Module-level cache (`_METADATA_CACHE`) with optional hot-reload via `QV_<ENGINE>_METADATA_HOT_RELOAD=1`
- [ ] Use `importlib.resources` anchored at `quantumvitas.drivers.<engine>.data`
- [ ] Write tests: load, lookup, case-insensitive lookup, category filter, validation, reload, debug info
- [ ] Run full test suite, record count in worklog

#### Required API Surface
```python
def safe_load_metadata() -> dict                    # Runtime-safe loader
def reload_metadata() -> None                       # Cache invalidation
def get_tag_info(name: str) -> dict | None          # Single-tag lookup (case-insensitive)
def list_tags(category: str | None = None) -> list  # All/filtered tag names
def list_categories() -> list                       # Distinct categories
def validate_params(params: dict) -> list[str]      # Return unknown param names
def get_tag_type(name: str) -> str | None           # Type shortcut
def get_tag_default(name: str) -> str | None        # Default shortcut
```

#### Acceptance Criteria
- All functions work
- Case-insensitive lookup works
- Unknown params correctly flagged by `validate_params()`
- No imports outside stdlib + `importlib.resources`
- Tests pass

---

### Phase 3: Curated Case Library

**Goal**: Create 8-12 curated input cases covering the engine's major workflow types. Each case is a self-contained directory with all input files plus metadata.

#### Checklist

- [ ] Identify 8-12 representative workflow types for the engine
- [ ] Create case directories under `tests/inputformat/samples/<engine>/`
- [ ] Each case: all required input files + `case.yaml` metadata
- [ ] Cover at minimum: basic SCF/SP, relaxation/optimization, and 6+ specialized workflows
- [ ] If replacing existing flat sample files, update ALL test references
- [ ] Write `test_<engine>_corpus.py` with parametrized tests: structure validation, parse, roundtrip, orchestrator
- [ ] Run full test suite, record count in worklog

#### case.yaml Schema
```yaml
case_id: <unique_id>
title: "<human-readable title>"
engine: <engine>
workflow_tags: [<tag1>, <tag2>]
species: [<element1>, <element2>]
description: "<what this case demonstrates>"
```

#### Minimum Case Coverage
| Category | Examples |
|----------|----------|
| Basic energy | SCF, single-point, ground state |
| Optimization | Relaxation, geometry opt, vc-relax |
| Electronic structure | Bands, DOS, PDOS |
| Special physics | Magnetism, SOC, DFT+U, hybrid, vdW |
| Dynamics | MD, NEB, phonons |
| Post-processing | Wannier, optics, response |

Not all categories apply to every engine. Cover what the engine supports.

#### Acceptance Criteria
- 8-12 cases present
- Every case has all required input files + `case.yaml`
- All cases parse without error
- Roundtrip (parse -> write -> parse) preserves parameters
- No broken references in existing tests
- Tests pass

---

### Phase 4: Parser/Writer Robustness

**Goal**: Harden I/O modules to handle the full range of input syntax discovered in the case library and corpus. Extract reusable write functions.

#### Checklist

- [ ] Audit parser against all curated cases — identify edge cases
- [ ] Fix edge cases (comments in values, array syntax, continuation lines, etc.)
- [ ] Extract writer function to `io/<format>.py` if currently inline in `inputspec.py`
- [ ] Ensure `inputspec.py` delegates to `io/<format>.write_*()` — no inline writing
- [ ] Write edge-case tests for every syntax quirk discovered
- [ ] Run full test suite, record count in worklog

#### Common Edge Cases by Engine Family
| Family | Common Issues |
|--------|--------------|
| Fortran namelist (QE, ABINIT) | Multi-line arrays, string quoting, namelist nesting |
| Flat key=value (VASP INCAR) | Comments in values (SYSTEM tag), boolean formats, N*value expansion, semicolons |
| Keyword-block (ORCA) | `!` keyword line parsing, `%...end` block boundaries, inline comments |
| LAMMPS commands | Multi-word commands, variable substitution, include files |
| Free-format (xTB, Siesta) | Block delimiters, mixed formats, embedded coordinates |

#### Acceptance Criteria
- All curated cases roundtrip cleanly
- Writer produces output the engine would accept (verified by parse -> write -> parse)
- No inline writing in `inputspec.py` — all delegated to `io/` modules
- Edge-case tests cover every syntax quirk found
- Tests pass

---

### Phase 5: Resource Staging (if applicable)

**Goal**: Handle engine-specific resource files that must be staged alongside inputs (pseudopotentials, basis sets, etc.).

Not all engines need this phase. Skip if the engine has no external resource files.

#### Checklist

- [ ] Create `drivers/<engine>/engine/__init__.py`
- [ ] Create `drivers/<engine>/engine/<engine>_<resource>.py`
- [ ] Implement: resource discovery, staging/concatenation, library listing
- [ ] Write tests (mock library for deterministic tests; conditional tests for real library)
- [ ] Run full test suite, record count in worklog

#### Examples by Engine
| Engine | Resource | Staging Logic |
|--------|----------|--------------|
| VASP | POTCAR | Concatenate per-element POTCARs from library |
| QE | Pseudopotentials | Copy `.UPF` files from pseudo library |
| ORCA | None | (skip this phase) |
| LAMMPS | Force fields | Copy potential files referenced in input |
| Siesta | Pseudopotentials | Copy `.psf`/`.vps` files |

#### Acceptance Criteria
- Resource staging produces correct output for mock inputs
- Missing resources raise clear `FileNotFoundError` (not silent fallback)
- Conditional tests skip gracefully when library not available
- Tests pass

---

### Phase 6: Output Digest Parser

**Goal**: Parse engine output files into a canonical digest dataclass. Register with the parser registry.

#### Checklist

- [ ] Create `drivers/<engine>/parsers/__init__.py`
- [ ] Create `drivers/<engine>/parsers/output.py`
- [ ] Define `<Engine>Digest` dataclass with all relevant output fields
- [ ] Implement `<Engine>OutputParser` with `can_parse()` and `parse()` methods
- [ ] Register with `@register_parser("<engine>", "scf_digest")`
- [ ] Primary parse path: structured output (XML, JSON, HDF5) if available
- [ ] Fallback parse path: regex on text output
- [ ] Write tests using synthetic/minimal output fixtures (NOT real engine outputs)
- [ ] Test registry lookup: `get_parser("<engine>", "scf_digest")` returns the class
- [ ] Run full test suite, record count in worklog

#### Standard Digest Fields
```python
@dataclass
class EngineDigest:
    final_energy_eV: float | None = None       # Total energy
    energy_per_atom_eV: float | None = None    # Per-atom energy
    n_atoms: int = 0                           # Atom count
    converged_electronic: bool = False         # SCF converged?
    converged_ionic: bool = False              # Geometry converged?
    n_ionic_steps: int = 0                     # Ionic/optimization steps
    n_electronic_steps: int = 0                # SCF iterations
    final_lattice: list | None = None          # Final cell vectors
    final_frac_coords: list | None = None      # Final positions
    volume_A3: float | None = None             # Cell volume
    max_force_eV_A: float | None = None        # Maximum force
    total_magnetization: float | None = None   # Total magnetic moment
    elapsed_time_s: float | None = None        # Wall time
    pressure_kBar: float | None = None         # External pressure

    def to_dict(self) -> dict:
        return asdict(self)
```

Omit fields that don't apply (e.g., lattice for molecular codes). Add engine-specific fields as needed (e.g., `homo_eV`, `lumo_eV` for molecular codes).

#### Acceptance Criteria
- Synthetic output fixture parses to correct values
- `can_parse()` returns True/False correctly
- Fallback path works when primary output is missing
- Empty directory returns default digest (no crash)
- Registry lookup succeeds
- `to_dict()` produces JSON-serializable output
- Tests pass

---

### Phase 7: Execution Framework (Optional)

**Goal**: Dev-only execution wrapper for validating that the I/O stack produces inputs the real engine accepts. NOT a product-level runner.

This phase is optional. Skip if the engine binary is not available or if execution testing is impractical.

#### Checklist

- [ ] Create `drivers/<engine>/engine/<engine>_runner.py` (dev-only, documented as such)
- [ ] Implement: `RunResult` dataclass, `run_<engine>_case()`, `verify_reference()`
- [ ] Binary discovery: environment variable override + standard paths
- [ ] Create `tests/drivers/<engine>/conftest.py` with availability fixtures
- [ ] Create `tests/drivers/<engine>/test_<engine>_execution.py` with conditional tests
- [ ] Add `ref_values.yaml` to at least one curated case
- [ ] All execution tests skip gracefully when binary/resources unavailable
- [ ] Run full test suite, record count in worklog

#### verify_reference() Design
```python
DEFAULT_TOLERANCES = {
    "final_energy_eV": 0.01,    # 10 meV
    "energy_per_atom_eV": 0.005, # 5 meV/atom
    "volume_A3": 0.5,
    "max_force_eV_A": 0.05,
}

def verify_reference(digest, ref: dict, tolerances: dict | None = None) -> dict:
    """Compare digest against reference values.
    Returns: {passed: bool, checks: list, n_passed: int, n_failed: int}
    """
```

#### Acceptance Criteria
- Mock tests (missing inputs, missing binary) pass unconditionally
- Real execution tests skip with clear message when resources unavailable
- `verify_reference()` correctly compares digest against reference values
- Tests pass

---

### Phase 8: Final Integration

**Goal**: Verify everything works together. Confirm acceptance criteria. Close out.

#### Checklist

- [ ] Run full test suite: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- [ ] Verify test count: baseline + new tests (record both in worklog)
- [ ] Verify zero failures
- [ ] Verify no kernel imports in leaf modules (`data/`, `io/`, `engine/`)
- [ ] Verify `inputformat/` package is untouched: `git diff HEAD -- src/quantumvitas/inputformat/`
- [ ] Verify all docs are in `docs/engines/<engine>/` (not in `.claude/` or other hidden dirs)
- [ ] Verify all research artifacts are in `.tmp/engine_research/<engine>/`
- [ ] Update worklog with final status: COMPLETE
- [ ] Update `MEMORY.md` with engine completion summary

#### Acceptance Criteria (Definition of Done)
All of the following must be true for an engine to be declared "B1 complete":

- [ ] Full pytest green (zero failures)
- [ ] Parameter metadata catalog: meets minimum count for engine type
- [ ] Metadata access layer: tag lookup, validation, category listing all work
- [ ] 8-12 curated cases with 100% parse + roundtrip success
- [ ] Writer functions extracted to `io/` module (not inline in `inputspec.py`)
- [ ] Output parser produces digest with energy/structure/convergence fields
- [ ] Output parser registered: `get_parser("<engine>", "scf_digest")` succeeds
- [ ] Resource staging works (where applicable)
- [ ] No kernel/API surface changes
- [ ] `inputformat/` leaf package untouched
- [ ] `docs/engines/<engine>/PHASE_B1_PLAN.md` exists
- [ ] `docs/engines/<engine>/PHASE_B1_WORKLOG.md` exists and is complete
- [ ] `docs/engines/<engine>/SOURCES.md` exists
- [ ] `.tmp/engine_research/<engine>/` has research corpus

---

## 3. Phase Dependency Graph

```
Phase 0 (Corpus Collection)
    |
    v
Phase 1 (Metadata Catalog)     Phase 3 (Case Library)
    |                                |
    v                                |
Phase 2 (Access Layer)               |
    |                                |
    +--------------------------------+
    |
    v
Phase 4 (Parser/Writer Robustness)
    |
    v
Phase 5 (Resource Staging) ← skip if N/A
    |
    v
Phase 6 (Output Digest Parser)
    |
    v
Phase 7 (Execution Framework) ← optional
    |
    v
Phase 8 (Final Integration)
```

Phases 1 and 3 can proceed in parallel (both depend only on Phase 0).
Phases 5 and 7 can be skipped where not applicable.

---

## 4. Kernel/Dev-Only vs Product API

Everything built in B1 is **kernel/dev-only**. The separation:

| Layer | B1 Scope | Product Scope (later) |
|-------|----------|-----------------------|
| `data/<engine>_tags.json` | Catalog of all params | Same — shared |
| `data/<engine>_metadata.py` | Access layer for validation | Same — shared |
| `io/<format>.py` | Pure text <-> dict mapping | Same — shared |
| `parsers/output.py` | Digest extraction | Same — shared |
| `engine/<engine>_runner.py` | Dev-only smoke test | Removed or gated behind dev flag |
| `inputspec.py` | `get_input_spec()` wiring | Used by inputformat orchestrator |
| Public API | None | TBD (facade module, CLI integration) |

B1 builds the foundation. Product API exposure is a separate phase that imports from these modules.

---

## 5. Common Pitfalls

These are mistakes actually made during the VASP B1 execution. Learn from them.

| # | Pitfall | Consequence | Prevention |
|---|---------|-------------|------------|
| 1 | **Storing research artifacts in hidden `.claude/` directory** | Work products invisible to the user; lost across sessions; violates transparency. | R3: All artifacts in repo — committed or `.tmp/`. |
| 2 | **Writing worklog only at the end** | No progress visibility during execution; hard to debug failures; user cannot verify incremental correctness. | P2: Update worklog after EVERY step. |
| 3 | **Running tests only at milestones** | Regressions accumulate silently; harder to identify which step broke something. | P3: Full suite after every step. Record count. |
| 4 | **Inline writers in `inputspec.py`** | Logic locked inside the inputformat wiring; not reusable by output parser or runner. | Phase 4: Extract to `io/` module, delegate from `inputspec.py`. |
| 5 | **Using real engine outputs as test fixtures** | Tests break on different machines; binary outputs not portable. | Phase 6: Use synthetic minimal fixtures (embedded strings or small files). |
| 6 | **Forgetting to update test references after restructuring** | Existing tests fail because sample paths changed. | Phase 3: Search all test files for old paths before deleting old files. |
| 7 | **Not recording baseline test count** | Cannot verify how many tests were added; cannot prove zero regressions. | Phase 1: Record baseline in plan AND worklog before writing any code. |
| 8 | **Importing kernel modules in leaf packages** | Circular dependencies; violates driver isolation. | P5: Leaf packages use stdlib only. Verify with grep before committing. |

---

## 6. QE Reference (the Gold Standard)

QE is the most mature engine. When in doubt about how something should work, check:

| Concern | QE Reference |
|---------|-------------|
| Metadata catalog | `src/quantumvitas/data/qe_module_parameters.json` (~13K lines) |
| Metadata access | `drivers/qe/data/qe_metadata.py` (~600 lines, cached, hot-reload) |
| I/O modules | `drivers/qe/io/` (parser.py, generator.py, model.py, structure_io.py) |
| Output parser | `drivers/qe/parsers/trajectory.py` (440 lines, @register_parser) |
| Test count | 14 dedicated test files |

The QE pattern is the template. Adapt it to the engine's input format; do not reinvent the architecture.

---

## 7. Engine-Specific Adaptations

Not every engine is VASP. Adapt the playbook to the engine's nature:

| Engine Trait | Adaptation |
|-------------|------------|
| Molecular code (ORCA, Gaussian, Psi4, PySCF) | Digest uses `cart_coords` not `frac_coords`; no lattice/volume; add `homo_eV`/`lumo_eV` |
| Python-script engine (GPAW, Psi4, PySCF) | No parseable input files; Phase 4 may be minimal or skipped |
| Classical MD (LAMMPS) | Commands not key=value; catalog is command list; no electronic convergence |
| Post-processing (Wannier90, Yambo) | Depends on upstream engine outputs; Phase 7 may require upstream results |
| Single input file (ORCA, xTB) | No multi-file orchestration; case library is simpler |
| Multi-file input (VASP, QE, ABINIT) | Full orchestration with content-role dispatch |

---

## Appendix: Quick-Start Checklist (Copy-Paste)

For starting a new engine B1, copy this to `docs/engines/<engine>/PHASE_B1_PLAN.md` and fill in:

```markdown
# Phase B1: <ENGINE> End-to-End "QE-Depth"

## Baseline
- Tests: ___ passed, ___ skipped, 0 failures
- Driver: ___ lines across ___ files
- Curated samples: ___

## Phases
- [ ] Phase 0: Corpus collection
- [ ] Phase 1: Parameter metadata catalog
- [ ] Phase 2: Metadata access layer
- [ ] Phase 3: Curated case library (___  cases)
- [ ] Phase 4: Parser/writer robustness
- [ ] Phase 5: Resource staging (skip if N/A)
- [ ] Phase 6: Output digest parser
- [ ] Phase 7: Execution framework (optional)
- [ ] Phase 8: Final integration

## Acceptance Criteria
- [ ] Full pytest green
- [ ] Metadata catalog: ___+ tags
- [ ] Access layer: lookup, validation, categories
- [ ] ___  curated cases, 100% roundtrip
- [ ] Writer extracted to io/ module
- [ ] Output parser registered
- [ ] No kernel changes, inputformat untouched
- [ ] All docs in docs/engines/<engine>/
- [ ] All research in .tmp/engine_research/<engine>/
```
