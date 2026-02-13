# Analysis Objects — Spec-Aligned Design

**Date**: 2026-02-12
**Status**: Design document (normative for implementation)
**Empirical baseline**: 52 demos, 36 OK, 16 NO_ANALYSIS, 0 FAILED (post QE Composite Pipelines)

---

## 1. Spec-Aligned Definitions

These definitions are derived from the authoritative specs and govern all terminology in this document.

| Term | Definition |
|------|-----------|
| **Calculation** | An ordered sequence of GEN steps executed by one or more engines. The GEN step sequence is the calculation's identity for analysis enumeration. |
| **GEN step** | Engine-agnostic intent string (`"scf"`, `"relax"`, `"bandspw"`, `"dos"`, `"vmc"`, `"td"`). Analysis capabilities are defined over ordered GEN step sequences. `step_type_spec = prefix + "_" + gen`. |
| **AnalysisCapability** | A `(object_type, gen_step_sequence, evidence_files)` tuple declared by an engine driver. States: "this engine can produce object_type X from evidence found at the step(s) matching GEN sequence Y." |
| **Expected instance** | A single match of an AnalysisCapability pattern against a contiguous slice of the calculation's GEN step sequence. One capability can produce many expected instances in a single calculation. |
| **Parsed instance** | An expected instance where the parser successfully read evidence files and returned an AnalysisObject + CanonicalPrimitiveBundle. |
| **Missing instance** | An expected instance that was NOT parsed. Either the capability is undeclared (Category A), the parser failed on evidence (Category B), or the sweep tool didn't probe it (Category C). |

### 1.1 Enumeration Semantics (normative)

**Enumeration** is the act of computing ALL expected analysis instances for a calculation. The input is the engine's declared `ANALYSIS_CAPABILITIES` list and the calculation's ordered GEN step sequence. The output is a list of `AnalysisInstance` records.

**Core rule: ALL matches, not first match.** The same AnalysisObject type can match multiple times in a single calculation. Different AnalysisObject types can match independently. There is no "one match per object_type" limit.

**Normative example:**

Given GEN step sequence `[scf, scf, scf]` and capability `convergence → ["scf"]`:
- Match at index 0 → Convergence instance #0 covering `[0, 1)`
- Match at index 1 → Convergence instance #1 covering `[1, 2)`
- Match at index 2 → Convergence instance #2 covering `[2, 3)`
- **Result: 3 Convergence instances.**

Given GEN step sequence `[scf, nscf, bandspw, bands]` and capabilities `convergence → ["scf"]`, `bands → ["scf", "nscf", "bandspw", "bands"]`, `bands → ["bandspw"]`:
- At index 0: convergence `["scf"]` matches `[0, 1)`; bands `["scf", "nscf", "bandspw", "bands"]` matches `[0, 4)`
- At index 2: bands `["bandspw"]` matches `[2, 3)`; but bands `["scf", "nscf", "bandspw", "bands"]` does NOT match (wrong start)
- Per-start-index longest-wins for bands at index 0: `[0, 4)` wins over nothing else at that index
- Per-start-index longest-wins for bands at index 2: `[2, 3)` is the only candidate
- **But** indices 0 and 2 are different start indices, so BOTH bands matches survive
- **Result: 1 Convergence `[0,1)`, 2 Bands `[0,4)` and `[2,3)`**

### 1.2 Algorithm: `enumerate_expected_instances()`

