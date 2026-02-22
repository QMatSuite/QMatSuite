# Occupations Scheme Preset - Implementation Plan

## Goal

Replace Material (metal/insulator) preset dimension with new `occupations_scheme` dimension.

**Options:**
- `fixed` → "Fixed occupations (gapped / default)"
- `smearing_gaussian` → "Gaussian smearing (degauss=0.02 Ry)"
- `tetrahedra` → "Tetrahedra method"
- `CUSTOM` when mismatched

---

## Phase 1: Update Dimension Definitions

### [x] 1.1 Update dimensions.py
- Remove `MaterialOption` enum
- Add `OccupationsSchemeOption` enum with: `FIXED`, `SMEARING_GAUSSIAN`, `TETRAHEDRA`
- Update `V1_DIMENSIONS` to use `"occupations_scheme"` instead of `"material"`
- Update dimension constants

### [x] 1.2 Update __init__.py exports
- Remove `MaterialOption` from exports
- Add `OccupationsSchemeOption` to exports

---

## Phase 2: Implement Compiler

### [x] 2.1 Update compiler.py
- Remove `compile_material()`
- Add `compile_occupations_scheme(option: OccupationsSchemeOption) -> Dict[str, Any]`
  - `fixed`: `{"SYSTEM": {"occupations": "fixed"}}` (explicitly remove smearing/degauss if present)
  - `smearing_gaussian`: `{"SYSTEM": {"occupations": "smearing", "smearing": "gaussian", "degauss": 0.02}}`
  - `tetrahedra`: `{"SYSTEM": {"occupations": "tetrahedra"}}` (explicitly remove smearing/degauss)
- Update `compile_presets()` to handle `occupations_scheme`

### [x] 2.2 Ensure cleanup of conflicting keys (handled by integration layer)
- When applying `fixed` or `tetrahedra`, ensure `smearing` and `degauss` are removed from step.yml
- When applying `smearing_gaussian`, ensure only these three keys are set

---

## Phase 3: Implement Detector

### [x] 3.1 Update detector.py
- Remove `detect_material()`
- Add `detect_occupations_scheme(params: Dict, step_type: str) -> Union[OccupationsSchemeOption, CUSTOM]`
  - Missing occupations → `FIXED`
  - `occupations='fixed'` → `FIXED`
  - `occupations='smearing'`:
    - Check `smearing` is `'gaussian'` or `'gauss'` (synonyms)
    - Check `degauss == 0.02` (within abs_tol=1e-12)
    - If all match → `SMEARING_GAUSSIAN`
    - Otherwise → `CUSTOM`
  - `occupations='tetrahedra'` → `TETRAHEDRA`
  - `occupations='tetrahedra_opt'` or other → `CUSTOM`
  - `occupations='from_input'` or other → `CUSTOM`

### [x] 3.2 Update aggregation logic
- Update `detect_dimension_from_steps()` to handle `occupations_scheme`
- Ensure receiver/wildcard semantics work correctly

---

## Phase 4: Update Receivers

### [x] 4.1 Update receivers.py
- Remove material receiver specs
- Add `occupations_scheme` receiver specs:
  - Receivers: `scf, nscf, relax, vc-relax, md, vc-md, bands`
  - Non-receivers: `bands_pw`, post-processing steps
- Update `filter_presets_for_step()` to handle new dimension

---

## Phase 5: Update Integration Layer

### [x] 5.1 Update integration.py
- Update `detect_presets_from_calculation()` to use new dimension
- Ensure footprints include occupations/smearing/degauss values

### [x] 5.2 Update daemon handlers (should work automatically)
- Update `_handle_detect_presets()` (should work automatically)
- Update `_handle_apply_presets_to_calculation()` (should work automatically)
- Verify step results show SKIPPED for non-receivers

---

## Phase 6: Update UI (TypeScript)

### [ ] 6.1 Update types (qms.ts)
- Remove `MaterialValue` type
- Add `OccupationsSchemeValue` type: `'fixed' | 'smearing_gaussian' | 'tetrahedra' | 'Custom'`
- Update `PresetState` interface

### [ ] 6.2 Update PresetSection.tsx
- Replace Material row with Occupations row
- Dropdown options: "Fixed" / "Smearing (Gaussian 0.02 Ry)" / "Tetrahedra"
- Show CUSTOM badge when detected
- Minimal copy: "May affect convergence and DOS."

### [ ] 6.3 Update footprints display
- Ensure occupations/smearing/degauss values are shown in step row footprints

---

## Phase 7: Tests

### [ ] 7.1 Unit tests for detection
- `test_detect_fixed_missing_occupations()`: missing → fixed
- `test_detect_fixed_explicit()`: occupations='fixed' → fixed
- `test_detect_smearing_gaussian_canonical()`: smearing + gaussian + degauss=0.02 → smearing_gaussian
- `test_detect_smearing_gaussian_synonym()`: smearing + gauss + degauss=0.02 → smearing_gaussian
- `test_detect_smearing_gaussian_wrong_degauss()`: degauss != 0.02 → CUSTOM
- `test_detect_smearing_non_gaussian()`: smearing='mv'/'cold' → CUSTOM
- `test_detect_tetrahedra()`: occupations='tetrahedra' → tetrahedra
- `test_detect_tetrahedra_opt()`: occupations='tetrahedra_opt' → CUSTOM
- `test_detect_from_input()`: occupations='from_input' → CUSTOM

### [ ] 7.2 Aggregation tests
- `test_aggregate_receiver_steps()`: all receivers agree → that value
- `test_aggregate_disagreement()`: receivers disagree → CUSTOM
- `test_aggregate_wildcard_steps()`: non-receivers ignored

### [ ] 7.3 Compiler/detector roundtrip tests
- `test_roundtrip_fixed()`: compile → detect → fixed
- `test_roundtrip_smearing_gaussian()`: compile → detect → smearing_gaussian
- `test_roundtrip_tetrahedra()`: compile → detect → tetrahedra

### [ ] 7.4 Integration tests
- `test_apply_occupations_scheme_to_receivers()`: verify receivers get updated
- `test_apply_occupations_scheme_skips_non_receivers()`: verify bands_pw skipped
- `test_apply_removes_conflicting_keys()`: verify smearing/degauss removed when not needed

---

## Verification

Run full test suite:
```bash
source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest tests/ -v --tb=short
```

All tests must pass.

