# StepRole Inference Specification

**Version**: 1.0  
**Date**: 2026-01-02  
**Status**: Design Specification  
**Constitution Reference**: New Decision A (Role-based applicability)

---

## 1. Overview

### 1.1 Problem Statement

Certain step types (notably `nscf`) can serve different physical purposes depending on their position in the step graph:
- An `nscf` followed by `dos` computes a dense k-mesh for DOS
- An `nscf` followed by `bands_pw` or used for band interpolation has different k-point requirements

Currently, `applies_to_step_types` treats all instances of a step type identically. This prevents:
- Applying different precision k-mesh multipliers to `nscf_dos` vs `nscf_bands`
- Context-aware preset defaults

### 1.2 Solution: StepRole

Introduce a compile-time concept **StepRole** that is:
1. **Inferred deterministically** from the step dependency graph (topology)
2. **A pure function** - no persisted truth, computed at runtime
3. **An input feature** for preset applicability matching (not a second overlay)

**Key Constraint**: Role is NOT persisted in step.yml. It may be logged in debug/provenance artifacts only.

---

## 2. StepRole Enumeration

### 2.1 Minimal Role Set

```python
class StepRole(str, Enum):
    """Role of a step in the calculation topology."""
    
    # Default role - step has no special context
    DEFAULT = "default"
    
    # NSCF feeding into DOS calculation
    NSCF_DOS = "nscf_dos"
    
    # NSCF feeding into bands post-processing (not bands_pw which is direct)
    NSCF_BANDS = "nscf_bands"
    
    # NSCF feeding into Wannier90 (w90_preproc/pw2wannier90)
    NSCF_WANNIER = "nscf_wannier"
    
    # SCF that precedes relaxation (used for initial guess)
    SCF_PRERELAX = "scf_prerelax"
    
    # Final SCF after relaxation
    SCF_POSTRELAX = "scf_postrelax"
```

### 2.2 Role Assignment Rules

| Step Type | Successor Step(s) | Assigned Role |
|-----------|-------------------|---------------|
| `nscf` | `dos`, `projwfc` | `NSCF_DOS` |
| `nscf` | `bands` (post-proc) | `NSCF_BANDS` |
| `nscf` | `w90_preproc`, `pw2wannier90` | `NSCF_WANNIER` |
| `nscf` | no successors or mixed | `DEFAULT` |
| `scf` | `relax`, `vc-relax` | `SCF_PRERELAX` |
| `scf` | follows `relax`/`vc-relax` | `SCF_POSTRELAX` |
| any other | - | `DEFAULT` |

### 2.3 Conflict Resolution

If a step would need multiple roles (e.g., a single `nscf` consumed by both DOS and bands):
1. **Preferred**: Split into two separate `nscf` steps
2. **Fallback**: Assign `DEFAULT` role (most general)
3. **Error condition**: If truly incompatible requirements, emit warning

---

## 3. Inference Algorithm

### 3.1 Interface

```python
def infer_step_roles(
    steps: List[StepInfo],
    dependencies: Dict[str, List[str]],  # step_id -> list of successor step_ids
) -> Dict[str, StepRole]:
    """
    Infer roles for all steps based on topology.
    
    Args:
        steps: List of step info (id, step_type)
        dependencies: Forward dependency graph (step produces data for successors)
        
    Returns:
        Dict mapping step_id -> StepRole
    
    Note: This is a pure function. It does not read or write any files.
    """
```

### 3.2 Algorithm

```python
def infer_step_roles(steps, dependencies):
    result = {}
    step_type_map = {s.id: s.step_type for s in steps}
    
    for step in steps:
        step_id = step.id
        step_type = step.step_type
        successors = dependencies.get(step_id, [])
        successor_types = {step_type_map.get(s) for s in successors}
        
        # Default role
        role = StepRole.DEFAULT
        
        # NSCF role inference
        if step_type == "nscf":
            if successor_types & {"dos", "projwfc"}:
                role = StepRole.NSCF_DOS
            elif successor_types & {"bands"}:
                role = StepRole.NSCF_BANDS
            elif successor_types & {"w90_preproc", "pw2wannier90"}:
                role = StepRole.NSCF_WANNIER
            # If mixed successors, keep DEFAULT
        
        # SCF role inference (based on predecessors and successors)
        elif step_type == "scf":
            if successor_types & {"relax", "vc-relax"}:
                role = StepRole.SCF_PRERELAX
            # Check if preceded by relaxation
            for other_step in steps:
                if step_id in dependencies.get(other_step.id, []):
                    if other_step.step_type in {"relax", "vc-relax"}:
                        role = StepRole.SCF_POSTRELAX
                        break
        
        result[step_id] = role
    
    return result
```

