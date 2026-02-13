# Engine Driver Architecture: Executive Overview

**Document Version**: 1.0
**Date**: 2026-01-20
**Status**: DESIGN PROPOSAL

---

## 1. Purpose

This document series proposes a **kernel-driver architecture** for QMatSuite's engine integration layer. The goal is to separate stable "kernel" abstractions from engine-specific "driver" implementations, enabling:

1. **Explicit binding**: step_type → driver with no silent fallbacks
2. **Capabilities negotiation**: Engines declare what they support
3. **Versioned interface**: Breaking changes are manageable
4. **Reduced coupling**: Engine code concentrated in driver bundles

---

## 2. Current State Assessment

### 2.1 Supported Engines (7 total)

| Engine | Family | Primary Location | Recipe Pattern |
|--------|--------|------------------|----------------|
| Quantum ESPRESSO | `qe` | `src/quantumvitas/core/qe/` | Directory-state |
| VASP | `vasp` | `src/quantumvitas/engine/vasp_engine.py` | Per-step workdir |
| ORCA | `orca` | `src/quantumvitas/engine/orca_engine.py` | Strong-chain |
| PySCF | `pyscf` | `src/quantumvitas/engine/pyscf_engine.py` | Weak-chain |
| LAMMPS | `lammps` | `src/quantumvitas/engine/lammps_engine.py` | Per-step workdir |
| CP2K | `cp2k` | `src/quantumvitas/engine/cp2k_engine.py` | Per-step workdir |
| Wannier90 | `w90` | `src/quantumvitas/core/w90/` | Chain (QE-coupled) |

### 2.2 Architecture Patterns Observed

**Three distinct recipe patterns**:

1. **QE-Recipe (Directory-State)**: Shared `outdir`, prefix-based artifact namespacing
2. **ORCA/PySCF-Recipe (Chain-Based)**: Strong or weak chain linking, namespace folders
3. **VASP/LAMMPS/CP2K-Recipe (Per-Step Workdir)**: Isolated `raw/<step_ulid>/` directories

### 2.3 Critical Architectural Problems

**CRITICAL VULNERABILITY: Silent QE Fallback**

File: `src/quantumvitas/core/calc_identity.py` (lines 78-116)

```python
elif machine_type.startswith("pyscf_"):
    families.add("pyscf")
elif machine_type.startswith("w90_"):
    families.add("w90")
else:
    # Unknown prefix - could be legacy step type
    # Assume QE for backward compatibility  <-- DANGEROUS
    families.add("qe")
```

This pattern means **any misspelled or unknown step type defaults to Quantum ESPRESSO**, potentially causing cross-engine execution failures that are difficult to diagnose.

**Additional Problems**:

1. **Scattered hardcoded detection**: Engine sets duplicated across 5+ files
2. **Inconsistent dispatch**: Some paths use registry, others use hardcoded conditionals
3. **Implicit capabilities**: No formal declaration of what each engine supports
4. **Tight kernel coupling**: Engine-specific logic embedded in core execution paths

---

## 3. Proposed Solution: Kernel-Driver Model

### 3.1 Core Concept

```
┌─────────────────────────────────────────────────────────────┐
│                         KERNEL                               │
│  (Stable interfaces: Recipe, Handler, StepTypeSpec, etc.)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ QE Driver│    │VASP Driver│   │CP2K Driver│  ...
    └──────────┘    └──────────┘    └──────────┘
```

### 3.2 Driver Bundle Structure

Each engine provides a **driver bundle** containing:

```python
class EngineDriver(Protocol):
    """Interface that all engine drivers must implement."""

    # Identity
    engine_family: str
    engine_version: str
    driver_api_version: str

    # Registration
    def get_step_type_specs(self) -> list[StepTypeSpec]
    def get_recipe_class(self) -> type[BaseRecipe]
    def get_handler(self) -> Callable

    # Capabilities
    def get_capabilities(self) -> EngineCapabilities
    def get_preflight_requirements(self, step) -> list[PreflightRequirement]

    # Artifact patterns
    def get_artifact_patterns(self) -> dict[str, str]
    def find_latest_artifact(self, workdir, artifact_type) -> Path | None
```

### 3.3 Explicit Binding

**No more prefix inference**. All step types must be explicitly registered:

```python
# Current (dangerous)
if machine_type.startswith("vasp_"):
    engine = "vasp"
else:
    engine = "qe"  # Silent fallback

# Proposed (safe)
spec = STEP_TYPE_REGISTRY.get(machine_type)
if spec is None:
    raise UnknownStepTypeError(f"Step type '{machine_type}' not registered")
engine = spec.engine
```

---

## 4. Migration Strategy

### 4.1 Phased Approach

| Phase | Focus | Risk | Duration |
|-------|-------|------|----------|
| **Phase 1** | Extract driver protocol, keep existing code | Low | Foundation |
| **Phase 2** | Migrate one engine (VASP) to driver model | Medium | Validation |
| **Phase 3** | Migrate remaining engines | Medium | Expansion |
| **Phase 4** | Remove legacy dispatch paths | High | Cleanup |

### 4.2 Key Constraints

- **Backward compatibility**: Existing workflows must continue working
- **Incremental migration**: One engine at a time
- **Test coverage**: Each phase requires comprehensive testing
- **No big bang**: Parallel legacy + driver paths during transition

---

## 5. Document Index

| Document | Purpose |
|----------|---------|
| [01_engine_code_inventory.md](01_engine_code_inventory.md) | Complete map of engine-specific code |
| [02_kernel_touchpoints_audit.md](02_kernel_touchpoints_audit.md) | Where kernel code touches engines |
| [03_driver_model_spec.md](03_driver_model_spec.md) | Detailed driver interface specification |
| [04_migration_assessment.md](04_migration_assessment.md) | Migration strategy and risk analysis |
| [05_open_questions.md](05_open_questions.md) | Unresolved design decisions |

---

## 6. Key Metrics

### 6.1 Current State

- **7 engines** supported
- **60+ step types** registered
- **5+ files** with duplicated engine detection logic
- **3 recipe patterns** (directory-state, chain, per-step)
- **1 critical vulnerability** (silent QE fallback)

### 6.2 Target State

- **Single registration point** per engine (driver bundle)
- **Zero silent fallbacks** (explicit errors on unknown types)
- **Formal capabilities** declared per engine
- **Versioned driver API** for stability

---

## 7. Recommendation

**Proceed with driver architecture implementation**, prioritizing:

1. **Immediate**: Add explicit error for unknown step types (remove QE fallback)
2. **Short-term**: Define EngineDriver protocol and migrate VASP as pilot
3. **Medium-term**: Migrate remaining engines incrementally
4. **Long-term**: Remove all legacy dispatch paths

The current architecture has grown organically and contains dangerous implicit assumptions. The driver model provides a clear path to a more maintainable, safer system.
