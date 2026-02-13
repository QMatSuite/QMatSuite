# Analysis Objects Review: Current State, 16 NO_ANALYSIS Fixes, and Exhaustive Expansion Roadmap

**Date**: 2026-02-12
**Context**: Post QE Composite Pipelines work. Full demo sweep: 52 demos, 36 OK, 16 NO_ANALYSIS, 0 FAILED.

---

## Part 1: Current Analysis Object Infrastructure

### 1.1 Existing Analysis Object Types (6 types)

| Type | Model Location | Description |
|------|---------------|-------------|
| **convergence** | `core/analysis/convergence/model.py` | SCF + ionic step tracking (energy, delta-E, max-force) |
| **bands** | `core/analysis/band_structure/model.py` | E(k) eigenvalues, high-symmetry points, Fermi energy, projections (4D fatbands) |
| **dos** | `core/analysis/dos/model.py` | Total DOS, PDOS (per-atom per-orbital), Fermi energy |
| **trajectory** | `core/analysis/trajectory/model.py` | Multi-frame geometry snapshots (positions, forces, energy, T, P, stress) |
| **field3d** | `core/analysis/field3d.py` | 3D volumetric grid data (charge density, ELF, Wannier functions) |
| **neb_trajectory** | `qe/parsers/neb_trajectory.py` | NEB path images (QE-only) |

### 1.2 Current Parser Registration Matrix

| Engine | scf_digest | convergence | bands | dos | trajectory | field3d | neb_trajectory |
|--------|:----------:|:-----------:|:-----:|:---:|:----------:|:-------:|:--------------:|
| QE | Y | Y | Y | Y | Y | Y | Y |
| VASP | Y | Y | Y | Y | Y | Y | - |
| ABINIT | Y | Y | Y | Y | Y* | Y | - |
| CP2K | Y | Y | Y | Y | Y | Y | - |
| Siesta | Y | Y | Y | Y | Y | Y | - |
| GPAW | - | - | Y | Y | Y | Y | - |
| LAMMPS | Y | - | - | - | Y | - | - |
| xTB | Y | - | - | - | Y | - | - |
| ORCA | Y | - | - | - | Y | Y | - |
| Gaussian | Y | - | - | - | Y | Y | - |
| Psi4 | - | - | - | - | Y | Y | - |
| PySCF | - | - | - | - | Y | Y | - |
| W90 | Y | - | - | - | - | Y | - |
| QMCPACK | Y | - | - | - | - | - | - |
| Yambo | Y | - | - | - | - | - | - |

*Y = `@register_parser` exists. `-` = no parser registered.*

### 1.3 ANALYSIS_CAPABILITIES (What Triggers Analysis Probing)

The `ANALYSIS_CAPABILITIES` list in each driver's `driver.py` declares which analysis object types
can be produced, for which gen_step_sequence, and with what evidence files. The orchestrator
(`core/analysis/orchestrator.py`) matches capabilities against the run's ordered steps.

| Engine | Declared Capabilities | gen_step_sequences |
|--------|----------------------|-------------------|
| QE | bands, dos, convergence, trajectory, neb_trajectory, field3d | bandspw, dos, scf/relax/md, relax/md, neb, scf |
| VASP | bands, dos, convergence, trajectory, field3d | bandspw, dos, scf/relax/md, relax/md, scf |
| ABINIT | bands, dos, convergence, trajectory, field3d | nscf, nscf, scf/relax, relax/md, scf |
| CP2K | bands, dos, convergence, trajectory, field3d | bandspw, dos, scf/relax, relax/md, scf |
| Siesta | bands, dos, convergence, trajectory, field3d | bands, dos, scf/relax, relax/md, scf |
| GPAW | bands, dos, trajectory, field3d | bandspw, dos, relax/md, scf |
| LAMMPS | trajectory | md, minimize |
| xTB | trajectory | relax, md |
| ORCA | trajectory, field3d | **relax**, scf |
| Gaussian | trajectory, field3d | **relax**, scf |
| Psi4 | trajectory, field3d | **relax**, scf |
| PySCF | trajectory, field3d | **relax**, scf |
| W90 | field3d | wannier |
| **QMCPACK** | **(none declared)** | — |
| **Yambo** | **(none declared)** | — |

### 1.4 ENGINE_ANALYSIS_TYPES (What the Demo Sweep Probes)

From `tools/demo_store/generate_ref_packs_realrun.py`:

