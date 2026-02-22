"""CP2K DOS analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.dos import DOS
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser

# Hartree to eV conversion
HA_TO_EV = 27.211386245988


def _parse_cp2k_pdos(pdos_path: Path) -> dict:
    """Parse a single CP2K PDOS file.

    Format:
        # Projected DOS for atomic kind Si at iteration step i = 0, E(Fermi) = 0.283521 a.u.
        #     MO Eigenvalue [a.u.]  Occupation  s  py  pz  px  d-2  d-1  d0  d+1  d+2
              1     -0.212339     2.000000     1.000  0.000  ...

    Returns dict with eigenvalues_eV, occupations, orbital_projections,
    orbital_names, fermi_eV, atom_kind.
    """
    text = pdos_path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    fermi_ha: Optional[float] = None
    atom_kind: Optional[str] = None
    orbital_names: list[str] = []
    eigenvalues: list[float] = []
    occupations: list[float] = []
    projections: list[list[float]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("#"):
            # Extract Fermi energy from header
            fermi_match = re.search(r"E\(Fermi\)\s*=\s*([-\d.]+)\s*a\.u\.", stripped)
            if fermi_match:
                try:
                    fermi_ha = float(fermi_match.group(1))
                except ValueError:
                    pass

            # Extract atom kind
            kind_match = re.search(r"atomic kind\s+(\w+)", stripped)
            if kind_match:
                atom_kind = kind_match.group(1)

            # Extract orbital names from column header
            if "MO" in stripped and "Eigenvalue" in stripped:
                # Column names come after "Occupation"
                parts = stripped.lstrip("#").split()
                try:
                    occ_idx = parts.index("Occupation")
                    orbital_names = parts[occ_idx + 1:]
                except ValueError:
                    pass
            continue

        # Data line: MO  Eigenvalue  Occupation  proj1  proj2  ...
        parts = stripped.split()
        if len(parts) >= 3:
            try:
                eigenvalues.append(float(parts[1]) * HA_TO_EV)
                occupations.append(float(parts[2]))
                if len(parts) > 3:
                    projections.append([float(x) for x in parts[3:]])
            except ValueError:
                continue

    fermi_eV = fermi_ha * HA_TO_EV if fermi_ha is not None else None

    return {
        "eigenvalues_eV": np.array(eigenvalues, dtype=float),
        "occupations": np.array(occupations, dtype=float),
        "projections": np.array(projections, dtype=float) if projections else None,
        "orbital_names": orbital_names,
        "fermi_eV": fermi_eV,
        "atom_kind": atom_kind,
    }


def _extract_fermi_from_out(out_path: Path) -> Optional[float]:
    """Extract Fermi energy from CP2K .out file. Returns eV."""
    text = out_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Fermi\s+energy:\s+([-\d.]+)", text)
    if match:
        try:
            return float(match.group(1)) * HA_TO_EV
        except ValueError:
            pass
    return None


@register_parser("cp2k", "dos")
class CP2KDOSProvider:
    """Parse CP2K DOS outputs into a canonical DOS object.

    CP2K outputs per-kind PDOS files (projected density of states).
    Each file contains eigenvalues with orbital projections for one
    atomic kind.
    """

    engine = "cp2k"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.pdos")))

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse CP2K PDOS files and return engine-agnostic DOS."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        pdos_files = sorted(raw_dir.glob("*.pdos"))
        if not pdos_files:
            raise FileNotFoundError(f"No CP2K .pdos files found in {raw_dir}")

        # Parse all PDOS files
        all_parsed: list[dict] = []
        for pf in pdos_files:
            all_parsed.append(_parse_cp2k_pdos(pf))

        source_files = [SourceFileStat.from_path(pf, evidence.calc_dir) for pf in pdos_files]

        # Use eigenvalues as energy grid (all files should have same eigenvalues)
        primary = all_parsed[0]
        energies = primary["eigenvalues_eV"]

        # Fermi energy: prefer PDOS header, fallback to .out
        fermi_energy = primary.get("fermi_eV")
        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            out_file = out_files[0]
            source_files.append(SourceFileStat.from_path(out_file, evidence.calc_dir))
            if fermi_energy is None:
                fermi_energy = _extract_fermi_from_out(out_file)

        if fermi_energy is None:
            warnings.append("No Fermi energy found in CP2K output.")

        # Build total DOS from occupations (sum across all kinds)
        total_dos = np.zeros_like(energies)
        for p in all_parsed:
            if len(p["occupations"]) == len(energies):
                total_dos += p["occupations"]

        # Build PDOS array: (n_atoms, nedos, n_orbitals)
        pdos = None
        atom_labels = None
        orbital_labels = None

        pdos_arrays: list[np.ndarray] = []
        atom_label_list: list[str] = []
        all_orbital_names: list[str] = []

        for p in all_parsed:
            if p["projections"] is not None and len(p["projections"]) == len(energies):
                pdos_arrays.append(p["projections"])
                kind = p["atom_kind"] or "X"
                # Label atoms by kind with sequence number
                count = sum(1 for lbl in atom_label_list if lbl.startswith(kind + "_"))
                atom_label_list.append(f"{kind}_{count + 1}")
                for oname in p["orbital_names"]:
                    if oname not in all_orbital_names:
                        all_orbital_names.append(oname)

        if pdos_arrays:
            n_atoms = len(pdos_arrays)
            nedos = len(energies)
            n_orbs = len(all_orbital_names)
            pdos_3d = np.zeros((n_atoms, nedos, n_orbs), dtype=float)

            for ai, (arr, p) in enumerate(zip(pdos_arrays, all_parsed)):
                for oi, oname in enumerate(p["orbital_names"]):
                    if oname in all_orbital_names and oi < arr.shape[1]:
                        global_oi = all_orbital_names.index(oname)
                        pdos_3d[ai, :, global_oi] = arr[:, oi]

            pdos = pdos_3d
            atom_labels = atom_label_list
            orbital_labels = all_orbital_names

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="cp2k_dos",
            parser_version="1.0",
            warnings=warnings,
        )

        return DOS(
            meta=meta,
            energies=energies,
            total_dos=total_dos,
            fermi_energy=fermi_energy,
            pdos=pdos,
            atom_labels=atom_labels,
            orbital_labels=orbital_labels,
            spin_polarized=False,
        )
