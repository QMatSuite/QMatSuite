"""
Mini smoke test: Validate structure loading chain for PySCF.

This test proves the entire chain works:
(Project structure file) -> pymatgen Molecule -> atoms list -> pyscf.gto.Mole builds -> SCF runs.
"""
import json
import pytest
from pathlib import Path
from pymatgen.core import Molecule


def _pyscf_available() -> bool:
    """Check if PySCF is installed with actual functionality.

    CI environments may have a stub pyscf module that passes basic import
    but fails on actual submodules like gto and scf. We check for these
    to ensure PySCF is fully functional.
    """
    try:
        from pyscf import gto, scf
        return True
    except ImportError:
        return False


@pytest.fixture
def h2_molecule_file(tmp_path: Path) -> Path:
    """Create a minimal H2 molecule structure file."""
    structures_dir = tmp_path / "structures"
    structures_dir.mkdir()
    
    # Create H2 molecule using pymatgen Molecule
    mol = Molecule(
        species=["H", "H"],
        coords=[[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]],
        charge=0,
        spin_multiplicity=1,
    )
    
    # Write as pymatgen Molecule dict (includes @module/@class for pymatgen)
    mol_dict = mol.as_dict()
    h2_file = structures_dir / "h2.json"
    h2_file.write_text(json.dumps(mol_dict, indent=2))
    
    return h2_file


@pytest.mark.skipif(
    not _pyscf_available(),
    reason="PySCF not installed - install with: pip install pyscf"
)
def test_structure_loading_chain(h2_molecule_file: Path):
    """
    Test the complete structure loading chain for PySCF.
    
    Steps:
    1. Load structure file using read_structure() (same code path as engine)
    2. Assert it's a pymatgen Molecule with sites
    3. Convert to PySCF atoms list format
    4. Build pyscf.gto.Mole
    5. Run minimal SCF
    """
    from qmatsuite.io.structure_io import read_structure
    from pymatgen.core import Molecule as PMGMolecule
    from pyscf import gto, scf
    
    # Step 1: Load structure using the same code path as engine
    structure = read_structure(h2_molecule_file)
    
    # Step 2: Assert it's a Molecule (not Structure)
    assert isinstance(structure, PMGMolecule), f"Expected Molecule, got {type(structure)}"
    assert len(structure) > 0, "Molecule has no sites"
    assert len(structure) == 2, f"Expected 2 atoms (H2), got {len(structure)}"
    
    # Step 3: Convert to PySCF atoms list format
    # PySCF expects: [[sym, (x, y, z)], ...] or [[sym, x, y, z], ...]
    atoms = []
    for site in structure:
        atoms.append([str(site.species_string), tuple(site.coords)])
    
    assert len(atoms) > 0, "Atoms list is empty"
    assert len(atoms) == 2, f"Expected 2 atoms in list, got {len(atoms)}"
    
    # Verify first atom format
    assert len(atoms[0]) == 2, f"Expected [symbol, (x,y,z)], got {atoms[0]}"
    assert len(atoms[0][1]) == 3, f"Expected 3 coordinates, got {len(atoms[0][1])}"
    
    # Step 4: Build pyscf.gto.Mole
    mol = gto.Mole()
    mol.atom = atoms
    mol.basis = 'sto-3g'
    mol.charge = structure.charge
    mol.spin = structure.spin_multiplicity - 1  # PySCF uses 2S, pymatgen uses 2S+1
    mol.unit = 'Angstrom'
    mol.build()
    
    # Step 5: Run minimal SCF
    mf = scf.RHF(mol)
    energy = mf.kernel()
    
    # Assertions
    assert mf.converged, "SCF did not converge"
    assert isinstance(energy, (int, float)), f"Energy should be numeric, got {type(energy)}"
    assert abs(energy) > 0, "Energy should be non-zero"
    
    print(f"✓ Structure loading chain works: H2 SCF energy = {energy:.6f} Hartree")


@pytest.mark.skipif(
    not _pyscf_available(),
    reason="PySCF not installed - install with: pip install pyscf"
)
def test_atoms_list_conversion_format(h2_molecule_file: Path):
    """
    Test that atoms list conversion produces the correct format for PySCF.
    
    Regression test: ensures atoms list is non-empty and in correct format.
    """
    from qmatsuite.io.structure_io import read_structure
    from pymatgen.core import Molecule as PMGMolecule
    
    structure = read_structure(h2_molecule_file)
    assert isinstance(structure, PMGMolecule)
    
    # Convert to atoms list (same format as PySCFEngine should use)
    atoms = []
    for site in structure:
        atoms.append({
            "element": site.species_string,
            "coords": [float(c) for c in site.coords],
        })
    
    # Assertions
    assert len(atoms) == 2, f"Expected 2 atoms, got {len(atoms)}"
    assert "element" in atoms[0], "Atom dict should have 'element' key"
    assert "coords" in atoms[0], "Atom dict should have 'coords' key"
    assert len(atoms[0]["coords"]) == 3, f"Coordinates should have 3 elements, got {len(atoms[0]['coords'])}"
    assert atoms[0]["element"] == "H", f"Expected H, got {atoms[0]['element']}"
    
    print(f"✓ Atoms list conversion works: {len(atoms)} atoms, format correct")