```python
ENGINE_ANALYSIS_TYPES = {
    "qe":       ["convergence", "bands", "dos", "trajectory"],
    "vasp":     ["convergence", "bands", "dos", "trajectory"],
    "abinit":   ["convergence", "bands", "dos", "trajectory"],
    "cp2k":     ["convergence", "bands", "dos", "trajectory"],
    "siesta":   ["convergence", "bands", "dos", "trajectory"],
    "gpaw":     ["bands", "dos", "trajectory"],
    "lammps":   ["trajectory"],
    "xtb":      ["trajectory"],
    "orca":     ["trajectory"],
    "gaussian": ["trajectory"],
    "psi4":     ["trajectory"],
    "pyscf":    ["trajectory"],
    "w90":      ["field3d"],
    "yambo":    [],
    "qmcpack":  [],
}
```

---

## Part 2: Root Cause Analysis — 16 NO_ANALYSIS Demos

### 2.1 Failure Breakdown by Root Cause

**Root Cause A: gen_step mismatch** (11 demos)
The demo step uses gen_step `scf`/`td`/`sp`, but the ANALYSIS_CAPABILITIES only declare
`gen_step_sequence=["relax"]` for trajectory. Since the demo isn't a relaxation,
the capability match fails silently.

**Root Cause B: No ANALYSIS_CAPABILITIES declared** (2 demos)
QMCPACK driver declares no capabilities at all.

**Root Cause C: No probed types in ENGINE_ANALYSIS_TYPES** (3 demos, GPAW SCF)
GPAW probes `["bands", "dos", "trajectory"]` but SCF demos produce none of these
(no bandspw/dos/relax step).

### 2.2 Per-Demo Diagnosis and Fix

| # | Demo | Engine | Step gen_type | Root Cause | Fix |
|---|------|--------|--------------|------------|-----|
| 1 | `gaussian_water_hf` | gaussian | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 2 | `gaussian_water_opt` | gaussian | relax | A: probed trajectory should match | **Investigate** — evidence file glob may not match |
| 3 | `gaussian_formaldehyde_tddft` | gaussian | td | A: no capability for `td` | Add `convergence` for `scf`/`td` |
| 4 | `orca_water_sp` | orca | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 5 | `orca_methane_freq` | orca | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 6 | `orca_formaldehyde_tddft` | orca | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 7 | `psi4_water_scf` | psi4 | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 8 | `psi4_ethanol_sp` | psi4 | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 9 | `psi4_h2o_opt` | psi4 | relax | A: probed trajectory should match | **Investigate** — evidence file glob may not match |
| 10 | `pyscf_water_scf` | pyscf | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 11 | `pyscf_h2o_dft` | pyscf | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 12 | `pyscf_n2_mp2` | pyscf | scf | A: only `relax` trajectory capability | Add `convergence` capability for `scf` |
| 13 | `gpaw_al_scf` | gpaw | scf | C: no convergence capability | Add `convergence` capability for `scf` |
| 14 | `gpaw_si_scf` | gpaw | scf | C: no convergence capability | Add `convergence` capability for `scf` |
| 15 | `qmcpack_he_vmc` | qmcpack | vmc | B: no capabilities | Add `convergence` for `vmc`/`dmc` |
| 16 | `qmcpack_h2_vmc` | qmcpack | vmc | B: no capabilities | Add `convergence` for `vmc`/`dmc` |

### 2.3 The Universal Fix: `convergence` for ALL Engines

The `convergence` analysis type is the **single most impactful addition** because:
1. Every engine produces convergence data (SCF iterations, energies)
2. Every demo has at least one SCF-like step
3. The `Convergence` model already supports molecular codes (energy-only, no ionic steps)
4. The Digest parsers already extract all needed data (energy, converged flag, n_iterations)

**What's needed per engine:**

| Engine | Parser exists? | `convergence.py` needed? | Capability gen_steps | Evidence files |
|--------|:-------------:|:------------------------:|---------------------|---------------|
| ORCA | **No** | **Yes, create** | `["scf", "relax", "freq", "td"]` | `*.out` |
| Gaussian | **No** | **Yes, create** | `["scf", "hf", "relax", "freq", "td"]` | `*.log` |
| Psi4 | **No** | **Yes, create** | `["scf", "relax"]` | `results.json` |
| PySCF | **No** | **Yes, create** | `["scf", "relax"]` | `results.json` |
| GPAW | **No** | **Yes, create** | `["scf", "relax"]` | `results.json` |
| QMCPACK | **No** | **Yes, create** | `["vmc", "dmc", "wfopt"]` | `*.scalar.dat` |
| xTB | **No** | **Yes, create** | `["scf", "relax"]` | `*.out` |
| LAMMPS | **No** | **Yes, create** | `["md", "minimize"]` | `log.lammps` |
| W90 | No | Optional (spread convergence) | `["wannier"]` | `*.wout` |
| Yambo | No | Optional (QP convergence) | `["gw"]` | `o-*.qp` |

