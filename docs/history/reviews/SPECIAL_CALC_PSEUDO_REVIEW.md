# Special Calculation & Pseudopotential Infrastructure Review

**Date**: 2026-02-27
**Scope**: SOC, TDDFT, NMR/EPR workflow readiness for MCP agent execution
**Purpose**: Determine readiness for knowledge distillation case study
**Method**: Read-only code analysis. No code changes. No test runs.

## Executive Summary

QMatSuite's pseudopotential infrastructure is mature and well-architected, with a
SHA256-keyed registry covering 8 libraries (3,083 unique files, 3,623 occurrences),
including full-relativistic (986 files) and GIPAW (73 occurrences) pseudopotentials.
The MCP tool surface provides `download_pseudo_library`, `auto_resolve_species_map`,
`set_species_map`, and `list_available_resources` — sufficient for an agent to
discover, install, and switch pseudo libraries.

Of the three target workflows:

- **NMR/EPR (GIPAW)** is the most ready: `qe_gipaw` is a registered step type,
  GIPAW pseudos ship bundled in `resources/pseudo/`, a curated test sample exists,
  and the `gipaw` gen step is in `SUPPORTED_GEN_STEPS`. An agent can complete this
  workflow end-to-end with existing MCP tools.

- **SOC** is nearly ready: magnetism preset `SOC_CANONICAL` correctly sets
  `noncolin=.true., lspinorb=.true.`. The pseudo index has rich metadata
  (`relativistic`, `has_spin_orbit` fields). However, `auto_resolve_species_map`
  defaults to SSSP (scalar-relativistic) and there is no preflight check warning
  about pseudo/SOC incompatibility. The agent can work around this via manual
  `set_species_map` + `download_pseudo_library(library='pseudodojo', variant='nc-fr_pbe_standard')`,
  but the experience is rough.

- **TDDFT** is blocked: `tddft_lanczos` and `tddft_spectrum` appear in the
  `EXECUTABLE_MAP` but are **not** registered as step types in `QE_STEP_TYPE_SPECS`
  and `tddft_lanczos` is **not** in `SUPPORTED_GEN_STEPS`. No workflow template
  exists. An agent cannot create a TDDFT calculation via MCP.

**Recommendation**: Run the case study with NMR/GIPAW as the primary scenario (fully
ready) and SOC as the stretch scenario (soft gaps only, no code changes required).
Defer TDDFT until step type registration is added.

---

## 1. Pseudo Infrastructure Status

### 1.1 Pseudo Info Registry

**Location**: `src/qmatsuite/resources/pseudo_libinfo/assets-2025-12-26/`

Two key files:

| File | Size | Purpose |
|------|------|---------|
| `PSEUDO_FILE_INDEX.json` | ~6 MB | Master index: 3,083 unique files, 3,623 occurrences |
| `MANIFEST_PSEUDO_SEED.json` | ~17 KB | Archive metadata for GitHub release downloads |

**Per-file metadata in PSEUDO_FILE_INDEX.json:**

```
sha256, sha_family, element, size_bytes, upf_format,
pseudo_type (paw|uspp|nc|unknown),
relativistic (scalar_rel|full_rel|nonrel),
has_spin_orbit (true|false|unknown),
has_gipaw (true|false|unknown),
functional_norm, z_valence, cutoff_wfc_upf, cutoff_rho_upf,
basenames, metadata_source
```

**Library coverage:**

| Library | Occurrences | Has FR? | Has GIPAW? | Elements |
|---------|-------------|---------|------------|----------|
| SSSP | 206 | No (SR only) | No | ~100 |
| PseudoDojo | 1,228 | Yes (nc-fr_pbe variants) | No | 72 |
| PSlibrary | 1,422 | Yes (rel-* prefixed) | No | 94 |
| GBRV | 193 | No | No | ~60 |
| SG15 | 219 | Yes | No | 64 |
| HGH | 266 | No | No | ~80 |
| GIPAW | 73 | No (but NMR-compatible) | Yes | 38 |
| SCAN_TM | 16 | Partial (1 FR) | No | ~16 |

**Key finding**: The `relativistic` and `has_spin_orbit` fields exist and are
populated for all 3,083 files. An agent querying the pseudo registry can
programmatically determine which pseudos support SOC. However, this metadata is
in the JSON file — not directly exposed via any MCP tool.

**Pseudo type distribution:**
- PAW: 1,051 files
- USPP: 985 files
- NC (norm-conserving): 1,046 files
- Unknown: 1 file

**Relativistic distribution:**
- scalar_rel: 1,837 files
- full_rel: 986 files
- nonrel: 260 files