### 3.3 Complexity

- **Time**: O(n × m) where n = number of steps, m = average successors
- **Space**: O(n)
- **Note**: For typical workflows (< 10 steps), this is negligible

---

## 4. ParamSpace Integration

### 4.1 Extended Applicability

Extend `ParamSpaceVariant` to include role constraints:

```python
@dataclass(frozen=True)
class ParamSpaceVariant:
    name: str
    dimension: str
    space: ParamSpace
    applies_to_step_types: FrozenSet[str]
    
    # NEW: Optional role filter
    # If None or empty: matches all roles for the step_type
    # If set: only matches if step role is in this set
    applies_to_roles: Optional[FrozenSet[StepRole]] = None
```

### 4.2 Matching Logic Update

```python
def variant_matches(variant: ParamSpaceVariant, step_type: str, role: StepRole) -> bool:
    """Check if variant applies to this step type and role."""
    # Must match step type
    if step_type not in variant.applies_to_step_types:
        return False
    
    # If no role filter, matches all roles
    if variant.applies_to_roles is None:
        return True
    
    # Must match role
    return role in variant.applies_to_roles
```

### 4.3 Example Variant Definitions

```python
# Precision variant for NSCF in DOS workflow
# Uses 1.5x k-mesh multiplier
PRECISION_NSCF_DOS_VARIANT = ParamSpaceVariant(
    name="PRECISION_NSCF_DOS",
    dimension="precision",
    space=build_precision_nscf_dos_space(),
    applies_to_step_types=frozenset({"nscf"}),
    applies_to_roles=frozenset({StepRole.NSCF_DOS}),
)

# Precision variant for NSCF in Wannier workflow
# Uses 1.0x k-mesh (uniform grid required)
PRECISION_NSCF_WANNIER_VARIANT = ParamSpaceVariant(
    name="PRECISION_NSCF_WANNIER",
    dimension="precision",
    space=build_precision_nscf_wannier_space(),
    applies_to_step_types=frozenset({"nscf"}),
    applies_to_roles=frozenset({StepRole.NSCF_WANNIER}),
)

# General NSCF variant (default role)
PRECISION_NSCF_DEFAULT_VARIANT = ParamSpaceVariant(
    name="PRECISION_NSCF_DEFAULT",
    dimension="precision",
    space=build_precision_nscf_default_space(),
    applies_to_step_types=frozenset({"nscf"}),
    applies_to_roles=frozenset({StepRole.DEFAULT, StepRole.NSCF_BANDS}),
)
```

---

## 5. UI Integration

### 5.1 Role Display

The UI may display inferred role as informational chip:
- "NSCF (for DOS)" 
- "SCF (post-relaxation)"

This is Info, not Truth - it can change if dependencies change.

### 5.2 No Role Editing

Users cannot directly set roles. Roles are inferred from:
1. Workflow template selection
2. Step dependency graph
3. Manual step addition/removal

---

## 6. Test Requirements

### 6.1 Unit Tests

