# PySCF Integration Specification

**Version**: 1.0  
**Date**: 2026-01-02  
**Status**: Implementation Ready  
**Constitution Reference**: Invariants T1-T5, E1-E3, Decision C (system_kind enforcement)

---

## 1. Overview

### 1.1 Goal

Integrate PySCF as the first molecular quantum chemistry engine in QMatSuite:
- Enable isolated molecule calculations (no periodic boundary conditions)
- Add Python-native execution (no external binaries)
- Maintain strict separation from existing QE/PBC workflows

### 1.2 Constraints (from Constitution)

| ID | Constraint | Constitution Ref |
|----|------------|-----------------|
| C1 | `step.yml` is the only executable truth | §10.1.1 |
| C2 | Do NOT break existing PBC/QE workflows | This spec |
| C3 | Preset is the only writer to step parameters | §10.3.3 |
| C4 | Engine resolution follows two-state model | §9.4.2 |
| C5 | Calc system_kind is immutable after creation | Decision C |

### 1.3 Molecular vs Periodic Detection Rule

**Simple rule**: A system is MOLECULAR if and only if it has **no lattice vectors**.

```python
def detect_system_kind(structure: dict) -> SystemKind:
    """
    Detect system kind from structure.
    
    Rules:
    1. If structure has lattice/cell → PERIODIC
    2. If structure has no lattice/cell → MOLECULAR
    
    No vacuum heuristics. No magic thresholds.
    """
    if has_lattice(structure):
        return SystemKind.PERIODIC
    return SystemKind.MOLECULAR
```

This ensures:
- Existing QE periodic structures remain periodic
- New molecular structures (atoms + coords, no cell) are molecular
- Clear separation, no ambiguity

---

## 2. Step Types

### 2.1 PYSCF_SCF (MVP)

Single-point Hartree-Fock or DFT calculation.

```python
_STEP_TYPES["pyscf_scf"] = StepTypeSpec(
    id="pyscf_scf",
    engine="pyscf",
    engine_group=EngineGroup.MOLECULAR_QC,
    executable="python",  # Python-native, no binary
    description="PySCF single-point calculation (HF/DFT)",
    accepts_presets=False,  # MVP: no presets yet
    allowed_dimensions=frozenset(),
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    allowed_system_kinds=frozenset({SystemKind.MOLECULAR}),
)
```

### 2.2 Future Step Types (Post-MVP)

| Step Type | Description | Status |
|-----------|-------------|--------|
| `pyscf_geomopt` | Geometry optimization | Future |
| `pyscf_mp2` | MP2 single point | Future |
| `pyscf_ccsd` | CCSD/CCSD(T) | Future |
| `pyscf_tddft` | TD-DFT excited states | Future |

---

## 3. PySCF Engine Adapter

### 3.1 Architecture

```python
class PySCFEngine(Engine):
    """
    PySCF engine adapter.
    
    Unlike QE, PySCF is Python-native:
    - No subprocess execution
    - Direct Python API calls
    - No input files (parameters from step.yml)
    
    Graceful degradation if pyscf not installed.
    """
    
    name = "pyscf"
    
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self._pyscf_available = self._check_pyscf()
    
    def _check_pyscf(self) -> bool:
        """Check if pyscf is importable."""
        try:
            import pyscf
            return True
        except ImportError:
            return False
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        """Run PySCF calculation."""
        if not self._pyscf_available:
            return StepResult(
                step_type="pyscf_scf",
                input_file=working_dir / "pyscf_input.py",
                success=False,
                error=(
                    "PySCF is not installed. Please install with:\n"
                    "  pip install pyscf"
                ),
            )
        
        # Extract parameters from step
        params = step.parameters if hasattr(step, 'parameters') else {}
        
        # Build molecule and run calculation
        return self._run_pyscf_scf(params, working_dir)
```

### 3.2 Execution Model

PySCF execution differs from QE:

