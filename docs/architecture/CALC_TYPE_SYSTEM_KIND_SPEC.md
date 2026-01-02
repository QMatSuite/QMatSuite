# Calculation Type & System Kind Specification

**Version**: 1.0  
**Date**: 2026-01-02  
**Status**: Design Specification  
**Constitution Reference**: New Decision C (Calculation type/system kind and engine compatibility)

---

## 1. Overview

### 1.1 Problem Statement

QMatSuite currently allows calculations without explicit type constraints:
1. A calculation could theoretically mix incompatible engines (QE + PySCF)
2. Periodic and molecular systems have fundamentally different requirements
3. In-place conversion between calculation types could break workflows

### 1.2 Solution: Calc Type System

Introduce explicit constraints:
1. **system_kind** - Periodic vs molecular boundary conditions
2. **engine_group** - Compatible engine sets
3. **Immutability** - Calc type fixed at creation

---

## 2. System Kind

### 2.1 Definition

```python
class SystemKind(str, Enum):
    """Physical system boundary conditions."""
    
    PERIODIC = "periodic"     # 3D periodic (bulk, surface, 2D material)
    MOLECULAR = "molecular"   # Isolated molecule/cluster
    # Future: SLAB, WIRE for explicit 2D/1D periodicity
```

### 2.2 System Kind Properties

| Kind | Boundary | K-Points | Typical Engines |
|------|----------|----------|-----------------|
| `PERIODIC` | PBC in 3D | Required mesh/path | QE, Wannier90, PySCF-PBC |
| `MOLECULAR` | No lattice | N/A (molecular) | PySCF (gto.Mole), Gaussian |

### 2.3 Structure ↔ System Kind

System kind is determined by structure:
```python
def infer_system_kind(structure: Structure) -> SystemKind:
    """
    Infer system kind from structure.
    
    Rules:
    1. If structure has no lattice → MOLECULAR
    2. Otherwise → PERIODIC
    
    Note: PySCF molecular calculations use gto.Mole (no lattice).
    PySCF-PBC calculations use pbc.gto.Cell (with lattice) and are PERIODIC.
    """
    if not structure.has_lattice:
        return SystemKind.MOLECULAR
    
    return SystemKind.PERIODIC
```

**UI Suggestion**: For structures with large vacuum regions, the UI may suggest using `assume_isolated` in QE, but this does not change the system_kind classification.

---

## 3. Engine Compatibility Groups

### 3.1 Engine Group Definition

```python
class EngineGroup(str, Enum):
    """Compatible engine groups."""
    
    # Periodic solid-state DFT
    SOLID_STATE_DFT = "solid_state_dft"
    
    # Molecular quantum chemistry
    MOLECULAR_QC = "molecular_qc"
    
    # Machine learning potentials (future)
    ML_POTENTIAL = "ml_potential"
```

### 3.2 Engine ↔ Group Mapping

```python
ENGINE_GROUPS: Dict[str, EngineGroup] = {
    # Solid-state DFT engines
    "qe": EngineGroup.SOLID_STATE_DFT,
    "wannier90": EngineGroup.SOLID_STATE_DFT,
    "vasp": EngineGroup.SOLID_STATE_DFT,  # Future
    
    # Molecular QC engines
    "pyscf": EngineGroup.MOLECULAR_QC,
    "gaussian": EngineGroup.MOLECULAR_QC,  # Future
}
```

### 3.3 Compatibility Matrix

| System Kind | Engine Group | Compatible |
|-------------|--------------|------------|
| PERIODIC | SOLID_STATE_DFT | ✅ |
| PERIODIC | MOLECULAR_QC | ❌ |
| MOLECULAR | SOLID_STATE_DFT | ⚠️ (with assume_isolated) |
| MOLECULAR | MOLECULAR_QC | ✅ |

### 3.4 Within-Calculation Engine Mixing

**Allowed**:
- QE + Wannier90 in same calculation (both SOLID_STATE_DFT)
- Multiple QE executables (pw.x, dos.x, ph.x)

**Disallowed**:
- QE + PySCF in same calculation
- VASP + Gaussian in same calculation

---

## 4. Calculation Model Extension

### 4.1 Schema Changes

```python
@dataclass
class CalculationModel:
    """Calculation model with type constraints."""
    
    # Existing fields
    meta: ResourceMeta
    structure_id: Optional[str] = None
    mode: str = "normal"
    working_dir: str = "raw"
    steps: List[CalculationStepEntry] = field(default_factory=list)
    species_map: Optional[Dict[str, Any]] = None
    
    # NEW: Type constraints (immutable after creation)
    system_kind: Optional[SystemKind] = None  # Inferred from structure
    engine_group: Optional[EngineGroup] = None  # Inferred from first step
```

### 4.2 calculation.yaml Extension

