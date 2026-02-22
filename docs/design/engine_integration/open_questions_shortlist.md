# Open Questions Shortlist

**Version**: 1.0
**Status**: REQUIRES DECISIONS

---

## Priority Legend

| Priority | Meaning | Deadline |
|----------|---------|----------|
| **P0** | Blocks Gate Zero | Before any migration |
| **P1** | Blocks first engine migration | Before ORCA migration |
| **P2** | Blocks later migrations | Before QE/W90 migration |

---

## 1. Protocol vs ABC for EngineDriver

**Priority**: P0
**Decision needed**: Interface implementation approach

| Option | Description |
|--------|-------------|
| **A. Protocol** | Structural typing, duck-typed compliance |
| **B. ABC** | Nominal typing, explicit inheritance |
| **C. ABC + Protocol** | ABC for implementation, Protocol for type hints |

**Recommended default**: **Option A (Protocol)**

Rationale: Allows third-party drivers without inheritance. Type checkers support Protocol. Less boilerplate for minimal drivers.

**Risk if not decided**: Drivers written with incompatible patterns. Refactoring needed later.

---

## 2. Driver Loading Strategy

**Priority**: P0
**Decision needed**: When are drivers loaded?

| Option | Description |
|--------|-------------|
| **A. Eager** | All drivers loaded at first import |
| **B. Lazy** | Drivers loaded on first use |
| **C. Explicit** | User configures which drivers to load |

**Recommended default**: **Option A (Eager)**

Rationale: Simple, catches errors at startup, no hidden import failures. Current codebase uses eager loading.

**Risk if not decided**: Performance issues or confusing delayed errors if wrong choice made.

---

## 3. QE Shared Outdir Handling

**Priority**: P2 (before QE migration)
**Decision needed**: How to handle QE's unique workdir model?

| Option | Description |
|--------|-------------|
| **A. WorkdirPolicy.SHARED** | QE declares SHARED, kernel handles specially |
| **B. Adapter layer** | QE driver virtualizes to look like per-step |
| **C. Accept divergence** | QE driver manages its own outdir logic |

**Recommended default**: **Option A (SHARED policy)**

Rationale: Clean declaration, kernel can apply QE-specific handling. Minimal QE driver complexity.

**Risk if not decided**: QE migration blocked or hacky implementation required.

---

## 4. W90/QE Cross-Engine Dependency

**Priority**: P2 (before W90 migration)
**Decision needed**: How does W90 declare QE dependency?

| Option | Description |
|--------|-------------|
| **A. Artifact-based** | W90 declares required artifacts (.amn, .mmn), kernel resolves |
| **B. Explicit dependency** | W90 driver declares `requires: ["qe"]` |
| **C. Workflow-level** | Dependency declared in workflow definition, not driver |

**Recommended default**: **Option A (Artifact-based)**

Rationale: More flexible than hard dependency. Kernel already has artifact resolution. Works if QE outputs come from different source.

**Risk if not decided**: W90 migration blocked or breaks on edge cases.

---

## 5. Capability Declaration Format

**Priority**: P1
**Decision needed**: How granular are capability declarations?

| Option | Description |
|--------|-------------|
| **A. String set** | `{"scf", "relax", "mpi"}` |
| **B. Typed dataclass** | `EngineCapabilities(scf=True, relax=True)` |
| **C. Hierarchical dict** | `{"calc": ["scf"], "features": ["mpi"]}` |

**Recommended default**: **Option A (String set)**

Rationale: Simple, extensible, no need to modify dataclass for new capabilities. Easy to query (`"scf" in caps`).

**Risk if not decided**: Inconsistent capability declarations across drivers, difficult to query.

---

## 6. Backward Compatibility Shim Duration

**Priority**: P1
**Decision needed**: How long to keep legacy import paths?

| Option | Description |
|--------|-------------|
| **A. No shims** | Break immediately |
| **B. 1 minor version** | Deprecation warning, remove next minor |
| **C. Until next major** | Long deprecation period |

**Recommended default**: **Option B (1 minor version)**

Rationale: Gives users one release to update imports. Not so long that dead code accumulates.

**Risk if not decided**: User breakage if too short, code bloat if too long.

---

## 7. Error Message Similarity Threshold

**Priority**: P1
**Decision needed**: How to generate "did you mean" suggestions?

| Option | Description |
|--------|-------------|
| **A. Levenshtein distance** | Edit distance < 3 |
| **B. Prefix matching** | Same first 4 chars |
| **C. Both** | Combine heuristics |

**Recommended default**: **Option A (Levenshtein)**

Rationale: Handles typos well (vaps_scf → vasp_scf). Standard approach. Libraries available.

**Risk if not decided**: Poor error messages, harder debugging.

---

## 8. CI for Licensed Engines

**Priority**: P1
**Decision needed**: How to test VASP and other licensed engines in CI?

| Option | Description |
|--------|-------------|
| **A. Mock only** | CI uses mocks, real tests run locally |
| **B. Conditional CI** | Run real tests only if license available |
| **C. Skip in CI** | No VASP tests in CI at all |

**Recommended default**: **Option A (Mock only)**

Rationale: CI always runs, catches regressions. Real engine tests are contributor responsibility. No license cost.

**Risk if not decided**: Either CI gaps or license cost/complexity.

---

## 9. Driver Package Namespace

**Priority**: P0
**Decision needed**: Where do driver packages live?

| Option | Description |
|--------|-------------|
| **A. `qmatsuite.drivers.*`** | New top-level package |
| **B. `qmatsuite.engine.*`** | Reuse existing engine/ |
| **C. `qmatsuite.core.drivers.*`** | Under core/ |

**Recommended default**: **Option A (`qmatsuite.drivers.*`)**

Rationale: Clean separation from kernel. Signals architectural change. Easy discovery.

**Risk if not decided**: Confusing code organization, import cycle risks.

---

## 10. PLUGIN Method Validation

**Priority**: P2
**Decision needed**: Should kernel validate PLUGIN methods exist before calling?

| Option | Description |
|--------|-------------|
| **A. hasattr check** | Check before calling, use default if missing |
| **B. Try/except** | Call and catch AttributeError |
| **C. Require all** | Even PLUGIN methods must be defined (can return default) |

**Recommended default**: **Option A (hasattr check)**

Rationale: Clean separation of MUST/SHOULD/PLUGIN. Minimal drivers don't need stub methods. Explicit fallback to defaults.

**Risk if not decided**: Runtime errors for minimal drivers or unnecessary boilerplate.

---

## Summary Table

| # | Question | Priority | Recommended | Risk |
|---|----------|----------|-------------|------|
| 1 | Protocol vs ABC | P0 | Protocol | Incompatible drivers |
| 2 | Driver loading | P0 | Eager | Startup issues |
| 3 | QE shared outdir | P2 | SHARED policy | QE migration blocked |
| 4 | W90/QE dependency | P2 | Artifact-based | W90 migration blocked |
| 5 | Capability format | P1 | String set | Inconsistent declarations |
| 6 | Compat shim duration | P1 | 1 minor version | User breakage |
| 7 | Error suggestions | P1 | Levenshtein | Poor error messages |
| 8 | Licensed engine CI | P1 | Mock only | CI gaps |
| 9 | Driver namespace | P0 | `drivers.*` | Import cycles |
| 10 | PLUGIN validation | P2 | hasattr check | Runtime errors |

---

## Decision Log

| Date | Question | Decision | Rationale |
|------|----------|----------|-----------|
| | | | |

(Fill in as decisions are made)
