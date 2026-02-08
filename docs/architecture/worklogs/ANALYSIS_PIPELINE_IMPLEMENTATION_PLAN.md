# Analysis Pipeline Implementation Plan

**Status:** READY FOR IMPLEMENTATION
**Spec:** `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v1.4 (BINDING)
**Proof-of-concept engine:** QE bands (single engine, end-to-end)
**Goal:** Implement the spec, prove with QE bands migration, delete legacy pipeline.

---

## Prerequisites — READ BEFORE IMPLEMENTING

### Test Environment

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

All tests MUST pass at every step boundary. Run the full suite after each step to verify no regressions.

### Governance Documents — READ BEFORE MAKING DECISIONS

When implementing this plan, you WILL encounter design decisions that require understanding the project's laws. Before writing code in any area, read the relevant governance document.

| If working on... | Read FIRST |
|---|---|
| Analysis objects, bundles, transforms, renderers | `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v1.4 (THE authoritative spec for this entire plan) |
| Engine drivers, adding `ANALYSIS_CAPABILITIES` | `docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md` + `CONSTITUTION.md` §17 |
| Engine recipes, runner post-run hook | `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` + `CONSTITUTION.md` §17.4 |
| Step types (GEN/SPEC), step_type_gen, step_type_spec | `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` + `CONSTITUTION.md` §7 |
| Parser registry, provider registration | `docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md` §5–6 |
| CAS, provenance, SQLite, pins | `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md` + `docs/governance/PROVENANCE_IMPLEMENTATION_PLAN.md` |
| SSOT, YAML persistence | `CONSTITUTION.md` §2 |
| Identity, ULIDs | `CONSTITUTION.md` §6 |
| Kernel vs API vs Frontend boundaries | `docs/governance/KERNEL_DEPENDENCY_SPEC.md` + `CONSTITUTION.md` §19 |
| API surface, imports, DTOs | `docs/governance/API_CONSTITUTION.md` + `CONSTITUTION.md` §18 |

### Hard Bans (from CLAUDE.md)

These are ABSOLUTE prohibitions that apply throughout:

1. **No scattered mapping dicts** outside the recipe/registry SSOT
2. **No runner engine imports** — Runner/executor MUST NOT import engine-specific modules
3. **No prefix inference** — Never determine engine from step type by prefix matching
4. **No silent fallbacks** — Unknown types must raise hard errors

### Key Invariants from the Spec (Quick Reference)

- **Inv-A1:** Raw artifacts are evidence, not SSOT. Only `drivers/<engine>/parsers/` reads raw files for analysis.
- **Inv-A2:** AnalysisObjects are engine-agnostic. Defined in `core/analysis/`, NOT in engine drivers.
- **Inv-A4:** CanonicalPrimitiveBundle ONLY from `to_primitives()`. Deterministic. No timestamps.
- **Inv-A5:** DerivedPrimitiveBundle ONLY from `PrimitiveTransform.apply()`. Ephemeral. NEVER cached.
- **Inv-A8:** Visualization consumes PrimitiveBundles via RenderMeta ONLY. MUST NOT read ProvenanceMeta.
- **Inv-A10:** Only canonical bundles may be memoized. Derived NEVER cached.
- **Inv-A11:** CAS is content-addressed by `canonical_sha`. SQLite links `(run_ulid, object_type) → canonical_sha`.
- **Inv-A13:** No `if engine == ...` in universal layer. All dispatch through registry.

---

## Code Map — Existing Files and Insertion Points

### Files to CREATE (new)

| File | Purpose |
|------|---------|
| `src/quantumvitas/core/analysis/bundles.py` | `RenderMeta`, `ProvenanceMeta`, `TransformRecord`, `CanonicalPrimitiveBundle`, `DerivedPrimitiveBundle` |
| `src/quantumvitas/core/analysis/transforms/__init__.py` | Transform package init |
| `src/quantumvitas/core/analysis/transforms/base.py` | `PrimitiveTransform` abstract base class |
| `src/quantumvitas/core/analysis/transforms/fermi_shift.py` | `FermiShift` transform (first concrete transform) |
| `src/quantumvitas/core/analysis/transforms/energy_crop.py` | `EnergyCrop` transform |
| `src/quantumvitas/core/analysis/band_structure/__init__.py` | Band structure package init |
| `src/quantumvitas/core/analysis/band_structure/model.py` | `BandStructure` AnalysisObject (engine-agnostic) |
| `src/quantumvitas/core/analysis/capability.py` | `AnalysisCapability`, `CapabilityMatch`, `find_contiguous_match()` |
| `src/quantumvitas/core/analysis/orchestrator.py` | Post-run analysis orchestrator (capability matching → parse → to_primitives → CAS) |
| `src/quantumvitas/drivers/qe/parsers/bands.py` | QE bands analysis provider (`@register_parser("qe", "bands")`) |
| `tests/core/analysis/test_bundles.py` | Bundle dataclass tests |
| `tests/core/analysis/test_capability.py` | Capability matching tests |
| `tests/core/analysis/test_transforms.py` | Transform tests |
| `tests/core/analysis/test_band_structure.py` | BandStructure model + `to_primitives()` tests |
| `tests/core/analysis/test_orchestrator.py` | Orchestrator integration tests |
| `tests/drivers/qe/test_qe_bands_provider.py` | QE bands provider tests (parse + roundtrip) |
| `tests/gates/test_analysis_invariants.py` | Gate tests for Inv-A2, A4, A5, A6, A8, A13 |

