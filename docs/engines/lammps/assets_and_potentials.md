# LAMMPS Assets and Potentials Management

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase  
**Constitution Reference**: §A (Parameters), §B (Assets)

---

## 1. Overview

LAMMPS relies on external potential files (force field parameters) rather than pseudopotentials. This document defines how QMatSuite manages these assets, drawing parallels to the existing `species_map`/`pseudo_dir` pattern for QE.

---

## 2. Comparison with QE Pseudopotential Pattern

| Aspect | QE (Pseudopotentials) | LAMMPS (Potentials) |
|--------|----------------------|---------------------|
| **Purpose** | Effective potentials for electrons | Interatomic force field parameters |
| **SSOT Key** | `species_map` | `potential_map` (proposed) |
| **Asset Location** | `project/pseudo/` | `project/potentials/` (proposed) |
| **Staging** | Copy to `calc/raw/pseudo/` | Copy to `calc/raw/potentials/` |
| **Per-Element** | Yes (one pseudo per element) | Varies (one file may cover many elements) |
| **File Format** | UPF, PSP | EAM, Tersoff, ReaxFF, etc. |

---

## 3. Potential Types

### 3.1 Common Potential File Types

| Type | File Extensions | Scope | Example |
|------|-----------------|-------|---------|
| **EAM (single element)** | `.eam`, `.funcfl` | Single element | `Cu_u3.eam` |
| **EAM (alloy)** | `.eam.alloy`, `.alloy` | Multiple elements | `NiAlH_jea.eam.alloy` |
| **EAM (Finnis-Sinclair)** | `.eam.fs` | Multiple elements | `Fe_mm.eam.fs` |
| **Tersoff** | `.tersoff` | Multiple elements | `SiC.tersoff` |
| **Stillinger-Weber** | `.sw` | Multiple elements | `Si.sw` |
| **ReaxFF** | `ffield.reax.*` | Multiple elements | `ffield.reax.CHO` |
| **MEAM (library)** | `.meam` + `.library` | Multiple elements | `library.meam` + `AlCu.meam` |
| **SNAP** | `.snapparam`, `.snapcoeff` | Multiple elements | Model coefficients |
| **DeepMD** | `.pb`, `.pth` | Trained model | `frozen_model.pb` |

### 3.2 Multi-File Potentials

Some potentials require multiple files:

```
MEAM:
  - library.meam (element library)
  - AlCu.meam (specific parameters)

ReaxFF:
  - ffield.reax.CHO (main parameters)
  - control.reax (optional control file)
```

---

## 4. Proposed `potential_map` Schema

### 4.1 Project-Level Definition

In `project.qms.yml` or a dedicated `potentials.yml`:

```yaml
# project.qms.yml
potentials:
  # Simple EAM potential
  eam_cu:
    type: eam
    style: eam
    file: potentials/Cu_u3.eam
    elements: [Cu]
    source: "https://www.ctcms.nist.gov/potentials/..."
    version: "1.0"
    
  # Alloy EAM potential
  eam_nialh:
    type: eam/alloy
    style: eam/alloy
    file: potentials/NiAlH_jea.eam.alloy
    elements: [Ni, Al, H]
    
  # ReaxFF (multi-file)
  reaxff_cho:
    type: reaxff
    style: reaxff
    files:
      - potentials/ffield.reax.CHO
      - potentials/control.reax  # optional
    elements: [C, H, O]
    
  # Machine learning potential
  deepmd_si:
    type: deepmd
    style: deepmd
    model_file: potentials/dp_si.pb
    elements: [Si]
    units: metal
```

### 4.2 Calculation-Level Reference

In `calculation.yaml`:

```yaml
# calculation.yaml
engine: lammps
structure_id: "01HQABC..."

# Reference potentials by key
potential: eam_cu  # Simple case: single potential

# Or for complex systems:
potentials:
  metal: eam_nialh
  organic: reaxff_cho
```

