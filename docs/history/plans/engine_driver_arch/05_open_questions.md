# Open Questions

**Document Version**: 1.0
**Date**: 2026-01-20
**Status**: REQUIRES DECISIONS

---

## 1. Overview

This document captures unresolved design decisions for the engine driver architecture. Each question includes context, options, and recommendations where applicable.

**Decision Status Legend**:
- **OPEN**: Requires team discussion
- **LEANING**: Have recommendation, need confirmation
- **BLOCKED**: Waiting on external information

---

## 2. Architectural Questions

### 2.1 Driver Package Location

**Status**: LEANING

**Question**: Where should driver packages live in the source tree?

**Options**:

| Option | Structure | Pros | Cons |
|--------|-----------|------|------|
| **A** | `src/qmatsuite/drivers/` | Clear separation, easy discovery | New top-level package |
| **B** | `src/qmatsuite/engine/` | Uses existing directory | Mixes old and new code |
| **C** | `src/qmatsuite/core/drivers/` | Near core abstractions | Clutters core/ |

**Recommendation**: **Option A** (`src/qmatsuite/drivers/`)

Clean separation between kernel and driver code. New directory signals architectural change.

---

### 2.2 Protocol vs Abstract Base Class

**Status**: OPEN

**Question**: Should EngineDriver be a Protocol (structural typing) or ABC (nominal typing)?

**Options**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | Protocol | Duck typing, flexible | No runtime validation |
| **B** | ABC | Explicit inheritance, IDE support | More boilerplate |
| **C** | Both | Protocol for typing, ABC for mixins | Complexity |

**Considerations**:
- Protocol allows third-party drivers without inheritance
- ABC enables shared default implementations
- Type checkers support both

**Recommendation**: Need team input. Leaning toward **Protocol** for flexibility.

---

### 2.3 Capability Querying Granularity

**Status**: OPEN

**Question**: How granular should capability declarations be?

**Current proposal** (EngineCapabilities dataclass):
```python
supports_scf: bool
supports_relax: bool
supports_hybrid_functionals: bool
# ... many boolean flags
```

**Alternative** (capability strings):
```python
capabilities: set[str] = {"scf", "relax", "hybrid_functionals"}
```

**Alternative** (hierarchical):
```python
capabilities: dict = {
    "calculations": ["scf", "relax", "md"],
    "features": {"spin": True, "soc": True},
}
```

**Considerations**:
- Boolean flags are type-safe but verbose
- String sets are flexible but lose type safety
- Hierarchical is expressive but complex

**Recommendation**: Need team input on how capabilities will be queried.

---

### 2.4 Cross-Engine Dependencies (Wannier90)

**Status**: BLOCKED

**Question**: How should W90 driver declare its dependency on QE?

**Context**: Wannier90 consumes QE outputs (`.amn`, `.mmn` files) and cannot run standalone.

**Options**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | Implicit | W90 handler reads from QE workdir | Hidden coupling |
| **B** | Explicit dep | W90 driver declares `requires: ["qe"]` | Clear but rigid |
| **C** | Artifact-based | W90 declares required artifacts, kernel resolves | Flexible |

**Blocked on**: Understanding current W90/QE coupling in codebase

**Recommendation**: Need to audit existing W90 code before deciding.

---

### 2.5 Shared Outdir Model (QE)

**Status**: OPEN

**Question**: How does QE's shared outdir model fit into per-driver workdir policy?

**Context**: QE uses `WorkdirPolicy.SHARED` where all steps share one outdir with prefix namespacing. This differs from VASP/LAMMPS per-step workdirs.

**Options**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | QE-specific policy | Driver declares `SHARED` policy | Requires special kernel handling |
| **B** | Virtualize workdirs | Kernel provides consistent interface | May not match QE semantics |
| **C** | Accept divergence | Let QE be different | Inconsistent API surface |

**Recommendation**: Need team input. **Option A** seems pragmatic given QE's established patterns.

---

## 3. Implementation Questions

### 3.1 Backward Compatibility Shims

**Status**: LEANING

**Question**: How long should we maintain backward compatibility for moved code?

**Context**: When moving `VASPRecipe` from `recipes.py` to `drivers/vasp/recipe.py`, existing code may import from old location.

**Options**:

| Option | Duration | Approach |
|--------|----------|----------|
| **A** | No shims | Break immediately |
| **B** | 1 minor version | Deprecation warning, then remove |
| **C** | Until next major | Long deprecation period |

**Recommendation**: **Option B** (1 minor version)

Add deprecation warning:
```python
# recipes.py (legacy location)
import warnings
warnings.warn(
    "VASPRecipe moved to qmatsuite.drivers.vasp.recipe. "
    "Update your imports.",
    DeprecationWarning,
)
from qmatsuite.drivers.vasp.recipe import VASPRecipe
```

---

### 3.2 Driver Loading: Eager vs Lazy

**Status**: OPEN

**Question**: Should drivers be loaded at startup (eager) or on first use (lazy)?

**Options**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | Eager | All drivers loaded at import | Simple, catches errors early | Slower startup |
| **B** | Lazy | Drivers loaded on first use | Fast startup | Delayed errors |
| **C** | Configurable | User chooses via config | Flexible | Complexity |

**Considerations**:
- Current codebase uses eager loading
- Lazy loading complicates error reporting
- Driver loading should be fast (< 100ms each)

**Recommendation**: Need performance testing. Leaning **Option A** for simplicity.

---

### 3.3 Error Message Internationalization

**Status**: OPEN

**Question**: Should error messages from drivers support i18n?

**Context**: Current codebase uses English error messages throughout.

**Options**:

