"""
Analysis artifacts module.

Manages JSON artifacts for analysis data (SCF, DOS, bands).
Convention: <workflow_dir>/analysis/<type>.json

The JSON artifacts serve as:
1. Cache for expensive parsing operations
2. Primary data source for GUI plotting (via RPC)
3. Persistent storage of analysis results
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from .parsers import (
    BandStructureData,
    DOSData,
    SCFResult,
    find_bands_files,
    find_dos_files,
    parse_bands_gnu,
    parse_dos_data,
    parse_scf_output,
)


class AnalysisType(str, Enum):
    """Supported analysis types."""
    SCF = "scf"
    DOS = "dos"
    BANDS = "bands"


@dataclass
class AnalysisStatus:
    """Result of ensure_workflow_analysis operation."""
    ok: bool
    analysis_type: str
    artifact_path: Optional[str] = None
    parsed_fresh: bool = False  # True if we just parsed (vs loaded from cache)
    error: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None  # Quick summary data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "ok": self.ok,
            "analysis_type": self.analysis_type,
            "artifact_path": self.artifact_path,
            "parsed_fresh": self.parsed_fresh,
            "error": self.error,
            "summary": self.summary,
        }


def get_analysis_dir(workflow_dir: Path) -> Path:
    """
    Get the analysis artifacts directory for a workflow.
    
    Convention: <workflow_dir>/analysis/
    
    Args:
        workflow_dir: Path to workflow directory
        
    Returns:
        Path to analysis directory (may not exist yet)
    """
    return workflow_dir / "analysis"


def get_artifact_path(
    workflow_dir: Path,
    analysis_type: Union[AnalysisType, str],
) -> Path:
    """
    Get the path for an analysis artifact.
    
    Convention: <workflow_dir>/analysis/<type>.json
    
    Args:
        workflow_dir: Path to workflow directory
        analysis_type: Type of analysis (scf, dos, bands)
        
    Returns:
        Path to artifact file (may not exist)
    """
    if isinstance(analysis_type, str):
        analysis_type = AnalysisType(analysis_type.lower())
    
    return get_analysis_dir(workflow_dir) / f"{analysis_type.value}.json"


def artifact_exists(
    workflow_dir: Path,
    analysis_type: Union[AnalysisType, str],
) -> bool:
    """Check if an analysis artifact exists."""
    return get_artifact_path(workflow_dir, analysis_type).exists()


def read_artifact(
    workflow_dir: Path,
    analysis_type: Union[AnalysisType, str],
) -> Optional[Dict[str, Any]]:
    """
    Read an analysis artifact from disk.
    
    Args:
        workflow_dir: Path to workflow directory
        analysis_type: Type of analysis
        
    Returns:
        Parsed JSON data, or None if not found
    """
    path = get_artifact_path(workflow_dir, analysis_type)
    if not path.exists():
        return None
    
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def write_artifact(
    workflow_dir: Path,
    analysis_type: Union[AnalysisType, str],
    data: Dict[str, Any],
) -> Path:
    """
    Write an analysis artifact to disk.
    
    Args:
        workflow_dir: Path to workflow directory
        analysis_type: Type of analysis
        data: Data to write (must be JSON-serializable)
        
    Returns:
        Path to written artifact
    """
    analysis_dir = get_analysis_dir(workflow_dir)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    path = get_artifact_path(workflow_dir, analysis_type)
    
    # Add metadata
    data["_artifact_meta"] = {
        "analysis_type": str(analysis_type.value if isinstance(analysis_type, AnalysisType) else analysis_type),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "qv_version": "2.0.0",  # TODO: Get from package
    }
    
    path.write_text(json.dumps(data, indent=2))
    return path


def delete_artifact(
    workflow_dir: Path,
    analysis_type: Union[AnalysisType, str],
) -> bool:
    """
    Delete an analysis artifact.
    
    Args:
        workflow_dir: Path to workflow directory
        analysis_type: Type of analysis
        
    Returns:
        True if deleted, False if didn't exist
    """
    path = get_artifact_path(workflow_dir, analysis_type)
    if path.exists():
        path.unlink()
        return True
    return False


def clear_analysis_artifacts(workflow_dir: Path) -> int:
    """
    Clear all analysis artifacts for a workflow.
    
    Used when a workflow is re-run to invalidate cached analysis.
    
    Args:
        workflow_dir: Path to workflow directory
        
    Returns:
        Number of artifacts deleted
    """
    analysis_dir = get_analysis_dir(workflow_dir)
    if not analysis_dir.exists():
        return 0
    
    deleted = 0
    for analysis_type in AnalysisType:
        if delete_artifact(workflow_dir, analysis_type):
            deleted += 1
    
    return deleted


# =============================================================================
# Analysis Type -> Required Files/Steps Mapping
# =============================================================================

def get_required_files_for_analysis(
    analysis_type: Union[AnalysisType, str],
    raw_dir: Path,
    step_selector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map analysis type to required QE output files.
    
    Args:
        analysis_type: Type of analysis
        raw_dir: Workflow raw directory
        step_selector: Optional step selector for SCF
        
    Returns:
        Dict with 'found' bool and file paths
    """
    if isinstance(analysis_type, str):
        analysis_type = AnalysisType(analysis_type.lower())
    
    result: Dict[str, Any] = {
        "found": False,
        "analysis_type": analysis_type.value,
        "files": {},
        "missing": [],
    }
    
    if analysis_type == AnalysisType.SCF:
        # Look for SCF/NSCF output files
        patterns = ["*scf*.out", "*nscf*.out", "*.pw.out"]
        if step_selector:
            patterns = [f"{step_selector}*.out", f"*{step_selector}*.out"] + patterns
        
        for pattern in patterns:
            matches = list(raw_dir.glob(pattern))
            if matches:
                result["files"]["scf_output"] = str(matches[0])
                result["found"] = True
                break
        
        if not result["found"]:
            result["missing"].append("SCF output file (*.out)")
    
    elif analysis_type == AnalysisType.DOS:
        # Look for DOS data files
        dos_files = find_dos_files(raw_dir)
        if dos_files.get("dos_dat"):
            result["files"]["dos_data"] = str(dos_files["dos_dat"])
            result["found"] = True
        else:
            result["missing"].append("DOS data file (*.dos.dat)")
        
        # Optional: SCF output for Fermi energy
        if dos_files.get("scf_out") or dos_files.get("nscf_out"):
            result["files"]["scf_output"] = str(dos_files.get("nscf_out") or dos_files.get("scf_out"))
    
    elif analysis_type == AnalysisType.BANDS:
        # Look for band structure files
        bands_files = find_bands_files(raw_dir)
        if bands_files.get("bands_gnu"):
            result["files"]["bands_gnu"] = str(bands_files["bands_gnu"])
            result["found"] = True
        else:
            result["missing"].append("Bands data file (*.dat.gnu)")
        
        # Optional files for better analysis
        if bands_files.get("bands_out"):
            result["files"]["bands_pp_out"] = str(bands_files["bands_out"])
        if bands_files.get("scf_out"):
            result["files"]["scf_output"] = str(bands_files["scf_out"])
        if bands_files.get("nscf_out"):
            result["files"]["nscf_output"] = str(bands_files["nscf_out"])
    
    return result