### 4.3 Step-Level Override

In `step.yaml`:

```yaml
# step.yaml
parameters:
  potential: eam_cu  # Use this potential for this step
```

---

## 5. Asset Storage Layout

### 5.1 Project-Level Storage

```
project_root/
├── potentials/                    # Project-level potential library
│   ├── Cu_u3.eam
│   ├── NiAlH_jea.eam.alloy
│   ├── ffield.reax.CHO
│   └── dp_si.pb
├── project.qms.yml                 # Contains potential_map
└── calculations/
    └── ...
```

### 5.2 Global/System-Level Storage (Optional)

```
~/.qmatsuite/
└── potentials/                    # User-global potential cache
    ├── eam/
    │   ├── Cu_u3.eam
    │   └── ...
    ├── reaxff/
    │   └── ...
    └── deepmd/
        └── ...
```

### 5.3 Calculation-Level Staging

During materialize, only needed potentials are staged:

```
calc/raw/<step_ulid>/
├── in.lammps
├── structure.data
└── potentials/                    # ONLY files needed for this step
    └── Cu_u3.eam
```

---

## 6. Staging Implementation

### 6.1 Staging Logic

```python
def stage_potentials(
    calculation: Calculation,
    potential_ref: str,
    target_dir: Path,
) -> StagedPotentials:
    """
    Stage potential files for a LAMMPS step.
    
    Args:
        calculation: Calculation context
        potential_ref: Key in potential_map
        target_dir: Destination directory (calc/raw/<step>/potentials/)
    
    Returns:
        StagedPotentials with:
        - staged_files: List of (name, path) tuples
        - digest: SHA256 of concatenated file contents
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Resolve potential definition
    pot_def = calculation.potential_map[potential_ref]
    
    # Get source files
    source_files = get_potential_files(pot_def, calculation.project.root)
    
    # Stage files
    staged = []
    for name, src_path in source_files:
        dst_path = target_dir / name
        shutil.copy2(src_path, dst_path)
        staged.append((name, dst_path))
    
    # Compute digest
    digest = compute_potential_digest(staged)
    
    return StagedPotentials(
        staged_files=staged,
        digest=digest,
        style=pot_def["style"],
        elements=pot_def.get("elements", []),
    )
```

### 6.2 Digest Computation

```python
def compute_potential_digest(staged_files: List[Tuple[str, Path]]) -> str:
    """
    Compute deterministic digest of potential files.
    
    Order-independent: sort by filename before hashing.
    """
    hasher = hashlib.sha256()
    
    for name, path in sorted(staged_files):
        hasher.update(name.encode())
        hasher.update(path.read_bytes())
    
    return hasher.hexdigest()
```

---

## 7. pair_style Generation

### 7.1 Template Blocks

Each potential type generates specific `pair_style`/`pair_coeff` blocks:

```python
PAIR_STYLE_TEMPLATES = {
    "eam": """
pair_style eam
pair_coeff * * {potentials_dir}/{filename}
""",
    
    "eam/alloy": """
pair_style eam/alloy
pair_coeff * * {potentials_dir}/{filename} {elements}
""",
    
    "reaxff": """
pair_style reaxff NULL
pair_coeff * * {potentials_dir}/ffield.reax {elements}
fix qeq all qeq/reaxff 1 0.0 10.0 1.0e-6 reaxff
""",
    
    "tersoff": """
pair_style tersoff
pair_coeff * * {potentials_dir}/{filename} {elements}
""",
    
    "deepmd": """
pair_style deepmd {potentials_dir}/{model_file}
pair_coeff * *
""",
}
```

### 7.2 Element Ordering

For multi-element potentials, element order must match structure atom types:

```python
def generate_pair_coeff(
    potential: StagedPotentials,
    structure: Structure,
) -> str:
    """
    Generate pair_coeff line with correct element ordering.
    
    Element order in pair_coeff MUST match atom type order in data file.
    """
    # Get unique elements in order of first appearance
    elements_in_structure = get_unique_elements_ordered(structure)
    
    # Map to potential elements
    element_string = " ".join(
        elem if elem in potential.elements else "NULL"
        for elem in elements_in_structure
    )
    
    return template.format(elements=element_string, ...)
```

---

## 8. Validation

### 8.1 Pre-Materialize Validation

```python
def validate_potential_for_structure(
    potential_ref: str,
    structure: Structure,
    potential_map: dict,
) -> ValidationResult:
    """
    Validate potential covers all elements in structure.
    """
    pot_def = potential_map.get(potential_ref)
    if not pot_def:
        return ValidationResult(
            valid=False,
            error=f"Potential '{potential_ref}' not found in potential_map"
        )
    
    structure_elements = set(get_unique_elements(structure))
    potential_elements = set(pot_def.get("elements", []))
    
    missing = structure_elements - potential_elements
    if missing:
        return ValidationResult(
            valid=False,
            error=f"Potential does not cover elements: {missing}"
        )
    
    return ValidationResult(valid=True)
```

### 8.2 File Existence Check

```python
def validate_potential_files(
    potential_ref: str,
    potential_map: dict,
    project_root: Path,
) -> ValidationResult:
    """Ensure all potential files exist."""
    pot_def = potential_map[potential_ref]
    
    files = pot_def.get("files") or [pot_def.get("file")]
    for f in files:
        path = project_root / f
        if not path.exists():
            return ValidationResult(
                valid=False,
                error=f"Potential file not found: {path}"
            )
    
    return ValidationResult(valid=True)
```

---

## 9. SSOT Compliance

### 9.1 Where Potentials Are Defined

| Location | Role | Mutability |
|----------|------|------------|
| `project.qms.yml` or `potentials.yml` | Define available potentials | User-editable |
| `calculation.yaml` | Select potential for calculation | User-editable |
| `step.yaml` | Override for specific step | User-editable |
| `calc/raw/potentials/` | Staged copies | Runtime-generated |

### 9.2 What Is NOT Allowed

❌ Parsing input scripts to extract potential info  
❌ Modifying staged potentials during run  
❌ Using potential files not in potential_map  
❌ Inferring potentials from existing runs

### 9.3 SSOT Flow

```
potential_map (definition)
    ↓
calculation.yaml (selection)
    ↓
step.yaml (override, optional)
    ↓
materialize → calc/raw/potentials/ (staging)
    ↓
in.lammps (pair_style/pair_coeff generated)
```

---

## 10. Integration with Manifest

### 10.1 New Manifest Field

Extend `ManifestStepEntry` to include potential digest:

```python
@dataclass
class ManifestStepEntry:
    ...
    potential_assets_sha: str = ""  # NEW: Hash of staged potential files
    ...
```

### 10.2 Skip Determination

Skip if all match:
- `structure_sha`
- `step_sha` (includes A-class params)
- `potential_assets_sha` (new)
- `done == True`

---

## 11. Future Extensions

### 11.1 Potential Download/Caching

Similar to pseudo download for QE:

```python
def ensure_potential(
    potential_def: dict,
    target_dir: Path,
    download: bool = True,
) -> Path:
    """
    Ensure potential file exists, optionally downloading.
    
    Sources:
    - NIST Interatomic Potentials Repository
    - OpenKIM
    - User-provided URLs
    """
    ...
```

### 11.2 OpenKIM Integration

```yaml
potential_map:
  kim_sw_si:
    type: kim
    model_name: "SW_StillingerWeber_1985_Si__MO_405512056662_006"
    elements: [Si]
```

### 11.3 Version Control

Track potential provenance:

```yaml
potentials:
  eam_cu:
    type: eam
    file: potentials/Cu_u3.eam
    version: "1.0"
    source: "https://..."
    downloaded_at: "2026-01-15T10:30:00Z"
    sha256: "abc123..."
```