After adding convergence parsers + capabilities, **update `ENGINE_ANALYSIS_TYPES`** to include
`"convergence"` for all engines that now have it.

### 2.4 Estimated Impact

| Fix | Demos resolved | Effort |
|-----|:-------------:|--------|
| Add `convergence` for ORCA + capability for scf/relax/freq/td | 3 | Small — ORCADigest already has energy + converged |
| Add `convergence` for Gaussian + capability for scf/hf/relax/freq/td | 2-3 | Small — GaussianDigest already has energy + converged |
| Add `convergence` for Psi4 + capability for scf/relax | 2-3 | Small — results.json has energy |
| Add `convergence` for PySCF + capability for scf/relax | 3 | Small — results.json has energy |
| Add `convergence` for GPAW + capability for scf | 2 | Small — results.json has energy |
| Add `convergence` for QMCPACK + capability for vmc/dmc | 2 | Medium — needs scalar.dat parser → Convergence model |
| **Total** | **16** | **~2-3 days** |

---

## Part 3: Exhaustive Analysis Object Expansion Roadmap

### 3.1 Tier 1 — Universal Baseline (Every User Needs These)

These are the "must have" analysis types. Current coverage shown.

| Analysis Type | Model exists? | Engines covered | Engines MISSING | Priority |
|--------------|:------------:|:---------------:|:---------------:|:--------:|
| **convergence** | Yes | QE, VASP, ABINIT, CP2K, Siesta (5/15) | **ORCA, Gaussian, Psi4, PySCF, GPAW, xTB, LAMMPS, QMCPACK, W90, Yambo** | **P0** |
| **bands** | Yes | QE, VASP, ABINIT, CP2K, Siesta, GPAW (6/15) | W90 (interpolated), Yambo (QP-corrected) | P1 |
| **dos** | Yes | QE, VASP, ABINIT, CP2K, Siesta, GPAW (6/15) | (molecular codes N/A) | P1 |
| **trajectory** | Yes | QE, VASP, ABINIT, CP2K, Siesta, GPAW, LAMMPS, xTB, ORCA, Gaussian, Psi4, PySCF (12/15) | QMCPACK, W90, Yambo (N/A) | P1 |
| **field3d** | Yes | QE, VASP, ABINIT, CP2K, Siesta, GPAW, ORCA, Gaussian, Psi4, PySCF, W90 (11/15) | LAMMPS, xTB, QMCPACK, Yambo (N/A) | P2 |

### 3.2 Tier 2 — New Analysis Object Types to Add

#### 3.2.1 `thermochemistry` (NEW type)

**What**: ZPE, enthalpy, entropy, Gibbs free energy, heat capacity from vibrational frequencies.

**Who produces it**: ORCA, Gaussian, xTB (directly in output). CP2K, Psi4, PySCF (computed from frequencies).

**Model sketch**:
```python
@dataclass
class Thermochemistry:
    temperature_K: float
    pressure_atm: float
    zpe_eV: float                    # Zero-point energy
    enthalpy_eV: float               # H(T)
    entropy_eV_per_K: float          # S(T)
    gibbs_free_energy_eV: float      # G(T)
    heat_capacity_eV_per_K: float    # Cp(T) (optional)
    frequencies_cm: list[float]      # All normal mode frequencies
    n_imaginary: int                 # Number of imaginary frequencies
    total_electronic_energy_eV: float
```

**Evidence files**: ORCA `*.out` (thermochemistry section), Gaussian `*.log` (thermochemistry section), xTB `*.out` (thermo data).

**Engines to wire**: ORCA, Gaussian, xTB (from freq output). Later: Psi4, PySCF, QE/phonopy.

**Priority**: P1 (molecular QC users request this constantly)

#### 3.2.2 `excitations` (NEW type)

**What**: Excited state energies, oscillator strengths, wavelengths from TDDFT/EOM-CC.

**Who produces it**: ORCA, Gaussian, CP2K (TDDFT). Psi4, PySCF (EOM-CCSD). GPAW (linear response).

**Model sketch**:
```python
@dataclass
class ExcitedState:
    state_number: int
    energy_eV: float
    wavelength_nm: float
    oscillator_strength: float
    symmetry: str | None
    dominant_transitions: list[dict]  # [{from_orbital, to_orbital, amplitude}]

@dataclass
class Excitations:
    method: str                      # "TDDFT", "EOM-CCSD", "CIS", "CASSCF"
    n_roots: int
    states: list[ExcitedState]
    ground_state_energy_eV: float
```

**Evidence files**: ORCA `*.out` (TDDFT section), Gaussian `*.log` (Excited State lines), CP2K `*.out` (TDDFT-EOM section).

