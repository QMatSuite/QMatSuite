# QMCPACK Phase B1 Worklog

## 2026-02-06 — Session Start

### Plan Written
- Created `PHASE_B1_PLAN.md` covering stages 1-3 exploration
- QMCPACK 4.1.0 binary at `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack`
- Also available: `convert4qmc`, `convertpw4qmc`, `ppconvert`, `qmcfinitesize`, `gpaw4qmcpack.py`
- QE pw2qmcpack.x at `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x`
- Build is MPI-enabled (openmpi 5.0.9)

### Stage 1: Corpus Collection — DONE
- Explored QMCPACK source tree: labs/ (5 tutorials), examples/ (He, H2O, solids), tests/ (25 molecule + 19 solid systems)
- Read XSD schema (`schema/qmcpack.xsd`): 886 lines, defines all major types
- Crawled readthedocs pages: input_overview, running, hamiltonians, methods, wavefunctions, examples, output_overview, afqmc, labs
- Key XML structure mapped: simulation > {project, qmcsystem > {simulationcell, particleset, wavefunction, hamiltonian}, qmc, loop}
- XSD enums cataloged: QMCEngineEnum (vmc/dmc/rmc/optimize/test), QMCMoveEnum (pbyp/walker), JastrowFunctionEnum (One-Body/Two-Body/Three-Body/Polarization), etc.
- Extracted 1,438 XML files to `.tmp/engine_research/qmcpack/extracted/`:
  - `labs/` (5 lab tutorials)
  - `examples/` (He, H2O, solids)
  - `tests_molecules/` (22 subdirectories: H2_ae, Be_STO, FeCO6, etc.)
  - `tests_solids/` (28 subdirectories: diamondC, bccMo, graphene, NiO, etc.)
  - `tests_converter/` (22 converter test directories)
  - `schema/` (10 XSD/XML schema files)
  - `pseudopotentials_for_tests/` (PP library)
- Crawled community/academic sources: GitHub workshops, Nexus docs, pseudopotential libraries, AFQMC tutorials

### Stage 2: Metadata Seed — DONE
- Created `metadata/qmcpack_xml_elements.json`: **175 entries** (71KB)
  - Categories: simulation root, system/cell, particles, wavefunction, SPO builders, Jastrow, hamiltonian, estimators, QMC blocks, loop, includes
  - Each entry: xpath, kind, type, description, allowed_values, default, required, provenance
- Created `metadata/qmcpack_qmc_parameters.json`: per-method parameter catalog
  - VMC, DMC, linear optimization, general optimize
  - All parameters with type, default, description, provenance
- Created `metadata/qmcpack_estimators.json`: estimator type catalog
  - LocalEnergy, density, spindensity, gofr, sk, dm1b, Force, Pressure, chiesa, etc.

### Stage 3: Normalized Case Library — DONE
- Created **13 normalized cases** under `.tmp/engine_research/qmcpack/normalized/`:
  - Each case: `qmc_input.xml` + `case.yaml` + `source.txt`

| Case ID | System | Method | Wavefunction | BC | External Assets |
|---------|--------|--------|-------------|-----|-----------------|
| he_vmc_sto | He atom | VMC | STO + Pade Jastrow | open | none |
| he_opt_pade | He atom | linear opt (4 loops) | STO + Pade Jastrow | open | none |
| he_dmc | He atom | VMC + DMC | STO + Pade Jastrow | open | none |
| he_bspline_jastrow | He atom | VMC | STO + bspline Jastrow | open | none |
| be_sto_vmc | Be atom | VMC | STO (Bunge basis) | open | none |
| h2_ae_vmc | H2 molecule | VMC | Gaussian LCAO + J1+J2 | open | none |
| h2o_vmc_pp | H2O | VMC | BFD PP | open | PP XMLs (ResourceRef) |
| lih_pp_vmc | LiH molecule | VMC | BFD PP | open | PP XMLs (ResourceRef) |
| heg_vmc | Electron gas | VMC | Free particle | PBC | none |
| o2_opt_bspline | O2 dimer | optimization | bspline/HDF5 | open | HDF5 (ResourceRef) |
| o2_dmc_bspline | O2 dimer | VMC+DMC | bspline/HDF5 | open | HDF5 (ResourceRef) |
| lih_solid_vmc_pp | LiH solid | VMC | einspline/HDF5 | PBC | HDF5 + PP (ResourceRef) |
| diamond_vmc_pp | Diamond C | VMC | bspline/HDF5 | PBC | HDF5 + PP (ResourceRef) |