| Aspect | QE | PySCF |
|--------|----|----|
| Execution | subprocess | Python API |
| Input | .in text file | Python dict from step.yml |
| Output | .out text file | results.json |
| Binary | pw.x etc. | None (Python-native) |

### 3.3 Parameter Mapping

```python
# step.yml parameters → PySCF API
PYSCF_PARAM_MAP = {
    # Molecule
    "atoms": lambda v: v,  # List of {element, x, y, z}
    "charge": lambda v: int(v),
    "spin": lambda v: int(v),  # 2S (PySCF convention)
    "unit": lambda v: v,  # "Angstrom" or "Bohr"
    "basis": lambda v: v,  # Basis set name
    
    # Method
    "method": lambda v: v,  # "rhf", "uhf", "rks", "uks"
    "xc": lambda v: v,  # DFT functional (e.g., "pbe", "b3lyp")
    
    # Convergence
    "max_cycle": lambda v: int(v),
    "conv_tol": lambda v: float(v),
}
```

---

## 4. Molecular System Schema

### 4.1 Structure Representation

For molecular systems, we use a simplified structure without lattice:

```yaml
# Molecular structure in step.yml (embedded)
structure:
  atoms:
    - element: O
      x: 0.0
      y: 0.0
      z: 0.117790
    - element: H
      x: 0.0
      y: 0.755453
      z: -0.471161
    - element: H
      x: 0.0
      y: -0.755453
      z: -0.471161
  charge: 0
  spin: 0  # 2S (singlet)
  unit: Angstrom
```

### 4.2 Structure in Demo YAML

For demo projects, molecular structures are stored inline (no separate JSON file):

```yaml
# Demo project with molecular system
structures:
  - meta:
      id: 01JG...
      name: H2O
      slug: h2o
      path: structures/h2o.json
      kind: structure
    data:
      # No @module/@class for pymatgen - simple dict
      charge: 0
      atoms:
        - element: O
          coords: [0.0, 0.0, 0.117790]
        - element: H
          coords: [0.0, 0.755453, -0.471161]
        - element: H
          coords: [0.0, -0.755453, -0.471161]
      unit: Angstrom
      # NO lattice field - this makes it MOLECULAR
```

### 4.3 Pymatgen Compatibility

For UI compatibility, molecular structures can also use pymatgen Molecule:

```python
from pymatgen.core import Molecule

# Molecule has no lattice (unlike Structure)
mol = Molecule(
    species=["O", "H", "H"],
    coords=[
        [0.0, 0.0, 0.117790],
        [0.0, 0.755453, -0.471161],
        [0.0, -0.755453, -0.471161],
    ]
)
```

---

## 5. PySCF Execution Flow

### 5.1 Step Execution