**Data already parsed**: GaussianDigest.`tddft_states` has `{energy_eV, wavelength_nm, oscillator_strength}`. ORCADigest doesn't have this yet but the output format is well-defined.

**Priority**: P1 (photochemistry, spectroscopy users)

#### 3.2.3 `frequencies` (NEW type)

**What**: Normal mode frequencies, IR intensities, Raman activities. Distinct from thermochemistry (which is derived from frequencies).

**Model sketch**:
```python
@dataclass
class VibrationalMode:
    frequency_cm: float
    ir_intensity: float | None       # km/mol
    raman_activity: float | None     # A^4/amu
    symmetry: str | None
    is_imaginary: bool

@dataclass
class Frequencies:
    modes: list[VibrationalMode]
    n_atoms: int
    n_modes: int                     # 3N-6 (nonlinear) or 3N-5 (linear)
    ir_spectrum: list[tuple[float, float]] | None   # (wavenumber, intensity) pairs
    raman_spectrum: list[tuple[float, float]] | None
```

**Evidence files**: ORCA `*.out` (VIBRATIONAL FREQUENCIES section), Gaussian `*.log` (Frequencies section), xTB `*.out` (hessian).

**Priority**: P2 (common characterization but less universal than energy/structure)

#### 3.2.4 `qmc_statistics` (NEW type — QMCPACK-specific)

**What**: QMC energy estimators with statistical error analysis, variance, correlation time, reblocking.

**Model sketch**:
```python
@dataclass
class QMCStatistics:
    method: str                      # "vmc", "dmc", "optimization"
    energy_Ha: float                 # Mean LocalEnergy
    energy_error_Ha: float           # Statistical error of mean
    energy_variance_Ha2: float       # LocalEnergy variance
    accept_ratio: float
    n_blocks: int
    n_walkers: int
    correlation_time: float | None   # Autocorrelation time
    reblocking_optimal_block: int | None
    series_data: list[dict] | None   # Per-series [{energy, error, variance}]
```

**Evidence files**: `*.scalar.dat` (per-block statistics), `*.stat.h5` (HDF5 stats).

**Priority**: P1 for QMCPACK (this IS the primary output of QMC)

#### 3.2.5 `gw_corrections` (NEW type — Yambo/ABINIT)

**What**: GW quasiparticle corrections to DFT eigenvalues.

**Model sketch**:
```python
@dataclass
class QPCorrection:
    k_point: list[float]
    band_index: int
    e_dft_eV: float
    e_qp_eV: float
    z_factor: float                  # Renormalization factor
    sigma_x_eV: float | None        # Exchange self-energy
    sigma_c_eV: float | None        # Correlation self-energy

@dataclass
class GWCorrections:
    method: str                      # "G0W0", "scGW", "GW0"
    n_qp_corrections: int
    corrections: list[QPCorrection]
    dft_gap_eV: float
    qp_gap_eV: float
    fundamental_gap_eV: float | None
```

**Evidence files**: Yambo `o-*.qp` (quasiparticle corrections table), ABINIT `*_GW` files.

**Data already parsed**: YamboDigest has `qp_gap_eV`, `dft_gap_eV`, `n_qp_corrections`.

**Priority**: P2 (GW users are specialized but growing)

#### 3.2.6 `optical_spectrum` (NEW type — Yambo/VASP/ABINIT/GPAW)

**What**: Frequency-dependent dielectric function / absorption spectrum from BSE, RPA, or TDDFT.

**Model sketch**:
```python
@dataclass
class OpticalSpectrum:
    method: str                      # "BSE", "RPA", "IP", "TDDFT"
    energies_eV: list[float]
    epsilon_real: list[float]        # Re[epsilon(omega)]
    epsilon_imag: list[float]        # Im[epsilon(omega)]
    absorption_coeff: list[float] | None  # alpha(omega)
    static_dielectric: float | None  # epsilon(0)
    n_spectrum_points: int
```

**Evidence files**: Yambo `o-*.eps_q1_ip`/`o-*.eps_q1_bse`, VASP `OPTIC` files, ABINIT `*_DS*_EIG` + `*_DS*_SCR`.

**Data already parsed**: YamboDigest has `spectrum_type`, `static_dielectric`, `n_spectrum_points`.

**Priority**: P2 (optical materials users)

#### 3.2.7 `wannier_summary` (NEW type — W90)

**What**: Wannier function localization summary — spreads, centers, disentanglement convergence.