### 1.2 Pseudo Download & Management via MCP

**MCP tools available:**

| Tool | Purpose | Scope |
|------|---------|-------|
| `download_pseudo_library(library, variant, version)` | Download & install any registered library | All 8 libraries |
| `auto_resolve_species_map(calc_ulid, library, variant)` | Auto-select pseudos for all elements | SSSP default; accepts any library |
| `set_species_map(calc_ulid, species_map)` | Manual per-element pseudo assignment | Any filename |
| `list_available_resources(engine, elements)` | Discover installed pseudos | QE, VASP, LAMMPS |

**Can agent list ALL available (not-yet-downloaded) libraries?**

Yes, indirectly. When `download_pseudo_library` fails with `invalid_library`, the
error response includes: `"Available libraries: gbrv, gipaw, hgh, ps-library, pseudodojo, scan_tm, sg15, sssp"`.
However, there is **no dedicated MCP tool to list downloadable libraries without
attempting a download first**. The agent must either:
1. Call `download_pseudo_library(library='???')` and parse the error, or
2. Call `download_pseudo_library(library='sssp')` first and have prior knowledge.

**Can agent download a non-SSSP library?**

Yes. `download_pseudo_library(library='pseudodojo', variant='nc-fr_pbe_standard')`
is fully functional. The registry resolves library key → archive → GitHub download URL.

**Can agent switch pseudo library?**

Yes, via two paths:
1. `auto_resolve_species_map(calc_ulid, library='pseudodojo', variant='nc-fr_pbe_standard')` — auto-resolve with different library
2. `set_species_map(calc_ulid, {"Bi": {"pseudopot": "Bi.upf"}})` — manual filename

**What happens if library not downloaded?**

`auto_resolve_species_map_internal` calls `resolve_project_pseudos` which has a
step 4 auto-download via `download_and_install()`. So the system will attempt
automatic download when the library is not installed. If download fails (network
error), the agent gets a descriptive error with context_hint.

### 1.3 Pseudo Selection & Switching

**Where is pseudo choice stored?**

In `calculation.yaml` as `species_map`:
```yaml
species_map:
  Si:
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF
    pseudo_sha256: 669fb75395a9d26...   # optional
    pseudo_sha_family: 9d5fdea5cc45... # optional
```

No library name/version is stored — only filenames and optional SHA256 hashes.
This means the system is library-agnostic at the calculation level.

**Default behavior**: `create_calculation()` auto-calls `auto_resolve_species_map_internal()`
with `library='sssp', variant='precision'` as defaults. The agent starts with SSSP
unless it explicitly overrides.

**Per-element override**: Fully supported. Different elements can use different
pseudo files (and thus different libraries). The `set_species_map` tool accepts
any per-element mapping:
```python
set_species_map(calc_ulid, {
    "Bi": {"pseudopot": "Bi.upf"},  # PseudoDojo FR
    "O": {"pseudopot": "O.pbe-n-kjpaw_psl.1.0.0.UPF"}  # SSSP
})
```

**Pseudo path resolution**: After `set_species_map`, the runner resolves pseudos via
`ensure_qe_pseudos()` which searches: (1) project/pseudo/, (2) resources/pseudo/,
(3) installed libraries. The PSEUDO_FILE_INDEX.json provides deterministic
element→filename mapping (no glob ambiguity).

---

## 2. SOC Workflow Readiness

### 2.1 Parameter Support

**SOC is a first-class preset dimension.** The `MagnetismOption` enum
(`src/qmatsuite/presets/dimensions.py`) has four states:

| Profile Name | Enum Value | QE Parameters |
|-------------|------------|---------------|
| `NM` | `NONMAGNETIC` | `nspin=1, noncolin=.false., lspinorb=.false.` |
| `COL` | `COLLINEAR_LSDA` | `nspin=2, noncolin=.false., lspinorb=.false.` |
| `NC_CANONICAL` | `NONCOLLINEAR` | `noncolin=.true., lspinorb=.false.` |
| `SOC_CANONICAL` | `NONCOLLINEAR_SOC` | `noncolin=.true., lspinorb=.true.` |

Agent path: `apply_preset(calc_ulid, {"magnetism": "SOC_CANONICAL"})`

Alternatively, manual: `set_parameters(calc_ulid, {"SYSTEM": {"noncolin": True, "lspinorb": True}})`

The IR layer (`src/qmatsuite/ir/parameters.py`) recognizes both `noncolin` and
`lspinorb` as IRParameters with type `bool`.

Physics constraints are enforced in `presets/integration.py`:
- `lspinorb=true` requires `noncolin=true`
- `noncolin=true` requires `nspin` absent or equal to 4

