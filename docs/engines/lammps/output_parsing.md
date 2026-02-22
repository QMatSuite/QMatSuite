# LAMMPS Output Parsing Strategy

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase  
**Constitution Reference**: §2 (Trajectory), §5 (Units)

---

## 1. Overview

LAMMPS produces multiple output file types. This document defines parsing strategies to extract data into QMatSuite's canonical trajectory and analysis objects.

---

## 2. Output File Types

| File | Content | Parser Priority |
|------|---------|-----------------|
| `log.lammps` | Thermo time series, diagnostics | P0 - Always parse |
| `*.lammpstrj` / `dump.*` | Atomic trajectory snapshots | P1 - If exists |
| `restart.*.bin` | Binary simulation state | P2 - For continuation info |
| `final.data` / `*.data` | Structure in LAMMPS format | P1 - For final geometry |

---

## 3. Canonical Trajectory Mapping

### 3.1 Target Structure (from TRAJECTORY_CORE.md)

```python
@dataclass
class Frame:
    # REQUIRED
    frame_index: int
    positions: NDArray[np.float64]  # (N, 3), Å
    species: List[str]              # Element symbols
    cell: NDArray[np.float64]       # (3, 3), Å
    pbc: Tuple[bool, bool, bool]
    
    # OPTIONAL
    time: Optional[float] = None          # fs
    iteration: Optional[int] = None
    velocities: Optional[NDArray] = None  # Å/fs
    momenta: Optional[NDArray] = None
    energy: Optional[float] = None        # eV
    forces: Optional[NDArray] = None      # eV/Å
    temperature: Optional[float] = None   # K
    pressure: Optional[float] = None      # GPa
    kinetic_energy: Optional[float] = None
    stress: Optional[NDArray] = None      # (3,3), GPa
    extras: Dict[str, Any] = field(default_factory=dict)
```

### 3.2 LAMMPS → Canonical Field Mapping

| Canonical Field | LAMMPS Source | Conversion |
|-----------------|---------------|------------|
| `positions` | dump: x,y,z or xu,yu,zu | Unwrap if needed |
| `species` | data file: atom types → element map | Type→Element lookup |
| `cell` | dump: BOX BOUNDS | Extract vectors |
| `pbc` | input: boundary command | Parse p/f/s flags |
| `time` | dump: TIMESTEP × timestep | Convert to fs |
| `iteration` | dump: TIMESTEP | Direct |
| `velocities` | dump: vx,vy,vz | Units conversion |
| `energy` | log: TotEng or PotEng | Units conversion |
| `forces` | dump: fx,fy,fz | Units conversion |
| `temperature` | log: Temp | Direct (K) |
| `pressure` | log: Press | Convert to GPa |

---

## 4. Units Conversion

### 4.1 LAMMPS Units Systems

| Quantity | metal | real | lj | Canonical (QMatSuite) |
|----------|-------|------|----|-----------------------|
| Length | Å | Å | σ | Å |
| Energy | eV | kcal/mol | ε | eV |
| Time | ps | fs | τ | fs |
| Velocity | Å/ps | Å/fs | σ/τ | Å/fs |
| Force | eV/Å | kcal/mol·Å | ε/σ | eV/Å |
| Pressure | bar | atm | ε/σ³ | GPa |
| Temperature | K | K | ε/kB | K |

### 4.2 Conversion Implementation

```python
class LammpsUnitsConverter:
    """Convert LAMMPS units to canonical QMatSuite units."""
    
    CONVERSIONS = {
        "metal": {
            "length": 1.0,           # Å → Å
            "energy": 1.0,           # eV → eV
            "time": 1000.0,          # ps → fs
            "velocity": 0.001,       # Å/ps → Å/fs
            "force": 1.0,            # eV/Å → eV/Å
            "pressure": 1e-4,        # bar → GPa
        },
        "real": {
            "length": 1.0,           # Å → Å
            "energy": 0.0433634,     # kcal/mol → eV
            "time": 1.0,             # fs → fs
            "velocity": 1.0,         # Å/fs → Å/fs
            "force": 0.0433634,      # kcal/mol·Å → eV/Å
            "pressure": 0.000101325, # atm → GPa
        },
        "lj": {
            # LJ units require sigma/epsilon from pair_style
            "length": lambda sigma: sigma,
            "energy": lambda epsilon: epsilon,
            # ...
        },
    }
    
    def __init__(self, units: str, lj_params: dict = None):
        self.units = units
        self.lj_params = lj_params or {}
    
    def convert(self, value, quantity: str):
        conv = self.CONVERSIONS[self.units][quantity]
        if callable(conv):
            return conv(self.lj_params.get(quantity, 1.0)) * value
        return conv * value
```