**Model sketch**:
```python
@dataclass
class WannierSummary:
    num_wann: int
    num_bands: int
    converged: bool
    total_spread_A2: float           # Omega total
    invariant_spread_A2: float       # Omega_I
    diagonal_spread_A2: float        # Omega_D
    offdiagonal_spread_A2: float     # Omega_OD
    wf_centres: list[list[float]]    # Per-WF centers [x,y,z]
    wf_spreads: list[float]          # Per-WF spread (Ang^2)
    disentanglement_converged: bool | None
    n_iterations: int
```

**Evidence files**: `*.wout` (Wannier90 stdout).

**Data already parsed**: W90Digest has ALL these fields.

**Priority**: P2 (Wannier users want this; spreads are the key quality metric)

#### 3.2.8 `phonon_bands` (NEW type)

**What**: Phonon dispersion omega(q) along high-symmetry paths.

**Model sketch**:
```python
@dataclass
class PhononBands:
    q_distances: list[float]
    frequencies_THz: list[list[float]]  # [n_branches × n_qpoints]
    high_symmetry_points: list[HighSymPoint]
    n_atoms: int
    n_branches: int                     # 3 * n_atoms
```

**Who produces it**: QE (matdyn.x), ABINIT (anaddb), VASP (via phonopy), CP2K (via phonopy).

**Evidence files**: QE `*.freq.gp` or `matdyn.freq`, ABINIT `*_PHBST.nc`, phonopy `band.yaml`.

**Priority**: P2 (very common for periodic systems, but requires multi-step workflows)

#### 3.2.9 `phonon_dos` (NEW type)

**What**: Vibrational density of states g(omega).

**Model sketch**:
```python
@dataclass
class PhononDOS:
    frequencies_THz: list[float]
    total_dos: list[float]
    pdos: list[list[float]] | None   # Per-atom projected phonon DOS
    atom_labels: list[str] | None
```

**Who produces it**: Same engines as phonon_bands.

**Priority**: P2

#### 3.2.10 `elastic_tensor` (NEW type)

**What**: Full 6x6 elastic stiffness matrix C_ij, derived bulk/shear/Young's moduli.

**Model sketch**:
```python
@dataclass
class ElasticTensor:
    c_ij: list[list[float]]          # 6x6 Voigt notation (GPa)
    bulk_modulus_voigt_GPa: float
    bulk_modulus_reuss_GPa: float
    bulk_modulus_vrh_GPa: float
    shear_modulus_voigt_GPa: float
    shear_modulus_reuss_GPa: float
    shear_modulus_vrh_GPa: float
    youngs_modulus_GPa: float
    poissons_ratio: float
```

**Who produces it**: VASP (IBRION=6), QE (thermo_pw/ElaStic), ABINIT (anaddb), LAMMPS (elastic script).

**Priority**: P3 (mechanical properties, important for materials screening)

#### 3.2.11 `dielectric_properties` (NEW type)

**What**: Static and high-frequency dielectric tensor, Born effective charges, piezoelectric tensor.

**Model sketch**:
```python
@dataclass
class DielectricProperties:
    epsilon_electronic: list[list[float]]  # 3x3 electronic dielectric tensor
    epsilon_static: list[list[float]] | None  # 3x3 static (ionic + electronic)
    born_charges: list[list[list[float]]] | None  # Per-atom 3x3 Born Z*
    piezoelectric_tensor: list[list[float]] | None  # 3x6 piezoelectric e_ij
```

**Who produces it**: QE (ph.x DFPT), ABINIT (DFPT), VASP (DFPT/finite field).

**Priority**: P3

#### 3.2.12 `molecular_properties` (NEW type)

**What**: Scalar molecular properties — dipole, polarizability, charge, spin.

**Model sketch**:
```python
@dataclass
class MolecularProperties:
    total_energy_eV: float
    dipole_moment_D: float | None
    dipole_vector: list[float] | None  # [x, y, z] in Debye
    polarizability: list[list[float]] | None  # 3x3 tensor (a.u.)
    charge: int
    multiplicity: int
    homo_eV: float | None
    lumo_eV: float | None
    homo_lumo_gap_eV: float | None
    mulliken_charges: list[float] | None
    mulliken_spins: list[float] | None
```

**Who produces it**: ORCA, Gaussian, Psi4, PySCF, xTB.

**Data already parsed**: GaussianDigest.`dipole_debye`, xTBDigest.`homo_lumo_gap_eV`.

**Priority**: P2 (every molecular QC user)

#### 3.2.13 `md_statistics` (NEW type)

**What**: Time-averaged thermodynamic properties from MD: T, P, E profiles, RDF, MSD, diffusion.

