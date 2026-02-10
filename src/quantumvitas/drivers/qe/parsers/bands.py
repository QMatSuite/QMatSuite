"""QE bands analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from quantumvitas.analysis.parsers import parse_bands_gnu, parse_scf_output
from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

# Regex for atomic wfc header in projwfc_up:
#   "    1    1 Si   3S     1    0    1"
#   wfc_idx  atom_idx  element  nl_label  n  l  m
_PROJWFC_WFC_RE = re.compile(
    r"^\s+(\d+)\s+(\d+)\s+(\w+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
)


def parse_projwfc_up(projwfc_path: Path) -> Dict[str, Any]:
    """Parse QE projwfc_up file (from filproj output) into projection arrays.

    The filproj file has:
      - Global header (9 lines): grid, cell, species, positions
      - Line 8: n_atomwfc, n_kpoints, n_bands
      - For each atomic wfc: 1 header line + n_kpoints * n_bands data lines
        Data lines: kpoint_idx  band_idx  |<psi_nk|phi_i>|^2

    We group projections by (atom, l) and sum over m-components.

    Returns dict with:
        n_kpoints: int
        n_bands: int
        n_atoms: int
        n_orbitals: int  (number of distinct l values)
        projections: ndarray (n_kpoints, n_bands, n_atoms, n_orbitals)
        orbital_labels: list[str]
        atom_labels: list[str]
    """
    text = projwfc_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) < 10:
        raise ValueError(f"projwfc_up file too short: {projwfc_path}")

    # Parse header line 8 (0-indexed line 7): n_atomwfc, n_kpoints, n_bands
    # Account for possible blank first line
    header_offset = 0
    if lines[0].strip() == "":
        header_offset = 1

    dim_line = lines[6 + header_offset].strip().split()
    if len(dim_line) < 3:
        raise ValueError(f"Cannot parse dimensions from projwfc_up: {lines[6 + header_offset]!r}")

    n_atomwfc = int(dim_line[0])
    n_kpoints = int(dim_line[1])
    n_bands = int(dim_line[2])

    # Parse atomic wfc definitions to build atom/orbital mapping
    # Each wfc header: wfc_idx, atom_idx, element, nl_label, n, l, m
    wfc_defs: list[dict] = []
    atom_elements: dict[int, str] = {}  # atom_idx -> element
    data_start = 8 + header_offset  # skip header + F/F line

    line_idx = data_start
    for _wfc_i in range(n_atomwfc):
        if line_idx >= len(lines):
            raise ValueError("Unexpected EOF parsing projwfc_up wfc headers")

        m = _PROJWFC_WFC_RE.match(lines[line_idx])
        if not m:
            raise ValueError(f"Cannot parse wfc header: {lines[line_idx]!r}")

        atom_idx = int(m.group(2))  # 1-based
        element = m.group(3)
        l_val = int(m.group(6))

        wfc_defs.append({"atom_idx": atom_idx, "element": element, "l": l_val})
        atom_elements[atom_idx] = element
        line_idx += 1

        # Skip n_kpoints * n_bands data lines for this wfc
        line_idx += n_kpoints * n_bands

    # Determine unique atoms and l-values
    n_atoms = len(atom_elements)
    all_l_values = sorted({w["l"] for w in wfc_defs})
    n_orbitals = len(all_l_values)
    l_to_idx = {l_val: i for i, l_val in enumerate(all_l_values)}

    l_label_map = {0: "s", 1: "p", 2: "d", 3: "f", 4: "g"}
    orbital_labels = [l_label_map.get(l_val, f"l={l_val}") for l_val in all_l_values]

    # Build atom labels
    atom_counts: Dict[str, int] = {}
    atom_labels: list[str] = []
    for atom_idx in sorted(atom_elements.keys()):
        elem = atom_elements[atom_idx]
        atom_counts[elem] = atom_counts.get(elem, 0) + 1
        atom_labels.append(f"{elem}_{atom_counts[elem]}")

    # Now re-parse data lines to build projection array
    projections = np.zeros((n_kpoints, n_bands, n_atoms, n_orbitals), dtype=np.float64)

    line_idx = data_start
    for wfc_def in wfc_defs:
        # Skip wfc header line
        line_idx += 1

        atom_array_idx = wfc_def["atom_idx"] - 1  # 0-based
        l_array_idx = l_to_idx[wfc_def["l"]]

        for _ in range(n_kpoints * n_bands):
            if line_idx >= len(lines):
                break
            parts = lines[line_idx].strip().split()
            if len(parts) >= 3:
                try:
                    k_idx = int(parts[0]) - 1  # 1-based -> 0-based
                    b_idx = int(parts[1]) - 1
                    proj_val = float(parts[2])
                    # Sum over m-components for same (atom, l)
                    projections[k_idx, b_idx, atom_array_idx, l_array_idx] += proj_val
                except (ValueError, IndexError):
                    pass
            line_idx += 1

    return {
        "n_kpoints": n_kpoints,
        "n_bands": n_bands,
        "n_atoms": n_atoms,
        "n_orbitals": n_orbitals,
        "projections": projections,
        "orbital_labels": orbital_labels,
        "atom_labels": atom_labels,
    }


@register_parser("qe", "bands")
class QEBandsProvider:
    """Parse QE bands outputs into a canonical BandStructure object."""

    engine = "qe"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(
            list(raw_dir.glob("*.bands.dat.gnu"))
            or list(raw_dir.glob("bands.dat.gnu"))
        )

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        """Parse QE bands output and return engine-agnostic BandStructure."""
        candidate_dirs = self._candidate_raw_dirs(evidence.primary_raw_dir, evidence.evidence_steps)

        bands_file = self._find_first(
            candidate_dirs,
            ["*.bands.dat.gnu", "bands.dat.gnu"],
        )
        if bands_file is None:
            raise FileNotFoundError(f"No QE bands.dat.gnu file found in {evidence.primary_raw_dir}")

        symmetry_file = self._find_first(
            [bands_file.parent],
            [
                "*.bands.pp.out",
                "*_bands.pp.out",
                "*.pp.out",
                "*.bands.out",
                "*_bands.out",
                "bands.pp.out",
                "bands.out",
            ],
        )
        pw_output = self._find_first(
            candidate_dirs,
            ["*.nscf.out", "nscf.out", "*.scf.out", "scf.out", "*.out"],
        )

        warnings: list[str] = []
        fermi_energy = None
        if pw_output is not None:
            try:
                fermi_energy = parse_scf_output(pw_output).fermi_energy
            except Exception:
                warnings.append(f"Failed to parse Fermi energy from {pw_output.name}")
        else:
            warnings.append("No SCF/NSCF output found for Fermi energy extraction.")

        if symmetry_file is None:
            warnings.append("No bands symmetry output found; high-symmetry labels may be absent.")

        band_data = parse_bands_gnu(
            bands_file=bands_file,
            symmetry_file=symmetry_file,
            fermi_energy=fermi_energy,
            pw_output_file=pw_output,
        )

        source_files = [SourceFileStat.from_path(bands_file, evidence.calc_dir)]
        if symmetry_file is not None:
            source_files.append(SourceFileStat.from_path(symmetry_file, evidence.calc_dir))
        if pw_output is not None:
            source_files.append(SourceFileStat.from_path(pw_output, evidence.calc_dir))

        eigenvalues = np.array(band_data.energies, copy=True).T
        n_kpoints_bands = eigenvalues.shape[0]
        n_bands_bands = eigenvalues.shape[1]

        # Check for projwfc_up file (fatband projections from projwfc.x)
        projections: Optional[np.ndarray] = None
        projection_labels: Optional[Dict[str, List[str]]] = None

        projwfc_file = self._find_first(
            candidate_dirs,
            ["*.projwfc_up", "projwfc_up"],
        )
        if projwfc_file is not None:
            try:
                projwfc_data = parse_projwfc_up(projwfc_file)
                if (
                    projwfc_data["n_kpoints"] == n_kpoints_bands
                    and projwfc_data["n_bands"] == n_bands_bands
                ):
                    projections = projwfc_data["projections"]
                    projection_labels = {
                        "atoms": projwfc_data["atom_labels"],
                        "orbitals": projwfc_data["orbital_labels"],
                    }
                    source_files.append(
                        SourceFileStat.from_path(projwfc_file, evidence.calc_dir)
                    )
                else:
                    warnings.append(
                        f"projwfc_up dimensions ({projwfc_data['n_kpoints']}k, "
                        f"{projwfc_data['n_bands']}b) mismatch bands "
                        f"({n_kpoints_bands}k, {n_bands_bands}b); "
                        "projections skipped."
                    )
            except (ValueError, OSError) as exc:
                warnings.append(f"Failed to parse projwfc_up: {exc}")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="qe_bands",
            parser_version="1.0",
            warnings=warnings,
        )

        return BandStructure(
            meta=meta,
            k_distances=np.array(band_data.k_distances, copy=True),
            eigenvalues=eigenvalues,
            high_symmetry_points=[
                HighSymPoint(k_distance=point.k_distance, label=point.label)
                for point in band_data.high_symmetry_points
            ],
            fermi_energy=band_data.fermi_energy,
            spin_polarized=False,
            projections=projections,
            projection_labels=projection_labels,
        )

    def _candidate_raw_dirs(
        self,
        raw_dir: Path,
        evidence_steps: list[tuple[str, str, Path]],
    ) -> list[Path]:
        dirs = [raw_dir]
        if evidence_steps:
            for _step_ulid, _gen_step, step_raw_dir in evidence_steps:
                if step_raw_dir not in dirs:
                    dirs.append(step_raw_dir)
        return dirs

    def _find_first(self, dirs: Sequence[Path], patterns: Sequence[str]) -> Optional[Path]:
        for directory in dirs:
            for pattern in patterns:
                matches = sorted(directory.glob(pattern))
                if matches:
                    return matches[0]
        return None