# =============================================================================
# Core Parsing Functions
# =============================================================================

def parse_and_write_scf_artifact(
    workflow_dir: Path,
    raw_dir: Path,
    step_selector: Optional[str] = None,
    force: bool = False,
) -> AnalysisStatus:
    """
    Parse SCF output and write artifact.
    
    Args:
        workflow_dir: Workflow directory
        raw_dir: Raw directory with QE outputs
        step_selector: Optional step selector
        force: Force re-parse even if artifact exists
        
    Returns:
        AnalysisStatus with result
    """
    artifact_path = get_artifact_path(workflow_dir, AnalysisType.SCF)
    
    # Check for existing artifact
    if not force and artifact_path.exists():
        existing = read_artifact(workflow_dir, AnalysisType.SCF)
        if existing:
            return AnalysisStatus(
                ok=True,
                analysis_type="scf",
                artifact_path=str(artifact_path),
                parsed_fresh=False,
                summary={
                    "converged": existing.get("converged"),
                    "n_iterations": len(existing.get("iterations", [])),
                    "total_energy_ry": existing.get("total_energy_ry"),
                    "fermi_energy_ev": existing.get("fermi_energy_ev"),
                },
            )
    
    # Find required files
    file_info = get_required_files_for_analysis(AnalysisType.SCF, raw_dir, step_selector)
    if not file_info["found"]:
        return AnalysisStatus(
            ok=False,
            analysis_type="scf",
            error=f"Missing required files: {', '.join(file_info['missing'])}",
        )
    
    # Parse SCF output
    try:
        scf_output = Path(file_info["files"]["scf_output"])
        scf_result = parse_scf_output(scf_output)
        
        # Convert to dict and add metadata
        data = scf_result.to_dict()
        data["workflow_dir"] = str(workflow_dir)
        data["source_file"] = str(scf_output)
        
        # Write artifact
        write_artifact(workflow_dir, AnalysisType.SCF, data)
        
        return AnalysisStatus(
            ok=True,
            analysis_type="scf",
            artifact_path=str(artifact_path),
            parsed_fresh=True,
            summary={
                "converged": scf_result.converged,
                "n_iterations": len(scf_result.iterations),
                "total_energy_ry": scf_result.total_energy,
                "fermi_energy_ev": scf_result.fermi_energy,
            },
        )
    except Exception as e:
        return AnalysisStatus(
            ok=False,
            analysis_type="scf",
            error=f"Failed to parse SCF output: {e}",
        )