```yaml
# calculation.yaml
meta:
  id: "01JGXYZ..."
  name: "Silicon SCF"
  slug: "si_scf"
  path: "calculations/si_scf"
  kind: "calculation"

structure_id: "01JGABC..."

# NEW: Type constraints
system_kind: periodic
engine_group: solid_state_dft

mode: normal
working_dir: raw

steps:
  - step_id: "01JGDEF..."
    type: scf
```

---

## 5. Immutability Rules

### 5.1 Creation-Time Locking

Once a calculation is created:
1. `system_kind` cannot be changed
2. `engine_group` cannot be changed
3. Steps can only use compatible engines

### 5.2 Enforcement Points

```python
def add_step_to_calculation(
    calculation: CalculationModel,
    step_type: str,
    step_engine: str,
) -> None:
    """Add step with engine compatibility check."""
    step_engine_group = ENGINE_GROUPS.get(step_engine)
    
    if calculation.engine_group is None:
        # First step sets the engine group
        calculation.engine_group = step_engine_group
    elif calculation.engine_group != step_engine_group:
        raise EngineCompatibilityError(
            f"Cannot add {step_engine} step to calculation with "
            f"engine_group={calculation.engine_group}"
        )
```

### 5.3 Conversion UX

If user wants to convert between types:
1. **Offer "Duplicate as..."** action
2. Create new calculation with new type
3. Copy structure reference
4. User must recreate steps (intentional friction)

---

## 6. Step Type ↔ Engine Mapping

### 6.1 Extended StepTypeSpec

```python
@dataclass(frozen=True)
class StepTypeSpec:
    """Step type specification with engine info."""
    
    id: str
    engine: str                    # Engine identifier
    engine_group: EngineGroup      # Derived from engine
    executable: str
    description: str
    
    # Existing fields
    accepts_presets: bool = False
    allowed_dimensions: FrozenSet[str] = field(default_factory=frozenset)
    requires_structure: bool = True
    requires_charge_density: bool = False
    produces_charge_density: bool = False
    
    # NEW: System kind compatibility
    allowed_system_kinds: FrozenSet[SystemKind] = field(
        default_factory=lambda: frozenset({SystemKind.PERIODIC, SystemKind.MOLECULAR})
    )
```

### 6.2 Step Type Examples

```python
_STEP_TYPES["scf"] = StepTypeSpec(
    id="scf",
    engine="qe",
    engine_group=EngineGroup.SOLID_STATE_DFT,
    executable="pw.x",
    description="Self-consistent field calculation",
    allowed_system_kinds=frozenset({SystemKind.PERIODIC, SystemKind.MOLECULAR}),
    # ... other fields
)

_STEP_TYPES["pyscf_rhf"] = StepTypeSpec(
    id="pyscf_rhf",
    engine="pyscf",
    engine_group=EngineGroup.MOLECULAR_QC,
    executable="python",  # Native Python
    description="Restricted Hartree-Fock",
    allowed_system_kinds=frozenset({SystemKind.MOLECULAR}),  # Only molecular!
    # ... other fields
)
```

---

## 7. UI Implications

### 7.1 Calculation Creation

When creating a new calculation:
1. User selects structure
2. System kind is inferred and displayed
3. Available workflow templates filtered by system kind
4. Engine group locked after first step added

### 7.2 Workflow Template Filtering

```python
def get_available_workflows(system_kind: SystemKind) -> List[WorkflowTemplate]:
    """Get workflows compatible with system kind."""
    return [
        wf for wf in all_workflows
        if wf.system_kind_compatible(system_kind)
    ]
```

| System Kind | Available Workflows |
|-------------|---------------------|
| PERIODIC | SCF, Bands, DOS, Phonon, Wannier90 |
| MOLECULAR | RHF, DFT Single Point, Geometry Opt |

### 7.3 Engine Compatibility Errors

When user attempts incompatible action:
```
❌ Cannot add PySCF step to periodic calculation
   
   This calculation uses QE (solid-state DFT).
   PySCF requires a molecular calculation.
   
   [Create New Molecular Calculation]
```

---

## 8. Validation Rules

### 8.1 Structure ↔ System Kind

```python
def validate_structure_system_kind(
    structure: Structure,
    system_kind: SystemKind,
) -> List[str]:
    """Validate structure is compatible with system kind."""
    warnings = []
    
    if system_kind == SystemKind.PERIODIC:
        if not structure.has_lattice:
            warnings.append("Periodic system requires lattice vectors")
    
    elif system_kind == SystemKind.MOLECULAR:
        if structure.has_lattice:
            warnings.append(
                "Molecular system should not have lattice vectors. "
                "Use PySCF gto.Mole (no lattice) for molecular calculations."
            )
    
    return warnings
```

### 8.2 Step ↔ Calculation Compatibility