```
Input:
  capabilities : list[AnalysisCapability]   — from driver.ANALYSIS_CAPABILITIES
  gen_steps    : list[str]                  — ordered GEN step names of the calculation
                                              (e.g., ["scf", "nscf", "dos"])

Output:
  list[AnalysisInstance]

Algorithm:

  instances = []

  for start_idx in range(len(gen_steps)):

      # 1. Collect all capabilities whose pattern matches starting at start_idx
      matches_at_start = []
      for cap_idx, cap in enumerate(capabilities):
          pat = cap.gen_step_sequence
          end_idx = start_idx + len(pat)
          if end_idx > len(gen_steps):
              continue
          if gen_steps[start_idx : end_idx] == pat:
              matches_at_start.append( (cap.object_type, start_idx, end_idx, cap_idx) )

      # 2. Group by object_type; within each group keep only the longest span.
      #    Tie-break on span length: lower cap_idx (declaration order) wins.
      best_per_type = {}
      for (otype, s, e, cidx) in matches_at_start:
          span_len = e - s
          prev = best_per_type.get(otype)
          if prev is None:
              best_per_type[otype] = (otype, s, e, cidx, span_len)
          else:
              _, _, _, prev_cidx, prev_len = prev
              if span_len > prev_len or (span_len == prev_len and cidx < prev_cidx):
                  best_per_type[otype] = (otype, s, e, cidx, span_len)

      # 3. Emit one AnalysisInstance per surviving match at this start_idx
      for (otype, s, e, cidx, _) in best_per_type.values():
          instances.append( AnalysisInstance(
              object_type = otype,
              span        = (s, e),            # half-open [start, end)
              gen_steps   = gen_steps[s : e],   # matched GEN step names
          ))

  # 4. Assign ordinals: per object_type, number instances 0, 1, 2, ...
  #    ordered by span start index (stable — start indices are unique per type
  #    because step 2 keeps at most one match per type per start index).
  from collections import Counter
  ordinal_counter = Counter()
  instances.sort(key=lambda inst: (inst.object_type, inst.span[0]))
  for inst in instances:
      inst.ordinal = ordinal_counter[inst.object_type]
      ordinal_counter[inst.object_type] += 1

  return instances
```

**Key properties:**

- **Per-start-index longest-wins**: If two capabilities of the SAME object_type both match starting at the same index, only the longer span survives. This prevents double-counting at a single step.
- **No cross-index collapse**: Matches at different start indices are NEVER collapsed, even if they overlap. A capability matching at index 0 and another at index 2 are independent instances.
- **Different types are independent**: Convergence matching at index 0 and Bands matching at index 0 coexist — the longest-wins rule applies only within the same object_type at the same start index.
- **Declaration order breaks ties**: Among same-length patterns of the same type at the same start, the capability declared earlier in `ANALYSIS_CAPABILITIES` wins.

### 1.3 AnalysisInstance Record

Each enumerated instance carries:

