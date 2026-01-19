# VASP Research and Specifications

**Purpose**: Web research on VASP execution model and specifications aligned with QMatSuite constitution.

---

## 1. VASP Execution Model Research

### 1.1 Input File Structure

VASP requires exactly 4 input files in the working directory:

| File | Purpose | Format |
|------|---------|--------|
| **POSCAR** | Crystal structure | Lattice vectors + atom positions (Direct/Cartesian) |
| **INCAR** | Calculation parameters | Tag = Value pairs (e.g., `ENCUT = 400`) |
| **KPOINTS** | K-point mesh/path | Multiple formats: Automatic, Gamma, Line-mode |
| **POTCAR** | Pseudopotentials | Concatenated element POTCARs in POSCAR element order |

**Source**: VASP Wiki - https://www.vasp.at/wiki/

### 1.2 POSCAR Format

```
System title
1.0                     # Universal scaling factor
5.43  0.0   0.0         # a1 vector
0.0   5.43  0.0         # a2 vector
0.0   0.0   5.43        # a3 vector
Si                      # Element symbols (VASP 5+)
2                       # Number of each element type
Direct                  # Direct (fractional) or Cartesian
0.0  0.0  0.0           # Atom 1 position
0.25 0.25 0.25          # Atom 2 position
```

**Key Points**:
- Element symbols line (VASP 5+) determines POTCAR order
- Positions can be `Direct` (fractional) or `Cartesian` (Angstrom)
- Pymatgen's `Poscar` class handles this format

### 1.3 INCAR Format

```
SYSTEM = Silicon SCF
ENCUT = 400             # Plane-wave cutoff (eV)
EDIFF = 1E-6            # Energy convergence (eV)
ISMEAR = 0              # Smearing: 0=Gaussian, 1=MP, -5=tetrahedra
SIGMA = 0.05            # Smearing width (eV)
IBRION = -1             # Ion dynamics: -1=static, 1=quasi-Newton, 2=CG
ISIF = 2                # Stress/relax: 0=nothing, 2=forces, 3=all
NSW = 0                 # Ionic steps (0=static)
PREC = Accurate         # Precision preset
LREAL = Auto            # Real-space projection
```

**Source**: VASP Wiki INCAR tag reference

### 1.4 KPOINTS Format

**Automatic mesh**:
```
Automatic mesh
0                       # 0 = automatic generation
Monkhorst-Pack          # or Gamma
6 6 6                   # Mesh density
0 0 0                   # Shift
```

**Line-mode for band structure**:
```
k-points along high symmetry lines
40                      # Points per segment
Line-mode               # Line mode flag
reciprocal              # Reciprocal coordinates
0.0  0.0  0.0   ! G
0.5  0.0  0.5   ! X
                        # Blank line = segment break
0.5  0.0  0.5   ! X
0.5  0.25 0.75  ! W
```

### 1.5 POTCAR Assembly

POTCAR is a concatenation of per-element POTCAR files, in the order elements appear in POSCAR.

```bash
# Example: Si and O in POSCAR
cat $POTCAR_DIR/Si/POTCAR $POTCAR_DIR/O/POTCAR > POTCAR
```