```python
def validate_step_compatibility(
    step_type: str,
    calculation: CalculationModel,
) -> Tuple[bool, Optional[str]]:
    """Validate step can be added to calculation."""
    spec = get_step_type_spec(step_type)
    
    # Check engine group
    if calculation.engine_group and spec.engine_group != calculation.engine_group:
        return False, f"Step engine {spec.engine} incompatible with calculation"
    
    # Check system kind
    if calculation.system_kind not in spec.allowed_system_kinds:
        return False, f"Step {step_type} not compatible with {calculation.system_kind}"
    
    return True, None
```

---

## 9. Test Requirements

### 9.1 Unit Tests

```python
class TestSystemKindInference:
    """System kind inference tests."""
    
    def test_bulk_crystal_is_periodic(self):
        """Bulk crystal structure is PERIODIC."""
        si_bulk = Structure.from_file("Si_bulk.cif")
        assert infer_system_kind(si_bulk) == SystemKind.PERIODIC
    
    def test_isolated_molecule_is_molecular(self):
        """Molecule in large box is MOLECULAR."""
        h2o = Structure.from_file("H2O_in_box.xyz")
        assert infer_system_kind(h2o) == SystemKind.MOLECULAR


class TestEngineCompatibility:
    """Engine compatibility tests."""
    
    def test_qe_wannier90_compatible(self):
        """QE and Wannier90 can coexist."""
        calc = create_calculation(engine_group=EngineGroup.SOLID_STATE_DFT)
        add_step(calc, "scf", engine="qe")
        add_step(calc, "w90_main", engine="wannier90")  # Should succeed
    
    def test_qe_pyscf_incompatible(self):
        """QE and PySCF cannot coexist."""
        calc = create_calculation(engine_group=EngineGroup.SOLID_STATE_DFT)
        add_step(calc, "scf", engine="qe")
        
        with pytest.raises(EngineCompatibilityError):
            add_step(calc, "pyscf_rhf", engine="pyscf")


class TestImmutability:
    """Type immutability tests."""
    
    def test_system_kind_immutable(self):
        """System kind cannot be changed after creation."""
        calc = create_calculation(system_kind=SystemKind.PERIODIC)
        
        with pytest.raises(ImmutableFieldError):
            calc.system_kind = SystemKind.MOLECULAR
    
    def test_engine_group_immutable(self):
        """Engine group cannot be changed after first step."""
        calc = create_calculation()
        add_step(calc, "scf", engine="qe")
        
        with pytest.raises(ImmutableFieldError):
            calc.engine_group = EngineGroup.MOLECULAR_QC
```

### 9.2 CI Gates

```yaml
- name: Type System Tests
  run: pytest tests/unit/test_calc_type.py -v

- name: Engine Compatibility Tests
  run: pytest tests/unit/test_engine_compat.py -v
```

---

## 10. Implementation Notes

### 10.1 File Changes

| File | Changes |
|------|---------|
| `core/models.py` | Add `system_kind`, `engine_group` fields |
| `workflow/registry.py` | Add `engine_group`, `allowed_system_kinds` to StepTypeSpec |
| `calculation/calculation.py` | Add validation hooks |
| `project/model.py` | Add creation-time type inference |

### 10.2 Migration

Existing calculations without `system_kind`/`engine_group`:
1. Infer from structure (if available)
2. Infer from existing steps (first step's engine)
3. Default to PERIODIC + SOLID_STATE_DFT for QE projects

### 10.3 Future Extensions

| Extension | Description |
|-----------|-------------|
| SLAB system_kind | Explicit 2D periodic for surfaces |
| WIRE system_kind | Explicit 1D periodic for nanowires |
| HYBRID engine_group | QM/MM combinations (future) |

---

## 11. Cross-Engine Data Flow

### 11.1 Wannier90 + QE Data Dependencies

```
[QE] scf
  ↓ (charge density)
[QE] nscf
  ↓ (wavefunctions)
[W90] w90_preproc ────────────────┐
  ↓ (seedname.nnkp)               │
[QE] pw2wannier90 ←───────────────┘
  ↓ (seedname.mmn, .amn, .eig)
[W90] w90_main
  ↓ (seedname.chk, seedname_hr.dat)
[W90] postw90 (optional)
```

### 11.2 Data Dependency Declaration

```python
CROSS_ENGINE_DEPENDENCIES = {
    "pw2wannier90": {
        "requires_from": {
            "qe:nscf": ["wavefunctions"],
            "wannier90:w90_preproc": ["seedname.nnkp"],
        },
        "produces": ["seedname.mmn", "seedname.amn", "seedname.eig"],
    },
    "w90_main": {
        "requires_from": {
            "qe:pw2wannier90": ["seedname.mmn", "seedname.amn", "seedname.eig"],
        },
        "produces": ["seedname.chk", "seedname_hr.dat"],
    },
}
```

---

*This specification is implementation-ready. PR can proceed.*

