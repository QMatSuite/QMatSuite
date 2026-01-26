# Analysis Objects Framework: Open Questions & Future Work

**Last Updated**: 2026-01-19  
**Status**: Living Document  
**Related Specs**: [ANALYSIS_OBJECTS_FRAMEWORK.md](./ANALYSIS_OBJECTS_FRAMEWORK.md), [TRAJECTORY_CORE.md](./TRAJECTORY_CORE.md)

---

This document tracks open questions and future work items for the Analysis Objects Framework. Items are grouped by theme and marked with decision points, rationale, and where they should be resolved.

---

## Performance & Scalability

### 1. Provenance Scanning Performance Policy (2026-01-19)

**Question**: Should provenance scanning apply optional performance-based ignores for scratch-heavy directories?

**Context**: Currently provenance tracks ALL files under `raw/` (including scratch-heavy dirs like QE `outdir/`, `.save/`). This is correct for completeness but may be slow on large calculations.

**Decision Needed**:
- Profile scan cost on real workloads (100+ step calculations, large outdirs).
- Define thresholds/heuristics: when does scan time become problematic?
- Decide if we need a default performance policy (e.g., optional ignores for scratch dirs) while preserving correctness.
- Preserve the "provenance is explanatory" philosophy: if we ignore something, it must be clearly documented and user-configurable.

**Where**: Spec + Settings/Advanced configuration.

---

### 2. Cache Invalidation Strictness Modes (2026-01-19)

**Question**: Should we add a "strict mode" for cache validation using SHA256 hashes?

**Context**: v1 stale detection uses `(size_bytes, mtime)` only. SHA256 is deferred but mentioned as a future extension.

**Decision Needed**:
- Define a "strict mode" and the UX/control surface (Settings/Advanced) for enabling SHA-based verification.
- Consider partial hashing or sampling for large files (e.g., hash first 1MB + last 1MB for multi-GB trajectories).
- Document performance tradeoffs: when is strict mode worth the cost?
- Decide whether strict mode should be per-analysis-object-type or global.

**Where**: Spec + `src/quantumvitas/core/analysis/cache.py` + Settings.

---

### 3. Materialization Format & Scaling (2026-01-19)

**Question**: What are the common conventions for chunking, compression, and incremental writes for very large analysis objects?

**Context**: Trajectory currently uses cache serialization (HDF5/chunked or equivalent). Need to scale to:
- Very large MD trajectories (10K+ frames, 1000+ atoms)
- Large band structures (many k-points, many bands)
- High-resolution DOS (many energy points)

**Decision Needed**:
- Decide common conventions for chunking strategies (time-based, frame-based, spatial).
- Decide compression algorithms and when to enable (always vs. size threshold).
- Consider whether we need streaming readers/writers for huge datasets (avoid loading entire trajectory into memory).
- Define maximum cache size policies (eviction, user warnings).

**Where**: Spec + `src/quantumvitas/core/analysis/trajectory/io.py` + future bands/DOS IO modules.

---

## Robustness & Cross-Platform

### 4. Cross-Platform Path + Timestamp Robustness (2026-01-19)

**Question**: Are our path normalization and timestamp handling robust across Windows/macOS/Linux?

**Context**: We use POSIX path normalization (`.as_posix()`) and `mtime` (float). Need to verify edge cases.

**Decision Needed**:
- Confirm path normalization rules (POSIX) are safe on Windows/macOS/Linux (test on all platforms).
- Decide whether to store `mtime_ns` everywhere; document any fallbacks and tolerances.
- Consider clock skew / filesystem timestamp granularity issues:
  - Network filesystems (NFS, SMB) may have coarse timestamps.
  - Clock adjustments (NTP sync) may cause apparent "time travel".
  - Virtual machines may have clock drift.
- Define tolerance thresholds for mtime comparisons (currently 0.01s; is this sufficient?).

**Where**: Spec + `src/quantumvitas/core/artifact_scanning.py` + `src/quantumvitas/core/analysis/base.py` + cross-platform test suite.

---

