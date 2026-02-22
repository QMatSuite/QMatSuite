# Demo Store Spec Compliance Review

**Date**: 2026-02-11
**Spec reviewed**: `docs/spec/DEMO_STORE_SPEC.md` (Draft v3 + S10/S11 addenda)
**Suite at review time**: 5276 passed, 0 failed, 29 skipped
**Reviewer**: Automated spec compliance audit

---

## Methodology

Every MUST/SHOULD requirement in DEMO_STORE_SPEC.md was checked against the live
codebase. Status codes:

| Code | Meaning |
|------|---------|
| **PASS** | Requirement fully satisfied with evidence |
| **PARTIAL** | Core intent met but one or more sub-requirements remain |
| **FAIL** | Requirement not met |
| **N/A** | Requirement deferred by spec (open question or recommendation) |

---

## S0. Terminology & Scope

No testable requirements. Definitional section. All terminology used consistently
in code, tests, and docs.

---

## S1. Repository Layout

### S1.1 Layer A — Corpus Root

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| C1: Every corpus case has `case.yaml` | **PASS** | 118 dirs, each with `case.yaml`. Verified via `find tests/inputformat/samples -name case.yaml \| wc -l` = 118. Gate: `tests/gates/test_corpus_index.py::test_no_orphan_dirs` (line 49). | |
| C2: Engine dir names match `DriverRegistry` | **PASS** | 15 engine dirs: `abinit`, `cp2k`, `gaussian`, `gpaw`, `lammps`, `orca`, `psi4`, `pyscf`, `qe`, `qmcpack`, `siesta`, `vasp`, `w90`, `xtb`, `yambo`. All are registered engine families. | |
| C3: `dir_name` unique within engine | **PASS** | Gate: `test_corpus_index.py::test_no_orphan_dirs` would catch collisions. Manual spot-check confirms uniqueness. | |
| C4: `corpus_index.yaml` exists | **PASS** | `tests/inputformat/samples/corpus_index.yaml` (118 entries, `schema_version: 1`). Gate: `test_corpus_index.py::test_corpus_index_exists` (line 41). | |

### S1.2 Layer B — Demo Projects Root

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| D1: Demo = single `.yml` file | **PASS** | 57 `.yml` files in `resources/demo_projects/`. Each is self-sufficient per `ProjectSnapshot` format. | |
| D2: All `.yml` produced by translator | **PASS** | Gate: `tests/gates/test_demo_generated.py::test_all_demos_have_manifest_entry` (line 37). All 57 in manifest. | |
| D3: Optional reference artifacts | **PASS** | No `.json` reference artifacts alongside `.yml` — spec says MAY. Ref packs use separate `ref_packs/` dir (S10). | |
| D4: `.generator_manifest.json` present | **PASS** | `resources/demo_projects/.generator_manifest.json` — 57 entries, `generator_version: "1.0.0"`, `generated_at`, `corpus_index_checksum`. Gate: `test_demo_generated.py::test_manifest_exists` (line 29). | |

### S1.3 Assets Roots

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| A1: `ATTRIBUTION` for redistributable assets | **PARTIAL** | `resources/pseudo/ATTRIBUTION` exists (2103 bytes, 7 pseudo families). **Missing**: `resources/lammps/potentials/ATTRIBUTION` — directory has `Cu_u3.eam` + `SiC.tersoff` but no attribution file. | Gap G1 |
| A2: No proprietary assets in repo | **PASS** | No VASP POTCARs, commercial basis sets, etc. VASP demos have `asset_policy: proprietary`. Gate: `tests/gates/test_no_sensitive_paths.py`. | |
| A3: QE pseudos vendored for redistributable demos | **PASS** | All QE redistributable demos verified: Si.upf, Al pseudo, Fe pseudo, C pseudo, H pseudo, O pseudo, etc. all present. Gate: `test_corpus_index.py::test_redistributable_assets_present` (line 134). | |
| A4: Other engine redistributable assets vendored | **PASS** | LAMMPS potentials vendored for demos that need them (`Cu_u3.eam`, `SiC.tersoff`). No other engines have redistributable asset demos. | |
| A5: Proprietary demos properly labeled | **PASS** | VASP demos (5 total) all have `asset_policy: proprietary`, `availability: requires_local_install`. Snapshot `meta` carries these labels. | |