### 2.2 Agent Walkthrough: "Calculate band structure of Bi with SOC"

| Step | MCP Tool | Input | Expected Result | Gap? |
|------|----------|-------|-----------------|------|
| 1 | `init_project` | `path="/tmp/bi_soc"` | Project initialized | None |
| 2 | `import_structure` | `file_content="Bi POSCAR...", format="poscar"` | Structure imported | None — agent must know/generate Bi structure |
| 3 | `create_calculation` | `engine="qe", workflow="bands", structure_selector="Bi"` | Calc created with steps: scf, bandspw, bands. **Auto-resolves SSSP pseudos** | **Soft gap**: auto-resolve picks SSSP (scalar-rel), incompatible with SOC |
| 4 | `apply_preset` | `calc_ulid, {"magnetism": "SOC_CANONICAL"}` | Sets `noncolin=.true., lspinorb=.true.` on scf + bandspw steps | None |
| 5 | `inspect_calculation` | `calc_ulid, step=0, dry_run=True` | Materializes input, runs preflight | **Soft gap**: preflight does NOT warn about SSSP/SOC incompatibility |
| 6 | `run_calculation` | `calc_ulid` | **QE CRASHES**: SSSP pseudos lack SOC projectors | **Hard gap in UX**: agent gets raw ENGINE_CRASH error, no SOC-specific guidance |
| 7 | Agent reads error | — | "Engine crashed (exit code 1)" | **Soft gap**: error_enrichment has no SOC-specific classification |
| 8 | `search_knowledge` | `query="spin-orbit pseudopotential"` | Finds SOC principle entry, but it doesn't mention pseudo requirements | **Soft gap**: KB entry says "SOC is essential for heavy elements" but not "requires FR pseudo" |
| 9 | Agent reasons | — | Needs full-relativistic pseudopotentials | Requires agent's own physics knowledge |
| 10 | `download_pseudo_library` | `library="pseudodojo", variant="nc-fr_pbe_standard"` | Downloads PseudoDojo FR library | None |
| 11 | `auto_resolve_species_map` | `calc_ulid, library="pseudodojo", variant="nc-fr_pbe_standard"` | Resolves Bi.upf (FR) from PseudoDojo | None |
| 12 | `run_calculation` | `calc_ulid` | Success (with FR pseudos) | None |

**Total tool calls**: 10-12 (including error recovery)

### 2.3 Hard Gaps (cannot work without code changes)

**None.** The SOC workflow is completable end-to-end with existing MCP tools.
The agent can download FR pseudos, set species_map, and re-run. No code
changes are strictly required.

### 2.4 Soft Gaps (works but agent experience is poor)

| Gap ID | Description | Impact | Fix Effort |
|--------|-------------|--------|------------|
| SOC-S1 | `auto_resolve_species_map` defaults to SSSP (SR). No option to request "FR-compatible" pseudos | Agent's first attempt always fails for SOC | Low: add `relativistic` filter parameter |
| SOC-S2 | Preflight checker has no SOC/pseudo compatibility rule | No warning before crash | Medium: add rule checking `lspinorb=true` vs pseudo `relativistic` field |
| SOC-S3 | Error enrichment has no SOC-specific error classification | Agent gets generic "ENGINE_CRASH" instead of "SOC_PSEUDO_INCOMPATIBLE" | Medium: add QE error pattern matching |
| SOC-S4 | KB entry for SOC doesn't mention pseudo requirements | Agent can't learn from KB that FR pseudos are needed | Low: update builtin entry text |
| SOC-S5 | No demo project for SOC calculation | Agent has no reference example to learn from | Low: add qe_bi_soc.yml demo |
| SOC-S6 | `list_available_resources` doesn't show pseudo `relativistic` field | Agent can't filter by relativistic type via MCP | Low: add field to response |

---

## 3. TDDFT Workflow Readiness

### 3.1 Step Type Support

**Status: BLOCKED**

The QE engine's `EXECUTABLE_MAP` (in `qe_engine.py`) knows about TDDFT executables:
```python
"tddft_lanczos": "turbo_lanczos.x",
"tddft_spectrum": "turbo_spectrum.x",
```

However, these are **not registered** in the critical places:

| Registry | tddft_lanczos | tddft_spectrum | Status |
|----------|--------------|----------------|--------|
| `EXECUTABLE_MAP` (qe_engine.py) | turbo_lanczos.x | turbo_spectrum.x | Present |
| `QE_STEP_TYPE_SPECS` (step_types.py) | **MISSING** | **MISSING** | **BLOCKED** |
| `SUPPORTED_GEN_STEPS` (driver.py) | **MISSING** | **MISSING** | **BLOCKED** |
| Workflow templates | **MISSING** | **MISSING** | **BLOCKED** |
| Input format spec | **MISSING** | **MISSING** | **BLOCKED** |