**Library Layout** (user's local path):
```
~/.qmatsuite/engines/vasp/potpaw_PBE/
├── Si/POTCAR
├── Si_sv/POTCAR      # Semi-core
├── O/POTCAR
├── O_s/POTCAR        # Soft
└── ...
```

---

## 2. Standard Workflows (QE Equivalents)

### 2.1 Static SCF

**Equivalent to**: QE pw.x calculation='scf'

**INCAR Settings**:
```
IBRION = -1             # No ion movement
NSW = 0                 # Zero ionic steps
ISMEAR = 0              # Gaussian smearing (insulators)
# or ISMEAR = 1         # Methfessel-Paxton (metals)
SIGMA = 0.05            # Smearing width
EDIFF = 1E-6            # SCF convergence
```

**Outputs**:
- `OUTCAR`: Main output (energies, forces, timing)
- `OSZICAR`: Convergence per ionic step
- `vasprun.xml`: Structured output (if LXML=.TRUE.)
- `CHGCAR`: Charge density (for subsequent NSCF)
- `WAVECAR`: Wavefunctions (optional restart)

### 2.2 Geometry Relaxation

**Equivalent to**: QE pw.x calculation='relax' or 'vc-relax'

**Positions only (ISIF=2)**:
```
IBRION = 2              # Conjugate gradient
# or IBRION = 1         # Quasi-Newton (faster near minimum)
NSW = 100               # Max ionic steps
ISIF = 2                # Relax positions only
EDIFFG = -0.01          # Force convergence (eV/Å, negative = force)
```

**Full relaxation (ISIF=3)**:
```
IBRION = 2
NSW = 100
ISIF = 3                # Relax positions + cell shape + volume
EDIFFG = -0.01
```

**Outputs**:
- `CONTCAR`: Final (relaxed) structure in POSCAR format
- `OUTCAR`: Contains all ionic step energies and final structure

### 2.3 Band Structure Workflow

**Two-step workflow** (like QE SCF → NSCF):

**Step 1: SCF with uniform k-mesh**
```
# INCAR
IBRION = -1
NSW = 0
ICHARG = 2              # Initial charge from superposition
LCHARG = .TRUE.         # Write CHGCAR
LWAVE = .FALSE.         # Don't need WAVECAR
```

**Step 2: Non-SCF along k-path**
```
# INCAR
IBRION = -1
NSW = 0
ICHARG = 11             # Read charge from CHGCAR (non-SCF)
LCHARG = .FALSE.
LWAVE = .FALSE.
LORBIT = 11             # Write PROCAR with orbital character
```

**KPOINTS for band path** (step 2):
```
k-points along high symmetry lines
20
Line-mode
reciprocal
0.0  0.0  0.0   ! G
0.5  0.0  0.5   ! X

0.5  0.0  0.5   ! X
0.5  0.25 0.75  ! W
```

**Critical**: Step 2 requires `CHGCAR` from Step 1 in working directory.

**Outputs**:
- `EIGENVAL`: Eigenvalues at each k-point
- `PROCAR`: Projected orbital character (if LORBIT set)

### 2.4 DOS Workflow

**Two-step workflow**:

**Step 1: SCF with coarse k-mesh** (same as band structure step 1)

**Step 2: Non-SCF with dense k-mesh**
```
# INCAR
ICHARG = 11             # Read CHGCAR
ISMEAR = -5             # Tetrahedra method for DOS (insulators)
# or ISMEAR = 0         # Gaussian for metals
LORBIT = 11             # Write DOSCAR with projections
NEDOS = 2000            # DOS points
EMIN = -10              # Energy range
EMAX = 10
```

**KPOINTS**: Dense uniform mesh (e.g., 12×12×12)

**Outputs**:
- `DOSCAR`: Total and projected DOS

---

## 3. Output Parsing Strategy

### 3.1 File Priority

| Priority | File | Use Case | Parsing Difficulty |
|----------|------|----------|-------------------|
| 1 | `OSZICAR` | Fast energy/convergence check | Easy (simple format) |
| 2 | `OUTCAR` | Detailed results (energy, forces, stress) | Medium (regex) |
| 3 | `vasprun.xml` | Structured data (if available) | Easy (XML parser) |
| 4 | `CONTCAR` | Relaxed structure | Easy (POSCAR format) |

### 3.2 OSZICAR Parsing

```
       N       E                     dE             d eps       ncg     rms          rms(c)
DAV:   1    -0.119051942420E+03   -0.11905E+03   -0.35815E+03   972   0.510E+02
DAV:   2    -0.104397887532E+03    0.14654E+02   -0.14247E+02   820   0.104E+02
...
   1 F= -.10439789E+03 E0= -.10439789E+03  d E =-.104398E+03
```

**Extract**: Final `F=` value (free energy in eV)

### 3.3 OUTCAR Parsing

```python
# Energy (search from end of file)
r"free  energy   TOTEN\s*=\s*([\d\.\-+Ee]+)\s*eV"

# Forces (per atom)
r"TOTAL-FORCE \(eV/Angst\).*?\n-+\n(.*?)\n-+\n"

# Stress tensor
r"FORCE on cell =-STRESS.*?\n.*?in kB\s+([\d\.\-+Ee\s]+)"

# Timing
r"Elapsed time \(sec\):\s*([\d\.]+)"

# VASP version
r"vasp\.([\d\.]+)"
```

### 3.4 vasprun.xml Parsing (Optional)

If available, use `pymatgen.io.vasp.Vasprun`:

```python
from pymatgen.io.vasp import Vasprun
vr = Vasprun("vasprun.xml")
energy = vr.final_energy
structure = vr.final_structure
forces = vr.forces
```

**Note**: vasprun.xml may be incomplete if run crashed.

### 3.5 Robustness Strategy

1. **Always produce a digest**, even if parsing fails
2. **Check file existence** before parsing
3. **Try OSZICAR first** (smallest, least fragile)
4. **Fall back gracefully**: If OUTCAR missing forces, return None (not error)
5. **Log warnings** for incomplete parses, don't fail

---

## 4. Specifications (Aligned with QMatSuite Constitution)

### 4.A Engine Member + Step Types

#### 4.A.1 PBC Family Rules

| Engine Family | Member | Mutual Exclusivity |
|---------------|--------|-------------------|
| qe | pw, ph, dos, bands, ... | QE calculation.yaml: `engine_family: qe` |
| vasp | vasp | VASP calculation.yaml: `engine_family: vasp` |

**Rule**: A calculation can only use ONE engine family. No mixing QE and VASP steps.

#### 4.A.2 Step Type Definitions

```python
# workflow/registry.py additions
_STEP_TYPES = {
    # ... existing QE types ...
    
    # VASP step types
    "vasp_scf": StepTypeSpec(
        id="scf",                    # Public type (shared with qe_scf)
        machine_type="vasp_scf",     # Machine type in step.yaml
        public_type="scf",
        engine="vasp",
        executable="vasp_std",       # Default, see selection logic
        description="VASP static SCF calculation",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=True,  # Produces CHGCAR
    ),
    "vasp_bands": StepTypeSpec(
        id="bands",
        machine_type="vasp_bands",
        public_type="bands",
        engine="vasp",
        executable="vasp_std",
        description="VASP band structure (non-SCF along k-path)",
        requires_structure=True,
        requires_charge_density=True,  # Needs CHGCAR from SCF
        produces_charge_density=False,
    ),
    "vasp_dos": StepTypeSpec(
        id="dos",
        machine_type="vasp_dos",
        public_type="dos",
        engine="vasp",
        executable="vasp_std",
        description="VASP density of states (non-SCF with dense k-mesh)",
        requires_structure=True,
        requires_charge_density=True,  # Needs CHGCAR from SCF
        produces_charge_density=False,
    ),
    "vasp_relax": StepTypeSpec(
        id="relax",
        machine_type="vasp_relax",
        public_type="relax",
        engine="vasp",
        executable="vasp_std",
        description="VASP geometry optimization",
        requires_structure=True,
        requires_charge_density=False,
        produces_charge_density=False,
        is_structure_transform=True,  # Produces CONTCAR
    ),
}
```

#### 4.A.3 Executable Selection Logic

```python
# core/engines/vasp_resolver.py

def select_vasp_executable(step_params: Dict[str, Any]) -> str:
    """
    Select VASP executable variant based on calculation parameters.
    
    Returns: "vasp_std", "vasp_gam", or "vasp_ncl"
    """
    # 1. SOC/Noncollinear → vasp_ncl
    if step_params.get("LSORBIT", False) or step_params.get("LNONCOLLINEAR", False):
        return "vasp_ncl"
    
    # 2. Gamma-only → vasp_gam
    kpoints = step_params.get("kpoints", {})
    if kpoints.get("type") == "gamma" or kpoints.get("mesh") == [1, 1, 1]:
        return "vasp_gam"
    
    # 3. Default → vasp_std
    return "vasp_std"
```

### 4.B YAML Schema for VASP step.yaml

#### 4.B.1 Structure

```yaml
# step.yaml for VASP step
meta:
  id: "01HXXXXXXXXXXXXXX"
  name: "scf"
  slug: "scf"
  path: "calculations/my_calc/steps/scf.step.yaml"
  kind: "step"

step_type: vasp_scf           # Machine type (SSOT)

# VASP-specific parameters
parameters:
  incar:                       # Maps to INCAR tags
    ENCUT: 400                 # Plane-wave cutoff (eV)
    EDIFF: 1.0e-6              # SCF convergence (eV)
    ISMEAR: 0                  # Smearing type
    SIGMA: 0.05                # Smearing width (eV)
    PREC: "Accurate"
    LREAL: "Auto"
    IBRION: -1                 # Static
    NSW: 0
    # Relaxation-specific
    # ISIF: 3
    # EDIFFG: -0.01
  
  kpoints:                     # Maps to KPOINTS file
    type: "monkhorst-pack"     # or "gamma", "line-mode"
    mesh: [6, 6, 6]            # For mesh types
    shift: [0, 0, 0]
    # For band structure (line-mode):
    # path:
    #   - ["G", [0.0, 0.0, 0.0]]
    #   - ["X", [0.5, 0.0, 0.5]]
    # divisions: 20
  
  parallel:                    # Optional parallel settings
    ncore: 4                   # NCORE tag
    kpar: 2                    # KPAR tag

# Step-level species overrides (optional, NOT SSOT for pseudo selection)
species_overrides:
  Si:
    potcar_variant: "Si_sv"    # Use semi-core variant
```

#### 4.B.2 Class A/B Key Typing

**Class A (Owned, Strict-Typed)**: Keys managed by presets
```python
VASP_CLASS_A_KEYS = {
    ("incar", "ENCUT"): "float",
    ("incar", "EDIFF"): "float", 
    ("incar", "ISMEAR"): "int",
    ("incar", "SIGMA"): "float",
    ("incar", "PREC"): "str",
    ("incar", "IBRION"): "int",
    ("incar", "NSW"): "int",
    ("incar", "ISIF"): "int",
    ("incar", "EDIFFG"): "float",
    ("incar", "ICHARG"): "int",
}
```

**Class B (Free, Permissive)**: All other INCAR tags
- User can add any INCAR tag
- No type enforcement
- Examples: NCORE, KPAR, LWAVE, LCHARG, LORBIT, etc.

**Staged Approach**: Start with Class B only (no preset enforcement), add Class A later.

### 4.C Pseudopotential / species_map Contract

#### 4.C.1 calculation.yaml species_map

```yaml
# calculation.yaml
meta:
  id: "01HXXXXXXXXXXXXXX"
  name: "silicon_scf"
  ...

engine_family: vasp
structure_id: "01HYYYYYYYYYYYYYYY"

species_map:
  Si:
    potcar_variant: "Si"       # Subdirectory in POTCAR library
    potcar_sha256: "abc123..." # SHA256 of POTCAR file (pinned)
    # Optional: potcar_functional: "PBE"  # Defaults to library default
```

**SSOT Rule**: `species_map` in `calculation.yaml` is SSOT for pseudo selection.

#### 4.C.2 POTCAR Library Reference

**User's local library**:
```
~/.qmatsuite/engines/vasp/potpaw_PBE/
├── Si/POTCAR
├── Si_sv/POTCAR
├── O/POTCAR
└── ...
```

**Environment Variable**: `QMATSUITE_VASP_POTCAR_DIR`
- Default: `~/.qmatsuite/engines/vasp/potpaw_*/` (auto-detect)

**NEVER committed to repo**: POTCAR files are proprietary.

#### 4.C.3 Materialization: POTCAR Assembly

```python
def assemble_potcar(
    structure: Structure,
    species_map: Dict[str, Dict[str, Any]],
    potcar_library: Path,
    working_dir: Path,
) -> Path:
    """
    Assemble POTCAR by concatenating element POTCARs.
    
    Args:
        structure: Pymatgen Structure (element order from POSCAR)
        species_map: Element → {potcar_variant, potcar_sha256}
        potcar_library: Path to POTCAR library
        working_dir: Where to write assembled POTCAR
        
    Returns:
        Path to assembled POTCAR file
    """
    # Get unique elements in POSCAR order
    elements = structure.symbol_set  # Preserves order
    
    potcar_path = working_dir / "POTCAR"
    with open(potcar_path, "wb") as out_f:
        for element in elements:
            spec = species_map.get(element, {})
            variant = spec.get("potcar_variant", element)  # Default to element symbol
            expected_sha = spec.get("potcar_sha256")
            
            element_potcar = potcar_library / variant / "POTCAR"
            if not element_potcar.exists():
                raise RuntimeError(f"POTCAR not found: {element_potcar}")
            
            # Verify SHA if pinned
            if expected_sha:
                actual_sha = compute_sha256_file(element_potcar)
                if actual_sha != expected_sha:
                    raise ValueError(f"POTCAR SHA mismatch for {element}")
            
            # Append to assembled POTCAR
            with open(element_potcar, "rb") as in_f:
                out_f.write(in_f.read())
    
    return potcar_path
```

#### 4.C.4 pseudo_set_sha Derivation

```python
def compute_vasp_pseudo_set_sha(
    structure: Structure,
    species_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    Compute pseudo_set_sha for VASP (same algorithm as QE).
    
    Uses canonical shared implementation from hash_utils.
    """
    # Get elements in structure order
    elements = sorted(structure.symbol_set)
    
    # Build list of (element, sha256) tuples
    sha_list = []
    for element in elements:
        spec = species_map.get(element, {})
        sha = spec.get("potcar_sha256", "")
        sha_list.append(f"{element}:{sha}")
    
    # Hash the concatenated list
    combined = "\n".join(sha_list)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

### 4.D Materialize Contract

#### 4.D.1 raw/ Layout for VASP

```
calculations/<calc_name>/
├── calculation.yaml
├── steps/
│   ├── scf.step.yaml
│   └── bands.step.yaml
└── raw/                        # Ephemeral working directory
    ├── POSCAR                  # Materialized by writer
    ├── INCAR                   # Materialized by writer
    ├── KPOINTS                 # Materialized by writer
    ├── POTCAR                  # Assembled from library
    ├── OUTCAR                  # VASP output
    ├── OSZICAR                 # VASP output
    ├── CHGCAR                  # Charge density (for bands/dos)
    ├── CONTCAR                 # Relaxed structure
    ├── vasprun.xml             # Optional structured output
    ├── WAVECAR                 # Optional (large)
    ├── vasp_scf.out            # stdout capture
    └── vasp_scf.err            # stderr capture
```

**Note**: VASP writes many files in-place. No subdirectory per step (unlike some QE workflows).

#### 4.D.2 Runtime-Managed Fields

Fields set by materializer/runner (UI shows as read-only):

| Field | Set By | UI Display |
|-------|--------|------------|
| `SYSTEM` (INCAR) | Materializer | Read-only (calc name) |
| `ENCUT` (if auto) | Materializer from POTCAR | Show computed value |

### 4.E Parsing & Digest Contract

#### 4.E.1 Minimal Digest for MVP

```python
@dataclass
class VaspStepDigest:
    """Minimal digest for VASP step."""
    success: bool                    # Calculation completed successfully
    final_energy_eV: Optional[float] # TOTEN from OUTCAR
    converged: bool                  # SCF converged
    n_ionic_steps: int               # Number of ionic steps
    walltime_sec: Optional[float]    # Elapsed time
    vasp_version: Optional[str]      # VASP version string
    
    # Best-effort extras
    forces_max_eV_A: Optional[float] # Max force component
    stress_max_kB: Optional[float]   # Max stress component
```

#### 4.E.2 Parsing Order

1. **OSZICAR** (fast): Extract final energy, check convergence
2. **OUTCAR** (detailed): Extract forces, stress, timing, version
3. **vasprun.xml** (optional): Use if available for structured data

```python
def parse_vasp_outputs(working_dir: Path) -> VaspStepDigest:
    """Parse VASP outputs in priority order."""
    
    # 1. Check OSZICAR (always present if ran)
    oszicar = working_dir / "OSZICAR"
    if not oszicar.exists():
        return VaspStepDigest(success=False, converged=False, n_ionic_steps=0, ...)
    
    # Parse OSZICAR for energy and convergence
    energy, converged, n_steps = parse_oszicar(oszicar)
    
    # 2. Try OUTCAR for details
    outcar = working_dir / "OUTCAR"
    forces_max = None
    stress_max = None
    walltime = None
    version = None
    
    if outcar.exists():
        forces_max, stress_max, walltime, version = parse_outcar_details(outcar)
    
    return VaspStepDigest(
        success=converged,
        final_energy_eV=energy,
        converged=converged,
        n_ionic_steps=n_steps,
        walltime_sec=walltime,
        vasp_version=version,
        forces_max_eV_A=forces_max,
        stress_max_kB=stress_max,
    )
```

### 4.F Testing Contract for Proprietary VASP

#### 4.F.1 CI Behavior

**VASP is proprietary**: CI MUST NOT require VASP binary or POTCAR files.

**Skip Logic**:
```python
# tests/integration/vasp/conftest.py

import pytest
from quantumvitas.core.engines.vasp_resolver import is_vasp_available

@pytest.fixture(scope="session")
def vasp_available():
    """Session fixture: skip all VASP tests if not available."""
    if not is_vasp_available():
        pytest.skip("VASP not available (binary or POTCAR missing)")
    return True

def is_vasp_available() -> bool:
    """Check if VASP can be run."""
    try:
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        vasp_bin = resolve_vasp_bin()
        return vasp_bin.exists()
    except RuntimeError:
        return False
```

#### 4.F.2 Fake VASP Harness

**Purpose**: Test execution flow without real VASP.

**Strategy**: Create fake outputs that VASP would produce.

```python
# tests/utils/fake_vasp.py

from pathlib import Path
from typing import Dict, Any

def fake_vasp_scf(working_dir: Path, params: Dict[str, Any]) -> int:
    """
    Simulate VASP SCF run by creating expected outputs.
    
    Returns exit code (0 = success).
    """
    # Write minimal OSZICAR
    oszicar_content = """       N       E                     dE             d eps       ncg     rms
DAV:   1    -0.100000000000E+02   -0.10000E+02   -0.10000E+02   100   0.100E+01
   1 F= -.10000000E+02 E0= -.10000000E+02  d E =-.100000E+02
"""
    (working_dir / "OSZICAR").write_text(oszicar_content)
    
    # Write minimal OUTCAR
    outcar_content = """
 vasp.6.1.0 11Aug20 (build May 01 2021)
 ...
 free  energy   TOTEN  =       -10.000000 eV
 ...
 Elapsed time (sec):        1.234
"""
    (working_dir / "OUTCAR").write_text(outcar_content)
    
    # Copy POSCAR to CONTCAR (no relaxation)
    if (working_dir / "POSCAR").exists():
        (working_dir / "CONTCAR").write_text((working_dir / "POSCAR").read_text())
    
    # Create empty CHGCAR (for bands/dos workflow testing)
    (working_dir / "CHGCAR").write_text("FAKE CHGCAR")
    
    return 0


def fake_vasp_bands(working_dir: Path, params: Dict[str, Any]) -> int:
    """Simulate VASP bands run."""
    # Same as SCF but different output
    fake_vasp_scf(working_dir, params)
    
    # Write EIGENVAL
    eigenval_content = """    1    1    1
  1   1   1
    1
  0.0000000E+00  0.0000000E+00  0.0000000E+00  1.0000000E+00
   1      -5.0000
   2       0.0000
   3       2.5000
"""
    (working_dir / "EIGENVAL").write_text(eigenval_content)
    
    return 0


def fake_vasp_dos(working_dir: Path, params: Dict[str, Any]) -> int:
    """Simulate VASP DOS run."""
    fake_vasp_scf(working_dir, params)
    
    # Write minimal DOSCAR
    doscar_content = """  Si
   1   1   1
  10.0000  -10.0000  100  0.0000  1.0000
  -10.0000   0.0000   0.0000
   -5.0000   1.0000   0.5000
    0.0000   2.0000   1.0000
"""
    (working_dir / "DOSCAR").write_text(doscar_content)
    
    return 0
```

**Usage in Tests**:
```python
# tests/integration/vasp/test_vasp_with_fake.py

from tests.utils.fake_vasp import fake_vasp_scf

def test_vasp_scf_parsing(tmp_path):
    """Test parsing of VASP outputs without real VASP."""
    # Setup minimal inputs
    (tmp_path / "POSCAR").write_text("...")
    (tmp_path / "INCAR").write_text("...")
    
    # Run fake VASP
    exit_code = fake_vasp_scf(tmp_path, {})
    assert exit_code == 0
    
    # Test parsing
    from quantumvitas.engines.vasp.output_parser import parse_vasp_outputs
    digest = parse_vasp_outputs(tmp_path)
    
    assert digest.success
    assert digest.final_energy_eV == pytest.approx(-10.0, abs=0.01)
```

#### 4.F.3 Local Developer Smoke Tests

**For developers with VASP license**:

```python
# tests/integration/vasp/test_vasp_real.py

import pytest

pytestmark = pytest.mark.skipif(
    not is_vasp_available(),
    reason="VASP not available"
)

class TestVaspRealExecution:
    """Real VASP tests (developer-only, not CI)."""
    
    def test_si_scf_runs(self, vasp_project_with_si):
        """Run real VASP SCF on silicon."""
        project_root = vasp_project_with_si["project_root"]
        calc_id = vasp_project_with_si["calc_id"]
        step_id = vasp_project_with_si["step_id"]
        
        result = QVService.run_step(project_root, calc_id, step_id)
        
        assert result.get("success") is True
        assert "final_energy" in result
```

**Artifacts**: NEVER commit POTCAR files or real VASP outputs.

---

## 5. Summary: VASP Specification Checklist

### Input Files
- [x] POSCAR: Structure (pymatgen Poscar)
- [x] INCAR: Parameters (tag=value format)
- [x] KPOINTS: K-mesh/path (multiple formats)
- [x] POTCAR: Concatenated per-element (SHA-pinned)

### Workflow Support
- [x] vasp_scf: Static SCF
- [x] vasp_bands: Band structure (requires CHGCAR)
- [x] vasp_dos: DOS (requires CHGCAR)
- [x] vasp_relax: Geometry optimization

### Output Parsing
- [x] OSZICAR: Energy, convergence (fast)
- [x] OUTCAR: Forces, stress, timing, version
- [x] vasprun.xml: Optional structured data
- [x] CONTCAR: Relaxed structure

### Testing
- [x] Fake VASP harness for CI
- [x] Skip fixtures for missing VASP
- [x] Local smoke tests (developer-only)

### Constitution Compliance
- [x] SSOT: step.yaml + calculation.yaml only
- [x] species_map: In calculation.yaml
- [x] Fingerprints: structure_sha + pseudo_set_sha + step_sha
- [x] Locking: Same as QE
- [x] ULID references: Same as QE

---

*Document generated for VASP integration planning. See companion documents for QE review and implementation plan.*

