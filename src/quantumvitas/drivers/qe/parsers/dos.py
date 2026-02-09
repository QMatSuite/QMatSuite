"""QE DOS analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from quantumvitas.analysis.parsers import parse_dos_data
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser


def _parse_pdos_file(path: Path) -> dict:
    """Parse a single QE projwfc.x PDOS file.

    Format: header line + energy/projection columns.
    Returns dict with energies and projection data.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    energies: list[float] = []
    projections: list[float] = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                energies.append(float(parts[0]))
                # Sum all LDOS columns (skip energy column)
                projections.append(sum(float(x) for x in parts[1:]))
            except ValueError:
                continue

    return {"energies": energies, "projections": projections}


def _parse_pdos_filename(filename: str) -> dict:
    """Extract atom/orbital info from projwfc.x PDOS filename.

    Patterns:
        si.pdos_atm#1(Si)_wfc#1(s)
        prefix.pdos_atm#2(O)_wfc#3(p)
    """
    result: dict = {"atom_index": None, "atom_symbol": None, "orbital_index": None, "orbital_name": None}

    atm_match = re.search(r"atm#(\d+)\((\w+)\)", filename)
    if atm_match:
        result["atom_index"] = int(atm_match.group(1))
        result["atom_symbol"] = atm_match.group(2)

    wfc_match = re.search(r"wfc#(\d+)\((\w+)\)", filename)
    if wfc_match:
        result["orbital_index"] = int(wfc_match.group(1))
        result["orbital_name"] = wfc_match.group(2)

    return result


@register_parser("qe", "dos")
class QEDOSProvider:
    """Parse QE DOS outputs into a canonical DOS object."""

    engine = "qe"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(
            list(raw_dir.glob("*.dos.dat"))
            or list(raw_dir.glob("dos.dat"))
            or (raw_dir / "dos.dat").exists()
        )

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse QE DOS output and return engine-agnostic DOS."""
        candidate_dirs = self._candidate_raw_dirs(evidence.primary_raw_dir, evidence.evidence_steps)

        dos_file = self._find_first(candidate_dirs, ["*.dos.dat", "dos.dat"])
        if dos_file is None:
            raise FileNotFoundError(f"No QE dos.dat file found in {evidence.primary_raw_dir}")

        warnings: list[str] = []

        # Parse total DOS using existing low-level parser
        dos_data = parse_dos_data(dos_file)

        source_files = [SourceFileStat.from_path(dos_file, evidence.calc_dir)]

        # Parse PDOS from projwfc.x output files if available
        pdos = None
        atom_labels = None
        orbital_labels = None

        pdos_files = sorted(dos_file.parent.glob("*.pdos_atm*"))
        if pdos_files:
            pdos_result = self._parse_projwfc_pdos(pdos_files)
            if pdos_result is not None:
                pdos = pdos_result["pdos"]
                atom_labels = pdos_result["atom_labels"]
                orbital_labels = pdos_result["orbital_labels"]
                for pf in pdos_files[:3]:  # Track first few source files
                    source_files.append(SourceFileStat.from_path(pf, evidence.calc_dir))

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="qe_dos",
            parser_version="1.0",
            warnings=warnings,
        )

        return DOS(
            meta=meta,
            energies=np.array(dos_data.energies, copy=True),
            total_dos=np.array(dos_data.dos, copy=True),
            fermi_energy=dos_data.fermi_energy,
            integrated_dos=np.array(dos_data.idos, copy=True) if dos_data.idos is not None else None,
            pdos=pdos,
            atom_labels=atom_labels,
            orbital_labels=orbital_labels,
            spin_polarized=False,
        )

    def _parse_projwfc_pdos(self, pdos_files: list[Path]) -> Optional[dict]:
        """Parse projwfc.x PDOS files into (n_atoms, nedos, n_orbitals) array."""
        # Group files by atom
        atom_orbitals: dict[int, dict] = {}  # atom_index -> {symbol, orbitals: {name: data}}

        for pf in pdos_files:
            info = _parse_pdos_filename(pf.name)
            if info["atom_index"] is None or info["orbital_name"] is None:
                continue

            parsed = _parse_pdos_file(pf)
            if not parsed["projections"]:
                continue

            atom_idx = info["atom_index"]
            if atom_idx not in atom_orbitals:
                atom_orbitals[atom_idx] = {
                    "symbol": info["atom_symbol"],
                    "orbitals": {},
                }
            atom_orbitals[atom_idx]["orbitals"][info["orbital_name"]] = parsed["projections"]

        if not atom_orbitals:
            return None

        # Build arrays
        sorted_atoms = sorted(atom_orbitals.keys())
        # Collect all unique orbital names in order
        all_orb_names: list[str] = []
        for aidx in sorted_atoms:
            for oname in atom_orbitals[aidx]["orbitals"]:
                if oname not in all_orb_names:
                    all_orb_names.append(oname)

        n_atoms = len(sorted_atoms)
        n_orbitals = len(all_orb_names)
        # Get nedos from first atom's first orbital
        first_atom = atom_orbitals[sorted_atoms[0]]
        first_orb = next(iter(first_atom["orbitals"].values()))
        nedos = len(first_orb)

        pdos_array = np.zeros((n_atoms, nedos, n_orbitals), dtype=float)
        for ai, aidx in enumerate(sorted_atoms):
            for oi, oname in enumerate(all_orb_names):
                data = atom_orbitals[aidx]["orbitals"].get(oname)
                if data is not None and len(data) == nedos:
                    pdos_array[ai, :, oi] = data

        # Build atom labels: "Si_1", "Si_2", "O_1", etc.
        counts: dict[str, int] = {}
        labels: list[str] = []
        for aidx in sorted_atoms:
            sym = atom_orbitals[aidx]["symbol"] or f"atom"
            counts[sym] = counts.get(sym, 0) + 1
            labels.append(f"{sym}_{counts[sym]}")

        return {
            "pdos": pdos_array,
            "atom_labels": labels,
            "orbital_labels": all_orb_names,
        }

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
