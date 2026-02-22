"""
Integration tests for GPAW execution.

These tests run actual GPAW calculations and verify results.
Tests are skipped if GPAW is not installed.

To run these tests:
    pip install gpaw
    pytest tests/integration/test_gpaw_execution.py -v
"""

import json
import subprocess
import sys
import textwrap

import pytest

from qmatsuite.core.engines.discovery import is_engine_available

pytestmark = pytest.mark.skipif(
    not is_engine_available("gpaw"),
    reason="GPAW not installed - install with: pip install gpaw"
)


class TestGPAWSCF:
    """Integration tests for GPAW SCF calculations."""

    def test_si_scf_pw_mode(self, tmp_path):
        """Run Si bulk SCF with PW mode and verify energy."""
        script = textwrap.dedent("""\
            import json
            from ase.build import bulk
            from gpaw import GPAW, PW, FermiDirac

            si = bulk('Si', 'diamond', a=5.43)

            calc = GPAW(
                mode=PW(300),
                xc='PBE',
                kpts=(4, 4, 4),
                convergence={'energy': 0.0005, 'density': 1e-4, 'eigenstates': 4e-8},
                occupations=FermiDirac(0.1),
                nbands=-4,
                maxiter=100,
                txt='scf.txt',
                symmetry={'point_group': False},
            )

            si.calc = calc
            energy = si.get_potential_energy()
            fermi = calc.get_fermi_level()

            results = {
                'total_energy_eV': energy,
                'fermi_level_eV': fermi,
                'n_bands': calc.get_number_of_bands(),
                'n_spins': calc.get_number_of_spins(),
                'n_irreducible_kpoints': len(calc.get_ibz_k_points()),
            }

            with open('results.json', 'w') as f:
                json.dump(results, f, indent=2)
        """)

        script_path = tmp_path / "scf.py"
        script_path.write_text(script)

        result = subprocess.run(
            [sys.executable, "scf.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, (
            f"GPAW SCF failed (exit {result.returncode}):\n{result.stderr[:1000]}"
        )

        results_file = tmp_path / "results.json"
        assert results_file.exists(), "results.json not created"

        results = json.loads(results_file.read_text())

        # Golden ref: -10.787 eV (PW 300, 4x4x4, PBE)
        energy = results["total_energy_eV"]
        assert -12.0 < energy < -9.0, f"Energy {energy} eV outside expected range"

        assert results["n_bands"] == 8
        assert results["n_spins"] == 1
        assert results["n_irreducible_kpoints"] > 0

        # Verify Fermi level is reasonable for Si
        fermi = results["fermi_level_eV"]
        assert 3.0 < fermi < 8.0, f"Fermi level {fermi} eV outside expected range"

    def test_scf_output_files(self, tmp_path):
        """Verify SCF output files are created."""
        script = textwrap.dedent("""\
            import json
            from ase.build import bulk
            from gpaw import GPAW, PW, FermiDirac

            si = bulk('Si', 'diamond', a=5.43)
            calc = GPAW(
                mode=PW(300),
                xc='PBE',
                kpts=(2, 2, 2),
                occupations=FermiDirac(0.1),
                maxiter=100,
                txt='scf.txt',
                symmetry={'point_group': False},
            )
            si.calc = calc
            energy = si.get_potential_energy()
            calc.write('scf.gpw')

            with open('results.json', 'w') as f:
                json.dump({'total_energy_eV': energy}, f)
        """)

        script_path = tmp_path / "scf.py"
        script_path.write_text(script)

        result = subprocess.run(
            [sys.executable, "scf.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Failed:\n{result.stderr[:500]}"

        # Check all expected output files
        assert (tmp_path / "scf.txt").exists(), "scf.txt log not created"
        assert (tmp_path / "scf.gpw").exists(), "scf.gpw restart not created"
        assert (tmp_path / "results.json").exists(), "results.json not created"


class TestGPAWBands:
    """Integration tests for GPAW SCF -> band structure chain."""

    def test_si_scf_bands_chain(self, tmp_path):
        """Run Si SCF -> bands (fixed_density) and verify band structure."""
        script = textwrap.dedent("""\
            import json
            import numpy as np
            from ase.build import bulk
            from gpaw import GPAW, PW, FermiDirac

            # Step 1: Ground state SCF
            si = bulk('Si', 'diamond', a=5.43)
            calc_gs = GPAW(
                mode=PW(300),
                xc='PBE',
                kpts=(4, 4, 4),
                convergence={'energy': 0.0005, 'density': 1e-4, 'eigenstates': 4e-8},
                occupations=FermiDirac(0.1),
                nbands=-4,
                maxiter=100,
                txt='gs.txt',
                symmetry={'point_group': False},
            )
            si.calc = calc_gs
            energy = si.get_potential_energy()
            fermi = calc_gs.get_fermi_level()
            calc_gs.write('gs.gpw')

            # Step 2: Band structure (fixed density)
            calc_bs = GPAW('gs.gpw').fixed_density(
                nbands=16,
                symmetry='off',
                kpts={'path': 'GXWK', 'npoints': 40},
                convergence={'bands': 8},
                txt='bands.txt',
            )

            bs = calc_bs.band_structure()
            bs.write('bandstructure.json')

            energies = bs.energies
            reference = bs.reference

            results = {
                'scf_energy_eV': energy,
                'fermi_eV': fermi,
                'bands_shape': list(energies.shape),
                'reference_eV': reference,
                'n_kpts_path': energies.shape[1],
                'n_bands': energies.shape[2],
            }

            with open('results.json', 'w') as f:
                json.dump(results, f, indent=2)
        """)

        script_path = tmp_path / "bands.py"
        script_path.write_text(script)

        result = subprocess.run(
            [sys.executable, "bands.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=600,
        )

        assert result.returncode == 0, (
            f"GPAW bands failed (exit {result.returncode}):\n{result.stderr[:1000]}"
        )

        results = json.loads((tmp_path / "results.json").read_text())

        # Verify SCF energy is reasonable
        assert -12.0 < results["scf_energy_eV"] < -9.0

        # Verify band structure output
        assert (tmp_path / "bandstructure.json").exists()
        assert results["n_bands"] == 16
        assert results["n_kpts_path"] > 0

        # Reference energy should be near Fermi level
        assert abs(results["reference_eV"] - results["fermi_eV"]) < 0.5


class TestGPAWRelax:
    """Integration tests for GPAW geometry relaxation."""

    def test_h2o_relax_fd_mode(self, tmp_path):
        """Run H2O molecule relaxation with FD mode."""
        script = textwrap.dedent("""\
            import json
            import numpy as np
            from ase import Atoms
            from ase.optimize import BFGS
            from gpaw import GPAW

            # H2O with slightly wrong geometry
            h2o = Atoms('H2O',
                        positions=[
                            [0.0, 0.0, 0.0],
                            [0.96, 0.0, 0.0],
                            [-0.24, 0.93, 0.0],
                        ])
            h2o.center(vacuum=4.0)

            calc = GPAW(
                mode='fd',
                h=0.25,
                xc='PBE',
                convergence={'energy': 0.0005, 'density': 1e-4},
                maxiter=100,
                txt='relax.txt',
            )

            h2o.calc = calc

            opt = BFGS(h2o, logfile='opt.log')
            opt.run(fmax=0.05)

            energy = h2o.get_potential_energy()
            forces = h2o.get_forces()
            positions = h2o.get_positions()

            # Bond lengths
            d_OH1 = np.linalg.norm(positions[1] - positions[0])
            d_OH2 = np.linalg.norm(positions[2] - positions[0])

            results = {
                'total_energy_eV': energy,
                'max_force_eV_per_ang': float(np.max(np.abs(forces))),
                'n_opt_steps': opt.nsteps,
                'oh_bond_1_ang': float(d_OH1),
                'oh_bond_2_ang': float(d_OH2),
                'symbols': list(h2o.get_chemical_symbols()),
                'converged': True,
            }

            with open('results.json', 'w') as f:
                json.dump(results, f, indent=2)
        """)

        script_path = tmp_path / "relax.py"
        script_path.write_text(script)

        result = subprocess.run(
            [sys.executable, "relax.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=600,
        )

        assert result.returncode == 0, (
            f"GPAW relax failed (exit {result.returncode}):\n{result.stderr[:1000]}"
        )

        results = json.loads((tmp_path / "results.json").read_text())

        # Golden ref: -14.948 eV
        energy = results["total_energy_eV"]
        assert -17.0 < energy < -12.0, f"Energy {energy} eV outside expected range"

        # Forces should be below convergence criterion
        assert results["max_force_eV_per_ang"] < 0.06  # fmax=0.05 + tolerance

        # Optimization should have converged in reasonable steps
        assert results["n_opt_steps"] > 0
        assert results["n_opt_steps"] < 100

        # Verify atoms are correct
        assert results["symbols"] == ["H", "H", "O"]

        # OH bond lengths should be reasonable (0.8 - 1.8 Angstrom)
        assert 0.8 < results["oh_bond_1_ang"] < 1.8
        assert 0.8 < results["oh_bond_2_ang"] < 1.8


class TestGPAWEngineProbe:
    """Test the GPAW engine adapter."""

    def test_engine_probe(self):
        """Test GpawEngine.probe() returns available=True."""
        from qmatsuite.engine.gpaw_engine import GpawEngine

        engine = GpawEngine()
        probe = engine.probe()

        assert probe["available"] is True
        assert probe["version"] is not None
        assert "." in probe["version"]  # Version string like "25.7.0"

    def test_driver_registry_lookup(self):
        """Verify GPAW driver is accessible via DriverRegistry."""
        import qmatsuite.drivers.gpaw  # noqa: F401 — triggers registration
        from qmatsuite.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("gpaw")
        assert driver is not None
        assert driver.PREFIX == "gpaw"
        assert driver.engine_family == "gpaw"
