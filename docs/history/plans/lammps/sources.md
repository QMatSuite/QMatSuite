# LAMMPS Integration Web Sources

**Version**: 1.0.0  
**Date**: 2026-01-20  
**Purpose**: Document all web research sources for LAMMPS integration

---

## 1. Official LAMMPS Documentation

### 1.1 Input Script Structure

**URL**: https://docs.lammps.org/Commands_structure.html

**Key Information**:
- Four-part structure: Initialization, System Definition, Simulation Settings, Run
- Command ordering requirements
- Variable and loop constructs

**Used For**: Template structure, command ordering validation

### 1.2 Commands Reference

**URLs**:
- `units`: https://docs.lammps.org/units.html
- `atom_style`: https://docs.lammps.org/atom_style.html
- `pair_style`: https://docs.lammps.org/pair_style.html
- `pair_coeff`: https://docs.lammps.org/pair_coeff.html
- `fix nve/nvt/npt`: https://docs.lammps.org/fix_nh.html
- `minimize`: https://docs.lammps.org/minimize.html
- `run`: https://docs.lammps.org/run.html
- `dump`: https://docs.lammps.org/dump.html
- `thermo`: https://docs.lammps.org/thermo.html
- `thermo_style`: https://docs.lammps.org/thermo_style.html
- `read_data`: https://docs.lammps.org/read_data.html
- `read_restart`: https://docs.lammps.org/read_restart.html
- `write_data`: https://docs.lammps.org/write_data.html
- `write_restart`: https://docs.lammps.org/write_restart.html

**Used For**: Template generation, parameter mapping

### 1.3 Output Documentation

**URL**: https://docs.lammps.org/Howto_output.html

**Key Information**:
- Thermo output format and customization
- Dump file types and formats
- Restart file behavior
- Fix and compute output

**Used For**: Parser implementation

### 1.4 Structured Data Output

**URL**: https://docs.lammps.org/Howto_structured_data.html

**Key Information**:
- YAML format for thermo output
- JSON format for computes
- Python integration formats

**Used For**: Parser format understanding

### 1.5 Data File Format

**URL**: https://docs.lammps.org/read_data.html

**Key Information**:
- Header format (atoms, atom types, box bounds)
- Atoms section format for each atom_style
- Masses section
- Velocities section (optional)
- Triclinic box specification (xy, xz, yz)

**Used For**: LAMMPS data file writer

---

## 2. Pair Style Documentation

### 2.1 LJ/Cut

**URL**: https://docs.lammps.org/pair_lj.html

**Key Information**:
- Built-in, no external file needed
- `pair_style lj/cut cutoff`
- `pair_coeff I J epsilon sigma cutoff`

**Used For**: LJ smoke test, inline potential handling

### 2.2 EAM

**URL**: https://docs.lammps.org/pair_eam.html

**Key Information**:
- File formats: funcfl, setfl, fs
- Single-element: `pair_style eam` + `pair_coeff * * file.eam`
- Alloy: `pair_style eam/alloy` + `pair_coeff * * file.eam.alloy elem1 elem2 ...`
- Element order in pair_coeff must match atom type order

**Used For**: EAM potential handling, pair_style block generation

### 2.3 Tersoff

**URL**: https://docs.lammps.org/pair_tersoff.html

**Key Information**:
- File format with element triplet parameters
- `pair_style tersoff`
- `pair_coeff * * file.tersoff elem1 elem2 ...`

**Used For**: Tersoff potential handling

### 2.4 ReaxFF

**URL**: https://docs.lammps.org/pair_reaxff.html

**Key Information**:
- Requires `ffield.reax.*` parameter file
- Requires charge equilibration fix: `fix qeq all qeq/reaxff ...`
- Complex setup, marked as P3 priority

**Used For**: Future ReaxFF support planning

---

## 3. Installation Documentation

### 3.1 Homebrew (macOS)

**Source**: `brew info lammps` (run locally)

**Key Information**:
- Package name: `lammps`
- Install command: `brew install lammps`
- Binary location: `/opt/homebrew/opt/lammps/bin/lmp_serial`
- Potentials location: `/opt/homebrew/opt/lammps/share/lammps/potentials/`
- Examples location: `/opt/homebrew/opt/lammps/share/lammps/bench/`
- Self-test file: `in.lj` in bench directory