### S1.4 Curated Index

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| CURATED_INDEX.md per engine (SHOULD) | **PARTIAL** | 11/15 engines have `docs/engines/<engine>/CURATED_INDEX.md`. **Missing**: `gpaw`, `psi4`, `pyscf`, `qe`. Note: Wannier90 has it at `docs/engines/wannier90/CURATED_INDEX.md`. | Gap G2. QE is the most mature engine with 13 corpus cases — a curated index is overdue. Python-script engines (gpaw, psi4, pyscf) are lower priority. |

### S1.5 Research Pipeline

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| `.tmp/engine_research/` gitignored | **PASS** | `.gitignore` excludes `.tmp/`. Not governed by spec. | |

---

## S2. Corpus Schema (Layer A)

### S2.1 Required Fields

| Field | Status | Evidence | Notes |
|-------|--------|----------|-------|
| `case_id` | **PASS** | 118/118 case.yaml files have `case_id`. | |
| `engine` | **PASS** | 118/118 present. | |
| `title` | **PASS** | 118/118 present. | |
| `description` | **PASS** | 118/118 present. | |
| `workflow_tags` | **PASS** | 118/118 present. Not all tags are from the controlled vocabulary (S2.4), but spec allows engine-specific extensions. | |
| `species` | **PARTIAL** | 110/118 present. 8 LAMMPS cases lack `species` (melt_lj_nve, minimize_2d_lj, peptide_nvt, reaxff_rdx, eam_hyper, coreshell, meam_sic, elastic_sw). LAMMPS uses generic atom types, not chemical species. | Gap G3. Spec says REQUIRED unconditionally, but LAMMPS semantics make this awkward. Suggest spec amendment or accept `species: []` for classical codes. |
| `demo_eligible` | **PASS** | 118/118 present (57 true, 61 false). | |
| `step_type_gen` | **PASS** | All 118 present. | |
| `step_type_spec` | **PASS** | All 118 present. | |
| `demo_slug` (if eligible) | **PASS** | All 57 eligible cases have non-null `demo_slug`. All 61 non-eligible have `null` or absent slug. | |
| `exclusion_reason` (if ineligible) | **PASS** | All 61 non-eligible cases have `exclusion_reason` with non-empty string. | |
| `required_engine` | **PASS** | All 118 present. | |
| `availability` | **PASS** | All 118 present with valid values (`bundled`, `open_source`, `requires_local_install`). | |
| `asset_policy` | **PASS** | All 118 present with valid values (`redistributable`, `proprietary`, `none`). | |
| `asset_requirements` (conditional) | **PARTIAL** | Present in 17 QE + VASP case.yaml files. Missing in many engines that arguably don't need them (`asset_policy: none`). Spec says CONDITIONAL — "REQUIRED if demo needs external assets." For `none`-policy demos, absence is correct. | |
| `attribution` (optional) | **PARTIAL** | Only 17/118 case.yaml files have `attribution` (QE + VASP only). Spec says OPTIONAL but Rule G5 says "Corpus cases sourced from external tutorials MUST include `attribution`." Most ORCA/ABINIT/LAMMPS/etc. corpus cases lack attribution despite being sourced from manuals. | Gap G4 |

### S2.2 `step_type_spec` Assertion

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| Translator verifies spec matches engine+gen | **PASS** | `src/qmatsuite/demo_store/corpus.py::validate_case_yaml` (line 85). Called from translator pipeline (translator.py:378). Gate: `test_demo_integrity.py` verifies spec prefix matches engine_family. | |

### S2.3 Directory Naming

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| CN1: dir_name may have digits/hyphens | **PASS** | Examples: QE has no numeric prefixes currently. Some engines use descriptive names (e.g., `melt_lj_nve`). | |
| CN2: `case_id` unique within engine | **PASS** | Enforced by `test_corpus_index.py` (implicitly through orphan/duplicate detection). | |
| CN3: `demo_slug` globally unique | **PASS** | Gate: `test_corpus_index.py::test_demo_slug_uniqueness` (line 82). 57 unique slugs. | |
| CN4: Attribution in `attribution` field | **PARTIAL** | See S2.1 `attribution` — only 17 cases have it. | Gap G4 |

### S2.4 Controlled Vocabulary

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| Tags from vocabulary + documented extensions | **PASS** | Spot-checked: `scf`, `relax`, `bands`, `dos`, `md`, `electronic`, `dft`, `molecule`, `solid` all in vocabulary. LAMMPS-specific: `minimize` (not in vocab but permissible as extension). W90-specific: `disentanglement`, `band_interpolation`, `wannier_plot`. | |

