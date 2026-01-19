# VASP Goals and Required Behaviors

**Date**: 2026-01-18  
**Version**: 2.0 (Updated alignment)  
**Purpose**: Document the finalized VASP behaviors as immutable rules for implementation.

---

## 1. Immutable Rules (Constitution-Level)

### 1.1 GEN Workflow and Mapping

| Rule | Description |
|------|-------------|
| **GEN workflow naming** | Unified across engines: DOS = `scf → nscf → dospp`; Bands = `scf → bands → bandspp` |
| **0-1 mapping rule** | Each GEN step maps to **0 or 1** SPEC step per engine member |
| **Workflow compilation** | 0-mapping GEN steps are **silently omitted** (no error) |
| **Explicit run_step on 0-mapped GEN** | **Hard error**: "Step 'dospp' is not supported by engine 'vasp'" |
| **UI behavior** | Hide 0-mapped GEN steps from UI for current engine member |

### 1.2 VASP GEN→SPEC Mapping Table

| GEN Step | VASP SPEC | QE SPEC | Notes |
|----------|-----------|---------|-------|
| `scf` | `vasp_scf` | `qe_scf` | Self-consistent field |
| `nscf` | `vasp_nscf` | `qe_nscf` | Non-self-consistent (dense k-mesh for DOS) |
| `bands` | `vasp_bands` | `qe_bands_pw` | Band structure along k-path |
| `bandspp` | **None (0)** | `qe_bands` | VASP doesn't need post-processing |
| `dospp` | **None (0)** | `qe_dos` | VASP DOS integrated in nscf output |
| `relax` | `vasp_relax` | `qe_relax` | Geometry optimization |

---

## 2. VASP Workdir / Clean / Staging Rules (Finalized)

### 2.1 Workdir Structure

```
calc/raw/
├── <scf_step_ulid>/          # SCF step workdir
│   ├── POSCAR
│   ├── INCAR
│   ├── KPOINTS
│   ├── POTCAR
│   ├── OUTCAR
│   ├── OSZICAR
│   ├── CHGCAR                # Charge density (artifact)
│   └── WAVECAR               # Wavefunction (optional artifact)
│
├── <bands_step_ulid>/        # Bands step workdir
│   ├── POSCAR
│   ├── INCAR                 # ICHARG=11 for non-SCF
│   ├── KPOINTS               # Line-mode for band path
│   ├── POTCAR
│   ├── CHGCAR                # COPIED from reference SCF
│   ├── WAVECAR               # COPIED (optional)
│   └── OUTCAR
```

### 2.2 Pre-Execution Clean Policy

**Rule**: Before step execution, the workdir is **completely cleared**:

```python
def prepare_vasp_workdir(step_ulid: str, calc_raw_dir: Path) -> Path:
    workdir = calc_raw_dir / step_ulid
    if workdir.exists():
        shutil.rmtree(workdir)  # COMPLETE CLEAN
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir
```

**Rationale**: Latest-only retention; each workdir represents the most recent run.

### 2.3 Reference Step Definition (CRITICAL)

**Rule**: The reference step is the **most recent SCF step** in topological order.

```
Reference step = GEN `scf` (cross-engine semantic: the last scf before current step)
```

**Resolver behavior**:
1. Walk backwards in step topology from current step
2. Find the **most recent `scf`** step (by GEN type, not SPEC type)
3. **Relax is a barrier**: SCF steps before a relax step CANNOT be used as reference
4. If no valid reference SCF found → error for non-scf steps

**Example**:
```
Step topology: scf_1 → relax → scf_2 → bands → dos

For bands step:
  - Walk backwards: scf_2 ✓ (most recent scf)
  - scf_1 is blocked by relax barrier

For dos step:
  - Walk backwards: bands (not scf) → scf_2 ✓

If relax was not present:
  scf_1 → bands → dos
  - bands uses scf_1
  - dos uses scf_1 (same reference)
```

### 2.4 CHGCAR Staging Rules (Finalized)