**Verification Command**:
```bash
brew --prefix lammps
# /opt/homebrew/opt/lammps

ls $(brew --prefix lammps)/bin/
# lmp_serial (or lmp_mpi if MPI enabled)
```

### 3.2 Ubuntu/Debian (apt)

**URL**: https://packages.ubuntu.com/search?keywords=lammps

**Key Information**:
- Package name: `lammps`
- Install command: `sudo apt install lammps`
- Binary: `/usr/bin/lmp` or `/usr/bin/lmp_mpi`
- Potentials: `/usr/share/lammps/potentials/`

**Verification Command**:
```bash
apt-cache policy lammps
dpkg -L lammps | grep bin
```

### 3.3 Conda

**URL**: https://anaconda.org/conda-forge/lammps

**Key Information**:
- Channel: conda-forge
- Install: `conda install -c conda-forge lammps`
- Binary: `$CONDA_PREFIX/bin/lmp`

---

## 4. Potential File Sources

### 4.1 LAMMPS Repository Potentials

**URL**: https://github.com/lammps/lammps/tree/stable/potentials

**Key Information**:
- Contains redistributable EAM, Tersoff, SW, MEAM potentials
- License: GPL-2.0 (same as LAMMPS)
- Can be downloaded and redistributed

**Files of Interest**:
- `Cu_u3.eam` - Single element Cu EAM
- `Al_zhou.eam.alloy` - Al alloy EAM
- `SiC.tersoff` - Si-C Tersoff
- `Si.sw` - Si Stillinger-Weber

### 4.2 NIST Interatomic Potentials Repository

**URL**: https://www.ctcms.nist.gov/potentials/

**Key Information**:
- Curated collection of validated potentials
- Individual license per potential (check before use)
- Citations provided
- Not directly redistributable without checking license

**Used For**: User documentation, not test fixtures

### 4.3 OpenKIM

**URL**: https://openkim.org/

**Key Information**:
- Standardized potential testing
- Model-driver pattern
- LAMMPS integration via `pair_style kim`
- Complex setup, future extension

---

## 5. Tutorials and Examples

### 5.1 LAMMPS Tutorials

**URL**: https://docs.lammps.org/Tutorials.html

**Key Information**:
- Basic workflow examples
- MD simulation setup
- Analysis examples

### 5.2 Benchmark Inputs

**Location**: `share/lammps/bench/` (in installation)

**Key Files**:
- `in.lj` - LJ fluid benchmark (no external files needed)
- `in.eam` - EAM metal benchmark
- `in.chain` - Polymer chain benchmark

**Used For**: Self-test, binary validation

---

## 6. Python Integration

### 6.1 LAMMPS Python Module

**URL**: https://docs.lammps.org/Python_module.html

**Key Information**:
- Direct Python bindings (not used in our integration)
- Log file format classes
- Useful for understanding output formats

### 6.2 pyiron_lammps

**URL**: https://github.com/pyiron/pyiron_lammps

**Key Information**:
- Reference implementation for LAMMPS wrapper
- Input file generation patterns
- Output parsing patterns
- MIT license

**Used For**: Implementation patterns (reference only, not copied)

---

## 7. Units and Conversions

### 7.1 LAMMPS Units

**URL**: https://docs.lammps.org/units.html

**Key Conversions (metal → canonical)**:

| Quantity | LAMMPS metal | Canonical | Conversion |
|----------|--------------|-----------|------------|
| Distance | Å | Å | 1:1 |
| Time | ps | fs | ×1000 |
| Energy | eV | eV | 1:1 |
| Velocity | Å/ps | Å/fs | ÷1000 |
| Force | eV/Å | eV/Å | 1:1 |
| Temperature | K | K | 1:1 |
| Pressure | bar | bar | 1:1 |

**Key Conversions (real → canonical)**:

| Quantity | LAMMPS real | Canonical | Conversion |
|----------|-------------|-----------|------------|
| Distance | Å | Å | 1:1 |
| Time | fs | fs | 1:1 |
| Energy | kcal/mol | eV | ×0.0433634 |
| Force | kcal/mol/Å | eV/Å | ×0.0433634 |

---

## 8. Dump File Format

