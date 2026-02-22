# Parameter System Audit & Fix Proposal

**Date**: 2026-02-20
**Trigger**: Mn metal band structure demo exposed three parameter-handling bugs
**Scope**: All 15 engines, step_defaults, presets, search_parameters, set_parameters, preflight

---

## 1. Executive Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 1 | Preset occupations_scheme excludes `bandspw` — metallic band calculations get wrong occupations |
| Medium | 1 | `search_parameters` returns namelist as `category` with no structural context — agents guess wrong sections |
| Low | 2 | Minor metadata gaps: no `section` field in response, no set_parameters validation |
| Info | 3 | Validation opportunities (warn-not-block), documentation gaps |

**Good news**: `diago_full_acc` is correctly placed in ELECTRONS at `step_defaults.py:105`. The original demo failure was caused by the agent misinterpreting `search_parameters` output, not by a step_defaults bug.

---

## 2. Bug Fixes (Critical)

### 2.1 CRITICAL: `bandspw` missing from `occupations_scheme` gen_type_steps

**File**: `src/qmatsuite/presets/variants_registry.py:49-54`

**Current code**:
```python
OCCUPATIONS_SCHEME_VARIANT = ParamSpaceVariant(
    name="OCCUPATIONS_SCHEME_PW",
    dimension="occupations_scheme",
    space=OCCUPATIONS_SCHEME_SPACE,
    applies_to_step_types=frozenset({
        "scf", "nscf", "relax", "md",
        # Note: bandspw excluded (uses kpath, not occupations)
    }),
)
```

**Problem**: The comment "uses kpath, not occupations" conflates K_POINTS (k-path) with SYSTEM.occupations (electronic filling). These are orthogonal concerns. `bandspw` runs `pw.x` with the exact same parameter space as SCF. When the SCF is run with `occupations=smearing` for metals:
- `bandspw` must also use `occupations=smearing` for consistent Fermi level
- Without smearing, QE may use `occupations=fixed` (the pw.x default), causing incorrect band occupations and potentially SCF convergence failure in metals
- This is exactly what failed in the Mn demo: SCF got smearing via preset, bandspw did not

**Evidence from step_defaults.py**: Lines 107-111 already include `occupations`, `smearing`, and `degauss` in bandspw defaults — confirming these parameters are valid and expected for bandspw.

**Fix** (line 49):
```python
applies_to_step_types=frozenset({
    "scf", "nscf", "bandspw", "relax", "md",
}),
```

Remove the incorrect comment. Add:
```python
# All pw.x step types share the same parameter space.
# bandspw needs occupations/smearing for consistent Fermi level with SCF.
```

---

## 3. Preset Scope Fixes

### 3.1 Coverage matrix (current state)

Source: `src/qmatsuite/presets/variants_registry.py:42-115`

| Dimension | scf | nscf | bandspw | relax | md | Comment |
|-----------|-----|------|---------|-------|----|---------|
| occupations_scheme (line 49) | Y | Y | **N** | Y | Y | **BUG**: bandspw excluded |
| magnetism (line 62) | Y | Y | Y | Y | Y | OK |
| precision (default, line 74) | Y | — | — | Y | Y | OK (scf/relax/md variant) |
| precision (nscf, line 85) | — | Y | — | — | — | OK (nscf variant with 2x k-mesh) |
| precision (bandspw, line 93) | — | — | Y | — | — | OK (no K_POINTS in bandspw variant) |
| convergence (line 102) | Y | Y | Y | Y | Y | OK |
| qc_precision (line 114) | Y | — | — | — | — | OK (QC only) |

### 3.2 Proposed fix

Add `"bandspw"` to occupations_scheme (line 49). No other changes needed.

**Rationale for NOT adding other step types**:
- Post-processing steps (`dos`, `bands`, `pdos`, `ph`, etc.) use different executables with different parameter spaces — presets correctly exclude them
- `neb`, `custom`, `gipaw` have specialized parameter spaces — correct to exclude

### 3.3 Why the comment was wrong

The comment "bandspw excluded (uses kpath, not occupations)" reveals a conceptual confusion. In QE:
- **K_POINTS** controls spatial sampling (k-path for bands, mesh for SCF)
- **SYSTEM.occupations** controls electronic filling (smearing for metals, fixed for insulators)

These are independent. A bandspw calculation uses a k-path for K_POINTS AND needs `occupations=smearing` for metals. The precision preset already handles this correctly — it has a separate PRECISION_PW_BANDSPW variant (line 88) that includes ecutwfc/ecutrho/conv_thr but NOT K_POINTS. The occupations preset should follow the same logic: include bandspw because `occupations` is valid for bandspw, even though K_POINTS is handled differently.

---

## 4. Parameter Metadata Gaps

### 4.1 QE: namelist info EXISTS but is poorly surfaced

**Source JSON**: `src/qmatsuite/data/qe_module_parameters.json` (schema v3)

Each QE parameter has an explicit `namelist` field:
```json
"&ELECTRONS.diago_full_acc": {
    "namelist": "&ELECTRONS",
    "name": "diago_full_acc",
    "type": "LOGICAL",
    "default": ".FALSE.",
    "description": "..."
}
```

**Access layer**: `src/qmatsuite/drivers/qe/data/qe_metadata.py:306-378`
- `_iter_params()` returns dicts with `{"module", "namelist", "name", "type", "default", "description"}`
- The `namelist` field is stripped of `&` prefix (line 364): `"ELECTRONS"` not `"&ELECTRONS"`

**Search index**: `src/qmatsuite/mcp/search_index.py:138-145`
```python
docs.append(TagDoc(
    engine="qe",
    tag_name=p.get("name", ""),
    category=p.get("namelist", ""),  # ← namelist stored as "category"!
    ...
))
```

The namelist IS available as `category`, but:
1. The field is named `category`, not `namelist` or `section`
2. For QE, `category="ELECTRONS"` means "nest under ELECTRONS namelist"
3. For VASP, `category="electronic"` means "semantic category, not a section"
4. The agent cannot distinguish structural meaning from semantic meaning

