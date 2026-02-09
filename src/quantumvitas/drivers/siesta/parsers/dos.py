"""Siesta DOS analysis provider."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.siesta.parser import parse_dos_file, parse_main_output, parse_pdos_xml
from quantumvitas.parsers.registry import register_parser


@register_parser("siesta", "dos")
class SiestaDOSProvider:
    """Parse Siesta DOS outputs into a canonical DOS object."""

    engine = "siesta"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.DOS")))

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse Siesta .DOS file and return engine-agnostic DOS."""
        raw_dir = evidence.primary_raw_dir

        dos_files = sorted(raw_dir.glob("*.DOS"))
        if not dos_files:
            raise FileNotFoundError(f"No Siesta .DOS file found in {raw_dir}")
        dos_file = dos_files[0]

        warnings: list[str] = []
        source_files = [SourceFileStat.from_path(dos_file, evidence.calc_dir)]

        # Parse total DOS
        dos_data = parse_dos_file(dos_file)
        energies = np.array(dos_data["energies_eV"], dtype=float)
        total_dos = np.array(dos_data["dos"], dtype=float)

        # Get Fermi energy from .out file
        fermi_energy: Optional[float] = None
        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            out_file = out_files[0]
            source_files.append(SourceFileStat.from_path(out_file, evidence.calc_dir))
            try:
                out_data = parse_main_output(out_file)
                fermi_energy = out_data.get("fermi_energy_eV")
            except Exception:
                warnings.append(f"Failed to parse Fermi energy from {out_file.name}")

        if fermi_energy is None:
            warnings.append("No Fermi energy found in Siesta output.")

        # Parse PDOS from .PDOS.xml if available
        pdos = None
        atom_labels = None
        orbital_labels = None

        pdos_xml_files = sorted(raw_dir.glob("*.PDOS.xml"))
        if pdos_xml_files:
            pdos_xml_file = pdos_xml_files[0]
            source_files.append(SourceFileStat.from_path(pdos_xml_file, evidence.calc_dir))
            try:
                pdos_result = self._parse_pdos_xml(pdos_xml_file)
                if pdos_result is not None:
                    pdos = pdos_result["pdos"]
                    atom_labels = pdos_result["atom_labels"]
                    orbital_labels = pdos_result["orbital_labels"]
                    # Use Fermi from PDOS.xml if not found in .out
                    if fermi_energy is None and pdos_result.get("fermi_energy") is not None:
                        fermi_energy = pdos_result["fermi_energy"]
                        warnings = [w for w in warnings if "No Fermi" not in w]
            except Exception:
                warnings.append(f"Failed to parse PDOS from {pdos_xml_file.name}")

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="siesta_dos",
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

    def _parse_pdos_xml(self, pdos_xml_path: Path) -> Optional[dict]:
        """Parse Siesta .PDOS.xml into (n_atoms, nedos, n_orbitals) array."""
        pdos_data = parse_pdos_xml(pdos_xml_path)

        orbitals = pdos_data.get("orbitals", [])
        if not orbitals:
            return None

        n_energy = pdos_data["n_energy_points"]
        fermi_eV = pdos_data.get("fermi_energy_eV")

        # Group orbitals by atom (using atom_index from attribs)
        atom_orbital_map: dict[str, dict] = {}  # "Symbol_index" -> {orbitals: {l_name: data}}

        # Map angular momentum quantum numbers to labels
        l_to_name = {0: "s", 1: "p", 2: "d", 3: "f"}

        for orb in orbitals:
            atom_index = orb.get("atom_index", orb.get("index", "?"))
            species = orb.get("species", "X")
            l_val = int(orb.get("l", 0))
            orb_name = l_to_name.get(l_val, f"l{l_val}")

            key = f"{species}_{atom_index}"
            if key not in atom_orbital_map:
                atom_orbital_map[key] = {"species": species, "orbitals": {}}

            data = orb.get("data", [])
            if not data:
                continue

            # Accumulate: if same atom has multiple orbitals of same l, sum them
            if orb_name in atom_orbital_map[key]["orbitals"]:
                existing = atom_orbital_map[key]["orbitals"][orb_name]
                for i in range(min(len(existing), len(data))):
                    existing[i] += data[i]
            else:
                atom_orbital_map[key]["orbitals"][orb_name] = list(data)

        if not atom_orbital_map:
            return None

        # Collect unique orbital labels
        all_orb_names: list[str] = []
        for key in sorted(atom_orbital_map.keys()):
            for oname in atom_orbital_map[key]["orbitals"]:
                if oname not in all_orb_names:
                    all_orb_names.append(oname)

        n_atoms = len(atom_orbital_map)
        n_orbitals = len(all_orb_names)

        pdos_array = np.zeros((n_atoms, n_energy, n_orbitals), dtype=float)
        atom_labels: list[str] = []
        counts: dict[str, int] = {}

        for ai, key in enumerate(sorted(atom_orbital_map.keys())):
            species = atom_orbital_map[key]["species"]
            counts[species] = counts.get(species, 0) + 1
            atom_labels.append(f"{species}_{counts[species]}")

            for oi, oname in enumerate(all_orb_names):
                data = atom_orbital_map[key]["orbitals"].get(oname)
                if data is not None:
                    usable = min(len(data), n_energy)
                    pdos_array[ai, :usable, oi] = data[:usable]

        return {
            "pdos": pdos_array,
            "atom_labels": atom_labels,
            "orbital_labels": all_orb_names,
            "fermi_energy": fermi_eV,
        }