### Stage 3: Fast Case Execution — DONE
- Executed **5 fast self-contained cases** with QMCPACK 4.1.0:

| Case | Method | Energy (Ha) | Reference (Ha) | Wall Time | Status |
|------|--------|-------------|-----------------|-----------|--------|
| he_vmc_sto | VMC | -2.773 | -2.904 | 1.1s | SUCCESS |
| he_dmc | VMC+DMC | -2.870 (DMC) | -2.904 | 4.9s | SUCCESS |
| he_opt_pade | opt+VMC | -2.897 (final) | -2.904 | 6.9s | SUCCESS |
| be_sto_vmc | VMC | -14.626 | -14.667 | 7.8s | SUCCESS |
| h2_ae_vmc | VMC | -1.177 | -1.175 | 1.7s | SUCCESS |

- Run manifests + digests stored in `.tmp/engine_research/qmcpack/runs/<case_id>/`
- Key observations:
  - Batch driver (QMCPACK 4.x) requires `driver_version=batch` or `legacy`
  - Legacy driver needed for `samples` parameter in optimization (batch driver checks `samples <= walkers * blocks * steps`)
  - All-electron cases (He, Be, H2) run in <10s each
  - DMC energy (-2.870 Ha) approaches exact He energy (-2.904 Ha) despite small walker population

### Lessons Learned (Stages 1-3)
1. **driver_version matters**: batch vs legacy have different sample semantics
2. **Self-contained inputs**: He/Be/H2 are fully self-contained (STO/Gaussian basis, no external files)
3. **HDF5-dependent cases**: O2/LiH/Diamond require pw2qmcpack preprocessing (not executed in Stage 3)
4. **Optimization with loop**: `<loop max="N">` wraps `<qmc method="linear">` for iterative optimization
5. **QMCPACK output structure**: scalar.dat (block-averaged), dmc.dat (step-level), opt.xml (optimized params)

---

## 2026-02-06 — Stages 4-8 Implementation

### Stage 4: XML Parser + Enhanced Writer — DONE

**Parser** (`_parse_qmcpack_text` in `inputspec.py`):
- Full XML parser using `xml.etree.ElementTree`
- Returns `{"params": {...}, "structure": {...}}` for content_role="combined"
- Handles 5 diverse XML patterns:
  - Simple open BC (He, Be): single species, STO/Gaussian basis
  - Multi-atom molecule (H2): ionid attrib, Cartesian coords
  - Periodic solid (LiH): lattice, fractional coords (condition="1"), PPs, einspline
  - Optimization (He opt): loop wrapper, linear method, cost elements
  - Electron gas (HEG): no ions, rs parameter, free-particle sposet
- Two position layouts: flat (with ionid) and grouped
- Wavefunction/hamiltonian preserved as XML strings for lossless roundtrip
- Also extracts structured semantic fields (determinantset type/href, jastrow types, etc.)

**Writer** (`_write_qmcpack_text`):
- Full XML generation from params + structure
- Re-inserts preserved `_wavefunction_xml` / `_hamiltonian_xml` for roundtrip
- Handles project, simulationcell, particlesets, qmc blocks, loop, costs, estimators
- Generates `condition="1"` for fractional coords, omits for Cartesian
- Ionid attrib written when >1 species

**Wired** `custom_parser=_parse_qmcpack_text` in `get_qmcpack_input_spec()`.

### Stage 5: Output Digest — DONE

Created `src/quantumvitas/drivers/qmcpack/parsers/`:
- `__init__.py` — import trigger for `@register_parser` registration
- `output.py` — `QMCPACKDigest` (14 fields) + `QMCPACKOutputParser`
  - Registered as `("qmcpack", "scf_digest")`
  - `can_parse`: checks for `*.scalar.dat` files
  - `parse`: delegates to existing `parser.py` functions (parse_scalar_dat, parse_qmcpack_run)
  - `parse_qmcpack_stdout_text`: convenience function for inline unit testing

### Stage 6: ResourceRef Handling — DONE

