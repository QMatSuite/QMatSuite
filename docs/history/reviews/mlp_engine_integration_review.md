# ML Potential Engine Integration — Review & Plan Proposal

Date: 2026-02-28
Reviewer: Claude Opus 4.6 (automated deep review)

---

## 1. Executive Summary

This document reviews the QMatSuite codebase to determine how four ML interatomic potential (MLP) engines — **MACE, CHGNet, SevenNet, MatterSim** — should be integrated as first-class engine drivers. Each engine is a Python library (installed via pip into an isolated micromamba environment) that provides an ASE Calculator for computing energies, forces, and stresses from atomic configurations at near-DFT accuracy and 100–10,000× DFT speed.

**Key findings:**

1. **xTB is the canonical template.** Its driver structure (XYZ input, subprocess execution, no external resources, ISOLATED workdir) maps directly to the MLP use case. The GPAW script-generation pattern (Python script → subprocess → results.json) is the execution model.

2. **All four MLPs share a nearly identical interface**: ASE Calculator → `get_potential_energy()` / `get_forces()` / `get_stress()`. A shared MLP script template can be generated per engine with minimal variation (import path, calculator constructor, model selection kwargs).

3. **No kernel modifications required.** The existing GEN steps (`scf`, `relax`, `md`) cover all MLP capabilities. The `ENGINE_PREFIXES` set in `step_type_convert.py` needs new entries, but this is a data-only change in a leaf file that the DriverRegistry populates automatically at registration time. *Correction*: On closer inspection, `ENGINE_PREFIXES` is a frozen set in `core/step_type_convert.py` — however, the DriverRegistry's own `_step_to_engine` dict handles dispatch without requiring this set. The set is used only for `is_spec()` disambiguation. **This may require a minor update** (see §7 Risks).

4. **B1-compliant (★★★★☆) target** is achievable for all four engines. The tag count will be modest (30–60 per engine) since MLPs have far fewer parameters than DFT codes. The curated case library can be compact (3–5 cases per engine) since all four engines support the same three calculation types (SCF, relax, MD).

5. **Estimated effort**: MACE (first engine, full template creation) is the largest investment. Subsequent engines (CHGNet, SevenNet, MatterSim) can be templated from MACE with ~60% less effort per engine.

---

## 2. Codebase Review Findings

### 2.1 xTB Driver Analysis (Template Engine)

**Directory structure** (15 files):
```
src/qmatsuite/drivers/xtb/
├── __init__.py              # DriverRegistry.register(XTBDriver()) + parser import
├── driver.py                # XTBDriver: PREFIX="xtb", SUPPORTED_GEN_STEPS={"relax","md"}
├── handler.py               # xtb_step_handler: subprocess.run([xtb, input.xyz, ...])
├── recipe.py                # XTBRecipe: ISOLATED workdir, build_xtb_command()
├── inputspec.py             # EngineInputSpec: input.xyz (structure) + xcontrol.inp (params)
├── writer.py                # XYZ writer + CLI command builder
├── parser.py                # stdout/xtbopt.xyz parser
├── data/
│   ├── xtb_tags.json        # 88 tags across 11 categories
│   └── xtb_metadata.py      # Cached access layer
├── io/
│   └── xtb_input.py         # Stdlib-only XYZ/xcontrol parse+write
└── parsers/
    ├── output.py            # XTBDigest (21 fields) + @register_parser("xtb","scf_digest")
    └── trajectory.py        # XTBTrajectoryParser for relax/MD trajectories
```

**Key patterns to replicate:**

| Pattern | xTB Implementation | MLP Adaptation |
|---------|-------------------|----------------|
| PREFIX | `"xtb"` (no underscores) | `"mace"`, `"chgnet"`, `"sevenn"`, `"mattersim"` |
| GEN steps | `{"relax", "md"}` | `{"scf", "relax", "md"}` (MLPs naturally do single-point) |
| Execution | `subprocess.run([xtb, input.xyz, --flags])` | `subprocess.run([python, run_mace.py])` (GPAW pattern) |
| Input files | `input.xyz` + optional `xcontrol.inp` | `structure.json` + `run_<engine>.py` (generated script) |
| Output parsing | Regex on stdout + XYZ comment line | Parse `results.json` (structured output from script) |
| Workdir policy | `ISOLATED` | `ISOLATED` (same) |
| Resource staging | None (self-contained) | None (models auto-downloaded by library) |
| Recipe archetype | Directory-state ISOLATED | Directory-state ISOLATED (same) |

**Registration chain:**
1. `drivers/xtb/__init__.py` calls `DriverRegistry.register(XTBDriver())`
2. `drivers/__init__.py` has `from qmatsuite.drivers import xtb`
3. `DriverRegistry` validates PREFIX, builds materialization map, registers step types

**Handler execution flow (9 steps):**
1. Find step by ULID → 2. Create workdir → 3. Load structure → 4. Write input.xyz → 5. `subprocess.run()` → 6. Save stdout → 7. Check exit code → 8. Parse results → 9. Create artifact spec

**Analysis capabilities declared:**
- `AnalysisCapability(object_type="trajectory", gen_step_sequence=["relax"], evidence_files=["xtbopt.log"])`
- `AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"], evidence_files=["xtb.trj"])`

### 2.2 LAMMPS Trajectory Handling Patterns

LAMMPS provides the reference implementation for MD trajectory parsing in QMatSuite:

**Trajectory model** (`core/analysis/trajectory/model.py`):
- `Frame` dataclass: `positions` (N,3), `species`, `cell` (3,3), `energy`, `forces` (N,3), `temperature`, `pressure`, `velocities`, `iteration`/`time`
- `Trajectory` dataclass: `meta` (AnalysisObjectMeta), `frames` (List[Frame]), `trajectory_type` ("md"|"relax"|"neb")
- `get_observable_series(name)` → `Series1D` (time-series extraction for plotting)