### 8.1 Custom Dump Format

**URL**: https://docs.lammps.org/dump.html

**Format**:
```
ITEM: TIMESTEP
{timestep}
ITEM: NUMBER OF ATOMS
{natoms}
ITEM: BOX BOUNDS {boundary types}
{xlo} {xhi}
{ylo} {yhi}
{zlo} {zhi}
ITEM: ATOMS {column names}
{atom data...}
```

**Our Fixed Columns**:
```
id type x y z vx vy vz fx fy fz
```

**Parser Strategy**:
1. Read `ITEM: TIMESTEP` to get frame number
2. Read `ITEM: NUMBER OF ATOMS` to get count
3. Read `ITEM: BOX BOUNDS` for cell
4. Parse `ITEM: ATOMS` header for column names
5. Read N lines of atom data
6. Sort by id column
7. Map types to species using structure type_map

---

## 9. Log File Format

### 9.1 Thermo Output

**Location in log**: After `run` or `minimize` command

**Format**:
```
Step Temp PotEng KinEng TotEng Press
0    300.00  -3.5420  0.0387  -3.5033  -12.345
100  298.52  -3.5418  0.0385  -3.5033  -11.892
...
```

**Parser Strategy**:
1. Find line starting with "Step" or matching thermo_style columns
2. Read subsequent numeric lines
3. Stop at non-numeric line or "Loop time" summary
4. Handle multiple thermo blocks (minimize then run)

---

## 10. Restart File Format

### 10.1 Binary Restart

**URL**: https://docs.lammps.org/read_restart.html

**Key Information**:
- Binary format, platform-specific endianness
- Contains: box, atoms, velocities, image flags
- Does NOT contain: pair_style, fixes, computes
- Must re-specify force field in continuation script

**Implications**:
- `pair_style`/`pair_coeff` must be in restart script
- `fix` commands must be re-specified
- `potential` reference must be re-provided

---

## 11. Summary Table

| Topic | Primary Source | Used In |
|-------|---------------|---------|
| Input script structure | docs.lammps.org/Commands_structure | Templates |
| Units systems | docs.lammps.org/units | Unit conversion |
| Pair styles | docs.lammps.org/pair_* | Potential staging |
| Output formats | docs.lammps.org/Howto_output | Parsers |
| Data file format | docs.lammps.org/read_data | Structure writer |
| Dump format | docs.lammps.org/dump | Trajectory parser |
| Homebrew install | `brew info lammps` | Binary discovery |
| Ubuntu install | packages.ubuntu.com | Binary discovery |
| Test potentials | github.com/lammps/potentials | Test fixtures |

---

## 12. Installation Paths (Phase 0 Verification)

### 12.1 macOS (Homebrew) - Verified 2026-01-20

**Installation**:
```bash
brew install lammps
```

**Binary Location** (Verified):
- Serial: `/opt/homebrew/opt/lammps/bin/lmp_serial` ✓
- MPI: `/opt/homebrew/opt/lammps/bin/lmp_mpi` ✓
- Version: 22 Jul 2025 - Update 2

**Potential Files** (Copied to `resources/lammps/potentials/`):
- **Cu_u3.eam**: `/opt/homebrew/opt/lammps/share/lammps/bench/POTENTIALS/Cu_u3.eam` ✓
  - License: GPL-2.0 (LAMMPS bundled)
  - Size: 36KB
- **Si.tersoff**: `/opt/homebrew/opt/lammps/share/lammps/bench/POTENTIALS/Si.tersoff` ✓
  - Copied as: `SiC.tersoff`
  - License: GPL-2.0 (LAMMPS bundled)
  - Size: 854B

**LJ Smoke Test** (Verified):
- `units lj` with `pair_style lj/cut` works without external files ✓
- Test command: `lmp_serial -in test_lj.in` (passed)

### 12.2 Ubuntu (apt) - To be verified in CI

**Installation**:
```bash
sudo apt-get update
sudo apt-get install -y lammps
```

**Expected Binary Location**:
- `/usr/bin/lmp` or `/usr/bin/lmp_mpi`

## 13. Document Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-20 | 1.0.0 | Initial compilation for implementation plan |
| 2026-01-20 | 1.1.0 | Phase 0 verification: Added installation paths and potential file locations |