`_extract_resource_refs()` in `inputspec.py`:
- Iterates XML tree for `href` attributes on `<determinantset>`, `<pseudo>`, `<include>`
- Returns `{"wavefunction_hrefs": [...], "pseudopotential_hrefs": [...], "include_hrefs": [...]}`
- Stored in `params["_resource_refs"]` when any refs found
- Tested on lih_solid_vmc_pp.xml (LiH.h5 + Li.xml + H.xml)

### Stage 7: QE→QMCPACK Workflow — DONE

Created `lih_qe_workflow` normalized case (14th case):
- **Step 1**: QE pw.x SCF (LiH Gamma-point, LDA, ecutwfc=450 Ry) — 1.5s
- **Step 2**: pw2qmcpack.x conversion (generates LiH-gamma.pwscf.h5) — 0.2s
- **Step 3**: QMCPACK VMC (einspline orbitals, batch driver) — 0.1s
- **Result**: -8.087 Ha (unoptimized Jastrow)
- **Lesson**: Batch driver rejects `walkers` tag (removed it; batch auto-manages walkers)
- Run artifacts in `.tmp/engine_research/qmcpack/runs/lih_qe_workflow/`

**Total validation runs**: 6 (5 self-contained + 1 QE workflow)

### Stage 8: Tests — DONE

**Curated samples** (`tests/inputformat/samples/qmcpack/`):
5 XML files: he_vmc_sto, h2_ae_vmc, lih_solid_vmc_pp, he_opt_pade, heg_vmc

**test_qmcpack_parse.py** (~50 tests):
- `TestPosArray` (4 tests): position array parsing
- `TestStringArray` (2 tests): string array parsing
- `TestParseHeVmcSto` (11 tests): simplest case, all fields
- `TestParseH2AeVmc` (6 tests): multi-atom molecule, random seed
- `TestParseLihSolid` (12 tests): periodic, PP, 2 QMC blocks, resource refs
- `TestParseHeOptPade` (4 tests): optimization loop, costs
- `TestParseHegVmc` (6 tests): electron gas, rs, free particle
- `TestParseMinimal` (3 tests): edge cases
- `TestWriter` (8 tests): XML generation
- `TestRoundtrip` (5 tests): parse→write→parse semantic equality
- `TestResourceRefs` (4 tests): href extraction
- `TestOrchestratorIntegration` (4 tests): end-to-end with inputformat package

**test_qmcpack_digest.py** (~15 tests):
- `TestQMCPACKDigest` (3 tests): dataclass, to_dict
- `TestParseStdoutText` (9 tests): inline stdout parsing
- `TestQMCPACKOutputParser` (5 tests): can_parse, scalar.dat, registry

### Lessons Learned (Stages 4-8)
1. **Batch driver rejects `walkers` tag**: Use auto-managed walkers or `total_walkers`
2. **Preserved XML strategy**: Storing wavefunction/hamiltonian as serialized XML strings enables lossless roundtrip without decomposing every QMCPACK wavefunction variant
3. **Ion position diversity**: QMCPACK uses both flat (with ionid) and grouped position formats; parser must handle both
4. **condition="1" means fractional**: Position attrib with condition="1" uses lattice coordinates
5. **QE→QMCPACK pipeline is fast**: LiH solid complete workflow under 2 seconds total

---

## 2026-02-07 — Playbook Compliance Audit & Remediation

### Audit Against B1_ENGINE_PLAYBOOK.md

Systematic audit identified 6 compliance gaps relative to the final playbook spec:

| Gap | Playbook Requirement | Status Before |
|-----|---------------------|---------------|
| G1 | `data/` directory with 50+ tags JSON | MISSING |
| G2 | `data/<engine>_metadata.py` access layer | MISSING |
| G3 | Parser/writer in `io/` module, not inline | MISSING (inline in inputspec.py) |
| G4 | 8+ curated samples in subdirectories with `case.yaml` | 5 flat XML files |
| G5 | `CURATED_INDEX.md` with diversity rationale | MISSING |
| G6 | `CORPUS_INDEX.json` in `.tmp/engine_research/` | Already existed |

### Fix G1: data/qmcpack_tags.json — DONE

- Created `src/quantumvitas/drivers/qmcpack/data/__init__.py`
- Created `src/quantumvitas/drivers/qmcpack/data/qmcpack_tags.json`
  - 65 tags across 11 categories: cell, control, dmc, estimator, hamiltonian, optimization, particles, project, qmc, vmc, wavefunction
  - Schema version 1, engine "qmcpack"
  - Exceeds 50-tag minimum for specialized engines

