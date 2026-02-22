"""VASP trajectory analysis provider (vasprun.xml / XDATCAR parser)."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# OSZICAR ionic line: "   1 F= -.10586221E+02 ..."
_VFLOAT = r"[-+]?\d*\.\d+E[+-]\d+"
_IONIC_RE = re.compile(rf"^\s*(\d+)\s+F=\s*({_VFLOAT})")
_MD_RE = re.compile(rf"^\s*(\d+)\s+T=\s*([-+]?\d*\.?\d+)\s+E=\s*({_VFLOAT})")

# Files larger than this threshold trigger a warning when XDATCAR fallback exists
_SIZE_WARN_THRESHOLD = 100 * 1024 * 1024  # 100 MB


def _parse_varray(elem: ET.Element) -> np.ndarray:
    """Parse a <varray> element into a numpy array."""
    rows = []
    for v in elem.findall("v"):
        if v.text:
            rows.append([float(x) for x in v.text.split()])
    return np.array(rows, dtype=float)


def _extract_species(root: ET.Element) -> List[str]:
    """Extract species list from <atominfo> (for DOM-based callers)."""
    species = []
    atom_array = root.find(".//atominfo/array[@name='atoms']/set")
    if atom_array is not None:
        for rc in atom_array.findall("rc"):
            cols = rc.findall("c")
            if cols:
                species.append(cols[0].text.strip() if cols[0].text else "X")
    return species


def _extract_species_from_elem(atominfo_elem: ET.Element) -> List[str]:
    """Extract species list from an <atominfo> element (iterparse-compatible)."""
    species = []
    atom_array = atominfo_elem.find("array[@name='atoms']/set")
    if atom_array is not None:
        for rc in atom_array.findall("rc"):
            cols = rc.findall("c")
            if cols:
                species.append(cols[0].text.strip() if cols[0].text else "X")
    return species


def _frac_to_cart(frac_coords: np.ndarray, lattice: np.ndarray) -> np.ndarray:
    """Convert fractional coordinates to Cartesian."""
    return frac_coords @ lattice


def parse_vasprun_trajectory(path: Path) -> dict:
    """Parse vasprun.xml into trajectory frames using iterparse.

    Uses streaming ElementTree iterparse to avoid loading the entire DOM
    into memory. Each ``<calculation>`` element is processed and then
    cleared to free memory immediately.

    Returns dict with:
    - species: list[str]
    - frames: list of dicts with positions, cell, energy, forces, stress
    """
    species: List[str] = []
    frames: list[dict] = []

    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "atominfo" and not species:
            species = _extract_species_from_elem(elem)

        elif elem.tag == "calculation":
            struct = elem.find("structure")
            if struct is not None:
                basis = struct.find("crystal/varray[@name='basis']")
                if basis is not None:
                    lattice = _parse_varray(basis)

                    pos_elem = struct.find("varray[@name='positions']")
                    if pos_elem is not None:
                        frac_positions = _parse_varray(pos_elem)
                        cart_positions = _frac_to_cart(frac_positions, lattice)

                        energy_elem = elem.find("energy/i[@name='e_fr_energy']")
                        energy = float(energy_elem.text.strip()) if energy_elem is not None and energy_elem.text else None

                        forces_elem = elem.find("varray[@name='forces']")
                        forces = _parse_varray(forces_elem) if forces_elem is not None else None

                        stress_elem = elem.find("varray[@name='stress']")
                        stress = _parse_varray(stress_elem) if stress_elem is not None else None

                        frames.append({
                            "positions": cart_positions,
                            "cell": lattice,
                            "energy": energy,
                            "forces": forces,
                            "stress": stress,
                        })
            elem.clear()  # free memory for this <calculation>

    if not species:
        raise ValueError(f"No species found in {path}")

    return {"species": species, "frames": frames}


def parse_xdatcar(path: Path) -> dict:
    """Parse XDATCAR into trajectory frames (positions only).

    Returns dict with:
    - species: list[str]
    - lattice: ndarray (3, 3)
    - frame_positions: list of ndarray (N, 3) in Cartesian
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 8:
        raise ValueError(f"XDATCAR too short: {path}")

    # Parse scale factor
    scale = float(lines[1].strip())

    # Parse lattice vectors (lines 2-4)
    lattice = np.array([
        [float(x) for x in lines[2].split()],
        [float(x) for x in lines[3].split()],
        [float(x) for x in lines[4].split()],
    ], dtype=float) * scale

    # Parse species (line 5) and counts (line 6)
    species_labels = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    species = []
    for label, count in zip(species_labels, counts):
        species.extend([label] * count)
    n_atoms = sum(counts)

    # Parse frames
    frame_positions = []
    i = 7
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Direct") or line.startswith("direct"):
            i += 1
            coords = []
            for _ in range(n_atoms):
                if i >= len(lines):
                    break
                parts = lines[i].split()
                if len(parts) >= 3:
                    coords.append([float(parts[0]), float(parts[1]), float(parts[2])])
                i += 1
            if len(coords) == n_atoms:
                frac = np.array(coords, dtype=float)
                cart = _frac_to_cart(frac, lattice)
                frame_positions.append(cart)
        else:
            i += 1

    return {
        "species": species,
        "lattice": lattice,
        "frame_positions": frame_positions,
    }