### Files to MODIFY (existing)

| File | What changes |
|------|-------------|
| `src/quantumvitas/core/analysis/base.py` | Update `AnalysisObjectMeta`: `step_ulid` → `step_ulids: list[str]`, add `gen_steps`, `engine_name`, `warnings`, `manifest_snapshot` |
| `src/quantumvitas/core/analysis/__init__.py` | Export new types (bundles, BandStructure, capability) |
| `src/quantumvitas/core/driver_protocol.py` | Add `ANALYSIS_CAPABILITIES: list = []` default on `BaseEngineDriver` |
| `src/quantumvitas/drivers/qe/driver.py` | Add `ANALYSIS_CAPABILITIES` list (bands, trajectory, scf) |
| `src/quantumvitas/provenance/schema.py` | Add `analysis_snapshots` table: `(run_ulid, object_type) → canonical_sha, thumbnail_sha` |
| `src/quantumvitas/provenance/pins.py` | Add `run_ulid_source` field (`exact` / `inferred` / `unknown`) to pin records |

### Files to DELETE (legacy, after migration proven)

| File | Why |
|------|-----|
| `src/quantumvitas/analysis/bands.py` | Replaced by `core/analysis/band_structure/` + `drivers/qe/parsers/bands.py` |
| `src/quantumvitas/analysis/dos.py` | Legacy DOS pipeline (replaced in a follow-up step) |
| `src/quantumvitas/analysis/artifacts.py` | Legacy artifact management (replaced by orchestrator + CAS) |
| `src/quantumvitas/core/analysis/cache.py` | Old `.analysis/` disk cache (replaced by canonical-only memo) |

### Files that MUST NOT be modified (runner is engine-agnostic)

- `src/quantumvitas/execution/runner.py`
- `src/quantumvitas/execution/executor.py`
- `src/quantumvitas/core/driver_registry.py` (no analysis dispatch here)

### Existing patterns to follow

The QE trajectory parser at `src/quantumvitas/drivers/qe/parsers/trajectory.py` is the gold-standard reference for how to write an analysis provider:
- `@register_parser("qe", "trajectory")` decorator
- `can_parse(raw_dir) -> bool`
- `parse(raw_dir, calc_dir, *, run_ulid, step_ulid, calc_ulid) -> Trajectory`
- Returns canonical `Trajectory` object with `AnalysisObjectMeta`

The `Trajectory` model at `src/quantumvitas/core/analysis/trajectory/model.py` shows the pattern for AnalysisObject with `meta: AnalysisObjectMeta` and `to_visual_primitives()` (note: this method will be renamed to `to_primitives()` and its return type changed to `CanonicalPrimitiveBundle`).

---

## Implementation Steps

### Step 1: Update AnalysisObjectMeta (base.py)

**File:** `src/quantumvitas/core/analysis/base.py`

**Changes:**

1. Replace `step_ulid: Optional[str] = None` with `step_ulids: List[str] = field(default_factory=list)`
2. Add `gen_steps: List[str] = field(default_factory=list)`
3. Add `engine_name: str = ""`
4. Add `warnings: List[str] = field(default_factory=list)`
5. Add `manifest_snapshot: Optional[Dict[str, Any]] = None`
6. Update `create()` factory method: remove `step_ulid` param, add `step_ulids`, `gen_steps`, `engine_name`, `warnings`
7. Update `to_dict()` and `from_dict()` for new fields
8. In `from_dict()`, add backward compat: if `step_ulid` (singular) exists in data, wrap it in `[step_ulid]` for `step_ulids`

**Also update all existing callers of `AnalysisObjectMeta.create(step_ulid=...):`**

- `src/quantumvitas/drivers/qe/parsers/trajectory.py` line ~50: change `step_ulid=step_ulid` to `step_ulids=[step_ulid] if step_ulid else []`

**Verify:** `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all existing tests pass.

---

### Step 2: Create Bundle Types (bundles.py)

**File:** `src/quantumvitas/core/analysis/bundles.py` (NEW)

**Implement these dataclasses per spec §6.3, §6.4, §7:**

```python
@dataclass
class RenderMeta:
    axis_labels: dict[str, str]          # {"x": "Energy", "y": "DOS"}
    units: dict[str, str]                # {"x": "eV", "y": "states/eV"}
    series_labels: list[str] | None = None
    reference_energy: float | None = None
    reference_position: float | None = None
    markers: list[Marker] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

