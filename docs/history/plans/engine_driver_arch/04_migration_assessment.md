# Migration Assessment

**Document Version**: 1.0
**Date**: 2026-01-20
**Status**: DESIGN PROPOSAL

---

## 1. Migration Strategy Overview

### 1.1 Core Principles

1. **Incremental migration**: One engine at a time, not big-bang
2. **Parallel paths**: Legacy and driver dispatch coexist during transition
3. **Zero downtime**: Existing workflows must continue working
4. **Test-driven**: Each phase requires comprehensive test coverage
5. **Rollback capability**: Each phase must be reversible

### 1.2 Phased Approach

| Phase | Focus | Scope | Risk Level |
|-------|-------|-------|------------|
| **Phase 0** | Foundation | Driver protocol, registry | Low |
| **Phase 1** | Critical fixes | Remove QE fallback | Medium |
| **Phase 2** | Pilot migration | VASP to driver model | Medium |
| **Phase 3** | Expand | Remaining engines | Medium |
| **Phase 4** | Cleanup | Remove legacy paths | High |

---

## 2. Phase 0: Foundation

### 2.1 Objectives

- Define EngineDriver protocol
- Implement DriverRegistry
- Create driver auto-discovery mechanism
- No changes to existing execution paths

### 2.2 Deliverables

| Deliverable | Description |
|-------------|-------------|
| `driver_protocol.py` | EngineDriver Protocol definition |
| `driver_registry.py` | DriverRegistry class |
| `driver_exceptions.py` | Custom exception classes |
| `drivers/__init__.py` | Auto-discovery mechanism |
| Unit tests | Registry and protocol tests |

### 2.3 Success Criteria

- [ ] EngineDriver Protocol compiles with type checker
- [ ] DriverRegistry handles registration/lookup
- [ ] Auto-discovery loads driver packages
- [ ] No impact on existing tests

### 2.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Protocol design flaws | Medium | High | Review against all 7 engines before finalizing |
| Import cycle issues | Low | Medium | Careful package structure |

---

## 3. Phase 1: Critical Fixes

### 3.1 Objectives

**IMMEDIATE PRIORITY**: Remove dangerous silent fallbacks

### 3.2 Changes Required

#### 3.2.1 calc_identity.py

**Current** (dangerous):
```python
else:
    families.add("qe")  # Silent fallback
```

**Target** (safe):
```python
else:
    raise UnknownStepTypeError(
        f"Step type '{machine_type}' not recognized. "
        f"Check spelling or ensure engine is supported."
    )
```

#### 3.2.2 recipes.py

**Current** (dangerous):
```python
return recipe_map.get(engine_family, QERecipe)  # Silent fallback
```

**Target** (safe):
```python
if engine_family not in recipe_map:
    raise UnknownEngineError(f"No recipe for engine '{engine_family}'")
return recipe_map[engine_family]
```

### 3.3 Migration Path

1. Add explicit errors with helpful messages
2. Scan codebase for any code relying on fallback behavior
3. Fix any legitimate cases found
4. Deploy with monitoring for error reports

### 3.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Hidden code relies on fallback | Medium | High | Comprehensive grep search |
| User workflows broken | Low | Medium | Clear error messages with fix guidance |
| Rollback needed | Low | Low | Simple revert to fallback behavior |

### 3.5 Rollback Plan

If critical issues discovered:
1. Revert to fallback behavior
2. Add logging to track fallback usage
3. Analyze logs to find legitimate cases
4. Fix cases before re-attempting

---

## 4. Phase 2: Pilot Migration (VASP)

### 4.1 Why VASP First

| Factor | Assessment |
|--------|------------|
| **Isolation** | Engine code well-contained in `engine/` |
| **Complexity** | Medium (representative but not simplest) |
| **Test coverage** | Good existing test suite |
| **User base** | Large (validates real-world usage) |
| **Pattern** | Per-step workdir (similar to CP2K/LAMMPS) |

### 4.2 Deliverables