def _parse_oszicar_energies(path: Path) -> List[float]:
    """Parse ionic step energies from OSZICAR."""
    energies = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _IONIC_RE.match(line)
        if m:
            energies.append(float(m.group(2)))
            continue
        m = _MD_RE.match(line)
        if m:
            energies.append(float(m.group(3)))
    return energies


@register_parser("vasp", "trajectory")
class VASPTrajectoryProvider:
    """VASP trajectory analysis provider."""

    engine = "vasp"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "vasprun.xml").exists() or (raw_dir / "XDATCAR").exists()

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        """Parse trajectory from vasprun.xml (primary) or XDATCAR+OSZICAR (fallback)."""
        raw_dir = evidence.primary_raw_dir
        vasprun_path = raw_dir / "vasprun.xml"
        xdatcar_path = raw_dir / "XDATCAR"
        oszicar_path = raw_dir / "OSZICAR"

        source_files: list[SourceFileStat] = []
        warnings: list[str] = []
        frames: list[Frame] = []
        traj_type = "relax"

        if vasprun_path.exists():
            # Primary path: vasprun.xml
            vasprun_size = vasprun_path.stat().st_size
            if vasprun_size > _SIZE_WARN_THRESHOLD and xdatcar_path.exists():
                warnings.append(
                    f"vasprun.xml is large ({vasprun_size / 1024 / 1024:.0f} MB); "
                    "consider XDATCAR fallback for lower memory usage."
                )
                logger.warning(
                    "vasprun.xml is %d MB; XDATCAR fallback available",
                    vasprun_size // (1024 * 1024),
                )
            source_files.append(SourceFileStat.from_path(vasprun_path, evidence.calc_dir))
            parsed = parse_vasprun_trajectory(vasprun_path)
            species = parsed["species"]

            for idx, frame_data in enumerate(parsed["frames"]):
                cell = frame_data["cell"]
                frames.append(Frame(
                    frame_index=idx,
                    positions=frame_data["positions"],
                    species=list(species),
                    cell=cell,
                    pbc=(True, True, True),
                    iteration=idx + 1,
                    energy=frame_data["energy"],
                    forces=frame_data["forces"],
                    stress=frame_data["stress"],
                ))

        elif xdatcar_path.exists():
            # Fallback path: XDATCAR + OSZICAR
            source_files.append(SourceFileStat.from_path(xdatcar_path, evidence.calc_dir))
            parsed_xdat = parse_xdatcar(xdatcar_path)
            species = parsed_xdat["species"]
            lattice = parsed_xdat["lattice"]

            energies: list[Optional[float]] = [None] * len(parsed_xdat["frame_positions"])
            if oszicar_path.exists():
                source_files.append(SourceFileStat.from_path(oszicar_path, evidence.calc_dir))
                oszicar_energies = _parse_oszicar_energies(oszicar_path)
                for i, e in enumerate(oszicar_energies):
                    if i < len(energies):
                        energies[i] = e

            for idx, positions in enumerate(parsed_xdat["frame_positions"]):
                frames.append(Frame(
                    frame_index=idx,
                    positions=positions,
                    species=list(species),
                    cell=np.array(lattice, copy=True),
                    pbc=(True, True, True),
                    iteration=idx + 1,
                    energy=energies[idx],
                ))

            if not frames:
                warnings.append("No frames found in XDATCAR.")
        else:
            raise FileNotFoundError(
                f"Neither vasprun.xml nor XDATCAR found in {raw_dir}"
            )

        # Detect trajectory type from gen_steps
        if any("md" in gs for gs in evidence.gen_steps):
            traj_type = "md"

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="vasp_trajectory",
            parser_version="1.0",
            warnings=warnings,
        )

        return Trajectory(
            meta=meta,
            frames=frames,
            trajectory_type=traj_type,
        )