def parse_and_write_dos_artifact(
    workflow_dir: Path,
    raw_dir: Path,
    step_selector: Optional[str] = None,
    force: bool = False,
) -> AnalysisStatus:
    """
    Parse DOS data and write artifact.
    
    Args:
        workflow_dir: Workflow directory
        raw_dir: Raw directory with QE outputs
        step_selector: Optional step selector
        force: Force re-parse even if artifact exists
        
    Returns:
        AnalysisStatus with result
    """
    artifact_path = get_artifact_path(workflow_dir, AnalysisType.DOS)
    
    # Check for existing artifact
    if not force and artifact_path.exists():
        existing = read_artifact(workflow_dir, AnalysisType.DOS)
        if existing:
            return AnalysisStatus(
                ok=True,
                analysis_type="dos",
                artifact_path=str(artifact_path),
                parsed_fresh=False,
                summary={
                    "n_points": existing.get("n_points"),
                    "fermi_energy_ev": existing.get("fermi_energy_ev"),
                    "energy_range_ev": existing.get("energy_range_ev"),
                },
            )
    
    # Find required files
    file_info = get_required_files_for_analysis(AnalysisType.DOS, raw_dir, step_selector)
    if not file_info["found"]:
        return AnalysisStatus(
            ok=False,
            analysis_type="dos",
            error=f"Missing required files: {', '.join(file_info['missing'])}",
        )
    
    # Parse DOS data
    try:
        dos_file = Path(file_info["files"]["dos_data"])
        dos_data = parse_dos_data(dos_file)
        
        # Try to get Fermi energy from SCF/NSCF if not in DOS header
        if dos_data.fermi_energy is None and file_info["files"].get("scf_output"):
            try:
                scf_result = parse_scf_output(file_info["files"]["scf_output"])
                dos_data = DOSData(
                    energies=dos_data.energies,
                    dos=dos_data.dos,
                    idos=dos_data.idos,
                    fermi_energy=scf_result.fermi_energy,
                )
            except Exception:
                pass
        
        # Convert to dict and add metadata
        data = dos_data.to_dict()
        data["workflow_dir"] = str(workflow_dir)
        data["source_file"] = str(dos_file)
        
        # Write artifact
        write_artifact(workflow_dir, AnalysisType.DOS, data)
        
        return AnalysisStatus(
            ok=True,
            analysis_type="dos",
            artifact_path=str(artifact_path),
            parsed_fresh=True,
            summary={
                "n_points": len(dos_data.energies),
                "fermi_energy_ev": dos_data.fermi_energy,
                "energy_range_ev": [float(dos_data.energies.min()), float(dos_data.energies.max())],
            },
        )
    except Exception as e:
        return AnalysisStatus(
            ok=False,
            analysis_type="dos",
            error=f"Failed to parse DOS data: {e}",
        )