---

## 5. Log File Parsing

### 5.1 Thermo Block Structure

```
# LAMMPS log.lammps example
...
Memory usage per processor = 3.5 Mbytes
Step Temp PotEng TotEng Press Volume
       0          300      -3.542      -3.503      1.234     47.001
     100       298.52      -3.541      -3.503      1.189     47.002
     200       301.23      -3.540      -3.502      1.203     47.003
...
Loop time of 1.23 on 4 procs for 1000 steps
```

### 5.2 Thermo Parser

```python
def parse_lammps_log(log_path: Path) -> LammpsLogData:
    """
    Parse LAMMPS log file for thermo data and metadata.
    
    Returns:
        LammpsLogData with:
        - thermo_blocks: List of ThermoBlock (header + data)
        - metadata: Dict of run info (version, timing, etc.)
    """
    content = log_path.read_text()
    
    thermo_blocks = []
    current_block = None
    
    for line in content.split('\n'):
        # Detect thermo header (column names)
        if is_thermo_header(line):
            current_block = ThermoBlock(
                columns=parse_thermo_columns(line),
                data=[],
            )
        # Detect thermo data row
        elif current_block and is_numeric_row(line):
            current_block.data.append(parse_numeric_row(line))
        # End of thermo block
        elif current_block and not is_numeric_row(line):
            thermo_blocks.append(current_block)
            current_block = None
    
    return LammpsLogData(
        thermo_blocks=thermo_blocks,
        metadata=extract_metadata(content),
    )
```

### 5.3 Common Thermo Columns

| Column Name | Meaning | Canonical Field |
|-------------|---------|-----------------|
| `Step` | Timestep number | `iteration` |
| `Time` | Simulation time | `time` |
| `Temp` | Temperature | `temperature` |
| `PotEng` / `pe` | Potential energy | `energy` |
| `KinEng` / `ke` | Kinetic energy | `kinetic_energy` |
| `TotEng` / `etotal` | Total energy | (derived) |
| `Press` | Pressure | `pressure` |
| `Volume` / `vol` | Volume | (cell derived) |
| `Lx`, `Ly`, `Lz` | Box dimensions | `cell` |

---

## 6. Dump File Parsing

### 6.1 Dump File Format

```
ITEM: TIMESTEP
1000
ITEM: NUMBER OF ATOMS
108
ITEM: BOX BOUNDS pp pp pp
0.0 10.8
0.0 10.8
0.0 10.8
ITEM: ATOMS id type xu yu zu vx vy vz fx fy fz
1 1 0.123 0.456 0.789 0.001 0.002 0.003 0.01 0.02 0.03
2 1 1.234 2.345 3.456 0.004 0.005 0.006 0.04 0.05 0.06
...
```

### 6.2 Dump Parser

```python
def parse_lammps_dump(dump_path: Path) -> Iterator[DumpSnapshot]:
    """
    Parse LAMMPS dump file, yielding snapshots.
    
    Handles:
    - Standard dump format (ITEM: blocks)
    - Wrapped (x,y,z) vs unwrapped (xu,yu,zu) coordinates
    - Variable column ordering
    - Triclinic boxes (with tilt factors)
    """
    with open(dump_path) as f:
        while True:
            snapshot = read_next_snapshot(f)
            if snapshot is None:
                break
            yield snapshot


def read_next_snapshot(f) -> Optional[DumpSnapshot]:
    """Read single snapshot from dump file."""
    timestep = None
    n_atoms = None
    box_bounds = None
    atom_columns = None
    atom_data = []
    
    for line in f:
        line = line.strip()
        
        if line == "ITEM: TIMESTEP":
            timestep = int(next(f).strip())
        
        elif line == "ITEM: NUMBER OF ATOMS":
            n_atoms = int(next(f).strip())
        
        elif line.startswith("ITEM: BOX BOUNDS"):
            # Parse boundary conditions (pp, ff, ss)
            pbc = parse_box_bounds_line(line)
            box_bounds = []
            for _ in range(3):
                bounds = list(map(float, next(f).split()))
                box_bounds.append(bounds)
        
        elif line.startswith("ITEM: ATOMS"):
            # Parse column order
            atom_columns = line.split()[2:]  # Skip "ITEM: ATOMS"
            
            # Read atom data
            for _ in range(n_atoms):
                values = next(f).split()
                atom_data.append(values)
            
            # Complete snapshot
            return DumpSnapshot(
                timestep=timestep,
                n_atoms=n_atoms,
                box_bounds=box_bounds,
                pbc=pbc,
                columns=atom_columns,
                atoms=atom_data,
            )
    
    return None
```