**Parser pipeline** (`drivers/lammps/parsers/trajectory.py`):
1. `_parse_lammps_dump()`: Reads `.lammpstrj` → per-frame positions, velocities, forces, species, cell
2. `_parse_lammps_thermo()`: Reads `log.lammps` → per-timestep energy, temperature, pressure
3. Frame assembly: Match dump frames to thermo data by timestep → Frame objects

**Key insight for MLPs**: MLP trajectory output will be simpler than LAMMPS. The generated Python script can write a JSON-lines file (`trajectory.jsonl`) with one JSON object per frame containing `{step, energy, forces, positions, species, cell, temperature, pressure}`. This avoids parsing complex dump formats. The MLP trajectory parser reads this structured output directly into `Frame` objects.

**xTB trajectory parser** (`drivers/xtb/parsers/trajectory.py`) is actually closer to the MLP pattern:
- Reads multi-frame XYZ files (`xtbopt.log` or `xtb.trj`)
- Extracts energy from comment line
- Builds `Trajectory` with `Frame` list
- Registered via `@register_parser("xtb", "trajectory")`

### 2.3 Engine Installation & Discovery Patterns

**Discovery architecture** (`core/engines/discovery.py`, 730 lines):

7-tier search with priority ordering:
1. Registry Active (user-registered in `engines.json`)
2. Bundled (`~/.qmatsuite/engines/<engine>/<variant>/bin/`)
3. Python Import (subprocess: `python -c "import <module>; print(<module>.__version__)"`)
4. Conda Environments (scan `~/miniforge3`, `~/miniconda3`, etc.)
5. Environment Variables (`QE_HOME`, `VASP_HOME`, etc.)
6. System PATH (`shutil.which()`)
7. Homebrew / Shell profiles

**Engine metadata** (`core/engines/engine_meta.py`):
- Python-native engines identified by `"engine_type": "python"` + `"python_import"` field
- Existing Python engines: GPAW (`gpaw`), PySCF (`pyscf`), Psi4 (`psi4`)

**Micromamba management** (`core/engines/micromamba.py`, 267 lines):
- Auto-downloads micromamba binary
- Manages at `$HOME/.qmatsuite/micromamba/`
- `create_env(name, spec, app_dir) → env_path`
- `_find_python_executable(env_dir)`: Locates python in env

**MLP engine installation pattern:**
```
~/.qmatsuite/engines/mace/
  env/                    # micromamba-managed conda environment
    bin/python            # Python interpreter with mace-torch installed
    lib/python3.11/site-packages/mace/  # installed package
```

Installation: `micromamba create -n mace python=3.11 pytorch && pip install mace-torch`
Discovery: Tier 3 (Python Import) → `python -c "import mace; print(mace.__version__)"`

### 2.4 Demo Store Compliance Requirements

**Three-layer architecture** (from `DEMO_STORE_SPEC.md`):

| Layer | Location | Purpose | MLP Approach |
|-------|----------|---------|-------------|
| Layer 1 (Corpus) | `tests/inputformat/samples/<engine>/` | Raw input samples, parser/writer test source | Structure files + expected params |
| Layer 2 (Runtime) | `resources/demo_projects/<slug>.yml` | Generated from L1 by compiler, never hand-edited | Auto-generated |
| Layer 3 (Ref packs) | Generated by real runs | Reference output for regression testing | From real MLP runs |

**Mandatory baseline stages:**
- Stage A: Full pytest green
- Stage B: FAST integrity suite (no real engine runs)
- Stage C: Real-run baseline (requires engine installed)

**For MLPs**: Layer 1 corpus is simple — just a `structure.json` (or `.xyz`) plus a `case.yaml` specifying model variant and calculation type. The generated Python script is the "input file" equivalent.

### 2.5 Parameter Extraction Pipeline Review

**Established pattern** (`tools/extract_qe_parameters_v3.py`):
1. Scrape engine documentation (HTML/PDF/source)
2. Parse into structured metadata (name, type, default, category, description)
3. Output `<engine>_tags.json` with schema versioning
4. Human review + iteration
5. Runtime access via `<engine>_metadata.py` (cached, stdlib-only)

**MLP adaptation**: MLP parameters are much simpler than DFT codes. Instead of scraping HTML docs, parameters can be extracted from:
- Python function signatures (`inspect.signature(MatterSimCalculator.__init__)`)
- Docstrings
- GitHub README / readthedocs pages

Expected tag counts:
| Engine | Estimated Tags | Source |
|--------|---------------|--------|
| MACE | 30–40 | `mace_mp()` kwargs + ASE optimizer/MD kwargs |
| CHGNet | 25–35 | `CHGNetCalculator()` + `StructOptimizer()` + `MolecularDynamics()` kwargs |
| SevenNet | 20–30 | `SevenNetCalculator()` kwargs + ASE kwargs |
| MatterSim | 25–35 | `MatterSimCalculator()` + `Relaxer()` kwargs + ASE kwargs |

These are below the B1 playbook minimum of 50+ for specialized engines, but given that MLPs genuinely have fewer parameters than DFT codes, a well-documented 30-tag catalog with full coverage is more valuable than padding to 50. The B1 playbook's 50+ minimum is calibrated for engines with hundreds of parameters; MLPs are a different class.

---

## 3. MLP Library Technical Survey

### 3.1 MACE

