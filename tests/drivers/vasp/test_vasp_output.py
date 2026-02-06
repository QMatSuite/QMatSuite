"""Tests for VASP output parser (vasprun.xml + OUTCAR).

Uses synthetic minimal fixtures — no real VASP outputs needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.vasp.parsers.output import VASPDigest, VASPOutputParser


# ──────────────────────────────────────────────────────────────────────────
# Synthetic vasprun.xml fixture
# ──────────────────────────────────────────────────────────────────────────

MINIMAL_VASPRUN_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<modeling>
 <generator>
  <i name="totaltime">    42.000</i>
 </generator>
 <parameters>
  <separator name="electronic">
   <i name="NELM">60</i>
  </separator>
  <separator name="ionic">
   <i name="NSW">0</i>
  </separator>
 </parameters>
 <atominfo>
  <atoms>2</atoms>
  <array name="atoms">
   <set>
    <rc><c>Si</c><c>1</c></rc>
    <rc><c>Si</c><c>1</c></rc>
   </set>
  </array>
 </atominfo>
 <structure name="initialpos">
  <crystal>
   <varray name="basis">
    <v>5.43090000 0.00000000 0.00000000</v>
    <v>0.00000000 5.43090000 0.00000000</v>
    <v>0.00000000 0.00000000 5.43090000</v>
   </varray>
  </crystal>
  <varray name="positions">
   <v>0.00000000 0.00000000 0.00000000</v>
   <v>0.25000000 0.25000000 0.25000000</v>
  </varray>
 </structure>
 <calculation>
  <scstep><energy><i name="e_fr_energy">-10.500</i></energy></scstep>
  <scstep><energy><i name="e_fr_energy">-10.800</i></energy></scstep>
  <scstep><energy><i name="e_fr_energy">-10.850</i></energy></scstep>
  <energy>
   <i name="e_fr_energy">  -10.85000000</i>
   <i name="e_0_energy">   -10.85000000</i>
  </energy>
  <varray name="forces">
   <v>  0.00100000  0.00200000  0.00300000</v>
   <v> -0.00100000 -0.00200000 -0.00300000</v>
  </varray>
 </calculation>
 <structure name="finalpos">
  <crystal>
   <varray name="basis">
    <v>5.43090000 0.00000000 0.00000000</v>
    <v>0.00000000 5.43090000 0.00000000</v>
    <v>0.00000000 0.00000000 5.43090000</v>
   </varray>
  </crystal>
  <varray name="positions">
   <v>0.00000000 0.00000000 0.00000000</v>
   <v>0.25000000 0.25000000 0.25000000</v>
  </varray>
 </structure>
</modeling>
"""

MAGNETIC_VASPRUN_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<modeling>
 <parameters>
  <separator name="electronic">
   <i name="NELM">60</i>
  </separator>
  <separator name="ionic">
   <i name="NSW">0</i>
  </separator>
 </parameters>
 <calculation>
  <scstep><energy><i name="e_fr_energy">-8.200</i></energy></scstep>
  <scstep><energy><i name="e_fr_energy">-8.500</i></energy></scstep>
  <energy>
   <i name="e_fr_energy">  -8.50000000</i>
  </energy>
  <separator name="magnetization">
   <i name="total">   2.00000000</i>
  </separator>
 </calculation>
 <structure name="finalpos">
  <crystal>
   <varray name="basis">
    <v>2.87000000 0.00000000 0.00000000</v>
    <v>0.00000000 2.87000000 0.00000000</v>
    <v>0.00000000 0.00000000 2.87000000</v>
   </varray>
  </crystal>
  <varray name="positions">
   <v>0.00000000 0.00000000 0.00000000</v>
   <v>0.50000000 0.50000000 0.50000000</v>
  </varray>
 </structure>
</modeling>
"""

SYNTHETIC_OUTCAR = """\
 running on    4 total cores
 free  energy   TOTEN  =       -10.85000000 eV
 number of electron      8.0000000 magnetization       2.0000000
 external pressure =       -1.23 kB
 Elapsed time (sec):    42.000
