"""VASP DOS analysis provider."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import xml.etree.ElementTree as ET

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.dos import DOS
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.vasp.io.poscar import parse_poscar_text
from qmatsuite.parsers.registry import register_parser


def _read_fermi_from_vasprun(path: Path) -> Optional[float]:
    """Read Fermi energy from vasprun.xml."""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    node = root.find(".//i[@name='efermi']")
    if node is None or node.text is None:
        return None
    try:
        return float(node.text.strip())
    except ValueError:
        return None


def _parse_doscar(doscar_path: Path) -> dict:
    """Parse DOSCAR file.

    Returns dict with:
    - nedos: int
    - efermi: float | None
    - energies: np.ndarray (nedos,)
    - total_dos: np.ndarray (nedos,) or (2, nedos)
    - integrated_dos: np.ndarray | None (nedos,)
    - pdos: np.ndarray | None (n_atoms, nedos, n_orbitals)
    - atom_labels: list[str] | None
    - orbital_labels: list[str] | None
    - spin_polarized: bool
    """
    if not doscar_path.exists():
        raise FileNotFoundError(f"DOSCAR not found: {doscar_path}")

    lines = doscar_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 7:
        raise ValueError(f"DOSCAR too short: {doscar_path}")

    # Parse header line 6: EMAX EMIN NEDOS EFERMI ???
    header_parts = lines[5].split()
    if len(header_parts) < 4:
        raise ValueError(f"Invalid DOSCAR header: {lines[5]!r}")

    try:
        nedos = int(float(header_parts[2]))
        efermi = float(header_parts[3])
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse DOSCAR header: {e}") from e

    # Parse total DOS block (lines 6 to 6+nedos-1)
    total_dos_data: list[list[float]] = []
    for i in range(6, 6 + nedos):
        if i >= len(lines):
            raise ValueError(f"DOSCAR truncated: expected {nedos} DOS lines, got {i - 6}")
        parts = lines[i].split()
        if len(parts) < 3:
            raise ValueError(f"Invalid DOS line {i}: {lines[i]!r}")
        try:
            row = [float(x) for x in parts]
            total_dos_data.append(row)
        except ValueError as e:
            raise ValueError(f"Failed to parse DOS line {i}: {e}") from e

    # Auto-detect spin from column count
    n_cols = len(total_dos_data[0])
    spin_polarized = n_cols >= 5

    energies = np.array([row[0] for row in total_dos_data], dtype=float)

    if spin_polarized:
        # Spin-polarized: energy, dos_up, dos_down, int_up, int_down
        total_dos = np.array(
            [[row[1], row[2]] for row in total_dos_data],
            dtype=float,
        ).T  # shape (2, nedos)
        integrated_dos = np.array([row[3] + row[4] for row in total_dos_data], dtype=float)
    else:
        # Non-spin: energy, dos, integrated_dos
        total_dos = np.array([row[1] for row in total_dos_data], dtype=float)  # shape (nedos,)
        integrated_dos = np.array([row[2] for row in total_dos_data], dtype=float)

    # Check if PDOS data follows
    pdos = None
    atom_labels = None
    orbital_labels = None

    next_line_idx = 6 + nedos
    if next_line_idx < len(lines) and lines[next_line_idx].strip():
        # PDOS data present - each atom block has:
        #   1 header line (same format as total DOS header: emax emin nedos efermi ...)
        #   nedos data lines (energy + orbital projections)
        pdos_blocks: list[list[list[float]]] = []
        current_idx = next_line_idx

        while current_idx < len(lines):
            # Skip blank lines
            while current_idx < len(lines) and not lines[current_idx].strip():
                current_idx += 1
            if current_idx >= len(lines):
                break

            # Per-atom header line (5 fields: emax, emin, nedos, efermi, weight)
            header_parts = lines[current_idx].split()
            if len(header_parts) >= 4:
                try:
                    block_nedos = int(float(header_parts[2]))
                except (ValueError, IndexError):
                    break
                if block_nedos != nedos:
                    break
                current_idx += 1  # skip header
            else:
                break

            # Read nedos data lines for this atom
            atom_data: list[list[float]] = []
            for _ in range(nedos):
                if current_idx >= len(lines):
                    break
                parts = lines[current_idx].split()
                if len(parts) >= 2:
                    try:
                        atom_data.append([float(x) for x in parts])
                    except ValueError:
                        break
                current_idx += 1
            if len(atom_data) == nedos:
                pdos_blocks.append(atom_data)
            else:
                break

        if pdos_blocks:
            # Determine orbital count from first atom's first line
            n_orbitals = len(pdos_blocks[0][0]) - 1  # minus energy column
            pdos_array = np.zeros((len(pdos_blocks), nedos, n_orbitals), dtype=float)
            for atom_idx, atom_data in enumerate(pdos_blocks):
                for energy_idx, row in enumerate(atom_data):
                    # Skip energy (first column), take orbitals
                    pdos_array[atom_idx, energy_idx, :] = row[1 : 1 + n_orbitals]

            pdos = pdos_array

            # Generate orbital labels based on count
            # LORBIT=10: s, p, d (3 orbitals)
            # LORBIT=11: s, py, pz, px, dxy, dyz, dz2, dxz, dx2-y2 (9 orbitals)
            if n_orbitals == 3:
                orbital_labels = ["s", "p", "d"]
            elif n_orbitals == 9:
                orbital_labels = ["s", "py", "pz", "px", "dxy", "dyz", "dz2", "dxz", "dx2-y2"]
            else:
                orbital_labels = [f"orb_{i}" for i in range(n_orbitals)]

            # Atom labels: generic for now (enriched by POSCAR in provider)
            atom_labels = [f"atom_{i+1}" for i in range(len(pdos_blocks))]

    return {
        "nedos": nedos,
        "efermi": efermi,
        "energies": energies,
        "total_dos": total_dos,
        "integrated_dos": integrated_dos,
        "pdos": pdos,
        "atom_labels": atom_labels,
        "orbital_labels": orbital_labels,
        "spin_polarized": spin_polarized,
    }


@register_parser("vasp", "dos")
class VASPDOSProvider:
    """VASP DOS analysis provider."""

    engine = "vasp"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "DOSCAR").exists()

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse DOSCAR and return DOS object."""
        doscar_path = evidence.primary_raw_dir / "DOSCAR"
        if not doscar_path.exists():
            raise FileNotFoundError(f"DOSCAR not found: {doscar_path}")

        parsed = _parse_doscar(doscar_path)

        # Enrich PDOS atom labels from POSCAR species (py4vasp convention)
        if parsed["atom_labels"] and parsed["pdos"] is not None:
            poscar_path = evidence.primary_raw_dir / "POSCAR"
            if poscar_path.exists():
                try:
                    structure = parse_poscar_text(
                        poscar_path.read_text(encoding="utf-8", errors="replace")
                    )
                    species: List[str] = structure["species"]
                    if len(species) == len(parsed["atom_labels"]):
                        counts: Dict[str, int] = {}
                        labels: List[str] = []
                        for sp in species:
                            counts[sp] = counts.get(sp, 0) + 1
                            labels.append(f"{sp}_{counts[sp]}")
                        parsed["atom_labels"] = labels
                except (ValueError, KeyError):
                    pass  # keep generic atom_1, atom_2, ... labels

        # Try to get Fermi energy from vasprun.xml if not in DOSCAR
        fermi_energy = parsed["efermi"]
        if fermi_energy is None:
            vasprun_path = evidence.primary_raw_dir / "vasprun.xml"
            fermi_energy = _read_fermi_from_vasprun(vasprun_path)

        source_files = [SourceFileStat.from_path(doscar_path, evidence.calc_dir)]
        vasprun_path = evidence.primary_raw_dir / "vasprun.xml"
        if vasprun_path.exists():
            source_files.append(SourceFileStat.from_path(vasprun_path, evidence.calc_dir))

        warnings: list[str] = []
        if fermi_energy is None:
            warnings.append("No Fermi energy found in DOSCAR or vasprun.xml.")

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="vasp_dos",
            parser_version="1.0",
            warnings=warnings,
        )

        return DOS(
            meta=meta,
            energies=parsed["energies"],
            total_dos=parsed["total_dos"],
            fermi_energy=fermi_energy,
            integrated_dos=parsed["integrated_dos"],
            pdos=parsed["pdos"],
            atom_labels=parsed["atom_labels"],
            orbital_labels=parsed["orbital_labels"],
            spin_polarized=parsed["spin_polarized"],
        )