**Why this blocks MCP agents**: `create_calculation` uses `SUPPORTED_GEN_STEPS` to
validate step types. Without `tddft_lanczos` in that set, the driver rejects the
step. Even if an agent uses `workflow="scf_td"` (which exists as a template with
`step_sequence=("scf", "td")`), the `td` gen step would need to materialize to
`qe_tddft_lanczos` spec, which doesn't exist.

**Note**: TDDFT is supported for ORCA and Gaussian (molecular codes), where it's
part of the route/keyword line, not a separate executable. The gap is
QE-specific.

### 3.2 Agent Walkthrough: "Calculate optical absorption of Si using TDDFT"

| Step | MCP Tool | Expected | Actual |
|------|----------|----------|--------|
| 1 | `init_project` | OK | OK |
| 2 | `import_structure` | Si imported | OK |
| 3 | `list_workflows(engine="qe")` | See available workflows | `scf_td` exists with steps `("scf", "td")` |
| 4 | `create_calculation(engine="qe", workflow="scf_td", ...)` | Calc with scf + td steps | **FAILS**: `td` gen step maps to... what? `qe_td` spec doesn't exist |
| — | Alternative: manual workflow | Agent tries `workflow="scf"` + add custom step | No MCP tool to add arbitrary steps post-creation |

**Verdict**: BLOCKED. Cannot proceed without code changes.

### 3.3 Hard Gaps (require code changes)

| Gap ID | Description | Fix Effort |
|--------|-------------|------------|
| TDDFT-H1 | Add `qe_tddft_lanczos` and `qe_tddft_spectrum` to `QE_STEP_TYPE_SPECS` | Small |
| TDDFT-H2 | Add `tddft_lanczos` (or `td`) to `SUPPORTED_GEN_STEPS` | Small |
| TDDFT-H3 | Create workflow template for TDDFT (scf → tddft_lanczos → tddft_spectrum) | Small |
| TDDFT-H4 | Create `&lr_input` / `&lr_control` namelist model for turbo_lanczos.x | Medium |
| TDDFT-H5 | Input materialization for turbo input format | Medium |

### 3.4 Soft Gaps

| Gap ID | Description |
|--------|-------------|
| TDDFT-S1 | No curated test samples for QE TDDFT |
| TDDFT-S2 | No knowledge base entry about TDDFT methodology |
| TDDFT-S3 | No output parser for turbo_lanczos.x / turbo_spectrum.x |
| TDDFT-S4 | TDDFT requires NCPP (no USPP/PAW) — no preflight check for this |

---

## 4. NMR/EPR (GIPAW) Readiness

### 4.1 Step Type / Parameter Support

**Status: FULLY SUPPORTED**

GIPAW is registered at all critical levels:

| Registry | Status | Value |
|----------|--------|-------|
| `QE_STEP_TYPE_SPECS` | `qe_gipaw` | executable=`gipaw.x` |
| `SUPPORTED_GEN_STEPS` | `gipaw` | In frozenset |
| `QEModule` enum | `GIPAW` | In model.py |
| `MODULE_NAMELISTS` | `gipaw: ["inputgipaw"]` | Namelist mapping |
| `EXECUTABLE_MAP` | `gipaw: gipaw.x` | In qe_engine.py |

**GIPAW input format**: The `&inputgipaw` namelist is recognized. Curated sample
exists at `tests/inputformat/samples/qe/nmr_gipaw/` with both SCF and GIPAW
input files.

### 4.2 Agent Walkthrough: "Calculate NMR chemical shifts of benzene"

| Step | MCP Tool | Input | Expected Result | Gap? |
|------|----------|-------|-----------------|------|
| 1 | `init_project` | `path="/tmp/benzene_nmr"` | Project initialized | None |
| 2 | `import_structure` | Benzene CIF/XYZ (inline or file) | Structure imported with C, H species | None |
| 3 | `search_demos` | `engine="qe", tag="gipaw"` | **May not find** — depends on demo tagging | **Soft gap**: no NMR demo in demo store |
| 4 | `create_calculation` | `engine="qe", workflow="scf", structure_selector="benzene"` | Calc created with scf step. **Auto-resolves SSSP** | **Soft gap**: needs GIPAW pseudo, not SSSP |
| 5 | — | Agent must manually add gipaw step | **Soft gap**: no "scf_gipaw" workflow template | Agent must create scf workflow then add gipaw step |
| 6 | `download_pseudo_library` | `library="gipaw"` | Downloads GIPAW library | None — but may already be bundled |
| 7 | `auto_resolve_species_map` | `calc_ulid, library="gipaw"` | Resolves C.pbe-tm-gipaw.UPF, H.pbe-tm-gipaw.UPF | None |
| 8 | `set_parameters` | GIPAW-specific params for step 1 | Sets `&inputgipaw` namelist params | None |
| 9 | `inspect_calculation` | `calc_ulid, step=0, dry_run=True` | Materializes, runs preflight | None |
| 10 | `run_calculation` | `calc_ulid` | SCF completes, GIPAW runs | None |

