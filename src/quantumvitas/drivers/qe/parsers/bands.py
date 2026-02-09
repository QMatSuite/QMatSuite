"""QE bands analysis provider."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from quantumvitas.analysis.parsers import parse_bands_gnu, parse_scf_output
from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser


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
            eigenvalues=np.array(band_data.energies, copy=True).T,
            high_symmetry_points=[
                HighSymPoint(k_distance=point.k_distance, label=point.label)
                for point in band_data.high_symmetry_points
            ],
            fermi_energy=band_data.fermi_energy,
            spin_polarized=False,
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
