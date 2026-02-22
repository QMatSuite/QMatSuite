# Engine Resource Management Review

**Date:** 2026-02-18
**Scope:** Review of resource handling (pseudopotentials, POTCARs, force fields, basis sets, etc.) across all 15 engines, with design proposals for unified resource management.
**Status:** Review + design proposal only — no source code changes.

---

## 1. Executive Summary

### 1.1 Key Findings

1. **QE has a mature, constitution-backed resource system; all other engines have ad-hoc solutions.** QE pseudopotentials have a 7-module infrastructure (`pseudo.py`, `pseudo_config.py`, `pseudo_materialization.py`, `pseudo_options.py`, `pseudo_runtime.py`, `pseudo_provenance.py`, `pseudo_libinfo.py`) with SHA256 pinning, a 3-source model, and UI-grade option generation. VASP and LAMMPS have basic single-file staging helpers. The remaining 12 engines have zero runtime resource management.

2. **The AI agent cannot discover what pseudopotentials are available.** During the real MCP demo, the agent knew it needed a pseudopotential but had no way to query which filenames exist on disk. The `set_species_map` tool (`src/qmatsuite/mcp/tools/set_species_map.py`) validates syntax only (line 36-41: checks that `cfg` is a dict with a `pseudopot` key) — it performs no file existence check and offers no suggestions. The `create_calculation` tool emits a `context_hint` about `set_species_map` (line 109-113) but provides no actionable data.

3. **Path resolution is dev-only and non-portable.** `paths.py:get_repo_root()` (lines 22-52) walks up from `__file__` looking for `pyproject.toml` + `src/qmatsuite/`. This works in development but fails in any installed package scenario. There is no `QMATSUITE_HOME` environment variable. `.qmatsuite/` is always created at the repo root (line 64-67), not at `~/.qmatsuite/` or any user-configurable location.

4. **No unified resource abstraction exists.** `ResourceRefSpec` in `inputformat/core.py` (lines 49-64) declares staging_policy per engine, but there is no runtime system that implements staging across engines. QE has `ensure_qe_pseudos()`, VASP has `stage_potcar()`, LAMMPS has `stage_potentials()` — three completely independent implementations with different search paths, error handling, and conventions.