### 4.2 Per-engine metadata status

| Engine | Metadata File | Param Count | Has Section Field | Section Type |
|--------|--------------|-------------|-------------------|-------------|
| QE | `data/qe_module_parameters.json` | ~292 | YES (`namelist`) | Fortran namelist |
| VASP | `drivers/vasp/data/vasp_incar_tags.json` | 238 | NO | N/A (flat INCAR) |
| ABINIT | `drivers/abinit/data/abinit_tags.json` | ~249 | NO | N/A (flat input) |
| CP2K | `drivers/cp2k/data/cp2k_tags.json` | 215 | YES (`section`) | Nested section |
| W90 | `drivers/w90/data/w90_tags.json` | ~140 | NO | N/A (flat input) |
| ORCA | `drivers/orca/data/orca_keywords.json` | ~136 | NO (blocks separate) | `%block` |
| Gaussian | `drivers/gaussian/data/gaussian_route_keywords.json` | 130 | NO | Route line / Link0 |
| LAMMPS | `drivers/lammps/data/lammps_commands.json` | 114 | NO | Command stream |
| xTB | `drivers/xtb/data/xtb_tags.json` | ~82 | NO | Flat input |
| Yambo | `drivers/yambo/data/yambo_tags.json` | ~73 | NO | N/A |
| QMCPACK | `drivers/qmcpack/data/qmcpack_tags.json` | ~65 | NO | XML elements |
| Siesta | — | 0 | — | — |
| GPAW | — | 0 | — | Python script |
| Psi4 | — | 0 | — | Python script |
| PySCF | — | 0 | — | Python script |

**Total indexed parameters**: ~1,744 across 11 engines

### 4.3 Key observations

1. **Only QE and CP2K** have section/namelist info in metadata
2. **VASP doesn't need sections** — all INCAR tags are flat key=value (no nesting)
3. **ORCA/Gaussian** — keyword vs block distinction exists in metadata (`keywords` vs `blocks` dicts) but is not surfaced in search results
4. **ABINIT** — flat input file, no section structure needed
5. **3 Python engines** (GPAW, Psi4, PySCF) — no external metadata; params are Python dicts

---

## 5. Validation Opportunities

### 5.1 `set_parameters` — no validation at all

**File**: `src/qmatsuite/mcp/tools/set_parameters.py:59-70`

Currently: top-level keys are classified as `parameters` vs `cards` (QE card auto-routing, line 67), then passed through to `update_step_params()` with **no type checking, no section validation, no engine-specific rules**.

**Opportunity**: Add a soft validation layer (warning, not blocking):

```python
# After classifying params, before applying:
if engine == "qe":
    _warn_qe_section_mismatch(params_dict, step_type_gen)
```

This would check QE parameters against the module metadata to warn when a parameter is in the wrong namelist. Example: if `diago_full_acc` appears under `SYSTEM`, emit a warning suggesting `ELECTRONS`.

**Cost/benefit**: Medium cost (need to load QE metadata, map step_type to module). High benefit (prevents the exact class of bug that caused the Mn demo failure).

**Constraint**: Must be warn-only. Our metadata is ~99% accurate but not 100%. A false positive that blocks a legitimate calculation is worse than no validation.

### 5.2 `inspect_calculation` preflight — already validates some things

**File**: `src/qmatsuite/mcp/tools/inspect_calculation.py:106-111`

The QE preflight checker (`drivers/qe/preflight.py`) validates 20 rules across 3 severity levels. It checks parameter VALUES (ecutwfc range, conv_thr, smearing consistency) but does **not** check parameter SECTIONS (whether a param is in the right namelist).

**Opportunity**: Add a preflight rule like:

```python
# P1: PARAM_WRONG_SECTION
# For each parameter in each namelist, check if QE metadata says it belongs elsewhere
for nl_name in ("CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL"):
    for param_name in step_params.get(nl_name, {}):
        correct_nl = _lookup_namelist(param_name, module="pw")
        if correct_nl and correct_nl != nl_name:
            issues.append(PreflightIssue(
                code="PARAM_WRONG_SECTION",
                severity="warning",
                message=f"'{param_name}' is in {nl_name} but QE expects it in {correct_nl}.",
                parameter=f"{nl_name}.{param_name}",
                suggestion=f"Move to {correct_nl}: set_parameters(..., params={{'{correct_nl}': {{'{param_name}': ...}}}})",
            ))
```

**Cost/benefit**: Low cost (QE metadata already has namelist info). Very high benefit (catches the exact bug class at dry_run time, before the calculation runs).

### 5.3 Input file writer — silent pass-through

**File**: `src/qmatsuite/drivers/qe/inputspec.py:95-107`

The QE writer iterates over known namelists in order (`CONTROL`, `SYSTEM`, `ELECTRONS`, `IONS`, `CELL`) and writes whatever parameters are in each. It does **not** check whether a parameter belongs in that namelist. A parameter in the wrong namelist will produce a syntactically valid but semantically incorrect input file.