@dataclass
class ProvenanceMeta:
    schema_version: str
    object_type: str
    run_ulid: str | None = None
    calc_ulid: str | None = None
    step_ulids: list[str] = field(default_factory=list)
    gen_steps: list[str] = field(default_factory=list)
    engine_name: str = ""
    source_files: list[SourceFileStat] = field(default_factory=list)
    parser_name: str = ""
    parser_version: str = ""
    warnings: list[str] = field(default_factory=list)
    manifest_snapshot: dict | None = None

@dataclass
class TransformRecord:
    transform_name: str
    parameters: dict[str, Any]
    # NO timestamps — derived bundles are ephemeral

@dataclass
class CanonicalPrimitiveBundle:
    bundle_kind: str = "canonical"       # Literal, always "canonical"
    object_type: str = ""
    render_meta: RenderMeta = ...
    provenance_meta: ProvenanceMeta = ...
    series: list[Series1D] = field(default_factory=list)
    geometry_frames: GeometryFrames | None = None
    arrays: dict[str, Any] = field(default_factory=dict)
    # to_dict() and from_dict() methods

@dataclass
class DerivedPrimitiveBundle:
    bundle_kind: str = "derived"         # Literal, always "derived"
    object_type: str = ""
    render_meta: RenderMeta = ...
    provenance_meta: ProvenanceMeta = ...
    series: list[Series1D] = field(default_factory=list)
    geometry_frames: GeometryFrames | None = None
    arrays: dict[str, Any] = field(default_factory=dict)
    transform_chain: list[TransformRecord] = field(default_factory=list)
```

**Key details:**
- `CanonicalPrimitiveBundle` has `to_dict()` that EXCLUDES `created_at` (dedup-friendly, Inv-A4)
- `DerivedPrimitiveBundle` includes `transform_chain`
- Both have `to_dict()` for JSON serialization
- Import `Marker`, `Series1D`, `GeometryFrames` from `primitives.py`
- Import `SourceFileStat` from `base.py`

**Verify:** Write `tests/core/analysis/test_bundles.py` with:
- Bundle construction tests
- `to_dict()` / `from_dict()` roundtrip
- Canonical bundle has no `created_at` in serialized form
- `bundle_kind` is correct literal

---

### Step 3: Create PrimitiveTransform Base + FermiShift

**Files:**
- `src/quantumvitas/core/analysis/transforms/__init__.py` (NEW)
- `src/quantumvitas/core/analysis/transforms/base.py` (NEW)
- `src/quantumvitas/core/analysis/transforms/fermi_shift.py` (NEW)
- `src/quantumvitas/core/analysis/transforms/energy_crop.py` (NEW)

**Implement per spec §8:**

```python
# base.py
from abc import ABC, abstractmethod

class PrimitiveTransform(ABC):
    name: str
    version: str

    @abstractmethod
    def apply(self, bundle) -> DerivedPrimitiveBundle:
        """Transform a bundle. MUST return DerivedPrimitiveBundle."""
        ...

    def validate(self, bundle) -> list[str]:
        """Pre-checks. Returns list of warnings (empty = valid)."""
        return []
```

**FermiShift:**
- Reads `bundle.render_meta.reference_energy`
- Subtracts from all energy-axis y-values in `bundle.series`
- Updates `render_meta.reference_energy = 0.0`
- Appends `TransformRecord("fermi_shift", {})` to `transform_chain`
- Returns `DerivedPrimitiveBundle`

**EnergyCrop:**
- Takes `emin`, `emax` parameters
- Trims series to energy window
- Appends `TransformRecord("energy_crop", {"emin": emin, "emax": emax})`
- Returns `DerivedPrimitiveBundle`

**Transform prohibitions (Inv-A7):**
- No `pathlib.Path` imports
- No `open()` calls
- No imports from `quantumvitas.drivers`
- Pure math only

**Verify:** Write `tests/core/analysis/test_transforms.py` with:
- FermiShift shifts energy values correctly
- FermiShift sets reference_energy to 0.0
- EnergyCrop trims data correctly
- Transform always returns DerivedPrimitiveBundle
- Transform appends TransformRecord
- Transform is pure (no side effects)
- Transform composition works (chain two transforms)

---

### Step 4: Create AnalysisCapability and Matching

**File:** `src/quantumvitas/core/analysis/capability.py` (NEW)

**Implement per spec §5.2 and §5.3:**

```python
@dataclass(frozen=True)
class AnalysisCapability:
    object_type: str                      # "trajectory" | "dos" | "bands" | "scf"
    gen_step_sequence: list[str]          # Ordered, length >= 1
    evidence_files: list[str]            # Expected raw file patterns

@dataclass
class CapabilityMatch:
    object_type: str
    step_ulids: list[str]                # Ordered ULIDs of matched steps
    gen_steps: list[str]                 # Corresponding GEN step names
    evidence_dirs: list[Path]            # Corresponding raw evidence directories

def find_contiguous_match(
    capability: AnalysisCapability,
    ordered_gen_steps: list[tuple[str, str, Path]],  # [(step_ulid, gen_step, raw_dir), ...]
) -> CapabilityMatch | None:
    """
    Match a capability's gen_step_sequence against a run's ordered GEN step list.

    Returns CapabilityMatch if the gen_step_sequence appears as a contiguous
    subsequence, or None if no match.

    Deterministic: prefers first occurrence if ambiguous.
    """