| Step Type | CHGCAR Behavior |
|-----------|-----------------|
| **Non-SCF steps** (nscf, bands, dos) | **Prerequisite**: Must copy from reference SCF. Reference SCF must have `done=True` in manifest AND CHGCAR file exists. If either fails → **hard error at materialize phase** |
| **SCF step** | **Optional**: Copy from most recent (done=True) SCF only if file exists. If reference SCF is `done=False` → **never copy** (even if file residually exists) |

**Implementation**:
```python
def stage_chgcar(
    current_step: Step,
    reference_scf_step: Step,
    manifest: Manifest,
    calc_raw_dir: Path,
) -> None:
    """Stage CHGCAR from reference SCF to current step workdir."""
    
    # Find manifest entry for reference SCF
    ref_entry = get_manifest_entry(manifest, reference_scf_step.meta.id)
    
    # Check done flag
    if ref_entry is None or not ref_entry.done:
        if is_scf_step(current_step):
            # SCF: optional, skip silently
            return
        else:
            # Non-SCF: prerequisite, hard error
            raise MissingPrerequisiteError(
                f"Reference SCF step {reference_scf_step.meta.id} is not done. "
                f"Run SCF first before running {current_step.step_type}."
            )
    
    # Check file exists
    ref_workdir = calc_raw_dir / reference_scf_step.meta.id
    chgcar_src = ref_workdir / "CHGCAR"
    
    if not chgcar_src.exists():
        if is_scf_step(current_step):
            # SCF: optional, skip silently
            return
        else:
            # Non-SCF: prerequisite, hard error
            raise MissingArtifactError(
                f"CHGCAR not found in reference SCF workdir: {ref_workdir}. "
                f"Ensure SCF completed successfully."
            )
    
    # Copy CHGCAR
    curr_workdir = calc_raw_dir / current_step.meta.id
    shutil.copy2(chgcar_src, curr_workdir / "CHGCAR")
```

### 2.5 WAVECAR Staging Rules

| Rule | Behavior |
|------|----------|
| **Optional** | WAVECAR is never a prerequisite |
| **Copy if exists** | From same reference SCF as CHGCAR |
| **Copy failure** | Warning only, does not block execution |
| **Global disable** | Settings can disable WAVECAR copying entirely |
| **No symlinks** | Always copy (cross-platform) |

### 2.6 Fallback Prohibition

**Rule**: Never fall back to an earlier SCF if the most recent one is unavailable.

```
If most_recent_scf.done == False OR most_recent_scf.CHGCAR missing:
    → Non-SCF step MUST error (not silently use older SCF)
    
Rationale: Provenance and topology consistency
```

---

## 3. VASP Workflow Targets (Must Run Locally)

### 3.1 SCF Workflow

**Goal**: Basic self-consistent field calculation.

**Input files**:
- `POSCAR` - Structure
- `INCAR` - Control parameters (IBRION=-1, NSW=0, ISMEAR, SIGMA, ENCUT, LWAVE=.TRUE., LCHARG=.TRUE.)
- `KPOINTS` - Monkhorst-Pack or Gamma-centered mesh
- `POTCAR` - Assembled from species_map

**Key outputs**:
- `OUTCAR` - Detailed output (energy, forces, timing)
- `OSZICAR` - Quick energy convergence (parse first)
- `CHGCAR` - Charge density (artifact for downstream)
- `WAVECAR` - Wavefunction (optional artifact)

**Parser priority**:
1. `OSZICAR` - Fast energy extraction (E0 column)
2. `OUTCAR` - Detailed info (TOTEN, timing, version)
3. `vasprun.xml` - Structured data (optional, fragile)

### 3.2 Bands Workflow

**Goal**: Band structure along high-symmetry k-path.

**Prerequisites**:
- Reference SCF with `done=True` and `CHGCAR` exists

**Input files**:
- `POSCAR` - Same structure as SCF
- `INCAR` - `ICHARG=11` (read CHGCAR, non-SCF), `IBRION=-1`, `NSW=0`, `LWAVE=.FALSE.`
- `KPOINTS` - Line-mode along high-symmetry path
- `POTCAR` - Same as SCF
- `CHGCAR` - **COPIED from reference SCF**