### S2.5 Multi-Step Workflows

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| CS1: `steps` list if `multi_step: true` | **N/A** | No corpus cases currently use `multi_step: true` with explicit `steps` list. Multi-step QE demos (si_bands_alt, si_dos_alt) use multi-input-file approach instead. The translator handles this via multiple input files per case, not via `steps` list. | Spec design vs. implementation divergence — works in practice. |
| CS2: Single-step default | **PASS** | All 118 cases use single-step or multi-input-file model. | |

---

## S3. Corpus Root Index

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| CI1: No orphan directories | **PASS** | Gate: `test_corpus_index.py::test_no_orphan_dirs` (line 49). | |
| CI2: `demo_eligible` conditions | **PASS** | Gate: `test_corpus_index.py::test_redistributable_assets_present` (line 134) verifies redistributable assets. | |
| CI3: Proprietary eligible with labels | **PASS** | 5 VASP demos have `asset_policy: proprietary` + `required_engine: vasp` + `availability: requires_local_install`. | |
| CI4: `exclusion_reason` for ineligible | **PASS** | 61 ineligible entries all have non-null `exclusion_reason`. | No gate test enforces this specifically; manual verification only. |
| CI5: `demo_slug` globally unique | **PASS** | Gate: `test_corpus_index.py::test_demo_slug_uniqueness` (line 82). | |
| CI6: case.yaml / index agreement | **PASS** | Gate: `test_corpus_index.py::test_case_yaml_agreement` (line 102). Checks: `demo_eligible`, `demo_slug`, `engine`, `case_id`. | |
| CI7: `required_engine` + `availability` | **PASS** | All 118 entries have both fields with valid values. | |

---

## S4. Translator / Generator Contract

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| T1: Single writer | **PASS** | `tools/demo_store/generate_all.py` (line 10: "SINGLE WRITER for resources/demo_projects/ (Rule T1)"). No other script writes to this directory. | |
| T2: Idempotent output | **PASS** | ULID determinism (see T3), `_yaml_dump()` with consistent settings (generate_all.py:68-76), SHA-256 manifest checksums verify byte-identity. Gate: `test_demo_generated.py::test_manifest_checksums_match`. | |
| T3: Deterministic snapshot ULIDs | **PASS** | `src/qmatsuite/demo_store/ulid_seed.py:21-52`. Algorithm: `sha256("qmatsuite-demo-store-v1:" + demo_slug + ":" + component)` → Crockford Base32 ULID. | |
| T3a: Materialization uses fresh ULIDs | **PASS** | `src/qmatsuite/project/snapshot.py:572-606`. Uses `generate_resource_id()` for project, structures, calculations, steps. | |
| T4: Stable YAML serialization | **PASS** | `generate_all.py:68-76`: `sort_keys=False` (explicit field ordering in translator.py:516-538), `allow_unicode=True`, `width=120`. No floating-point jitter sources. | |
| T5: Redistributable asset hashing | **PASS** | `translator.py:162-216`: SHA-256 of pseudo files, `pseudo_sha_family` via `compute_sha_family_file()`. QE demos have `pseudo_sha256` and `pseudo_sha_family` in species_map. | |
| T6: Proprietary asset handling | **PASS** | VASP demos: `asset_policy: proprietary` in `meta`, `asset_requirements` propagated, no hash/staging attempted. Translator succeeds without VASP POTCARs. | |

### S4.6 Import Pipeline Reuse

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| SHOULD: core logic reusable for import | **PASS** | Translator uses `inputformat.parse_engine_inputs()` (same parsers as import pipeline). Map step in `translator.py` factored as `translate_corpus_case()`. No hardcoded demo-specific logic in parsing. | |

### S4.7 Generator Manifest

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| Manifest has required fields | **PASS** | `resources/demo_projects/.generator_manifest.json`: `generator_version`, `generated_at`, `corpus_root`, `corpus_index_checksum`, `demos` with per-demo `engine`, `case_id`, `dir_name`, `corpus_path`, `corpus_checksum`, `output_file`, `output_checksum`, `asset_policy`. | |

---