"""


@pytest.fixture
def vasprun_dir(tmp_path):
    """Directory with minimal vasprun.xml."""
    (tmp_path / "vasprun.xml").write_text(MINIMAL_VASPRUN_XML)
    return tmp_path


@pytest.fixture
def magnetic_dir(tmp_path):
    """Directory with magnetic vasprun.xml."""
    (tmp_path / "vasprun.xml").write_text(MAGNETIC_VASPRUN_XML)
    return tmp_path


@pytest.fixture
def outcar_dir(tmp_path):
    """Directory with OUTCAR only (no vasprun.xml)."""
    (tmp_path / "OUTCAR").write_text(SYNTHETIC_OUTCAR)
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    """Empty directory (no outputs)."""
    return tmp_path


# ──────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────


class TestVASPDigest:
    """Test VASPDigest dataclass."""

    def test_defaults(self):
        d = VASPDigest()
        assert d.final_energy_eV is None
        assert d.n_atoms == 0
        assert d.converged_electronic is False

    def test_to_dict(self):
        d = VASPDigest(final_energy_eV=-10.85, n_atoms=2)
        result = d.to_dict()
        assert isinstance(result, dict)
        assert result["final_energy_eV"] == -10.85
        assert result["n_atoms"] == 2


class TestVASPOutputParser:
    """Test VASPOutputParser."""

    def test_can_parse_with_vasprun(self, vasprun_dir):
        parser = VASPOutputParser()
        assert parser.can_parse(vasprun_dir) is True

    def test_can_parse_with_outcar(self, outcar_dir):
        parser = VASPOutputParser()
        assert parser.can_parse(outcar_dir) is True

    def test_can_parse_empty(self, empty_dir):
        parser = VASPOutputParser()
        assert parser.can_parse(empty_dir) is False

    def test_parse_vasprun_energy(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.final_energy_eV is not None
        assert abs(digest.final_energy_eV - (-10.85)) < 1e-6

    def test_parse_vasprun_energy_per_atom(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.energy_per_atom_eV is not None
        assert abs(digest.energy_per_atom_eV - (-10.85 / 2)) < 1e-6

    def test_parse_vasprun_structure(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.final_lattice is not None
        assert len(digest.final_lattice) == 3
        assert abs(digest.final_lattice[0][0] - 5.4309) < 1e-4
        assert digest.final_frac_coords is not None
        assert len(digest.final_frac_coords) == 2
        assert digest.n_atoms == 2

    def test_parse_vasprun_convergence(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        # 3 electronic steps < NELM=60 → converged
        assert digest.converged_electronic is True
        # NSW=0 → SCF only → ionic = electronic
        assert digest.converged_ionic is True
        assert digest.n_ionic_steps == 1
        assert digest.n_electronic_steps == 3

    def test_parse_vasprun_forces(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.max_force_eV_A is not None
        # Force magnitude: sqrt(0.001^2 + 0.002^2 + 0.003^2) ≈ 0.00374
        assert digest.max_force_eV_A > 0.003
        assert digest.max_force_eV_A < 0.004

    def test_parse_vasprun_volume(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.volume_A3 is not None
        # 5.4309^3 ≈ 160.2
        assert abs(digest.volume_A3 - 5.4309**3) < 0.1

    def test_parse_vasprun_elapsed(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        assert digest.elapsed_time_s is not None
        assert abs(digest.elapsed_time_s - 42.0) < 0.01

    def test_parse_vasprun_magnetization(self, magnetic_dir):
        parser = VASPOutputParser()
        digest = parser.parse(magnetic_dir)
        assert digest.total_magnetization is not None
        assert abs(digest.total_magnetization - 2.0) < 1e-6

    def test_outcar_fallback_energy(self, outcar_dir):
        parser = VASPOutputParser()
        digest = parser.parse(outcar_dir)
        assert digest.final_energy_eV is not None
        assert abs(digest.final_energy_eV - (-10.85)) < 1e-6

    def test_outcar_fallback_magnetization(self, outcar_dir):
        parser = VASPOutputParser()
        digest = parser.parse(outcar_dir)
        assert digest.total_magnetization is not None
        assert abs(digest.total_magnetization - 2.0) < 1e-6

    def test_outcar_fallback_pressure(self, outcar_dir):
        parser = VASPOutputParser()
        digest = parser.parse(outcar_dir)
        assert digest.pressure_kBar is not None
        assert abs(digest.pressure_kBar - (-1.23)) < 1e-4

    def test_outcar_fallback_elapsed(self, outcar_dir):
        parser = VASPOutputParser()
        digest = parser.parse(outcar_dir)
        assert digest.elapsed_time_s is not None
        assert abs(digest.elapsed_time_s - 42.0) < 0.01

    def test_parse_empty_returns_defaults(self, empty_dir):
        parser = VASPOutputParser()
        digest = parser.parse(empty_dir)
        assert digest.final_energy_eV is None
        assert digest.n_atoms == 0

    def test_parser_registry_lookup(self):
        """VASPOutputParser is registered and findable."""
        from quantumvitas.parsers.registry import get_parser
        cls = get_parser("vasp", "scf_digest")
        assert cls is VASPOutputParser

    def test_digest_to_dict_roundtrip(self, vasprun_dir):
        parser = VASPOutputParser()
        digest = parser.parse(vasprun_dir)
        d = digest.to_dict()
        assert isinstance(d, dict)
        assert d["final_energy_eV"] == digest.final_energy_eV
        assert d["n_atoms"] == digest.n_atoms
        assert d["converged_electronic"] == digest.converged_electronic