**Key outputs**:
- `OUTCAR` - Band eigenvalues
- `EIGENVAL` - Eigenvalue data (parse for band structure)
- `vasprun.xml` - Structured band data

**Parser priority**:
1. `EIGENVAL` - Direct eigenvalue parsing
2. `vasprun.xml` - If EIGENVAL parsing fails

### 3.3 DOS Workflow

**Goal**: Density of states with dense k-mesh.

**Prerequisites**:
- Reference SCF with `done=True` and `CHGCAR` exists

**Input files**:
- `POSCAR` - Same structure as SCF
- `INCAR` - `ICHARG=11`, `ISMEAR=-5` (tetrahedron), `LORBIT=11` (projected DOS), `NEDOS=3001`
- `KPOINTS` - Dense uniform mesh (denser than SCF)
- `POTCAR` - Same as SCF
- `CHGCAR` - **COPIED from reference SCF**

**Key outputs**:
- `DOSCAR` - DOS data (total and projected)
- `vasprun.xml` - Structured DOS data

**Parser priority**:
1. `DOSCAR` - Direct DOS parsing
2. `vasprun.xml` - Alternative structured source

---

## 4. VASP Binary and POTCAR Locations

### 4.1 Binary Resolution Priority

```
1. Environment variable: QMATS_VASP_STD_BIN (explicit path)
2. Managed install: ~/.qmatsuite/engines/vasp/*/bin/vasp_std
3. System PATH: vasp_std in PATH
```

### 4.2 POTCAR Library Location

```
Primary:  ~/.qmatsuite/engines/vasp/potpaw_PBE/
          ~/.qmatsuite/engines/vasp/potpaw_LDA/

Structure:
~/.qmatsuite/engines/vasp/potpaw_PBE/
├── H/POTCAR
├── H_s/POTCAR
├── Si/POTCAR
├── Si_sv/POTCAR
└── ...
```

### 4.3 POTCAR Assembly

POTCARs are concatenated in **POSCAR species order** (not alphabetical):

```python
def assemble_potcar(structure: Structure, species_map: dict, potcar_root: Path) -> str:
    seen = set()
    potcar_content = []
    for site in structure:
        symbol = site.species_string
        if symbol not in seen:
            seen.add(symbol)
            variant = species_map.get(symbol, {}).get("potcar_variant", symbol)
            potcar_path = potcar_root / variant / "POTCAR"
            potcar_content.append(potcar_path.read_text())
    return "".join(potcar_content)
```

---

## 5. Testing Contract for Proprietary VASP

### 5.1 CI Requirements

| Requirement | Behavior |
|-------------|----------|
| **No real VASP required** | All CI tests must pass without VASP binary |
| **fake_vasp harness** | Generate minimal valid outputs |
| **Skip pattern** | Real VASP tests skipped if binary unavailable |
| **No licensed artifacts** | Never commit POTCAR, WAVECAR, CHGCAR content |

### 5.2 Test Markers

```python
pytestmark = [pytest.mark.integration, pytest.mark.vasp]

@pytest.fixture(scope="module")
def skip_if_vasp_unavailable():
    if not is_vasp_available():
        pytest.skip("VASP not installed")
```

---

## 6. Summary: Behavior Decision Matrix

| Behavior | Decision |
|----------|----------|
| **Workdir pattern** | `calc/raw/<step_ulid>/` (isolated, flat) |
| **Pre-run clean** | Complete rm -rf of workdir contents |
| **Reference step** | Most recent `scf` in topology |
| **Relax barrier** | SCF before relax cannot be reference |
| **CHGCAR for non-scf** | Prerequisite: done=True AND file exists |
| **CHGCAR for scf** | Optional: copy only if done=True AND exists |
| **WAVECAR** | Optional, warning-only on copy failure |
| **Fallback prohibition** | Never use older SCF if recent unavailable |
| **GEN→SPEC(0)** | Silent omission in workflow compilation |
| **Explicit unmapped run** | Hard error |
| **CI tests** | Skip or fake_vasp harness |