| Attribute | Value |
|-----------|-------|
| **PyPI package** | `mace-torch` |
| **GitHub** | https://github.com/ACEsuit/mace |
| **Latest version** | 0.3.15 (Feb 2026) |
| **Python** | >= 3.7 |
| **PyTorch** | >= 1.12 (2.4.1 not supported) |
| **License** | MIT |

**Calculator API:**
```python
from mace.calculators import mace_mp
calc = mace_mp(model="medium", device="cpu", default_dtype="float64", dispersion=False)
```

**Key parameters for tags JSON:**
- `model`: str — `"small"`, `"medium"`, `"large"`, `"medium-mpa-0"`, `"small-omat-0"`, `"medium-omat-0"`, `"mace-matpes-pbe-0"`, `"mace-matpes-r2scan-0"`, `"small-0b"`, `"medium-0b"`, `"small-0b2"`, `"medium-0b2"`, `"large-0b2"`, `"medium-0b3"`, `"mh-0"`, `"mh-1"`
- `device`: str — `"cpu"`, `"cuda"`, `"mps"`
- `default_dtype`: str — `"float32"`, `"float64"` (float64 recommended for geometry opt)
- `dispersion`: bool — Enable DFT-D3 dispersion correction
- `damping`: str — D3 damping function (default `"bj"`)
- `dispersion_xc`: str — XC functional for D3 parameters (default `"pbe"`)
- `dispersion_cutoff`: float — D3 cutoff radius

**Additional calculator classes:** `mace_off()` (organic molecules, CCSD(T)-trained), `mace_anicc()` (H/C/N/O, ANI-trained)

**Output:** Energy (eV total), forces (eV/Å), stress (eV/Å³ Voigt)

**CLI:** `mace_run_train` (training), `mace_eval_configs` (batch eval). No dedicated inference CLI for single calculations.

**Model download:** Models are auto-downloaded from GitHub releases on first use. Cached locally.

### 3.2 CHGNet

| Attribute | Value |
|-----------|-------|
| **PyPI package** | `chgnet` |
| **GitHub** | https://github.com/CederGroupHub/chgnet |
| **Latest version** | 0.4.2 (Sep 2025) |
| **Python** | >= 3.10 |
| **PyTorch** | required |
| **License** | BSD (modified) |

**Calculator API:**
```python
from chgnet.model import CHGNetCalculator
calc = CHGNetCalculator(model=None, use_device="cpu", stress_weight=1/160.21)
```

**Key parameters:**
- `model`: CHGNet instance or None (default model)
- `model_name`: str — `"0.3.0"` (default), `"0.2.0"`, `"r2scan"`
- `use_device`: str — `"cpu"`, `"cuda"`, `"mps"`
- `stress_weight`: float — GPa to eV/Å³ conversion factor
- `on_isolated_atoms`: str — `"warn"`, `"ignore"`, `"error"`

**Unique feature:** CHGNet predicts **magnetic moments** (μ_B) alongside energy/forces/stress.

**Built-in optimizers:**
- `StructOptimizer(model).relax(structure)` — geometry optimization
- `MolecularDynamics(atoms, model, ensemble="nvt", temperature=300, timestep=2)` — MD

**Output:** Energy (eV/atom via pymatgen, eV total via ASE), forces (eV/Å), stress (GPa via pymatgen, eV/Å³ via ASE), magnetic moments (μ_B)

**Dependency note:** CHGNet requires pymatgen (significant dependency). The generated script should use the ASE Calculator interface to avoid pulling pymatgen into structure handling.

### 3.3 SevenNet

| Attribute | Value |
|-----------|-------|
| **PyPI package** | `sevenn` |
| **GitHub** | https://github.com/MDIL-SNU/SevenNet |
| **Latest version** | 0.12.0 (Dec 2025) |
| **Python** | >= 3.10 |
| **PyTorch** | >= 2.0.0 |
| **License** | MIT |

**Calculator API:**
```python
from sevenn.calculator import SevenNetCalculator
calc = SevenNetCalculator(model="7net-0", device="cpu")
```

**Key parameters:**
- `model`: str — `"7net-0"`, `"7net-0_11Jul2024"`, `"7net-0_22May2024"`, `"7net-l3i5"`, `"7net-MF-0"`, `"7net-MF-ompa"`, `"7net-Omni"`
- `device`: str — `"cpu"`, `"cuda"`, `"auto"`
- `modal`: str — Multi-fidelity target: `"PBE"`, `"R2SCAN"` (only for MF models)

**Unique feature:** CUDA-accelerated Grimme's D3 dispersion corrections built-in. Multi-fidelity models can target different levels of theory with the same model.

**CLI tools:** `sevenn_inference <checkpoint> <structures>` — batch inference CLI outputting CSV. Also `sevenn_graph_build`, `sevenn_get_model`.

**Output:** Energy (eV total), forces (eV/Å), stress (eV/Å³)

### 3.4 MatterSim

| Attribute | Value |
|-----------|-------|
| **PyPI package** | `mattersim` |
| **GitHub** | https://github.com/microsoft/mattersim |
| **Latest version** | 1.2.1 (Feb 2026) |
| **Python** | >= 3.10 |
| **PyTorch** | required |
| **License** | MIT |

**Calculator API:**
```python
from mattersim.forcefield import MatterSimCalculator
calc = MatterSimCalculator(load_path=None, device="cpu", dtype=torch.float32)
```

**Key parameters:**
- `load_path`: str or None — `None` for default 1M model, `"MatterSim-v1.0.0-5M.pth"` for larger
- `device`: str — `"cpu"`, `"cuda"` (avoid `"mps"` — numerical instability)
- `dtype`: torch.dtype — `torch.float32` or `torch.float64`
- `compute_stress`: bool — whether to compute stress tensors
- `stress_weight`: float — unit conversion factor