**Critical observation**: GIPAW pseudos for C and H are **bundled in
`resources/pseudo/`** (confirmed: `C.pbe-tm-gipaw.UPF`, `H.pbe-tm-gipaw.UPF`,
`Si.pbe-tm-gipaw.UPF`). For light-element NMR (organic molecules), the agent
doesn't even need to download a library — the bundled pseudos are discovered
during resolution step 2 (resources/pseudo).

**Workflow gap**: There is no `scf_gipaw` workflow template. The agent must either:
1. Create an `scf` calculation and add a GIPAW step manually (if such an MCP tool
   exists), or
2. Use `workflow="scf"` and set up GIPAW as a separate calculation.

Checking whether add-step is exposed via MCP... `create_calculation` adds steps
from the template. There is no standalone `add_step` MCP tool. However, the agent
could create a `custom` workflow or use `set_parameters` on a custom step type.

**Actual feasible path**: The agent can use `create_calculation(workflow="scf")` to
create the SCF step, run it, then create a second calculation with custom
parameters for GIPAW. This is awkward but functional.

**Better path**: If a "gipaw" or "nmr" workflow template existed with
`step_sequence=("scf", "gipaw")`, the agent could use it directly.

### 4.3 Hard Gaps

| Gap ID | Description | Fix Effort |
|--------|-------------|------------|
| NMR-H1 | No `scf_gipaw` or `nmr` workflow template | Small: add to templates.py |

This is the only hard gap, and it's minimal — just adding a 4-line template.

### 4.4 Soft Gaps

| Gap ID | Description | Impact |
|--------|-------------|--------|
| NMR-S1 | No NMR/GIPAW demo in demo store | Agent has no reference example |
| NMR-S2 | No KB entry about NMR methodology or GIPAW pseudo requirements | Agent must know physics independently |
| NMR-S3 | No output parser for gipaw.x (chemical shifts, g-tensor) | `get_results_summary` won't parse NMR results |
| NMR-S4 | No preflight check for GIPAW/pseudo compatibility (GIPAW requires GIPAW-compatible NCPP) | Silent failure if wrong pseudo |
| NMR-S5 | GIPAW library covers only 38 elements | Heavy-element NMR may lack pseudos |
| NMR-S6 | `auto_resolve_species_map` doesn't know about GIPAW requirements | Defaults to SSSP even for GIPAW workflow |

---

## 5. Cross-Cutting Issues

### 5.1 Pseudo Library Switching Mechanism

**Current state**: Pseudo choice is stored as `species_map` in `calculation.yaml`
with filenames only (no library name). This is library-agnostic by design.

**Switching path**:
```
# Method 1: Auto-resolve with different library
auto_resolve_species_map(calc_ulid, library="pseudodojo", variant="nc-fr_pbe_standard")

# Method 2: Manual per-element
set_species_map(calc_ulid, {"Bi": {"pseudopot": "Bi.upf"}})
```

Both methods immediately update `calculation.yaml`. No restart required.

**Per-element override**: Fully supported. Call `set_species_map` with a dict
containing only the elements to change; other elements retain their pseudos.

**Path resolution after switching**: `ensure_qe_pseudos()` resolves files via:
1. `project/pseudo/` (project-local)
2. `resources/pseudo/` (bundled)
3. `~/.qmatsuite/libraries/pseudo/<lib>/<variant>/<version>/` (installed)

When `auto_resolve_species_map_internal` finds a match in an installed library,
it **copies the file to `project/pseudo/`**. This means the calculation becomes
self-contained.

**Key limitation**: `auto_resolve_species_map_internal` hardcodes
`library='sssp', variant='precision', version='1.3.0'` as defaults. When called
from `create_calculation`, there's no way to specify a different library.
The agent must call `auto_resolve_species_map` separately after creation.

### 5.2 Error Message Quality for Pseudo Mismatches