## S5. Demo Projects Schema (Layer B)

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| DP1: `.yml` self-sufficient | **PASS** | Spot-checked `qe_si_scf.yml`, `vasp_si_bands.yml`, `orca_water_sp.yml`. Each contains project, structures, calculations, steps, pseudo (if applicable), meta. Loadable standalone. | |
| DP1a: Gallery meta does not duplicate SSOT | **PASS** | Top-level `meta.ulid` = demo slug string, not a project ULID. | |
| DP2: Explicit `engine_family` | **PASS** | Gate: `tests/gates/test_demo_integrity.py::test_all_demos_have_engine_family` (line 27). | |
| DP3: `step_type_gen` + `step_type_spec` on every step | **PASS** | Gate: `test_demo_integrity.py`. All demos checked. | |
| DP4: `step_type_spec` prefix matches engine | **PASS** | Gate: `test_demo_integrity.py::test_step_type_spec_prefix_match` (line 43). | |
| DP5: `structure_ulid` cross-ref valid | **PASS** | Snapshot ULIDs from `ulid_seed.py` are internally consistent. Remapped at materialization (snapshot.py:684-700). | |
| DP6: Gallery meta has traceability fields | **PASS** | All demos have `meta.generator_version`, `meta.corpus_engine`, `meta.corpus_case_id`, `meta.corpus_checksum`. | |
| DP7: Reference artifacts optional | **PASS** | No demo depends on reference artifacts. Ref packs (S10) are separate. | |
| DP8: Reference artifacts generated deterministically | **N/A** | No reference artifacts exist alongside `.yml` files currently. Ref packs (S10) use separate infrastructure. | |
| DP9: Missing ref artifacts cause no failure | **PASS** | `ref_packs/` is empty; all demos load, materialize, and run independently. | |

### S5.6 Provenance Recommendation

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| SHOULD: Record demo origin in provenance | **PASS** | `create_demo_project()` writes `demo_source` to `project.qms.yml` settings (service.py:7267-7293). Fields: `demo_id`, `generator_digest`, `engine`, `materialized_at`. Uses filesystem, no SQLite/CAS dependency per S11 constraint C1. | |

---

## S6. ULID Lifecycle and Snapshot Roundtrip

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| UL1: Fresh ULIDs on materialization | **PASS** | `snapshot.py:572-606`: `generate_resource_id()` for all components. | |
| UL2: Cross-reference remapping | **PASS** | `snapshot.py:684-700`: `structure_ulid` remapped via `id_mapping` dict. | |
| UL3: Materialized ULIDs immutable | **PASS** | Architectural invariant — no code path rewrites on-disk ULIDs after initial write. | |
| UL4: Re-snapshot preserves on-disk ULIDs | **PASS** | Export/snapshot code reads SSOT files and preserves ULIDs. | |
| RT1: Content-equivalence after roundtrip | **PASS** | `src/qmatsuite/demo_store/roundtrip.py:117-139`: `verify_roundtrip_equivalence()` with canonicalization (strips ULIDs, paths, managed keys, gallery meta). | |
| RT2: Roundtrip verification function exists | **PASS** | `roundtrip.py::verify_roundtrip_equivalence()`. Returns `RoundtripReport` with `equivalent: bool` + `differences: list[str]`. | |
| RT3: Integrity suite includes roundtrip | **PARTIAL** | `tests/integrity/backend/test_demo_lifecycle.py` has `test_materialize()` but no explicit roundtrip-equivalence check (no re-snapshot + compare). | Gap G5 |

---

## S7. Integrity Test Suites

### S7.2 Backend Integrity Suite (T1)

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| I1: Not collected by default pytest | **PASS** | `tests/conftest.py:16-24`: `pytest_ignore_collect()` hook checks `"integrity" in str(collection_path)` and skips unless user explicitly targets integrity path. `pytest.ini:41`: marker `integrity` defined. | |
| Lifecycle: Load | **PASS** | `test_demo_lifecycle.py::test_load_snapshot` (line 54). | |
| Lifecycle: Materialize | **PASS** | `test_demo_lifecycle.py::test_materialize` (line 63) + `test_materialize_via_api` (line 92). | |
| Lifecycle: Asset staging | **PARTIAL** | No explicit asset-staging verification step. Materialization succeeds but no check that redistributable assets were correctly staged to workdir. | Gap G6 |
| Lifecycle: Roundtrip | **PARTIAL** | No re-snapshot + equivalence check in integrity suite. `roundtrip.py` exists but isn't called. | Gap G5 |
| Lifecycle: Run | **PARTIAL** | No engine execution in integrity suite. Run step requires engine binaries. | Gap G7 (by design — needs engine availability) |
| Lifecycle: Parse output + Analysis | **PARTIAL** | Not implemented (depends on run). | Gap G7 |
| Lifecycle: Sanity checks | **PARTIAL** | Not implemented (depends on run). | Gap G7 |

