"""QE trajectory parser (relax + MD)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Ry to eV conversion
RY_TO_EV = 13.605693122994
BOHR_TO_ANG = 0.529177249


@register_parser("qe", "trajectory")
class QETrajectoryParser:
    """Parse QE relax/vc-relax/MD output to canonical Trajectory."""

    engine = "qe"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        for pattern in ["*.relax.out", "*.md.out", "relax.out", "vc-relax.out", "md.out"]:
            if list(raw_dir.glob(pattern)):
                return True
        return False

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        output_file = self._find_output_file(raw_dir)
        if output_file is None:
            raise FileNotFoundError(f"No QE trajectory output found in {raw_dir}")

        text = output_file.read_text(errors="replace")
        traj_type = self._detect_trajectory_type(output_file, text)
        frames = self._parse_relax_output(text) if traj_type == "relax" else self._parse_md_output(text)

        if not frames:
            raise ValueError(f"No frames found in {output_file}")

        source_files = [SourceFileStat.from_path(output_file, evidence.calc_dir)]

        # Override traj_type from gen_steps if available
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
            parser_name="qe_trajectory",
            parser_version="2.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)

    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        for pattern in ["*.vc-relax.out", "*.relax.out", "*.md.out",
                        "vc-relax.out", "relax.out", "md.out",
                        "si.relax.out", "si.md.out"]:
            matches = sorted(raw_dir.glob(pattern))
            if matches:
                return matches[0]
        return None

    def _detect_trajectory_type(self, output_file: Path, text: str) -> str:
        name = output_file.name.lower()
        if "md" in name:
            return "md"
        if "vc-relax" in name or "vcrelax" in name or "relax" in name:
            return "relax"
        header = text[:5000].lower()
        if "molecular dynamics" in header or "calculation='md'" in header or "calculation = 'md'" in header:
            return "md"
        return "relax"

    def _parse_relax_output(self, text: str) -> List[Frame]:
        frames: List[Frame] = []
        lines = text.split("\n")

        # Extract alat
        alat = 1.0
        for line in lines:
            if "lattice parameter" in line.lower() and "a.u." in line:
                match = re.search(r"=\s*([\d.]+)", line)
                if match:
                    alat = float(match.group(1)) * BOHR_TO_ANG

        current_positions: list = []
        current_species: list = []
        current_cell: list | None = None
        current_energy: float | None = None
        in_positions = False
        in_cell = False
        pos_unit = "angstrom"
        cell_unit = "angstrom"

        total_energy_re = re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry")
        new_coords_re = re.compile(r"ATOMIC_POSITIONS\s*\(([^)]+)\)")
        cell_params_re = re.compile(r"CELL_PARAMETERS\s*\(([^)]+)\)")

        for line in lines:
            stripped = line.strip()

            energy_match = total_energy_re.search(line)
            if energy_match:
                current_energy = float(energy_match.group(1)) * RY_TO_EV

            pos_match = new_coords_re.search(line)
            if pos_match:
                pos_unit = pos_match.group(1).lower().strip()
                in_positions = True
                in_cell = False
                current_positions = []
                current_species = []
                continue

            cell_match = cell_params_re.search(line)
            if cell_match:
                cell_unit = cell_match.group(1).lower().strip()
                in_cell = True
                in_positions = False
                current_cell = []
                continue

            if in_positions:
                if stripped == "" or stripped.startswith("End") or stripped.startswith("CELL"):
                    in_positions = False
                else:
                    parts = stripped.split()
                    if len(parts) >= 4:
                        try:
                            current_species.append(parts[0])
                            current_positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
                        except ValueError:
                            in_positions = False

            if in_cell:
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        current_cell.append([float(parts[0]), float(parts[1]), float(parts[2])])
                        if len(current_cell) == 3:
                            in_cell = False
                    except ValueError:
                        in_cell = False

            if "number of scf cycles" in line.lower() or "bfgs converged" in line.lower():
                if current_positions:
                    frame = self._build_frame(
                        len(frames), current_positions, current_species,
                        current_cell, current_energy, pos_unit, cell_unit, alat,
                    )
                    frames.append(frame)

        # Final frame
        if current_positions and (not frames or frames[-1].frame_index != len(frames)):
            frame = self._build_frame(
                len(frames), current_positions, current_species,
                current_cell, current_energy, pos_unit, cell_unit, alat,
            )
            frames.append(frame)

        return frames

    def _parse_md_output(self, text: str) -> List[Frame]:
        frames: List[Frame] = []
        lines = text.split("\n")

        # Extract alat
        alat = 1.0
        for line in lines:
            if "lattice parameter" in line.lower() and "a.u." in line:
                match = re.search(r"=\s*([\d.]+)", line)
                if match:
                    alat = float(match.group(1)) * BOHR_TO_ANG

        # Get initial cell from celldm or CELL_PARAMETERS
        initial_cell: list | None = None
        in_cell = False
        cell_unit = "angstrom"
        for line in lines:
            cell_match = re.search(r"CELL_PARAMETERS\s*\(([^)]+)\)", line)
            if cell_match:
                cell_unit = cell_match.group(1).lower().strip()
                in_cell = True
                initial_cell = []
                continue
            if in_cell:
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        initial_cell.append([float(parts[0]), float(parts[1]), float(parts[2])])
                        if len(initial_cell) == 3:
                            in_cell = False
                    except ValueError:
                        in_cell = False

        current_positions: list = []
        current_species: list = []
        current_energy: float | None = None
        current_temperature: float | None = None
        current_kinetic: float | None = None
        in_positions = False
        pos_unit = "angstrom"

        total_energy_re = re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry")
        new_coords_re = re.compile(r"ATOMIC_POSITIONS\s*\(([^)]+)\)")
        temp_re = re.compile(r"temperature\s*=\s*([\d.]+)\s*K")
        ekin_re = re.compile(r"kinetic energy \(Ekin\)\s*=\s*([-\d.]+)\s*Ry")

        for line in lines:
            stripped = line.strip()

            energy_match = total_energy_re.search(line)
            if energy_match:
                current_energy = float(energy_match.group(1)) * RY_TO_EV

            temp_match = temp_re.search(line)
            if temp_match:
                current_temperature = float(temp_match.group(1))

            ekin_match = ekin_re.search(line)
            if ekin_match:
                current_kinetic = float(ekin_match.group(1)) * RY_TO_EV

            pos_match = new_coords_re.search(line)
            if pos_match:
                # Save previous frame if we have positions
                if current_positions:
                    frame = self._build_md_frame(
                        len(frames), current_positions, current_species,
                        initial_cell, current_energy, current_temperature,
                        current_kinetic, pos_unit, cell_unit, alat,
                    )
                    frames.append(frame)

                pos_unit = pos_match.group(1).lower().strip()
                in_positions = True
                current_positions = []
                current_species = []
                continue

            if in_positions:
                if stripped == "" or stripped.startswith("End") or stripped.startswith("CELL") or stripped.startswith("kinetic"):
                    in_positions = False
                else:
                    parts = stripped.split()
                    if len(parts) >= 4:
                        try:
                            current_species.append(parts[0])
                            current_positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
                        except ValueError:
                            in_positions = False

        # Final frame
        if current_positions:
            frame = self._build_md_frame(
                len(frames), current_positions, current_species,
                initial_cell, current_energy, current_temperature,
                current_kinetic, pos_unit, cell_unit, alat,
            )
            frames.append(frame)

        return frames

    def _build_frame(
        self, idx: int, positions_raw: list, species: list,
        cell_raw: list | None, energy: float | None,
        pos_unit: str, cell_unit: str, alat: float,
    ) -> Frame:
        cell = self._scale_cell(cell_raw, cell_unit, alat)
        positions = self._convert_positions(positions_raw, pos_unit, cell, alat)
        pbc = (True, True, True) if cell is not None else (False, False, False)
        return Frame(
            frame_index=idx, positions=positions, species=list(species),
            cell=cell, pbc=pbc, iteration=idx, energy=energy,
        )

    def _build_md_frame(
        self, idx: int, positions_raw: list, species: list,
        cell_raw: list | None, energy: float | None,
        temperature: float | None, kinetic_energy: float | None,
        pos_unit: str, cell_unit: str, alat: float,
    ) -> Frame:
        cell = self._scale_cell(cell_raw, cell_unit, alat)
        positions = self._convert_positions(positions_raw, pos_unit, cell, alat)
        pbc = (True, True, True) if cell is not None else (False, False, False)
        return Frame(
            frame_index=idx, positions=positions, species=list(species),
            cell=cell, pbc=pbc, iteration=idx, energy=energy,
            temperature=temperature, kinetic_energy=kinetic_energy,
        )

    def _scale_cell(self, cell_raw: list | None, cell_unit: str, alat: float) -> np.ndarray | None:
        if cell_raw is None or len(cell_raw) != 3:
            return None
        cell = np.array(cell_raw, dtype=float)
        if "alat" in cell_unit:
            cell = cell * alat
        elif "bohr" in cell_unit:
            cell = cell * BOHR_TO_ANG
        return cell

    def _convert_positions(
        self, positions_raw: list, pos_unit: str,
        cell: np.ndarray | None, alat: float,
    ) -> np.ndarray:
        positions = np.array(positions_raw, dtype=float)
        if "crystal" in pos_unit and cell is not None:
            positions = positions @ cell
        elif "bohr" in pos_unit:
            positions = positions * BOHR_TO_ANG
        elif "alat" in pos_unit:
            positions = positions * alat
        return positions