| Scenario | Error Path | What Agent Sees | Quality |
|----------|-----------|-----------------|---------|
| SOC + SSSP → QE crash | `error_enrichment._classify_error()` | `"Engine crashed (exit code 1). Step details: ..."` | **Poor**: generic ENGINE_CRASH, no SOC-specific diagnosis |
| TDDFT + USPP → QE crash | Same path | `"Engine crashed (exit code 1)"` | **Poor**: same generic error |
| Pseudo library not downloaded | `resolve_project_pseudos()` | Auto-download attempted; if fails: `"resolution_failed: Could not auto-resolve..."` | **Good**: clear error with context_hint |
| Wrong pseudo for GIPAW | QE gipaw.x crash | `"Engine crashed"` | **Poor**: no GIPAW-specific error handling |

**Error enrichment only classifies**: SCF_NOT_CONVERGED, IONIC_NOT_CONVERGED,
OUT_OF_MEMORY, ENGINE_CRASH, UNKNOWN_FAILURE. There are no pseudo-compatibility
error classifications. All pseudo mismatch errors fall into ENGINE_CRASH.

The `_build_suggested_fixes()` function only generates fixes for convergence
and memory issues. No fixes for pseudo-related crashes.

### 5.3 Knowledge Base Coverage (builtin.db)

Searched `builtin_entries.py` (the authoritative source of builtin knowledge):

| Topic | KB Entry Exists? | Content Quality |
|-------|-----------------|-----------------|
| SOC general | Yes (principle) | "SOC essential for Z>50... QE: lspinorb+noncolin" — **doesn't mention pseudo requirements** |
| SOC + pseudo | No | **GAP**: Agent can't learn from KB that FR pseudos are needed |
| TDDFT methodology | No | **GAP**: No TDDFT guidance at all |
| TDDFT + pseudo | No | **GAP** |
| NMR/GIPAW methodology | No | **GAP**: No NMR methodology guidance |
| NMR/GIPAW + pseudo | No | **GAP**: No mention of GIPAW-compatible pseudos |
| Pseudo types (PAW/USPP/NC) | Yes (principle) | Good: explains PAW vs USPP vs NC tradeoffs |
| Pseudo library choice | No | **GAP**: No guidance on which library for which purpose |
| PseudoDojo FR for SOC | No | **GAP** |

**For the case study**: These gaps are actually **desirable**. The agent will
encounter these knowledge gaps, learn from experience (QE error messages + its
own physics reasoning), and record insights via `record_insight()`. This is
exactly the knowledge distillation we want to study.

---

## 6. Readiness Matrix

| Scenario | Pseudo Available? | Download via MCP? | Switch via MCP? | Error Guidance? | KB Entry? | Workflow Template? | Verdict |
|----------|------------------|-------------------|-----------------|-----------------|-----------|-------------------|---------|
| SOC (FR pseudo) | Yes: PseudoDojo nc-fr (72 elem), PSlibrary (94 elem), SG15 (64 elem) | Yes: `download_pseudo_library(library='pseudodojo', variant='nc-fr_pbe_standard')` | Yes: `auto_resolve_species_map(library='pseudodojo', variant='nc-fr_pbe_standard')` | No: ENGINE_CRASH only | Partial: SOC entry exists but no pseudo req | Yes: `bands` works for SOC | **SOFT GAP** |
| TDDFT (NCPP) | Yes: NCPP available in PseudoDojo, SG15, HGH | Yes | Yes | No | No | No: no tddft workflow or step type | **BLOCKED** |
| NMR/GIPAW | Yes: 38 elem in GIPAW library + C/H/Si bundled | Yes: `download_pseudo_library(library='gipaw')` | Yes: `auto_resolve_species_map(library='gipaw')` | No | No | No: no scf_gipaw template (but gipaw step exists) | **SOFT GAP** |

---

## 7. Recommendations

### 7.1 Hard Gaps to Fix Before Case Study

| Priority | Gap | Fix | Effort | Required for Case Study? |
|----------|-----|-----|--------|-------------------------|
| P1 | NMR-H1: No `scf_gipaw` workflow template | Add `WorkflowTemplate(id="nmr", step_sequence=("scf", "gipaw"))` to templates.py | 15 min | Yes, for NMR scenario |
| P2 | TDDFT-H1 through H5: TDDFT not registered | Add step types, gen steps, workflow, input model | 2-4 hours | Only if TDDFT scenario desired |

### 7.2 Soft Improvements (nice to have)