5. **The MCP layer has no resource-awareness tools.** The 4 missing tools identified: `list_pseudopotentials` (what's available for an element?), `resolve_species_map` (given a structure, auto-generate species_map), `get_resource_status` (are all required resources present?), `download_pseudo_library` (install missing resources).

### 1.2 Priority Recommendations

| Priority | Recommendation | Impact |
|----------|---------------|--------|
| P0 | Add `list_available_pseudopotentials` MCP tool | Unblocks agent workflow immediately |
| P0 | Add `auto_resolve_species_map` MCP tool | Eliminates the most common agent failure |
| P1 | Pre-run resource validation in `run_calculation` | Prevents cryptic engine failures |
| P1 | Expose VASP `list_available_potcars()` via MCP | Already implemented, just needs wiring |
| P2 | Unified resource resolution chain | Architectural improvement |
| P3 | Portable path resolution (`QMATSUITE_HOME`) | Required for release |

---

## 2. Current State Audit

### 2.1 Global Resource Layout

**Source:** `src/qmatsuite/core/paths.py`

The `.qmatsuite/` directory is the persistent asset root. It is located at the repository root in development mode:

```
.qmatsuite/
├── config/           # paths.py:86-91  — home_config_dir()
│   └── settings.json # paths.py:200-202 — get_settings_json_path()
├── engines/          # paths.py:94-99  — home_engines_dir()
│   ├── qe/           # paths.py:127-132 — home_qe_engines_dir()
│   ├── vasp/         # vasp_potcar.py:77 — potpaw_PBE.64/ subdirs
│   └── lammps/       # lammps_potential.py:37 — potentials/ subdir
├── libraries/        # paths.py:110-115 — home_libraries_dir()
│   └── pseudo/       # paths.py:143-148 — home_pseudo_libraries_dir()
│       └── sssp/     # pseudo_config.py:367-369 — ${version}/${flavor}/library/
├── seeds/            # paths.py:102-107 — home_seeds_dir()
│   ├── qe/           # paths.py:135-140 — home_qe_seeds_dir()
│   └── pseudo/       # paths.py:151-156 — home_pseudo_seeds_dir()
└── logs/             # paths.py:118-123 — home_logs_dir()
```

**Path resolution mechanism:** `get_repo_root()` (lines 22-52) starts from `Path(__file__).parent` and walks up until it finds both `pyproject.toml` and `src/qmatsuite/`. The result is cached in module-level `_repo_root_cache` (line 19). This is the sole entry point; `get_qmatsuite_home_root()` (lines 55-67) delegates to `get_repo_root()` and appends `.qmatsuite/`.

**Gitignore:** `.qmatsuite/` is gitignored (it contains user-local engine binaries and pseudopotential libraries). The `resources/pseudo/` directory (committed, ~30 bundled UPF files) is the only resource directory tracked by git.

**Portability gap:** No `QMATSUITE_HOME` env var exists. No `~/.qmatsuite/` fallback. The `get_repo_root()` function will fail in installed-package scenarios where `pyproject.toml` doesn't exist above the module. The `_find_qmatsuite_root()` function in `pseudo_config.py` (lines 56-67) has the same limitation — it searches for `src/qmatsuite/`, not `pyproject.toml`.

### 2.2 QE Pseudopotential Lifecycle

QE has the most mature resource system. Its lifecycle spans 7 modules:

#### 2.2.1 Constitution (§9)

**Source:** `CONSTITUTION.md`, lines 228-254

Three sources only:
- **internal**: `resources/pseudo/` (committed, ~30 demo/test UPF files)
- **lib**: `~/.qmatsuite/libraries/pseudo/` (SSSP installed via download or seed)
- **project**: `project/pseudo/` (staging area, run-local copies)

A fourth source is explicitly forbidden (line 247).

SHA semantics:
- **SHA256**: Bitwise identical (strict, primary UI key)
- **SHA_FAMILY**: SHA256 after stripping all whitespace (physical equivalence)

#### 2.2.2 Storage Layout

```
resources/pseudo/                          # Internal: ~30 committed UPFs
resources/pseudo_libinfo/<tag>/            # Vendored metadata: MANIFEST + FILE_INDEX
.qmatsuite/libraries/pseudo/              # Lib store
    sssp/1.3.0/efficiency/library/*.UPF   # Installed SSSP
    sssp/1.3.0/efficiency/cutoffs.json
    sssp/1.3.0/efficiency/manifest.json
.qmatsuite/seeds/pseudo/                  # Seed archives for offline install
    sssp/1.3.0/efficiency/*.tar.gz
project/pseudo/                            # Per-project staging area
```

#### 2.2.3 Species Map Fields

Each element in `calculation.yaml`'s `species_map` can have:

| Field | Purpose | Source |
|-------|---------|--------|
| `pseudopot` | Filename (e.g., `Si.pbe-n-rrkjus_psl.1.0.0.UPF`) | User or auto |
| `pseudo_basename` | Preferred basename (same as pseudopot in most cases) | Auto |
| `pseudo_sha256` | Strict bytes identity | Auto (computed on selection) |
| `pseudo_sha_family` | Physical equivalence hash | Auto (computed on selection) |
| `mass` | Atomic mass | User or auto |

**Source:** `pseudo_runtime.py:636` — `species_map_to_selections()` reads these fields.

#### 2.2.4 Resolution Flow (Run-Time)

**`ensure_qe_pseudos()`** — `pseudo.py:67-477`

1. **Extract required elements**: From species_map (primary) or QE input ATOMIC_SPECIES (fallback) (lines 137-212)
2. **For each pseudo file** (lines 382-444):
   - Check `project_pseudo_dir` (project/pseudo)
   - Check `system_pseudo_dir` (resources/pseudo)
   - Check `additional_search_dirs` (test fixtures, `QMS_PSEUDO_PATH` env var)
   - Download if not found (unless `strict=True`)
3. **Placeholder detection**: `__MISSING_PSEUDO__<element>` placeholder pattern (lines 21-47) distinguishes configuration errors from missing files.

**`materialize_calc_pseudos()`** — `pseudo_materialization.py:22-301`

Executed at run-time. Uses SHA256-pinned path when available (lines 100-135), falls back to legacy filename resolution (lines 138-297). Resolution: project/pseudo → internal → installed archives (with tar/zip extraction).

**`prepare_project_pseudos_for_run()`** — `pseudo_runtime.py:349-532`

Step0 executor. The ONLY function allowed to mutate `project/pseudo`. Collision rules:
- Same SHA256 → noop (line 461-469)
- Same SHA_FAMILY, different SHA256 → overwrite with canonical (lines 471-481)
- Different SHA_FAMILY → rename existing file, update affected calculations (lines 483-515)

#### 2.2.5 Download Mechanism

**Source:** `pseudo_config.py:964-1215`

Downloads from GitHub releases (`QMatSuite/qmatsuite-assets`, tag `assets-2025-12-26`). Manifest-driven: fetches `MANIFEST_PSEUDO_SEED.json`, selects entries by version/flavor/xc, downloads tar.gz + cutoffs JSON, verifies SHA256, extracts UPF files to store, optionally caches archive to seed dir.

Supported libraries: SSSP 1.3.0 PBE (efficiency + precision).

#### 2.2.6 UI Option Generation

**Source:** `pseudo_options.py:228-642`

`get_pseudo_options_for_elements()` generates a complete list of available pseudopotentials per element. Each option is a `PseudoVariant` keyed by SHA256 with:
- Sources (project/internal/lib) with installed/corrupt status
- SHA_FAMILY for collision warnings
- Family-match warnings when project has same basename with different bytes

Scan order: project → internal → library (from occurrences index).

### 2.3 Per-Engine Resource Inventory

| Engine | Resource Type | Has Staging? | Staging Policy | Search Locations | Env Var | MCP Exposed? |
|--------|-------------|-------------|----------------|-----------------|---------|-------------|
| **QE** | Pseudopotentials (.UPF) | Yes (7 modules) | copy | project/pseudo → resources/pseudo → QMS_PSEUDO_PATH → download | `QMS_PSEUDO_PATH` | No |
| **VASP** | POTCARs | Yes (1 module) | copy | VASP_PP_PATH → .qmatsuite/engines/vasp/ → CWD walk | `VASP_PP_PATH` | No (list_available_potcars exists but not exposed) |
| **LAMMPS** | Force-field files (.eam, .tersoff, etc.) | Yes (1 module) | copy | LAMMPS_POTENTIALS → .qmatsuite/engines/lammps/potentials/ → CWD walk → Homebrew | `LAMMPS_POTENTIALS` | No |
| **ABINIT** | Pseudopotentials | Declared | reference | None implemented | None | No |
| **Siesta** | Pseudopotentials (.psf/.psml) | Declared | copy | None implemented | None | No |
| **CP2K** | Basis sets + potentials | Declared | reference | None implemented | None | No |
| **QMCPACK** | Wavefunction HDF5 + PPs | Declared | symlink+copy | None implemented | None | No |
| **Gaussian** | Checkpoint files (.chk) | Declared | copy | None implemented | None | No |
| **W90** | .amn/.mmn/.eig from DFT | Declared | symlink | None implemented | None | No |
| **Yambo** | SAVE directory | Declared | symlink | None implemented | None | No |
| **ORCA** | None | N/A | N/A | N/A | N/A | N/A |
| **GPAW** | None (built-in) | N/A | N/A | N/A | N/A | N/A |
| **Psi4** | None (built-in) | N/A | N/A | N/A | N/A | N/A |
| **PySCF** | None (built-in) | N/A | N/A | N/A | N/A | N/A |
| **xTB** | None (built-in) | N/A | N/A | N/A | N/A | N/A |

#### 2.3.1 VASP POTCAR Details

**Source:** `drivers/vasp/engine/vasp_potcar.py`

`stage_potcar()` (lines 97-160) concatenates per-element POTCARs into a single `POTCAR` file. It looks up element POTCARs at `<root>/<library_dir>/<element>/POTCAR` where `library_dir` is `potpaw_PBE.64` or `potpaw_LDA.64` (line 17-19).

`get_default_potcar_root()` (lines 56-94) searches:
1. `VASP_PP_PATH` env var (line 65-69)
2. Repo root → `.qmatsuite/engines/vasp/` (lines 73-80)
3. CWD walk up (lines 83-93)

`list_available_potcars()` (lines 163-191) **already exists** and returns sorted element/variant names (e.g., `["Al", "Al_sv", "Fe", "Fe_pv", "O", "O_s", "Si"]`). This is a key function that should be exposed to MCP but currently is not.

`potcar_overrides` (line 101) allows selecting POTCAR variants (e.g., `Fe_pv` instead of `Fe`). This is critical for materials science accuracy but has no agent-accessible interface.

#### 2.3.2 LAMMPS Potential Details

**Source:** `drivers/lammps/engine/lammps_potential.py`

`extract_potential_refs()` (lines 62-99) scans parsed LAMMPS parameters for potential filenames. Heuristic: looks for tokens containing `.` that aren't purely numeric, in `pair_coeff` entries and `_commands` stream.

`stage_potentials()` (lines 130-187) copies referenced files to the working directory. Search: target_dir → potential_root → recursive search in potential_root.

`get_default_potential_root()` (lines 16-59) searches:
1. `LAMMPS_POTENTIALS` env var (lines 26-30)
2. Repo root → `.qmatsuite/engines/lammps/potentials/` (lines 33-39)
3. CWD walk up (lines 42-53)
4. Homebrew `/opt/homebrew/share/lammps/potentials` (lines 55-57)

The Homebrew fallback (line 55-57) is macOS-specific and a nice touch, but there's no equivalent for Linux package managers.

#### 2.3.3 ResourceRefSpec Declarations (Declared but Not Implemented)

These engines have `ResourceRefSpec` entries in their `inputspec.py` but no runtime staging code:

- **ABINIT** (`drivers/abinit/inputspec.py:48-51`): `staging_policy="reference"` — path reference, not copied
- **Siesta** (`drivers/siesta/inputspec.py:55-58`): `staging_policy="copy"` — `.psf/.psml` files
- **CP2K** (`drivers/cp2k/inputspec.py:39-42`): `staging_policy="reference"` — basis set and potential files
- **QMCPACK** (`drivers/qmcpack/inputspec.py:45-53`): `staging_policy="symlink"` for wavefunction HDF5, `staging_policy="copy"` for PPs
- **Gaussian** (`drivers/gaussian/inputspec.py:46-49`): `staging_policy="copy"` — checkpoint files
- **W90** (`drivers/w90/inputspec.py:49-52`): `staging_policy="symlink"` — DFT prerequisites
- **Yambo** (`drivers/yambo/inputspec.py:52-55`, 78-81): `staging_policy="symlink"` — SAVE directory

#### 2.3.4 Engines With No External Resources

These engines bundle their basis sets internally and require no external resource files:
- **ORCA**: Basis sets built into the binary
- **GPAW**: Uses PAW setups downloaded by GPAW itself
- **Psi4**: Basis sets built-in
- **PySCF**: Basis sets built-in
- **xTB**: Parameters built-in

### 2.4 Portability Assessment

| Aspect | Current State | Portable? | Notes |
|--------|-------------|-----------|-------|
| Repo root detection | Walk up from `__file__` to `pyproject.toml` | Dev-only | Fails in installed packages |
| `.qmatsuite/` location | Always at repo root | Dev-only | No `~/.qmatsuite/` fallback |
| User config path | Platform-specific (`~/Library/Application Support/QMatSuite/config.json`) | Yes | `pseudo_config.py:135-155` handles macOS/Linux/Windows |
| `QMS_PSEUDO_PATH` | Env var for QE pseudo search | Yes | `pseudo.py:344` |
| `VASP_PP_PATH` | Env var for VASP POTCAR search | Yes | `vasp_potcar.py:65` |
| `LAMMPS_POTENTIALS` | Env var for LAMMPS potential search | Yes | `lammps_potential.py:27` |
| SSSP download | GitHub releases via urllib | Yes | `pseudo_config.py:905-961`, SSL via certifi |

**Summary:** The QE pseudo system is partially portable (user config is platform-aware, download works anywhere), but the global path resolution (`paths.py`) is fundamentally tied to the development layout. This is acceptable for the current v2-python phase but must be addressed before any release packaging.

---

## 3. Agent Experience Gap Analysis

### 3.1 Current Friction Points

The MCP agent demo exposed a specific failure mode:

1. Agent calls `create_calculation(engine="qe", workflow="scf", structure_selector="Si")` — succeeds, returns `calc_ulid` and a `context_hint` saying "call set_species_map first".

2. Agent needs to call `set_species_map(calc_ulid, {"Si": {"pseudopot": "???.UPF"}})` — but **cannot determine the filename**. There is no MCP tool to list available pseudopotentials.

3. Agent guesses a filename like `"Si.UPF"` or `"Si.pbe-n-rrkjus_psl.1.0.0.UPF"` — this may or may not match what's actually on disk.

4. `set_species_map` accepts the mapping without checking file existence (`set_species_map.py:36-41` only validates syntax).

5. `run_calculation` fails deep inside `ensure_qe_pseudos()` with a cryptic error about missing pseudo files.

**Root cause:** The agent has no introspection tools. It cannot ask "what pseudopotentials are available for Si?" — a question that the QE backend can already answer via `get_pseudo_options_for_elements()` (`pseudo_options.py:228`) and the VASP backend can answer via `list_available_potcars()` (`vasp_potcar.py:163`).

The same gap exists for VASP (which POTCAR variant to use?) and LAMMPS (which potential files are available?).

### 3.2 Ideal Agent Workflow

The ideal workflow should be:

```
1. Agent: create_calculation(engine="qe", workflow="scf", structure="Si")
   Response: calc_ulid, elements=["Si"]

2. Agent: list_available_resources(engine="qe", elements=["Si"])
   Response: {"Si": [
     {"filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "source": "internal", "installed": true},
     {"filename": "Si.pbe-nl-kjpaw_psl.1.0.0.UPF", "source": "lib:sssp-1.3.0-efficiency", "installed": true},
     ...
   ]}

3. Agent: set_species_map(calc_ulid, {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}})
   Response: OK (validated that file exists)

4. Agent: run_calculation(calc_ulid)
   Response: completed (or: "missing resource: ..." with actionable fix)
```

Or even simpler with auto-resolution:

```
1. Agent: quick_run(engine="qe", workflow="scf", structure="Si")
   → auto-resolves species_map from internal/lib resources
   → runs calculation
   Response: completed
```

### 3.3 Specific Missing Capabilities

| Capability | Status | Blocking? |
|-----------|--------|-----------|
| List pseudopotentials for element (QE) | `get_pseudo_options_for_elements()` exists, not MCP-exposed | Yes |
| List POTCAR variants for element (VASP) | `list_available_potcars()` exists, not MCP-exposed | Yes |
| List potentials for LAMMPS | `extract_potential_refs()` + dir listing possible, not implemented | Moderate |
| Auto-resolve species_map from structure | Not implemented | Yes |
| Pre-run resource validation | Not implemented | Yes |
| Download missing resources on demand | QE SSSP download exists, not MCP-exposed | Moderate |
| Resource status check | Not implemented | Moderate |

---

## 4. Design Proposal

### 4.1 Resource Taxonomy

Resources fall into four categories:

| Category | Example | Engines | Cardinality | Lifecycle |
|----------|---------|---------|-------------|-----------|
| **Per-element pseudopotential** | UPF, POTCAR, PSP8 | QE, VASP, ABINIT, Siesta, QMCPACK | 1 per element | Selected per calculation |
| **Global basis/potential files** | BASIS_MOLOPT, GTH_POTENTIALS | CP2K | 1 per engine config | Shared across calculations |
| **Per-calculation force fields** | EAM, Tersoff, ReaxFF | LAMMPS | 1+ per calculation | Specific to potential model |
| **Workflow prerequisite files** | .amn, .eig, SAVE/, .chk, HDF5 | W90, Yambo, Gaussian, QMCPACK | 1+ per workflow chain | Generated by previous step |

Category 4 (workflow prerequisites) is fundamentally different — these files are generated by upstream steps, not selected from a library. They should be handled by the workflow/runner system, not the resource management system.

### 4.2 Unified Storage Layout

Proposed layout (building on the existing `.qmatsuite/` structure):

```
.qmatsuite/
├── engines/
│   ├── qe/                    # QE binaries (existing)
│   ├── vasp/
│   │   └── potpaw_PBE.64/     # VASP POTCARs (existing)
│   └── lammps/
│       └── potentials/        # LAMMPS potentials (existing)
├── libraries/
│   └── pseudo/
│       ├── sssp/              # SSSP library (existing)
│       │   └── 1.3.0/efficiency/library/
│       ├── pseudodojo/        # Future: PseudoDojo
│       └── archives/          # Downloaded archives (existing)
├── resources/                 # NEW: Engine-agnostic resource store
│   ├── cp2k/
│   │   ├── BASIS_MOLOPT
│   │   └── GTH_POTENTIALS
│   └── abinit/
│       └── pseudos/           # ABINIT pseudo collection
└── config/
    └── settings.json          # Existing user config
```

**Key decision:** Keep the existing QE pseudo system (`libraries/pseudo/`) as-is. It's mature and works. For other engines, add engine-specific directories under `.qmatsuite/engines/` (which already exists for VASP and LAMMPS). The `resources/` directory is for engine-agnostic resources.

### 4.3 Resolution Chain

For per-element pseudopotentials (QE, VASP, ABINIT, Siesta, QMCPACK), the resolution chain should be:

```
1. project/pseudo/              (project-local copies)
2. resources/pseudo/             (committed internal demos)
3. .qmatsuite/libraries/pseudo/  (installed SSSP/PseudoDojo)
4. env var (QMS_PSEUDO_PATH, VASP_PP_PATH, etc.)
5. Download (if allowed and library known)
```

For engine-specific resources (VASP POTCARs, LAMMPS potentials):

```
1. Working directory
2. Engine env var (VASP_PP_PATH, LAMMPS_POTENTIALS)
3. .qmatsuite/engines/<engine>/
4. System package paths (Homebrew, etc.)
```

This matches the existing implementations but formalizes the chain.

### 4.4 Staging Protocol

The existing `ResourceRefSpec.staging_policy` already declares the correct strategy per engine:

| Policy | Meaning | Used By |
|--------|---------|---------|
| `copy` | Copy file to working directory | QE, VASP, Siesta, LAMMPS, QMCPACK (PPs), Gaussian |
| `symlink` | Symlink to source (saves space for large files) | QMCPACK (HDF5), W90, Yambo |
| `reference` | Path reference in input file (no copy) | ABINIT, CP2K |

**Proposal:** Implement a generic `stage_resource()` function that dispatches based on `staging_policy`:

```python
def stage_resource(
    ref: ResourceRefSpec,
    source_path: Path,
    target_dir: Path,
) -> Path:
    """Stage a resource file according to its policy."""
    if ref.staging_policy == "copy":
        shutil.copy2(source_path, target_dir / source_path.name)
    elif ref.staging_policy == "symlink":
        (target_dir / source_path.name).symlink_to(source_path)
    elif ref.staging_policy == "reference":
        return source_path  # No staging needed
    return target_dir / source_path.name
```

This would live in `inputformat/` (leaf package, no kernel deps) alongside `ResourceRefSpec`.

### 4.5 MCP Tool Design

#### Tool 1: `list_available_resources` (P0)

```python
@mcp.tool
def list_available_resources(
    engine: str,
    elements: list[str] | None = None,
) -> dict:
    """List available resources (pseudopotentials, POTCARs, etc.) for an engine.

    Args:
        engine: Engine family (e.g. 'qe', 'vasp', 'lammps').
        elements: Optional element filter (e.g. ['Si', 'O']).
    """
```

Backend dispatch:
- `qe` → `get_pseudo_options_for_elements()` (already exists in `pseudo_options.py:228`)
- `vasp` → `list_available_potcars()` (already exists in `vasp_potcar.py:163`)
- `lammps` → directory listing of `get_default_potential_root()` (new, trivial)
- Others → return `{"resources_available": false, "reason": "built-in"}`

**Response format:**
```json
{
  "engine": "qe",
  "resources": {
    "Si": [
      {
        "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        "source": "internal",
        "installed": true,
        "recommended": true
      }
    ]
  }
}
```

#### Tool 2: `auto_resolve_species_map` (P0)

```python
@mcp.tool
def auto_resolve_species_map(
    calc_ulid: str,
    library: str = "sssp",
    flavor: str = "efficiency",
) -> dict:
    """Auto-resolve and set species_map for a calculation.

    Determines required elements from the calculation's structure,
    then resolves pseudopotentials from available sources.

    Args:
        calc_ulid: Calculation ULID.
        library: Preferred pseudo library (default: 'sssp').
        flavor: Library quality flavor (default: 'efficiency').
    """
```

Backend:
1. Load calculation → get structure → extract elements
2. For QE: use `resolve_project_pseudos()` (already exists in `pseudo_config.py:1326`)
3. For VASP: use `list_available_potcars()` and pick default variant per element
4. Set species_map on calculation
5. Return resolved mapping

This is the single most impactful tool — it turns the agent's 4-step failure mode into a 1-step success.

#### Tool 3: Pre-run resource validation (P1)

Add validation inside `run_calculation` and `quick_run` before the actual run:

```python
# In run_calculation, before svc.run.run_calculation():
def _validate_resources(calc_ulid: str, svc) -> list[str]:
    """Check that all required resources are present."""
    detail = svc.calculation.get_detail(calc_ulid)
    engine = detail.get("engine_family", "")
    species_map = detail.get("species_map", {})

    issues = []
    if engine in ("qe", "abinit", "siesta") and not species_map:
        issues.append("species_map not set — call set_species_map() first")

    for element, cfg in species_map.items():
        pp = cfg.get("pseudopot", "")
        if not pp or pp.startswith("__MISSING_PSEUDO__"):
            issues.append(f"No pseudopotential configured for {element}")

    return issues
```

#### Tool 4: `get_resource_status` (P2)

```python
@mcp.tool
def get_resource_status(calc_ulid: str) -> dict:
    """Check resource readiness for a calculation.

    Returns which resources are present, missing, or need installation.
    """
```

### 4.6 Manifest Format

QE's existing `MANIFEST_PSEUDO_SEED.json` format (used by `pseudo_config.py:758-846`) is well-designed:

```json
{
  "schema_version": "1.0",
  "generated_at": "2025-12-26T...",
  "files": [
    {
      "relative_path": "sssp/1.3.0/PBE/efficiency/SSSP_1.3.0_PBE_efficiency.tar.gz",
      "size_bytes": 12345678,
      "sha256": "abc123...",
      "category": "sssp",
      "library_name": "sssp",
      "library_version": "1.3.0",
      "xc": "pbe",
      "quality": "efficiency"
    }
  ]
}
```

**Proposal:** Keep this format for QE pseudos. For other engines, use a simpler `resources.json` per engine:

```json
{
  "engine": "vasp",
  "resource_type": "potcar",
  "entries": [
    {"element": "Si", "variant": "Si", "path": "potpaw_PBE.64/Si/POTCAR"},
    {"element": "Si", "variant": "Si_sv", "path": "potpaw_PBE.64/Si_sv/POTCAR"}
  ]
}
```

### 4.7 SHA Semantics

Constitution §9.4 defines:
- **SHA256** = bitwise identity (strict, line 251)
- **SHA_FAMILY** = SHA256 after stripping all whitespace (physical equivalence, line 252)

**Source:** `pseudo_libinfo.py` implements `compute_sha_family_file()` which strips whitespace before hashing.

**Recommendation:** Keep SHA256/SHA_FAMILY for QE pseudopotentials (where the distinction matters because different distributions may have whitespace differences). For VASP POTCARs and LAMMPS potentials, SHA256 alone is sufficient (these files are either binary or have standardized formatting).

### 4.8 Path Resolution (Dev/Release)

**Current state (dev-only):**
```python
# paths.py:22-52
def get_repo_root() -> Path:
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() and (current / "src" / "qmatsuite").exists():
            return current
        current = current.parent
    raise RuntimeError(...)
```

**Proposed (portable):**
```python
def get_qmatsuite_home() -> Path:
    """Get QMatSuite home directory.

    Resolution order:
    1. QMATSUITE_HOME env var
    2. ~/.qmatsuite/ (user home)
    3. Repo root / .qmatsuite/ (dev mode fallback)
    """
    env_home = os.environ.get("QMATSUITE_HOME")
    if env_home:
        return Path(env_home)

    user_home = Path.home() / ".qmatsuite"
    if user_home.exists():
        return user_home

    # Dev mode fallback
    try:
        return get_repo_root() / ".qmatsuite"
    except RuntimeError:
        # Not in dev mode — create at user home
        user_home.mkdir(parents=True, exist_ok=True)
        return user_home
```

This is a P3 item — needed for packaging but not blocking current development.

### 4.9 Edge Cases

1. **Multiple projects sharing the same `.qmatsuite/`**: Currently all projects under the same repo root share one `.qmatsuite/`. This is fine for development but may cause issues if multiple projects need different pseudo libraries. The project-level `project/pseudo/` already handles this for per-calculation resources.

2. **VASP POTCAR licensing**: VASP POTCARs cannot be freely distributed. The system correctly uses env vars and local paths rather than download. No change needed.

3. **CP2K basis sets shipped with CP2K**: CP2K's `BASIS_MOLOPT` and `GTH_POTENTIALS` are shipped with CP2K itself. The `staging_policy="reference"` correctly handles this by pointing to the installation path. The system just needs to know where CP2K is installed (env var `CP2K_DATA_DIR`).

4. **QMCPACK multi-step workflows**: QMCPACK requires wavefunction HDF5 from a prior DFT step. This is a workflow prerequisite, not a library resource. The `staging_policy="symlink"` correctly handles this, but the source path must be resolved from the upstream step's output directory.

5. **Offline/air-gapped environments**: The QE pseudo system already supports this via seed archives (manual import → install from seed). Other engines don't have download capability, so they already work offline (user provides files manually).

---

## 5. Implementation Roadmap

### Phase 1: Agent Unblocking (P0, ~2-3 days)

**Goal:** Make the AI agent able to complete QE and VASP calculations without human intervention.

1. **Add `list_available_resources` MCP tool**
   - Wire QE → `get_pseudo_options_for_elements()` (exists)
   - Wire VASP → `list_available_potcars()` (exists)
   - Wire LAMMPS → directory listing (new, ~20 lines)
   - New file: `src/qmatsuite/mcp/tools/list_resources.py`

2. **Add `auto_resolve_species_map` MCP tool**
   - Wire QE → `resolve_project_pseudos()` (exists in `pseudo_config.py:1326`)
   - Wire VASP → pick default POTCAR variant per element (new, ~40 lines)
   - New file: `src/qmatsuite/mcp/tools/resolve_species_map.py`

3. **Add pre-run resource validation in `run_calculation`**
   - Check species_map is set for pseudo engines
   - Check pseudo files resolve to existing files
   - Return actionable error with `context_hint` on failure
   - Modified file: `src/qmatsuite/mcp/tools/run_calculation.py`

4. **Enhance `set_species_map` with file existence validation**
   - Add optional file existence check (warning, not error)
   - Suggest available alternatives when file not found
   - Modified file: `src/qmatsuite/mcp/tools/set_species_map.py`

### Phase 2: Resource Validation (P1, ~2 days)

**Goal:** Prevent cryptic engine failures with clear, early error messages.

1. **Implement `get_resource_status` MCP tool**
   - Check all resources for a calculation before run
   - Return structured status per resource

2. **Add resource readiness check to `inspect_calculation` dry_run**
   - Include resource status in dry_run output
   - Show which resources are resolved vs. missing

3. **Enhance `quick_run` with auto-resolution**
   - If species_map not provided, auto-resolve for QE/VASP
   - Log resolution in response

### Phase 3: Unified Abstraction (P2, ~3-5 days)

**Goal:** Bring all engines to a common resource management baseline.

1. **Implement `stage_resource()` in inputformat**
   - Generic staging based on `ResourceRefSpec.staging_policy`
   - Copy, symlink, and reference policies

2. **Add CP2K basis set resolution**
   - Env var `CP2K_DATA_DIR` support
   - List available basis sets

3. **Add ABINIT pseudo resolution**
   - Path reference support
   - List available pseudos

4. **Add Siesta pseudo resolution**
   - Copy-based staging like QE
   - List available pseudos

### Phase 4: Portability (P3, ~2 days)

**Goal:** Make resource paths work outside the development repo.

1. **Add `QMATSUITE_HOME` env var support**
2. **Add `~/.qmatsuite/` fallback**
3. **Update all `_find_repo_root()` functions to use unified resolution**

---

## 6. Open Questions

### Q1: Should `auto_resolve_species_map` be opt-in or default?

**Option A (Conservative):** `quick_run` always requires explicit `species_map` for pseudo engines. Agent must call `auto_resolve_species_map` separately.

**Option B (Progressive):** `quick_run` auto-resolves species_map if not provided, using the default library (SSSP 1.3.0 efficiency for QE).

**Recommendation:** Option B. The whole point of `quick_run` is to reduce friction. The agent can always override with explicit `species_map` if the default is wrong.

### Q2: Should VASP POTCAR variant selection be automated?

VASP has multiple POTCAR variants per element (e.g., `Fe` vs `Fe_pv` vs `Fe_sv`). The "standard" choice depends on the calculation type and accuracy requirements.

**Option A:** Always use bare element name (e.g., `Fe`).
**Option B:** Use recommended variants from VASP manual/community (e.g., `Fe_pv` for most calculations).
**Option C:** Let the user choose via preset dimension.

**Recommendation:** Option B as default with Option C as override. The VASP community has well-known "recommended" variants for each element.

### Q3: How should CP2K/ABINIT basis set paths be discovered?

CP2K expects `BASIS_SET_FILE_NAME` to be an absolute path or a file in the working directory. ABINIT expects `pp_dirpath` with pseudopotential files.

**Option A:** Require env vars (`CP2K_DATA_DIR`, `ABINIT_PP_DIR`).
**Option B:** Auto-detect from engine binary location.
**Option C:** Store in `.qmatsuite/engines/<engine>/`.

**Recommendation:** Option A + C. Env var as primary, `.qmatsuite/engines/` as secondary. Auto-detection from binary is fragile.

### Q4: Should we support per-project pseudo libraries?

Currently, the SSSP library is installed globally in `.qmatsuite/libraries/pseudo/`. Should different projects be able to use different SSSP versions?

**Recommendation:** No, for now. Global library + per-project `project/pseudo/` override is sufficient. The current system already allows project-level overrides via `project/pseudo/` directory (Constitution §9.3).

### Q5: What about ONCVPSP / PseudoDojo support?

The QE pseudo system is designed for SSSP but the architecture supports any library with `(sha256, basename, archive)` triples. PseudoDojo/ONCVPSP would need:
- New entries in `pseudo_libinfo` index
- New manifest entries for download
- No code changes to the resolution chain

**Recommendation:** Add when there's demand. The architecture is ready.

## 7. Architectural Decisions (2026-02-18)

Decisions made during Stage P2 implementation planning.

### D1: App Data Location — Platform-Specific, NOT ~/.qmatsuite/

- **Decision**: Use platform-specific application data directories, not a visible dotfile in home.
- **Rationale**: `~/.qmatsuite/` is too visible and too easy for users to accidentally delete or corrupt.
- **Paths**: macOS `~/Library/Application Support/QMatSuite/`, Windows `%LOCALAPPDATA%\QMatSuite\`, Linux `~/.local/share/qmatsuite/`, Dev mode `repo_root/.qmatsuite/`, Override via `QMATSUITE_HOME` env var.
- **Resolution order**: (1) `QMATSUITE_HOME` env var, (2) Platform-specific app data, (3) `repo_root/.qmatsuite/` dev fallback.
- **Implementation**: Single `get_qmatsuite_home() -> Path` function in `paths.py`.

### D2: Program vs Resources Separation

- **Decision**: QMatSuite program binaries and user/engine resources are fully separated. App updates do NOT touch the resource directory.
- Program goes in platform install location; Resources go in `get_qmatsuite_home()`.
- Updating version never re-downloads pseudo libraries; uninstalling optionally preserves resources; multiple versions can share the same resource directory.

### D3: External Engine Pointer Mechanism

- **Decision**: User-installed engines (VASP, ORCA, etc.) are NOT copied into the resource directory. Instead, an `engine.json` pointer file records their location.
- Defines the full directory layout under `get_qmatsuite_home()` (engines, bin, libraries, knowledge, config, logs).
- Defines `engine.json` format with engine, version, source, paths (binary, potcar_root), configured_at, configured_by.
- Runner resolution chain: (1) QMatSuite-managed binary, (2) engine.json pointer, (3) PATH lookup, (4) Error with hint.

### D4: Auto-Resolve Species Map Uses SSSP Precision

- **Decision**: Auto-resolution defaults to SSSP 1.3.0 Precision library (not Efficiency).
- **Rationale**: One pseudo per element (no ambiguity), higher cutoffs are safer, full distribution ships with it, efficiency library has multiple choices per element in some cases.
- If SSSP Precision is not installed, auto-resolve returns an actionable error with download instructions.

### D5: Download Requires User Consent (Client-Side)

- **Decision**: The `download_pseudo_library` tool itself does NOT block for consent. It is the client's responsibility to confirm with the user before executing side-effect operations.
- Follows the BYOE principle.

### D6: No Agent Self-Download Mechanism

- **Decision**: Agents must NOT use curl/wget to download resources directly. All resource downloads go through QMatSuite tools.
- **Rationale**: Bypasses SHA verification, won't be in resolution chain, no provenance record, not reproducible.

### D7: Distribution Strategy (Lite vs Full)

- **Lite version**: QMatSuite program only, empty resource directory, user downloads engines and pseudos on demand.
- **Full version**: QMatSuite program + pre-populated resource directory including QE binary + SSSP 1.3.0 Precision, out-of-box `quick_run(engine="qe", ...)` works immediately.
- Both versions include micromamba binary.

### D8: Micromamba Placement

- **Decision**: Micromamba binary lives at `get_qmatsuite_home()/bin/micromamba`. Conda environments go to `engines/conda-envs/`.
- Micromamba is very stable (C++ reimplementation of conda) with strong backward compatibility. Pin a version and update rarely.