### Fix G2: data/qmcpack_metadata.py — DONE

- Created `src/quantumvitas/drivers/qmcpack/data/qmcpack_metadata.py` (261 lines)
- Full API: safe_load_metadata, reload_metadata, get_tag_info (case-insensitive), list_tags, list_categories, validate_params, get_tag_type, get_tag_default, get_metadata_file_info
- Module-level cache with optional hot-reload via `QV_QMCPACK_METADATA_HOT_RELOAD=1`
- Uses `importlib.resources`, stdlib only

### Fix G3: io/qmcpack_xml.py — DONE

- Created `src/quantumvitas/drivers/qmcpack/io/__init__.py`
- Created `src/quantumvitas/drivers/qmcpack/io/qmcpack_xml.py` (550+ lines)
  - Moved ALL parse/write functions from inputspec.py
  - Public: `parse_qmcpack_text`, `write_qmcpack_text`
  - Helpers: `_parse_pos_array`, `_parse_lattice_text`, `_parse_string_array`, `_find_ion_particleset`, `_parse_ion_particleset`, `_parse_qmc_block`, `_extract_resource_refs`
- Rewrote `inputspec.py` to 59-line wiring module (imports from io.qmcpack_xml)

### Fix G4: Curated samples restructured — DONE

- Deleted 5 flat XML files
- Created 8 subdirectories, each with `qmc_input.xml` + `case.yaml`
- 3 new cases promoted from normalized corpus: he_dmc, be_sto_vmc, lih_qe_workflow

| Case ID | Type | Boundary | Special Features |
|---------|------|----------|------------------|
| he_vmc_sto | VMC | Open | Simplest, STO basis |
| h2_ae_vmc | VMC | Open | Gaussian LCAO, J1+J2 |
| lih_solid_vmc_pp | VMC+DMC | PBC | Einspline, PPs, 2 QMC blocks |
| he_opt_pade | Opt+VMC | Open | Loop wrapper, linear method |
| heg_vmc | VMC | PBC | Electron gas, no ions |
| he_dmc | VMC+DMC | Open | DMC chain, pbyp moves |
| be_sto_vmc | VMC | Open | STO Bunge basis, sposet_collection |
| lih_qe_workflow | VMC | PBC | QE→QMCPACK composite (§1.12 W1) |

### Fix G5: CURATED_INDEX.md — DONE

- Created `docs/engines/qmcpack/CURATED_INDEX.md` (161 lines)
- Diversity rationale: 4 QMC methods, 4 wavefunction types, 3 Jastrow forms, PBC + open, 5 system types
- Parser coverage matrix: 25+ features mapped to cases
- Validation status table

### Fix G6: CORPUS_INDEX.json — Already existed

- Updated `.tmp/engine_research/qmcpack/CORPUS_INDEX.json` (9 entries, comprehensive)

### Tests Updated — DONE

- Updated `_read_sample()` to use subdirectory paths (`name / "qmc_input.xml"`)
- All call sites updated (no `.xml` extensions)
- Added 3 new parser test classes: TestParseHeDmc (6 tests), TestParseBeStoVmc (7 tests), TestParseLihQeWorkflow (7 tests)
- Added TestQMCPACKMetadata class (12 tests): load, lookup, case-insensitive, categories, validation
- **Total QMCPACK tests**: 123 (parse + digest), all passing

### Final Compliance Status: COMPLETE

All 15 Definition of Done items from B1_ENGINE_PLAYBOOK.md §Phase 8 are satisfied:

1. ✅ Full pytest green
2. ✅ Parameter metadata catalog: 65 tags (min 50)
3. ✅ Metadata access layer: all 8 functions
4. ✅ 8 curated cases, 100% parse + roundtrip
5. ✅ Writer extracted to io/qmcpack_xml.py
6. ✅ Output parser: QMCPACKDigest (14 fields)
7. ✅ Parser registered: @register_parser("qmcpack", "scf_digest")
8. ✅ Resource staging: wavefunction + pseudopotentials
9. ✅ No kernel/API changes
10. ✅ inputformat/ untouched
11. ✅ PHASE_B1_PLAN.md exists
12. ✅ PHASE_B1_WORKLOG.md complete (this file)
13. ✅ SOURCES.md exists
14. ✅ .tmp/engine_research/qmcpack/ has corpus
15. ✅ CURATED_INDEX.md exists