```

**Matching rules:**
- Contiguous subsequence matching
- First occurrence wins (deterministic tie-breaking)
- Each capability produces AT MOST ONE match per run
- A matched step MAY appear in multiple CapabilityMatches

**Verify:** Write `tests/core/analysis/test_capability.py` with:
- Single-step capability matches correctly (e.g., `["scf"]` against `[scf, nscf, bandspw, bands]`)
- Multi-step capability matches correctly (e.g., `["bandspw", "bands"]` against `[scf, nscf, bandspw, bands]`)
- Non-matching capability returns None (e.g., `["dos"]` against `[scf, bandspw, bands]`)
- First occurrence wins when ambiguous
- Overlapping matches are allowed (same step in multiple CapabilityMatches)
- Empty gen_step_sequence raises ValueError
- Deterministic: same input → same output

---

### Step 5: Create BandStructure AnalysisObject

**Files:**
- `src/quantumvitas/core/analysis/band_structure/__init__.py` (NEW)
- `src/quantumvitas/core/analysis/band_structure/model.py` (NEW)

**Implement per spec §6.2:**

```python
@dataclass
class BandStructure:
    """Engine-agnostic band structure analysis object."""
    meta: AnalysisObjectMeta
    k_distances: np.ndarray              # (n_kpoints,) cumulative k-path distance
    eigenvalues: np.ndarray              # (n_kpoints, n_bands) or (n_spin, n_kpoints, n_bands)
    high_symmetry_points: list[HighSymPoint]  # [(k_distance, label), ...]
    fermi_energy: float | None = None    # eV
    spin_polarized: bool = False

    @property
    def n_kpoints(self) -> int: ...
    @property
    def n_bands(self) -> int: ...

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        """
        Convert to canonical primitive bundle. PARAMETER-FREE.

        Produces:
        - series: one Series1D per band (x=k_distance, y=eigenvalue_eV)
        - render_meta.reference_energy = fermi_energy
        - render_meta.markers = high-symmetry points as x-axis Markers
        - render_meta.axis_labels = {"x": "k-path", "y": "Energy"}
        - render_meta.units = {"x": "1/A", "y": "eV"}
        - provenance_meta = split from self.meta (per spec §7.4)
        - arrays["eigenvalues"] = full eigenvalue grid
        """
```

**`HighSymPoint` dataclass** (local to this module or in primitives):
```python
@dataclass(frozen=True)
class HighSymPoint:
    k_distance: float
    label: str