QE's pw.x will either:
- Silently ignore it (if the namelist parser doesn't recognize it) — **silent wrong results**
- Crash with `STOP 1` (if it's an explicitly rejected key) — **what happened with diago_full_acc in SYSTEM**

**Recommendation**: Do NOT add validation in the writer. The writer should be fast and deterministic. Validation belongs in preflight (section 5.2 above).

---

## 6. `search_parameters` Enhancement

### 6.1 Current response format

**File**: `src/qmatsuite/mcp/tools/search_parameters.py:36-43`

```python
results_out.append({
    "engine": doc.engine,
    "tag_name": doc.tag_name,
    "type": doc.type,
    "default": doc.default,
    "category": doc.category,       # QE: "ELECTRONS", VASP: "electronic"
    "description": doc.description[:200],
    "relevance_score": round(score, 3),
})
```

### 6.2 Problem

The `category` field is overloaded:
- For QE: `"ELECTRONS"` means "this parameter goes in the &ELECTRONS namelist"
- For VASP: `"electronic"` means "this is an electronic structure parameter" (all go in INCAR)
- For ORCA: `"methods"` means "this is a method keyword" (goes on `!` line)

The agent sees `category: "ELECTRONS"` for QE's `diago_full_acc` but cannot distinguish this from a semantic label. It doesn't know this means `{"ELECTRONS": {"diago_full_acc": true}}`.

### 6.3 Proposed fix

**File**: `src/qmatsuite/mcp/search_index.py`

**Step 1**: Add a `section` field to `TagDoc`:

```python
class TagDoc:
    __slots__ = ("engine", "tag_name", "type", "default", "category",
                 "description", "section", "tokens")

    def __init__(self, ..., section: str | None = None):
        ...
        self.section = section or ""
```

**Step 2**: Populate `section` from metadata:

For QE (line 138-145):
```python
docs.append(TagDoc(
    engine="qe",
    tag_name=p.get("name", ""),
    type_=p.get("type"),
    default=p.get("default"),
    category=p.get("namelist", ""),
    section=p.get("namelist", ""),   # ← NEW: explicit section
    description=p.get("description"),
))
```

For CP2K (in the standard tags loop):
```python
section=info.get("section", ""),    # ← CP2K has section field
```

For all others: `section=""` (no section structure).

**Step 3**: Return `section` in search results:

**File**: `src/qmatsuite/mcp/tools/search_parameters.py:36-43`

```python
results_out.append({
    "engine": doc.engine,
    "tag_name": doc.tag_name,
    "type": doc.type,
    "default": doc.default,
    "category": doc.category,
    "section": doc.section,          # ← NEW
    "description": doc.description[:200],
    "relevance_score": round(score, 3),
})
```

**Step 4**: Add `usage_hint` to context_hint:

```python
context_hint=(
    "Use these parameters with set_parameters(calc_ulid, params=...). "
    "For QE, nest parameters under their namelist section "
    "(e.g. {\"ELECTRONS\": {\"diago_full_acc\": true}}). "
    "The 'section' field shows the correct nesting."
),
```

**Estimated effort**: ~30 minutes, ~20 lines changed across 2 files.

---

## 7. Per-Engine Status Matrix

| Engine | Has Metadata | Param Count | Has Section Info | Has Input Writer | Has Preflight | Has Output Parser | Search Indexed |
|--------|-------------|-------------|-----------------|-----------------|---------------|-------------------|----------------|
| QE | Yes | ~292 | Yes (namelist) | Yes (inputspec.py) | Yes (20 rules) | Yes | Yes |
| VASP | Yes | 238 | No (flat) | Yes (inputspec.py) | No | Yes (vasprun.xml) | Yes |
| ABINIT | Yes | ~249 | No (flat) | Yes (inputspec.py) | No | Yes (.abo regex) | Yes |
| CP2K | Yes | 215 | Yes (section) | Yes (inputspec.py) | No | Yes | Yes |
| ORCA | Yes | ~136 | Partial (blocks) | Yes (inputspec.py) | No | Yes | Yes |
| Gaussian | Yes | 130 | No | Yes (inputspec.py) | No | Yes | Yes |
| LAMMPS | Yes | 114 | No | Yes (inputspec.py) | No | Yes | Yes |
| W90 | Yes | ~140 | No | Yes (inputspec.py) | No | No | Yes |
| xTB | Yes | ~82 | No | Yes (inputspec.py) | No | No | Yes |
| Yambo | Yes | ~73 | No | Yes (inputspec.py) | No | No | Yes |
| QMCPACK | Yes | ~65 | No | Yes (inputspec.py) | No | Yes | Yes |
| Siesta | No | 0 | — | Yes (inputspec.py) | No | No | No |
| GPAW | No | 0 | — | Yes (inputspec.py) | No | No | No |
| Psi4 | No | 0 | — | Yes (inputspec.py) | No | No | No |
| PySCF | No | 0 | — | Yes (inputspec.py) | No | No | No |

---

## 8. Step Type to Executable Cross-Reference

### 8.1 QE: the only multi-executable engine

**File**: `src/qmatsuite/drivers/qe/step_types.py:6-127`

| Step Type | Gen Type | Executable | Parameter Space | Preset-Eligible |
|-----------|----------|-----------|----------------|-----------------|
| qe_scf | scf | pw.x | INPUT_PW | Yes (all 4) |
| qe_nscf | nscf | pw.x | INPUT_PW | Yes (all 4) |
| qe_bandspw | bandspw | pw.x | INPUT_PW | Yes (3 of 4)* |
| qe_relax | relax | pw.x | INPUT_PW | Yes (all 4) |
| qe_md | md | pw.x | INPUT_PW | Yes (all 4) |
| qe_bands | bands | bands.x | INPUT_BANDS | No |
| qe_dos | dos | dos.x | INPUT_DOS | No |
| qe_pdos | projwfc | projwfc.x | INPUT_PROJWFC | No |
| qe_ph | ph | ph.x | INPUT_PH | No |
| qe_pp | pp | pp.x | INPUT_PP | No |
| qe_hp | hp | hp.x | INPUT_HP | No |
| qe_gipaw | gipaw | gipaw.x | INPUT_GIPAW | No |
| qe_q2r | q2r | q2r.x | INPUT_Q2R | No |
| qe_matdyn | matdyn | matdyn.x | INPUT_MATDYN | No |
| qe_dynmat | dynmat | dynmat.x | INPUT_DYNMAT | No |
| qe_plotband | plotband | plotband.x | INPUT_PLOTBAND | No |
| qe_pw2wannier | pw2wannier | pw2wannier90.x | INPUT_PW2WANNIER | No |
| qe_pw2qmcpack | pw2qmcpack | pw2qmcpack.x | INPUT_PW2QMCPACK | No |
| qe_neb | neb | neb.x | INPUT_NEB | No |
| qe_custom | custom | pw.x | INPUT_PW | No |

*`bandspw` currently gets 3 of 4 presets. With the fix in section 2.1, it will get all 4.

### 8.2 All other engines: single executable

| Engine | Executable | All Step Types Share Param Space |
|--------|-----------|-------------------------------|
| VASP | vasp_std | Yes |
| ORCA | orca | Yes |
| ABINIT | abinit | Yes |
| CP2K | cp2k.psmp | Yes |
| Gaussian | g16 | Yes (multi-job via Link1) |
| LAMMPS | lmp | Yes |
| Siesta | siesta | Yes |
| W90 | wannier90.x | Yes |
| xTB | xtb | Yes |
| GPAW | python (script) | Yes |
| Psi4 | python (script) | Yes |
| PySCF | python (script) | Yes |
| QMCPACK | qmcpack | Yes |
| Yambo | yambo | Yes |

**Key insight**: Parameter section validation is primarily a QE concern because QE is the only engine where:
1. Multiple executables have different parameter spaces
2. Parameters must be in specific Fortran namelists (CONTROL/SYSTEM/ELECTRONS/IONS/CELL)

VASP has one flat INCAR. ABINIT has one flat input. ORCA has `!` keywords + `%` blocks (but blocks are syntactically distinct). CP2K has nested sections but the writer handles section hierarchy.

---

## 9. Detailed File References

### 9.1 step_defaults.py — All parameters verified correct

**File**: `src/qmatsuite/calculation/step_defaults.py:14-200`

| Step Type | Lines | CONTROL | SYSTEM | ELECTRONS | IONS | Verified |
|-----------|-------|---------|--------|-----------|------|----------|
| qe_scf | 15-39 | calculation, outdir, restart_mode | ecutwfc, occupations, smearing, degauss | conv_thr | — | All correct |
| qe_nscf | 40-64 | calculation, outdir, restart_mode | ecutwfc, occupations, smearing, degauss | conv_thr | — | All correct |
| qe_dos | 65-75 | — | — | — | — | Uses DOS module params (correct) |
| qe_bands | 76-95 | calculation, outdir, restart_mode | ecutwfc | conv_thr | — | All correct |
| qe_bandspw | 96-119 | calculation, outdir, restart_mode | ecutwfc, occupations, smearing, degauss | conv_thr, **diago_full_acc** | — | All correct (line 105) |
| qe_relax | 120-150 | calculation, outdir, restart_mode | ecutwfc, occupations, smearing, degauss | conv_thr | ion_dynamics | All correct |
| qe_md | 152-179 | calculation, outdir, restart_mode | ecutwfc, occupations, smearing, degauss | conv_thr | ion_dynamics | All correct |

**Confirmed**: `diago_full_acc` is at line 105 in `ELECTRONS` — the correct namelist. No parameters are in wrong sections.

### 9.2 QE namelist assignments (ground truth)

From `src/qmatsuite/data/qe_module_parameters.json` (schema v3, pw module):

| Namelist | Key Parameters (non-exhaustive) |
|----------|-------------------------------|
| CONTROL | calculation, restart_mode, prefix, pseudo_dir, outdir, tprnfor, tstress, etot_conv_thr, forc_conv_thr, nstep, dt, disk_io, verbosity |
| SYSTEM | ibrav, nat, ntyp, ecutwfc, ecutrho, occupations, smearing, degauss, nbnd, nspin, noncolin, lspinorb, input_dft, lda_plus_u, Hubbard_U, vdw_corr, nosym, starting_magnetization |
| ELECTRONS | electron_maxstep, conv_thr, mixing_beta, mixing_mode, **diago_full_acc**, diagonalization, startingpot, startingwfc, mixing_ndim |
| IONS | ion_dynamics, upscale, trust_radius_ini, trust_radius_min, trust_radius_max, tempw, ion_temperature |
| CELL | cell_dynamics, press, press_conv_thr, cell_dofree |

---

## 10. Recommended Implementation Order

### Priority 1: Fix occupations_scheme scope (Critical, ~5 min)
- **File**: `src/qmatsuite/presets/variants_registry.py:49`
- Add `"bandspw"` to `applies_to_step_types`
- Update comment
- Run preset regression tests

### Priority 2: Add `section` field to search_parameters (Medium, ~30 min)
- **Files**: `src/qmatsuite/mcp/search_index.py`, `src/qmatsuite/mcp/tools/search_parameters.py`
- Add `section` slot to `TagDoc`, populate from QE `namelist` and CP2K `section`
- Return in search results
- Update context_hint with QE nesting guidance

### Priority 3: Add PARAM_WRONG_SECTION preflight rule (Medium, ~1 hour)
- **File**: `src/qmatsuite/drivers/qe/preflight.py`
- Load QE metadata, build param→namelist lookup
- For each parameter in each namelist, check if metadata says it belongs elsewhere
- Emit `severity="warning"` PreflightIssue with corrective suggestion
- Only for QE pw.x steps (already gated by `_PW_X_GEN_STEPS` in inspect_calculation.py:11)

### Priority 4: Add soft validation to set_parameters (Low, ~1 hour)
- **File**: `src/qmatsuite/mcp/tools/set_parameters.py`
- After parameter classification (line 70), if engine is QE:
  - Load module metadata for the step's module
  - For each parameter, check if it's in the right namelist
  - Add `warnings` list to response (not blocking)
- Low priority because preflight (Priority 3) already catches this at inspect time

### Not recommended:
- **Writer-level validation**: The writer should remain a dumb serializer. Validation in the writer would slow materialization and could block legitimate edge cases.
- **Architectural changes to metadata schema**: Adding section fields to all 11 engines' JSON files is high effort, low benefit (only QE and CP2K have meaningful section structure).
- **Automatic parameter relocation**: Silently moving a parameter to the "correct" section violates SSOT and would be confusing. Better to warn and let the user/agent fix it explicitly.

---

## Appendix A: How the Mn Demo Bug Actually Happened

1. Agent called `search_parameters(query="diago_full_acc", engine="qe")`
2. Got back: `{"tag_name": "diago_full_acc", "category": "ELECTRONS", ...}`
3. Agent misinterpreted `category: "ELECTRONS"` as a semantic label (not a section)
4. Agent called `set_parameters(params={"SYSTEM": {"diago_full_acc": true}})` — wrong section
5. QE input writer put `diago_full_acc = .true.` inside `&SYSTEM` namelist
6. `pw.x` crashed with `STOP 1` (unrecognized variable in &SYSTEM)
7. Agent debugged, discovered the error, and manually moved to ELECTRONS — 4 extra tool calls

**Root causes**:
- (a) `search_parameters` doesn't clearly indicate which section a parameter belongs to
- (b) `set_parameters` doesn't validate section placement
- (c) `bandspw` didn't get `occupations=smearing` from preset (separate but compounding issue)

With fixes 1-3 above: (a) agent sees `section: "ELECTRONS"` and knows where to put it; (b) if agent still gets it wrong, preflight warns; (c) bandspw gets correct occupations from preset.

## Appendix B: QE Preflight Checker Current Rules

**File**: `src/qmatsuite/drivers/qe/preflight.py:50-350`

| Code | Severity | What It Checks |
|------|----------|---------------|
| MISSING_ECUTWFC | blocking | ecutwfc missing or non-positive |
| MISSING_KPOINTS | blocking | No k-points for periodic structure |
| INVALID_CALCULATION_TYPE | blocking | calculation not in valid set |
| NSCF_WITHOUT_SCF | blocking | nscf/bands step without preceding scf |
| NEGATIVE_DEGAUSS | blocking | degauss < 0 |
| ZERO_NAT | blocking | nat explicitly set to 0 |
| METAL_FIXED_OCC | advisory | Fixed occupations with metallic elements |
| SPIN_UNPOLARIZED_MAGNETIC | warning | nspin=1 with magnetic elements |
| TETRAHEDRA_WITH_RELAX | warning | Tetrahedra with relax/md |
| TETRAHEDRA_METALS | warning | Tetrahedra with metals |
| SMEARING_NO_DEGAUSS | warning | smearing without degauss |
| ECUTRHO_TOO_LOW | warning | ecutrho < 4*ecutwfc |
| VC_RELAX_FIXED_CELL | advisory | vc-relax with constrained cell |
| MD_NO_TEMPERATURE | warning | MD without temperature |
| LOW_ECUTWFC | advisory | ecutwfc < 20 Ry |
| LOOSE_CONV_THR | advisory | conv_thr > 1e-4 |
| LOW_ELECTRON_MAXSTEP | advisory | electron_maxstep < 30 |
| GAUSSIAN_SMEARING_FOR_DOS | advisory | Gaussian smearing with DOS workflow |
| LARGE_MIXING_BETA | advisory | mixing_beta > 0.7 |
| ECUTWFC_VERY_HIGH | advisory | ecutwfc > 200 Ry |

**Proposed addition**: `PARAM_WRONG_SECTION` (warning) — would be rule #21.

---

## 11. Deep-Dive: Preset Compilation Flow for bandspw

### 11.1 Complete code path trace

When the agent calls `apply_preset(calc_ulid, presets={"occupations_scheme": "SMEARING_GAUSSIAN", "precision": "MED"})`:

```
MCP apply_preset.py:10
  → svc.calculation.apply_presets(calc_ulid, normalized)

api/service.py:4769
  → iterates over step files in the calculation

presets/integration.py:469-479  (for each step file)
  → doc = StepDoc.load(step_path)
  → step_type_spec = doc.get(["step_type_spec"])   # e.g. "qe_bandspw"
  → step_type_gen = gen_from(step_type_spec)        # e.g. "bandspw"

presets/integration.py:496-500  (for each dimension in options)
  → variant = get_variant(dimension, step_type_gen)
  → if variant is None: continue   ← THIS IS WHERE bandspw GETS SKIPPED

presets/variants_registry.py:308-333  (get_variant)
  → key = (step_type_gen, dimension)
  → return VARIANT_BY_STEP_AND_DIMENSION.get(key)
  → lookup: ("bandspw", "occupations_scheme") → None  ← NOT IN REGISTRY
```

The skip happens at `integration.py:499-500`: `get_variant()` returns `None` because `OCCUPATIONS_SCHEME_VARIANT.applies_to_step_types` doesn't include `"bandspw"`. The `if variant is None: continue` silently skips the dimension for this step. No error, no warning — just silently omitted.

### 11.2 Two-phase compilation

The integration module splits dimensions into two phases (`integration.py:526-533`):

| Phase | Dimensions | Why |
|-------|-----------|-----|
| Phase 1 (prerequisite) | occupations_scheme, magnetism | Set values that Phase 2 reads |
| Phase 2 (dependent) | precision, convergence | Oracle reads Phase 1 state |

Phase 1 patches are applied to `step_yaml` at lines 583-597 **before** Phase 2 runs. This ensures the Oracle (which reads `step_yaml`) can see the occupations value set by Phase 1 when evaluating Phase 2 decisions.

Critical flow for `degauss`:
1. Phase 1: occupations_scheme sets `SYSTEM.occupations = "smearing"` → applied to step_yaml
2. Phase 2: precision calls `oracle.degauss_applicability()` → reads `SYSTEM.occupations` from step_yaml → returns `True`
3. Phase 2: precision writes `SYSTEM.degauss = 0.02` (for MED)

If Phase 1 is skipped (current bug for bandspw), the Oracle reads whatever is in the step defaults. Since `step_defaults.py:109` has `"occupations": "smearing"`, the Oracle would still return `True` for degauss — **but only because the defaults happen to include smearing**. If the agent had reset occupations to "fixed" via `set_parameters`, degauss applicability would be wrong.

### 11.3 Parameter ownership analysis — ZERO overlap

| Parameter | Owned By | Evidence |
|-----------|----------|---------|
| `SYSTEM.occupations` | occupations_scheme | `paramspace.py:707-708` — key_occupations |
| `SYSTEM.smearing` | occupations_scheme | `paramspace.py:728-734` — key_smearing |
| `SYSTEM.ecutwfc` | precision | `precision_variants.py` — cutoff computation |
| `SYSTEM.ecutrho` | precision | `precision_variants.py` — cutoff computation |
| `SYSTEM.degauss` | precision | `paramspace.py:710` — "degauss owned by Precision per Constitution 10.8.6" |
| `ELECTRONS.conv_thr` | precision | `variants_registry.py:500-502` |
| `cards.K_POINTS` | precision | `variants_registry.py:524-545` (only for default/nscf variants, NOT bandspw) |
| `SYSTEM.nspin` | magnetism | `paramspace.py:778-867` |
| `ELECTRONS.mixing_beta` | convergence | `paramspace.py:1108-1204` |

**occupations_scheme** touches: `SYSTEM.occupations`, `SYSTEM.smearing` (2 params)
**PRECISION_PW_BANDSPW** touches: `SYSTEM.ecutwfc`, `SYSTEM.ecutrho`, `ELECTRONS.conv_thr`, conditionally `SYSTEM.degauss` (3-4 params)

**ZERO overlap**. Adding `"bandspw"` to occupations_scheme cannot conflict with precision_bandspw because they own completely disjoint sets of keys.

### 11.4 Why adding bandspw to occupations_scheme is safe

1. **No parameter conflicts**: Zero key overlap (proven above)
2. **Phase ordering preserved**: occupations_scheme runs in Phase 1, precision in Phase 2 — the Oracle dependency is maintained
3. **step_defaults already expect it**: `step_defaults.py:109-111` includes `occupations`, `smearing`, `degauss` for bandspw — the preset is just setting what the defaults already declare
4. **Magnetism already includes bandspw**: `MAGNETISM_VARIANT` at line 63 includes `"bandspw"` — this proves the pattern of "all pw.x steps should be in the same scope" is already followed by other dimensions

### 11.5 Why bandspw was excluded — and why the reasoning was wrong

The comment at `variants_registry.py:51` says: `"bandspw excluded (uses kpath, not occupations)"`.

This conflates two orthogonal concerns:
- **K_POINTS format** (k-path vs k-mesh) — controlled by precision variant, which has a separate `PRECISION_PW_BANDSPW` variant that deliberately excludes K_POINTS
- **SYSTEM.occupations** (smearing vs fixed) — independent of K_POINTS, must match SCF settings for consistent Fermi level

The precision system correctly handles this by having a separate bandspw variant without K_POINTS. The occupations system should follow the same pattern: include bandspw because occupations is valid for bandspw.

---

## 12. ORCA Block Info in search_parameters

### 12.1 ORCA metadata structure

**File**: `drivers/orca/data/orca_keywords.json`

ORCA metadata has two separate top-level dictionaries:

```json
{
  "keywords": {
    "B3LYP":  {"type": "flag", "category": "methods", ...},
    "def2-SVP": {"type": "flag", "category": "basis_sets", ...},
    "TightSCF": {"type": "flag", "category": "scf", ...}
  },
  "blocks": {
    "scf":    {"type": "block", "category": "scf", ...},
    "pal":    {"type": "block", "category": "parallel", ...},
    "cpcm":   {"type": "block", "category": "solvation", ...}
  }
}
```

### 12.2 How the ORCA writer distinguishes `!` line vs `%block`

**File**: `drivers/orca/inputspec.py`

The writer auto-routes by role:
- Top-level keys matching known keyword names → `!` line (space-separated)
- Top-level keys matching known block names → `%blockname ... end`
- `method`, `basis`, `extra_keywords` → merged onto `!` line

The agent using `set_parameters` passes a flat dict. The writer handles routing. There is no "wrong section" problem for ORCA because there's only one input file.

### 12.3 What a useful `section` field would look like for ORCA

For ORCA, `section` should indicate **syntax target** (how the parameter appears in the input file):

| Metadata Source | `section` Value | Meaning |
|----------------|----------------|---------|
| `keywords` dict | `"keyword_line"` | Goes on `!` line |
| `blocks` dict | `"block:scf"` or `"block:pal"` | Goes in `%scf ... end` block |

This helps the agent construct correct `set_parameters` calls:
- `section: "keyword_line"` → `params={"extra_keywords": ["TightSCF"]}`
- `section: "block:scf"` → `params={"scf": {"MaxIter": 200}}`

### 12.4 Implementation cost

**Low** — but lower priority than QE. The ORCA writer is tolerant of flat params and auto-routes correctly. The main benefit is agent guidance, not error prevention.

The search index (`search_index.py:152-168`) already indexes ORCA keywords and blocks separately. Adding `section` requires:
- Distinguishing `keywords` vs `blocks` source in the indexer loop
- Setting `section="keyword_line"` or `section="block:<name>"` accordingly

---

## 13. set_parameters Response Enhancement for Wrong-Section

### 13.1 Current response format

**File**: `src/qmatsuite/mcp/tools/set_parameters.py:80-100`

```python
return make_response({
    "calc_ulid": calc_ulid,
    "step_ulid": step_ulid,
    "updated_keys": updated_keys,
    "engine": engine,
}, context_hint="...")
```

No warnings, no validation, no suggestions. The tool is a pure pass-through.

### 13.2 Where to add validation

After parameter classification (line 70) and before the `update_step_params()` call:

```python
# After line 70 (parameter classification):
validation_warnings = []
if engine == "qe":
    validation_warnings = _validate_qe_sections(params_dict, step_type_gen)

# Include in response:
response = {
    "calc_ulid": calc_ulid,
    "step_ulid": step_ulid,
    "updated_keys": updated_keys,
    "engine": engine,
}
if validation_warnings:
    response["validation_warnings"] = validation_warnings
```

### 13.3 What `validation_warnings` should look like

```python
{
    "validation_warnings": [
        {
            "code": "PARAM_WRONG_SECTION",
            "severity": "warning",
            "parameter": "diago_full_acc",
            "current_section": "SYSTEM",
            "expected_section": "ELECTRONS",
            "message": "'diago_full_acc' is in SYSTEM but QE expects it in ELECTRONS.",
            "suggested_fix": {
                "tool": "set_parameters",
                "params": {
                    "SYSTEM": {"diago_full_acc": null},
                    "ELECTRONS": {"diago_full_acc": true}
                }
            }
        }
    ]
}
```

Key design decisions:
1. **Non-blocking**: The `set_parameters` call succeeds — the warning is informational
2. **Structured `suggested_fix`**: The agent can directly use the `params` dict in a follow-up `set_parameters` call to fix the issue
3. **`null` to delete**: The fix removes the wrong-section entry and adds the correct-section entry
4. **Only for QE pw.x steps**: Other engines don't have this problem (flat params or auto-routing)

### 13.4 Implementation notes

The validation function needs to:
1. Load QE metadata via `qe_metadata.py:_iter_params()` (cached)
2. Build a `param_name → expected_namelist` lookup for the step's module (pw, dos, bands, etc.)
3. For each parameter in each namelist in `params_dict`, check against the lookup
4. Only warn for parameters that exist in the lookup and are in the wrong section — unknown parameters should pass through silently (the agent may be using newer QE features not in our metadata)

### 13.5 Relationship to preflight

This overlaps with the proposed `PARAM_WRONG_SECTION` preflight rule (section 5.2). Both are valuable:
- `set_parameters` validation: catches the error at **write time** (earliest possible)
- Preflight validation: catches the error at **inspect time** (catches manual YAML edits too)
- Neither blocks — both are advisory

Implementing both gives defense-in-depth, but if only one is chosen, **preflight is higher value** because it catches all sources of section errors (set_parameters, manual YAML edits, GUI edits), not just MCP tool calls.

---

## 14. CP2K Section Validation

### 14.1 How CP2K handles nesting

**File**: `drivers/cp2k/io/cp2k_input.py`

CP2K uses a nested `&SECTION ... &END SECTION` input format. The writer handles nesting recursively:

```python
def _write_section(name, data, indent=0):
    lines.append(f"{'  ' * indent}&{name}")
    for key, val in data.items():
        if isinstance(val, dict):
            _write_section(key, val, indent + 1)  # Recurse for nested sections
        else:
            lines.append(f"{'  ' * (indent + 1)}{key}  {val}")
    lines.append(f"{'  ' * indent}&END {name}")
```

The user passes a flat/nested dict to `set_parameters`, and the writer auto-nests. Example:

```python
# User passes:
params = {"FORCE_EVAL": {"DFT": {"XC": {"XC_FUNCTIONAL": {"_SECTION_PARAMETERS_": "PBE"}}}}}
# Writer produces:
# &FORCE_EVAL
#   &DFT
#     &XC
#       &XC_FUNCTIONAL PBE
#       &END XC_FUNCTIONAL
#     &END XC
#   &END DFT
# &END FORCE_EVAL
```

### 14.2 Is section validation worth doing for CP2K?

**No, low priority.**

Reasons:
1. **Auto-nesting prevents most errors**: The writer recursively handles section hierarchy. If you put a key in the wrong section, it will appear in a `&WRONG_SECTION ... &END` block — CP2K's parser will reject it with a clear error message
2. **CP2K has 300+ sections**: Building a complete section→parameter mapping is a large effort (CP2K's manual is 1000+ pages)
3. **CP2K tags already have `section` field**: `cp2k_tags.json` has 215 tags with section info. This is already surfaced in search results via the `category` field. The agent can see which section a parameter belongs to.
4. **No silent wrong results**: Unlike QE (where a parameter in the wrong namelist may be silently ignored), CP2K's parser explicitly rejects unknown keywords in a section

**Recommendation**: Low priority. The existing CP2K `section` field in metadata is sufficient. If implemented, it would follow the same pattern as QE but with section hierarchy awareness.

---

## 15. Cutoffs Loading Fix and Presets

### 15.1 Two separate cutoff paths

There are two independent code paths for SSSP cutoffs:

| Path | Source | Used By | Fixed By |
|------|--------|---------|----------|
| **Path A**: PSEUDO_FILE_INDEX.json | Vendored JSON in `resources/pseudo/` | Preset compilation (PrecisionAdvisor) | N/A (always worked) |
| **Path B**: SSSP cutoffs JSON | Downloaded with SSSP library | Local pseudo resolution (pseudo_config.py) | Recent dict-vs-list fix at pseudo_config.py:538-544 |

### 15.2 Path A: Preset compilation (UNAFFECTED by the fix)

```
PSEUDO_FILE_INDEX.json
  → aggregate_cutoffs(element_list) → {ecutwfc: max, ecutrho: max}
  → PrecisionAdvisor.advise() → precision_context
  → _compile_precision_patch_for_step() at variants_registry.py:464-470
  → base_ecutwfc * policy.cutoff_multiplier → final ecutwfc
```

`PSEUDO_FILE_INDEX.json` is a vendored file at `resources/pseudo/PSEUDO_FILE_INDEX.json`. It is NOT the SSSP library's cutoffs JSON. It is a pre-built index mapping elements to their recommended cutoffs.

The `aggregate_cutoffs()` function (in `pseudo/resolution_utils.py`) reads from this vendored index and returns the maximum ecutwfc/ecutrho across all elements in the structure. If an element is missing, it falls back to 50.0 Ry / 400.0 Ry.

**This path was never broken and is unaffected by the pseudo_config.py fix.**

### 15.3 Path B: Local pseudo resolution (FIXED)

```
SSSP cutoffs JSON (in installed library dir)
  → pseudo_config.py:resolve_project_pseudos()
  → cutoffs_data is a dict: {"Ac": {...}, "Ag": {...}, ...}
  → OLD code: isinstance(cutoffs_data, list) → always False → cutoffs = []
  → NEW code: isinstance(cutoffs_data, dict) → iterate items → populate cutoffs
```

**Bug**: The SSSP cutoffs JSON is a dict keyed by element, but the parser used `isinstance(cutoffs_data, list)` which always evaluated to `False` for dicts. Cutoffs were **never loaded** from the SSSP library.

**Impact on presets**: NONE. The presets use Path A (PSEUDO_FILE_INDEX.json), not Path B. Path B is only used by the local pseudo resolution flow (for determining recommended cutoffs when staging pseudopotentials to a project).

### 15.4 After the fix, do preset values change?

**No.** Preset cutoff values are determined entirely by:
1. `PSEUDO_FILE_INDEX.json` (vendored, unchanged)
2. `PrecisionPolicy.cutoff_multiplier` (LOW=0.8, MED=1.0, HIGH=1.2)
3. `round_cutoff_integer()` (rounds to nearest 5 Ry)

None of these inputs are affected by the pseudo_config.py fix. Preset compilation produces identical results before and after the fix.

---

## 16. Comprehensive gen_type_steps Review — ALL Preset Dimensions

### 16.1 Complete coverage matrix

Source: `variants_registry.py:42-115`

pw.x gen_type steps (from `qe/step_types.py`): `scf`, `nscf`, `bandspw`, `relax`, `md`, `custom`

| Dimension | Variant Name | scf | nscf | bandspw | relax | md | custom | Comment |
|-----------|-------------|-----|------|---------|-------|----|--------|---------|
| occupations_scheme | OCCUPATIONS_SCHEME_PW (line 45) | Y | Y | **N** | Y | Y | N | **BUG: bandspw missing** |
| magnetism | MAGNETISM_PW (line 58) | Y | Y | Y | Y | Y | N | OK |
| precision | PRECISION_PW_DEFAULT (line 70) | Y | — | — | Y | Y | N | OK (scf/relax/md variant) |
| precision | PRECISION_PW_NSCF (line 81) | — | Y | — | — | — | N | OK (nscf-specific: 2x k-mesh) |
| precision | PRECISION_PW_BANDSPW (line 88) | — | — | Y | — | — | N | OK (bandspw-specific: no K_POINTS) |
| convergence | CONVERGENCE_PW (line 98) | Y | Y | Y | Y | Y | N | OK |
| qc_precision | QC_PRECISION_SCF (line 110) | Y | — | — | — | — | N | OK (QC engines only) |

### 16.2 Findings

**Only occupations_scheme is missing bandspw.** All other dimensions have correct coverage:

1. **magnetism**: Includes all 5 pw.x steps (scf, nscf, bandspw, relax, md). Correct — nspin/noncolin/lspinorb must be consistent across all pw.x runs.

2. **precision**: Three separate variants correctly handle different k-point needs:
   - Default (scf/relax/md): includes K_POINTS auto-mesh
   - NSCF: includes K_POINTS with 2x multiplier
   - bandspw: NO K_POINTS (k-path is set separately via `generate_kpath`)
   All three include ecutwfc/ecutrho/conv_thr. Correct.

3. **convergence**: Includes all 5 pw.x steps. Correct — mixing parameters and diagonalization settings apply to all pw.x runs.

4. **qc_precision**: Only applies to `"scf"`. Correct — this is for quantum chemistry (molecular) engines, not periodic QE.

### 16.3 Should `custom` be included in any dimension?

`custom` is a special gen_type that maps to pw.x but is intended for advanced users who set all parameters manually. Including it in preset dimensions would make presets partially overwrite custom configurations. **Recommendation: keep custom excluded from all dimensions.** Users who choose `custom` are opting out of the preset system.

### 16.4 The single required fix

Add `"bandspw"` to `OCCUPATIONS_SCHEME_VARIANT.applies_to_step_types` at `variants_registry.py:49`:

```python
applies_to_step_types=frozenset({
    "scf", "nscf", "bandspw", "relax", "md",
    # All pw.x step types share the same parameter space.
    # bandspw needs occupations/smearing for consistent Fermi level with SCF.
    # custom excluded: users opting for custom set all parameters manually.
}),
```

This is the only code change needed for correct preset scope. No other dimensions have missing step types.

---

## 10. Recommended Implementation Order (Updated)

### Priority 1: Fix occupations_scheme scope (Critical, ~5 min)
- **File**: `src/qmatsuite/presets/variants_registry.py:49`
- Add `"bandspw"` to `applies_to_step_types`
- Update comment (remove incorrect "uses kpath, not occupations")
- Run preset regression tests
- **Confidence**: Very high — zero parameter overlap with precision_bandspw (proven in section 11.3), phase ordering preserved (section 11.2)

### Priority 2: Add `section` field to search_parameters (Medium, ~30 min)
- **Files**: `src/qmatsuite/mcp/search_index.py`, `src/qmatsuite/mcp/tools/search_parameters.py`
- Add `section` slot to `TagDoc`, populate from QE `namelist` and CP2K `section`
- For ORCA: `section="keyword_line"` or `section="block:<name>"` (section 12.3)
- Return in search results, update context_hint with QE nesting guidance

### Priority 3: Add PARAM_WRONG_SECTION preflight rule (Medium, ~1 hour)
- **File**: `src/qmatsuite/drivers/qe/preflight.py`
- Load QE metadata, build param→namelist lookup
- Emit `severity="warning"` with corrective suggestion
- Higher value than set_parameters validation because it catches all error sources (section 13.5)

### Priority 4: Add soft validation to set_parameters (Low, ~1 hour)
- **File**: `src/qmatsuite/mcp/tools/set_parameters.py`
- Add `validation_warnings` array with structured `suggested_fix` (section 13.3)
- Lower priority than preflight — defense-in-depth, not primary gate

### Not recommended (unchanged from original):
- Writer-level validation
- Architectural changes to metadata schema for all engines
- Automatic parameter relocation
- CP2K section validation (section 14.2 — auto-nesting prevents most errors)