**Model sketch**:
```python
@dataclass
class MDStatistics:
    timesteps: list[int]
    time_ps: list[float]
    temperature_K: list[float]
    pressure_GPa: list[float] | None
    total_energy_eV: list[float]
    kinetic_energy_eV: list[float]
    potential_energy_eV: list[float]
    avg_temperature_K: float
    avg_pressure_GPa: float | None
    rdf: list[tuple[float, float]] | None   # (r, g(r))
    msd: list[tuple[float, float]] | None   # (t, MSD)
    diffusion_coeff: float | None           # cm^2/s
```

**Who produces it**: LAMMPS (log.lammps thermo), CP2K (energy file), VASP (AIMD), xTB (MD).

**Priority**: P2 (essential for MD users, LAMMPS is a major engine)

#### 3.2.14 `neb_path` (Generalize existing `neb_trajectory`)

**What**: Minimum energy path with reaction coordinate, images, barrier height.

Currently QE-only (`neb_trajectory`). Should be generalized for VASP NEB, LAMMPS NEB.

**Model sketch**:
```python
@dataclass
class NEBPath:
    n_images: int
    reaction_coordinate: list[float]
    energies_eV: list[float]
    forward_barrier_eV: float
    reverse_barrier_eV: float
    images: list[GeometryFrame]
    converged: bool
```

**Who produces it**: QE (neb.x), VASP (NEB), LAMMPS (neb fix), ORCA (NEB).

**Priority**: P3 (catalysis, diffusion)

### 3.3 Summary: Expansion Priority Matrix

| Priority | Analysis Type | New model? | Engines to wire | Demo impact |
|:--------:|--------------|:----------:|:---------------:|:-----------:|
| **P0** | convergence (extend to ALL engines) | No (exists) | +10 engines | **Fixes all 16 NO_ANALYSIS** |
| **P1** | thermochemistry | **Yes** | ORCA, Gaussian, xTB, Psi4, PySCF | New demos possible |
| **P1** | excitations | **Yes** | ORCA, Gaussian, CP2K, Psi4, PySCF | Covers TDDFT demos |
| **P1** | qmc_statistics | **Yes** | QMCPACK | Primary QMCPACK output |
| **P2** | frequencies | **Yes** | ORCA, Gaussian, xTB | IR/Raman spectra |
| **P2** | gw_corrections | **Yes** | Yambo, ABINIT | Primary Yambo output |
| **P2** | optical_spectrum | **Yes** | Yambo, VASP, ABINIT, GPAW | BSE/optics |
| **P2** | wannier_summary | **Yes** | W90 | Primary W90 output |
| **P2** | molecular_properties | **Yes** | ORCA, Gaussian, Psi4, PySCF, xTB | Dipole, charges |
| **P2** | md_statistics | **Yes** | LAMMPS, CP2K, VASP, xTB | Thermo time series |
| **P2** | phonon_bands | **Yes** | QE, ABINIT, VASP, CP2K | Lattice dynamics |
| **P2** | phonon_dos | **Yes** | QE, ABINIT, VASP, CP2K | Vibrational DOS |
| **P3** | elastic_tensor | **Yes** | VASP, QE, ABINIT, LAMMPS | Mechanical properties |
| **P3** | dielectric_properties | **Yes** | QE, ABINIT, VASP | DFPT properties |
| **P3** | neb_path (generalize) | Extend | VASP, LAMMPS, ORCA | Reaction barriers |

---

## Part 4: Per-Engine Roadmap

### 4.1 ORCA (3 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, extract from `*.out`: SCF energy per cycle, converged flag. Add capability for `["scf", "relax", "freq", "td", "hf"]` |
| 2 | thermochemistry | Parse thermochemistry section from freq output (ZPE, H, S, G, Cp at 298.15K) |
| 3 | excitations | Parse TDDFT excited states (energies, oscillator strengths, dominant transitions) |
| 4 | frequencies | Parse VIBRATIONAL FREQUENCIES + IR intensities + Raman activities |
| 5 | molecular_properties | Parse dipole moment, Mulliken charges, orbital energies |

### 4.2 Gaussian (3 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, extract from `*.log`: SCF Done energy, convergence. Add capability for `["scf", "hf", "relax", "freq", "td", "mp2"]` |
| 2 | thermochemistry | Parse thermochemistry (ZPE, thermal corrections, G). Data partly in GaussianDigest already |
| 3 | excitations | Parse Excited State lines. Data partly in GaussianDigest.`tddft_states` already |
| 4 | frequencies | Parse Frequencies/IR/Raman sections |
| 5 | molecular_properties | Parse dipole (already in GaussianDigest), NBO, Mulliken charges |

### 4.3 Psi4 (3 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, parse `results.json` energy/converged. Add capability for `["scf", "relax"]` |
| 2 | molecular_properties | Parse energy, dipole from results.json |

### 4.4 PySCF (3 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, parse `results.json` energy/converged. Add capability for `["scf", "relax"]` |
| 2 | molecular_properties | Parse energy, method, orbital energies from results.json |

