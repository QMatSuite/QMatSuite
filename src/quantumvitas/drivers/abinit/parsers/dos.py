"""ABINIT DOS analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

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
        return bool(list(raw_dir.glob("*_DOS")))

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse ABINIT _DOS file and return engine-agnostic DOS."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        dos_files = sorted(raw_dir.glob("*_DOS"))
        if not dos_files:
            raise FileNotFoundError(f"No ABINIT _DOS file found in {raw_dir}")
        dos_file = dos_files[0]

        parsed = _parse_abinit_dos(dos_file)
        source_files = [SourceFileStat.from_path(dos_file, evidence.calc_dir)]

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
        )
