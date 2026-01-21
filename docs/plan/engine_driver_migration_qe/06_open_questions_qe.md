# QE Migration: Open Questions and Decisions

> This document tracks unresolved decisions and questions that need answers before or during the QE migration.

---

## Critical Decisions (Must Resolve Before Starting)

### Q1: W90 Step Type Ownership

**Question**: Should `w90_preproc` and `w90_run` step types move to the W90 driver or stay with QE?

**Current State**:
- These steps have `engine="qe"` in `workflow/registry.py`
- W90 driver already exists at `drivers/w90/`
- Tests expect `engine="qe"` for backward compatibility

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Keep in QE | Minimal change, backward compat | Violates driver ownership principle |
| B: Move to W90 | Cleaner architecture | Breaks tests, needs migration |
| C: Dual registration | Both drivers register them | Complexity, potential conflicts |

**Recommendation**: **Option B** with staged migration
- PR 4-8: Keep `engine="qe"` for compatibility
- Post-migration PR: Move to W90 driver, update tests

**Decision**: [ ] A / [ ] B / [ ] C (need input)

---

### Q2: Step.engine Default Removal Strategy

**Question**: How do we handle existing code that creates Steps without explicit engine?

**Current State**:
- `Step` dataclass has `engine: str = "qe"` default
- Unknown how many places rely on this default

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Remove default, fail on None | Clean, forces explicit | Breaks all legacy code immediately |
| B: Deprecation warning then remove | Gradual migration | Longer timeline |
| C: Infer from step_type | Smart default | Complex, hides issues |

**Recommendation**: **Option B**
- PR 10: Add deprecation warning when engine is None
- Future PR: Make engine required, remove warning

**Decision**: [ ] A / [ ] B / [ ] C (need input)

---

### Q3: IR Backend Generalization

**Question**: Should other engines get IR backends, or is IR QE-only?

**Current State**:
- Only QE has `ir/backends/qe/`
- IR is designed for QE parameter mapping
- Other engines don't use IR layer

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Keep IR QE-only | Simpler, fits current use | Limits IR usefulness |
| B: Generalize IR interface | Extensible | Significant refactor |
| C: Move IR to QE driver entirely | Clean separation | IR becomes QE-internal |

**Recommendation**: **Option C**
- Move `ir/backends/qe/` to `drivers/qe/ir/`
- Don't generalize IR for other engines (not needed currently)
- If other engines need IR, they implement their own in their driver bundle

**Decision**: [ ] A / [ ] B / [ ] C (need input)

---

### Q4: Pseudo Handling Generalization

**Question**: Should `core/pseudo.py` become engine-agnostic or stay QE-specific?

**Current State**:
- `core/pseudo.py` uses `QEInputParser` to extract ATOMIC_SPECIES
- Pseudo resolution is tightly coupled to QE input format
- VASP uses POTCARs, not UPF pseudopotentials

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Move entirely to QE driver | Clean, QE owns its pseudos | Breaks current kernel-level pseudo API |
| B: Abstract interface in kernel | Engine-agnostic | Over-engineering for single use |
| C: Keep in kernel, add QE-specific impl in driver | Hybrid | Duplication |

**Recommendation**: **Option A**
- Move `ensure_qe_pseudos()` to `drivers/qe/pseudo.py`
- Kernel only provides generic pseudo directory paths
- Each driver handles its own pseudo format

**Decision**: [ ] A / [ ] B / [ ] C (need input)

---

## Medium Priority Questions

### Q5: I/O Model Location

**Question**: Should QE I/O models (`QEModule`, `QEInput`, etc.) be part of public API or internal to driver?

**Current State**:
- Exported from `quantumvitas.io`
- Used by external code for QE input manipulation

**Recommendation**: Keep as public API via re-exports
- Move implementation to `drivers/qe/io/`
- Re-export from `quantumvitas.io` for backward compat
- Document as stable API

**Decision**: [ ] Public API / [ ] Internal only / [ ] Hybrid

---

### Q6: Test Coverage Targets

**Question**: What test coverage is required before each PR can merge?

**Proposed Targets**:
| PR Range | Unit Coverage | Integration Required |
|----------|---------------|----------------------|
| PR 1-2 | 80% | No |
| PR 3-4 | 85% | Yes (if QE available) |
| PR 5-8 | 85% | Yes |
| PR 9-10 | 90% | Yes (mandatory) |
| PR 11 | 90% | Yes (full regression) |

**Decision**: Approve / Modify targets

---

### Q7: Deprecation Warning Duration

**Question**: How long should deprecation warnings remain before removing old import paths?

**Options**:
- A: 1 minor version (e.g., removed in v2.1 if added in v2.0)
- B: 2 minor versions
- C: 1 major version (e.g., removed in v3.0)

**Recommendation**: **Option B** - 2 minor versions
- Gives users time to update imports
- Not too long to carry technical debt

**Decision**: [ ] A / [ ] B / [ ] C

---

## Low Priority Questions

### Q8: QE Settings Location

**Question**: Should `settings.qe` section stay in core settings or move to driver?

**Recommendation**: Keep in core settings
- Settings are user-facing configuration
- Users expect engine settings in one place
- Driver can read from core settings

**Decision**: [ ] Keep in core / [ ] Move to driver

---

### Q9: Error Message Standardization

**Question**: Should QE errors use a specific format/prefix for identification?

**Proposal**:
```
[QE_ERROR] Step execution failed: ...
[QE_WARN] Pseudo not found, downloading...
[QE_INFO] Using QE bin: /path/to/bin
```

**Decision**: [ ] Adopt prefix format / [ ] Keep current format

---

### Q10: Documentation Updates

**Question**: What documentation needs updating as part of migration?

**Checklist**:
- [ ] API reference (moved modules)
- [ ] Getting started guide (if mentions QE paths)
- [ ] Contributing guide (driver structure)
- [ ] Migration guide for users

---

## Resolved Questions

### Q-Resolved-1: Should qe_shim be deleted?

**Decision**: YES
**Rationale**: Shim is a temporary wrapper; proper driver replaces it
**PR**: PR 11

### Q-Resolved-2: Should backward compat re-exports be permanent?

**Decision**: NO - deprecate after 2 versions
**Rationale**: Clean codebase, but give users time to migrate
**Timeline**: v2.0 (add), v2.2 (deprecation warning), v3.0 (remove)

---

## Questions for Stakeholders

### For Product/UX Team
1. Should migration documentation be visible to end users?
2. Any user-facing changes in error messages?

### For QA Team
1. Any specific QE workflows that need manual testing?
2. Performance benchmarks to run?

### For DevOps Team
1. CI job for QE integration tests - resource requirements?
2. QE version to test against?

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Legacy code breaks | Medium | High | Backward compat re-exports |
| W90 integration breaks | Medium | Medium | Staged W90 migration |
| IR compilation changes | Low | High | Extensive IR unit tests |
| Performance regression | Low | Medium | Benchmark before/after |
| Test coverage gaps | Medium | Medium | Review coverage per PR |

---

## Decision Log

| Date | Question | Decision | Rationale | Decided By |
|------|----------|----------|-----------|------------|
| TBD | Q1: W90 ownership | | | |
| TBD | Q2: Step.engine | | | |
| TBD | Q3: IR backend | | | |
| TBD | Q4: Pseudo handling | | | |

---

## Next Steps

1. **Review this document** with team
2. **Make decisions** on critical questions (Q1-Q4)
3. **Update PR checklists** based on decisions
4. **Begin PR 1** once decisions are finalized
