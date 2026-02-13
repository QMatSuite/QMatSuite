# Engine Integration Constitution

**Version**: 1.0
**Status**: SPECIFICATION
**Parent Law**: `CONSTITUTION.md` §17
**Scope**: Defines inviolable invariants for engine integration architecture

---

## 1. Purpose

This document establishes the constitutional invariants for QMatSuite's engine integration layer. These rules are **non-negotiable** and must be enforced by tests, code review, and CI.

---

## 2. Constitutional Invariants

### INV-1: No Guessing (Explicit Registry Only)

**Statement**: All routing decisions must be explicit lookups against registered mappings. No inference, no pattern matching, no fallbacks.

**Prohibitions**:
```python
# PROHIBITED: prefix-based inference
if step_type.startswith("vasp_"):
    engine = "vasp"

# PROHIBITED: silent fallback
engine = mapping.get(step_type, "qe")  # defaults to QE

# PROHIBITED: pattern matching
if "scf" in step_type:
    ...
```

**Required pattern**:
```python
# REQUIRED: explicit lookup with hard error
engine = REGISTRY.get_engine_for_step_type(step_type)
# raises UnknownStepTypeError if not found
```

**Testable assertion**: Any code path that determines engine/handler/recipe from step_type must use explicit registry lookup and raise on miss.

---

### INV-2: Hard Error on Unknown

**Statement**: Unknown step types, engine families, or mappings must raise an error with a helpful message listing known alternatives.

**Required error format**:
```
UnknownStepTypeError: Step type 'vaps_scf' is not registered.
Did you mean: vasp_scf, vasp_relax, vasp_md?
Known step types: pw_scf, pw_relax, vasp_scf, vasp_relax, ...
```

**Prohibitions**:
- Returning `None` and letting caller handle
- Returning a default value
- Silently skipping the step
- Logging a warning and continuing

**Testable assertion**: `pytest.raises(UnknownStepTypeError)` for any unregistered type.

---

### INV-3: Explicit Three-Level Mapping

**Statement**: The routing chain must be explicitly defined at each level:

| Level | Mapping | Example |
|-------|---------|---------|
| **L1** | GEN → SPEC | `(vasp, GEN_SCF) → vasp_scf` |
| **L2** | SPEC → Engine | `vasp_scf → vasp` |
| **L3** | Engine → Driver | `vasp → VASPDriver` |

Each mapping is a discrete registry lookup. No level may infer from another.

**Data flow**:
```
User input: GEN_SCF + engine_hint="vasp"
    │
    ▼ [L1: MATERIALIZATION_REGISTRY]
machine_type: vasp_scf
    │
    ▼ [L2: STEP_TYPE_REGISTRY]
engine_family: vasp
    │
    ▼ [L3: DRIVER_REGISTRY]
driver: VASPDriver
    │
    ▼ [driver provides]
handler, recipe, capabilities
```

**Testable assertion**: Each registry is independently queryable and returns explicit errors for unknown keys.

---

### INV-4: No Kernel Edits to Add Engines

**Statement**: Adding a new engine or new step types requires ONLY:
1. Creating a driver bundle (new directory under `drivers/`)
2. Registering the driver (call `DriverRegistry.register()`)
3. Adding tests

**Prohibited modifications** when adding an engine:
- `handlers.py` (kernel aggregator)
- `recipes.py` (kernel aggregator)
- `calc_identity.py` (kernel routing)
- `generalized_steps.py` (kernel mapping)
- `structure_steps.py` (kernel logic)
- `step_done.py` (kernel policy)
- Any file outside `drivers/<engine_name>/` and `tests/`

**Testable assertion**: CI check that PRs adding a new engine modify only `drivers/` and `tests/`.

---

### INV-5: Driver Self-Containment

**Statement**: All engine-specific logic must reside within the driver bundle. The kernel contains only:
- Abstract protocols/interfaces
- Registry infrastructure
- Dispatch machinery (thin wrappers that delegate to drivers)

**Driver bundle contents**:
```
drivers/<engine>/
├── __init__.py      # Registration
├── driver.py        # EngineDriver implementation
├── handler.py       # Step execution logic
├── recipe.py        # Recipe implementation
├── writer.py        # Input file generation (optional)
├── parser.py        # Output parsing (optional)
└── ...              # Engine-specific utilities
```

**Prohibited in kernel**:
- Engine-specific constants (e.g., `VASP_STEP_TYPES = {...}`)
- Engine-specific conditionals (e.g., `if engine == "vasp":`)
- Engine-specific file paths or patterns