**Built-in optimizers:**
- `Relaxer(potential, optimizer="FIRE", filter="EXPCELLFILTER", constrain_symmetry=True)` — geometry opt
- `BatchRelaxer(potential, fmax=0.01, max_natoms_per_batch=512)` — batch optimization

**Output:** Energy (eV total), forces (eV/Å), stress (eV/Å³)

**Model variants:** 1M (default, faster) and 5M (more accurate). Both support 89 elements, 0–5000 K, 0–1000 GPa.

### Cross-Library Comparison

| Feature | MACE | CHGNet | SevenNet | MatterSim |
|---------|------|--------|----------|-----------|
| Calculator import | `mace.calculators.mace_mp` | `chgnet.model.CHGNetCalculator` | `sevenn.calculator.SevenNetCalculator` | `mattersim.forcefield.MatterSimCalculator` |
| Model selection | `model="medium"` | `model_name="0.3.0"` | `model="7net-0"` | `load_path=None` |
| Device kwarg | `device=` | `use_device=` | `device=` | `device=` |
| Precision control | `default_dtype="float64"` | — | — | `dtype=torch.float64` |
| D3 dispersion | `dispersion=True` | optional extra | Built-in CUDA D3 | — |
| Magnetic moments | No | Yes | No | No |
| pymatgen dependency | No | Yes (required) | No | No |
| Model variants | 16+ | 3 | 7+ | 2 |
| Elements | 89 | 89 | 89 | 89 |

---

## 4. Architecture Decisions

### 4.1 Driver Structure (One Driver per MLP, Flat Layout)

Each MLP engine gets its own independent driver directory at the same level as all existing engines:

```
src/qmatsuite/drivers/
├── mace/           # MACE driver
├── chgnet/         # CHGNet driver
├── sevenn/         # SevenNet driver
├── mattersim/      # MatterSim driver
├── xtb/            # (existing)
├── vasp/           # (existing)
├── qe/             # (existing)
└── ...
```

**No shared MLP parent directory.** Each engine is self-contained per INV-4 and INV-5. Shared utilities (if any emerge) can be extracted later into a leaf utility module, but premature abstraction is explicitly avoided.

**Per-engine directory layout** (follows B1 playbook standard):
```
drivers/<engine>/
├── __init__.py           # DriverRegistry.register()
├── driver.py             # EngineDriver (PREFIX + SUPPORTED_GEN_STEPS)
├── handler.py            # Script generation + subprocess execution
├── recipe.py             # Materialization (ISOLATED workdir)
├── inputspec.py          # EngineInputSpec definition
├── writer.py             # Structure JSON writer + script generator
├── parser.py             # results.json parser
├── data/
│   ├── __init__.py
│   ├── <engine>_tags.json      # Parameter metadata
│   └── <engine>_metadata.py    # Cached access layer
├── io/
│   ├── __init__.py
│   └── <engine>_script.py      # Python script template (stdlib only)
└── parsers/
    ├── __init__.py
    ├── output.py               # Digest parser + @register_parser
    └── trajectory.py           # Trajectory parser for relax/MD
```

### 4.2 Execution Model (Script Generation → Subprocess)