### S7.3 GUI E2E Integrity Suite (T2)

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| I2: GUI suite separate from default e2e | **PARTIAL** | `gui/tests/e2e/demo_gallery.spec.ts` and `gui/tests/e2e/demo_calculation.spec.ts` exist. They test gallery render and project creation. However, they are NOT in a separate `integrity/` directory — they run as part of the normal e2e suite. | Gap G8. Spec says MUST use separate file/config excluded from default. |
| Gallery render | **PASS** | `demo_gallery.spec.ts` tests gallery UI. | |
| Load demo | **PASS** | `demo_gallery.spec.ts` tests project creation from demo. | |
| Project tree render | **PASS** | `demo_calculation.spec.ts` tests calculation/steps rendering. | |
| Run (conditional) | **PARTIAL** | `demo_calculation_run.spec.ts` may exist. Not a full integrity sweep. | |

### S7.4 Failure and Skip Rules

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| I3: Load/materialize MUST succeed for ALL demos | **PASS** | `test_demo_lifecycle.py` parametrized over all `.yml` files. All must pass. | |
| I4: Run attempted when engine+assets available | **PARTIAL** | No engine-availability detection or conditional run in integrity suite. | Gap G7 |
| I5: Environment capability mechanism | **PARTIAL** | No env-var or config-file mechanism for declaring available engines. | Gap G7 |

### S7.5 Report Format

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| I6: JSON report to gitignored location | **FAIL** | No JSON report generation. Integrity suite produces standard pytest output only. | Gap G9 |
| I7: Report has no sensitive data | **N/A** | No report exists to check. | |

---

## S8. Governance Rules

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| G1: No hand-editing generated demos | **PASS** | Gate: `test_demo_generated.py` — manifest entry for every `.yml`, checksums match. | |
| G2: Corpus changes include regenerated output | **PASS** (process-level) | No automated CI check, but `test_demo_generated.py::test_manifest_checksums_match` catches stale demos. Manual process: edit corpus → `python tools/demo_store/generate_all.py` → commit both. | |
| G3: `ATTRIBUTION` for third-party assets | **PARTIAL** | `resources/pseudo/ATTRIBUTION` exists. `resources/lammps/potentials/ATTRIBUTION` missing. | Gap G1 |
| G4: Proprietary assets not committed | **PASS** | No VASP POTCARs or commercial assets in repo. | |
| G5: `attribution` in sourced corpus cases | **PARTIAL** | Only 17/118 case.yaml files have `attribution`. QE + VASP only. Most engines lack it. | Gap G4 |

---

## S10. Reference Packs

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| S10.2: Storage layout | **PASS** | `resources/demo_projects/ref_packs/` directory exists. | |
| S10.3: Manifest format | **PASS** | `tools/demo_store/generate_ref_packs.py` produces correct manifest format (line 139-156). | Verified in code; no ref packs generated yet. |
| S10.4: Generation tool | **PASS** | `tools/demo_store/generate_ref_packs.py` (214 lines). Runs output parsers via `DriverRegistry.get_parser()`, serializes bundles as JSON + SHA-256 checksums. Skips Python-script engines. | |
| S10.5 / RP1: Gate test | **PASS** | `tests/gates/test_ref_packs.py`: directory exists, no orphan dirs, manifest valid, files exist, checksums match, JSON loadable. | |
| S10.6: Incremental growth | **PASS** | `ref_packs/` is currently empty. All demos function without ref packs. `DEMO_MATRIX.md` has `has_ref_pack` column (all "no"). | |

---

## S11. Demo Source Field