**Testable assertion**: `grep -r "vasp\|orca\|lammps" src/quantumvitas/core/` returns zero matches (excluding registry/protocol files).

---

### INV-6: Auditable Routing

**Statement**: Every routing decision must be traceable and loggable for debugging.

**Required**: Debug logging at each routing level:
```
DEBUG: L1 materialization: (vasp, GEN_SCF) → vasp_scf
DEBUG: L2 step type lookup: vasp_scf → engine=vasp
DEBUG: L3 driver lookup: vasp → VASPDriver
DEBUG: Handler dispatch: VASPDriver.get_handler()
```

**Testable assertion**: Routing paths are logged at DEBUG level; logs capture full chain for any step execution.

---

## 3. Kernel-Driver Boundary

### 3.1 Boundary Definition

```
┌─────────────────────────────────────────────────────────────────┐
│                           KERNEL                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Protocols  │  │  Registries │  │  Dispatch   │              │
│  │  (abstract) │  │  (storage)  │  │  (routing)  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  NO ENGINE-SPECIFIC CODE                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ EngineDriver protocol
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │ QE Driver│      │VASP Driver│     │CP2K Driver│
   │ (bundle) │      │ (bundle)  │     │ (bundle)  │
   └──────────┘      └──────────┘      └──────────┘
```

### 3.2 What Lives Where

| Component | Location | Rationale |
|-----------|----------|-----------|
| `EngineDriver` protocol | Kernel | Defines contract |
| `DriverRegistry` | Kernel | Storage infrastructure |
| `StepTypeSpec` dataclass | Kernel | Data structure |
| Step type definitions | Driver | Engine declares its types |
| Handler implementation | Driver | Engine-specific execution |
| Recipe implementation | Driver | Engine-specific staging |
| Materialization mappings | Driver | Engine declares GEN→SPEC |
| Capability declarations | Driver | Engine declares features |

### 3.3 Cross-Cutting Concerns

Some concerns span kernel and drivers:

| Concern | Kernel Responsibility | Driver Responsibility |
|---------|----------------------|----------------------|
| Preflight checks | Invoke checker, report errors | Declare requirements |
| Workdir management | Apply policy | Declare policy |
| Artifact discovery | Provide utilities | Declare patterns |
| Logging | Framework | Use framework |

---

## 4. Enforcement Mechanisms

### 4.1 CI Gates

| Gate | Trigger | Assertion |
|------|---------|-----------|
| `no-prefix-matching` | Every PR | No `startswith` on step_type in kernel |
| `no-silent-fallback` | Every PR | No `.get(..., default)` for routing |
| `driver-isolation` | PR adds engine | Only `drivers/` and `tests/` modified |
| `unknown-type-errors` | Every PR | Tests assert `UnknownStepTypeError` raised |

### 4.2 Code Review Checklist

For any PR touching engine integration:

- [ ] No prefix-based inference added
- [ ] No silent fallbacks added
- [ ] New step types registered via driver
- [ ] Unknown types raise helpful errors
- [ ] Routing is logged at DEBUG level

### 4.3 Architectural Decision Records

Any proposal to violate these invariants requires:
1. Written justification
2. Team review
3. Explicit exception documented in ADR
4. Sunset plan for the exception

---

## 5. Rationale

### Why these invariants?

| Invariant | Problem it prevents |
|-----------|---------------------|
| No guessing | Cross-engine execution bugs, silent failures |
| Hard error | Hours of debugging "why did my VASP job run QE?" |
| Explicit mapping | Unmaintainable spaghetti routing |
| No kernel edits | Merge conflicts, kernel bloat, review burden |
| Self-containment | Engine bugs leak into kernel |
| Auditable routing | "It worked yesterday" debugging |

### Historical context

The codebase evolved organically with:
- Prefix-based engine detection (`startswith("vasp_")`)
- Silent QE fallback for unknown types
- Hardcoded step type sets in 5+ kernel files
- 1400+ line `handlers.py` aggregator

These patterns led to:
- Silent cross-engine execution
- Difficult debugging
- Merge conflicts on shared files
- Fear of adding new engines

---

## 6. Amendment Process

This constitution may be amended by:
1. RFC document with rationale
2. Impact analysis on existing code
3. Migration plan for affected code
4. Team consensus
5. Version bump to this document

Amendments are tracked in the document header.
