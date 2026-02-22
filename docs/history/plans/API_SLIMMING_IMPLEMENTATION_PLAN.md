# API Slimming Implementation Plan

**Status**: IN PROGRESS
**Created**: 2026-02-02
**Baseline Audit**: 2026-02-02

---

## Governing Documents

- **API Constitution**: `docs/api/API_CONSTITUTION.md` (v2.0)
- **Slimming Review**: `docs/api/API_SLIMMING_REVIEW.md` (v2)
- **Worklog**: `docs/api/API_SLIMMING_WORKLOG.md`

---

## Baseline Metrics (2026-02-02)

| Category | Count |
|----------|-------|
| utils | 91 |
| service_static | 38 |
| service_nested | 91 |
| errors | 10 |
| dtos | 11 |
| api_init | 2 |
| **TOTAL** | **243** |

### Usage Coverage

| Status | Count |
|--------|-------|
| Daemon only | 115 |
| CLI only | 51 |
| Both daemon+CLI | 44 |
| **UNUSED (0 refs)** | **33** |

---

## Target State

| Metric | Current | Target | Delta |
|--------|---------|--------|-------|
| Utils exports | 91 | <20 | -71+ |
| Static methods | 38 | <15 | -23+ |
| Total surface | 243 | <180 | -63+ |
| Unused | 33 | 0 | -33 |

---

## Implementation Phases

### Phase 1: Delete Unused Entrypoints (Priority: HIGH)

**Criteria**: 0 daemon refs AND 0 CLI refs

**Utils (6 candidates)**:
1. `generate_resource_id` - unused
2. `get_display_mode_params_class` - unused
3. `create_online_structure_cache` - unused (Law H3 violation: online search is capability)
4. `F401` entries (3x) - noqa comments, not real exports

**Service Nested (16 candidates)**:
1. `Analysis.list_properties`
2. `Analysis.get_property_ref`
3. `Analysis.load_artifact`
4. `Analysis.find_band_files`
5. `Structure.get_atoms`
6. `Structure.update_meta`
7. `Calculation.require_enclosing`
8. `Calculation.get_effective_params`
9. `Calculation.update_meta`
10. `Run.get_status`
11. `Project.get_species_map`
12. `Project.get_potential_map`
13. `Project.analyze_pseudo_effects`
14. `Engine.get_info`
15. `Engine.list_step_types`
16. `Engine.validate_installation`

**Service Static (1 candidate)**:
1. `get_pseudo_options_for_elements`

**Errors (2 candidates)**:
1. `ConflictError` - unused
2. `FilesystemError` - unused

**DTOs (8 candidates)**:
1. `RunResultDTO`
2. `AnalysisRefDTO`
3. `AnalysisSummaryDTO`
4. `ErrorDTO`
5. `CalculationDTO`
6. `MetaDTO`
7. `StructureDTO`
8. `BaseDTO` (keep - base class)

---

### Phase 2: Utils Domain Reexports → Service Methods

**Criteria**: Functions that proxy domain logic should be service methods

Per API_SLIMMING_REVIEW.md consolidation proposals:
- Online search functions → `QMSService.OnlineSearch.*`
- Analysis functions → `QMSService.Analysis.*`
- Structure functions → `QMSService.Structure.*`

---

### Phase 3: Static Method Reduction

**Criteria**: Methods with project context should be nested capability methods

Review 38 static methods for:
- Bootstrap/factory operations (keep)
- Methods that could be nested capabilities (migrate)

---

### Phase 4: Utils Docstring Justification

**Criteria**: Per Law H2, all remaining utils must have docstring justification

Add PROXIES: and JUSTIFICATION: to legitimate utils proxies.

---

## Process Per Batch

1. **Pre-delete audit**: `python tools/api_surface_audit.py`
2. **Delete 1-3 entrypoints**
3. **Full test suite**: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
4. **Post-delete audit**: `python tools/api_surface_audit.py`
5. **Log to worklog**: Record delta and any issues

---

## Risk Assessment

| Action | Risk | Mitigation |
|--------|------|------------|
| Delete unused utils | LOW | Verify 0 refs in daemon+CLI+tests |
| Delete unused DTOs | MEDIUM | Some may be base classes or used in type hints |
| Delete unused service methods | LOW | No runtime impact if truly unused |
| Delete unused errors | LOW | No runtime impact |

---

## Current Focus

**Phase 1 Progress**:
- [x] Batch 1: Deleted `generate_resource_id` (243 → 242)
- [x] Batch 2: Deleted `get_display_mode_params_class`, `create_online_structure_cache` (242 → 240)
- [ ] Phase 1 complete when all safe unused deletions done

**Next Steps**:
- Evaluate unused service nested methods for deletion
- Consider consolidation of remaining utils functions

---

## Current Metrics (After Batch 2)

| Metric | Baseline | Current | Target | Progress |
|--------|----------|---------|--------|----------|
| Total | 243 | 240 | <180 | -3 (-1.2%) |
| Utils | 91 | 88 | <20 | -3 (-3.3%) |
| Unused | 33 | 30 | 0 | -3 |

---

**End of Implementation Plan**