| Deliverable | Description |
|-------------|-------------|
| `drivers/vasp/__init__.py` | Driver registration |
| `drivers/vasp/driver.py` | VASPDriver implementation |
| `drivers/vasp/recipe.py` | VASPRecipe (moved from recipes.py) |
| `drivers/vasp/handler.py` | vasp_step_handler (moved from handlers.py) |
| `drivers/vasp/staging.py` | vasp_staging.py (moved) |
| `drivers/vasp/reference.py` | reference_resolver.py (VASP parts) |
| `drivers/vasp/resolver.py` | Executable discovery |
| Integration tests | Full VASP workflow tests |

### 4.3 Migration Steps

#### Step 1: Create Driver Package

```
mkdir -p src/qmatsuite/drivers/vasp/
touch src/qmatsuite/drivers/vasp/__init__.py
```

#### Step 2: Implement VASPDriver

Implement all protocol methods, initially delegating to existing code:

```python
class VASPDriver:
    def get_handler(self):
        # Initially import from existing location
        from qmatsuite.execution.handlers import vasp_step_handler
        return vasp_step_handler
```

#### Step 3: Register Driver

```python
# drivers/vasp/__init__.py
from .driver import VASPDriver
from qmatsuite.core.driver_registry import DriverRegistry
DriverRegistry.register(VASPDriver())
```

#### Step 4: Dual Dispatch

Modify kernel to try driver registry first, fall back to legacy:

```python
def get_handler_for_step(step):
    try:
        driver = DriverRegistry.get_driver_for_step_type(step.step_type)
        return driver.get_handler()
    except UnknownStepTypeError:
        # Legacy fallback during migration
        return legacy_handler_lookup(step)
```

#### Step 5: Move Code

Move VASP-specific code from shared modules to driver package:
- `handlers.py` → `drivers/vasp/handler.py`
- `recipes.py` → `drivers/vasp/recipe.py`
- `vasp_staging.py` → `drivers/vasp/staging.py`

#### Step 6: Remove Legacy VASP

Once driver proven stable, remove VASP code from shared modules.

### 4.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Subtle behavior change | Medium | High | Extensive comparison testing |
| Import path changes break users | Low | Medium | Maintain compatibility shims |
| Performance regression | Low | Low | Profile before/after |

### 4.5 Validation Strategy

1. **Unit tests**: All existing VASP tests pass
2. **Integration tests**: Full workflow execution
3. **Comparison tests**: Run same calculation with legacy and driver, compare results
4. **Performance tests**: Measure startup and execution time
5. **Real-world validation**: Test with actual VASP binary on representative systems

---

## 5. Phase 3: Engine Expansion

### 5.1 Migration Order

Based on complexity assessment from code inventory:

| Order | Engine | Complexity | Notes |
|-------|--------|------------|-------|
| 1 | VASP | Medium | (Pilot, already done) |
| 2 | ORCA | Low | Clean chain pattern |
| 3 | PySCF | Low | Similar to ORCA |
| 4 | LAMMPS | Medium | Restart resolution logic |
| 5 | CP2K | Medium | Follows LAMMPS pattern |
| 6 | QE | High | Oldest, deepest integration |
| 7 | W90 | High | Cross-engine dependency |

### 5.2 Per-Engine Checklist

For each engine migration:

- [ ] Create driver package structure
- [ ] Implement EngineDriver protocol
- [ ] Move recipe class to driver
- [ ] Move handler function to driver
- [ ] Move engine-specific utilities
- [ ] Register driver
- [ ] Update dual dispatch
- [ ] Run existing tests
- [ ] Add comparison tests
- [ ] Remove from legacy modules
- [ ] Update documentation

### 5.3 Special Considerations

#### QE Migration (Complex)

- Oldest engine with deepest integration
- Many QE-specific utilities in `core/qe/`
- Shared outdir model differs from other engines
- Many step types (~20+)
- Should be migrated after simpler engines validate pattern

#### W90 Migration (Complex)

- Cross-engine dependency on QE
- Driver must declare QE dependency
- May need inter-driver communication mechanism
- Consider migrating simultaneously with QE

### 5.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Engine-specific bugs | Medium | Medium | Thorough testing per engine |
| Accumulated technical debt | Medium | Low | Periodic refactoring |
| Team fatigue | Low | Medium | Pace migrations appropriately |

---

## 6. Phase 4: Legacy Cleanup

### 6.1 Objectives

