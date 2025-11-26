# QE Module Support

## Overview

QuantumVITAS now supports multiple Quantum ESPRESSO modules, each with their own input format. The parser automatically detects the module type from the namelist names in the input file.

## Supported Modules

### pw.x (Main DFT Code)
- **Namelists**: `&CONTROL`, `&system`, `&ELECTRONS`, `&IONS`, `&CELL`
- **Cards**: `ATOMIC_SPECIES`, `ATOMIC_POSITIONS`, `K_POINTS`, `CELL_PARAMETERS`, etc.
- **Use cases**: SCF, NSCF, structural optimization, molecular dynamics
- **Documentation**: [INPUT_PW.html](https://www.quantum-espresso.org/Doc/INPUT_PW.html)

### ph.x (Phonon Calculations)
- **Namelist**: `&inputph`
- **Use cases**: Phonon frequencies, dielectric constants, Raman spectra
- **Example**: `temp/downloads/qe_tutorial_examples/9_Si_phonon/1_gamma_point/si.2_ph.in` (auto-downloaded from [GitHub](https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects))

### gipaw.x (NMR/EPR Calculations)
- **Namelist**: `&inputgipaw`
- **Use cases**: Nuclear magnetic resonance, electron paramagnetic resonance
- **Example**: `temp/downloads/qe_tutorial_examples/12_NMR_gipaw/2_benzene/benzene.2_gipaw.in` (auto-downloaded from [GitHub](https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects))

### pp.x (Post-Processing)
- **Namelist**: `&inputpp`
- **Use cases**: Charge density analysis, wavefunction processing

### neb.x (Nudged Elastic Band)
- **Namelist**: `&PATH`
- **Use cases**: Transition state calculations, reaction pathways
- **Note**: Often contains embedded pw.x input

### bands.x, dos.x, projwfc.x
- **Namelists**: Similar to pw.x (`&CONTROL`, `&system`, `&ELECTRONS`)
- **Additional namelists**: Module-specific (e.g., `&bands`, `&DOS`, `&projwfc`)

## Module Detection

The parser automatically detects the module type by examining namelist names:

```python
from quantumvitas.io import QEInputParser, QEModule

qe_input = QEInputParser.parse_file("input.in")
print(qe_input.module)  # QEModule.PH, QEModule.GIPAW, etc.
```

### Detection Logic

1. **ph.x**: Detected by presence of `&inputph` namelist
2. **gipaw.x**: Detected by presence of `&inputgipaw` namelist
3. **pp.x**: Detected by presence of `&inputpp` namelist
4. **neb.x**: Detected by presence of `&PATH` namelist
5. **pw.x**: Default for files with `&CONTROL`, `&system`, `&ELECTRONS`
6. **bands.x, dos.x, projwfc.x**: Detected by calculation type or additional namelists

## Usage Examples

### Parse ph.x Input

```python
from quantumvitas.io import QEInputParser

qe_input = QEInputParser.parse_file("si.2_ph.in")
assert qe_input.module == QEModule.PH

inputph = qe_input.get_namelist('inputph')
print(f"Prefix: {inputph.get('prefix')}")
print(f"Outdir: {inputph.get('outdir')}")
```

### Generate gipaw.x Input

```python
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig

engine = QuantumEspressoEngine(EngineConfig(name="qe"))

input_data = {
    'namelists': {
        'inputgipaw': {
            'job': 'nmr',
            'prefix': 'benzene',
            'tmp_dir': './outdir/',
            'restart_mode': 'from_scratch'
        }
    }
}

input_file = engine.generate_input(
    step_type='gipaw',
    input_data=input_data,
    working_dir=Path('.')
)
```

### Detect Module from File

```python
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig

engine = QuantumEspressoEngine(EngineConfig(name="qe"))
module = engine.detect_module_from_input(Path("input.in"))
print(f"Detected module: {module}")
```

## Command Line Flags

Different QE modules use different command-line flags:

- **pw.x, bands.x, dos.x, etc.**: Use `-inp` flag
- **ph.x, pp.x, gipaw.x**: Use `-i` flag

The engine automatically selects the correct flag based on the step type.

## References

- [Quantum ESPRESSO Documentation](https://www.quantum-espresso.org/documentation/)
- [pw.x Input Documentation](https://www.quantum-espresso.org/Doc/INPUT_PW.html)
- [ph.x Input Documentation](https://www.quantum-espresso.org/Doc/INPUT_PH.html)

