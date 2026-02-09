#!/usr/bin/env python3
"""Generate real VASP DOS fixtures for testing.

This script runs small VASP calculations to produce DOSCAR files:
- Si non-spin TDOS
- Fe spin TDOS  
- TiO2 PDOS with LORBIT=11
"""
import subprocess
import shutil
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).parent.parent
VASP_BIN = REPO_ROOT / ".qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std"
POTCAR_DIR = REPO_ROOT / ".qmatsuite/engines/vasp/potpaw_PBE.64"
OUTPUT_DIR = REPO_ROOT / "tests/data/analysis_vasp_dos"

def create_potcar(species: list[str], output_path: Path):
    """Create POTCAR by concatenating individual POTCARs."""
    potcar_paths = []
    for spec in species:
        potcar_file = POTCAR_DIR / f"{spec}/POTCAR"
        if not potcar_file.exists():
            # Try alternative names
            alternatives = [
                POTCAR_DIR / f"{spec}_pv/POTCAR",
                POTCAR_DIR / f"{spec}_sv/POTCAR",
                POTCAR_DIR / f"{spec}_d/POTCAR",
            ]
            found = False
            for alt in alternatives:
                if alt.exists():
                    potcar_file = alt
                    found = True
                    break
            if not found:
                raise FileNotFoundError(f"POTCAR not found for {spec}")
        potcar_paths.append(potcar_file)
    
    with open(output_path, 'wb') as outfile:
        for potcar in potcar_paths:
            with open(potcar, 'rb') as infile:
                shutil.copyfileobj(infile, outfile)

def run_vasp_dos(work_dir: Path, poscar_content: str, incar_content: str, kpoints_content: str, species: list[str]):
    """Run VASP DOS calculation."""
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Write input files
    (work_dir / "POSCAR").write_text(poscar_content)
    (work_dir / "INCAR").write_text(incar_content)
    (work_dir / "KPOINTS").write_text(kpoints_content)
    create_potcar(species, work_dir / "POTCAR")
    
    # Run VASP
    print(f"Running VASP in {work_dir}...")
    result = subprocess.run(
        [str(VASP_BIN)],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"VASP failed in {work_dir}")
        print(f"STDOUT: {result.stdout[-500:]}")
        print(f"STDERR: {result.stderr[-500:]}")
        return False
    
    return True

def main():
    """Generate all DOS fixtures."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = REPO_ROOT / ".tmp" / "vasp_dos_fixtures"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Si non-spin TDOS
    print("Generating Si DOSCAR...")
    si_dir = tmp_dir / "si"
    si_poscar = """Si
1.0
5.4309 0.0 0.0
0.0 5.4309 0.0
0.0 0.0 5.4309
Si
2
Direct
0.000000 0.000000 0.000000
0.250000 0.250000 0.250000
"""
    si_incar = """SYSTEM = Si DOS
ENCUT = 300
ISMEAR = -5
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 2
LWAVE = .FALSE.
LCHARG = .FALSE.
NEDOS = 301
"""
    si_kpoints = """Automatic mesh
0
Monkhorst-Pack
8 8 8
0 0 0
"""
    if run_vasp_dos(si_dir, si_poscar, si_incar, si_kpoints, ["Si"]):
        shutil.copy2(si_dir / "DOSCAR", OUTPUT_DIR / "DOSCAR")
        if (si_dir / "vasprun.xml").exists():
            shutil.copy2(si_dir / "vasprun.xml", OUTPUT_DIR / "vasprun.xml")
    
    # 2. Fe spin TDOS
    print("Generating Fe spin DOSCAR...")
    fe_dir = tmp_dir / "fe"
    fe_poscar = """Fe
1.0
2.87 0.0 0.0
0.0 2.87 0.0
0.0 0.0 2.87
Fe
1
Direct
0.000000 0.000000 0.000000
"""
    fe_incar = """SYSTEM = Fe DOS
ENCUT = 300
ISMEAR = 0
SIGMA = 0.2
IBRION = -1
NSW = 0
ICHARG = 2
ISPIN = 2
MAGMOM = 2.0
LWAVE = .FALSE.
LCHARG = .FALSE.
NEDOS = 301
"""
    fe_kpoints = """Automatic mesh
0
Monkhorst-Pack
8 8 8
0 0 0
"""
    if run_vasp_dos(fe_dir, fe_poscar, fe_incar, fe_kpoints, ["Fe"]):
        shutil.copy2(fe_dir / "DOSCAR", OUTPUT_DIR / "DOSCAR_spin")
    
    # 3. TiO2 PDOS with LORBIT=11
    print("Generating TiO2 PDOS DOSCAR...")
    tio2_dir = tmp_dir / "tio2"
    tio2_poscar = """TiO2 rutile
1.0
4.5937 0.0 0.0
0.0 4.5937 0.0
0.0 0.0 2.9587
Ti O
2 4
Direct
0.000000 0.000000 0.000000
0.500000 0.500000 0.500000
0.305300 0.305300 0.000000
0.694700 0.694700 0.000000
0.194700 0.805300 0.500000
0.805300 0.194700 0.500000
"""
    tio2_incar = """SYSTEM = TiO2 DOS
ENCUT = 400
ISMEAR = -5
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 2
LWAVE = .FALSE.
LCHARG = .FALSE.
LORBIT = 11
NEDOS = 301
"""
    tio2_kpoints = """Automatic mesh
0
Monkhorst-Pack
6 6 6
0 0 0
"""
    if run_vasp_dos(tio2_dir, tio2_poscar, tio2_incar, tio2_kpoints, ["Ti", "O"]):
        shutil.copy2(tio2_dir / "DOSCAR", OUTPUT_DIR / "DOSCAR_pdos")
    
    # Create README
    readme = """# VASP DOS Test Fixtures

Generated from real VASP calculations.

## Files

- `DOSCAR`: Si non-spin total DOS (NEDOS=301)
- `DOSCAR_spin`: Fe spin-polarized DOS (ISPIN=2, NEDOS=301)
- `DOSCAR_pdos`: TiO2 with LORBIT=11 for full lm PDOS (NEDOS=301)
- `vasprun.xml`: Minimal vasprun.xml from Si calculation (for efermi)

## INCAR Key Settings

### Si (DOSCAR)
- ISMEAR = -5 (tetrahedron)
- NEDOS = 301
- Non-spin (default)

### Fe (DOSCAR_spin)
- ISMEAR = 0 (Gaussian)
- ISPIN = 2
- MAGMOM = 2.0
- NEDOS = 301

### TiO2 (DOSCAR_pdos)
- ISMEAR = -5
- LORBIT = 11 (full lm decomposition)
- NEDOS = 301
"""
    (OUTPUT_DIR / "README.md").write_text(readme)
    
    print(f"\nFixtures generated in {OUTPUT_DIR}")
    print("Files created:")
    for f in OUTPUT_DIR.glob("*"):
        if f.is_file():
            print(f"  - {f.name}")

if __name__ == "__main__":
    main()