### 4.5 GPAW (2 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, parse `results.json` or GPAW text output. Add capability for `["scf"]` |

### 4.6 QMCPACK (2 NO_ANALYSIS demos to fix)

| Step | Type | What to do |
|------|------|-----------|
| 1 | qmc_statistics | Create `parsers/qmc_statistics.py`, parse `*.scalar.dat` (block-averaged energy, variance, accept ratio). This IS QMCPACK's primary analysis output |
| 2 | convergence | Optionally map to convergence model (energy per block → convergence series) |

### 4.7 Yambo (0 NO_ANALYSIS demos, but needs analysis for composite demos)

| Step | Type | What to do |
|------|------|-----------|
| 1 | gw_corrections | Parse `o-*.qp` file for quasiparticle corrections. YamboDigest already extracts summary |
| 2 | optical_spectrum | Parse `o-*.eps_q1_*` for dielectric function / absorption |

### 4.8 W90 (0 NO_ANALYSIS demos, but needs analysis for composite demos)

| Step | Type | What to do |
|------|------|-----------|
| 1 | wannier_summary | Parse `*.wout` for spreads, centers, convergence. W90Digest already has all fields |
| 2 | bands | Parse interpolated band structure from `*_band.dat` (Wannier-interpolated E(k)) |

### 4.9 xTB (0 NO_ANALYSIS demos)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Create `parsers/convergence.py`, parse `*.out` for SCF convergence. Add capability for `["scf"]` |
| 2 | thermochemistry | Parse thermo output (mRRHO) from frequency calculations |

### 4.10 LAMMPS (0 NO_ANALYSIS demos)

| Step | Type | What to do |
|------|------|-----------|
| 1 | convergence | Parse `log.lammps` thermo output for minimize convergence |
| 2 | md_statistics | Parse thermo data (T, P, E time series) from `log.lammps` |

---

## Part 5: What OTHER Workflow Tools Provide (Competitive Analysis)

### 5.1 AiiDA (aiida-core + plugins)

AiiDA uses `Data` nodes for all outputs. Key analysis-relevant types:
- `BandsData` — band structure
- `TrajectoryData` — MD/optimization trajectory
- `ArrayData` — generic arrays (forces, stress, etc.)
- `XyData` — 1D x-y plots (DOS, spectra)
- `Dict` — structured results (convergence, parameters)
- Plugin-specific: `PhononWorkChain` (aiida-phonopy), `DielectricWorkChain` (aiida-vibroscopy), `PwBandsWorkChain` (aiida-quantumespresso)

### 5.2 atomate2 / emmet-core (Materials Project)

Full document schemas from emmet-core:
- `ElectronicStructureDoc` (bands + DOS)
- `PhononBSDoc` (phonon bands + DOS)
- `ElasticityDoc` (elastic tensor + moduli)
- `DielectricDoc` (dielectric tensor)
- `PiezoelectricDoc` (piezoelectric tensor)
- `MagnetismDoc` (ordering, moments)
- `AbsorptionDoc` (optical absorption)
- `EOSDoc` (equation of state)
- `DefectDoc` (point defect energetics)
- `SurfacePropDoc` (surface energies)
- `GrainBoundaryDoc` (GB energies)
- `ElectrodeDoc` (battery voltage profiles)
- `XASDoc` (X-ray absorption)
- `ThermoDoc` (formation energy, stability)

### 5.3 ASE (Atomic Simulation Environment)

ASE focuses on calculators and doesn't have formal analysis types, but provides:
- `ase.thermochemistry` — `IdealGasThermo`, `CrystalThermo`, `HarmonicThermo`
- `ase.phonons` — `Phonons` class with band structure and DOS
- `ase.dft.bandgap` — `bandgap()` utility
- `ase.eos` — `EquationOfState` fitter
- `ase.neb` — `NEB` analysis
- `ase.md.analysis` — MD post-processing (diffusion, RDF)

---

## Part 6: Recommended Implementation Order

### Phase 1: Fix 16 NO_ANALYSIS (P0)

**Goal**: All 52 demos produce at least one analysis bundle.

1. Create `convergence.py` parsers for: ORCA, Gaussian, Psi4, PySCF, GPAW, QMCPACK
2. Add `ANALYSIS_CAPABILITIES` entries for convergence in each driver
3. Update `ENGINE_ANALYSIS_TYPES` in `generate_ref_packs_realrun.py`
4. Also add convergence for xTB and LAMMPS (already have parsers? No — create them)
5. Run full demo sweep → expect 52 OK (or 52 - some = OK + those without convergence)

**Estimated effort**: 2-3 days

