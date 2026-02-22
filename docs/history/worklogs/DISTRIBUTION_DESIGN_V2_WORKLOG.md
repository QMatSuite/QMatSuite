# Distribution Design v2 — Deep Investigation & Update Worklog

**Date**: 2026-02-21
**Scope**: Dependency audit, PyInstaller feasibility, engine binary verification, design doc corrections

---

## Phase 1: Dependency Graph Investigation

### 1.1 Daemon Import Trace

Traced the full import chain from `python -m qmatsuite.daemon.server`:

**Heavy dependencies loaded at daemon startup:**
- **pymatgen** (~29 modules) — via module-level imports in:
  - `core/structure_fingerprint.py:23-24` (`from pymatgen.core import Structure, Molecule`)
  - `core/structure_canonicalize.py:11-12` (same)
  - `io/structure_io.py:16-18` (`from pymatgen.core import Element, Lattice, Structure, Molecule`)
  - `api/utils.py:558` (`from qmatsuite.analysis.structure_viz import DisplayModeParams`)
- **matplotlib** (~94 modules) — via `analysis/structure_viz.py:47-48,59-60` (module-level `matplotlib.use("Agg")` and `import matplotlib.pyplot`)
  - Triggered indirectly by `api/utils.py:558` and `core/structure_fingerprint.py:27`
- **scipy** (~178 modules) — transitive via pymatgen
- **numpy** — unavoidable, used directly and transitively

**NOT loaded at startup:**
- `ase` — NOT IMPORTED ANYWHERE in `src/qmatsuite/`. Dead dependency.
- `beautifulsoup4` — NOT IMPORTED ANYWHERE. Dead dependency.
- `plotext` — only in `mcp/renderers/plotext_renderer.py:15` (lazy, MCP analysis only)
- `jinja2` — only in `engine/lammps_writer.py:9` (lazy, LAMMPS only)
- `scipy` (direct usage) — only in `drivers/abinit/parsers/trajectory.py:36` (lazy import inside function)

### 1.2 Pymatgen Submodules Used

- `pymatgen.core` (Structure, Lattice, Element, Molecule, periodic_table, composition, sites, units)
- `pymatgen.io` (cif, vasp, xyz, qe — structure I/O)
- `pymatgen.symmetry` (analyzer, bandstructure, kpath — space group + k-path generation)
- `pymatgen.electronic_structure` (bandstructure — band structure objects)

Cannot replace pymatgen with lighter alternatives — it's deeply integrated for structure representation, space group analysis, and band structure k-paths.

**Can be made lazy**: YES. The module-level imports in `structure_fingerprint.py`, `structure_canonicalize.py`, `api/utils.py:558` can be moved inside functions. This would defer pymatgen+matplotlib+scipy loading to first structure operation.

### 1.3 Minimal Daemon Dependencies (if heavy deps made lazy)

Only these packages would load at startup:
- numpy (~20MB) — unavoidable, used directly in many places
- PyYAML (~0.8MB)
- typer (~0.4MB)
- ulid-py (~0.2MB)
- msgpack (~0.3MB)
- requests + certifi (~0.7MB)
- portalocker (~0.1MB)
- fastmcp (~3.2MB) — for MCP server
- qmatsuite (~17.5MB source)

Total minimal startup: ~43MB loaded, vs current ~350MB.

---

## Phase 2: Python Engine Isolation Verification

### Finding: All three Python engines are ALREADY subprocess-isolated

- **Psi4**: `engine/psi4_engine.py:564` — `subprocess.run(cmd, ...)` where cmd = `[psi4_python, "-m", "qmatsuite.engines.psi4", job_chain.json]`
- **PySCF**: `engine/pyscf_engine.py:390` — `subprocess.run(cmd, ...)` where cmd = `[sys.executable, "-m", "qmatsuite.engines.pyscf", job_chain.json]`
- **GPAW**: `drivers/gpaw/handler.py:126` — `subprocess.run([sys.executable, script_name], ...)`

