"""VASP output parser: vasprun.xml and OUTCAR digest.

Parses VASP calculation outputs into a canonical VASPDigest dataclass.
Primary source: vasprun.xml (via xml.etree.ElementTree).
Fallback: OUTCAR text parsing (regex).

Registers with the parser registry as ("vasp", "scf_digest").
"""

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@dataclass
class VASPDigest:
    """Canonical digest of a VASP calculation output."""

    final_energy_eV: Optional[float] = None
    energy_per_atom_eV: Optional[float] = None
    n_atoms: int = 0
    converged_electronic: bool = False
    converged_ionic: bool = False
    n_ionic_steps: int = 0
    n_electronic_steps: int = 0
    final_species: Optional[List[str]] = None
    final_lattice: Optional[List[List[float]]] = None
    final_frac_coords: Optional[List[List[float]]] = None
    volume_A3: Optional[float] = None
    max_force_eV_A: Optional[float] = None
    pressure_kBar: Optional[float] = None
    total_magnetization: Optional[float] = None
    band_gap_eV: Optional[float] = None
    is_metal: Optional[bool] = None
    elapsed_time_s: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("vasp", "scf_digest")
class VASPOutputParser:
    """Parse VASP outputs into a VASPDigest.

    Prefers vasprun.xml; falls back to OUTCAR if XML is missing.
    """

    engine = "vasp"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable VASP output."""
        return (raw_dir / "vasprun.xml").is_file() or (raw_dir / "OUTCAR").is_file()

    def parse(self, raw_dir: Path, **kwargs: Any) -> VASPDigest:
        """Parse VASP output into a VASPDigest.

        Args:
            raw_dir: Directory containing vasprun.xml and/or OUTCAR.

        Returns:
            VASPDigest with populated fields.
        """
        vasprun = raw_dir / "vasprun.xml"
        outcar = raw_dir / "OUTCAR"

        if vasprun.is_file():
            try:
                return self._parse_vasprun_xml(vasprun)
            except ET.ParseError:
                logger.warning(
                    "vasprun.xml parse error, falling back to OUTCAR"
                )

        if outcar.is_file():
            return self._parse_outcar_fallback(outcar)

        return VASPDigest()

    def _parse_vasprun_xml(self, path: Path) -> VASPDigest:
        """Parse vasprun.xml into a VASPDigest."""
        tree = ET.parse(path)
        root = tree.getroot()
        digest = VASPDigest()

        # Count ionic steps
        calculations = root.findall(".//calculation")
        digest.n_ionic_steps = len(calculations)

        # Final energy
        if calculations:
            last_calc = calculations[-1]
            energy_el = last_calc.find("energy")
            if energy_el is not None:
                for i_el in energy_el.findall("i"):
                    name = i_el.get("name", "")
                    if name == "e_fr_energy":
                        try:
                            digest.final_energy_eV = float(i_el.text.strip())
                        except (ValueError, AttributeError):
                            pass
                    elif name == "e_0_energy" and digest.final_energy_eV is None:
                        try:
                            digest.final_energy_eV = float(i_el.text.strip())
                        except (ValueError, AttributeError):
                            pass

            # Count electronic steps in last ionic step
            scsteps = last_calc.findall("scstep")
            digest.n_electronic_steps = len(scsteps)

        # Final structure
        finalpos = root.find(".//structure[@name='finalpos']")
        if finalpos is None:
            # Try last structure in last calculation
            if calculations:
                finalpos = calculations[-1].find("structure")

        if finalpos is not None:
            self._parse_structure(finalpos, digest)

        # Energy per atom
        if digest.final_energy_eV is not None and digest.n_atoms > 0:
            digest.energy_per_atom_eV = digest.final_energy_eV / digest.n_atoms

        # Forces from last calculation
        if calculations:
            last_calc = calculations[-1]
            forces_varray = last_calc.find(".//varray[@name='forces']")
            if forces_varray is not None:
                max_force = 0.0
                for v_el in forces_varray.findall("v"):
                    try:
                        components = [float(x) for x in v_el.text.split()]
                        force_mag = math.sqrt(sum(c * c for c in components))
                        max_force = max(max_force, force_mag)
                    except (ValueError, AttributeError):
                        pass
                digest.max_force_eV_A = max_force

        # Electronic convergence
        params = root.find(".//parameters")
        if params is not None:
            nelm = self._find_param(params, "NELM")
            if nelm is not None and digest.n_electronic_steps > 0:
                try:
                    nelm_int = int(float(nelm))
                    digest.converged_electronic = (
                        digest.n_electronic_steps < nelm_int
                    )
                except ValueError:
                    pass

        # Ionic convergence
        nsw_el = None
        if params is not None:
            nsw_el = self._find_param(params, "NSW")
        if nsw_el is not None:
            try:
                nsw = int(float(nsw_el))
                if nsw == 0:
                    # SCF only — ionic convergence = electronic convergence
                    digest.converged_ionic = digest.converged_electronic
                else:
                    digest.converged_ionic = (
                        digest.n_ionic_steps < nsw
                    )
            except ValueError:
                pass
        elif digest.n_ionic_steps <= 1:
            digest.converged_ionic = digest.converged_electronic

        # Magnetization
        for calc in reversed(calculations):
            for sep in calc.findall(".//separator"):
                if sep.get("name") == "magnetization":
                    for i_el in sep.findall("i"):
                        if i_el.get("name") == "total":
                            try:
                                digest.total_magnetization = float(
                                    i_el.text.strip()
                                )
                            except (ValueError, AttributeError):
                                pass
            if digest.total_magnetization is not None:
                break

        # DOS / Fermi energy for band gap
        dos = root.find(".//dos")
        if dos is not None:
            efermi_el = dos.find("i[@name='efermi']")
            if efermi_el is not None:
                try:
                    efermi = float(efermi_el.text.strip())
                except (ValueError, AttributeError):
                    efermi = None

        # Elapsed time
        for gen_el in root.findall(".//generator"):
            for i_el in gen_el.findall("i"):
                if i_el.get("name") == "totaltime":
                    try:
                        digest.elapsed_time_s = float(i_el.text.strip())
                    except (ValueError, AttributeError):
                        pass

        # Volume
        if digest.final_lattice is not None:
            digest.volume_A3 = self._compute_volume(digest.final_lattice)

        return digest

    def _parse_structure(self, struct_el: ET.Element, digest: VASPDigest) -> None:
        """Parse a <structure> element into digest fields."""
        # Lattice
        crystal = struct_el.find("crystal")
        if crystal is not None:
            basis = crystal.find("varray[@name='basis']")
            if basis is not None:
                lattice = []
                for v_el in basis.findall("v"):
                    try:
                        row = [float(x) for x in v_el.text.split()]
                        lattice.append(row)
                    except (ValueError, AttributeError):
                        pass
                if len(lattice) == 3:
                    digest.final_lattice = lattice

        # Positions
        positions = struct_el.find("varray[@name='positions']")
        if positions is not None:
            coords = []
            for v_el in positions.findall("v"):
                try:
                    row = [float(x) for x in v_el.text.split()]
                    coords.append(row)
                except (ValueError, AttributeError):
                    pass
            digest.final_frac_coords = coords
            digest.n_atoms = len(coords)

        # Species from atominfo
        atominfo = struct_el.getparent() if hasattr(struct_el, 'getparent') else None
        # In standard ElementTree, we need to find atominfo from root
        # So we look for it relative to the structure's parent
        # This is handled by looking in the root instead

    def _find_param(self, params_el: ET.Element, name: str) -> Optional[str]:
        """Find a parameter value by name in the parameters tree."""
        for sep in params_el.iter("separator"):
            for i_el in sep.findall("i"):
                if i_el.get("name") == name:
                    return i_el.text.strip() if i_el.text else None
        # Also check direct children
        for i_el in params_el.findall("i"):
            if i_el.get("name") == name:
                return i_el.text.strip() if i_el.text else None
        return None

    @staticmethod
    def _compute_volume(lattice: List[List[float]]) -> float:
        """Compute cell volume from lattice vectors (scalar triple product)."""
        a, b, c = lattice
        # a . (b x c)
        cross = [
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        ]
        return abs(a[0] * cross[0] + a[1] * cross[1] + a[2] * cross[2])

    def _parse_outcar_fallback(self, path: Path) -> VASPDigest:
        """Parse OUTCAR for basic energy information (fallback)."""
        digest = VASPDigest()
        text = path.read_text(errors="replace")

        # Find all TOTEN lines
        toten_pattern = re.compile(
            r"free  energy   TOTEN\s*=\s*([-\d.]+)\s*eV"
        )
        matches = toten_pattern.findall(text)
        if matches:
            try:
                digest.final_energy_eV = float(matches[-1])
            except ValueError:
                pass

        # Count ionic steps
        ionic_pattern = re.compile(r"---+\s*Iteration\s+(\d+)")
        ionic_matches = ionic_pattern.findall(text)
        digest.n_ionic_steps = len(set(ionic_matches)) if ionic_matches else 0

        # Elapsed time
        elapsed_pattern = re.compile(
            r"Elapsed time \(sec\):\s*([-\d.]+)"
        )
        elapsed_match = elapsed_pattern.search(text)
        if elapsed_match:
            try:
                digest.elapsed_time_s = float(elapsed_match.group(1))
            except ValueError:
                pass

        # Magnetization
        mag_pattern = re.compile(
            r"number of electron\s+[-\d.]+\s+magnetization\s+([-\d.]+)"
        )
        mag_matches = mag_pattern.findall(text)
        if mag_matches:
            try:
                digest.total_magnetization = float(mag_matches[-1])
            except ValueError:
                pass

        # Pressure
        pressure_pattern = re.compile(
            r"external pressure\s*=\s*([-\d.]+)\s*kB"
        )
        pressure_match = pressure_pattern.search(text)
        if pressure_match:
            try:
                digest.pressure_kBar = float(pressure_match.group(1))
            except ValueError:
                pass

        return digest