| Priority | Gap | Fix | Effort |
|----------|-----|-----|--------|
| P1 | SOC-S4: KB entry doesn't mention pseudo requirements | Update builtin entry to include "Requires full-relativistic pseudopotentials (PseudoDojo nc-fr or PSlibrary rel- prefix)" | 5 min |
| P2 | SOC-S2: No preflight SOC/pseudo check | Add rule: if `lspinorb=true`, check species_map pseudo filename for `rel-` prefix or consult index metadata | 1-2 hours |
| P2 | NMR-S2: No NMR KB entry | Add principle entry about NMR methodology, GIPAW workflow, pseudo requirements | 10 min |
| P3 | SOC-S1: `auto_resolve` has no relativistic filter | Add `relativistic` parameter to `auto_resolve_species_map` tool | 1 hour |
| P3 | SOC-S3: Error enrichment has no SOC classification | Add QE error pattern: "Pseudopotential not suited for this calculation" → SOC_PSEUDO_INCOMPATIBLE | 1 hour |
| P3 | SOC-S5: No SOC demo project | Add `qe_bi_soc.yml` demo with FR pseudo | 30 min |
| P3 | NMR-S1: No NMR demo | Add `qe_benzene_nmr.yml` demo with GIPAW pseudo | 30 min |
| P4 | SOC-S6/NMR-S6: `list_available_resources` doesn't show relativistic field | Add `relativistic` to per-element pseudo info | 30 min |

### 7.3 Knowledge Entries to Add to builtin.db

These entries would improve agent experience, but for the case study we may
intentionally **NOT** add them so the agent learns from scratch:

1. **SOC + Pseudo** (principle): "SOC calculations (lspinorb=.true.) require
   full-relativistic pseudopotentials. Standard SSSP (scalar-relativistic) will
   crash QE. Use PseudoDojo nc-fr_pbe_standard or PSlibrary rel- variants.
   Download with: download_pseudo_library(library='pseudodojo', variant='nc-fr_pbe_standard')."

2. **GIPAW + Pseudo** (principle): "NMR/EPR chemical shift calculations with
   gipaw.x require GIPAW-compatible norm-conserving pseudopotentials (not PAW or
   USPP). Use the GIPAW library: download_pseudo_library(library='gipaw').
   Workflow: scf → gipaw. Tight SCF convergence (conv_thr=1e-10) recommended."

3. **TDDFT Overview** (principle): "Time-dependent DFT in QE uses turbo_lanczos.x
   (linear response) followed by turbo_spectrum.x (spectral properties).
   Requires norm-conserving pseudopotentials (not USPP/PAW). Not yet available
   as a QMatSuite workflow template."

4. **Pseudo Library Guide** (principle): "Pseudopotential library selection guide:
   - Standard DFT: SSSP (precision or efficiency)
   - SOC/spin-orbit: PseudoDojo nc-fr_pbe_standard (full-relativistic NCPP)
   - NMR/EPR: GIPAW library (GIPAW-compatible NCPP)
   - TDDFT: PseudoDojo nc-sr or SG15 (norm-conserving, scalar-relativistic)
   - High-accuracy: PseudoDojo paw-sr_pbe_stringent"

### 7.4 Recommended Case Study Scenario

**Primary: NMR/GIPAW (benzene chemical shifts)**

Rationale:
- Infrastructure nearly complete (only need 1 workflow template addition)
- GIPAW pseudos for C, H are bundled — no download needed for basic case
- Step type, driver support, input format all working
- Knowledge gaps are ideal for distillation: agent must discover GIPAW pseudo
  requirements, tight convergence needs, workflow structure
- Well-defined success metric: correct chemical shift values vs reference

**Stretch: SOC (Bi band structure)**

Rationale:
- All MCP tools needed are present, just not optimally wired
- Agent must discover FR pseudo requirement through failure + reasoning
- Rich learning opportunity: download library, switch pseudo, re-run
- Demonstrates agent's ability to recover from domain errors
- No code changes required (though soft improvements would help)

**Not ready: TDDFT**

Rationale:
- Blocked at step type registration level
- 2-4 hours of development needed before agent can attempt
- Better as a Phase 2 case study after infrastructure work

---

## Appendix A: File Reference

### Pseudo Infrastructure
- `src/qmatsuite/resources/pseudo_libinfo/assets-2025-12-26/PSEUDO_FILE_INDEX.json` — 3,083 pseudo files, 3,623 occurrences
- `src/qmatsuite/resources/pseudo_libinfo/assets-2025-12-26/MANIFEST_PSEUDO_SEED.json` — download archive manifest
- `src/qmatsuite/pseudo/registry.py` — `PseudoRegistry` class, 8 library categories, `resolve_element_from_index()`
- `src/qmatsuite/pseudo/pipeline.py` — 5-step download pipeline
- `src/qmatsuite/pseudo/layout.py` — installed library discovery
- `src/qmatsuite/core/pseudo_config.py` — `PseudoConfig`, `resolve_project_pseudos()`
- `src/qmatsuite/core/pseudo.py` — `ensure_qe_pseudos()` (runtime resolution)