```python
def _run_pyscf_scf(self, params: dict, working_dir: Path) -> StepResult:
    """Execute PySCF SCF calculation."""
    import time
    from pyscf import gto, scf, dft
    
    start_time = time.time()
    
    # 1. Build molecule
    mol = self._build_mole(params)
    
    # 2. Setup SCF/DFT
    method = params.get("method", "rhf").lower()
    
    if method in ("rhf", "hf"):
        mf = scf.RHF(mol)
    elif method == "uhf":
        mf = scf.UHF(mol)
    elif method in ("rks", "dft"):
        mf = dft.RKS(mol)
        mf.xc = params.get("xc", "pbe")
    elif method == "uks":
        mf = dft.UKS(mol)
        mf.xc = params.get("xc", "pbe")
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # 3. Convergence settings
    mf.max_cycle = params.get("max_cycle", 50)
    mf.conv_tol = params.get("conv_tol", 1e-9)
    
    # 4. Run SCF
    try:
        energy = mf.kernel()
        converged = mf.converged
    except Exception as e:
        return StepResult(
            step_type="pyscf_scf",
            input_file=working_dir / "pyscf_input.py",
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )
    
    # 5. Extract results
    mo_energies = mf.mo_energy.tolist()
    mo_occ = mf.mo_occ.tolist()
    
    # Find HOMO/LUMO
    homo_idx = None
    lumo_idx = None
    for i, occ in enumerate(mo_occ):
        if occ > 0:
            homo_idx = i
        elif lumo_idx is None:
            lumo_idx = i
            break
    
    homo_energy = mo_energies[homo_idx] if homo_idx is not None else None
    lumo_energy = mo_energies[lumo_idx] if lumo_idx is not None else None
    gap = (lumo_energy - homo_energy) if (homo_energy and lumo_energy) else None
    
    results = {
        "energy": energy,
        "converged": converged,
        "mo_energies": mo_energies,
        "mo_occupations": mo_occ,
        "homo_index": homo_idx,
        "lumo_index": lumo_idx,
        "homo_energy": homo_energy,
        "lumo_energy": lumo_energy,
        "gap": gap,
        "gap_ev": gap * 27.2114 if gap else None,  # Hartree to eV
    }
    
    # 6. Write results.json
    results_file = working_dir / "results.json"
    import json
    results_file.write_text(json.dumps(results, indent=2))
    
    return StepResult(
        step_type="pyscf_scf",
        input_file=working_dir / "pyscf_input.py",
        output_file=results_file,
        success=converged,
        return_code=0 if converged else 1,
        execution_time=time.time() - start_time,
        parsed_output=results,
    )

def _build_mole(self, params: dict):
    """Build PySCF Mole object from parameters."""
    from pyscf import gto
    
    atoms = params.get("atoms", [])
    unit = params.get("unit", "Angstrom")
    charge = params.get("charge", 0)
    spin = params.get("spin", 0)
    basis = params.get("basis", "sto-3g")
    
    # Build atom string for PySCF
    atom_str = ""
    for atom in atoms:
        element = atom.get("element", atom.get("symbol", "X"))
        x = atom.get("x", atom.get("coords", [0, 0, 0])[0])
        y = atom.get("y", atom.get("coords", [0, 0, 0])[1])
        z = atom.get("z", atom.get("coords", [0, 0, 0])[2])
        atom_str += f"{element} {x} {y} {z}; "
    
    mol = gto.Mole()
    mol.atom = atom_str.strip("; ")
    mol.basis = basis
    mol.charge = charge
    mol.spin = spin
    mol.unit = unit
    mol.build()
    
    return mol
```

---

## 6. Demo Project

### 6.1 Water Single Point (H2O RHF)

**File**: `resources/demo_projects/water_pyscf_scf.yml`

```yaml
version: 1
project:
  meta:
    id: 01PYSCFH2ODEMOULID000000
    name: Water PySCF SCF
    slug: water-pyscf-scf
    path: .
    kind: project
  settings: {}

structures:
  - meta:
      id: 01PYSCFH2OSTRUCT00000000
      name: H2O
      slug: h2o
      path: structures/h2o.json
      kind: structure
    data:
      charge: 0
      spin: 0
      atoms:
        - element: O
          coords: [0.0, 0.0, 0.117790]
        - element: H
          coords: [0.0, 0.755453, -0.471161]
        - element: H
          coords: [0.0, -0.755453, -0.471161]
      unit: Angstrom

calculations:
  - meta:
      id: 01PYSCFH2OCALC000000000
      name: H2O RHF Single Point
      slug: h2o-rhf
      path: calculations/h2o-rhf
      kind: calculation
    mode: normal
    working_dir: raw
    system_kind: molecular
    engine_group: molecular_qc
    structure_id: 01PYSCFH2OSTRUCT00000000
    steps:
      - meta:
          id: 01PYSCFH2OSTEP000000000
          name: pyscf_scf
          slug: pyscf-scf
          path: calculations/h2o-rhf/steps/pyscf_scf.step.yaml
          kind: step
        step_type: pyscf_scf
        parameters:
          method: rhf
          basis: 6-31g
          charge: 0
          spin: 0
          max_cycle: 50
          conv_tol: 1.0e-9
          atoms:
            - element: O
              x: 0.0
              y: 0.0
              z: 0.117790
            - element: H
              x: 0.0
              y: 0.755453
              z: -0.471161
            - element: H
              x: 0.0
              y: -0.755453
              z: -0.471161
          unit: Angstrom

meta:
  id: water_pyscf_scf_demo
  title: Water PySCF RHF Single Point
  subtitle: "Molecular HF calculation"
  tags:
    - pyscf
    - molecular
    - HF
    - tutorial
  recommended_analysis: energy
  difficulty: beginner
  reference_artifacts:
    scf: water_pyscf_scf.scf.json
```