```python
class TestRoleInference:
    """Role inference algorithm tests."""
    
    def test_single_scf_default_role(self):
        """Single SCF step has DEFAULT role."""
        steps = [StepInfo(id="1", step_type="scf")]
        deps = {}
        roles = infer_step_roles(steps, deps)
        assert roles["1"] == StepRole.DEFAULT
    
    def test_nscf_dos_workflow(self):
        """NSCF followed by DOS has NSCF_DOS role."""
        steps = [
            StepInfo(id="1", step_type="scf"),
            StepInfo(id="2", step_type="nscf"),
            StepInfo(id="3", step_type="dos"),
        ]
        deps = {"1": ["2"], "2": ["3"]}
        roles = infer_step_roles(steps, deps)
        assert roles["2"] == StepRole.NSCF_DOS
    
    def test_nscf_wannier_workflow(self):
        """NSCF followed by pw2wannier90 has NSCF_WANNIER role."""
        steps = [
            StepInfo(id="1", step_type="scf"),
            StepInfo(id="2", step_type="nscf"),
            StepInfo(id="3", step_type="w90_preproc"),
            StepInfo(id="4", step_type="pw2wannier90"),
        ]
        deps = {"1": ["2"], "2": ["4"], "3": ["4"]}
        roles = infer_step_roles(steps, deps)
        assert roles["2"] == StepRole.NSCF_WANNIER
    
    def test_scf_postrelax_role(self):
        """SCF following vc-relax has SCF_POSTRELAX role."""
        steps = [
            StepInfo(id="1", step_type="vc-relax"),
            StepInfo(id="2", step_type="scf"),
        ]
        deps = {"1": ["2"]}
        roles = infer_step_roles(steps, deps)
        assert roles["2"] == StepRole.SCF_POSTRELAX
    
    def test_mixed_successors_default_role(self):
        """NSCF with mixed successors gets DEFAULT role."""
        steps = [
            StepInfo(id="1", step_type="scf"),
            StepInfo(id="2", step_type="nscf"),
            StepInfo(id="3", step_type="dos"),
            StepInfo(id="4", step_type="bands"),  # Post-proc bands
        ]
        deps = {"1": ["2"], "2": ["3", "4"]}
        roles = infer_step_roles(steps, deps)
        assert roles["2"] == StepRole.DEFAULT  # Cannot be both DOS and BANDS
```

### 6.2 Contract Tests

```python
class TestVariantRoleMatching:
    """Variant role matching contract tests."""
    
    def test_role_variant_matches_only_specified_role(self):
        """Variant with role filter only matches that role."""
        variant = PRECISION_NSCF_DOS_VARIANT
        
        assert variant_matches(variant, "nscf", StepRole.NSCF_DOS) is True
        assert variant_matches(variant, "nscf", StepRole.DEFAULT) is False
        assert variant_matches(variant, "nscf", StepRole.NSCF_WANNIER) is False
    
    def test_variant_without_role_matches_all(self):
        """Variant without role filter matches all roles."""
        variant = ParamSpaceVariant(
            name="TEST",
            dimension="test",
            space=...,
            applies_to_step_types=frozenset({"nscf"}),
            applies_to_roles=None,  # No role filter
        )
        
        assert variant_matches(variant, "nscf", StepRole.DEFAULT) is True
        assert variant_matches(variant, "nscf", StepRole.NSCF_DOS) is True
        assert variant_matches(variant, "nscf", StepRole.NSCF_WANNIER) is True
```

### 6.3 CI Gate

Add to CI:
```yaml
- name: Role Inference Tests
  run: pytest tests/unit/test_role_inference.py -v
  
- name: Variant Role Matching Tests  
  run: pytest tests/unit/test_variants_registry.py::TestVariantRoleMatching -v
```

---

## 7. Implementation Notes

### 7.1 File Locations

| New File | Purpose |
|----------|---------|
| `src/quantumvitas/workflow/role_inference.py` | Role enum and inference algorithm |
| `tests/unit/test_role_inference.py` | Role inference tests |

### 7.2 Migration

1. Role inference is additive - no breaking changes
2. Existing variants continue to work (no role filter = match all)
3. New role-specific variants can be added incrementally

### 7.3 Not Persisted

Per Constitution requirement:
- Role is computed at runtime
- Never written to step.yml
- May appear in debug logs or provenance artifacts

---

## 8. Future Extensions

### 8.1 Additional Roles

As new workflows are added, roles may expand:
- `PH_DFPT` vs `PH_GAMMA` for phonon calculations
- `EPW_COARSE` vs `EPW_FINE` for electron-phonon

### 8.2 User-Specified Roles

For advanced users, consider allowing explicit role hints in workflow templates (not step.yml):
```yaml
# workflow_template.yaml (not persisted, UI-only)
steps:
  - step_type: nscf
    role_hint: nscf_dos  # Overrides inference
```

This would be Info-layer only, not Truth.

---

*This specification is implementation-ready. PR can proceed.*

