"""ABINIT DOS analysis provider."""
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


def _parse_abinit_dos(dos_path: Path) -> dict:
    """Parse ABINIT _DOS file.

    Format (varies by prtdos value):
        # energy(Ha)  DOS  integrated_DOS
        -0.5000  0.0000  0.0000
        ...

    Returns dict with energies_eV, dos, integrated_dos.
    """
    text = dos_path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    energies: list[float] = []
    dos_vals: list[float] = []
    idos_vals: list[float] = []
    fermi_ha: Optional[float] = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            # Check for Fermi energy in header: "# Fermi energy :       0.21915481"
            fermi_match = re.search(r"Fermi\s+energy\s*:\s*([-\d.E+]+)", stripped, re.IGNORECASE)
            if fermi_match:
                try:
                    fermi_ha = float(fermi_match.group(1))
                except ValueError:
                    pass
            continue
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            try:
                energy_ha = float(parts[0])
                energies.append(energy_ha * HA_TO_EV)
                dos_vals.append(float(parts[1]))
                if len(parts) >= 3:
                    idos_vals.append(float(parts[2]))
            except ValueError:
                continue

    fermi_eV = fermi_ha * HA_TO_EV if fermi_ha is not None else None

    return {
        "energies_eV": np.array(energies, dtype=float),
        "dos": np.array(dos_vals, dtype=float),
        "integrated_dos": np.array(idos_vals, dtype=float) if idos_vals else None,
        "fermi_eV": fermi_eV,
    }


_L_LABELS = ["s", "p", "d", "f", "g"]


def _parse_abinit_pdos_at(path: Path) -> dict:
    """Parse ABINIT _DOS_AT file (l-projected per-atom DOS from prtdos 3).

    Format:
        # energy(Ha)  l=0  l=1  l=2  l=3  l=4  (integral=>)  l=0  l=1  l=2  l=3  l=4
        -0.30000  0.0000  0.0000  0.0000  0.0000  0.0000  0.00  0.00  0.00  0.00  0.00

    Returns dict with energies_eV, projections (nedos, 5), integrated (nedos, 5).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    energies: list[float] = []
    proj_rows: list[list[float]] = []
    integ_rows: list[list[float]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 6:
            continue
        try:
            energy_ha = float(parts[0])
            ldos = [float(x) for x in parts[1:6]]
            energies.append(energy_ha * HA_TO_EV)
            # Convert DOS from states/Ha to states/eV
            proj_rows.append([v / HA_TO_EV for v in ldos])
            if len(parts) >= 11:
                integ_rows.append([float(x) for x in parts[6:11]])
        except ValueError:
            continue

    return {
        "energies_eV": np.array(energies, dtype=float),
        "projections": np.array(proj_rows, dtype=float),
        "integrated": np.array(integ_rows, dtype=float) if integ_rows else None,
    }


def _extract_fermi_from_abo(abo_path: Path) -> Optional[float]:
    """Extract Fermi energy from ABINIT .abo output file. Returns eV."""
    text = abo_path.read_text(encoding="utf-8", errors="replace")
    patterns = [
        r"Fermi\s*\(or\s+HOMO\)\s*energy\s*\(hartree\)\s*=\s*([-\d.E+]+)",
        r"Fermi\s+energy\s*\(hartree\)\s*=\s*([-\d.E+]+)",
        r"mu\s*=\s*([-\d.E+]+)\s*Hartree",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1)) * HA_TO_EV
            except ValueError:
                continue
    return None


@register_parser("abinit", "dos")
class ABINITDOSProvider:
    """Parse ABINIT DOS outputs into a canonical DOS object."""

    engine = "abinit"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        # Accept *_DOS (total) or *_DOS_TOTAL (prtdos 3 total file)
        return bool(list(raw_dir.glob("*_DOS")) or list(raw_dir.glob("*_DOS_TOTAL")))

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse ABINIT _DOS file and return engine-agnostic DOS."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        dos_at_files = sorted(raw_dir.glob("*_DOS_AT*"))
        dos_files = sorted(raw_dir.glob("*_DOS"))
        dos_total_files = sorted(raw_dir.glob("*_DOS_TOTAL"))

        # Prefer *_DOS (standard total DOS) over *_DOS_TOTAL (prtdos 3 variant)
        if dos_files:
            total_dos_file = dos_files[0]
        elif dos_total_files:
            total_dos_file = dos_total_files[0]
        else:
            raise FileNotFoundError(f"No ABINIT _DOS or _DOS_TOTAL file found in {raw_dir}")

        parsed = _parse_abinit_dos(total_dos_file)
        source_files = [SourceFileStat.from_path(total_dos_file, evidence.calc_dir)]
        nedos = len(parsed["energies_eV"])

        # Fermi energy: prefer DOS header, fallback to .abo
        fermi_energy: Optional[float] = parsed.get("fermi_eV")
        abo_files = sorted(raw_dir.glob("*.abo"))
        if abo_files:
            abo_file = abo_files[0]
            source_files.append(SourceFileStat.from_path(abo_file, evidence.calc_dir))
            if fermi_energy is None:
                fermi_energy = _extract_fermi_from_abo(abo_file)

        if fermi_energy is None:
            warnings.append("No Fermi energy found in ABINIT output.")

        # PDOS: parse _DOS_AT files if present (from prtdos 3)
        pdos: Optional[np.ndarray] = None
        atom_labels: Optional[list[str]] = None
        orbital_labels: Optional[list[str]] = None

        if dos_at_files:
            per_atom_data: list[np.ndarray] = []
            for at_file in dos_at_files:
                source_files.append(SourceFileStat.from_path(at_file, evidence.calc_dir))
                at_parsed = _parse_abinit_pdos_at(at_file)
                per_atom_data.append(at_parsed["projections"])  # (nedos_pdos, 5)

            if per_atom_data:
                # Stack into (n_atoms, nedos_pdos, 5)
                pdos_full = np.stack(per_atom_data, axis=0)

                # Verify grid matches total DOS
                if pdos_full.shape[1] != nedos:
                    warnings.append(
                        f"PDOS grid ({pdos_full.shape[1]}) != total DOS grid ({nedos}); "
                        "skipping PDOS."
                    )
                else:
                    # Determine active l-channels (any non-zero across all atoms)
                    max_l_plus_1 = pdos_full.shape[2]
                    active_mask = np.any(pdos_full > 1e-12, axis=(0, 1))
                    n_active = int(np.sum(active_mask))
                    if n_active == 0:
                        n_active = min(2, max_l_plus_1)  # at least s, p
                        active_mask[:n_active] = True

                    pdos = pdos_full[:, :, :n_active]
                    orbital_labels = _L_LABELS[:n_active]

                    # Atom labels: extract index from filename pattern _DOS_AT####
                    atom_labels = []
                    for at_file in dos_at_files:
                        # e.g. si_pdoso_DS2_DOS_AT0001 -> atom_1
                        match = re.search(r"_DOS_AT(\d+)", at_file.name)
                        if match:
                            atom_labels.append(f"atom_{int(match.group(1))}")
                        else:
                            atom_labels.append(f"atom_{len(atom_labels) + 1}")

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="abinit_dos",
            parser_version="1.0",
            warnings=warnings,
        )

        return DOS(
            meta=meta,
            energies=parsed["energies_eV"],
            total_dos=parsed["dos"],
            fermi_energy=fermi_energy,
            integrated_dos=parsed["integrated_dos"],
            spin_polarized=False,
            pdos=pdos,
            atom_labels=atom_labels,
            orbital_labels=orbital_labels,
        )