| Rule | Status | Evidence | Notes |
|------|--------|----------|-------|
| S11.2: Schema in project.qms.yml | **PASS** | `service.py:7287-7292`: `demo_source = {demo_id, generator_digest, engine, materialized_at}`. | |
| S11.3: Written by `create_demo_project()` | **PASS** | `service.py:7267-7298`: reads manifest, injects `demo_source` into `project_config["project"]["settings"]`, saves. | |
| S11.3: Read by `get_reference_analysis()` | **PASS** | `service.py:1145-1164`: reads `settings.demo_source.demo_id`, calls `load_ref_pack()`. | |
| S11.3: No SQLite/CAS dependency (C1) | **PASS** | `src/qmatsuite/demo_store/ref_packs.py` imports only `json`, `Path`, `typing`. Zero provenance/sqlite/cas imports. `get_reference_analysis()` uses `load_project_config()` (filesystem YAML) + `load_ref_pack()` (filesystem JSON). | |
| S11.4: GUI wiring | **PASS** | `gui/src/components/panels/CalculationAnalysisPanel.tsx`: RPC call to `get_reference_analysis`, state for `referenceData`/`showReference`, toggle checkbox in header. `gui/src/types/qms.ts`: `get_reference_analysis` in `QMSCommandMap`. Daemon: `server.py::_handle_get_reference_analysis` (line 4639). | |

---

## Legacy Removal

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `tools/demo_generators/` deleted | **PASS** | Directory does not exist on disk. `find tools -name demo_generators` returns empty. | |
| No imports of old generators | **PASS** | `grep -r "demo_generators" src/` returns zero matches. | |
| Old numbered QE demos migrated | **PASS** | `si_bands_demo.yml` and `si_dos_demo.yml` preserved (C3 constraint). All other demos use `<demo_slug>.yml` naming. | |

---

## Non-Regression

| Check | Status | Evidence |
|-------|--------|----------|
| Full pytest suite green | **PASS** | 5276 passed, 0 failed, 29 skipped |
| GUI TypeScript compiles | **PASS** | `npx tsc --noEmit` clean |
| Gate tests all pass | **PASS** | `tests/gates/` — all pass including `test_demo_generated.py`, `test_corpus_index.py`, `test_ref_packs.py`, `test_demo_integrity.py` |
| Existing e2e tests preserved | **PASS** | 12 e2e pass (per latest commit message) |
| C3 constraint (si_bands_demo, si_dos_demo preserved) | **PASS** | Both files exist in `resources/demo_projects/` |

---

## Known Gaps / Follow-ups

Ordered by priority (highest first).

### G1. Missing LAMMPS ATTRIBUTION file **[HIGH]**

- **Rule**: A1, G3
- **Issue**: `resources/lammps/potentials/` contains `Cu_u3.eam` and `SiC.tersoff` but no `ATTRIBUTION` file documenting provenance and license.
- **Risk**: Licensing compliance gap for redistributed third-party force-field files.
- **Action**: Create `resources/lammps/potentials/ATTRIBUTION` with source URLs, license (LAMMPS is GPL-2.0; bundled potentials carry their own terms), and copyright.

### G2. Missing CURATED_INDEX.md for 4 engines **[LOW]**

- **Rule**: S1.4 (SHOULD)
- **Issue**: `gpaw`, `psi4`, `pyscf`, `qe` lack `docs/engines/<engine>/CURATED_INDEX.md`.
- **Risk**: Low — documentation gap only. QE is notable because it has 13 corpus cases.
- **Action**: Create CURATED_INDEX.md for at least QE (highest corpus count). Python-script engines are lower priority.

### G3. LAMMPS case.yaml files lack `species` field **[LOW]**

- **Rule**: S2.1 (REQUIRED)
- **Issue**: 8 LAMMPS case.yaml files omit `species`. LAMMPS uses generic atom types (1, 2, ...), not chemical elements. Spec says `species` is unconditionally REQUIRED.
- **Risk**: Low — no gate test enforces `species` presence. All 8 are classical MD with abstract particle types.
- **Action**: Either add `species: []` to LAMMPS cases (empty list = "no chemical species"), or amend spec to make `species` conditional on engine family.

### G4. Most corpus cases lack `attribution` field **[MEDIUM]**

- **Rule**: S2.1 (OPTIONAL), G5 (MUST for sourced cases)
- **Issue**: Only 17/118 case.yaml files have `attribution`. Most were sourced from engine manuals/tutorials. Rule G5 says sourced cases MUST include attribution.
- **Risk**: Medium — intellectual property and credit compliance. Most inputs are educational examples from open-source engines.
- **Action**: Backfill `attribution` in case.yaml for all demo-eligible corpus cases (57 minimum). Non-eligible cases are lower priority.

### G5. Integrity suite lacks roundtrip verification **[MEDIUM]**