```

**Key `to_primitives()` contract:**
- MUST be parameter-free
- MUST be deterministic (no timestamps, no random IDs in output)
- MUST NOT shift eigenvalues by Fermi energy (that's a transform)
- MUST set `reference_energy = fermi_energy` in RenderMeta (annotation only)
- MUST populate ProvenanceMeta from `self.meta` per §7.4 mapping (exclude `created_at`)
- MUST produce valid markers from `high_symmetry_points`

**Verify:** Write `tests/core/analysis/test_band_structure.py` with:
- Construction with mock data
- `to_primitives()` returns CanonicalPrimitiveBundle with correct bundle_kind
- `to_primitives()` is deterministic (two calls produce byte-equal serialization)
- `reference_energy` set correctly
- Markers match high-symmetry points
- No `created_at` in serialized bundle
- ProvenanceMeta populated correctly from meta
- RenderMeta contains no provenance fields

---

### Step 6: Create QE Bands Analysis Provider

**File:** `src/quantumvitas/drivers/qe/parsers/bands.py` (NEW)

**Pattern:** Follow `drivers/qe/parsers/trajectory.py` exactly.

```python
@register_parser("qe", "bands")
class QEBandsProvider:
    engine = "qe"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check for bands.dat.gnu file."""
        return bool(list(raw_dir.glob("*.bands.dat.gnu")) or
                     list(raw_dir.glob("bands.dat.gnu")))

    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_ulid: str | None = None,
        step_ulids: list[str] | None = None,
        gen_steps: list[str] | None = None,
        calc_ulid: str | None = None,
        evidence_steps: list | None = None,
    ) -> BandStructure:
        """Parse QE bands output to canonical BandStructure."""
```

**Implementation strategy — EXTRACT from legacy:**

The parsing logic already exists in `src/quantumvitas/analysis/parsers.py`:
- `parse_bands_gnu()` (lines ~400–700) — extracts k_distances, energies from `bands.dat.gnu`
- `BandStructureData` — legacy data holder with `k_distances`, `energies`, `high_symmetry_points`, `fermi_energy`

The provider MUST:
1. Locate `bands.dat.gnu` in raw_dir (or within evidence_steps dirs if multi-step)
2. Locate optional `bands.pp.out` (symmetry labels) and `scf.out`/`nscf.out` (Fermi energy, reciprocal lattice)
3. Reuse the core regex-based parsing from `parsers.py` (or import the parsing functions)
4. Convert legacy `BandStructureData` → new `BandStructure` AnalysisObject
5. Populate `AnalysisObjectMeta` with `step_ulids`, `gen_steps`, `engine_name="qe"`, `source_files`

**Multi-step handling:**
- QE bands capability has `gen_step_sequence = ["bandspw"]` (QE produces bands from the bandspw step alone)
- But the provider may also look for SCF/NSCF output in sibling directories for Fermi energy
- If `evidence_steps` is provided, use it; otherwise, search `raw_dir`

**Test data available:**
- `tests/data/analysis_bands/si.bands.dat.gnu` — 736-line GNU plot format
- `tests/data/analysis_bands/si.3_bands.pp.out` — bands.x output with high-sym points
- `tests/data/7_Si_bandStructure/reference/` — full QE bands run with SCF + NSCF + bands outputs

**Verify:** Write `tests/drivers/qe/test_qe_bands_provider.py` with:
- `can_parse()` returns True for dirs with `bands.dat.gnu`
- `can_parse()` returns False for empty dirs
- `parse()` returns `BandStructure` (not legacy `BandStructureData`)
- Parsed data matches expected: n_kpoints, n_bands, fermi_energy
- `meta.engine_name == "qe"`, `meta.parser_name == "qe_bands"`, `meta.object_type == "bands"`
- `meta.source_files` populated with correct calc-relative paths
- Roundtrip: `parse() → to_primitives() → to_dict()` produces valid JSON
- Determinism: two identical parses produce byte-equal canonical bundles

---

### Step 7: Add ANALYSIS_CAPABILITIES to BaseEngineDriver and QEDriver

**File:** `src/quantumvitas/core/driver_protocol.py`

**Change:** Add to `BaseEngineDriver`:

```python
# In class BaseEngineDriver, after COMPANION_ENGINES:
ANALYSIS_CAPABILITIES: list = []  # Override in engine drivers
```

This is a class attribute with an empty default. Engines that don't declare capabilities simply produce no analysis.

**File:** `src/quantumvitas/drivers/qe/driver.py`

**Change:** Add `ANALYSIS_CAPABILITIES` to `QEDriver`:

```python
from quantumvitas.core.analysis.capability import AnalysisCapability

class QEDriver(BaseEngineDriver):
    ...
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="bands",
            gen_step_sequence=["bandspw"],
            evidence_files=["*.bands.dat.gnu"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["*.relax.out"],
        ),
        # Future: scf, dos, phonon, etc.
    ]
```

**Note on import:** Use a lazy import or TYPE_CHECKING guard to avoid circular imports between `core/analysis/capability.py` and `core/driver_protocol.py`. The `ANALYSIS_CAPABILITIES` attribute is just a list; the type annotation is informational.

**Verify:** Run full test suite. Check that:
- `QEDriver().ANALYSIS_CAPABILITIES` returns a non-empty list
- Each capability has `gen_step_sequence` with length >= 1
- `BaseEngineDriver().ANALYSIS_CAPABILITIES` returns `[]`

---

### Step 8: Create Analysis Orchestrator

**File:** `src/quantumvitas/core/analysis/orchestrator.py` (NEW)

**This is the thin scheduling loop per spec §5.5:**

```python
def run_post_run_analysis(
    engine: str,
    driver,
    ordered_gen_steps: list[tuple[str, str, Path]],  # [(step_ulid, gen_step, raw_dir)]
    *,
    run_ulid: str | None = None,
    calc_ulid: str | None = None,
    calc_dir: Path | None = None,
) -> list[dict]:
    """
    Post-run analysis orchestrator.

    For each capability declared by the engine driver:
    1. Match against the run's ordered GEN step list
    2. Resolve analysis provider from registry
    3. Parse raw evidence → AnalysisObject
    4. to_primitives() → CanonicalPrimitiveBundle
    5. Return list of results [{object_type, canonical_bundle, analysis_object}, ...]

    This function does NOT write to CAS or SQLite (that's the API layer's job).
    It performs pure kernel work: parse + transform to canonical.
    """
```

**Implementation:**
```python
for cap in driver.ANALYSIS_CAPABILITIES:
    match = find_contiguous_match(cap, ordered_gen_steps)
    if match is None:
        continue

    provider_cls = get_parser(engine, cap.object_type)
    if provider_cls is None:
        warnings.warn(f"No provider for ({engine}, {cap.object_type})")
        continue

    provider = provider_cls()
    if not provider.can_parse(match.evidence_dirs[0]):
        continue

    # Parse
    if len(match.step_ulids) == 1:
        obj = provider.parse(
            match.evidence_dirs[0], calc_dir,
            run_ulid=run_ulid, step_ulids=match.step_ulids,
            gen_steps=match.gen_steps, calc_ulid=calc_ulid,
        )
    else:
        obj = provider.parse(
            match.evidence_dirs[0], calc_dir,
            run_ulid=run_ulid, step_ulids=match.step_ulids,
            gen_steps=match.gen_steps, calc_ulid=calc_ulid,
            evidence_steps=list(zip(match.step_ulids, match.gen_steps, match.evidence_dirs)),
        )

    canonical = obj.to_primitives()
    results.append({"object_type": cap.object_type, "canonical": canonical, "analysis_object": obj})
```

**Key design:**
- The orchestrator is KERNEL code: pure computation, no persistence
- CAS writes and SQLite updates are the API layer's responsibility
- The orchestrator returns results; the caller decides what to persist
- Failures are logged, not raised — partial success is OK

**Verify:** Write `tests/core/analysis/test_orchestrator.py` with:
- Mock driver with 2 capabilities (bands, trajectory)
- Mock ordered_gen_steps with matching and non-matching steps
- Verify correct number of results returned
- Verify non-matching capabilities are skipped
- Verify failure in one capability doesn't block others
- Integration test: real QE driver + real test data from `tests/data/analysis_bands/`

---

### Step 9: Update Existing Trajectory to Use New Pattern

**File:** `src/quantumvitas/core/analysis/trajectory/model.py`

**Changes:**
1. Rename `to_visual_primitives()` → `to_primitives()`
2. Change return type from `Dict[str, Any]` to `CanonicalPrimitiveBundle`
3. Populate `RenderMeta` and `ProvenanceMeta` from `self.meta`
4. Return `CanonicalPrimitiveBundle` with series and geometry_frames

**File:** `src/quantumvitas/drivers/qe/parsers/trajectory.py`

**Changes:**
- Update `parse()` signature: `step_ulid` → `step_ulids` (accept list)
- Populate `AnalysisObjectMeta` with new fields (`step_ulids`, `gen_steps`, `engine_name`)

**Verify:** All existing trajectory tests pass. The renamed method doesn't break anything because `to_visual_primitives()` was only called from tests and the old analysis pipeline.

---

### Step 10: Add SQLite Analysis Snapshots Table

**File:** `src/quantumvitas/provenance/schema.py`

**Add new table to `SCHEMA_DDL`:**

```sql
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid TEXT NOT NULL,
    object_type TEXT NOT NULL,
    canonical_sha TEXT NOT NULL,          -- SHA-256 of canonical bundle in CAS
    thumbnail_sha TEXT,                   -- SHA-256 of thumbnail in CAS
    step_ulids TEXT NOT NULL,             -- JSON array of step ULIDs
    gen_steps TEXT NOT NULL,              -- JSON array of GEN step names
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(run_ulid, object_type),        -- One canonical per (run, type)
    FOREIGN KEY (run_ulid) REFERENCES runs(run_ulid)
);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_run ON analysis_snapshots(run_ulid);
CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_sha ON analysis_snapshots(canonical_sha);
```

**Bump schema version** to 2 and add migration from v1 → v2 in `migrate_schema()`.

**Also update `src/quantumvitas/provenance/pins.py`:**
- Add `run_ulid_source: str` field to pin records (`"exact"` | `"inferred"` | `"unknown"`)
- Update `pin_analysis_to_history()` to accept and store `run_ulid_source`

**Verify:** Run full test suite. Provenance tests in `tests/gates/test_provenance_*.py` should still pass. Check `tests/gates/test_cas_integrity.py` is unaffected.

---

### Step 11: Gate Tests for Analysis Invariants

**File:** `tests/gates/test_analysis_invariants.py` (NEW)

Implement the gate tests from spec §12.1. Priority order (implement at least these):

1. **test_analysis_object_meta_required** (Inv-A2): Every AnalysisObject subclass in `core/analysis/` has a `meta: AnalysisObjectMeta` field.

2. **test_canonical_bundle_deterministic** (Inv-A4): `to_primitives()` called twice on the same object produces byte-equal serialization. No `created_at` in serialized output.

3. **test_to_primitives_is_parameterless** (Inv-A4): AST scan — all `to_primitives()` signatures accept only `self`.

4. **test_derived_never_cached** (Inv-A5): AST scan — no `@lru_cache`, `@functools.cache`, or dict-based caching on any code path returning `DerivedPrimitiveBundle`.

5. **test_render_meta_no_provenance** (Inv-A6): `RenderMeta` type has no fields for engine_name, run_ulid, step_ulids, parser_name, source_files, or warnings.

6. **test_transform_no_engine_imports** (Inv-A7): AST scan — no transform module imports from `quantumvitas.drivers`.

7. **test_no_engine_branching_in_orchestrator** (Inv-A13): AST scan — orchestrator, bundles, transforms contain no `if engine ==` or `engine_name ==`.

8. **test_analysis_capability_declaration** (§5.2): Every engine with registered analysis providers has matching `ANALYSIS_CAPABILITIES` with `gen_step_sequence` (list, length >= 1).

9. **test_capability_match_deterministic** (§5.3): Same input → same output for capability matching.

**Verify:** All gate tests pass green.

---

### Step 12: End-to-End Integration Test (QE Bands)

**File:** `tests/core/analysis/test_qe_bands_e2e.py` (NEW)

This is the proof-of-concept that the entire pipeline works:

```python
def test_qe_bands_end_to_end():
    """
    Full pipeline: raw QE bands files → BandStructure → CanonicalPrimitiveBundle → JSON.

    Uses test data at tests/data/analysis_bands/.
    """
    raw_dir = Path("tests/data/analysis_bands")
    calc_dir = raw_dir.parent

    # 1. Provider can_parse
    provider = QEBandsProvider()
    assert provider.can_parse(raw_dir)

    # 2. Parse → BandStructure
    band_struct = provider.parse(
        raw_dir, calc_dir,
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
    )
    assert isinstance(band_struct, BandStructure)
    assert band_struct.meta.object_type == "bands"
    assert band_struct.n_kpoints > 0
    assert band_struct.n_bands > 0

    # 3. to_primitives → CanonicalPrimitiveBundle
    canonical = band_struct.to_primitives()
    assert canonical.bundle_kind == "canonical"
    assert canonical.object_type == "bands"
    assert len(canonical.render_meta.markers) > 0  # high-sym points
    assert canonical.provenance_meta.engine_name == "qe"

    # 4. Determinism: two calls produce identical output
    canonical2 = band_struct.to_primitives()
    import json
    assert json.dumps(canonical.to_dict(), sort_keys=True) == \
           json.dumps(canonical2.to_dict(), sort_keys=True)

    # 5. Transform: FermiShift
    from quantumvitas.core.analysis.transforms.fermi_shift import FermiShift
    derived = FermiShift().apply(canonical)
    assert derived.bundle_kind == "derived"
    assert len(derived.transform_chain) == 1
    assert derived.transform_chain[0].transform_name == "fermi_shift"

    # 6. JSON serialization (for frontend transport)
    bundle_json = json.dumps(canonical.to_dict())
    assert "created_at" not in bundle_json  # Inv-A4

def test_qe_bands_orchestrator_integration():
    """
    Orchestrator integration: simulate a run with bandspw step.
    """
    raw_dir = Path("tests/data/analysis_bands")
    driver = QEDriver()

    ordered_gen_steps = [
        ("01STEP1", "bandspw", raw_dir),
    ]

    results = run_post_run_analysis(
        engine="qe",
        driver=driver,
        ordered_gen_steps=ordered_gen_steps,
        calc_dir=raw_dir.parent,
    )

    assert len(results) >= 1
    bands_result = next(r for r in results if r["object_type"] == "bands")
    assert bands_result["canonical"].bundle_kind == "canonical"
```

**Verify:** This test demonstrates the full pipeline end-to-end.

---

### Step 13: Update Trajectory Model to Return CanonicalPrimitiveBundle (Retrofit)

**Already partially done in Step 9.** Ensure the `Trajectory` model's `to_primitives()` returns a proper `CanonicalPrimitiveBundle` with `RenderMeta` and `ProvenanceMeta`, not a raw dict.

Add a test similar to the bands E2E test:

```python
def test_trajectory_to_primitives_returns_bundle():
    """Trajectory.to_primitives() returns CanonicalPrimitiveBundle."""
    traj = ... # construct with mock data
    canonical = traj.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.bundle_kind == "canonical"
```

---

### Step 14: Delete Legacy Pipeline (After All Tests Pass)

**IMPORTANT:** Only delete after steps 1–13 are complete and all tests pass.

1. **Delete** `src/quantumvitas/analysis/bands.py` (replaced by `core/analysis/band_structure/` + `drivers/qe/parsers/bands.py`)
2. **Delete** `src/quantumvitas/core/analysis/cache.py` (old `.analysis/` disk cache)
3. **Update** `src/quantumvitas/analysis/__init__.py` to remove deleted imports
4. **Update** `src/quantumvitas/core/analysis/__init__.py` to remove `CacheManager`, `is_cache_stale` exports
5. **Search** for any remaining imports of deleted modules and fix them:
   - `grep -r "from quantumvitas.analysis.bands import" src/`
   - `grep -r "from quantumvitas.core.analysis.cache import" src/`
6. **Do NOT delete** `src/quantumvitas/analysis/parsers.py` yet — it contains parsing functions still used by the new QE bands provider (the provider reuses the regex-based parsing). It can be refactored later.
7. **Do NOT delete** `src/quantumvitas/analysis/dos.py` yet — DOS migration is a follow-up.
8. **Do NOT delete** `src/quantumvitas/analysis/artifacts.py` yet — it's used by other code paths.

**Verify:** `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all tests pass with no import errors.

---

## Acceptance Criteria Checklist

Each criterion is mechanically verifiable. Check each one after completing all steps.

| # | Criterion | How to verify | Spec ref |
|---|-----------|--------------|----------|
| AC-1 | `BandStructure` has `meta: AnalysisObjectMeta` | `assert hasattr(BandStructure, '__dataclass_fields__') and 'meta' in BandStructure.__dataclass_fields__` | Inv-A2 |
| AC-2 | `BandStructure.to_primitives()` returns `CanonicalPrimitiveBundle` | `assert isinstance(bs.to_primitives(), CanonicalPrimitiveBundle)` | Inv-A4 |
| AC-3 | `to_primitives()` is deterministic | Two calls produce byte-equal JSON; no `created_at` in output | Inv-A4 |
| AC-4 | `FermiShift.apply()` returns `DerivedPrimitiveBundle` | `assert isinstance(result, DerivedPrimitiveBundle)` | Inv-A5 |
| AC-5 | `DerivedPrimitiveBundle` never cached | AST scan in gate test | Inv-A5, Inv-A10 |
| AC-6 | `RenderMeta` has no provenance fields | Inspect `RenderMeta.__dataclass_fields__` — no `engine_name`, `run_ulid`, etc. | Inv-A6 |
| AC-7 | Viz code doesn't read `provenance_meta` | AST scan in gate test | Inv-A8 |
| AC-8 | Transforms don't import from `drivers/` | AST scan in gate test | Inv-A7 |
| AC-9 | No `if engine ==` in orchestrator/bundles/transforms | AST scan in gate test | Inv-A13 |
| AC-10 | `QEBandsProvider` registered as `("qe", "bands")` | `assert get_parser("qe", "bands") is QEBandsProvider` | §5.1 |
| AC-11 | `QEDriver.ANALYSIS_CAPABILITIES` includes bands | `assert any(c.object_type == "bands" for c in QEDriver.ANALYSIS_CAPABILITIES)` | §5.2 |
| AC-12 | Capability matching is deterministic | Same input → same CapabilityMatch (tested) | §5.3 |
| AC-13 | Multi-step capability produces ONE canonical bundle | `["bandspw", "bands"]` → exactly 1 bundle, not 2 | §5.3 |
| AC-14 | Orchestrator returns correct results for QE bands | E2E test with real test data | §5.5 |
| AC-15 | `analysis_snapshots` table in SQLite schema | Schema DDL includes the table | Inv-A11 |
| AC-16 | CAS blob keyed by `canonical_sha` (content hash) | Existing CAS.store() returns SHA-256 — confirmed reusable | Inv-A11 |
| AC-17 | Pin records carry `run_ulid_source` | `PinResult` or pin payload includes the field | Inv-A11 |
| AC-18 | All tests pass | `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` | — |
| AC-19 | Legacy `analysis/bands.py` deleted | File does not exist; no import errors | §14 |
| AC-20 | Gate tests pass | `python -m pytest tests/gates/test_analysis_invariants.py -v` | §12.1 |

---

## Proposed Test Summary

| Test file | Count | What it tests |
|-----------|-------|---------------|
| `tests/core/analysis/test_bundles.py` | ~10 | Bundle construction, to_dict/from_dict, no timestamps in canonical |
| `tests/core/analysis/test_capability.py` | ~10 | Contiguous matching, single/multi-step, no-match, determinism |
| `tests/core/analysis/test_transforms.py` | ~8 | FermiShift, EnergyCrop, composition, purity, DerivedBundle output |
| `tests/core/analysis/test_band_structure.py` | ~8 | BandStructure model, to_primitives, determinism, RenderMeta/ProvenanceMeta split |
| `tests/core/analysis/test_orchestrator.py` | ~6 | Mock driver, matching, failure isolation, partial success |
| `tests/core/analysis/test_qe_bands_e2e.py` | ~4 | Full pipeline with real QE test data |
| `tests/drivers/qe/test_qe_bands_provider.py` | ~8 | can_parse, parse, meta fields, roundtrip, determinism |
| `tests/gates/test_analysis_invariants.py` | ~10 | AST scans for all architectural invariants |
| **Total** | **~64** | |

---

## Dependency Order

```
Step 1 (base.py)
  ↓
Step 2 (bundles.py) ←─── Step 3 (transforms)
  ↓                           ↓
Step 4 (capability)       Step 5 (BandStructure model)
  ↓                           ↓
Step 7 (driver caps)  ←── Step 6 (QE bands provider)
  ↓
Step 8 (orchestrator)
  ↓
Step 9 (trajectory retrofit)
  ↓
Step 10 (SQLite schema)
  ↓
Step 11 (gate tests)
  ↓
Step 12 (E2E integration)
  ↓
Step 13 (trajectory bundle return)
  ↓
Step 14 (delete legacy)
```

Steps 2 and 3 can be done in parallel.
Steps 4 and 5 can be done in parallel (after Step 2).
Steps 6 and 7 depend on Steps 4 and 5.
Step 8 depends on Steps 6 and 7.
Steps 9, 10, 11 depend on Step 8.
Steps 12 and 13 depend on all prior steps.
Step 14 is last.

---

## Non-Goals (Explicitly Out of Scope)

- Implementing DOS, SCF, phonon, or other analysis object types beyond bands (follow-up work)
- Implementing the API layer / QVService orchestration (this plan covers kernel + QE proof only)
- Implementing the Electron frontend rendering (follows after API layer)
- Implementing CAS persistence (CAS already exists; this plan creates the schema and data structures but the actual persist-at-run-end call is API layer work)
- Migrating engines other than QE (each engine gets its own providers later)
- Implementing the memo cache (runtime optimization, implemented in the API layer)

---

*End of Implementation Plan*