### 6.2 Expected Results

For H2O with RHF/6-31G:

| Property | Expected Value | Unit |
|----------|----------------|------|
| Total Energy | ~-75.98 | Hartree |
| HOMO | ~-0.50 | Hartree |
| LUMO | ~0.21 | Hartree |
| HOMO-LUMO Gap | ~0.71 | Hartree |
| HOMO-LUMO Gap | ~19.3 | eV |

---

## 7. Artifacts

### 7.1 results.json Schema

```json
{
  "energy": -75.98...,
  "converged": true,
  "mo_energies": [-20.5, -1.3, ..., 0.21, ...],
  "mo_occupations": [2.0, 2.0, 2.0, 2.0, 2.0, 0.0, ...],
  "homo_index": 4,
  "lumo_index": 5,
  "homo_energy": -0.497,
  "lumo_energy": 0.211,
  "gap": 0.708,
  "gap_ev": 19.27,
  "dipole_moment": [0.0, 0.0, 0.78],
  "mulliken_charges": [-0.35, 0.17, 0.17]
}
```

### 7.2 run.log (Optional)

Captured PySCF stdout for debugging:

```
converged SCF energy = -75.9850779...
```

---

## 8. Test Strategy

### 8.1 Unit Tests

```python
# tests/unit/test_pyscf_integration.py

class TestPySCFStepType:
    """Step type registration tests."""
    
    def test_pyscf_scf_registered(self):
        """PYSCF_SCF step type is registered."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        assert registry.has("pyscf_scf")
    
    def test_pyscf_scf_engine(self):
        """PYSCF_SCF uses pyscf engine."""
        from quantumvitas.workflow.registry import get_registry
        spec = get_registry().get("pyscf_scf")
        assert spec.engine == "pyscf"
    
    def test_pyscf_scf_molecular_only(self):
        """PYSCF_SCF only allows molecular systems."""
        from quantumvitas.workflow.registry import get_registry
        spec = get_registry().get("pyscf_scf")
        assert SystemKind.MOLECULAR in spec.allowed_system_kinds
        assert SystemKind.PERIODIC not in spec.allowed_system_kinds


class TestPySCFEngine:
    """Engine adapter tests."""
    
    def test_pyscf_check(self):
        """Check if pyscf is available."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        engine = PySCFEngine()
        # Should not raise, just return True/False
        assert isinstance(engine._pyscf_available, bool)
    
    def test_mole_building(self):
        """Molecule building from parameters."""
        pytest.importorskip("pyscf")
        
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        engine = PySCFEngine()
        
        params = {
            "atoms": [
                {"element": "O", "x": 0, "y": 0, "z": 0.117790},
                {"element": "H", "x": 0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0, "y": -0.755453, "z": -0.471161},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 0,
        }
        
        mol = engine._build_mole(params)
        assert mol.nelectron == 10
        assert mol.natm == 3
```

### 8.2 Integration Tests