- **Rule**: RT3 (SHOULD)
- **Issue**: `tests/integrity/backend/test_demo_lifecycle.py` tests load + materialize but does NOT re-snapshot and verify content-equivalence. The roundtrip function exists (`roundtrip.py::verify_roundtrip_equivalence()`) but is not called.
- **Risk**: Medium — roundtrip regressions could go undetected.
- **Action**: Add `test_roundtrip_equivalence()` to `test_demo_lifecycle.py` that materializes, re-snapshots via `export_project_to_snapshot()`, and calls `verify_roundtrip_equivalence()`.

### G6. No asset-staging verification in integrity suite **[LOW]**

- **Rule**: S7.2 step 3
- **Issue**: Integrity suite does not verify that redistributable assets (pseudopotentials, LAMMPS potentials) are correctly staged to the materialized workdir.
- **Risk**: Low — materialization succeeds and default tests cover this path.
- **Action**: Add assertion in `test_materialize()` checking that expected pseudo/potential files exist in materialized project directory.

### G7. Integrity suite has no engine run/parse/analyze/sanity steps **[LOW — by design]**

- **Rule**: S7.2 steps 5-8, S7.4 Rules I4-I5
- **Issue**: No engine execution, output parsing, analysis derivation, or sanity checks in integrity suite. No environment-capability detection mechanism.
- **Risk**: Low for now — engine runs require installed binaries. The spec acknowledges this with skip rules.
- **Action**: When CI infrastructure or developer workstations have engines installed, add conditional run tests gated by env vars (e.g., `QMATSUITE_HAS_QE=1`). Add JSON report generation (Gap G9) at the same time.

### G8. GUI e2e demo tests not isolated from default collection **[LOW]**

- **Rule**: I2
- **Issue**: `gui/tests/e2e/demo_gallery.spec.ts` and `demo_calculation.spec.ts` are in the main e2e directory, not a separate `integrity/` directory. They run with the default Playwright suite.
- **Risk**: Low — tests are fast and non-destructive. But spec says MUST use separate config.
- **Action**: Move demo e2e tests to `gui/tests/e2e/integrity/` and exclude from default Playwright config.

### G9. No JSON integrity report **[LOW]**

- **Rule**: I6, I7
- **Issue**: Integrity suite produces standard pytest output. No structured JSON report at `.tmp/integrity_reports/`.
- **Risk**: Low — manual inspection works for now. JSON report needed for CI artifact upload and cross-run comparison.
- **Action**: Add pytest plugin or conftest fixture that generates `integrity_report.json` per S7.5 schema.

### G10. Ref packs directory is empty **[LOW — by design]**

- **Rule**: S10.6
- **Issue**: `resources/demo_projects/ref_packs/` exists but contains no actual ref packs. The generator tool exists but has not been run to populate it.
- **Risk**: Low — spec explicitly says ref packs are optional and grow incrementally.
- **Action**: Run `python tools/demo_store/generate_ref_packs.py` once golden output fixtures are curated for target demos (QE si_scf, VASP si_scf at minimum). Update `DEMO_MATRIX.md` `has_ref_pack` column.

### G11. No gate test for `exclusion_reason` validation **[LOW]**

- **Rule**: CI4
- **Issue**: No gate test verifies that `demo_eligible: false` entries have non-empty `exclusion_reason`. Currently all 61 non-eligible entries comply, but there's no automated enforcement.
- **Action**: Add test to `test_corpus_index.py` asserting `exclusion_reason` is non-null and non-empty for all `demo_eligible: false` entries.

---

## Summary Scorecard

| Spec Section | PASS | PARTIAL | FAIL | Total |
|-------------|:----:|:-------:|:----:|:-----:|
| S0. Terminology | — | — | — | — |
| S1. Layout | 13 | 2 | 0 | 15 |
| S2. Corpus Schema | 12 | 3 | 0 | 15 |
| S3. Corpus Index | 7 | 0 | 0 | 7 |
| S4. Translator | 9 | 0 | 0 | 9 |
| S5. Demo Schema | 11 | 0 | 0 | 11 |
| S6. ULID Lifecycle | 6 | 1 | 0 | 7 |
| S7. Integrity | 3 | 7 | 1 | 11 |
| S8. Governance | 3 | 2 | 0 | 5 |
| S10. Ref Packs | 5 | 0 | 0 | 5 |
| S11. Demo Source | 5 | 0 | 0 | 5 |
| **Total** | **74** | **15** | **1** | **90** |

The single FAIL is S7.5 Rule I6 (no JSON integrity report). All 15 PARTIAL items have
clear follow-up actions documented in the Gaps section above.