Neither pyscf nor psi4 is ever imported into the main daemon process. The `engines/pyscf/chain_execution.py` (which does `import pyscf`) is only loaded in the runner subprocess.

**However**: PySCF is still listed as optional pip dependency in `pyproject.toml` (line 38-40). Per design direction, this should be removed — PySCF, Psi4, GPAW should be micromamba-managed engines, each in their own conda env.

---

## Phase 3: Dependency Audit

### 3.1 Full Transitive Closure

74 packages, 348.4 MB total installed size.

| Package | Installed Size | Required? | Can Be Lazy? |
|---------|---------------|-----------|-------------|
| scipy | 78.5 MB | Transitive (pymatgen) | Already lazy (direct use in 1 place) |
| pandas | 45.6 MB | Transitive (pymatgen) | N/A — pymatgen dep |
| plotly | 41.2 MB | Transitive (pymatgen) | N/A — pymatgen dep |
| sympy | 38.2 MB | Transitive (scipy) | N/A — scipy dep |
| matplotlib | 25.0 MB | Yes (plotting) | YES — make lazy |
| numpy | 19.9 MB | Yes (core arrays) | No — ubiquitous |
| pymatgen | 19.2 MB | Yes (structures) | YES — make lazy |
| fonttools | 14.7 MB | Transitive (matplotlib) | N/A |
| pillow | 13.1 MB | Transitive (matplotlib) | N/A |
| ase | 11.3 MB | **DEAD — not imported** | Remove from deps |
| networkx | 10.9 MB | Transitive (pymatgen) | N/A |
| spglib | 5.9 MB | Yes (symmetry, via pymatgen) | YES — via pymatgen lazy |
| fastmcp | 3.2 MB | Yes (MCP server) | No — core |
| rich | 2.1 MB | Transitive (typer) | N/A |
| narwhals | 1.8 MB | Transitive | N/A |
| palettable | 1.5 MB | Transitive (pymatgen) | N/A |
| jinja2 | 1.2 MB | Yes (LAMMPS writer) | Already lazy |
| beautifulsoup4 | 0.8 MB | **DEAD — not imported** | Remove from deps |
| plotext | 0.7 MB | Yes (MCP ASCII plots) | Already lazy |
| PyYAML | 0.8 MB | Yes (SSOT) | No — core |
| qmatsuite | 17.5 MB | Yes | N/A |

### 3.2 Dead Dependencies to Remove

- `ase` (11.3 MB) — zero imports in src/qmatsuite/
- `beautifulsoup4` (0.8 MB) — zero imports in src/qmatsuite/

### 3.3 PySCF Optional Extra to Remove from pyproject.toml

`pyscf` extra (line 38-40) should be removed. PySCF is a micromamba-managed engine, not a pip dependency.

---

## Phase 4: Engine Binary Verification

Verified exact binary names from handler/recipe source code:

| Engine | Primary Exe | Source File | Version Check |
|--------|-----------|------------|---------------|
| QE | pw.x | drivers/qe/engine/qe_engine.py:30 | `pw.x --version` |
| VASP | vasp_std | drivers/vasp/recipe.py:73 | N/A |
| xTB | xtb | drivers/xtb/handler.py:109 | `xtb --version` |
| LAMMPS | lmp | drivers/lammps/recipe.py:74 | `lmp -h` |
| ORCA | orca | drivers/orca/recipe.py:121 | N/A |
| Gaussian | g09/g16 | drivers/gaussian/handler.py:37-68 | N/A |
| ABINIT | abinit | drivers/abinit/handler.py:38 | `abinit --version` |
| CP2K | cp2k.ssmp | drivers/cp2k/recipe.py:90 | `cp2k.ssmp --version` |
| Siesta | siesta | drivers/siesta/handler.py:39 | `siesta --version` |
| Wannier90 | wannier90.x | drivers/w90/recipe.py:51 | N/A |
| Yambo | yambo, p2y | drivers/yambo/handler.py:38-50 | `yambo -h` |
| QMCPACK | qmcpack | drivers/qmcpack/recipe.py:70 | N/A |
| GPAW | python (sys.executable) | drivers/gpaw/handler.py:126 | `python -c "import gpaw; print(gpaw.__version__)"` |
| Psi4 | python (discover_engine) | engine/psi4_engine.py:83 | `python -c "import psi4; print(psi4.__version__)"` |
| PySCF | python (sys.executable) | engine/pyscf_engine.py:100 | `python -c "import pyscf; print(pyscf.__version__)"` |