## Schema & Evolution

### 5. Provenance Map Schema Evolution (2026-01-19)

**Question**: Should we keep a small bounded history window (last N runs) for better user explanations?

**Context**: Current-only `provenance.json` is OK for v1. But users may want to see "this file was produced by run X, then updated by run Y".

**Decision Needed**:
- Decide whether to keep a small bounded history window (last N runs, e.g., N=5 or N=10).
- Define migration strategy for `schema_version` bumps (how to upgrade old provenance.json files).
- Consider whether history should be in a separate file (`.runtime/provenance_history.json`) vs. embedded in main file.
- Decide on retention policy: keep forever vs. bounded window vs. user-configurable.

**Where**: Spec + `src/quantumvitas/core/provenance.py` + migration utilities.

---

## UX & Semantics

### 6. "Missing Artifacts" UX and Semantics (2026-01-19)

**Question**: What is the standard taxonomy for NotAvailable/error states when parsing fails due to missing/disabled engine outputs?

**Context**: When parsing fails (e.g., trajectory parser can't find output file, or engine output was disabled), we need consistent error handling and UI messaging.

**Decision Needed**:
- Define standard NotAvailable/error taxonomy for UI:
  - `NotAvailable` (file missing, but expected)
  - `ParseError` (file exists but malformed)
  - `Disabled` (engine output was disabled by user/config)
  - `Stale` (file exists but cache is stale)
- Decide which warnings vs hard errors make sense per analysis kind:
  - Trajectory: missing relax.out → error? warning?
  - Bands: missing bands.out → error? warning?
  - DOS: missing dos.out → error? warning?
- Define UI presentation: error banners, warning badges, "retry parse" buttons.

**Where**: Spec + `src/quantumvitas/core/analysis/base.py` (add `NotAvailable` exception types) + UI components.

---

### 7. UI Provenance Presentation (2026-01-19)

**Question**: What is the standard UI text and panels for provenance explanation?

**Context**: Provenance is for "UI explanation only". Need consistent presentation across all analysis objects.

**Decision Needed**:
- Decide standard UI text and panels:
  - "Derived from run_id X at time Y"
  - "Updated by run_id Z at time W"
  - "Cache refreshed at time T"
  - "Cache stale; re-parse needed" (with button to refresh)
- Decide where provenance appears:
  - Tooltip on analysis object?
  - Sidebar panel?
  - Info icon with modal?
- Define how to surface "cache refreshed" vs. "cache stale; re-parse needed" states.
- Consider whether to show provenance history (if we implement #5).

**Where**: UI design doc + GUI components + CLI output formatting.

---

## Data Model & Conventions

### 8. Canonical Cell / PBC / Wrapping Conventions (2026-01-19)

**Question**: Are our canonical rules for cell/PBC/wrapping complete and unambiguous?

**Context**: Canonical positions are unwrapped Cartesian. Cell may be `None` or `3x3`. Wrapping is computed later by utilities.

**Decision Needed**:
- Document canonical rules for `pbc` when `cell=None`:
  - If `cell=None`, should `pbc` be `(False, False, False)` always?
  - Or can we have `cell=None` with `pbc=(True, True, True)` for "infinite box" molecular systems?
- Decide how to represent both wrapped and unwrapped in a future extension (if needed) without ambiguity:
  - Add `positions_wrapped` as optional field?
  - Or keep only unwrapped and require explicit `wrap_positions()` call?
- Document any coordinate system conversions (crystal vs. Cartesian, alat scaling) and where they happen (parser vs. utilities).

**Where**: Spec + `src/quantumvitas/core/analysis/trajectory/model.py` + `src/quantumvitas/core/analysis/trajectory/utils.py`.

---

## Testing & Quality

### 9. Engine Parser Correctness Hardening (2026-01-19)

**Question**: What is the consistent testing strategy for each new analysis kind and each new engine?

**Context**: We've started adding minimal fixture-based tests for QE trajectory parser unit conversions. Need a systematic approach.

**Decision Needed**:
- Continue adding minimal fixture-based tests for unit conversions and coordinate conventions per engine:
  - QE: alat/crystal/bohr → Å conversions
  - VASP: direct → Cartesian conversions
  - CP2K: (future) coordinate system handling
- Decide a consistent testing strategy for each new analysis kind:
  - Trajectory: unit conversions, unwrapped positions, cell/PBC
  - Bands: k-point conventions, energy units, band indexing
  - DOS: energy grid conventions, smearing, normalization
- Define minimal fixture requirements:
  - Small, self-contained test outputs (not full calculation outputs)
  - Known expected values (golden reference)
  - Cross-engine consistency checks (same system, different engines → same canonical object)

**Where**: Test strategy doc + `tests/unit/parsers/` + `tests/fixtures/`.

---

## Related Future Work

### 10. Analysis Object Versioning & Backward Compatibility (2026-01-19)

**Question**: How do we handle schema version bumps and backward compatibility for cached analysis objects?

**Context**: `AnalysisObjectMeta` has `schema_version`, but we haven't defined migration paths.

**Decision Needed**:
- Define migration strategy: when `schema_version` changes, how do we upgrade old cache files?
- Decide whether to support reading old cache formats or require re-parse.
- Consider versioning at the object level (trajectory v1.0, v1.1) vs. framework level (analysis objects v1.0).

**Where**: Spec + `src/quantumvitas/core/analysis/cache.py` + migration utilities.

---

### 11. Parser Registry & Discovery (2026-01-19)

**Question**: How do we discover and register parsers for new analysis kinds and engines?

**Context**: We have `@register_parser("qe", "trajectory")` decorator, but need to ensure discoverability.

**Decision Needed**:
- Verify parser registry is sufficient for auto-discovery.
- Decide whether parsers should be lazy-loaded or eagerly registered.
- Consider plugin-style extensions for third-party parsers (future).

**Where**: `src/quantumvitas/parsers/registry.py` + documentation.

---

### 12. Visual Primitives Extension Points (2026-01-19)

**Question**: Are our visual primitives sufficient for all analysis kinds, or do we need extension points?

**Context**: Current primitives: `Series1D`, `GeometryFrame`, `GeometryFrames`, `Marker`. Bands and DOS may need additional types.

**Decision Needed**:
- Evaluate if bands need additional primitives (e.g., `BandStructure2D` for k-path plots).
- Evaluate if DOS needs additional primitives (e.g., `DensitySeries` for partial DOS).
- Decide whether to add new primitives or extend existing ones.
- Keep primitives data-only (no style) as per spec.

**Where**: Spec + `src/quantumvitas/core/analysis/primitives.py` + bands/DOS implementations.

---

### 13. Analysis Object Composition (2026-01-19)

**Question**: How do we represent relationships between analysis objects (e.g., trajectory + bands for the same calculation)?

**Context**: A calculation may produce multiple analysis objects. They may reference each other (e.g., "bands at final trajectory frame").

**Decision Needed**:
- Decide whether to add cross-references (e.g., `Trajectory` has optional `bands_ref: AnalysisObjectRef`).
- Or keep objects independent and let UI/analysis code compose them.
- Consider whether composition belongs in the framework or in higher-level analysis modules.

**Where**: Spec + future analysis composition modules.

---

## How to Add New Items

When adding new open questions to this document:

1. **Date-stamp each item**: Use format `(YYYY-MM-DD)` in the heading.

2. **Keep items actionable**:
   - **Decision needed**: What specific decision must be made?
   - **Why it matters**: What problem does this solve or what risk does it mitigate?
   - **Where it should be decided**: Spec vs. code vs. UI vs. settings

3. **Group by theme**: Use the existing theme sections, or create a new one if needed.

4. **Be concise**: Bullets + brief rationale. Link to related specs or code for details.

5. **Mark resolved items**: When a question is resolved, move it to a "Resolved" section at the bottom (or remove if no longer relevant).

6. **Link to implementation**: When an item is being worked on, add a link to the relevant PR or implementation plan.

---

**End of Document**