| Field | Type | Description |
|-------|------|-------------|
| `object_type` | str | e.g., `"convergence"`, `"bands"`, `"spectrum"` |
| `span` | (int, int) | Half-open `[start, end)` indices into the GEN step sequence |
| `gen_steps` | list[str] | The matched GEN step names (slice of the calculation's sequence) |
| `ordinal` | int | 0-based index within this object_type for this calculation |

**Critical framing**: Analysis is not boolean ("has analysis" / "no analysis"). Every calculation has an expected set of analysis instances derived mechanically from its GEN step sequence crossed with the engine's declared capabilities. The gap between expected and parsed is the actionable delta.

---

## 2. Sources of Truth

| Document | Path | Authority | Key content |
|----------|------|-----------|-------------|
| **AnalysisObject Primitives Spec** | `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` | BINDING v1.4 | 14 invariants (Inv-A1–A14), data model, post-run pipeline, capability matching |
| **Analysis Objects Framework** | `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md` | Proposed v1.1 | Two-layer philosophy, system boundaries, domain objects |
| **Analysis Pipeline Playbook** | `docs/architecture/ANALYSIS_PIPELINE_PLAYBOOK.md` | Implementation guide | Recipe A (extend engine), Recipe B (add object type), triangle pattern |
| **Analysis Pipeline Review** | `docs/architecture/ANALYSIS_PIPELINE_REVIEW.md` | Review (2026-02-10) | Spec compliance matrix (13/14 PASS), engine×analysis capability matrix |
| **Step Type GEN/SPEC Constitution** | `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | Final v1.1 | GEN/SPEC derivation rule, GenStepRegistry as SSOT |
| **Driver capabilities** | `src/quantumvitas/drivers/*/driver.py` | Code (SSOT) | `ANALYSIS_CAPABILITIES` list per engine — the ONLY source for what analysis an engine can produce |

### 2.1 Current Code vs This Design

The current orchestrator (`src/quantumvitas/core/analysis/orchestrator.py`) and matching function (`src/quantumvitas/core/analysis/capability.py`) implement **first-match-per-type** semantics: one result per `object_type`, longest sequence wins globally, `find_contiguous_match()` returns the first sliding-window hit. This is a **spec violation** relative to the all-matches semantics defined in §1.1–1.2 above. The implementation must be updated to match this design before the enumeration semantics are correct.

---

## 3. Root Cause Taxonomy

Every missing analysis instance falls into exactly one of three categories:

### Category A — Expected capability not declared

The engine COULD produce this analysis (it has the data in its output), but no `AnalysisCapability` entry exists in the driver's `ANALYSIS_CAPABILITIES` list for the relevant `gen_step_sequence`. The orchestrator never even attempts a match.

**Fix**: Add the missing `AnalysisCapability` to the driver + create/wire the parser.

### Category B — Capability declared, parsing failed

An `AnalysisCapability` entry exists, the enumeration produces an expected instance, but either:
- (B1) `can_parse()` returns False — evidence files not present in `raw/`
- (B2) `parse()` raises an exception — evidence exists but parser can't handle it

**Fix**: For B1, ensure the demo's engine run produces the expected evidence files (may need input parameter changes). For B2, fix the parser.

### Category C — Sweep instrumentation incomplete

The demo sweep tool (`generate_ref_packs_realrun.py`) uses a hardcoded `ENGINE_ANALYSIS_TYPES` dict to decide which analysis types to probe. This is a **second truth** that diverges from the driver's `ANALYSIS_CAPABILITIES`. Types not listed in `ENGINE_ANALYSIS_TYPES` are never probed, even if the orchestrator would successfully produce them.

**Fix**: Eliminate `ENGINE_ANALYSIS_TYPES` as an independent list. Derive the probe list from the driver's `ANALYSIS_CAPABILITIES` at runtime.

---

## 4. Current Capability Matrix

### 4.1 Declared ANALYSIS_CAPABILITIES by Engine

Extracted from each engine's `driver.py`. This is the ONLY truth for what analysis the orchestrator can dispatch.

| Engine | Capabilities (object_type → gen_step_sequences) |
|--------|------------------------------------------------|
| **QE** | convergence→[scf], [relax], [md]; bands→[bandspw]; dos→[dos]; trajectory→[relax], [md]; neb_trajectory→[neb]; field3d→[scf] |
| **VASP** | convergence→[scf], [relax], [md]; bands→[bandspw]; dos→[dos]; trajectory→[relax], [md]; field3d→[scf] |
| **ABINIT** | convergence→[scf], [relax]; bands→[nscf]; dos→[nscf]; trajectory→[relax], [md]; field3d→[scf] |
| **CP2K** | convergence→[scf], [relax]; bands→[bandspw]; dos→[dos]; trajectory→[relax], [md]; field3d→[scf] |
| **Siesta** | convergence→[scf], [relax]; bands→[bands]; dos→[dos]; trajectory→[relax], [md]; field3d→[scf] |
| **GPAW** | bands→[bandspw]; dos→[dos]; trajectory→[relax], [md]; field3d→[scf] |
| **LAMMPS** | trajectory→[md], [minimize] |
| **xTB** | trajectory→[relax], [md] |
| **ORCA** | trajectory→[relax]; field3d→[scf] |
| **Gaussian** | trajectory→[relax]; field3d→[scf] |
| **Psi4** | trajectory→[relax]; field3d→[scf] |
| **PySCF** | trajectory→[relax]; field3d→[scf] |
| **W90** | field3d→[wannier] |
| **QMCPACK** | **(none)** |
| **Yambo** | **(none)** |

### 4.2 ENGINE_ANALYSIS_TYPES (the second truth — to be eliminated)

From `tools/demo_store/generate_ref_packs_realrun.py` lines 57–75. This dict controls what the sweep tool probes — it is NOT derived from `ANALYSIS_CAPABILITIES` and has diverged:

| Engine | Probe list | Missing vs ANALYSIS_CAPABILITIES |
|--------|-----------|----------------------------------|
| GPAW | bands, dos, trajectory | **Missing: field3d** (declared in driver) |
| ORCA | trajectory | **Missing: field3d** (declared in driver) |
| Gaussian | trajectory | **Missing: field3d** (declared in driver) |
| Psi4 | trajectory | **Missing: field3d** (declared in driver) |
| PySCF | trajectory | **Missing: field3d** (declared in driver) |
| W90 | field3d | Correct |
| QMCPACK | [] | Correct (no capabilities) |
| Yambo | [] | Correct (no capabilities) |
| QE, VASP, ABINIT, CP2K, Siesta | convergence, bands, dos, trajectory | **Missing: field3d** (declared in all) |

**Conclusion**: `ENGINE_ANALYSIS_TYPES` omits `field3d` for 10 engines that declare it. This is a systematic instrumentation gap, but field3d would also fail at B1 (no cube files produced by default SCF runs).

---

## 5. Motivating Evidence: 16 NO_ANALYSIS Demos

The demo sweep (52 demos, post QE Composite Pipelines) found 16 demos that produced zero analysis instances. This section diagnoses each case using the enumeration semantics from §1 and the root cause taxonomy from §3.

### 5.1 Per-Demo Diagnosis

For each demo: GEN step sequence, expected capability matches (under current declarations), what the sweep probed, and root cause category.

#### Gaussian (2 NO_ANALYSIS + 1 OK for reference)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `gaussian_water_hf` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | No convergence cap for scf; field3d not probed; field3d would also be B1 (no .cube) |
| `gaussian_formaldehyde_tddft` | [td] | (none) | trajectory | 0 | **A** | No capability matches gen="td"; needs spectrum(td) |
| `gaussian_water_opt` | [relax] | trajectory(relax) | trajectory | 1 | — | OK: trajectory matched and parsed |

**Missing capabilities**: convergence for [scf]; spectrum for [td].

#### ORCA (3 NO_ANALYSIS)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `orca_water_sp` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | No convergence cap for scf; field3d not probed + B1 |
| `orca_methane_freq` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | Same as above |
| `orca_formaldehyde_tddft` | [scf, td] | field3d(scf) | trajectory | 0 | **A+C** | No convergence for scf; no spectrum for td; field3d not probed + B1 |

**Missing capabilities**: convergence for [scf]; spectrum for [td].

Note on `orca_formaldehyde_tddft`: under the all-matches enumeration (§1.1), a correctly wired ORCA driver would produce **2 instances**: convergence at `[0,1)` for the scf step, and spectrum at `[1,2)` for the td step.

#### GPAW (3 NO_ANALYSIS)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `gpaw_al_scf` | [scf] | field3d(scf) | bands, dos, trajectory | 0 | **A+C** | No convergence cap; field3d not probed + B1 |
| `gpaw_si_scf` | [scf] | field3d(scf) | bands, dos, trajectory | 0 | **A+C** | Same |
| `gpaw_si_bands` | [bandspw] | bands(bandspw) | bands, dos, trajectory | 0 | **B1** | bands cap matches, but parser can't find bandstructure.json evidence |

**Missing capabilities**: convergence for [scf]. GPAW bands evidence issue for gpaw_si_bands.

#### Psi4 (3 NO_ANALYSIS)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `psi4_water_scf` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | No convergence cap; field3d not probed + B1 |
| `psi4_ethanol_sp` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | Same |
| `psi4_h2o_opt` | [relax] | trajectory(relax) | trajectory | 0 | **B1** | trajectory cap matches, but parser can't find *.dat evidence |

**Missing capabilities**: convergence for [scf]. Psi4 trajectory evidence issue for psi4_h2o_opt.

#### PySCF (3 NO_ANALYSIS)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `pyscf_water_scf` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | No convergence cap; field3d not probed + B1 |
| `pyscf_h2o_dft` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | Same |
| `pyscf_n2_mp2` | [scf] | field3d(scf) | trajectory | 0 | **A+C** | Same |

**Missing capabilities**: convergence for [scf].

#### QMCPACK (2 NO_ANALYSIS)

| Demo | GEN sequence | Expected matches | Probed | Parsed | Category | Root cause |
|------|-------------|-----------------|--------|--------|----------|------------|
| `qmcpack_he_vmc` | [vmc] | (none) | (none) | 0 | **A** | No ANALYSIS_CAPABILITIES declared at all |
| `qmcpack_h2_vmc` | [vmc] | (none) | (none) | 0 | **A** | Same |

**Missing capabilities**: entire ANALYSIS_CAPABILITIES list. Need convergence and/or qmc_sample for [vmc].

### 5.2 Global Summary

| Category | Demo count | Root cause | Fix |
|----------|:---------:|-----------|-----|
| **A** (sole or primary) | 14 | Capability not declared for the demo's GEN step | Add capability + parser |
| **B1** (sole) | 2 | Capability matches but evidence files missing | Fix evidence production or parser evidence_files glob |
| **C** (contributing) | 12 | Sweep tool didn't probe the type | Eliminate ENGINE_ANALYSIS_TYPES; derive from capabilities |

Note: 12 demos have both A and C. The A is the primary cause (no convergence capability), the C is secondary (field3d not probed, but would also fail as B1).

### 5.3 The 2 Category-B Demos (detail)

**`gpaw_si_bands`**: GPAW declares `bands` capability for gen_step_sequence `["bandspw"]`. The demo's GEN sequence is `["bandspw"]`. The capability matches. But the GPAW bands parser looks for `bandstructure.json` evidence, which the GPAW script-based runner may not produce in the expected location. Investigation needed: does the demo run actually produce `bandstructure.json`?

**`psi4_h2o_opt`**: Psi4 declares `trajectory` capability for gen_step_sequence `["relax"]`. The demo's GEN sequence is `["relax"]`. The capability matches. But the Psi4 trajectory parser looks for `*.dat` evidence, which the Psi4 script-based runner may not produce. Investigation needed: what trajectory evidence does Psi4's `geometric` optimizer actually write?

---

## 6. Type Taxonomy — Merged Top-Level Set

### 6.1 Current types (6)

`convergence`, `bands`, `dos`, `trajectory`, `field3d`, `neb_trajectory`

### 6.2 Proposed types (9 total = 6 existing + 3 new)

| # | object_type | New? | Description | Merge absorbs |
|---|-------------|:----:|-------------|---------------|
| 1 | **convergence** | Exists | SCF + ionic step energy/force convergence series | — |
| 2 | **bands** | Exists | E(k) eigenvalues along k-path | phonon_bands (via `meta.kind="phonon"`), GW bands (via `meta.kind="gw"`) |
| 3 | **dos** | Exists | Density of states g(E) | phonon_dos (via `meta.kind="phonon"`) |
| 4 | **trajectory** | Exists | Multi-frame geometry snapshots | NEB path (via `meta.kind="neb"`), scan (via `meta.kind="scan"`), MD (via `meta.kind="md"`) |
| 5 | **field3d** | Exists | 3D volumetric grid data | — |
| 6 | **spectrum** | **New** | 1D spectral data: optical absorption, TDDFT excitations, IR, Raman, EELS, GW spectral function | Absorbs: excitations, optical_spectrum, ir_spectrum, raman_spectrum, eels |
| 7 | **scalar_report** | **New** | Structured scalar properties: thermochemistry, molecular properties (dipole, charges), elastic moduli, dielectric tensor | Absorbs: thermochemistry, molecular_properties, elastic_tensor, dielectric_properties, wannier_summary |
| 8 | **qmc_sample** | **New** | QMC block-averaged energy statistics: mean, error, variance, correlation time, acceptance ratio | Absorbs: qmc_statistics |
| 9 | **gw_correction** | **New** | Quasiparticle corrections table: per-k-point per-band DFT→QP energy mapping | — |

**Total: 9 types (6 existing + 3 new).** Within the 8±2 target.

### 6.3 Open Question: Further Merges

Some of the 9 proposed types may merit further consolidation. Specifically:

**`gw_correction` → `scalar_report`?** GW corrections are a per-band per-k-point table `(E_DFT, E_QP, Z_factor)`. Arguments for merging into `scalar_report`: it is structured scalar data, not a 1D/2D array in the bands/dos sense. Arguments against: the correction table has a natural 2D structure (k-points × bands) and specific render needs (scatter plot of corrections, Z-factor heatmap) that differ from the "bag of labeled numbers" pattern of scalar_report. Additionally, corrected eigenvalues can be plotted as quasiparticle band structures, which may argue for `bands(meta.kind="gw")` instead.

**`qmc_sample` → `convergence`?** QMC block-averaged energy could be viewed as a convergence series. Arguments against: QMC statistics carry unique fields (variance, error bars per block, correlation time, acceptance ratio, reblocking) that have no analog in deterministic SCF convergence. The statistical vs deterministic distinction is fundamental to how the data is rendered and interpreted.

**Decision criteria**: A merge is justified when (a) the data shapes are structurally identical, (b) the `to_primitives()` output uses the same primitive types, and (c) the renderer can handle both sub-kinds with only a `meta.kind` switch. If any of these fail, keep the types separate. This evaluation should be done at implementation time with concrete data model prototypes, not pre-decided here.

### 6.4 Merge Rules

| Absorbed concept | Merged into | Discriminator field |
|-----------------|------------|-------------------|
| `neb_trajectory` | `trajectory` | `meta.kind = "neb"` |
| `phonon_bands` | `bands` | `meta.kind = "phonon"` (units THz instead of eV) |
| `phonon_dos` | `dos` | `meta.kind = "phonon"` |
| `optical_spectrum` | `spectrum` | `meta.kind = "optical"` |
| TDDFT `excitations` | `spectrum` | `meta.kind = "excitation"` (discrete peaks + envelope) |
| IR spectrum | `spectrum` | `meta.kind = "ir"` |
| Raman spectrum | `spectrum` | `meta.kind = "raman"` |
| `thermochemistry` | `scalar_report` | `meta.kind = "thermochemistry"` |
| `molecular_properties` | `scalar_report` | `meta.kind = "molecular_properties"` |
| `elastic_tensor` | `scalar_report` | `meta.kind = "elastic"` |
| `dielectric_properties` | `scalar_report` | `meta.kind = "dielectric"` |
| `wannier_summary` | `scalar_report` | `meta.kind = "wannier_summary"` |
| `md_statistics` | `scalar_report` | `meta.kind = "md_statistics"` |

### 6.5 Why These Merges Work

**Bands absorbs phonon_bands**: Both are dispersion relations along a k/q-path. The `BandStructure` model already has `series: list[Series1D]`, high-symmetry markers, and a reference energy. Phonon bands just use THz units and have 3N branches. The `meta.kind` field tells the renderer which unit convention to use.

**DOS absorbs phonon_dos**: Same argument. The `DOS` model is `(energy_axis, density_values, optional PDOS)`. Phonon DOS is `(frequency_axis, density_values, optional atom-projected)`.

**Trajectory absorbs NEB**: NEB images are geometry frames along a reaction coordinate. The existing `Trajectory` model handles this — `neb_trajectory` is already implemented as `Trajectory(type="neb")` in the QE parser.

**Spectrum is the universal 1D peak/envelope container**: Optical absorption, TDDFT excitations, IR/Raman spectra, and EELS all share the same primitive structure: `(x_axis, y_axis, peak_positions, peak_labels)`. They differ in units and physics but not in data shape. A single `Spectrum` type with `meta.kind` avoids 5+ nearly-identical domain objects.

**Scalar_report is the catch-all for structured scalars**: Thermochemistry, molecular properties, elastic constants, dielectric tensors — these are all "a bag of labeled numbers." They don't have the array structure of bands/dos/trajectory. A single `scalar_report` with typed sections avoids 5+ single-engine domain objects.

---

## 7. Action Plan — Resolving the 16 NO_ANALYSIS Demos

### 7.1 Action 1: Add convergence capability for 6 engines (resolves 10 demos)

**Engines**: ORCA, Gaussian, Psi4, PySCF, GPAW, QMCPACK

For each engine:
1. Create `drivers/<engine>/parsers/convergence.py` implementing `parse(evidence: EvidenceBundle) -> Convergence`
2. Register via `@register_parser("<engine>", "convergence")`
3. Add `AnalysisCapability(object_type="convergence", gen_step_sequence=[...], evidence_files=[...])` to driver.py

Data sources per engine (most already in Digest parsers):

| Engine | Evidence file | Data available | GEN steps to declare |
|--------|-------------|---------------|---------------------|
| ORCA | `*.out` | `final_energy_eV`, `converged_scf`, `n_scf_cycles` from ORCADigest | `["scf"]` |
| Gaussian | `*.log` | `final_energy_eV`, `converged_scf`, `n_scf_cycles` from GaussianDigest | `["scf"]` |
| Psi4 | `results.json` | energy, converged from results dict | `["scf"]` |
| PySCF | `results.json` | energy, converged from results dict | `["scf"]` |
| GPAW | `results.json` | energy from results dict | `["scf"]` |
| QMCPACK | `*.scalar.dat` | block-averaged energy from existing `parse_scalar_dat()` | `["vmc"]`, `["dmc"]` |

**Demos resolved by this action alone**: gaussian_water_hf, orca_water_sp, orca_methane_freq, psi4_water_scf, psi4_ethanol_sp, pyscf_water_scf, pyscf_h2o_dft, pyscf_n2_mp2, gpaw_al_scf, gpaw_si_scf (10 demos)

**Important**: Convergence is for gen steps where iterative electronic convergence occurs (scf, relax, md, vmc, dmc). It is NOT for gen steps like `"td"`, `"bandspw"`, `"dos"`, or `"freq"` — those produce different analysis object types (spectrum, bands, dos, etc. respectively).

### 7.2 Action 2: Fix Category-B evidence issues (resolves 2 demos)

**`gpaw_si_bands`**: Investigate what evidence files GPAW's bandstructure calculation produces. Fix either the parser's evidence_files glob or the demo's input parameters to ensure evidence is written.

**`psi4_h2o_opt`**: Investigate what evidence files Psi4's geometry optimizer produces. Fix either the parser's evidence_files glob or ensure the optimizer writes trajectory data.

**Demos resolved**: gpaw_si_bands, psi4_h2o_opt (2 demos)

### 7.3 Action 3: Add spectrum capability for gen="td" (resolves 2 demos)

The TDDFT demos (`gaussian_formaldehyde_tddft`, `orca_formaldehyde_tddft`) have gen steps involving `"td"`. The `"td"` step produces excited-state energies and oscillator strengths — this is spectral data, not convergence data.

**Design**: Map `td → spectrum`, NOT `td → convergence`.

- Convergence tracks iterative progress toward a self-consistent solution. The `"td"` gen step is NOT an iterative solver in the same sense — it is a post-SCF response calculation that produces discrete excitation energies and oscillator strengths.
- The correct analysis for `"td"` is `spectrum(meta.kind="excitation")`: a set of excited states with energies (eV), wavelengths (nm), and oscillator strengths.

**Implementation per engine:**

| Engine | Evidence file | Data available | Capability to add |
|--------|-------------|---------------|-------------------|
| Gaussian | `*.log` | GaussianDigest already has `tddft_states: [{energy_eV, wavelength_nm, oscillator_strength}]` | `spectrum → ["td"]` |
| ORCA | `*.out` | TDDFT section with excited state energies and oscillator strengths | `spectrum → ["td"]` |

**For `orca_formaldehyde_tddft`** (GEN: [scf, td]): under the all-matches enumeration, the expected instances are:
- convergence at `[0,1)` for the scf step (from Action 1)
- spectrum at `[1,2)` for the td step (from this action)

**For `gaussian_formaldehyde_tddft`** (GEN: [td]): the expected instance is:
- spectrum at `[0,1)` for the td step

**Prerequisite**: The `spectrum` domain object (§6.2 type #6) must be created first. This can be a minimal initial implementation: `Spectrum` with `meta.kind="excitation"`, a list of peaks `(energy_eV, oscillator_strength)`, and a `to_primitives()` that produces `Series1D` for the stick spectrum.

**Demos resolved**: gaussian_formaldehyde_tddft, orca_formaldehyde_tddft (2 demos)

### 7.4 Action 4: Eliminate ENGINE_ANALYSIS_TYPES second truth

Replace the hardcoded `ENGINE_ANALYSIS_TYPES` dict in `generate_ref_packs_realrun.py` with a dynamic derivation:

```python
def _get_engine_analysis_types(engine: str) -> list[str]:
    """Derive probe list from driver's ANALYSIS_CAPABILITIES."""
    import quantumvitas.drivers
    from quantumvitas.core.driver_registry import DriverRegistry
    driver = DriverRegistry.get_driver(engine)
    capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []
    # Unique object_types in declaration order
    seen = set()
    types = []
    for cap in capabilities:
        ot = cap.object_type.lower()
        if ot not in seen:
            seen.add(ot)
            types.append(ot)
    return types
```

This ensures the sweep tool always probes exactly what the driver declares. No manual sync needed.

### 7.5 Action 5: Update orchestrator to all-matches semantics

The current `run_post_run_analysis()` in `orchestrator.py` implements first-match-per-type. It must be updated to implement the `enumerate_expected_instances()` algorithm from §1.2, producing ALL matches across all start indices.

This is a prerequisite for correct analysis enumeration in multi-step calculations (e.g., scf→scf→scf producing 3 convergence instances, or scf→td producing convergence + spectrum).

### 7.6 Summary: All 16 Resolved

| Action | Demos resolved | Effort |
|--------|:-------------:|--------|
| 1: convergence for 6 engines | 10 | ~2 days (thin wrappers over existing Digest data) |
| 2: Fix evidence for GPAW bands + Psi4 trajectory | 2 | ~0.5 day (investigation + fix) |
| 3: spectrum for gen="td" (requires new Spectrum domain object) | 2 | ~1.5 days (new domain object + 2 parsers) |
| 4: Eliminate ENGINE_ANALYSIS_TYPES | 0 (instrumentation) | ~0.5 day |
| 5: Update orchestrator to all-matches | 0 (correctness) | ~0.5 day |
| **Total** | **14 + 2** | **~5 days** |

Note: QMCPACK demos (qmcpack_he_vmc, qmcpack_h2_vmc) are resolved by Action 1 via convergence for `["vmc"]`. These are counted in Action 1's 10 demos.

---

## 8. Beyond the 16: New Type Buildout Roadmap

After closing the 16 NO_ANALYSIS gaps, the next priorities for new types:

### Priority 1 — Engine primary outputs

| Type | Engines | Why | Prerequisite |
|------|---------|-----|-------------|
| `qmc_sample` | QMCPACK | This IS QMC's primary output. Block energy stats with error bars. QMCPACK's `parse_scalar_dat()` already exists. | Action 1 (convergence) done first |
| `spectrum` (excitations) | ORCA, Gaussian | 2 TDDFT demos exist. GaussianDigest already has `tddft_states`. | Action 3 creates the Spectrum type |
| `gw_correction` | Yambo | Primary Yambo output. YamboDigest already has `qp_gap_eV`, `dft_gap_eV`. | New domain object + parser |

### Priority 2 — Common analysis types

| Type | Engines | Why |
|------|---------|-----|
| `scalar_report` (thermochemistry) | ORCA, Gaussian, xTB | Molecular QC users need ZPE, Gibbs, entropy |
| `scalar_report` (molecular_properties) | ORCA, Gaussian, Psi4, PySCF, xTB | Dipole, charges, HOMO-LUMO |
| `spectrum` (IR/Raman) | ORCA, Gaussian, xTB | Common characterization |
| `scalar_report` (wannier_summary) | W90 | Spreads, centers — primary W90 quality metric |
| `bands` (phonon) | QE, ABINIT, CP2K | Lattice dynamics (common for periodic) |
| `dos` (phonon) | QE, ABINIT, CP2K | Vibrational DOS |

### Priority 3 — Advanced properties

| Type | Engines | Why |
|------|---------|-----|
| `scalar_report` (elastic) | VASP, QE, ABINIT | Mechanical screening |
| `scalar_report` (dielectric) | QE, ABINIT | DFPT properties |
| `spectrum` (optical) | Yambo, VASP, ABINIT | BSE/optics |
| `scalar_report` (md_statistics) | LAMMPS, CP2K, VASP | MD thermo time series |

---

## 9. Acceptance Criteria

### For closing the 16 NO_ANALYSIS gaps:

- [ ] All 52 demos produce ≥1 parsed analysis instance (0 NO_ANALYSIS)
- [ ] Convergence parser registered + ANALYSIS_CAPABILITIES declared for: ORCA, Gaussian, Psi4, PySCF, GPAW, QMCPACK
- [ ] Convergence capability covers gen steps: scf (all 6 new engines), vmc/dmc (QMCPACK)
- [ ] Spectrum domain object created; spectrum parser wired for Gaussian td and ORCA td
- [ ] GPAW bands evidence issue resolved (gpaw_si_bands produces bands bundle)
- [ ] Psi4 trajectory evidence issue resolved (psi4_h2o_opt produces trajectory bundle)
- [ ] `ENGINE_ANALYSIS_TYPES` dict in `generate_ref_packs_realrun.py` replaced with dynamic derivation from `ANALYSIS_CAPABILITIES`
- [ ] Orchestrator updated to all-matches enumeration (§1.2 algorithm)
- [ ] Full demo sweep: 52 demos, ≥52 OK, 0 NO_ANALYSIS, 0 FAILED
- [ ] pytest green: ≥5459 passed, 0 failed

### For the merged type taxonomy:

- [ ] `neb_trajectory` merged into `trajectory` with `meta.kind="neb"` (or documented as planned)
- [ ] No new type added without checking if it fits an existing type + `meta.kind` discriminator
- [ ] `spectrum`, `scalar_report`, `qmc_sample`, `gw_correction` types created only when implementation starts
- [ ] Open-question merges (§6.3) evaluated at implementation time with concrete prototypes

### For this document:

- [x] Document does not contain "first match" or "one match per object_type" semantics
- [x] Document explicitly states "ALL matches" and gives scf-scf-scf → 3 convergence as a normative example
- [x] Document does not suggest or imply "td produces Convergence"; td maps to spectrum
- [x] Algorithmic definition of `enumerate_expected_instances()` is unambiguous and implementable
- [x] No mention of "fallback/baseline analysis"
- [x] No mention of "ENGINE_ANALYSIS_TYPES as probe truth"
- [x] No boolean "has analysis" framing — uses expected/parsed/missing instances
- [x] Sources of Truth section cites spec doc paths
- [x] Type count within 8±2 range (9 types)
- [x] Framed as a design document, not a review