| Option | Approach |
|--------|----------|
| **A** | English only | Keep current behavior |
| **B** | i18n framework | Message keys + translations |
| **C** | Future consideration | Design for i18n, implement later |

**Recommendation**: **Option A** for now, with **Option C** mindset (avoid hardcoding strings in multiple places).

---

### 3.4 Driver Testing Strategy

**Status**: OPEN

**Question**: How should drivers be tested when engine binaries aren't available?

**Current state**: Mock engines exist in `tests/fixtures/mock_engines/`

**Options**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | Mock engine binaries | Test against mock outputs | Doesn't test real behavior |
| **B** | CI with real engines | Run subset of tests with real binaries | Expensive, slow |
| **C** | Recorded fixtures | Capture real outputs, replay in tests | Brittle to format changes |
| **D** | Hybrid | Mocks for unit tests, real for integration | Best coverage | Complexity |

**Recommendation**: **Option D** (hybrid)
- Unit tests: Mock engine outputs
- Integration tests: Real binaries in CI (matrix for available engines)

---

## 4. Process Questions

### 4.1 Driver Contribution Guidelines

**Status**: OPEN

**Question**: What guidelines should third-party driver contributors follow?

**Needed**:
- [ ] Driver template/skeleton
- [ ] Required test coverage
- [ ] Documentation requirements
- [ ] Review checklist
- [ ] Versioning policy

**Recommendation**: Create `CONTRIBUTING_DRIVERS.md` before Phase 3.

---

### 4.2 Engine Support Lifecycle

**Status**: OPEN

**Question**: How do we handle engine version support and deprecation?

**Questions to resolve**:
- Minimum supported version per engine?
- How long do we support old engine versions?
- How do we handle breaking engine updates?

**Recommendation**: Define policy per engine based on user base.

---

### 4.3 CI/CD for Driver Testing

**Status**: OPEN

**Question**: How should CI test engines that require licenses or specific hardware?

**Engines with constraints**:
- **VASP**: Licensed software
- **Gaussian**: Licensed software
- **GPU engines**: Need GPU hardware

**Options**:

| Option | Approach |
|--------|----------|
| **A** | Skip in CI | Only test locally |
| **B** | Mock in CI | Real tests local only |
| **C** | Licensed CI runners | Pay for license in CI |
| **D** | Community testing | Contributors test licensed engines |

**Recommendation**: Need budget discussion. Likely **Option B** for licensed engines.

---

## 5. Future Considerations

### 5.1 Plugin System

**Status**: FUTURE

**Question**: Should drivers be installable as separate packages?

**Vision**:
```bash
pip install qmatsuite-driver-vasp
pip install qmatsuite-driver-cp2k
```

**Considerations**:
- Enables third-party drivers
- Complicates dependency management
- Requires stable driver API

**Recommendation**: Not for initial implementation. Revisit after API stabilizes.

---

### 5.2 Remote Engine Execution

**Status**: FUTURE

**Question**: How do drivers interact with remote execution (HPC, cloud)?

**Current state**: Engines assumed to run locally

**Future considerations**:
- Job submission to schedulers (SLURM, PBS)
- Cloud execution (AWS, GCP)
- Container execution (Docker, Singularity)

**Recommendation**: Design driver interface to be execution-agnostic. Handler receives workdir and returns results; doesn't assume local execution.

---

### 5.3 Driver Marketplace

**Status**: FUTURE

**Question**: Should there be a registry/marketplace for community drivers?

**Vision**: Central listing of available drivers with:
- Verification status
- Compatibility matrix
- User ratings

**Recommendation**: Future consideration after plugin system.

---

## 6. Decision Tracking

### 6.1 Decisions Needed Before Phase 0

| ID | Question | Section | Priority |
|----|----------|---------|----------|
| Q2.1 | Driver package location | 2.1 | HIGH |
| Q2.2 | Protocol vs ABC | 2.2 | HIGH |
| Q3.2 | Eager vs lazy loading | 3.2 | MEDIUM |

### 6.2 Decisions Needed Before Phase 2

| ID | Question | Section | Priority |
|----|----------|---------|----------|
| Q2.3 | Capability granularity | 2.3 | MEDIUM |
| Q3.1 | Backward compat duration | 3.1 | MEDIUM |
| Q3.4 | Testing strategy | 3.4 | HIGH |

### 6.3 Decisions Needed Before Phase 3

| ID | Question | Section | Priority |
|----|----------|---------|----------|
| Q2.4 | Cross-engine dependencies | 2.4 | HIGH |
| Q2.5 | Shared outdir model | 2.5 | HIGH |
| Q4.1 | Contribution guidelines | 4.1 | MEDIUM |

---

## 7. Action Items

| Item | Owner | Deadline | Status |
|------|-------|----------|--------|
| Audit W90/QE coupling | TBD | Before Phase 3 | NOT STARTED |
| Performance test eager loading | TBD | Before Phase 0 | NOT STARTED |
| Draft CONTRIBUTING_DRIVERS.md | TBD | Before Phase 3 | NOT STARTED |
| Define engine version policy | TBD | Before Phase 3 | NOT STARTED |
| Discuss CI budget for licensed engines | TBD | Before Phase 2 | NOT STARTED |

---

## 8. References

- [00_overview.md](00_overview.md) - Executive summary
- [01_engine_code_inventory.md](01_engine_code_inventory.md) - Code inventory
- [02_kernel_touchpoints_audit.md](02_kernel_touchpoints_audit.md) - Touchpoints audit
- [03_driver_model_spec.md](03_driver_model_spec.md) - Driver specification
- [04_migration_assessment.md](04_migration_assessment.md) - Migration strategy
