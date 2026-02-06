# AnalysisObject → Primitive Pipeline Specification

**Status:** BINDING v1.1
**Date:** 2026-02-06
**Scope:** Data model, transform contract, persistence policy, and layering for analysis output rendering.

---

## Table of Contents

1. [Terminology](#1-terminology)
2. [Invariants](#2-invariants)
3. [Data Model](#3-data-model)
4. [PrimitiveBundle Metadata: RenderMeta vs ProvenanceMeta](#4-primitivebundle-metadata-rendermeta-vs-provenancemeta)
5. [Transform Layer Contract](#5-transform-layer-contract)
6. [Visualization Contract](#6-visualization-contract)
7. [Caching and Persistence Policy](#7-caching-and-persistence-policy)
8. [Layering Responsibilities](#8-layering-responsibilities)
9. [Acceptance Criteria and Future Gate Tests](#9-acceptance-criteria-and-future-gate-tests)

---

## 1. Terminology

| Term | Definition |
|------|-----------|
| **Raw artifact** | Engine-native output file residing in `calc/raw/` (e.g., `vasprun.xml`, `scf.out`, `DOSCAR`). Raw artifacts are engine-native *evidence* used for analysis derivation. They are NOT SSOT. |
| **SSOT** | Present-tense YAML resources only: `calculation.yaml`, `step.yaml`, structure resources. Raw artifacts, analysis objects, and primitive bundles are never SSOT. |
| **Post-run digest** | Small, flat summary of a completed step (energy, convergence, Fermi level, forces, timing). Mandatory. Persisted eagerly into the SQLite `run_steps` table immediately after each step completes. Examples: `VASPDigest`, `ORCADigest`, `LAMMPSDigest`. |
| **AnalysisObject** | Engine-agnostic, in-memory domain data structure derived from raw evidence by an engine parser. Carries full numeric payload (arrays, frames, spectra) plus a single `AnalysisObjectMeta` container. Computed on demand, never persisted to disk as a primary store. |
| **AnalysisObjectMeta** | The mandatory metadata container on every AnalysisObject. Contains provenance IDs, source file stats, parser identity, and warnings. Defined once; every AnalysisObject subclass inherits the same schema. |
| **to_primitives()** | The required, parameter-free method on every AnalysisObject that produces a `CanonicalPrimitiveBundle`. Deterministic and pure. The ONLY producer of CanonicalPrimitiveBundle. |
| **CanonicalPrimitiveBundle** | The deterministic, dedup-friendly reshaping of an AnalysisObject into renderer-consumable arrays and annotations. May ONLY be produced by `AnalysisObject.to_primitives()`. Contains no timestamps, random IDs, or environment-dependent fields. |
| **DerivedPrimitiveBundle** | A primitive bundle produced by applying a `PrimitiveTransform` to a canonical or derived bundle. May ONLY be produced by `PrimitiveTransform`. Ephemeral: MUST NOT be cached or persisted. |
| **PrimitiveTransform** | A pure math operation `(Canonical|Derived) -> Derived`. Examples: smoothing, cropping, resampling, Fermi-shift, 3D-to-2D slice. Transforms MUST NOT read raw artifacts or contain engine logic. |
| **PrimitiveBundle** | Generic term covering both `CanonicalPrimitiveBundle` and `DerivedPrimitiveBundle`. Visualization accepts either. |
| **RenderMeta** | The renderer-facing metadata namespace inside a PrimitiveBundle: axis labels, units, series labels, markers, suggested reference/offset values. Viz MAY use RenderMeta for rendering decisions. |
| **ProvenanceMeta** | The provenance/audit metadata namespace inside a PrimitiveBundle: engine name, run/step/calc ULIDs, source files, parser identity, warnings, timestamps. Viz MUST NOT use ProvenanceMeta for rendering decisions. |
| **View parameter** | Any rendering/display control: smoothing window, crop range, slice plane, camera angle, color map. View parameters live exclusively in the frontend or transform call site. They MUST NOT appear inside AnalysisObjects or PrimitiveBundles. |
| **Engine parser** | Code in `drivers/<engine>/parsers/` that reads raw evidence and returns an AnalysisObject. Parsers are the only code permitted to read raw artifacts for analysis purposes. |

---

## 2. Invariants

These invariants are BINDING. Each is labeled for cross-reference and future gate enforcement.

### Inv-A1: Raw Artifacts Are Evidence, Not SSOT

> Raw artifacts are engine-native evidence used for analysis derivation. They are NOT SSOT. SSOT in this project refers exclusively to `calculation.yaml`, `step.yaml`, and structure resources.

- Engine parsers MUST read raw evidence to produce AnalysisObjects.
- No code outside `drivers/<engine>/parsers/` may read raw artifacts for analysis derivation.
- Deleting raw artifacts makes analysis unavailable but MUST NOT break SSOT or project runnability.

### Inv-A2: AnalysisObjects Are Universal and Engine-Agnostic

> AnalysisObjects are the sole in-memory domain representation of analysis results. They are engine-agnostic in type and interface.

- Every AnalysisObject MUST carry exactly one `AnalysisObjectMeta` field.
- AnalysisObject subclasses (Trajectory, BandStructure, DOS, etc.) are defined in `core/analysis/`, not in engine drivers.
- Engine parsers return instances of these shared types; they MUST NOT define engine-specific AnalysisObject subclasses.
- AnalysisObjects MUST NOT contain view parameters (smoothing, cropping, camera, slice, color).

### Inv-A3: AnalysisObjectMeta Is the Single Metadata Schema

> Every AnalysisObject carries a single `AnalysisObjectMeta` instance. No alternative metadata containers.

Required fields in `AnalysisObjectMeta`:

| Field | Type | Purpose |
|-------|------|---------|
| `schema_version` | str | Schema version of this meta format |
| `object_type` | str | Discriminator: `"trajectory"`, `"dos"`, `"bands"`, `"scf"`, etc. |
| `created_at` | str (ISO 8601) | Timestamp of object construction (runtime only; excluded from CAS serialization) |
| `source_files` | list[SourceFileStat] | Paths + size + mtime of raw files consumed |
| `run_ulid` | str or None | Provenance: which run produced the raw evidence |
| `calc_ulid` | str or None | Provenance: parent calculation |
| `step_ulid` | str or None | Provenance: parent step |
| `parser_name` | str | Registered parser identifier |
| `parser_version` | str | Parser version for reproducibility |
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
- `run_ulid`, `calc_ulid`, `step_ulid`
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
- AnalysisObjects and canonical primitives are computed on demand: when the UI/API requests analysis for a particular step/run/kind.
- There MUST NOT be `LazyArray`, `LateList`, deferred-load proxy objects, or similar lazy payload wrappers inside AnalysisObjects. Once constructed, an AnalysisObject holds all its data in memory.
- All kernel calls in the analysis path are synchronous.

### Inv-A10: Canonical-Only Memoization; Derived Never Cached

> Only CanonicalPrimitiveBundles (and their source AnalysisObjects) may be memoized in memory. Derived bundles and transform outputs are ALWAYS computed on-the-fly.

- In-memory memoization of AnalysisObjects and CanonicalPrimitiveBundles is allowed as a runtime enhancement in long-lived processes (daemon, Jupyter kernel). CLI processes typically do not cache.
- `DerivedPrimitiveBundle` MUST NOT be memoized or cached in any form: no LRU cache, no single-slot cache, no dictionary lookup, no memoization decorator.
- `PrimitiveTransform` outputs are always recomputed by applying the transform chain to the canonical bundle.
- There MUST NOT be a persistent (on-disk) cache for any analysis results (neither AnalysisObjects nor any PrimitiveBundles).
- No cross-process cache pointers or shared-memory analysis stores.
- Every process that needs analysis MUST be capable of re-deriving it from raw evidence.

### Inv-A11: CAS Persistence Is Explicit and Scoped (Tier 0.8)

> CAS auto-persistence for analysis is tightly scoped. Derived bundles are never persisted.

- The operational UI path MUST derive analysis from raw evidence on demand. It MUST NOT implicitly read CanonicalPrimitiveBundles from CAS as a substitute for live derivation.
- CAS is used ONLY for explicit provenance replay and snapshot viewing features.
- Auto-persistence into CAS is allowed ONLY for:
  - (a) `CanonicalPrimitiveBundle`: one per `(run_ulid, step_ulid, object_type)` triple; overwrite-on-recompute (keep only latest).
  - (b) A "last rendered thumbnail" per `(run_ulid, step_ulid, object_type)` triple; overwrite-on-rerender (keep only latest).
- `DerivedPrimitiveBundle` MUST NEVER be persisted to CAS or any other store.
- User "pin" actions may persist additional screenshots or view snapshots as separate CAS entries (append, not auto-managed).

### Inv-A12: Layering — Kernel vs API vs Frontend

> Kernel provides pure capabilities. API owns orchestration and persistence. Frontend interacts only with API.

- **Kernel** provides: engine parsers, AnalysisObject types, `to_primitives()`, PrimitiveTransform implementations, and pure rendering functions.
- **API/QVService** owns: request routing, canonical-only in-memory memoization, ALL writes to SQLite and CAS (including overwrite/dedup policies for Tier-0.8 snapshots).
- **Frontend** (Electron or Jupyter) interacts ONLY with the API layer. It MUST NOT import kernel modules directly, call parsers, or access SQLite/CAS.

---

## 3. Data Model

### 3.1 AnalysisObjectMeta

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
├── step_ulid: str | None
├── engine_name: str                  Engine family (informational; MUST NOT drive rendering)
├── parser_name: str                  Registered parser ID
├── parser_version: str
├── warnings: list[str]               Parser warnings
└── manifest_snapshot: dict | None    Reserved for future (stale/debug)
```

Note: `created_at` is a runtime convenience field. It MUST be excluded when serializing a CanonicalPrimitiveBundle for CAS persistence, to preserve dedup-friendliness (Inv-A4).

### 3.2 AnalysisObject (Abstract Base)

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

### 3.3 CanonicalPrimitiveBundle

Produced exclusively by `AnalysisObject.to_primitives()`. Tagged with `bundle_kind = "canonical"`.

```
CanonicalPrimitiveBundle
├── bundle_kind: "canonical"          Literal tag (always "canonical")
├── object_type: str                  Matches source AnalysisObject's object_type
│
├── render_meta: RenderMeta           Renderer-facing annotations (see §4)
│   ├── axis_labels: dict[str, str]       e.g., {"x": "Energy", "y": "DOS"}
│   ├── units: dict[str, str]             e.g., {"x": "eV", "y": "states/eV"}
│   ├── series_labels: list[str] | None
│   ├── reference_energy: float | None    (e.g., Fermi energy — arrays NOT shifted)
│   ├── reference_position: float | None
│   └── markers: list[Marker]             Annotation markers (position, label, axis)
│
├── provenance_meta: ProvenanceMeta   Audit/debug metadata (see §4)
│   ├── schema_version: str
│   ├── run_ulid: str | None
│   ├── calc_ulid: str | None
│   ├── step_ulid: str | None
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

### 3.4 DerivedPrimitiveBundle

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

### 3.5 Post-Run Digest (Separate Category)

Post-run digests are NOT AnalysisObjects. They are lightweight, flat summaries persisted eagerly into SQLite.

```
Post-run digest workflow:
  1. Step completes.
  2. Runner calls registered digest parser: get_parser(engine, "scf_digest").parse(raw_dir).
  3. Digest dataclass returned (VASPDigest, ORCADigest, LAMMPSDigest, etc.).
  4. Digest serialized to JSON and stored in run_steps.digest_json column.
  5. Done. No AnalysisObject constructed. No to_primitives() called.
```

Digests are engine-specific flat dataclasses (not AnalysisObjects) because they are small, mandatory, and require no transforms or rendering pipeline. They feed SQLite timeline queries and summary dashboards directly.

---

## 4. PrimitiveBundle Metadata: RenderMeta vs ProvenanceMeta

### 4.1 Rationale

PrimitiveBundle metadata serves two fundamentally different consumers with different trust boundaries:

1. **Renderers** need axis labels, units, series names, reference values, and markers to produce correct visualizations.
2. **Provenance/audit tools** need engine identity, run/step ULIDs, parser version, source file stats, and warnings to trace lineage and detect staleness.

Mixing these into a single flat namespace creates a hazard: renderers might accidentally branch on engine name or parser version, violating engine-agnosticism. The split into two namespaces makes the contract enforceable by gate tests.

### 4.2 RenderMeta

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

### 4.3 ProvenanceMeta

```
ProvenanceMeta
├── schema_version: str                  Bundle schema version
├── object_type: str                     "trajectory" | "dos" | "bands" | "scf" | ...
├── run_ulid: str | None
├── calc_ulid: str | None
├── step_ulid: str | None
├── engine_name: str                     Engine family (informational only)
├── source_files: list[SourceFileStat]   For staleness detection
├── parser_name: str
├── parser_version: str
├── warnings: list[str]
└── manifest_snapshot: dict | None       Reserved for future
```

- ProvenanceMeta is for audit, staleness detection, and provenance replay.
- Visualization code MUST NOT read ProvenanceMeta. Gate tests enforce this.
- ProvenanceMeta MUST NOT contain timestamps or environment-dependent values in the canonical bundle (to preserve dedup-friendliness).
- The API layer uses `source_files` from ProvenanceMeta for staleness checks.

### 4.4 Mapping from AnalysisObjectMeta

When `to_primitives()` constructs a CanonicalPrimitiveBundle, it splits the single `AnalysisObjectMeta` into the two namespaces:

| AnalysisObjectMeta field | Destination | Notes |
|--------------------------|-------------|-------|
| `object_type` | ProvenanceMeta | |
| `schema_version` | ProvenanceMeta | |
| `created_at` | **Excluded** | Not copied into bundle; preserves dedup |
| `source_files` | ProvenanceMeta | |
| `run_ulid`, `calc_ulid`, `step_ulid` | ProvenanceMeta | |
| `engine_name` | ProvenanceMeta | Informational; never for rendering |
| `parser_name`, `parser_version` | ProvenanceMeta | |
| `warnings` | ProvenanceMeta | |
| `manifest_snapshot` | ProvenanceMeta | |
| (axis labels, units, references, markers) | RenderMeta | Computed by `to_primitives()` logic |

---

## 5. Transform Layer Contract

### 5.1 PrimitiveTransform Interface

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

### 5.2 Transform Composition

Transforms compose by chaining: the output of one transform feeds the input of the next. Derived outputs are always ephemeral and recomputed on-the-fly.

```
canonical = analysis_object.to_primitives()         # CanonicalPrimitiveBundle
shifted  = FermiShift().apply(canonical)             # DerivedPrimitiveBundle (ephemeral)
smoothed = GaussianSmooth(sigma=0.05).apply(shifted) # DerivedPrimitiveBundle (ephemeral)
cropped  = EnergyCrop(emin=-5, emax=5).apply(smoothed) # DerivedPrimitiveBundle (ephemeral)
```

The `transform_chain` on the final bundle records all three transforms in order. No intermediate or final derived bundles are cached or persisted.

### 5.3 Standard Transform Catalog (Non-Exhaustive)

| Transform | Input requirement | Parameters | Effect |
|-----------|-------------------|------------|--------|
| `FermiShift` | Bundle with `reference_energy` in RenderMeta | (none) | Subtracts reference_energy from energy arrays; updates RenderMeta |
| `GaussianSmooth` | 1D series | `sigma` (float), `unit` (str) | Gaussian convolution on y-values |
| `EnergyCrop` | 1D series with energy axis | `emin`, `emax` | Trims data to energy window |
| `KPathResample` | Band-structure arrays | `n_points` | Resamples along k-path |
| `TrajectorySlice` | GeometryFrames | `start`, `stop`, `step` | Selects frame subset |
| `Unwrap` | GeometryFrames with PBC | (none) | Unwraps atomic positions across PBC |
| `ProjectDOS` | DOS arrays | `atom_indices`, `orbital` | Extracts projected DOS subset |

### 5.4 Transform Prohibitions

- Transforms MUST NOT read raw artifact files.
- Transforms MUST NOT import from `drivers/` or any engine-specific module.
- Transforms MUST NOT write to disk, databases, or CAS.
- Transforms MUST NOT modify the input bundle in place; they MUST produce a new bundle.
- Transforms MUST NOT produce CanonicalPrimitiveBundles.

---

## 6. Visualization Contract

### 6.1 Rendering Interface

All renderers (matplotlib, Electron/web, Jupyter widget, file export) MUST conform to:

```
render(bundle: PrimitiveBundle, style: RenderStyle) -> RenderOutput
```

Where:
- `bundle` is a `CanonicalPrimitiveBundle` or `DerivedPrimitiveBundle`.
- `style` is a pure presentation object (colors, line widths, fonts, axis limits for display, figure size). Style is NOT data; it does not alter the numeric content.
- `RenderOutput` is target-specific (matplotlib Figure, HTML fragment, PNG bytes, etc.).

### 6.2 Metadata Access Rules

- Viz MUST render "as-is" from numeric arrays (series, geometry_frames, arrays) + `render_meta` only.
- Viz MAY read `render_meta.axis_labels`, `render_meta.units`, `render_meta.series_labels`, `render_meta.markers`, `render_meta.reference_energy`, etc.
- Viz MUST NOT read `provenance_meta` for any rendering decision. ProvenanceMeta fields (engine_name, parser_name, run_ulid, etc.) MUST NOT influence what is drawn or how it is drawn.
- Viz MAY pass `provenance_meta` through to a separate "info panel" or tooltip, but MUST NOT use it to select rendering paths, colors, layouts, or data transformations.

### 6.3 Visualization Prohibitions

| Forbidden action | Rationale |
|------------------|-----------|
| Read raw artifacts | Viz layer has no filesystem access to calc/raw/ |
| Call engine parsers | Parsing is kernel's responsibility |
| Branch on `provenance_meta.engine_name` or any ProvenanceMeta field | Bundles are engine-agnostic; rendering must be universal |
| Perform data transforms (even trivial ones like energy shifting) | Use PrimitiveTransform before rendering |
| Access SQLite or CAS | Persistence is API layer's responsibility |
| Import from `drivers/` | Engine isolation |

### 6.4 Schema Universality

Both Electron UI and Python renderers consume the identical `PrimitiveBundle` schema. The API serializes bundles to JSON for transport to the Electron frontend. Python renderers consume the in-memory dataclass directly. No schema divergence is permitted.

---

## 7. Caching and Persistence Policy

### 7.1 Two Categories of Analysis Output

| Category | Examples | Timing | Persistence |
|----------|----------|--------|-------------|
| **(A) Post-run digest** | Energy, Fermi, convergence, forces, timing | Eager: immediately after step completes | SQLite `run_steps.digest_json` — mandatory |
| **(B) AnalysisObject → Primitives** | Bands, DOS, trajectory, phonon dispersion | Lazy: on-demand when UI requests | Canonical-only in-memory memo; CAS Tier-0.8 snapshot optional |

### 7.2 Post-Run Digest Persistence (Category A)

- Runner calls the registered `scf_digest` parser after each step.
- Digest result is serialized to JSON and written to the `run_steps.digest_json` column.
- This is mandatory for every engine that has a registered digest parser.
- Digest parsers return engine-specific dataclasses (not AnalysisObjects) with `to_dict()`.
- Digests are small (< 10 KB typically); no CAS involvement.

### 7.3 Canonical-Only Memoization (Category B — In-Memory)

The API layer MAY maintain an in-memory memoization cache for AnalysisObjects and CanonicalPrimitiveBundles. Rules:

- Cache key: `(step_ulid, object_type, source_file_stats_tuple)`.
- Staleness: If any source file's `(size_bytes, mtime)` changes, the cache entry is invalidated and re-derived from raw evidence.
- Scope: Per-process only. No cross-process sharing. Lost on process exit.
- Canonical bundles and their source AnalysisObjects are the ONLY analysis results eligible for memoization.
- **DerivedPrimitiveBundles MUST NOT be memoized.** No LRU, no single-slot, no dictionary, no decorator, no caching of any kind for derived bundles or transform outputs.

### 7.4 CAS Tier-0.8 Snapshots (Category B — Persistent)

When the API layer computes a CanonicalPrimitiveBundle, it MAY auto-persist it to CAS under these rules:

- **Key:** `(run_ulid, step_ulid, object_type)` triple.
- **Policy:** One canonical bundle per key. If a new canonical bundle is computed for the same key (e.g., parser upgrade), it OVERWRITES the previous CAS entry.
- **Thumbnail:** One rendered thumbnail image per key, same overwrite policy.
- **DerivedPrimitiveBundle MUST NEVER be written to CAS.**
- **Reading:** The operational UI path MUST NOT read from CAS as a substitute for live derivation. CAS snapshots are for provenance replay and snapshot comparison features ONLY.
- **User pins:** Additional screenshots or view exports may be persisted as separate CAS entries via explicit user "pin" action (append, not auto-managed).

### 7.5 What Is NOT Persisted or Cached

| Item | In-memory memo | CAS | SQLite | Filesystem |
|------|----------------|-----|--------|------------|
| Post-run digest | N/A (read from SQLite) | No | Yes (mandatory) | No |
| AnalysisObject | Yes (optional) | No | No | No |
| CanonicalPrimitiveBundle | Yes (optional) | Yes (Tier-0.8, optional) | No | No |
| DerivedPrimitiveBundle | **No** | **No** | **No** | **No** |
| Transform chain state | **No** | **No** | **No** | **No** |

---

## 8. Layering Responsibilities

### 8.1 Kernel Layer

Provides pure capabilities. No orchestration, no persistence decisions.

| Responsibility | Location |
|---------------|----------|
| AnalysisObject type definitions | `core/analysis/` |
| AnalysisObjectMeta, SourceFileStat | `core/analysis/base.py` |
| Visual primitives (Series1D, GeometryFrame, etc.) | `core/analysis/primitives.py` |
| CanonicalPrimitiveBundle, DerivedPrimitiveBundle | `core/analysis/bundles.py` |
| RenderMeta, ProvenanceMeta | `core/analysis/bundles.py` |
| PrimitiveTransform base + standard transforms | `core/analysis/transforms/` |
| Engine parsers (raw → AnalysisObject) | `drivers/<engine>/parsers/` |
| Digest parsers (raw → Digest dataclass) | `drivers/<engine>/parsers/` |
| Parser registry | `parsers/registry.py` |
| Pure rendering functions (bundle → figure) | `core/analysis/renderers/` |

Kernel MUST NOT:
- Decide when to parse or cache.
- Write to SQLite or CAS.
- Hold memoization state.

### 8.2 API / QVService Layer

Owns orchestration, caching, and persistence.

| Responsibility | Notes |
|---------------|-------|
| Receive analysis requests from frontend | Route by `(calc_ulid, step_ulid, object_type)` |
| Call engine parser → AnalysisObject | Via parser registry lookup |
| Call `to_primitives()` | Produces CanonicalPrimitiveBundle |
| Apply requested transforms | Calls PrimitiveTransform chain; produces DerivedPrimitiveBundle (ephemeral, never cached) |
| Canonical-only in-memory memoization | Cache AnalysisObjects and/or canonical bundles keyed by `(step_ulid, object_type, source_file_stats)` |
| Staleness check | Compare source_files stats against current raw artifact stats |
| Persist post-run digests to SQLite | Mandatory, eager, at run time |
| Persist canonical bundles to CAS (Tier-0.8) | Optional auto-persist; overwrite policy |
| Persist thumbnails to CAS (Tier-0.8) | Optional auto-persist; overwrite policy |
| Enforce derived non-persistence and non-caching | MUST NOT write or cache derived bundles anywhere |
| Serialize bundles for frontend transport | JSON serialization of PrimitiveBundle |

### 8.3 Frontend Layer

Pure consumer. No analysis logic.

| Allowed | Forbidden |
|---------|-----------|
| Receive PrimitiveBundle (JSON) from API | Import kernel modules |
| Render bundle using numeric arrays + RenderMeta | Branch on ProvenanceMeta fields |
| Send transform requests to API (e.g., "apply FermiShift") | Perform data transforms locally |
| Send style preferences (colors, zoom) | Read raw artifacts |
| Request re-render with different transforms | Access SQLite or CAS |
| Display ProvenanceMeta in info panels/tooltips | Use ProvenanceMeta for rendering decisions |

### 8.4 Request Flow

```
Frontend                        API/QVService                     Kernel
   │                                │                                │
   │  GET /analysis                 │                                │
   │  {step_ulid, object_type,      │                                │
   │   transforms: [...]}           │                                │
   ├───────────────────────────────>│                                │
   │                                │                                │
   │                                │  1. Check canonical memo cache │
   │                                │     (cache miss)               │
   │                                │                                │
   │                                │  2. parser = get_parser(       │
   │                                │       engine, object_type)     │
   │                                ├───────────────────────────────>│
   │                                │     analysis_obj = parser      │
   │                                │       .parse(raw_dir)          │
   │                                │<───────────────────────────────┤
   │                                │                                │
   │                                │  3. canonical = analysis_obj   │
   │                                │       .to_primitives()         │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │                                │  4. Store canonical memo cache │
   │                                │  5. CAS Tier-0.8 persist       │
   │                                │     (optional, canonical only) │
   │                                │                                │
   │                                │  6. Apply transforms           │
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
   │  7. Render from arrays +       │                                │
   │     render_meta ONLY           │                                │
   │     (ignore provenance_meta)   │                                │
```

---

## 9. Acceptance Criteria and Future Gate Tests

### 9.1 Gate Test Inventory

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
| **Inv-A6** | `test_render_meta_no_provenance.py` | RenderMeta type has no fields for engine_name, run_ulid, step_ulid, parser_name, source_files, or warnings |
| **Inv-A7** | `test_transform_no_raw_access.py` | AST scan: no transform module imports `pathlib.Path`, `open()`, or `drivers/` modules |
| **Inv-A7** | `test_transform_no_engine_imports.py` | AST scan: no transform module imports from `quantumvitas.drivers` |
| **Inv-A8** | `test_viz_no_raw_access.py` | AST scan: no renderer/viz module reads files or imports engine parsers |
| **Inv-A8** | `test_viz_no_engine_logic.py` | AST scan: no renderer/viz module imports from `quantumvitas.drivers` |
| **Inv-A8** | `test_viz_no_transforms.py` | AST scan: no renderer/viz module imports from `core/analysis/transforms/` |
| **Inv-A8** | `test_viz_no_provenance_meta_access.py` | AST scan: no renderer/viz module accesses `.provenance_meta` or any ProvenanceMeta field for rendering logic (attribute access to `engine_name`, `parser_name`, `run_ulid`, etc.) |
| **Inv-A9** | `test_no_lazy_payloads.py` | AST scan: no `LazyArray`, `LateList`, or deferred-proxy classes in `core/analysis/` |
| **Inv-A10** | `test_no_analysis_disk_cache.py` | No analysis module writes to disk (except CAS via API layer) |
| **Inv-A10** | `test_derived_never_memoized.py` | API layer memo cache keys and values never reference DerivedPrimitiveBundle |
| **Inv-A11** | `test_derived_never_persisted.py` | API layer CAS write paths reject DerivedPrimitiveBundle |
| **Inv-A11** | `test_operational_path_no_cas_read.py` | The default analysis request path does not read from CAS; only explicit replay/snapshot endpoints do |
| **Inv-A12** | `test_frontend_no_kernel_import.py` | Frontend code does not import from kernel analysis modules |

### 9.2 Acceptance Criteria (Behavioral)

1. **Roundtrip determinism**: For any engine's test corpus, `parser.parse(raw_dir).to_primitives()` called twice yields byte-equal serialized canonical bundles (no timestamps or nondeterministic fields).

2. **Transform purity**: For any transform T and any bundle B, `T.apply(B)` returns the same result regardless of call order with other unrelated operations. No hidden state.

3. **Staleness detection**: If a raw artifact is modified (touched with new mtime), the API layer's staleness check detects it and re-derives the AnalysisObject instead of returning a stale memoized result.

4. **Bundle schema universality**: The JSON schema emitted by the API for PrimitiveBundles is consumed without modification by both Electron UI and Jupyter renderers.

5. **Graceful absence**: If raw artifacts are missing (deleted or never produced), the analysis request returns a clear error. It does NOT fall back to CAS, does NOT return partial data, and does NOT crash the API.

6. **Digest independence**: Post-run digest persistence (SQLite) operates independently of the AnalysisObject pipeline. Digest parsing failure does NOT block run completion (warning logged; run status still set).

7. **CAS deletion safety**: Deleting `.provenance/.cas/` does NOT affect the operational analysis path. Analysis is re-derived from raw evidence. Only provenance replay features become unavailable.

8. **Derived ephemerality**: No derived bundle survives beyond the request that created it. Re-requesting the same analysis with the same transforms recomputes from the canonical bundle.

9. **RenderMeta isolation**: A renderer that receives a PrimitiveBundle with `provenance_meta.engine_name = "vasp"` and one with `provenance_meta.engine_name = "orca"` produces visually identical output for identical numeric arrays and render_meta. Engine identity does not leak into rendering.

---

*End of Specification v1.1*