def parse_and_write_bands_artifact(
    workflow_dir: Path,
    raw_dir: Path,
    step_selector: Optional[str] = None,
    force: bool = False,
) -> AnalysisStatus:
    """
    Parse band structure data and write artifact.
    
    Args:
        workflow_dir: Workflow directory
        raw_dir: Raw directory with QE outputs
        step_selector: Optional step selector
        force: Force re-parse even if artifact exists
        
    Returns:
        AnalysisStatus with result
    """
    artifact_path = get_artifact_path(workflow_dir, AnalysisType.BANDS)
    
    # Check for existing artifact
    if not force and artifact_path.exists():
        existing = read_artifact(workflow_dir, AnalysisType.BANDS)
        if existing:
            return AnalysisStatus(
                ok=True,
                analysis_type="bands",
                artifact_path=str(artifact_path),
                parsed_fresh=False,
                summary={
                    "n_bands": existing.get("n_bands"),
                    "n_kpoints": existing.get("n_kpoints"),
                    "fermi_energy_ev": existing.get("fermi_energy_ev"),
                    "n_high_symmetry_points": len(existing.get("high_symmetry_points", [])),
                },
            )
    
    # Find required files
    file_info = get_required_files_for_analysis(AnalysisType.BANDS, raw_dir, step_selector)
    if not file_info["found"]:
        return AnalysisStatus(
            ok=False,
            analysis_type="bands",
            error=f"Missing required files: {', '.join(file_info['missing'])}",
        )
    
    # Parse band structure
    try:
        bands_file = Path(file_info["files"]["bands_gnu"])
        
        # Get Fermi energy from pw.x output
        fermi_energy = None
        pw_output = None
        
        # Prefer NSCF over SCF for Fermi energy
        if file_info["files"].get("nscf_output"):
            pw_output = Path(file_info["files"]["nscf_output"])
        elif file_info["files"].get("scf_output"):
            pw_output = Path(file_info["files"]["scf_output"])
        
        if pw_output and pw_output.exists():
            try:
                scf_result = parse_scf_output(pw_output)
                fermi_energy = scf_result.fermi_energy
            except Exception:
                pass
        
        # Parse bands
        symmetry_file = None
        if file_info["files"].get("bands_pp_out"):
            symmetry_file = Path(file_info["files"]["bands_pp_out"])
        
        band_data = parse_bands_gnu(
            bands_file,
            symmetry_file=symmetry_file,
            fermi_energy=fermi_energy,
            pw_output_file=pw_output,
        )
        
        # Convert to dict and add metadata
        data = band_data.to_dict()
        data["workflow_dir"] = str(workflow_dir)
        data["source_file"] = str(bands_file)
        
        # Write artifact
        write_artifact(workflow_dir, AnalysisType.BANDS, data)
        
        return AnalysisStatus(
            ok=True,
            analysis_type="bands",
            artifact_path=str(artifact_path),
            parsed_fresh=True,
            summary={
                "n_bands": band_data.n_bands,
                "n_kpoints": band_data.n_kpoints,
                "fermi_energy_ev": band_data.fermi_energy,
                "n_high_symmetry_points": len(band_data.high_symmetry_points),
            },
        )
    except Exception as e:
        return AnalysisStatus(
            ok=False,
            analysis_type="bands",
            error=f"Failed to parse band structure: {e}",
        )


def ensure_analysis_artifact(
    analysis_type: Union[AnalysisType, str],
    workflow_dir: Path,
    raw_dir: Path,
    step_selector: Optional[str] = None,
    force: bool = False,
) -> AnalysisStatus:
    """
    Ensure an analysis artifact exists, parsing if necessary.
    
    This is the main entry point for the analysis pipeline.
    
    Args:
        analysis_type: Type of analysis (scf, dos, bands)
        workflow_dir: Workflow directory
        raw_dir: Raw directory with QE outputs
        step_selector: Optional step selector (for SCF)
        force: Force re-parse even if artifact exists
        
    Returns:
        AnalysisStatus with result
    """
    if isinstance(analysis_type, str):
        analysis_type = AnalysisType(analysis_type.lower())
    
    if analysis_type == AnalysisType.SCF:
        return parse_and_write_scf_artifact(workflow_dir, raw_dir, step_selector, force)
    elif analysis_type == AnalysisType.DOS:
        return parse_and_write_dos_artifact(workflow_dir, raw_dir, step_selector, force)
    elif analysis_type == AnalysisType.BANDS:
        return parse_and_write_bands_artifact(workflow_dir, raw_dir, step_selector, force)
    else:
        return AnalysisStatus(
            ok=False,
            analysis_type=str(analysis_type),
            error=f"Unsupported analysis type: {analysis_type}",
        )