- Remove dual dispatch paths
- Delete legacy handler/recipe code from shared modules
- Remove hardcoded step type sets
- Update all documentation

### 6.2 Prerequisites

- All 7 engines migrated and stable
- No fallback path usage in production
- Comprehensive test coverage
- Documentation updated

### 6.3 Cleanup Checklist

#### 6.3.1 handlers.py

- [ ] Remove all engine-specific handlers
- [ ] Remove build_handler_map function
- [ ] Keep only thin dispatcher using registry

#### 6.3.2 recipes.py

- [ ] Remove all engine-specific recipe classes
- [ ] Remove get_recipe_class function
- [ ] Keep only thin dispatcher using registry

#### 6.3.3 calc_identity.py

- [ ] Remove prefix-based inference entirely
- [ ] Use only registry lookup

#### 6.3.4 structure_steps.py

- [ ] Remove hardcoded step type sets
- [ ] Query registry for engine information

#### 6.3.5 step_done.py

- [ ] Remove hardcoded step type sets
- [ ] Query drivers for done policy

#### 6.3.6 generalized_steps.py

- [ ] Remove hardcoded MATERIALIZATION_MAP
- [ ] Aggregate from driver declarations

### 6.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Missed legacy usage | Medium | High | Comprehensive code search |
| Breaking external tools | Low | Medium | Deprecation warnings first |
| Documentation gaps | Medium | Low | Documentation audit |

### 6.5 Rollback Considerations

Phase 4 is **irreversible** once completed. Before starting:

1. Tag release with legacy code intact
2. Document rollback procedure (revert to tag)
3. Ensure all stakeholders approve
4. Plan extended stabilization period

---

## 7. Resource Requirements

### 7.1 Per-Phase Estimates

| Phase | Scope | Files Changed |
|-------|-------|---------------|
| Phase 0 | Foundation | 4 new files |
| Phase 1 | Critical fixes | 2-3 files |
| Phase 2 | VASP pilot | 8-10 files |
| Phase 3 | 6 engines | ~50 files total |
| Phase 4 | Cleanup | 10-15 files |

### 7.2 Testing Effort

| Category | Estimate |
|----------|----------|
| Unit tests | 1-2 per driver method |
| Integration tests | 3-5 per engine |
| Comparison tests | 1 per step type |
| Performance tests | Startup + per-engine |

---

## 8. Success Metrics

### 8.1 Technical Metrics

| Metric | Target |
|--------|--------|
| Test pass rate | 100% |
| New driver addition | No kernel changes required |
| Silent fallbacks | 0 |
| Duplicated step type sets | 0 |
| Lines in handlers.py | < 100 (dispatcher only) |
| Lines in recipes.py | < 100 (dispatcher only) |

### 8.2 Quality Metrics

| Metric | Target |
|--------|--------|
| Driver self-containment | 100% (no engine code in kernel) |
| API documentation coverage | 100% |
| Migration guide completeness | All 7 engines documented |

---

## 9. Risks and Mitigations Summary

| Risk | Phase | Probability | Impact | Mitigation |
|------|-------|-------------|--------|------------|
| Protocol design flaws | 0 | Medium | High | Multi-engine review |
| Hidden fallback reliance | 1 | Medium | High | Comprehensive search |
| Behavior changes | 2-3 | Medium | High | Comparison testing |
| Import path breaks | 2-3 | Low | Medium | Compatibility shims |
| Cross-engine issues (W90) | 3 | Medium | Medium | Careful dependency handling |
| Missed legacy usage | 4 | Medium | High | Code search + deprecation period |

---

## 10. Recommendation

**Proceed with migration** following the phased approach:

1. **Start immediately**: Phase 0 (Foundation) and Phase 1 (Critical fixes)
2. **Validate thoroughly**: Phase 2 (VASP pilot) with extensive testing
3. **Expand systematically**: Phase 3 (remaining engines) one at a time
4. **Clean up carefully**: Phase 4 (legacy removal) only after full stabilization

The current architecture has accumulated significant technical debt and contains critical vulnerabilities (silent QE fallback). The driver model provides a clear path to a safer, more maintainable system.

**Priority recommendation**: Even before full migration, implement Phase 1 critical fixes to eliminate silent fallback vulnerabilities.
