# LAMMPS Parser Fixtures

**Generated**: 2026-01-20  
**Purpose**: Regression testing for LAMMPS output parsers  
**LAMMPS Version**: 22 Jul 2025 - Update 2

## Files

| File | Description | Source |
|------|-------------|--------|
| `log_minimize_lj.lammps` | LJ minimize log with thermo output | `units lj`, `minimize` command |
| `log_md_nvt.lammps` | NVT MD log with thermo output | `units metal`, `fix nvt`, `run 100` |
| `dump_minimize.lammpstrj` | Minimize trajectory dump | `dump custom` during minimize |
| `dump_md.lammpstrj` | MD trajectory dump (10 frames) | `dump custom` during MD run |
| `final_minimize.data` | Relaxed structure from minimize | `write_data` after minimize |

## Generation

Fixtures were generated using:
- LAMMPS binary: `/opt/homebrew/opt/lammps/bin/lmp_serial`
- Script: `generate_lammps_fixtures.sh`

## Usage

These fixtures are used by:
- `tests/unit/test_lammps_parser.py` - Parser unit tests
- `tests/integration/test_lammps_*.py` - Integration tests (reference only)

## License

Fixtures are generated outputs from LAMMPS (GPL-2.0), used for testing purposes only.