### MCP Tools
- `src/qmatsuite/mcp/tools/download_pseudo_library.py` — library download
- `src/qmatsuite/mcp/tools/resolve_species_map.py` — auto-resolve pseudos
- `src/qmatsuite/mcp/tools/set_species_map.py` — manual pseudo assignment
- `src/qmatsuite/mcp/tools/list_resources.py` — resource discovery
- `src/qmatsuite/mcp/tools/_resource_utils.py` — internal resolution helpers
- `src/qmatsuite/mcp/tools/create_calculation.py` — calculation creation + auto-resolve
- `src/qmatsuite/mcp/tools/apply_preset.py` — preset application (magnetism SOC)
- `src/qmatsuite/mcp/tools/set_parameters.py` — arbitrary parameter setting
- `src/qmatsuite/mcp/tools/inspect_calculation.py` — dry-run + preflight
- `src/qmatsuite/mcp/error_enrichment.py` — error classification + fixes

### SOC Support
- `src/qmatsuite/presets/dimensions.py` — `MagnetismOption.NONCOLLINEAR_SOC`
- `src/qmatsuite/presets/variants_registry.py` — `SOC_CANONICAL` profile
- `src/qmatsuite/presets/integration.py` — physics constraint enforcement
- `src/qmatsuite/ir/parameters.py` — `lspinorb`, `noncolin` IR parameters

### QE TDDFT (partial)
- `src/qmatsuite/drivers/qe/engine/qe_engine.py:43-44` — `tddft_lanczos`, `tddft_spectrum` in EXECUTABLE_MAP
- `src/qmatsuite/drivers/qe/step_types.py` — TDDFT **NOT** in QE_STEP_TYPE_SPECS
- `src/qmatsuite/drivers/qe/driver.py:11-13` — TDDFT **NOT** in SUPPORTED_GEN_STEPS

### NMR/GIPAW
- `src/qmatsuite/drivers/qe/step_types.py:56-60` — `qe_gipaw` step type
- `src/qmatsuite/drivers/qe/driver.py:13` — `gipaw` in SUPPORTED_GEN_STEPS
- `src/qmatsuite/drivers/qe/io/model.py` — `QEModule.GIPAW`, `MODULE_NAMELISTS["gipaw"]`
- `tests/inputformat/samples/qe/nmr_gipaw/` — curated 2-step sample (SCF + GIPAW)
- `src/qmatsuite/resources/pseudo/` — bundled GIPAW pseudos (C, H, Si)

### Knowledge & Validation
- `src/qmatsuite/mcp/knowledge/builtin_entries.py:440-458` — SOC principle entry
- `src/qmatsuite/drivers/qe/preflight.py` — 20 preflight rules (no SOC/pseudo check)
- `src/qmatsuite/workflow/templates.py` — workflow templates (no scf_gipaw, no tddft)

## Appendix B: Pseudo Registry Libraries

Output of `PseudoRegistry().list_libraries()`:

| Library Key | Dir Name | Default Variant | Variants | Versions |
|-------------|----------|-----------------|----------|----------|
| gbrv | GBRV | pbe | lda, pbe, pbesol | 1.5 |
| gipaw | GIPAW | default | default | current |
| hgh | HGH | default | default | current |
| ps-library | PS-Library | default | default, legacy | 1.0.0, legacy |
| pseudodojo | PseudoDojo | nc-sr_pbe_standard | 16 variants (nc-fr/sr, paw-sr, pbe/pbesol/pw, standard/stringent) | 0.4, 1.1 |
| scan_tm | SCAN_TM | default | default | 2017 |
| sg15 | SG15 | oncv | oncv | 2020-02-06 |
| sssp | SSSP | precision | efficiency, precision | 1.3.0 |

## Appendix C: Full-Relativistic Pseudo Coverage

Libraries with full-relativistic pseudos suitable for SOC:

| Library | FR Variant | Elements |
|---------|-----------|----------|
| PseudoDojo | nc-fr_pbe_standard | 72 (Ag, Al, Ar, As, Au, B, Ba, Be, Bi, Br, ...) |
| PseudoDojo | nc-fr_pbe_stringent | 72 |
| PseudoDojo | nc-fr_pbesol_standard | 71 |
| PseudoDojo | nc-fr_pbesol_stringent | 71 |
| PSlibrary | default (rel- prefix files) | 94 |
| SG15 | oncv (some FR) | 64 |

Bi specifically has 30 pseudo files across all libraries, including 8 with
`relativistic=full_rel` and 4 with `has_spin_orbit=true`.