---

## Phase 5: PyInstaller Feasibility Reassessment

### Key findings:
1. All heavy deps (numpy, scipy, pymatgen, matplotlib) have well-maintained PyInstaller hooks
2. pymatgen needs `--collect-data pymatgen` for data files (periodic table, etc.)
3. spglib C extension is detected by PyInstaller automatically
4. No dynamic imports that would break PyInstaller

### Bundle size estimate:
- PyInstaller typically achieves 60-70% of installed package size (strips docs, tests, unused code)
- 348 MB installed → ~210-250 MB PyInstaller bundle
- Add Python interpreter: ~20 MB
- **Total PyInstaller bundle: ~230-270 MB**

### Comparison with micromamba approach:
- **PyInstaller**: ~250 MB (Python + all deps + qmatsuite)
- **Micromamba env**: ~500 MB (full Python environment)
- **Saving**: ~250 MB

### Full release total (with QE + SSSP):
- PyInstaller: 250 + 150 (QE OpenMP) + 80 (SSSP eff) = **~480 MB**
- Micromamba: 500 + 150 + 80 = **~730 MB**

### Revised feasibility: **Medium** (up from "Medium-Low")

The dependency tree is standard scientific Python — well-tested with PyInstaller. Main challenges:
1. pymatgen data files require `--collect-data`
2. matplotlib backends need selective exclusion
3. Testing needed for all platforms

**Recommendation**: Keep micromamba as Plan A (simpler, more extensible). PyInstaller as Plan B if bundle size is critical. Could use a hybrid: PyInstaller for core, micromamba for optional extensions (PySCF, etc.).

---

## Phase 6: Code Signing Research

### Micromamba binary: NOT code-signed
- Only SHA256 checksums provided alongside releases
- No macOS notarization, no Windows Authenticode
- Known issue: macOS code signature enforcement breaks unsigned micromamba (Spyder issue #18661)
- **Implication**: QMatSuite must ad-hoc sign (macOS) or embed in signed app bundle

### conda-forge packages: NOT signed
- TUF framework (`conda-content-trust`) exists in conda 4.10.1+
- But conda-forge does NOT currently generate signatures
- Integrity relies on HTTPS transport security only
- **Implication**: Package integrity verification = checksums only

---

## Phase 7: Design Document Updates

Applied all corrections to `CROSS_PLATFORM_DISTRIBUTION_DESIGN.md`:
1. Lite channel framing corrected (not "manage own engines" — selective install via package manager)
2. QE binary dual variant (OpenMP-only + MPI-enabled) with GitHub Release download mechanism
3. Python engines (PySCF, Psi4, GPAW) → micromamba-managed with `user_venv` alternative
4. Designed Python engine subprocess isolation for distribution (§3.8):
   - Engine adapter uses registered Python executable (not `sys.executable`)
   - PYTHONPATH injection so engine's Python can import qmatsuite
   - Dev mode compatibility: falls back to `sys.executable` (developer's venv)
   - `user_venv` source type: user can point to existing venv with engine installed
5. Code signing strategy section added (§7)
6. Engine detection table with verified binary names from source code
7. Dependency audit appendix with actual measured sizes
8. PyInstaller feasibility revised to Medium (from Medium-Low)
9. Added Option D (hybrid PyInstaller + micromamba) as Plan B
10. Added Phase 0 to roadmap: dead dep cleanup, lazy imports, QE OpenMP CI
11. Updated source types: added `github_release` and `user_venv`
12. Removed dead deps (ase, beautifulsoup4) from all tables and commands
