# Structure I/O and CLI Usage Guide

This document provides detailed examples and usage patterns for QuantumVITAS structure handling and CLI commands.

## Table of Contents

1. [Structure I/O Functions](#structure-io-functions)
2. [CLI Commands](#cli-commands)
3. [Parameter Overrides](#parameter-overrides)
4. [Complete Workflow Examples](#complete-workflow-examples)
5. [API Reference](#api-reference)

---

## Structure I/O Functions

### `read_structure(filepath, format=None)`

Reads atomic structures from various file formats using pymatgen.

**Supported Formats:**
- `.cif` - Crystallographic Information File
- `.poscar`, `.vasp` - VASP POSCAR format
- `.in`, `.qe` - Quantum ESPRESSO input files
- `.json` - pymatgen Structure JSON (canonical format)

**Example 1: Reading from CIF**

```python
from pathlib import Path
from quantumvitas.io import read_structure

# Read a CIF file
structure = read_structure(Path("si.cif"))
print(f"Formula: {structure.formula}")
print(f"Number of sites: {len(structure)}")
print(f"Lattice: {structure.lattice}")
```

**Example 2: Reading from QE Input**

```python
# Read structure from an existing QE input file
structure = read_structure(Path("si.scf.in"), format="qe")
# The function extracts ATOMIC_POSITIONS and CELL_PARAMETERS
```

**Example 3: Reading from JSON (canonical format)**

```python
# Read from our canonical JSON format
structure = read_structure(Path("structures/si.json"))
```

---

### `write_structure(structure, filepath, format=None, metadata=None)`

Writes atomic structures to various file formats.

**Example 1: Writing to JSON (canonical format)**

```python
from quantumvitas.io import write_structure
from pymatgen.core import Structure, Lattice

# Create a simple structure
lattice = Lattice.cubic(5.43)
structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])

# Write to JSON (recommended for project storage)
# Metadata (ResourceMeta or dict) is embedded automatically when provided.
write_structure(structure, Path("structures/si.json"), format="json", metadata={"kind": "structure"})
```

**Example 2: Writing to CIF**

```python
# Export to CIF for external tools
write_structure(structure, Path("si.cif"), format="cif")
```

**Example 3: Writing to POSCAR**

```python
# Export to VASP POSCAR format
write_structure(structure, Path("POSCAR"), format="poscar")
```

---

### `qe_input_from_structure(structure)`

Generates a minimal QE input file from a pymatgen Structure.

**What it creates:**
- `&CONTROL` namelist with `calculation='scf'`
- Empty `&SYSTEM` and `&ELECTRONS` namelists (to be filled by parameters)
- `ATOMIC_SPECIES` card with element symbols, masses, and placeholder pseudopotentials
- `ATOMIC_POSITIONS` card in angstrom
- `CELL_PARAMETERS` card in angstrom
- `K_POINTS` card with automatic mesh (4x4x4 default)

**Example:**

```python
from quantumvitas.io import read_structure, qe_input_from_structure
from quantumvitas.io import QEInputGenerator

# Read structure
structure = read_structure(Path("si.cif"))

# Generate QE input
qe_input = qe_input_from_structure(structure)

# Write to file
QEInputGenerator.write_file(qe_input, Path("si.pw.in"))
```

**Generated output (si.pw.in):**

```
&CONTROL
    calculation = 'scf'
/
&SYSTEM
/
&ELECTRONS
/
ATOMIC_SPECIES
Si  28.085  Si.upf
ATOMIC_POSITIONS angstrom
Si  0.0  0.0  0.0
Si  1.3575  1.3575  1.3575
CELL_PARAMETERS angstrom
   5.430000  0.000000  0.000000
   0.000000  5.430000  0.000000
   0.000000  0.000000  5.430000
K_POINTS automatic
4 4 4 0 0 0
```

---

### `structure_from_qe_input(qe_input)`

Extracts a pymatgen Structure from a parsed QE input.

**Example:**

```python
from quantumvitas.io import QEInputParser
from quantumvitas.io.structure_io import structure_from_qe_input

# Parse QE input
qe_input = QEInputParser.parse_file(Path("si.scf.in"))

# Extract structure
structure = structure_from_qe_input(qe_input)
```

---

## CLI Commands

### `qv import-structure`

Imports a structure file and registers it in the project.

**Basic Usage:**

```bash
# Import from CIF
qv import-structure si.cif --id si

# Import from POSCAR
qv import-structure POSCAR --id si_vasp

# Import from QE input
qv import-structure si.scf.in --id si_from_qe

# Specify output format (default is json)
qv import-structure si.cif --id si --output-format json
```

**What it does:**
1. Reads the structure file using pymatgen
2. Saves it to `structures/<id>.json` (or specified format)
3. Registers it in `project.qv.yml`

**Example project.qv.yml after import:**

```yaml
structures:
  - id: si
    file: structures/si.json
    format: json
```

**Example Output:**

```
Imported structure 'si' -> structures/si.json
```

---

### `qv run-structure`

Generates a QE input from a stored structure and runs it with parameter overrides.

**Basic Usage:**

```bash
# Run with structure ID from project
qv run-structure si --ecutwfc=60 --ecutrho=240

# Run with direct file path
qv run-structure structures/si.json --ecutwfc=60

# Specify working directory
qv run-structure si --workdir temp/si_scf --ecutwfc=60

# Custom input filename
qv run-structure si --input-name si.pw.in --ecutwfc=60
```

**What it does:**
1. Loads the structure (from project or file path)
2. Generates a minimal QE input via `qe_input_from_structure`
3. Applies parameter overrides from CLI
4. Runs the calculation via `qv run-step`

**Example with multiple parameters:**

```bash
qv run-structure si \
  --ecutwfc=60 \
  --ecutrho=240 \
  --degauss=0.01 \
  --k_points="[6,6,6,0,0,0]"
```

---

### `qv run-stepfile`

Runs a QE step described by a YAML file (structure id/path, calculation type,
parameter dictionaries). This is useful for sharing single-step recipes or
keeping complex parameter sets in version control.

**Step YAML Format:**

```yaml
structure: si
step_type: scf
input_name: si_scf.pw.in
parameters:
  CONTROL:
    prefix: si
  SYSTEM:
    ecutwfc: 60
    ecutrho: 240
  ELECTRONS:
    conv_thr: 1.0e-8
```

**Usage:**

```bash
qv run-stepfile workflows/si_scf_step.yaml

# CLI overrides take precedence over YAML values
qv run-stepfile workflows/si_scf_step.yaml --SYSTEM.ecutwfc=70
```

**What it does:**
1. Loads the structure (from project or explicit path)
2. Generates a QE input via `qe_input_from_structure`
3. Applies parameters from YAML (and any CLI overrides)
4. Executes the QE step via `run_input_step`

---

### `qv run-step`

Runs a QE input file with optional parameter overrides.

**Basic Usage:**

```bash
# Run without overrides
qv run-step si.scf.in

# Run with parameter overrides
qv run-step si.scf.in --ecutwfc=60 --degauss=0.01

# Run with section-prefixed parameters
qv run-step si.scf.in --SYSTEM.ecutwfc=60 --SYSTEM.ecutrho=240

# Run with working directory
qv run-step si.scf.in --workdir temp/run_scf
```

**Example with various parameter types:**

```bash
# Integer
qv run-step si.scf.in --ecutwfc=60

# Float
qv run-step si.scf.in --degauss=0.01

# Boolean (true)
qv run-step si.scf.in --tprnfor

# Boolean (false)
qv run-step si.scf.in --tprnfor=false

# String
qv run-step si.scf.in --prefix='si'

# List (Python/JSON syntax)
qv run-step si.scf.in --k_points="[6,6,6,0,0,0]"

# Multiple parameters
qv run-step si.scf.in \
  --ecutwfc=60 \
  --ecutrho=240 \
  --degauss=0.01 \
  --SYSTEM.nspin=2 \
  --CONTROL.restart_mode='from_scratch'
```

---

## Step & Workflow Import Helpers

To migrate existing QE inputs into the structured workflow layout, leverage
`quantumvitas.workflow.importers`:

- `build_step_spec_from_qe_input(input_file, destination_dir, ...)`  
  Parses a QE input, stores the extracted structure as JSON, captures
  namelists/cards, and emits a `*.step.yaml` ready for `qv run-stepfile`.
- `build_workflow_from_qe_inputs(files, workflow_dir, ...)`  
  Processes multiple QE inputs in order, copies the originals under
  `raw/original_inputs/`, writes per-step YAML files, and generates
  `workflow.yaml` that references those specs. Structures can be referenced by
  absolute/relative path (self-contained workflows) or by structure id for
  project-integrated setups.

---

## Parameter Overrides

### How Parameter Mapping Works

The CLI uses `qe_module_parameters.json` to automatically map parameters to their correct namelists.

**Example: Ambiguous Parameters**

If a parameter exists in multiple sections, you must specify the section:

```bash
# This will fail if 'prefix' exists in both CONTROL and SYSTEM
qv run-step input.in --prefix='si'

# This works (explicit section)
qv run-step input.in --CONTROL.prefix='si'
```

**Example: Unknown Parameters**

If a parameter is not in the metadata, you must provide the section:

```bash
# This will fail
qv run-step input.in --custom_param=value

# This works
qv run-step input.in --CONTROL.custom_param=value
```

### Parameter Value Coercion

The CLI automatically converts string values to appropriate types:

- **Booleans**: `true`, `false`, `.true.`, `.false.`, `t`, `f`
- **Integers**: `60`, `-1`
- **Floats**: `60.0`, `0.01`, `1e-5`
- **Lists**: `[1,2,3]`, `(1,2,3)`, `1,2,3` (comma-separated)
- **Strings**: Quoted values or default

**Examples:**

```bash
# Boolean
--tprnfor              # True
--tprnfor=false        # False

# Integer
--ecutwfc=60

# Float
--degauss=0.01

# List (multiple formats)
--k_points="[6,6,6,0,0,0]"
--k_points="(6,6,6,0,0,0)"
--k_points="6,6,6,0,0,0"

# String
--prefix='si'
--calculation="scf"
```

### Card Overrides (K_POINTS, CELL_PARAMETERS, etc.)

Card overrides can be supplied either with the explicit `CARD.` prefix or via
shorthands:

```bash
# Replace the entire K_POINTS card
qv run-step si.scf.in --CARD.K_POINTS.data="[[6,6,6,0,0,0]]"

# Shorthand: option:data syntax (auto-splits on the first colon)
qv run-step si.scf.in --k_points="automatic:6,6,6,0,0,0"

# Update only a single row (e.g., Monkhorst-Pack offsets)
qv step-set-param steps/nscf.step.yaml --CARD.K_POINTS.rows.row1=0,0,1
```

Cell and atomic-position cards follow the same pattern:

```bash
qv run-step si.relax.in --CARD.CELL_PARAMETERS.data="[[5.3,0,0],[0,5.3,0],[0,0,5.3]]"
qv run-step si.relax.in --CARD.ATOMIC_POSITIONS.option=angstrom --CARD.ATOMIC_POSITIONS.rows.Si1="0.0 0.0 0.0"
```

Use `--remove` with `qv step-set-param` to drop card rows/entries.

### Species Overrides (masses/pseudopotentials)

Pseudopotentials and atomic masses live in the `ATOMIC_SPECIES` card. Override
them declaratively:

```bash
# Update mass and pseudopotential filename
qv run-structure si_bulk \
  --SPECIES.Si.mass=28.0855 \
  --SPECIES.Si.pseudopot=Si.pbe-n-rrkjus_psl.1.0.0.UPF

# Remove a mass override from a step spec
qv step-set-param steps/scf.step.yaml --remove --SPECIES.Si.mass=0
```

Species overrides pair naturally with the unified pseudo directory (`temp/pseudo`
in tests) so QE never downloads to scattered locations.

---

## Complete Workflow Examples

### Example 1: Import Structure and Run SCF

```bash
# Step 1: Import structure from CIF
qv import-structure si.cif --id si

# Step 2: Run SCF calculation with parameters
qv run-structure si \
  --ecutwfc=60 \
  --ecutrho=240 \
  --degauss=0.01 \
  --k_points="[6,6,6,0,0,0]" \
  --workdir temp/si_scf
```

### Example 2: Modify Existing QE Input

```bash
# Run existing input with modified parameters
qv run-step si.scf.in \
  --ecutwfc=80 \
  --ecutrho=320 \
  --workdir temp/si_scf_high_cutoff
```

### Example 3: Structure from Multiple Sources

```bash
# Import from VASP POSCAR
qv import-structure POSCAR --id si_vasp

# Import from QE input
qv import-structure si.scf.in --id si_from_qe

# Run either one
qv run-structure si_vasp --ecutwfc=60
qv run-structure si_from_qe --ecutwfc=60
```

### Example 4: Python API Usage

```python
from pathlib import Path
from quantumvitas.io import (
    read_structure,
    write_structure,
    qe_input_from_structure,
    QEInputGenerator,
)
from quantumvitas.workflow.input_runner import (
    run_input_step,
    ParameterOverride,
)
from quantumvitas.engine.registry import create_default_registry

# Read structure
structure = read_structure(Path("si.cif"))

# Save to project
write_structure(structure, Path("structures/si.json"), format="json")

# Generate QE input
qe_input = qe_input_from_structure(structure)

# Apply parameter overrides programmatically
from quantumvitas.workflow.input_runner import _apply_parameter_overrides
overrides = [
    ParameterOverride(name="ecutwfc", value=60, section=None),
    ParameterOverride(name="ecutrho", value=240, section=None),
]
_apply_parameter_overrides(qe_input, overrides)

# Write input file
QEInputGenerator.write_file(qe_input, Path("si.pw.in"))

# Run calculation
registry = create_default_registry()
engine = registry.get("qe")
result, prepared = run_input_step(
    engine=engine.backend,
    input_file=Path("si.pw.in"),
    working_dir=Path("temp/run_scf"),
    project_root=Path("."),
    parameter_overrides=overrides,
)
print(f"Output: {result.output_file}")
```

---

## API Reference

### `read_structure(filepath: Path, format: Optional[str] = None) -> PMGStructure`

Reads a structure from a file.

**Parameters:**
- `filepath`: Path to structure file
- `format`: Optional format hint (auto-detected from extension if None)

**Returns:**
- `pymatgen.core.Structure`: The parsed structure

**Raises:**
- `FileNotFoundError`: If file doesn't exist
- `ValueError`: If format is unsupported or structure cannot be parsed

---

### `write_structure(structure: PMGStructure, filepath: Path, format: Optional[str] = None, metadata: Optional[dict] = None) -> None`

Writes a structure to a file.

**Parameters:**
- `structure`: pymatgen Structure object
- `filepath`: Path to output file
- `format`: Optional format hint (auto-detected from extension if None)
- `metadata`: Optional resource metadata (`dict` or `ResourceMeta`) embedded when writing JSON

**Raises:**
- `ValueError`: If format is unsupported

---

### `qe_input_from_structure(structure: PMGStructure) -> QEInput`

Generates a minimal QE input from a structure.

**Parameters:**
- `structure`: pymatgen Structure object

**Returns:**
- `QEInput`: Minimal QE input with structure cards and default namelists

---

### `ParameterOverride`

Dataclass for parameter overrides.

**Fields:**
- `name: str`: Parameter name
- `value: Any`: Parameter value (auto-coerced)
- `section: Optional[str]`: Optional section hint (e.g., "CONTROL", "SYSTEM")

**Example:**

```python
from quantumvitas.workflow.input_runner import ParameterOverride

override = ParameterOverride(name="ecutwfc", value=60, section="SYSTEM")
```

---

### `run_input_step(...)`

Runs a QE input step with optional parameter overrides.

**Parameters:**
- `engine`: QuantumEspressoEngine instance
- `input_file`: Path to QE input file
- `working_dir`: Working directory for execution
- `project_root`: Project root (for pseudopotentials)
- `step_type`: Optional step type hint
- `timeout`: Optional timeout in seconds
- `parameter_overrides`: Optional list of ParameterOverride objects

**Returns:**
- `tuple[StepResult, PreparedInputStep]`: Execution result and prepared step metadata

---

## Troubleshooting

### Parameter Not Found

If you get an error like "Parameter 'xyz' is not defined", check:

1. The parameter name is correct (case-insensitive)
2. The module supports the parameter (check `qv params <module>`)
3. You've specified the section if needed: `--SECTION.parameter=value`

### Structure Import Fails

If structure import fails:

1. Check the file format is supported
2. For QE inputs, ensure `ATOMIC_POSITIONS` and `CELL_PARAMETERS` cards exist
3. Try specifying format explicitly: `--output-format json`

### Parameter Override Not Applied

If overrides don't seem to work:

1. Check the parameter is valid for the module
2. Verify the section is correct
3. Check the generated input file in the working directory

---

## Best Practices

1. **Use JSON for project storage**: JSON is the canonical format and preserves all structure metadata
2. **Register structures in project**: Use `qv import-structure` to register structures in `project.qv.yml`
3. **Specify sections for ambiguous parameters**: Use `--SECTION.parameter=value` when needed
4. **Use working directories**: Specify `--workdir` to keep outputs organized
5. **Check generated inputs**: Inspect generated `.in` files in the working directory to verify overrides