### 6.3 Converting Dump to Canonical Frame

```python
def dump_snapshot_to_frame(
    snapshot: DumpSnapshot,
    type_map: Dict[int, str],  # atom_type → element
    units: str,
    converter: LammpsUnitsConverter,
) -> Frame:
    """Convert LAMMPS dump snapshot to canonical Frame."""
    
    # Parse box
    cell = parse_box_to_cell(snapshot.box_bounds)
    
    # Map columns to indices
    col_idx = {col: i for i, col in enumerate(snapshot.columns)}
    
    # Extract positions (prefer unwrapped)
    if 'xu' in col_idx:
        pos_cols = ['xu', 'yu', 'zu']
    else:
        pos_cols = ['x', 'y', 'z']
    
    positions = np.array([
        [float(atom[col_idx[c]]) for c in pos_cols]
        for atom in snapshot.atoms
    ])
    
    # Extract species
    type_col = col_idx.get('type')
    species = [
        type_map.get(int(atom[type_col]), 'X')
        for atom in snapshot.atoms
    ]
    
    # Optional: velocities
    velocities = None
    if 'vx' in col_idx:
        velocities = np.array([
            [float(atom[col_idx[c]]) for c in ['vx', 'vy', 'vz']]
            for atom in snapshot.atoms
        ])
        velocities = converter.convert(velocities, 'velocity')
    
    # Optional: forces
    forces = None
    if 'fx' in col_idx:
        forces = np.array([
            [float(atom[col_idx[c]]) for c in ['fx', 'fy', 'fz']]
            for atom in snapshot.atoms
        ])
        forces = converter.convert(forces, 'force')
    
    return Frame(
        frame_index=snapshot.timestep,
        positions=positions,
        species=species,
        cell=cell,
        pbc=snapshot.pbc,
        iteration=snapshot.timestep,
        velocities=velocities,
        forces=forces,
    )
```

---

## 7. Restart File Handling

### 7.1 Restart File Content

Restart files are binary and contain:
- Simulation box (dimensions, boundary conditions)
- Atom positions and velocities
- Atom types and IDs
- Some fix/compute internal state

**NOT stored in restart**:
- Force field definitions (`pair_style`, `pair_coeff`)
- Fix/compute definitions
- Output settings

### 7.2 Parsing Strategy

Restart files are NOT directly parsed for trajectory data. Instead:

1. **For structure extraction**: Use LAMMPS itself via `restart2data`:
   ```bash
   lmp -r restart.bin data.converted
   ```

2. **For continuation**: Reference restart file in continuation script:
   ```bash
   read_restart restart.bin
   ```

3. **Metadata only**: Record restart file existence and timestamp for provenance.

---

## 8. Data File Parsing

### 8.1 Data File Structure

```
LAMMPS data file via QMatSuite

4 atoms
1 atom types

0.0 3.6 xlo xhi
0.0 3.6 ylo yhi
0.0 3.6 zlo zhi

Masses

1 63.546

Atoms  # atomic

1 1 0.0 0.0 0.0
2 1 1.8 1.8 0.0
3 1 0.0 1.8 1.8
4 1 1.8 0.0 1.8
```

### 8.2 Data File Parser

