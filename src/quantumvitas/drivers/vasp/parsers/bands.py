"""VASP bands analysis provider."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import numpy as np

from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.drivers.vasp.io.poscar import parse_poscar_text
from quantumvitas.parsers.registry import register_parser


EvidenceStep = Tuple[str, str, Path]
_EFERMI_RE = re.compile(r"E-fermi\s*:\s*([-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?)")


def parse_eigenval(eigenval_path: Path) -> dict[str, Any]:
    """Parse VASP EIGENVAL into k-point and eigenvalue arrays."""
    if not eigenval_path.exists():
        raise FileNotFoundError(f"EIGENVAL not found: {eigenval_path}")

    lines = eigenval_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 7:
        raise ValueError(f"Invalid EIGENVAL (too short): {eigenval_path}")

    system_name = lines[4].strip()
    counts = lines[5].split()
    if len(counts) < 3:
        raise ValueError(f"Invalid EIGENVAL header counts: {lines[5]!r}")

    n_electrons = int(float(counts[0]))
    n_kpoints = int(float(counts[1]))
    n_bands = int(float(counts[2]))

    kpoints: list[list[float]] = []
    weights: list[float] = []
    eigen_blocks: list[list[list[float]]] = []
    occupation_blocks: list[list[list[float]]] = []

    line_index = 6
    for _ in range(n_kpoints):
        while line_index < len(lines) and not lines[line_index].strip():
            line_index += 1
        if line_index >= len(lines):
            raise ValueError("Unexpected EOF before k-point blocks completed")

        kpoint_parts = lines[line_index].split()
        if len(kpoint_parts) < 4:
            raise ValueError(f"Invalid k-point line: {lines[line_index]!r}")
        kpoints.append([float(kpoint_parts[0]), float(kpoint_parts[1]), float(kpoint_parts[2])])
        weights.append(float(kpoint_parts[3]))
        line_index += 1

        band_values: list[list[float]] = []
        band_occupations: list[list[float]] = []
        for _band in range(n_bands):
            while line_index < len(lines) and not lines[line_index].strip():
                line_index += 1
            if line_index >= len(lines):
                raise ValueError("Unexpected EOF inside band entries")

            band_parts = lines[line_index].split()
            if len(band_parts) >= 5:
                # Spin-polarized format: idx, e_up, occ_up, e_dn, occ_dn
                values = [float(band_parts[1]), float(band_parts[3])]
                occupations = [float(band_parts[2]), float(band_parts[4])]
            elif len(band_parts) >= 3:
                # Non-spin format: idx, e, occ
                values = [float(band_parts[1])]
                occupations = [float(band_parts[2])]
            else:
                raise ValueError(f"Invalid band line: {lines[line_index]!r}")

            band_values.append(values)
            band_occupations.append(occupations)
            line_index += 1

        eigen_blocks.append(band_values)
        occupation_blocks.append(band_occupations)

    spin_counts = {len(values) for block in eigen_blocks for values in block}
    if not spin_counts:
        raise ValueError("No eigenvalue data parsed from EIGENVAL")
    if spin_counts - {1, 2}:
        raise ValueError(f"Unsupported spin channel counts in EIGENVAL: {sorted(spin_counts)}")
    if len(spin_counts) != 1:
        raise ValueError(f"Inconsistent spin channel counts in EIGENVAL: {sorted(spin_counts)}")

    n_spin = spin_counts.pop()
    if n_spin == 1:
        eigenvalues = np.array(
            [[values[0] for values in block] for block in eigen_blocks],
            dtype=float,
        )
        occupations = np.array(
            [[values[0] for values in block] for block in occupation_blocks],
            dtype=float,
        )
    else:
        eigenvalues = np.transpose(np.array(eigen_blocks, dtype=float), (2, 0, 1))
        occupations = np.transpose(np.array(occupation_blocks, dtype=float), (2, 0, 1))

    return {
        "n_electrons": n_electrons,
        "n_kpoints": n_kpoints,
        "n_bands": n_bands,
        "n_spin": n_spin,
        "kpoints": np.array(kpoints, dtype=float),
        "weights": np.array(weights, dtype=float),
        "eigenvalues": eigenvalues,
        "occupations": occupations,
        "system_name": system_name,
    }


def _reciprocal_lattice(lattice: np.ndarray) -> np.ndarray:
    """Compute reciprocal lattice B = 2π * inv(A)^T.

    Args:
        lattice: Real-space lattice matrix (3x3), rows = lattice vectors.

    Returns:
        Reciprocal lattice matrix (3x3), rows = reciprocal vectors.
    """
    return 2.0 * np.pi * np.linalg.inv(lattice).T


def _read_kpoints_labels(
    raw_dir: Path,
    lattice: np.ndarray | None = None,
) -> list[HighSymPoint]:
    """Extract high-symmetry labels from line-mode KPOINTS.

    Args:
        raw_dir: Directory containing KPOINTS file.
        lattice: Real-space lattice matrix (3x3, rows = vectors). When
            provided, k-point distances are computed in reciprocal Cartesian
            space (correct metric). When ``None``, fractional Euclidean is
            used as fallback.
    """
    kpoints_path = raw_dir / "KPOINTS"
    if not kpoints_path.exists():
        return []

    lines = kpoints_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 6:
        return []
    if "line" not in lines[2].strip().lower():
        return []

    recip = _reciprocal_lattice(lattice) if lattice is not None else None

    segments: list[tuple[np.ndarray, np.ndarray, str, str]] = []
    point_entries: list[tuple[np.ndarray, str]] = []
    for raw_line in lines[4:]:
        stripped = raw_line.strip()
        if not stripped:
            continue
        coords_text, separator, label_text = stripped.partition("!")
        coords_parts = coords_text.split()
        if len(coords_parts) < 3:
            continue
        try:
            coords = np.array(
                [float(coords_parts[0]), float(coords_parts[1]), float(coords_parts[2])],
                dtype=float,
            )
        except ValueError:
            continue
        point_entries.append((coords, label_text.strip() if separator else ""))

    for index in range(0, len(point_entries) - 1, 2):
        start_coords, start_label = point_entries[index]
        end_coords, end_label = point_entries[index + 1]
        segments.append((start_coords, end_coords, start_label, end_label))

    if not segments:
        return []

    points: list[HighSymPoint] = []
    cumulative = 0.0

    start_label = segments[0][2]
    if start_label:
        points.append(HighSymPoint(k_distance=0.0, label=start_label))

    for _, (start_coords, end_coords, _start_label, end_label) in enumerate(segments):
        if recip is not None:
            delta_cart = recip.T @ (end_coords - start_coords)
            cumulative += float(np.linalg.norm(delta_cart))
        else:
            cumulative += float(np.linalg.norm(end_coords - start_coords))
        if not end_label:
            continue
        if points and points[-1].label == end_label and abs(points[-1].k_distance - cumulative) < 1e-8:
            continue
        points.append(HighSymPoint(k_distance=cumulative, label=end_label))

    return points


def _compute_k_distances(
    kpoints: np.ndarray,
    lattice: np.ndarray | None = None,
) -> np.ndarray:
    """Compute cumulative k-path distances.

    Args:
        kpoints: Fractional k-point coordinates, shape ``(n_kpoints, 3)``.
        lattice: Real-space lattice matrix (3x3, rows = vectors). When
            provided, distances are computed in reciprocal Cartesian space
            (the physically correct metric). When ``None``, fractional
            Euclidean is used as fallback.

    Returns:
        Cumulative k-path distances, shape ``(n_kpoints,)``, in units of
        1/Angstrom when lattice is provided.
    """
    distances = np.zeros(kpoints.shape[0], dtype=float)
    if kpoints.shape[0] <= 1:
        return distances
    dk_frac = np.diff(kpoints, axis=0)  # (n-1, 3)
    if lattice is not None:
        recip = _reciprocal_lattice(lattice)
        dk_cart = dk_frac @ recip  # (n-1, 3) in Cartesian reciprocal space
        deltas = np.linalg.norm(dk_cart, axis=1)
    else:
        deltas = np.linalg.norm(dk_frac, axis=1)
    distances[1:] = np.cumsum(deltas)
    return distances


def _read_fermi_from_vasprun(path: Path) -> Optional[float]:
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


def _read_fermi_from_outcar(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _EFERMI_RE.search(line)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def _read_fermi_energy(raw_dirs: Sequence[Path]) -> tuple[Optional[float], Optional[Path]]:
    for raw_dir in raw_dirs:
        vasprun = raw_dir / "vasprun.xml"
        value = _read_fermi_from_vasprun(vasprun)
        if value is not None:
            return value, vasprun

    for raw_dir in raw_dirs:
        outcar = raw_dir / "OUTCAR"
        value = _read_fermi_from_outcar(outcar)
        if value is not None:
            return value, outcar

    return None, None


@register_parser("vasp", "bands")
class VASPBandsProvider:
    """VASP band structure analysis provider."""

    engine = "vasp"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "EIGENVAL").exists()

    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_ulid: Optional[str] = None,
        step_ulids: Optional[list[str]] = None,
        gen_steps: Optional[list[str]] = None,
        calc_ulid: Optional[str] = None,
        evidence_steps: Optional[Sequence[EvidenceStep]] = None,
        engine_name: Optional[str] = None,
    ) -> BandStructure:
        candidate_dirs = [raw_dir]
        if evidence_steps:
            for _step_ulid, _gen_step, evidence_dir in evidence_steps:
                if evidence_dir not in candidate_dirs:
                    candidate_dirs.append(evidence_dir)

        eigenval_path = next((d / "EIGENVAL" for d in candidate_dirs if (d / "EIGENVAL").exists()), None)
        if eigenval_path is None:
            raise FileNotFoundError(f"No EIGENVAL found in {candidate_dirs}")

        parsed = parse_eigenval(eigenval_path)
        kpoints = parsed["kpoints"]

        # Read lattice from POSCAR for reciprocal Cartesian k-distances
        lattice: np.ndarray | None = None
        for d in candidate_dirs:
            poscar_path = d / "POSCAR"
            if poscar_path.exists():
                try:
                    structure = parse_poscar_text(
                        poscar_path.read_text(encoding="utf-8", errors="replace")
                    )
                    lattice = np.array(structure["lattice"], dtype=float)
                except (ValueError, KeyError):
                    pass
                break

        k_distances = _compute_k_distances(kpoints, lattice)

        labels = _read_kpoints_labels(eigenval_path.parent, lattice)
        fermi_energy, fermi_source = _read_fermi_energy(candidate_dirs)

        source_files = [SourceFileStat.from_path(eigenval_path, calc_dir)]
        kpoints_path = eigenval_path.parent / "KPOINTS"
        if kpoints_path.exists():
            source_files.append(SourceFileStat.from_path(kpoints_path, calc_dir))
        poscar_used = eigenval_path.parent / "POSCAR"
        if poscar_used.exists():
            source_files.append(SourceFileStat.from_path(poscar_used, calc_dir))
        if fermi_source is not None:
            source_files.append(SourceFileStat.from_path(fermi_source, calc_dir))

        warnings: list[str] = []
        if lattice is None:
            warnings.append("No POSCAR found; k-distances use fractional Euclidean (incorrect for non-cubic cells).")
        if not labels:
            warnings.append("No line-mode KPOINTS labels found.")
        if fermi_energy is None:
            warnings.append("No Fermi energy found in vasprun.xml or OUTCAR.")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            step_ulids=step_ulids or [],
            gen_steps=gen_steps or [],
            engine_name=engine_name or "vasp",
            parser_name="vasp_bands",
            parser_version="1.0",
            warnings=warnings,
        )

        return BandStructure(
            meta=meta,
            k_distances=k_distances,
            eigenvalues=np.array(parsed["eigenvalues"], copy=True),
            high_symmetry_points=labels,
            fermi_energy=fermi_energy,
            spin_polarized=bool(parsed["n_spin"] == 2),
        )