### Phase 2: Engine-Specific Primary Outputs (P1)

**Goal**: Each engine produces its "signature" analysis type.

6. `qmc_statistics` for QMCPACK (this IS what QMC produces)
7. `thermochemistry` for ORCA, Gaussian, xTB
8. `excitations` for ORCA, Gaussian (TDDFT demos exist)

**Estimated effort**: 3-5 days

### Phase 3: Molecular QC Analysis Suite (P2)

**Goal**: Feature parity across molecular engines.

9. `frequencies` for ORCA, Gaussian, xTB
10. `molecular_properties` for ORCA, Gaussian, Psi4, PySCF, xTB
11. `gw_corrections` for Yambo
12. `optical_spectrum` for Yambo
13. `wannier_summary` for W90

**Estimated effort**: 5-7 days

### Phase 4: Periodic Systems Advanced (P2-P3)

**Goal**: Coverage for periodic DFT advanced properties.

14. `md_statistics` for LAMMPS, CP2K
15. `phonon_bands` + `phonon_dos` for QE, ABINIT (from DFPT)
16. `elastic_tensor` for VASP, QE
17. `dielectric_properties` for QE, ABINIT
18. Generalize `neb_path` from QE-only to VASP, LAMMPS

**Estimated effort**: 7-10 days

---

## Appendix A: Complete Suggested Analysis Object Type List

| # | Type | Category | New model? | Engine count | Priority |
|---|------|---------|:----------:|:------------:|:--------:|
| 1 | convergence | Energetics | Exists | 15 (extend) | P0 |
| 2 | bands | Electronic | Exists | 6+ | P1 |
| 3 | dos | Electronic | Exists | 6+ | P1 |
| 4 | trajectory | Structural | Exists | 12 | P1 |
| 5 | field3d | Electronic | Exists | 11 | P2 |
| 6 | neb_trajectory | Reaction | Exists (QE-only) | 1 | P3 |
| 7 | **thermochemistry** | Vibrational | **New** | 5+ | **P1** |
| 8 | **excitations** | Optical | **New** | 5+ | **P1** |
| 9 | **qmc_statistics** | QMC | **New** | 1 | **P1** |
| 10 | **frequencies** | Vibrational | **New** | 5+ | **P2** |
| 11 | **gw_corrections** | Electronic | **New** | 2 | **P2** |
| 12 | **optical_spectrum** | Optical | **New** | 4+ | **P2** |
| 13 | **wannier_summary** | Topological | **New** | 1 | **P2** |
| 14 | **molecular_properties** | Misc | **New** | 5 | **P2** |
| 15 | **md_statistics** | MD | **New** | 4+ | **P2** |
| 16 | **phonon_bands** | Vibrational | **New** | 4 | **P2** |
| 17 | **phonon_dos** | Vibrational | **New** | 4 | **P2** |
| 18 | **elastic_tensor** | Mechanical | **New** | 4 | **P3** |
| 19 | **dielectric_properties** | Optical | **New** | 3 | **P3** |
| 20 | **neb_path** | Reaction | Extend | 4 | **P3** |
| 21 | **surface_energy** | Surface | **New** | 2 | **P3** |
| 22 | **defect_energy** | Defect | **New** | 2 | **P3** |

**Total**: 6 existing + 16 new = **22 analysis object types**

---

## Appendix B: Data Already Available in Digest Parsers

Much of the data for new convergence parsers is ALREADY extracted by the existing `scf_digest` parsers
in each engine's `parsers/output.py`. The convergence parser can often be a thin wrapper that
reformats Digest fields into the `Convergence` model.

| Engine | Digest has energy? | Digest has converged? | Digest has n_iterations? |
|--------|:------------------:|:---------------------:|:------------------------:|
| ORCA | Yes (`final_energy_eV`) | Yes (`converged_scf`) | Yes (`n_scf_cycles`) |
| Gaussian | Yes (`final_energy_eV`) | Yes (`converged_scf`) | Yes (`n_scf_cycles`) |
| xTB | Yes (`final_energy_eV`) | Yes (via `success`) | No (add iteration count) |
| LAMMPS | Yes (`final_energy`) | Yes (`converged_minimize`) | Yes (`minimize_iterations`) |
| W90 | Yes (via spread) | Yes (`converged`) | Yes (`num_iter_completed`) |
| Yambo | Yes (`qp_gap_eV`) | Yes (`success`) | No |
| QMCPACK | Yes (`energy_Ha`) | Yes (`success`) | Yes (`n_blocks`) |
| GPAW | No scf_digest | — | — (parse results.json) |
| Psi4 | No scf_digest | — | — (parse results.json) |
| PySCF | No scf_digest | — | — (parse results.json) |