```python
def parse_lammps_data(data_path: Path) -> Structure:
    """
    Parse LAMMPS data file to QMatSuite Structure.
    
    Handles:
    - Orthogonal and triclinic boxes
    - Multiple atom styles
    - Atom type → mass → element mapping
    """
    content = data_path.read_text()
    
    # Parse header
    n_atoms = parse_header_value(content, r"(\d+) atoms")
    n_types = parse_header_value(content, r"(\d+) atom types")
    
    # Parse box
    box_lo_hi = parse_box_bounds(content)
    tilt = parse_tilt_factors(content)  # Optional
    cell = construct_cell(box_lo_hi, tilt)
    
    # Parse masses (for type → element mapping)
    masses = parse_masses_section(content)
    type_to_element = map_mass_to_element(masses)
    
    # Parse atoms
    atoms = parse_atoms_section(content)
    
    # Build structure
    species = [type_to_element[a.type] for a in atoms]
    positions = np.array([[a.x, a.y, a.z] for a in atoms])
    
    return Structure(
        species=species,
        positions=positions,
        cell=cell,
        pbc=(True, True, True),  # Default, can be overridden
    )
```

---

## 9. Meta/Provenance (Not Core Data)

The following information is recorded as metadata/provenance but does NOT enter the canonical trajectory Frame:

| Information | Source | Storage Location |
|-------------|--------|------------------|
| LAMMPS version | log header | `.runtime/provenance.json` |
| Build packages | `lmp -h packages` | Engine discovery cache |
| Input script | `in.lammps` | Calc raw directory |
| `units` command | Input script | Step parameters |
| `atom_style` | Input script | Step parameters |
| `pair_style` | Input script | Step parameters |
| MPI ranks/threads | Log timing | `.runtime/provenance.json` |
| Wall time | Log timing | Run revision |

---

## 10. Parser Integration

### 10.1 Parser Registry Entry

```python
# In src/qmatsuite/parsers/registry.py

PARSER_REGISTRY = {
    ...
    "lammps": {
        "log": LammpsLogParser,
        "dump": LammpsDumpParser,
        "data": LammpsDataParser,
    },
}
```

### 10.2 Unified Trajectory Builder

```python
def build_lammps_trajectory(
    calc_dir: Path,
    step_ulid: str,
    step_params: dict,
) -> Trajectory:
    """
    Build canonical trajectory from LAMMPS outputs.
    
    Combines:
    - Thermo data from log (global properties)
    - Atomic data from dump (per-atom properties)
    - Final structure from data file
    """
    raw_dir = calc_dir / "raw" / step_ulid
    
    # Determine units for conversion
    units = step_params.get("units", "metal")
    converter = LammpsUnitsConverter(units)
    
    # Parse log for thermo
    log_path = raw_dir / "log.lammps"
    log_data = parse_lammps_log(log_path)
    
    # Parse dump for trajectory frames
    dump_path = find_dump_file(raw_dir)
    if dump_path:
        dump_frames = list(parse_lammps_dump(dump_path))
    else:
        dump_frames = []
    
    # Get type map from structure or data file
    type_map = build_type_map(raw_dir)
    
    # Build frames
    frames = []
    for i, dump_snapshot in enumerate(dump_frames):
        frame = dump_snapshot_to_frame(
            dump_snapshot, type_map, units, converter
        )
        
        # Merge thermo data for this timestep
        thermo_row = find_thermo_for_timestep(log_data, dump_snapshot.timestep)
        if thermo_row:
            frame.temperature = thermo_row.get("Temp")
            frame.pressure = converter.convert(thermo_row.get("Press", 0), "pressure")
            frame.energy = converter.convert(thermo_row.get("PotEng", 0), "energy")
        
        frames.append(frame)
    
    return Trajectory(
        frames=frames,
        meta=TrajectoryMeta(
            engine="lammps",
            step_type=step_params.get("step_type"),
            trajectory_type="md",  # or "relax"
            ...
        ),
    )
```

---

## 11. Error Handling

### 11.1 Parsing Failures

| Scenario | Behavior |
|----------|----------|
| Log file missing | Hard error - required for all steps |
| Dump file missing | Warning - proceed without trajectory |
| Corrupted dump frame | Skip frame with warning |
| Unknown thermo column | Ignore column |
| Type map unavailable | Use "X" as placeholder element |

### 11.2 Partial Data

Parser should be resilient to partial data:

```python
def parse_lammps_dump_resilient(dump_path: Path) -> List[Frame]:
    """Parse dump file, handling partial/corrupted snapshots."""
    frames = []
    for snapshot in parse_lammps_dump(dump_path):
        try:
            frame = convert_snapshot(snapshot)
            frames.append(frame)
        except Exception as e:
            logger.warning(f"Skipping corrupted frame at timestep {snapshot.timestep}: {e}")
    return frames
```