All MLP engines follow the **GPAW pattern** (not xTB's direct binary invocation):

1. **Handler generates a Python runner script** (`run_<engine>.py`) that:
   - Imports the MLP calculator from the isolated environment
   - Loads structure from `structure.json`
   - Configures the calculator with user parameters
   - Runs the calculation (SCF / relax / MD)
   - Writes `results.json` (structured output)
   - For relax/MD: writes `trajectory.jsonl` (one JSON object per frame)

2. **Handler invokes via subprocess:**
   ```python
   result = subprocess.run(
       [python_exe, "run_mace.py"],
       cwd=str(working_dir),
       capture_output=True,
       text=True,
       timeout=timeout,
   )
   ```

3. **`python_exe` resolved via engine registry:**
   ```python
   python_exe = resolve_active_python("mace")
   # → ~/.qmatsuite/engines/mace/env/bin/python
   ```

**Why not direct binary invocation (xTB pattern)?**
- MLP libraries have no standalone CLI for general-purpose calculations
- SevenNet has `sevenn_inference` but it's batch-only and doesn't support optimization/MD
- The Python API (ASE Calculator) is the primary interface for all four libraries
- Script generation gives full control over calculation workflow (optimizer choice, MD ensemble, trajectory output format)

**Generated script template** (example for MACE SCF):
```python
import json
import numpy as np
from pathlib import Path
from ase.io import read

# Load structure
with open("structure.json") as f:
    struct_data = json.load(f)
from ase import Atoms
atoms = Atoms(
    symbols=struct_data["species"],
    positions=struct_data["cart_coords"],
    cell=struct_data.get("cell"),
    pbc=struct_data.get("pbc", [True, True, True]),
)

# Configure calculator
from mace.calculators import mace_mp
calc = mace_mp(model="medium", device="cpu", default_dtype="float64")
atoms.calc = calc

# Run calculation
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
stress = atoms.get_stress(voigt=False)

# Write results
results = {
    "total_energy_eV": float(energy),
    "forces_eV_per_ang": forces.tolist(),
    "stress_eV_per_ang3": stress.tolist(),
    "n_atoms": len(atoms),
    "species": list(atoms.get_chemical_symbols()),
    "success": True,
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
```

### 4.3 Output Parsing Strategy (No ASE Data Structures)

**Principle**: QMatSuite's parser layer extracts raw numbers from `results.json` and `trajectory.jsonl` and constructs QMatSuite-native objects. No ASE `Atoms` or `Trajectory` objects cross the subprocess boundary.

**Output files produced by generated scripts:**

| File | Calc Type | Format | Contents |
|------|-----------|--------|----------|
| `results.json` | All | JSON | `{total_energy_eV, forces_eV_per_ang, stress_eV_per_ang3, n_atoms, species, success, ...}` |
| `trajectory.jsonl` | relax, md | JSON Lines | Per-frame: `{step, energy_eV, forces, positions, species, cell, temperature_K, ...}` |
| `final_structure.json` | relax | JSON | `{species, cart_coords, cell, pbc}` — optimized geometry |
| `<engine>.out` | All | Text | Combined stdout+stderr for debugging |

**Parser chain:**
1. `parser.py`: Reads `results.json` → dict with energy/forces/stress
2. `parsers/output.py`: `<Engine>Digest` dataclass + `@register_parser("<engine>", "scf_digest")`
3. `parsers/trajectory.py`: Reads `trajectory.jsonl` → `Trajectory` with `Frame` list

**Digest dataclass** (common across all MLP engines, ~15 fields):
```python
@dataclass
class MACEDigest:
    success: bool
    calc_type: str                          # "scf", "relax", "md"
    model_name: str                         # e.g., "medium"
    final_energy_eV: float | None
    forces_eV_per_ang: list[list[float]] | None
    stress_eV_per_ang3: list[list[float]] | None
    n_atoms: int
    final_species: list[str] | None
    final_cart_coords: list[list[float]] | None
    converged_geometry: bool | None         # relax only
    n_opt_steps: int | None                 # relax only
    n_md_steps: int | None                  # md only
    wall_time_s: float | None
    error_message: str | None
```

### 4.4 Tags JSON Generation Plan

**Approach**: Semi-automated extraction from Python source + documentation.

For each MLP engine:
1. Inspect `Calculator.__init__` signature and docstring
2. Scrape readthedocs / GitHub README for parameter descriptions
3. Include ASE optimizer kwargs (fmax, steps, optimizer type) for relax
4. Include ASE MD kwargs (timestep, temperature, friction, ensemble, steps) for MD
5. Output `<engine>_tags.json` with standard schema

**Tag categories** (common across all MLPs):
- `model`: Model variant selection
- `device`: Hardware targeting (cpu/cuda/mps)
- `precision`: Numerical precision control
- `dispersion`: Dispersion correction settings
- `optimizer`: Geometry optimization parameters (relax only)
- `md`: Molecular dynamics parameters (MD only)
- `output`: Output control flags
- `environment`: Environment variables (OMP, CUDA)

**Minimum viable tag count justification**: The B1 playbook specifies 50+ for "specialized" engines. MLPs are ultra-specialized (no basis sets, no SCF convergence, no k-point meshes, no pseudopotentials). A 30–40 tag catalog with 100% coverage of the actual parameter space is more rigorous than a padded 50-tag catalog. The playbook minimum should be interpreted relative to the engine's actual complexity.

### 4.5 Engine Installation / Discovery

**Installation flow** (per engine):
```
qmatsuite engine install mace
  → micromamba create -p ~/.qmatsuite/engines/mace/env python=3.11 pytorch
  → ~/.qmatsuite/engines/mace/env/bin/pip install mace-torch
  → Register in engines.json: {source: "micromamba", python_executable: "~/.qmatsuite/engines/mace/env/bin/python"}
```

**Engine metadata entries** (new entries in `engine_meta.py`):
```python
"mace": {
    "engine_type": "python",
    "python_import": "mace",
    "display_name": "MACE",
    "pip_package": "mace-torch",
    "conda_package": None,  # pip-only
    "conda_channel": None,
},
"chgnet": {
    "engine_type": "python",
    "python_import": "chgnet",
    "display_name": "CHGNet",
    "pip_package": "chgnet",
},
"sevenn": {
    "engine_type": "python",
    "python_import": "sevenn",
    "display_name": "SevenNet",
    "pip_package": "sevenn",
},
"mattersim": {
    "engine_type": "python",
    "python_import": "mattersim",
    "display_name": "MatterSim",
    "pip_package": "mattersim",
    "conda_channel": "conda-forge",
},
```

**Discovery**: Tier 3 (Python Import) is the primary discovery mechanism:
```python
subprocess.run([python_exe, "-c", "import mace; print(mace.__version__)"])
```

---

## 5. Plan Proposal: MACE (First Engine)

### 5.1 B1 Playbook Phase Mapping

| Phase | B1 Playbook Phase | MACE Adaptation | Notes |
|-------|-------------------|-----------------|-------|
| 0 | Corpus Collection | Web scrape mace-docs.readthedocs.io + GitHub source | Store in `.tmp/engine_research/mace/` |
| 1 | Parameter Metadata Catalog | Generate `mace_tags.json` (~35 tags) | From Calculator kwargs + ASE optimizer/MD kwargs |
| 2 | Metadata Access Layer | `mace_metadata.py` | Standard pattern, copy from xTB |
| 3 | Curated Case Library | 3–5 cases in `tests/inputformat/samples/mace/` | si_scf, si_relax, water_md, li_metal_scf, perovskite_relax |
| 4 | Parser/Writer Robustness | `io/mace_script.py` — script generator | Stdlib-only Python script template |
| 5 | Resource Staging | **Skip** — models auto-downloaded | No pseudopotentials or external files |
| 6 | Output Digest Parser | `parsers/output.py` — MACEDigest + MACEOutputParser | Parse results.json |
| 6b | Trajectory Parser | `parsers/trajectory.py` — MACETrajectoryParser | Parse trajectory.jsonl |
| 7 | Execution Framework | `engine/mace_runner.py` (dev-only) | Real-run validation |
| 8 | Final Integration | Full pytest, registration, docs | B1 acceptance criteria |

### 5.2 File Inventory (Expected Files and Purposes)

```
# Driver (committed)
src/qmatsuite/drivers/mace/
├── __init__.py                    # DriverRegistry.register(MACEDriver())
├── driver.py                      # PREFIX="mace", SUPPORTED_GEN_STEPS={"scf","relax","md"}
├── handler.py                     # Script generation + subprocess.run([python, run_mace.py])
├── recipe.py                      # MACERecipe(BaseRecipe): ISOLATED workdir
├── inputspec.py                   # EngineInputSpec: structure.json + run_mace.py
├── writer.py                      # Structure JSON writer + MACE script generator
├── parser.py                      # results.json + trajectory.jsonl parser
├── data/
│   ├── __init__.py
│   ├── mace_tags.json             # ~35 tags (model, device, precision, dispersion, opt, md)
│   └── mace_metadata.py           # Cached access layer
├── io/
│   ├── __init__.py
│   └── mace_script.py             # Python script template generation (stdlib only)
└── parsers/
    ├── __init__.py
    ├── output.py                  # MACEDigest + @register_parser("mace", "scf_digest")
    └── trajectory.py              # MACETrajectoryParser + @register_parser("mace", "trajectory")

# Tests (committed)
tests/drivers/mace/
├── conftest.py                    # mace_available fixture (check import in isolated env)
├── test_mace_driver.py            # 7+ tests: driver properties, registration, isolation
├── test_mace_metadata.py          # 10+ tests: catalog, lookup, validation
├── test_mace_execution.py         # 2+ tests: real subprocess (skip if not installed)
└── test_mace_trajectory_parser.py # Trajectory parsing tests

tests/inputformat/samples/mace/
├── si_scf/
│   ├── structure.json             # Silicon diamond (2 atoms)
│   └── case.yaml
├── si_relax/
│   ├── structure.json             # Slightly distorted Si
│   └── case.yaml
├── water_md/
│   ├── structure.json             # Water molecule in box
│   └── case.yaml
├── li_metal_scf/
│   ├── structure.json             # Li BCC (metallic system)
│   └── case.yaml
└── perovskite_relax/
    ├── structure.json             # CaTiO3 perovskite
    └── case.yaml

# Docs (committed)
docs/engines/mace/
├── PHASE_B1_PLAN.md
├── PHASE_B1_WORKLOG.md
├── SOURCES.md
└── CURATED_INDEX.md

# Research (NOT committed, .gitignored)
.tmp/engine_research/mace/
├── raw_web/                       # Scraped docs
├── metadata/                      # Extracted parameter info
├── normalized/                    # Normalized cases
├── runs/                          # Real validation runs
├── SOURCES.md
└── WORKLOG.md
```

### 5.3 Step Types and GEN→SPEC Mapping

**PREFIX**: `"mace"` (no underscores, lowercase alphanumeric ✓)

**SUPPORTED_GEN_STEPS**: `frozenset({"scf", "relax", "md"})`

**Materialization map** (auto-derived):
| GEN | SPEC |
|-----|------|
| `scf` | `mace_scf` |
| `relax` | `mace_relax` |
| `md` | `mace_md` |

**StepTypeSpec declarations:**
```python
StepTypeSpec(step_type_spec="mace_scf", engine="mace", executable="python",
             description="MACE single-point energy/forces/stress", mpi_aware=False)
StepTypeSpec(step_type_spec="mace_relax", engine="mace", executable="python",
             description="MACE geometry optimization", mpi_aware=False)
StepTypeSpec(step_type_spec="mace_md", engine="mace", executable="python",
             description="MACE molecular dynamics", mpi_aware=False)
```

**Analysis capabilities:**
```python
ANALYSIS_CAPABILITIES = [
    AnalysisCapability(object_type="trajectory", gen_step_sequence=["relax"],
                      evidence_files=["trajectory.jsonl"]),
    AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"],
                      evidence_files=["trajectory.jsonl"]),
]
```

### 5.4 Demo Corpus Plan (3–5 Cases, Layer 1→2→3)

| Case | System | Calc Type | Atoms | Purpose |
|------|--------|-----------|-------|---------|
| `si_scf` | Si diamond | SCF | 2 | Baseline single-point |
| `si_relax` | Si (distorted) | Relax | 2 | Geometry optimization convergence |
| `water_md` | H₂O in box | MD (NVT, 300K, 100 steps) | 3 | MD trajectory output |
| `li_metal_scf` | Li BCC | SCF | 1 | Metallic system |
| `perovskite_relax` | CaTiO₃ | Relax | 5 | Multi-element oxide |

**Layer 1 (Corpus)**: `structure.json` + `case.yaml` per case
**Layer 2 (Runtime)**: Generated by demo compiler from Layer 1
**Layer 3 (Ref packs)**: Generated by real MACE runs (requires mace-torch installed)

### 5.5 Tags JSON Extraction Approach

1. **Phase 0**: Scrape `mace-docs.readthedocs.io` and `mace/calculators/foundations_models.py` source
2. **Extract calculator kwargs**: `model`, `device`, `default_dtype`, `dispersion`, `damping`, `dispersion_xc`, `dispersion_cutoff`, `return_raw_model`
3. **Extract ASE optimizer kwargs**: `optimizer` (BFGS/LBFGS/FIRE), `fmax`, `steps`, `filter` (FrechetCellFilter/ExpCellFilter)
4. **Extract ASE MD kwargs**: `ensemble` (NVE/NVT/NPT), `timestep`, `temperature_K`, `friction`, `steps`, `taut`, `taup`, `pressure`
5. **Add output control**: `write_trajectory` (bool), `trajectory_interval` (int)
6. **Add environment**: `MACE_DEVICE`, `OMP_NUM_THREADS`, `CUDA_VISIBLE_DEVICES`
7. **Review + iterate**: Verify against MACE changelog for completeness

### 5.6 Output Parser Design

**MACEDigest** (dataclass, ~15 fields):
- `success`: bool
- `calc_type`: str (`"scf"`, `"relax"`, `"md"`)
- `model_name`: str
- `final_energy_eV`: float | None
- `forces_eV_per_ang`: list[list[float]] | None
- `max_force_eV_per_ang`: float | None
- `stress_eV_per_ang3`: list[list[float]] | None
- `n_atoms`: int
- `final_species`: list[str] | None
- `final_cart_coords`: list[list[float]] | None
- `converged_geometry`: bool | None (relax)
- `n_opt_steps`: int | None (relax)
- `n_md_steps`: int | None (md)
- `wall_time_s`: float | None
- `error_message`: str | None

**MACEOutputParser** (`@register_parser("mace", "scf_digest")`):
- `can_parse(raw_dir)`: Check for `results.json`
- `parse(raw_dir)`: Read JSON → MACEDigest

**MACETrajectoryParser** (`@register_parser("mace", "trajectory")`):
- `can_parse(raw_dir)`: Check for `trajectory.jsonl`
- `parse(raw_dir)`: Read JSONL → Frame list → Trajectory

### 5.7 Estimated Effort

| Phase | Work Items | Relative Size |
|-------|-----------|---------------|
| Phase 0 (Corpus) | Scrape docs, extract parameters | Small |
| Phase 1 (Tags JSON) | Generate mace_tags.json (~35 tags) | Small |
| Phase 2 (Metadata) | Copy xTB pattern, adapt | Small |
| Phase 3 (Curated cases) | 5 structure.json + case.yaml files | Small |
| Phase 4 (IO module) | mace_script.py — script template generator | Medium |
| Phase 5 (Resources) | Skip | — |
| Phase 6 (Digest) | output.py + trajectory.py | Medium |
| Phase 7 (Execution) | mace_runner.py (dev validation) | Small |
| Phase 8 (Integration) | driver.py, handler.py, recipe.py, inputspec.py, registration, tests | Large |

**Total**: MACE is the most work because it establishes the full MLP driver template (script generation pattern, results.json schema, trajectory.jsonl format, structure.json format). Once MACE is done, the template is proven and subsequent engines are significantly faster.

---

## 6. Plan Proposal: Subsequent Engines (CHGNet, SevenNet, MatterSim)

### 6.1 What Can Be Templated from MACE

| Component | Reusability | Engine-Specific Delta |
|-----------|------------|----------------------|
| Directory structure | 100% identical | — |
| `driver.py` | ~90% — change PREFIX, display_name | PREFIX string |
| `handler.py` | ~95% — same subprocess pattern | Script filename |
| `recipe.py` | ~95% — same ISOLATED workdir | — |
| `inputspec.py` | ~90% — same structure.json + script | Script filename |
| `parser.py` | ~95% — same results.json schema | — |
| `parsers/output.py` | ~80% — same digest structure | Digest class name, extra fields |
| `parsers/trajectory.py` | ~95% — same trajectory.jsonl | — |
| `data/<engine>_metadata.py` | ~95% — same access layer | Engine name, env var name |
| Tests | ~85% — same patterns | Fixture names, tag counts |

**Key: the `io/<engine>_script.py` (script template) is the main engine-specific file.** Each MLP has different:
- Import path for the calculator
- Constructor kwargs and their names
- Model selection mechanism
- Optional features (dispersion, magnetic moments)

### 6.2 Engine-Specific Differences

**CHGNet:**
- PREFIX: `"chgnet"`
- Extra digest field: `magnetic_moments` (unique to CHGNet)
- Model loading: `CHGNet.load(model_name="0.3.0")` → `CHGNetCalculator(model=model)`
- Device kwarg: `use_device=` (not `device=`)
- Note: pymatgen is a dependency of the library but we don't use it in our parser

**SevenNet:**
- PREFIX: `"sevenn"` (matches PyPI package name `sevenn`)
- Multi-fidelity: extra `modal` parameter for MF models
- Built-in D3 dispersion (CUDA-accelerated)
- Has CLI (`sevenn_inference`) but we use Python API for consistency

**MatterSim:**
- PREFIX: `"mattersim"`
- Model loading: `MatterSimCalculator(load_path=None)` for 1M, `load_path="MatterSim-v1.0.0-5M.pth"` for 5M
- Precision: `dtype=torch.float32` (torch dtype, not string)
- Device: `"mps"` explicitly discouraged (numerical instability)
- Has built-in `Relaxer` with `constrain_symmetry` option (unique feature)

### 6.3 Incremental Effort Estimates

| Engine | Effort vs MACE | Rationale |
|--------|---------------|-----------|
| CHGNet | ~40% | Template from MACE + magnetic moments handling |
| SevenNet | ~35% | Template from MACE + multi-fidelity modal param |
| MatterSim | ~35% | Template from MACE + torch.dtype handling |

**Recommended implementation order**: MACE → CHGNet → SevenNet → MatterSim

**Rationale**:
1. **MACE first**: Most popular, best documented, most model variants, establishes template
2. **CHGNet second**: Second most popular, unique magnetic moment feature tests the template's extensibility
3. **SevenNet third**: Multi-fidelity feature is architecturally interesting
4. **MatterSim fourth**: Simplest parameter space, benefits from all prior learnings

---

## 7. Risks & Open Questions

### R1: `ENGINE_PREFIXES` Frozen Set Update

**Risk**: `ENGINE_PREFIXES` in `core/step_type_convert.py` is a frozen set that lists all known engine prefixes. Adding new engines may require updating this set, which is a kernel file.

**Mitigation**: Check whether `is_spec()` / `is_gen()` rely on this set at runtime for new engines. If DriverRegistry's `_step_to_engine` dict handles dispatch independently, the frozen set may only be used for validation and could be made dynamic (populated from registry).

**Status**: Needs investigation. If the set must be updated, this is a minimal, data-only change that doesn't violate INV-4's spirit (no logic changes to kernel).

### R2: Psi4 (Not `psi4`) PREFIX Precedent

**Risk**: The existing Psi4 driver uses PREFIX `"psi4"` which contains a digit. Verify that digit-containing PREFIXes are allowed by the constitution.

**Status**: Constitution says "lowercase alphanumeric" — digits are alphanumeric. `"sevenn"` and `"mattersim"` are valid.

### R3: Model Auto-Download in Isolated Environment

**Risk**: MLP models are typically downloaded on first use (from GitHub releases or Hugging Face). In a CI/CD environment or air-gapped system, this may fail.

**Mitigation**:
- Document the first-run model download requirement
- Support pre-downloading models: `qmatsuite engine setup mace` could trigger a model download
- For CI: cache models in `~/.cache/mace/` (MACE's default cache location)

### R4: PyTorch Version Conflicts Between MLP Engines

**Risk**: Different MLP libraries may require different PyTorch versions. MACE specifically notes PyTorch 2.4.1 is not supported.

**Mitigation**: Each engine has its own isolated micromamba environment. No cross-engine dependency conflicts possible. The trade-off is disk space (~2-5 GB per environment with PyTorch).

### R5: GPU Memory Management

**Risk**: Multiple MLP calculations on GPU could exhaust VRAM, especially with large models (MACE large, MatterSim 5M).

**Mitigation**:
- Default to `device="cpu"` in tags JSON defaults
- Add `CUDA_VISIBLE_DEVICES` as an environment tag
- The generated script can include `torch.cuda.empty_cache()` cleanup

### R6: ASE Version Compatibility

**Risk**: Different MLP libraries may pin different ASE versions in their requirements. The isolated environment handles this, but the structure.json format must be stable across ASE versions.

**Mitigation**: We don't depend on ASE's data structures. `structure.json` is our own format (`{species, cart_coords, cell, pbc}`). ASE is only used inside the generated script as a calculation driver.

### R7: Trajectory Output Size

**Risk**: Long MD trajectories with forces can produce large `trajectory.jsonl` files (forces are N×3 per frame).

**Mitigation**:
- `trajectory_interval` parameter controls write frequency
- `write_forces` parameter to optionally skip forces in trajectory
- Binary format (e.g., `.npz`) could be a future optimization but JSON is sufficient for initial implementation

### R8: Tag Count Below B1 Minimum

**Risk**: The B1 playbook specifies 50+ tags for specialized engines. MLPs may have only 30-40 genuine parameters.

**Mitigation**: Document the justification in the B1 plan. Include ASE optimizer and MD parameters as engine-level tags (they are valid configuration parameters for the engine's execution). This should bring counts to 40-50 range. If still short, environment variables and output control flags provide legitimate additional tags.

---

## 8. References (Spec Documents Consulted)

### Architecture & Constitution
- `docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md` — INV-1 through INV-6
- `docs/laws/L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` — EngineDriver protocol, recipe archetypes, hard bans
- `docs/laws/L1/STEP_TYPE_GEN_SPEC_CONSTITUTION.md` — GEN/SPEC rules, PREFIX constraints

### Playbook & Specs
- `docs/laws/L2/B1_ENGINE_PLAYBOOK.md` — 8-phase SOP
- `docs/specs/DEMO_STORE_SPEC.md` — Three-layer demo architecture
- `docs/specs/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` — Analysis object system

### Existing Driver Code (Read)
- `src/qmatsuite/drivers/xtb/` — All 15 files (primary template)
- `src/qmatsuite/drivers/lammps/parsers/trajectory.py` — Trajectory handling
- `src/qmatsuite/drivers/gpaw/handler.py` + `writer.py` — Python script generation pattern
- `src/qmatsuite/drivers/pyscf/handler.py` — Chain handler pattern (negative example)

### Registry & Conversion
- `src/qmatsuite/core/driver_registry.py` — DriverRegistry implementation
- `src/qmatsuite/core/step_type_convert.py` — ENGINE_PREFIXES, spec_from/gen_from
- `src/qmatsuite/workflow/gen_steps.py` — GenStepRegistry.GEN_STEPS
- `src/qmatsuite/core/engines/discovery.py` — Engine discovery (7-tier)
- `src/qmatsuite/core/engines/engine_meta.py` — Engine metadata
- `src/qmatsuite/core/engines/micromamba.py` — Isolated environment management

### Parameter Extraction
- `tools/extract_qe_parameters_v3.py` — Production extractor pattern
- `src/qmatsuite/drivers/xtb/data/xtb_tags.json` — xTB tags reference (88 tags)
- `src/qmatsuite/drivers/vasp/data/vasp_incar_tags.json` — VASP tags reference (232 tags)

### External Documentation
- MACE: https://mace-docs.readthedocs.io/en/latest/
- CHGNet: https://chgnet.lbl.gov/ + https://github.com/CederGroupHub/chgnet
- SevenNet: https://sevennet.readthedocs.io/en/latest/ + https://github.com/MDIL-SNU/SevenNet
- MatterSim: https://microsoft.github.io/mattersim/ + https://github.com/microsoft/mattersim