```python
# tests/integration/test_pyscf_execution.py

@pytest.mark.skipif(
    not _pyscf_available(),
    reason="PySCF not installed"
)
class TestPySCFExecution:
    """Integration tests that run actual PySCF calculations."""
    
    def test_h2o_rhf(self, tmp_path):
        """Run H2O RHF calculation."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "O", "x": 0, "y": 0, "z": 0.117790},
                {"element": "H", "x": 0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0, "y": -0.755453, "z": -0.471161},
            ],
            "charge": 0,
            "spin": 0,
        }
        
        result = engine._run_pyscf_scf(params, tmp_path)
        
        assert result.success
        assert result.parsed_output["converged"]
        assert result.parsed_output["energy"] < -74.0  # Reasonable for STO-3G
        assert result.parsed_output["gap"] > 0  # Positive gap
        
        # Check results.json was written
        results_file = tmp_path / "results.json"
        assert results_file.exists()
    
    def test_graceful_failure_no_pyscf(self, tmp_path, monkeypatch):
        """Graceful error when PySCF not installed."""
        # Mock pyscf as unavailable
        monkeypatch.setattr(
            "quantumvitas.engine.pyscf_engine.PySCFEngine._check_pyscf",
            lambda self: False
        )
        
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        engine = PySCFEngine()
        
        result = engine.run_step(None, tmp_path)
        assert not result.success
        assert "pip install pyscf" in result.error


def _pyscf_available() -> bool:
    try:
        import pyscf
        return True
    except ImportError:
        return False
```

---

## 9. Implementation Checklist

### Phase 1: Foundation
- [x] Create PYSCF_INTEGRATION_SPEC.md
- [ ] Add PYSCF_SCF to StepType enum
- [ ] Add PYSCF_SCF to StepTypeRegistry
- [ ] Add SystemKind.MOLECULAR detection

### Phase 2: Engine
- [ ] Create pyscf_engine.py
- [ ] Implement _build_mole()
- [ ] Implement _run_pyscf_scf()
- [ ] Add graceful error handling

### Phase 3: Demo
- [ ] Create generate_pyscf_demo.py
- [ ] Generate water_pyscf_scf.yml
- [ ] Add reference artifacts

### Phase 4: Tests
- [ ] Unit tests for step types
- [ ] Unit tests for molecule building
- [ ] Integration tests (skip if pyscf missing)

### Phase 5: Dependencies
- [ ] Add pyscf to pyproject.toml [pyscf] optional
- [ ] Update CI to skip pyscf tests if not installed

---

## 10. Limitations (MVP)

| Feature | Status | Notes |
|---------|--------|-------|
| RHF | ✅ MVP | Restricted Hartree-Fock |
| UHF | ✅ MVP | Unrestricted HF for open-shell |
| RKS | ✅ MVP | DFT (restricted) |
| UKS | ✅ MVP | DFT (unrestricted) |
| Geometry Opt | ❌ Future | Requires geomopt module |
| MP2 | ❌ Future | Post-HF |
| CCSD | ❌ Future | Post-HF |
| TD-DFT | ❌ Future | Excited states |
| PBC/Cell | ❌ N/A | Use QE for periodic |
| Presets | ❌ Future | No preset dimensions yet |

---

## 11. Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `docs/architecture/PYSCF_INTEGRATION_SPEC.md` | Create | This spec |
| `src/quantumvitas/calculation/types.py` | Modify | Add PYSCF_SCF to StepType |
| `src/quantumvitas/workflow/registry.py` | Modify | Add PYSCF_SCF StepTypeSpec |
| `src/quantumvitas/engine/pyscf_engine.py` | Create | PySCF engine adapter |
| `tools/generate_pyscf_demo.py` | Create | Demo generator |
| `resources/demo_projects/water_pyscf_scf.yml` | Create | Demo project |
| `tests/unit/test_pyscf_integration.py` | Create | Unit tests |
| `tests/integration/test_pyscf_execution.py` | Create | Integration tests |
| `pyproject.toml` | Modify | Add pyscf optional dep |

---

*This specification is implementation-ready. Proceed with PRs in checklist order.*

