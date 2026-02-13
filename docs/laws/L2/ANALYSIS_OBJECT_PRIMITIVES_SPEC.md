# AnalysisObject → Primitive Pipeline Specification

**Status:** BINDING v1.5
**Date:** 2026-02-12
**Scope:** Data model, transform contract, persistence policy, layering, post-run pipeline ordering, run-level capability matching, and GUI result surfaces for analysis output rendering.

---

## Table of Contents

1. [Terminology](#1-terminology)
2. [Invariants](#2-invariants)
3. [GUI Result Surfaces](#3-gui-result-surfaces)
4. [Post-Run Pipeline Ordering](#4-post-run-pipeline-ordering)
5. [Engine Analysis Provider Registry](#5-engine-analysis-provider-registry)
6. [Data Model](#6-data-model)
7. [PrimitiveBundle Metadata: RenderMeta vs ProvenanceMeta](#7-primitivebundle-metadata-rendermeta-vs-provenancemeta)
8. [Transform Layer Contract](#8-transform-layer-contract)
9. [Visualization Contract](#9-visualization-contract)
10. [Caching and Persistence Policy](#10-caching-and-persistence-policy)
11. [Layering Responsibilities](#11-layering-responsibilities)
12. [Acceptance Criteria and Future Gate Tests](#12-acceptance-criteria-and-future-gate-tests)

---

## 0. Motivation & Philosophy

> **Merge note**: This section incorporates the "Big Picture & Motivation" from the former `ANALYSIS_OBJECTS_FRAMEWORK.md` (v1.1, 2026-01-19, PROPOSED). The Framework document has been retired; its unique motivational context is preserved here.

### The Two-Layer Philosophy

QMatSuite manages computational materials science workflows across multiple engines (QE, VASP, LAMMPS, ORCA, PySCF, etc.). Each engine has its own:
- Input format (INCAR vs pw.in vs .inp)
- Output format (OUTCAR vs .out vs .xyz)
- Trajectory format (XDATCAR vs .pos/.vel vs .dcd)
- Units (Ry vs eV, Bohr vs Å)
- Conventions (stress sign, cell vectors)

**Core Principle**: Separation of concerns between engine artifacts and canonical analysis.

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: Engine Artifacts (raw/)                                │
│                                                                   │
│  • Engine-native inputs and outputs                              │
│  • Engine-specific formats (OUTCAR, .out, XDATCAR, etc.)         │
│  • Evidence for analysis derivation (not SSOT)                   │
│  • We do NOT force a universal artifact format                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  Parser (one per engine × object type)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2: Canonical Analysis Objects (in-memory)                 │
│                                                                   │
│  • Engine-agnostic dataclasses                                   │
│  • Unified units (Å, eV, eV/Å, fs, GPa, K)                       │
│  • Common schema for same task type                              │
│  • All visualization/analysis targets these objects              │
│  • NO engine-specific fields in core schema                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  to_primitives()
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2a: Canonical Primitive Bundles                            │
│                                                                   │
│  • Renderer-consumable arrays + RenderMeta + ProvenanceMeta      │
│  • Deterministic, dedup-friendly (CAS by content hash)           │
│  • Can be regenerated from raw evidence anytime                  │
└──────────────────────────────────────────────────────────────────┘
```

### Why This Matters

1. **Multi-engine support**: Supporting VASP, QE, LAMMPS, ORCA, etc. trajectory/DOS/bands without separate viewers per engine.

2. **Consistent user experience**: User compares DOS from QE and VASP runs. Same plotting interface, same units.

3. **Future-proofing**: Adding a new engine requires only a parser, not touching UI/viz/analysis code.

### System Boundaries

- **`calc/raw/`** — Engine-native evidence files. Read-only for analysis; never modified by analysis code. Not SSOT (see Inv-A1).
- **CAS (`.provenance/.cas/`)** — Content-addressed storage for canonical bundle snapshots. For provenance replay only; operational path derives from raw evidence (see Inv-A11).
- **SQLite** — Post-run digests (`run_steps.digest_json`) and CAS linkage rows (`(run_ulid, object_type) → canonical_sha`). See §10.

---

## 1. Terminology

| Term | Definition |
|------|-----------|
| **Raw artifact** | Engine-native output file residing in `calc/raw/` (e.g., `vasprun.xml`, `scf.out`, `DOSCAR`). Raw artifacts are engine-native *evidence* used for analysis derivation. They are NOT SSOT. |
| **SSOT** | Present-tense YAML resources only: `calculation.yaml`, `step.yaml`, structure resources. Raw artifacts, analysis objects, and primitive bundles are never SSOT. |
| **Post-run digest** | Small, flat summary of a completed step (energy, convergence, Fermi level, forces, timing). Mandatory. Persisted eagerly into SQLite immediately after each step completes. Examples: `VASPDigest`, `ORCADigest`, `LAMMPSDigest`. Derived from the step's primary output text; it is NOT an AnalysisObject. |
| **AnalysisObject** | Engine-agnostic, in-memory domain data structure derived from raw evidence by an engine analysis provider. Carries full numeric payload (arrays, frames, spectra) plus a single `AnalysisObjectMeta` container. |
| **AnalysisObjectMeta** | The mandatory metadata container on every AnalysisObject. Contains provenance IDs, source file stats, parser identity, and warnings. Defined once; every AnalysisObject subclass inherits the same schema. |
| **to_primitives()** | The required, parameter-free method on every AnalysisObject that produces a `CanonicalPrimitiveBundle`. Deterministic and pure. The ONLY producer of CanonicalPrimitiveBundle. |
| **CanonicalPrimitiveBundle** | The deterministic, dedup-friendly reshaping of an AnalysisObject into renderer-consumable arrays and annotations. May ONLY be produced by `AnalysisObject.to_primitives()`. Contains no timestamps, random IDs, or environment-dependent fields. |
| **DerivedPrimitiveBundle** | A primitive bundle produced by applying a `PrimitiveTransform` to a canonical or derived bundle. May ONLY be produced by `PrimitiveTransform`. Ephemeral: MUST NOT be cached or persisted. |
| **PrimitiveTransform** | A pure math operation `(Canonical|Derived) -> Derived`. Examples: smoothing, cropping, resampling, Fermi-shift, 3D-to-2D slice. Transforms MUST NOT read raw artifacts or contain engine logic. |
| **PrimitiveBundle** | Generic term covering both `CanonicalPrimitiveBundle` and `DerivedPrimitiveBundle`. Visualization accepts either. |
| **RenderMeta** | The renderer-facing metadata namespace inside a PrimitiveBundle: axis labels, units, series labels, markers, suggested reference/offset values. Viz MAY use RenderMeta for rendering decisions. |
| **ProvenanceMeta** | The provenance/audit metadata namespace inside a PrimitiveBundle: engine name, run ULID, step ULIDs, GEN step names, source files, parser identity, warnings. Viz MUST NOT use ProvenanceMeta for rendering decisions. |
| **View parameter** | Any rendering/display control: smoothing window, crop range, slice plane, camera angle, color map. View parameters live exclusively in the frontend or transform call site. They MUST NOT appear inside AnalysisObjects or PrimitiveBundles. |
| **Engine analysis provider** | Code in `drivers/<engine>/parsers/` that reads raw evidence and returns AnalysisObjects. Registered via the centralized analysis provider registry. Providers are the only code permitted to read raw artifacts for analysis purposes. |
| **GEN step** | Engine-agnostic intent step type (e.g., `"scf"`, `"bands"`, `"dos"`, `"relax"`). Analysis capabilities are defined over ordered GEN step sequences. See `STEP_TYPE_GEN_SPEC_CONSTITUTION.md`. |
| **AnalysisCapability** | A declaration by an engine driver that it can produce a specific analysis object type from an ordered GEN step sequence (length ≥ 1). See §5.2. |
| **CapabilityMatch** | The result of matching an `AnalysisCapability` against a run's ordered GEN step list. Contains the matched step ULIDs, GEN step names, and raw evidence directories. One canonical bundle is produced per match. See §5.3. |
| **Evidence corpus (.tmp)** | Non-committed R&D corpus at `.tmp/engine_research/<engine>/`. Append-only for development. Runtime analysis MUST NOT read from `.tmp/`; CI/tests MUST NOT depend on `.tmp/` content. |
| **Demo store** | Committed curated demos at `resources/demo_projects/`. Integrity-gated. Used for GUI gallery, test fixtures, and golden-ref validation. |

---

## 2. Invariants

These invariants are BINDING. Each is labeled for cross-reference and future gate enforcement.

### Inv-A1: Raw Artifacts Are Evidence, Not SSOT

> Raw artifacts are engine-native evidence used for analysis derivation. They are NOT SSOT. SSOT in this project refers exclusively to `calculation.yaml`, `step.yaml`, and structure resources.

- Engine analysis providers MUST read raw evidence to produce AnalysisObjects.
- No code outside `drivers/<engine>/parsers/` may read raw artifacts for analysis derivation.
- Deleting raw artifacts makes analysis unavailable but MUST NOT break SSOT or project runnability.
- Runtime analysis MUST only read the calculation's own `calc/raw/` evidence. It MUST NOT read from `.tmp/engine_research/` or any external corpus.

### Inv-A2: AnalysisObjects Are Universal and Engine-Agnostic

> AnalysisObjects are the sole in-memory domain representation of analysis results. They are engine-agnostic in type and interface.

- Every AnalysisObject MUST carry exactly one `AnalysisObjectMeta` field.
- AnalysisObject subclasses (Trajectory, BandStructure, DOS, etc.) are defined in `core/analysis/`, not in engine drivers.
- Engine analysis providers return instances of these shared types; they MUST NOT define engine-specific AnalysisObject subclasses.
- AnalysisObjects MUST NOT contain view parameters (smoothing, cropping, camera, slice, color).

### Inv-A3: AnalysisObjectMeta Is the Single Metadata Schema

> Every AnalysisObject carries a single `AnalysisObjectMeta` instance. No alternative metadata containers.

Required fields in `AnalysisObjectMeta`:

| Field | Type | Purpose |
|-------|------|---------|
| `schema_version` | str | Schema version of this meta format |
| `object_type` | str | Discriminator: `"trajectory"`, `"dos"`, `"bands"`, `"scf"`, etc. |
| `created_at` | str (ISO 8601) | Timestamp of object construction (runtime only; excluded from CAS serialization) |
| `source_files` | list[SourceFileStat] | Paths + size + mtime of raw files consumed (across all matched steps) |
| `run_ulid` | str or None | Provenance: which run produced the raw evidence |
| `calc_ulid` | str or None | Provenance: parent calculation |
| `step_ulids` | list[str] | Ordered list of step ULIDs covered by this capability match (same order as the matched GEN step sequence) |
| `gen_steps` | list[str] | Corresponding ordered GEN step names (same length/order as `step_ulids`) |
| `engine_name` | str | Engine family (informational; MUST NOT drive rendering) |
| `parser_name` | str | Registered provider identifier |
| `parser_version` | str | Provider version for reproducibility |
| `warnings` | list[str] | Parser warnings (non-fatal issues during parsing) |

The `source_files` list enables staleness detection: if any source file's `(size_bytes, mtime)` differs from the cached meta, the analysis is stale and must be re-derived.

A `manifest_snapshot` field (dict, optional) is reserved for future use: a minimal digest of the run manifest state at parse time, for debugging cross-run staleness. It MAY be defined as empty/None and populated later without a schema break.

### Inv-A4: Canonical Bundles May Only Come From to_primitives() — Deterministic and Dedup-Friendly

> `CanonicalPrimitiveBundle` may ONLY be produced by `AnalysisObject.to_primitives()`. Canonical bundles MUST be deterministic and deduplicable.

- `to_primitives()` MUST be a required, non-optional method on every AnalysisObject subclass.
- `to_primitives()` MUST accept zero parameters.
- `to_primitives()` MUST be deterministic and pure: identical raw evidence + identical parser version => identical canonical bundle (semantically identical after float normalization; not necessarily byte-identical to raw evidence).
- Canonicalization operations allowed inside `to_primitives()`: reshape, reindex, unit normalization, reference annotation (e.g., `reference_energy = E_F`). These are expected and represent the data as standard 1D/2D/3D arrays. Arrays MUST NOT be shifted, smoothed, or cropped.
- **Dedup rule:** `CanonicalPrimitiveBundle` MUST NOT contain timestamps, random IDs, process IDs, or any environment-dependent fields. If runtime timing is needed for debugging, it MUST be kept outside the canonical bundle (e.g., in a separate debug log) and explicitly excluded from CAS serialization.

### Inv-A5: Derived Bundles May Only Come From PrimitiveTransform — Always Ephemeral

> `DerivedPrimitiveBundle` may ONLY be produced by `PrimitiveTransform`. Derived bundles are always ephemeral.

- `PrimitiveTransform` accepts a `CanonicalPrimitiveBundle` or `DerivedPrimitiveBundle` as input.
- `PrimitiveTransform` MUST ALWAYS output a `DerivedPrimitiveBundle`, never a `CanonicalPrimitiveBundle`.
- No other code path may construct a `DerivedPrimitiveBundle`.
- `DerivedPrimitiveBundle` MUST NOT be cached (no LRU, no single-slot, no memoization of any kind).
- `DerivedPrimitiveBundle` MUST NOT be persisted anywhere (not CAS, not SQLite, not filesystem).
- Derived bundles are always recomputed on-the-fly by re-applying transforms to a canonical bundle.

### Inv-A6: Bundles Contain Data, RenderMeta, and ProvenanceMeta Only

> PrimitiveBundles carry numeric arrays plus two distinct metadata namespaces: RenderMeta (for rendering) and ProvenanceMeta (for audit/debugging). Nothing more.

Allowed in **RenderMeta** (renderer-facing):
- Axis labels, units, series names
- Suggested reference values (e.g., `reference_energy`, `reference_position`) as scalar annotations
- Annotation markers (positions + labels for high-symmetry points, phase boundaries, etc.)
- Series labels, array dimension labels

Allowed in **ProvenanceMeta** (audit-facing):
- `object_type`, `schema_version`
- `run_ulid`, `calc_ulid`
- `step_ulids` (ordered list), `gen_steps` (ordered list)
- `source_files` (list of SourceFileStat)
- `parser_name`, `parser_version`
- `warnings`
- `engine_name` (informational; MUST NOT be used for rendering branching)
- `manifest_snapshot` (reserved)

Allowed in **bundle body** (data):
- 1D/2D/3D numeric arrays (numpy ndarrays or plain lists for serialization)
- Geometry frames (positions, species, cell, pbc, per-atom scalars)

Forbidden everywhere in bundles:
- View parameters: smoothing window, crop range, zoom level, camera position, color map, line width, font size
- Timestamps, random IDs, or environment-dependent values (in canonical bundles)
- Raw file paths or raw file contents

### Inv-A7: Transforms Are the Only Place for Data Manipulation

> `PrimitiveTransform` is the ONLY mechanism for applying mathematical or data-processing operations to primitive bundles.

- Transforms perform pure math: smoothing, cropping, resampling, unwrapping, Fermi-shifting, 3D-to-2D slicing, derivative computation, interpolation.
- Transforms MUST NOT read raw artifacts.
- Transforms MUST NOT depend on engine-specific knowledge or import engine driver code.
- Transforms MUST NOT write to disk, databases, or CAS.
- Visualization code MUST NOT perform transforms (not even simple ones like energy shifting).

### Inv-A8: Visualization Consumes Only PrimitiveBundles via RenderMeta

> All visualization code MUST consume PrimitiveBundles exclusively, using only numeric arrays and RenderMeta for rendering decisions.

- Visualization code accepts `CanonicalPrimitiveBundle` or `DerivedPrimitiveBundle`.
- Visualization MUST render "as-is" from numeric arrays + RenderMeta only.
- Visualization MUST ignore ProvenanceMeta entirely. It MUST NOT branch on engine name, parser identity, run/step ULIDs, or any ProvenanceMeta field.
- Visualization MUST NOT read raw artifacts.
- Visualization MUST NOT call engine parsers.
- Visualization MUST NOT perform data transforms (use PrimitiveTransform instead).
- Both Electron UI and Python renderers MUST consume the same PrimitiveBundle schema. No separate data formats for different rendering targets.

### Inv-A9: Lazy Means Trigger Timing Only

> "Lazy" in this system means on-demand computation trigger. It does NOT mean lazy payload objects inside AnalysisObjects.

- Post-run digests are eager and mandatory: parsed and persisted into SQLite immediately after each step completes.
- Canonical primitives are eagerly materialized at end-of-run via capability matching (see §4). On-demand recomputation is allowed for subsequent requests if staleness is detected.
- There MUST NOT be `LazyArray`, `LateList`, deferred-load proxy objects, or similar lazy payload wrappers inside AnalysisObjects. Once constructed, an AnalysisObject holds all its data in memory.
- All kernel calls in the analysis path are synchronous.

### Inv-A10: Canonical-Only Memoization; Derived Never Cached

> Only CanonicalPrimitiveBundles (and their source AnalysisObjects) may be memoized in memory. Derived bundles and transform outputs are ALWAYS computed on-the-fly.

- In-memory memoization of AnalysisObjects and CanonicalPrimitiveBundles is allowed as a runtime enhancement in long-lived processes (daemon, Jupyter kernel). CLI processes typically do not cache.
- In-memory memoization of the raw→canonical path (raw evidence → AnalysisObject → `to_primitives()`) is allowed and recommended as a runtime optimization. This memoization is not persisted truth and may be dropped at any time. It does not violate present-tense SSOT because live analysis always derives from present raw evidence when the cache is cold or stale.
- `DerivedPrimitiveBundle` MUST NOT be memoized or cached in any form: no LRU cache, no single-slot cache, no dictionary lookup, no memoization decorator.
- `PrimitiveTransform` outputs are always recomputed by applying the transform chain to the canonical bundle.
- There MUST NOT be a persistent (on-disk) cache for any analysis results (neither AnalysisObjects nor any PrimitiveBundles).
- No cross-process cache pointers or shared-memory analysis stores.
- Every process that needs analysis MUST be capable of re-deriving it from raw evidence.

### Inv-A11: CAS Is Content-Addressed; Persistence Is Explicit and Scoped (Tier 0.8)

> CAS stores blobs by content hash (`canonical_sha`). Tuples like `(run_ulid, object_type)` are SQLite linkage fields, not CAS dedup identities. Derived bundles are never persisted.

- **CAS identity is content hash.** CAS stores and deduplicates blobs by `canonical_sha` (e.g., sha256 of the serialized canonical bundle payload). `(run_ulid, object_type)` is a SQLite index, not a CAS key.
- **SQLite links runs to CAS blobs.** SQLite stores association rows `(run_ulid, object_type, step_ulids, …) → canonical_sha`. "Keep-latest" / "overwrite-on-recompute" semantics apply to the SQLite reference row (which hash is "current"), not to CAS blob identity.
- The operational UI path MUST derive analysis from raw evidence on demand. It MUST NOT implicitly read CanonicalPrimitiveBundles from CAS as a substitute for live derivation. In-memory reuse of canonical bundles computed from present evidence within the same process is allowed.
- CAS is used ONLY for explicit provenance replay and snapshot viewing features.
- Auto-persistence into CAS is allowed ONLY for:
  - (a) `CanonicalPrimitiveBundle`: one per capability match per run. CAS blob keyed by `canonical_sha`; SQLite links `(run_ulid, object_type) → canonical_sha` (overwrite-on-recompute updates the SQLite reference, not the CAS blob).
  - (b) A "last rendered thumbnail" per capability match per run. Same content-addressed storage (`thumbnail_sha`) and SQLite linkage.
- Canonical snapshots MUST NOT require an "owner_step_ulid". ProvenanceMeta contains `step_ulids` and `gen_steps`, sufficient for provenance tracing and UI association.
- `DerivedPrimitiveBundle` MUST NEVER be persisted to CAS or any other store.
- **User pin actions:** Pins persist additional screenshots or view snapshots as separate CAS entries (append, not auto-managed). When pinning, the API MAY attempt best-effort inference of `run_ulid` for the pin record:
  - (A) Evidence fingerprint match against recorded run artifacts in SQLite (exact match).
  - (B) Fallback: latest successful run for the calculation.
  - (C) Otherwise: `run_ulid` = null.
  The pin record MUST carry a `run_ulid_source` field (`exact` | `inferred` | `unknown`) indicating provenance confidence. This inference is for provenance display/audit only and MUST NOT affect runtime logic, skip logic, or correctness.

### Inv-A12: Layering — Kernel vs API vs Frontend

> Kernel provides pure capabilities. API owns orchestration and persistence. Frontend interacts only with API.

- **Kernel** provides: engine analysis providers, AnalysisObject types, `to_primitives()`, PrimitiveTransform implementations, and pure rendering functions.
- **API/QVService** owns: request routing, canonical-only in-memory memoization, ALL writes to SQLite and CAS (including overwrite/dedup policies for Tier-0.8 snapshots), and post-run pipeline orchestration.
- **Frontend** (Electron or Jupyter) interacts ONLY with the API layer. It MUST NOT import kernel modules directly, call parsers, or access SQLite/CAS.

### Inv-A13: No Engine Branching in the Universal Layer

> The universal analysis layer (orchestrator, bundle types, transforms, renderers) MUST NOT contain `if engine == ...` logic. All engine-specific dispatch goes through the analysis provider registry.

- The orchestrator resolves engine identity from the step's SSOT metadata and dispatches to the registered provider. No fallback, no pattern matching.
- Unknown engine + object_type combinations MUST raise a hard error, not silently skip or fall back.

### Inv-A14: Evidence Corpus Isolation

> `.tmp/engine_research/` is for R&D only. Runtime analysis reads only `calc/raw/`. CI/tests depend only on committed fixtures and `resources/demo_projects/`.

- No import path, runtime code, or test fixture may reference `.tmp/` content.
- Demo store at `resources/demo_projects/` is committed and integrity-gated.

---

## 3. GUI Result Surfaces

The GUI presents three clearly separated result surfaces for a completed step. These are distinct subsystems; they share no code paths.

### Surface A: Raw Text Viewer

- Direct file viewer over `calc/raw/` artifacts (stdout, stderr, log files, input echoes).
- Read-only filesystem access; no parsing, no domain model.
- NOT part of the analysis pipeline. GUI opens files directly from raw evidence.

### Surface B: Step Digest Panel

- Displays the post-run digest (energy, convergence, forces, timing, etc.) at the top of the step results panel.
- Data source: SQLite `run_steps.digest_json` column (pre-persisted, already available).
- GUI reads digest JSON from API; no parser invocation at display time.
- Digest is NOT an AnalysisObject. It feeds summary dashboards and timeline queries.

### Surface C: Analysis Visualization

- Full analysis pipeline: raw evidence → AnalysisObject → CanonicalPrimitiveBundle → (optional transforms) → PrimitiveBundle → renderer.
- Data source: live derivation from raw evidence via the analysis provider registry (canonical bundle may be memoized in memory or read from CAS for provenance replay only).
- GUI renders PrimitiveBundles using arrays + RenderMeta only (Inv-A8).
- Available analysis types are determined by matching the engine's declared capabilities against the run's GEN step list (§5).
- **UI step-to-analysis association:** When a user clicks a step, the UI shows analysis tiles whose canonical `ProvenanceMeta.step_ulids` includes that step's ULID. This is membership-based, not ownership-based — a single canonical bundle may appear under multiple steps.

### Surface Isolation

| Concern | Surface A | Surface B | Surface C |
|---------|-----------|-----------|-----------|
| Data source | `calc/raw/` files directly | SQLite digest_json | Raw evidence → AnalysisObject → Bundle |
| Parsing | None | None at display time | Engine analysis provider |
| Domain model | None | Flat digest dict | AnalysisObject + PrimitiveBundle |
| Transforms | N/A | N/A | PrimitiveTransform (optional) |
| Persistence | N/A | SQLite (mandatory, eager) | CAS Tier-0.8 (optional, eager) |

---

## 4. Post-Run Pipeline Ordering

After a run completes, the Runner/API layer executes the following phases **in order**. This is the eager materialization pipeline. Failures at any phase MUST NOT block subsequent phases or fail the overall run.

### Phase 1: Step Digests (mandatory, per-step)

```
For each completed step in the run:
  → Runner calls registered digest provider: get_parser(engine, "scf_digest")
  → Digest dataclass returned (engine-specific, flat)
  → Digest serialized to JSON → SQLite run_steps.digest_json
  → DONE. Digest is immediately available for Surface B.
```

Failure mode: If digest parsing fails for a step, log a warning and continue to the next step. The run status is still set. Digest absence is displayed as "digest unavailable" in the GUI.

### Phase 2: Run-Level Capability Matching and Eager Canonical Primitives

```
Run completes → collect the run's ordered GEN step list with ULIDs:
  [(step_ulid_1, "scf"), (step_ulid_2, "nscf"), (step_ulid_3, "bandspw"), (step_ulid_4, "bands")]

engine = resolve_engine(run)
capabilities = engine_driver.ANALYSIS_CAPABILITIES

For each capability in capabilities:
  → Match capability.gen_step_sequence against the run's ordered GEN step list
  → If no match: skip
  → If match found (a CapabilityMatch):
      matched_steps = [(step_ulid, gen_step, raw_dir), ...]  # ordered
      → Resolve analysis provider from registry
      → provider.parse(matched_steps) → AnalysisObject
      → analysis_object.to_primitives() → CanonicalPrimitiveBundle
      → canonical_sha = hash(serialize(CanonicalPrimitiveBundle))
      → Persist blob to CAS by canonical_sha
      → SQLite: link (run_ulid, object_type) → canonical_sha (overwrite-on-recompute)
      → Store in in-memory memo cache keyed by canonical_sha
```

Failure mode: If any single capability fails, log a warning and continue to the next capability. Partial success is allowed. The run status is unaffected.

**Example:** A VASP run with GEN steps `[scf, nscf, bandspw, bands]` and engine capabilities:

| Capability | `gen_step_sequence` | Match result |
|---|---|---|
| `scf` (object_type=`"scf"`) | `["scf"]` | Matches step 1 → one canonical SCF bundle |
| `bands` (object_type=`"bands"`) | `["bandspw", "bands"]` | Matches steps 3–4 → one canonical bands bundle |
| `dos` (object_type=`"dos"`) | `["dos"]` | No match (no dos step in this run) → skipped |

Result: 2 canonical bundles produced (not 4). The bands bundle's `step_ulids` lists both step 3 and step 4.

### Phase 3: Default Thumbnails (per canonical bundle produced in Phase 2)

```
For each CanonicalPrimitiveBundle produced in Phase 2:
  → Render default thumbnail (headless, no user style)
  → thumbnail_sha = hash(thumbnail_bytes)
  → Persist thumbnail to CAS by thumbnail_sha
  → SQLite: link (run_ulid, object_type) → thumbnail_sha (overwrite-on-rerender)
```

Failure mode: If thumbnail rendering fails, log a warning. Thumbnail absence is displayed as a placeholder in the GUI.

### Phase 4: Provenance Writes

```
Record run completion in SQLite:
  → Update run status, finished_at
  → canonical_sha and thumbnail_sha references (from Phases 2–3) stored in run_steps
```

### Ordering Guarantees

- Phase 1 completes before Phase 2 begins (digest may inform analysis decisions, e.g., convergence gating).
- Phase 2 and Phase 3 may be interleaved per-capability (produce canonical for capability A, render thumbnail for capability A, then capability B, etc.) or batched. The spec does not prescribe internal ordering.
- Phase 4 runs after all analysis phases complete (or fail gracefully).
- The entire post-run pipeline is synchronous within the Runner's post-run hook. No background jobs, no deferred queues.

---

## 5. Engine Analysis Provider Registry

### 5.1 Registry Design

The analysis provider registry is an extension of the existing parser registry (`parsers/registry.py`). It maps `(engine, object_type)` tuples to provider classes. The universal orchestration layer dispatches through this registry and MUST NOT contain engine-specific branching (Inv-A13).

```
Registry: dict[(engine: str, object_type: str)] -> ProviderClass
```

- Registration is via `@register_parser(engine, object_type)` decorator (existing mechanism).
- Lookup is via `get_parser(engine, object_type)` (existing mechanism).
- Unknown `(engine, object_type)` MUST return None; the orchestrator raises a hard error if a declared-supported capability has no registered provider.

### 5.2 AnalysisCapability Declaration

Each engine driver declares, **in a single location**, the analysis capabilities it supports. Each capability specifies an ordered GEN step sequence that must be present in a run for the analysis to be produced.

```
AnalysisCapability
├── object_type: str                    "trajectory" | "dos" | "bands" | "scf" | ...
├── gen_step_sequence: list[str]        Ordered GEN step sequence (length ≥ 1)
│                                       e.g., ["scf"] or ["bandspw", "bands"]
└── evidence_files: list[str]           Expected raw file patterns (for can_parse())
                                        e.g., ["DOSCAR", "vasprun.xml"]
```

Each engine driver exposes this declaration as:

```
class <Engine>Driver:
    ...
    ANALYSIS_CAPABILITIES: list[AnalysisCapability] = [...]
```

**Key properties:**
- `gen_step_sequence` is **ordered** and represents a contiguous subsequence that must appear in the run's GEN step list.
- Length 1 = single-step analysis (common case). Length > 1 = multi-step analysis.
- The old `multi_step: bool` flag is subsumed by `len(gen_step_sequence) > 1`.

**Examples by engine:**

| Engine | object_type | gen_step_sequence | Rationale |
|--------|-------------|-------------------|-----------|
| VASP | `"scf"` | `["scf"]` | Single SCF step |
| VASP | `"bands"` | `["bandspw", "bands"]` | Needs NSCF k-path then band extraction |
| QE | `"bands"` | `["bandspw"]` | QE produces bands from bandspw alone |
| VASP | `"trajectory"` | `["relax"]` | Geometry optimization trajectory |
| ORCA | `"scf"` | `["scf"]` | Single-point energy |

### 5.3 Run-Level Capability Matching

At end-of-run, the orchestrator matches each declared capability against the run's ordered GEN step list. Each successful match produces exactly one `CapabilityMatch`:

```
CapabilityMatch
├── object_type: str                    From the matched capability
├── step_ulids: list[str]              Ordered ULIDs of the matched steps
├── gen_steps: list[str]               Corresponding GEN step names
└── evidence_dirs: list[Path]          Corresponding raw evidence directories
```

**Matching rules:**
- A capability matches if its `gen_step_sequence` appears as a **contiguous subsequence** of the run's ordered GEN step list.
- Each capability produces **at most one** canonical bundle per run. If the same sequence could match in multiple positions, the implementation MUST use a deterministic tie-breaking rule (e.g., prefer the first occurrence).
- A matched step MAY appear in multiple CapabilityMatches (e.g., an SCF step may be covered by both the `"scf"` capability and a `"bands"` capability that starts with SCF). This is expected — the same step can contribute evidence to multiple analysis types.
- Unmatched capabilities are silently skipped (the run simply lacks those analysis types).

**UI association** is by membership, not ownership:
- When a user clicks any step in the GUI, display analysis tiles whose `ProvenanceMeta.step_ulids` includes that step's ULID.
- A bands bundle covering steps [bandspw, bands] appears when clicking either step.
- There is NO "belongs to last step" or "owner step" semantic.

### 5.4 Provider Protocol

Every analysis provider (registered via `@register_parser`) MUST implement:

```
class AnalysisProvider:
    engine: str                         # Engine family
    object_type: str                    # Analysis kind

    def can_parse(self, raw_dir: Path) -> bool
        """Check if raw evidence is present and parseable."""

    def parse(self, raw_dir: Path, **context) -> AnalysisObject
        """
        Parse raw evidence and return a universal AnalysisObject.

        For single-step capabilities (gen_step_sequence length 1):
          raw_dir = the matched step's raw directory.

        For multi-step capabilities (gen_step_sequence length > 1):
          raw_dir = first matched step's raw directory (by convention).
          context["evidence_steps"] = [(step_ulid, gen_step, raw_dir), ...]
            ordered list of all matched steps.
        """
```

- `parse()` MUST return a universal AnalysisObject subclass (defined in `core/analysis/`).
- `parse()` MUST NOT return engine-specific types.
- `parse()` MUST populate `AnalysisObjectMeta` fully, including `step_ulids` and `gen_steps`.

### 5.5 Analysis Scheduling (Thin)

Analysis scheduling is deliberately thin. It is NOT a DAG system, NOT a UI model, and NOT a separate planner.

The scheduling logic runs once at end-of-run:

```
after run R completes:
    engine = resolve_engine(R)
    capabilities = engine_driver.ANALYSIS_CAPABILITIES
    ordered_gen_steps = [(s.step_ulid, s.step_type_gen, s.raw_dir) for s in R.steps]

    for cap in capabilities:
        match = find_contiguous_match(cap.gen_step_sequence, ordered_gen_steps)
        if match is None:
            continue

        provider = get_parser(engine, cap.object_type)
        if provider is None:
            warn("no provider registered for ({engine}, {cap.object_type})")
            continue
        if not provider.can_parse(match.evidence_dirs[0]):
            continue

        if len(match.step_ulids) == 1:
            obj = provider.parse(match.evidence_dirs[0])
        else:
            obj = provider.parse(
                match.evidence_dirs[0],
                evidence_steps=list(zip(match.step_ulids, match.gen_steps, match.evidence_dirs)),
            )

        canonical = obj.to_primitives()
        canonical_sha = persist_to_cas(canonical)                      # CAS by content hash
        link_in_sqlite(R.run_ulid, cap.object_type, canonical_sha)     # SQLite linkage
        render_thumbnail(canonical)                                     # Phase 3
```

This is expressible as a for-loop over the capability list with simple contiguous-subsequence matching. No graph resolution, no priority queues, no async scheduling.

**Suggestion (implementation strategy A — preferred):** Add `ANALYSIS_CAPABILITIES` as a class attribute on `BaseEngineDriver` (empty by default). Each engine populates it in its driver subclass. The Runner's post-run hook iterates the list. This requires zero changes to runner.py dispatch logic; the capability list is data, not code.

**Suggestion (matching determinism):** To avoid overlapping ambiguity, prefer longest match first, then stable declaration order. If a capability `["bandspw", "bands"]` and a capability `["bandspw"]` are both declared, the longer one matches first and consumes both steps; the shorter one then has no remaining `bandspw` to match (greedy-longest). Implementer freedom is OK as long as behavior is deterministic and documented.

---

## 6. Data Model

### 6.1 AnalysisObjectMeta

```
AnalysisObjectMeta
├── schema_version: str               "1.0"
├── object_type: str                  "trajectory" | "dos" | "bands" | "scf" | ...
├── created_at: str                   ISO 8601 (runtime only; excluded from CAS serialization)
├── source_files: list[SourceFileStat]
│   └── SourceFileStat
│       ├── path: str                 Calc-relative (e.g., "raw/vasprun.xml")
│       ├── size_bytes: int
│       └── mtime: float              Unix timestamp
├── run_ulid: str | None
├── calc_ulid: str | None
├── step_ulids: list[str]             Ordered step ULIDs covered by this capability match
├── gen_steps: list[str]              Corresponding ordered GEN step names
├── engine_name: str                  Engine family (informational; MUST NOT drive rendering)
├── parser_name: str                  Registered provider ID
├── parser_version: str
├── warnings: list[str]               Parser warnings
└── manifest_snapshot: dict | None    Reserved for future (stale/debug)
```

Note: `created_at` is a runtime convenience field. It MUST be excluded when serializing a CanonicalPrimitiveBundle for CAS persistence, to preserve dedup-friendliness (Inv-A4).

### 6.2 AnalysisObject (Abstract Base)

Every concrete AnalysisObject subclass MUST:
1. Carry a `meta: AnalysisObjectMeta` field.
2. Implement `to_primitives() -> CanonicalPrimitiveBundle`.
3. Contain no view parameters.
4. Be defined in `core/analysis/`, not in engine drivers.

```
AnalysisObject (abstract)
├── meta: AnalysisObjectMeta          [REQUIRED]
├── to_primitives() -> CanonicalPrimitiveBundle   [REQUIRED, parameter-free]
└── ... domain-specific data fields ...
```

Concrete subclasses (non-exhaustive):

| Subclass | object_type | Key data fields |
|----------|-------------|----------------|
| `Trajectory` | `"trajectory"` | frames (positions, species, cell, pbc, forces, velocities, energy, temperature, pressure per frame), trajectory_type (md/relax/neb) |
| `BandStructure` | `"bands"` | k_distances, eigenvalues (nk x nbands), high_symmetry_points, fermi_energy, spin_polarized flag |
| `DOS` | `"dos"` | energies, total_dos, projected_dos (optional), fermi_energy |
| `SCFConvergence` | `"scf"` | iterations (energy, accuracy, timing per step), converged flag, final_energy |
| `PhononDispersion` | `"phonon"` | q_distances, frequencies (nq x nmodes), high_symmetry_points |

### 6.3 CanonicalPrimitiveBundle

Produced exclusively by `AnalysisObject.to_primitives()`. Tagged with `bundle_kind = "canonical"`.

```
CanonicalPrimitiveBundle
├── bundle_kind: "canonical"          Literal tag (always "canonical")
├── object_type: str                  Matches source AnalysisObject's object_type
│
├── render_meta: RenderMeta           Renderer-facing annotations (see §7)
│   ├── axis_labels: dict[str, str]       e.g., {"x": "Energy", "y": "DOS"}
│   ├── units: dict[str, str]             e.g., {"x": "eV", "y": "states/eV"}
│   ├── series_labels: list[str] | None
│   ├── reference_energy: float | None    (e.g., Fermi energy — arrays NOT shifted)
│   ├── reference_position: float | None
│   └── markers: list[Marker]             Annotation markers (position, label, axis)
│
├── provenance_meta: ProvenanceMeta   Audit/debug metadata (see §7)
│   ├── schema_version: str
│   ├── run_ulid: str | None
│   ├── calc_ulid: str | None
│   ├── step_ulids: list[str]             Ordered step ULIDs (from capability match)
│   ├── gen_steps: list[str]              Ordered GEN step names
│   ├── engine_name: str
│   ├── source_files: list[SourceFileStat]
│   ├── parser_name: str
│   ├── parser_version: str
│   ├── warnings: list[str]
│   └── manifest_snapshot: dict | None
│
├── series: list[Series1D]            1D data series (x, y, labels, units, name)
├── geometry_frames: GeometryFrames | None
└── arrays: dict[str, ndarray]        Named 2D/3D arrays (e.g., eigenvalue grids)
```

Key properties:
- Arrays are in canonical units (eV for energy, Angstrom for length, fs for time).
- Arrays are NOT shifted by reference values, NOT smoothed, NOT cropped.
- `reference_energy` in RenderMeta is an annotation that transforms or renderers may use, but the data itself is unmodified.
- `bundle_kind` is always the literal string `"canonical"`.
- **No timestamps, random IDs, or environment-dependent fields anywhere in the bundle.** The `created_at` field from AnalysisObjectMeta is NOT copied into the bundle or its ProvenanceMeta. This ensures identical raw evidence + identical parser version => identical canonical bundle for CAS dedup.

### 6.4 DerivedPrimitiveBundle

Produced exclusively by `PrimitiveTransform`. Tagged with `bundle_kind = "derived"`. Always ephemeral.

```
DerivedPrimitiveBundle
├── bundle_kind: "derived"            Literal tag (always "derived")
├── object_type: str                  Inherited from input bundle
│
├── render_meta: RenderMeta           May be modified by transforms
├── provenance_meta: ProvenanceMeta   Inherited from input bundle (read-only)
│
├── series: list[Series1D]
├── geometry_frames: GeometryFrames | None
├── arrays: dict[str, ndarray]
│
└── transform_chain: list[TransformRecord]   Ordered log of transforms applied
    └── TransformRecord
        ├── transform_name: str       e.g., "fermi_shift", "gaussian_smooth"
        └── parameters: dict          e.g., {"sigma": 0.05, "unit": "eV"}
```

Key properties:
- Structurally identical to CanonicalPrimitiveBundle except for `bundle_kind` and `transform_chain`.
- `transform_chain` records the full history of transforms applied, enabling reproducibility.
- `TransformRecord` contains NO timestamps. Derived bundles are ephemeral and recomputed on-the-fly; recording when a transform was applied is meaningless.
- Derived bundles MUST NEVER be cached (no LRU, no memoization).
- Derived bundles MUST NEVER be persisted to CAS or any other store.

### 6.5 Post-Run Digest (Separate Category)

Post-run digests are NOT AnalysisObjects. They are lightweight, flat summaries persisted eagerly into SQLite.

```
Post-run digest workflow:
  1. Step completes.
  2. Runner calls registered digest provider: get_parser(engine, "scf_digest").parse(raw_dir).
  3. Digest dataclass returned (VASPDigest, ORCADigest, LAMMPSDigest, etc.).
  4. Digest serialized to JSON and stored in run_steps.digest_json column.
  5. Done. No AnalysisObject constructed. No to_primitives() called.
```

Digests are engine-specific flat dataclasses (not AnalysisObjects) because they are small, mandatory, and require no transforms or rendering pipeline. They feed SQLite timeline queries and summary dashboards directly.

---

## 7. PrimitiveBundle Metadata: RenderMeta vs ProvenanceMeta

### 7.1 Rationale

PrimitiveBundle metadata serves two fundamentally different consumers with different trust boundaries:

1. **Renderers** need axis labels, units, series names, reference values, and markers to produce correct visualizations.
2. **Provenance/audit tools** need engine identity, run/step ULIDs, parser version, source file stats, and warnings to trace lineage and detect staleness.

Mixing these into a single flat namespace creates a hazard: renderers might accidentally branch on engine name or parser version, violating engine-agnosticism. The split into two namespaces makes the contract enforceable by gate tests.

### 7.2 RenderMeta

```
RenderMeta
├── axis_labels: dict[str, str]          e.g., {"x": "Energy", "y": "DOS"}
├── units: dict[str, str]                e.g., {"x": "eV", "y": "states/eV"}
├── series_labels: list[str] | None      Labels for multi-series data
├── reference_energy: float | None       Suggested reference (e.g., E_F); arrays NOT shifted
├── reference_position: float | None     Suggested position reference
├── markers: list[Marker]                Annotation markers (high-sym points, etc.)
└── extra: dict[str, Any]                Reserved for future generic annotations
```

- RenderMeta is the ONLY metadata namespace that visualization code may read.
- RenderMeta MUST NOT contain engine-specific fields, provenance IDs, or source file information.
- RenderMeta MUST NOT contain view parameters (smoothing, crop, camera, color).
- Transforms MAY modify RenderMeta (e.g., FermiShift may update `reference_energy` to 0.0 and relabel the energy axis).

### 7.3 ProvenanceMeta

```
ProvenanceMeta
├── schema_version: str                  Bundle schema version
├── object_type: str                     "trajectory" | "dos" | "bands" | "scf" | ...
├── run_ulid: str | None
├── calc_ulid: str | None
├── step_ulids: list[str]                Ordered step ULIDs covered by this capability match
├── gen_steps: list[str]                 Corresponding ordered GEN step names
├── engine_name: str                     Engine family (informational only)
├── source_files: list[SourceFileStat]   For staleness detection (across all matched steps)
├── parser_name: str
├── parser_version: str
├── warnings: list[str]
└── manifest_snapshot: dict | None       Reserved for future
```

- ProvenanceMeta is for audit, staleness detection, and provenance replay.
- Visualization code MUST NOT read ProvenanceMeta. Gate tests enforce this.
- ProvenanceMeta MUST NOT contain timestamps or environment-dependent values in the canonical bundle (to preserve dedup-friendliness).
- The API layer uses `source_files` from ProvenanceMeta for staleness checks.

### 7.4 Mapping from AnalysisObjectMeta

When `to_primitives()` constructs a CanonicalPrimitiveBundle, it splits the single `AnalysisObjectMeta` into the two namespaces:

| AnalysisObjectMeta field | Destination | Notes |
|--------------------------|-------------|-------|
| `object_type` | ProvenanceMeta | |
| `schema_version` | ProvenanceMeta | |
| `created_at` | **Excluded** | Not copied into bundle; preserves dedup |
| `source_files` | ProvenanceMeta | |
| `run_ulid`, `calc_ulid` | ProvenanceMeta | |
| `step_ulids` | ProvenanceMeta | Ordered list of covered step ULIDs |
| `gen_steps` | ProvenanceMeta | Corresponding ordered GEN step names |
| `engine_name` | ProvenanceMeta | Informational; never for rendering |
| `parser_name`, `parser_version` | ProvenanceMeta | |
| `warnings` | ProvenanceMeta | |
| `manifest_snapshot` | ProvenanceMeta | |
| (axis labels, units, references, markers) | RenderMeta | Computed by `to_primitives()` logic |

---

## 8. Transform Layer Contract

### 8.1 PrimitiveTransform Interface

```
PrimitiveTransform (abstract)
├── name: str                         Unique transform identifier
├── version: str                      Semantic version
├── apply(bundle: PrimitiveBundle) -> DerivedPrimitiveBundle    [REQUIRED]
└── validate(bundle: PrimitiveBundle) -> list[str]              [OPTIONAL: pre-checks]
```

Contract:
- `apply()` MUST accept either `CanonicalPrimitiveBundle` or `DerivedPrimitiveBundle`.
- `apply()` MUST return a `DerivedPrimitiveBundle` (never Canonical).
- `apply()` MUST append a `TransformRecord` to the output's `transform_chain`.
- `apply()` MUST be a pure function: no side effects, no I/O, no raw artifact access, no engine imports.
- `validate()` returns a list of warnings (empty = valid). It does NOT raise.

### 8.2 Transform Composition

Transforms compose by chaining: the output of one transform feeds the input of the next. Derived outputs are always ephemeral and recomputed on-the-fly.

```
canonical = analysis_object.to_primitives()         # CanonicalPrimitiveBundle
shifted  = FermiShift().apply(canonical)             # DerivedPrimitiveBundle (ephemeral)
smoothed = GaussianSmooth(sigma=0.05).apply(shifted) # DerivedPrimitiveBundle (ephemeral)
cropped  = EnergyCrop(emin=-5, emax=5).apply(smoothed) # DerivedPrimitiveBundle (ephemeral)
```

The `transform_chain` on the final bundle records all three transforms in order. No intermediate or final derived bundles are cached or persisted.

### 8.3 Standard Transform Catalog (Non-Exhaustive)

| Transform | Input requirement | Parameters | Effect |
|-----------|-------------------|------------|--------|
| `FermiShift` | Bundle with `reference_energy` in RenderMeta | (none) | Subtracts reference_energy from energy arrays; updates RenderMeta |
| `GaussianSmooth` | 1D series | `sigma` (float), `unit` (str) | Gaussian convolution on y-values |
| `EnergyCrop` | 1D series with energy axis | `emin`, `emax` | Trims data to energy window |
| `KPathResample` | Band-structure arrays | `n_points` | Resamples along k-path |
| `TrajectorySlice` | GeometryFrames | `start`, `stop`, `step` | Selects frame subset |
| `Unwrap` | GeometryFrames with PBC | (none) | Unwraps atomic positions across PBC |
| `ProjectDOS` | DOS arrays | `atom_indices`, `orbital` | Extracts projected DOS subset |

### 8.4 Transform Prohibitions

- Transforms MUST NOT read raw artifact files.
- Transforms MUST NOT import from `drivers/` or any engine-specific module.
- Transforms MUST NOT write to disk, databases, or CAS.
- Transforms MUST NOT modify the input bundle in place; they MUST produce a new bundle.
- Transforms MUST NOT produce CanonicalPrimitiveBundles.

---

## 9. Visualization Contract

### 9.1 Rendering Interface

All renderers (matplotlib, Electron/web, Jupyter widget, file export) MUST conform to:

```
render(bundle: PrimitiveBundle, style: RenderStyle) -> RenderOutput
```

Where:
- `bundle` is a `CanonicalPrimitiveBundle` or `DerivedPrimitiveBundle`.
- `style` is a pure presentation object (colors, line widths, fonts, axis limits for display, figure size). Style is NOT data; it does not alter the numeric content.
- `RenderOutput` is target-specific (matplotlib Figure, HTML fragment, PNG bytes, etc.).

### 9.2 Metadata Access Rules

- Viz MUST render "as-is" from numeric arrays (series, geometry_frames, arrays) + `render_meta` only.
- Viz MAY read `render_meta.axis_labels`, `render_meta.units`, `render_meta.series_labels`, `render_meta.markers`, `render_meta.reference_energy`, etc.
- Viz MUST NOT read `provenance_meta` for any rendering decision. ProvenanceMeta fields (engine_name, parser_name, run_ulid, step_ulids, etc.) MUST NOT influence what is drawn or how it is drawn.
- Viz MAY pass `provenance_meta` through to a separate "info panel" or tooltip, but MUST NOT use it to select rendering paths, colors, layouts, or data transformations.

### 9.3 Visualization Prohibitions

| Forbidden action | Rationale |
|------------------|-----------|
| Read raw artifacts | Viz layer has no filesystem access to calc/raw/ |
| Call engine parsers | Parsing is kernel's responsibility |
| Branch on `provenance_meta.engine_name` or any ProvenanceMeta field | Bundles are engine-agnostic; rendering must be universal |
| Perform data transforms (even trivial ones like energy shifting) | Use PrimitiveTransform before rendering |
| Access SQLite or CAS | Persistence is API layer's responsibility |
| Import from `drivers/` | Engine isolation |

### 9.4 Schema Universality

Both Electron UI and Python renderers consume the identical `PrimitiveBundle` schema. The API serializes bundles to JSON for transport to the Electron frontend. Python renderers consume the in-memory dataclass directly. No schema divergence is permitted.

---

## 10. Caching and Persistence Policy

### 10.1 Two Categories of Analysis Output

| Category | Examples | Timing | Persistence |
|----------|----------|--------|-------------|
| **(A) Post-run digest** | Energy, Fermi, convergence, forces, timing | Eager: immediately after each step completes (Phase 1) | SQLite `run_steps.digest_json` — mandatory |
| **(B) AnalysisObject → Primitives** | Bands, DOS, trajectory, phonon dispersion | Eager at end of run via capability matching (Phase 2); on-demand for subsequent requests | Canonical-only in-memory memo; CAS Tier-0.8 snapshot (eager) |

### 10.2 Post-Run Digest Persistence (Category A)

- Runner calls the registered `scf_digest` provider after each step.
- Digest result is serialized to JSON and written to the `run_steps.digest_json` column.
- This is mandatory for every engine that has a registered digest provider.
- Digest providers return engine-specific dataclasses (not AnalysisObjects) with `to_dict()`.
- Digests are small (< 10 KB typically); no CAS involvement.

### 10.3 Canonical-Only Memoization (Category B — In-Memory)

The API layer MAY maintain an in-memory memoization cache for AnalysisObjects and CanonicalPrimitiveBundles. Rules:

- **Memo key = `canonical_sha`** (content hash of the serialized canonical bundle), aligned with CAS identity. Compute `canonical_sha` once at production time and reuse it for both CAS persistence and memo cache lookup.
- **Lookup index:** The API layer maintains an in-memory index `(run_ulid, object_type) → (canonical_sha, source_file_stats)` to resolve requests to memo entries.
- **Staleness:** If any source file's `(size_bytes, mtime)` changes, the index entry is invalidated and the bundle is re-derived from raw evidence. Staleness never falls back to CAS.
- Scope: Per-process only. No cross-process sharing. Lost on process exit.
- Canonical bundles and their source AnalysisObjects are the ONLY analysis results eligible for memoization.
- In-memory memoization of the raw→canonical path is a runtime optimization, not a persisted truth. It may be dropped at any time. It does not violate present-tense SSOT because live analysis always derives from present raw evidence when the cache is cold or stale.
- **DerivedPrimitiveBundles MUST NOT be memoized.** No LRU, no single-slot, no dictionary, no decorator, no caching of any kind for derived bundles or transform outputs.

### 10.4 CAS Tier-0.8 Snapshots (Category B — Persistent)

Canonical bundles are eagerly persisted to CAS at run completion (Phase 2 in §4). CAS is content-addressed; dedup is by content hash.

- **CAS blob identity:** `canonical_sha` = content hash (e.g., sha256) of the serialized canonical bundle. CAS stores and deduplicates by this hash. If two runs produce byte-identical canonical bundles, only one CAS blob exists.
- **SQLite linkage:** One row per `(run_ulid, object_type)` linking to `canonical_sha`. If a new canonical bundle is computed for the same `(run_ulid, object_type)` (e.g., parser upgrade, re-run), the SQLite row is updated to point to the new hash. Old CAS blobs may be garbage-collected by standard CAS retention policy.
- **Thumbnail:** Same content-addressed storage. SQLite links `(run_ulid, object_type) → thumbnail_sha`.
- **No owner_step_ulid:** Canonical snapshots do NOT have a single "owner step". ProvenanceMeta's `step_ulids` and `gen_steps` record the full ordered list of covered steps.
- **DerivedPrimitiveBundle MUST NEVER be written to CAS.**
- **Reading:** The operational UI path MUST NOT read from CAS as a substitute for live derivation. CAS snapshots are for provenance replay and snapshot comparison features ONLY.
- **User pins:** Additional screenshots or view exports may be persisted as separate CAS entries via explicit user "pin" action (append, not auto-managed). Pin records carry a `run_ulid_source` field (`exact` | `inferred` | `unknown`) indicating provenance confidence (see Inv-A11).

### 10.5 What Is NOT Persisted or Cached

| Item | In-memory memo | CAS | SQLite | Filesystem |
|------|----------------|-----|--------|------------|
| Post-run digest | N/A (read from SQLite) | No | Yes (mandatory) | No |
| AnalysisObject | Yes (optional) | No | No | No |
| CanonicalPrimitiveBundle | Yes (optional) | Yes (Tier-0.8, eager) | No | No |
| DerivedPrimitiveBundle | **No** | **No** | **No** | **No** |
| Transform chain state | **No** | **No** | **No** | **No** |

---

## 11. Layering Responsibilities

### 11.1 Kernel Layer

Provides pure capabilities. No orchestration, no persistence decisions.

| Responsibility | Location |
|---------------|----------|
| AnalysisObject type definitions | `core/analysis/` |
| AnalysisObjectMeta, SourceFileStat | `core/analysis/base.py` |
| Visual primitives (Series1D, GeometryFrame, etc.) | `core/analysis/primitives.py` |
| CanonicalPrimitiveBundle, DerivedPrimitiveBundle | `core/analysis/bundles.py` |
| RenderMeta, ProvenanceMeta | `core/analysis/bundles.py` |
| PrimitiveTransform base + standard transforms | `core/analysis/transforms/` |
| Engine analysis providers (raw → AnalysisObject) | `drivers/<engine>/parsers/` |
| Digest providers (raw → Digest dataclass) | `drivers/<engine>/parsers/` |
| Analysis provider registry | `parsers/registry.py` |
| Engine analysis capability declarations | `drivers/<engine>/driver.py` (`ANALYSIS_CAPABILITIES`) |
| Pure rendering functions (bundle → figure) | `core/analysis/renderers/` |

Kernel MUST NOT:
- Decide when to parse or cache.
- Write to SQLite or CAS.
- Hold memoization state.

### 11.2 API / QVService Layer

Owns orchestration, caching, and persistence.

| Responsibility | Notes |
|---------------|-------|
| Receive analysis requests from frontend | Route by `(calc_ulid, run_ulid, object_type)` |
| Execute post-run pipeline (§4) | Phases 1-4 after run completion |
| Perform run-level capability matching | Match engine capabilities against run's GEN step list (§5.3) |
| Call engine analysis provider → AnalysisObject | Via provider registry lookup |
| Call `to_primitives()` | Produces CanonicalPrimitiveBundle |
| Apply requested transforms | Calls PrimitiveTransform chain; produces DerivedPrimitiveBundle (ephemeral, never cached) |
| Canonical-only in-memory memoization | Cache canonical bundles keyed by `canonical_sha` (content hash); lookup index `(run_ulid, object_type) → (canonical_sha, source_file_stats)` with staleness detection |
| Staleness check | Compare source_files stats against current raw artifact stats |
| Persist post-run digests to SQLite | Mandatory, eager, Phase 1 |
| Persist canonical bundles to CAS (Tier-0.8) | Eager, Phase 2; CAS blob by `canonical_sha`; SQLite links `(run_ulid, object_type) → canonical_sha` |
| Persist thumbnails to CAS (Tier-0.8) | Eager, Phase 3; CAS blob by `thumbnail_sha`; SQLite links `(run_ulid, object_type) → thumbnail_sha` |
| Enforce derived non-persistence and non-caching | MUST NOT write or cache derived bundles anywhere |
| Serialize bundles for frontend transport | JSON serialization of PrimitiveBundle |

### 11.3 Frontend Layer

Pure consumer. No analysis logic.

| Allowed | Forbidden |
|---------|-----------|
| Receive PrimitiveBundle (JSON) from API | Import kernel modules |
| Render bundle using numeric arrays + RenderMeta | Branch on ProvenanceMeta fields |
| Send transform requests to API (e.g., "apply FermiShift") | Perform data transforms locally |
| Send style preferences (colors, zoom) | Read raw artifacts |
| Request re-render with different transforms | Access SQLite or CAS |
| Display ProvenanceMeta in info panels/tooltips | Use ProvenanceMeta for rendering decisions |
| Display digest from Surface B | Parse raw files |
| Open raw files via Surface A | Call analysis providers |
| Show analysis tiles for a clicked step by checking membership in `step_ulids` | Assume single-step ownership |

### 11.4 Request Flow (On-Demand, Post-Initial-Run)

```
Frontend                        API/QVService                     Kernel
   │                                │                                │
   │  GET /analysis                 │                                │
   │  {run_ulid, object_type,       │                                │
   │   transforms: [...]}           │                                │
   ├───────────────────────────────>│                                │
   │                                │                                │
   │                                │  1. Check canonical memo cache │
   │                                │     lookup: (run_ulid,         │
   │                                │       object_type) → sha       │
   │                                │     + staleness check on       │
   │                                │       source_file_stats        │
   │                                │     (hit? stale? re-derive)    │
   │                                │                                │
   │                                │  2. If miss/stale:             │
   │                                │     Re-match capability,       │
   │                                │     resolve evidence dirs      │
   │                                │     provider = get_parser(     │
   │                                │       engine, object_type)     │
   │                                ├───────────────────────────────>│
   │                                │     analysis_obj = provider    │
   │                                │       .parse(...)              │
   │                                │<───────────────────────────────┤
   │                                │                                │
   │                                │  3. canonical = analysis_obj   │
   │                                │       .to_primitives()         │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │                                │  4. Update memo cache + CAS   │
   │                                │                                │
   │                                │  5. Apply transforms           │
   │                                │     (always on-the-fly;        │
   │                                │      derived never cached)     │
   │                                ├───────────────────────────────>│
   │                                │     derived = transform        │
   │                                │       .apply(canonical)        │
   │                                │<───────────────────────────────┤
   │                                │                                │
   │  PrimitiveBundle (JSON)        │                                │
   │  {render_meta, provenance_meta,│                                │
   │   series, arrays, ...}         │                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │  6. Render from arrays +       │                                │
   │     render_meta ONLY           │                                │
   │     (ignore provenance_meta)   │                                │
```

---

## 12. Acceptance Criteria and Future Gate Tests

### 12.1 Gate Test Inventory

| Invariant | Gate test file | Test description |
|-----------|---------------|------------------|
| **Inv-A2** | `test_analysis_object_meta_required.py` | Every AnalysisObject subclass has a `meta: AnalysisObjectMeta` field |
| **Inv-A2** | `test_analysis_object_no_view_params.py` | No AnalysisObject subclass defines fields matching view-parameter patterns (smooth, crop, camera, zoom, color, slice, window) |
| **Inv-A4** | `test_canonical_bundle_source.py` | CanonicalPrimitiveBundle can only be instantiated via to_primitives(); direct construction outside that path raises or is gated |
| **Inv-A4** | `test_to_primitives_is_parameterless.py` | Inspect all to_primitives() signatures: must accept only `self`, no other arguments |
| **Inv-A4** | `test_canonical_bundle_deterministic.py` | CanonicalPrimitiveBundle contains no `created_at`, no random IDs, no timestamps, no environment-dependent fields. Two calls to `to_primitives()` on the same AnalysisObject produce byte-equal serialization. |
| **Inv-A5** | `test_derived_bundle_source.py` | DerivedPrimitiveBundle can only be instantiated via PrimitiveTransform.apply() |
| **Inv-A5** | `test_derived_never_cached.py` | AST scan: no memoization decorator, LRU cache, or dictionary caching applied to any code path that produces or stores DerivedPrimitiveBundles |
| **Inv-A6** | `test_bundle_no_view_params.py` | Neither bundle type defines fields matching view-parameter patterns |
| **Inv-A6** | `test_render_meta_no_provenance.py` | RenderMeta type has no fields for engine_name, run_ulid, step_ulids, parser_name, source_files, or warnings |
| **Inv-A7** | `test_transform_no_raw_access.py` | AST scan: no transform module imports `pathlib.Path`, `open()`, or `drivers/` modules |
| **Inv-A7** | `test_transform_no_engine_imports.py` | AST scan: no transform module imports from `quantumvitas.drivers` |
| **Inv-A8** | `test_viz_no_raw_access.py` | AST scan: no renderer/viz module reads files or imports engine parsers |
| **Inv-A8** | `test_viz_no_engine_logic.py` | AST scan: no renderer/viz module imports from `quantumvitas.drivers` |
| **Inv-A8** | `test_viz_no_transforms.py` | AST scan: no renderer/viz module imports from `core/analysis/transforms/` |
| **Inv-A8** | `test_viz_no_provenance_meta_access.py` | AST scan: no renderer/viz module accesses `.provenance_meta` or any ProvenanceMeta field for rendering logic |
| **Inv-A9** | `test_no_lazy_payloads.py` | AST scan: no `LazyArray`, `LateList`, or deferred-proxy classes in `core/analysis/` |
| **Inv-A10** | `test_no_analysis_disk_cache.py` | No analysis module writes to disk (except CAS via API layer) |
| **Inv-A10** | `test_derived_never_memoized.py` | API layer memo cache keys and values never reference DerivedPrimitiveBundle |
| **Inv-A11** | `test_derived_never_persisted.py` | API layer CAS write paths reject DerivedPrimitiveBundle |
| **Inv-A11** | `test_operational_path_no_cas_read.py` | The default analysis request path does not read from CAS; only explicit replay/snapshot endpoints do |
| **Inv-A11** | `test_cas_is_content_addressed.py` | CAS blobs are keyed by content hash (`canonical_sha`), not by `(run_ulid, …)`. SQLite linkage rows reference `canonical_sha`. No `owner_step_ulid` field exists. |
| **Inv-A12** | `test_frontend_no_kernel_import.py` | Frontend code does not import from kernel analysis modules |
| **Inv-A13** | `test_no_engine_branching_in_orchestrator.py` | AST scan: analysis orchestrator, bundle types, transforms, and renderers contain no `if engine ==`, `engine_name ==`, or similar engine-conditional logic |
| **Inv-A13** | `test_unknown_engine_analysis_raises.py` | Requesting analysis for an unregistered (engine, object_type) pair raises a hard error, not silent skip |
| **Inv-A14** | `test_no_tmp_corpus_in_runtime.py` | No import path or runtime code references `.tmp/` |
| **§5.2** | `test_analysis_capability_declaration.py` | Every engine with registered analysis providers has a matching `ANALYSIS_CAPABILITIES` declaration with `gen_step_sequence` (list, length ≥ 1) |
| **§5.3** | `test_capability_match_deterministic.py` | Given the same run GEN step list and engine capabilities, matching always produces the same set of CapabilityMatches (same step_ulids, same order) |
| **§5.3** | `test_no_redundant_canonical.py` | A run with GEN steps `[bandspw, bands]` and a capability `["bandspw", "bands"]` produces exactly ONE canonical bands bundle, not two |

### 12.2 Acceptance Criteria (Behavioral)

1. **Roundtrip determinism**: For any engine's test corpus, `provider.parse(...).to_primitives()` called twice yields byte-equal serialized canonical bundles (no timestamps or nondeterministic fields).

2. **Transform purity**: For any transform T and any bundle B, `T.apply(B)` returns the same result regardless of call order with other unrelated operations. No hidden state.

3. **Staleness detection**: If a raw artifact is modified (touched with new mtime), the API layer's staleness check detects it and re-derives the AnalysisObject instead of returning a stale memoized result.

4. **Bundle schema universality**: The JSON schema emitted by the API for PrimitiveBundles is consumed without modification by both Electron UI and Jupyter renderers.

5. **Graceful absence**: If raw artifacts are missing (deleted or never produced), the analysis request returns a clear error. It does NOT fall back to CAS, does NOT return partial data, and does NOT crash the API.

6. **Digest independence**: Post-run digest persistence (SQLite) operates independently of the AnalysisObject pipeline. Digest parsing failure does NOT block run completion (warning logged; run status still set).

7. **CAS deletion safety**: Deleting `.provenance/.cas/` does NOT affect the operational analysis path. Analysis is re-derived from raw evidence. Only provenance replay features become unavailable.

8. **Derived ephemerality**: No derived bundle survives beyond the request that created it. Re-requesting the same analysis with the same transforms recomputes from the canonical bundle.

9. **RenderMeta isolation**: A renderer that receives a PrimitiveBundle with `provenance_meta.engine_name = "vasp"` and one with `provenance_meta.engine_name = "orca"` produces visually identical output for identical numeric arrays and render_meta. Engine identity does not leak into rendering.

10. **Run-level canonical identity**: After a successful run, each matched capability produces exactly one canonical bundle stored in CAS by `canonical_sha` (content hash) and linked from SQLite via `(run_ulid, object_type) → canonical_sha`. Multi-step capabilities produce a single canonical bundle whose `step_ulids` covers all participating steps.

11. **No redundant generation**: A run with GEN steps `[scf, bandspw, bands]` and a bands capability `["bandspw", "bands"]` MUST NOT produce two separate bands analyses for bandspw and bands. Exactly one bands canonical bundle is produced.

12. **Surface isolation**: Raw text viewer (Surface A) shares no code path with digest display (Surface B) or analysis visualization (Surface C). Each can function independently.

13. **Membership-based UI association**: Clicking any step in the GUI shows analysis tiles by checking `step_ulid ∈ canonical.provenance_meta.step_ulids`. No "owner step" field or "belongs to last step" logic exists.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.4 | 2026-02-08 | Run-level capability matching, CAS identity clarification |
| 1.5 | 2026-02-12 | Merged "Big Picture & Motivation" from ANALYSIS_OBJECTS_FRAMEWORK.md (v1.1) as §0; Framework document retired |

---

*End of Specification v1.5*
