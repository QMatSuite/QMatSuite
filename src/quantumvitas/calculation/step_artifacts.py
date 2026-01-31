"""
Step artifacts recognition rules.

Defines which files should be recognized as artifacts for each step type,
and which one should be the default for GUI display.
"""
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path


def _get_wannier90_seedname(params: Dict[str, Any]) -> Optional[str]:
    """Extract seedname from step parameters (supports nested and flat structures)."""
    # Handle nested parameters
    flat_params = {}
    if isinstance(params, dict):
        for key, value in params.items():
            if isinstance(value, dict):
                flat_params.update(value)
            else:
                flat_params[key] = value
    
    return flat_params.get("seedname")


def _get_bands_filband(params: Dict[str, Any]) -> Optional[str]:
    """Extract filband from step parameters (supports nested and flat structures)."""
    flat_params = {}
    if isinstance(params, dict):
        for key, value in params.items():
            if isinstance(value, dict):
                flat_params.update(value)
            else:
                flat_params[key] = value
    
    # filband might be in BANDS namelist or at top level
    bands_params = flat_params.get("bands", {})
    if isinstance(bands_params, dict):
        filband = bands_params.get("filband")
        if filband:
            return filband
    
    return flat_params.get("filband")


# Artifact rule functions: (step_type_spec, params, raw_dir) -> List[str]
# Returns list of artifact filenames (just names, not paths)
ArtifactRule = Callable[[str, Dict[str, Any], Path], List[str]]


def _wannierprep_artifacts(step_type_spec: str, params: Dict[str, Any], raw_dir: Path) -> List[str]:
    """Artifacts for wannierprep step."""
    seedname = _get_wannier90_seedname(params)
    if not seedname:
        return []
    
    # Primary artifact: <seed>.nnkp
    return [f"{seedname}.nnkp"]


def _pw2wannier_artifacts(step_type_spec: str, params: Dict[str, Any], raw_dir: Path) -> List[str]:
    """Artifacts for pw2wannier step."""
    seedname = _get_wannier90_seedname(params)
    if not seedname:
        return []
    
    # Primary artifacts: <seed>.amn, <seed>.mmn, <seed>.eig (if they exist)
    artifacts = [
        f"{seedname}.amn",
        f"{seedname}.mmn",
        f"{seedname}.eig",
    ]
    
    # Filter to only existing files
    existing = [a for a in artifacts if (raw_dir / a).exists()]
    return existing


def _wannier_artifacts(step_type_spec: str, params: Dict[str, Any], raw_dir: Path) -> List[str]:
    """Artifacts for wannier step."""
    seedname = _get_wannier90_seedname(params)
    if not seedname:
        return []
    
    # Primary artifact: <seed>.wout (this is the main output for GUI)
    return [f"{seedname}.wout"]


def _bands_artifacts(step_type_spec: str, params: Dict[str, Any], raw_dir: Path) -> List[str]:
    """Artifacts for bands step."""
    filband = _get_bands_filband(params)
    if not filband:
        # If no filband specified, check common patterns
        # Look for files matching *.bands.dat pattern
        candidates = list(raw_dir.glob("*.bands.dat*"))
        if candidates:
            return sorted([f.name for f in candidates])
        return []
    
    # Primary artifacts: <filband>, <filband>.gnu, <filband>.rap
    # Note: filband might be a full path or just filename
    # Extract just the filename if it's a path
    filband_name = Path(filband).name if filband else None
    if not filband_name:
        return []
    
    artifacts = [
        filband_name,
        f"{filband_name}.gnu",
        f"{filband_name}.rap",
    ]
    
    # Filter to only existing files
    existing = [a for a in artifacts if (raw_dir / a).exists()]
    return existing


# Registry of artifact rules by step_type
STEP_ARTIFACT_RULES: Dict[str, ArtifactRule] = {
    "wannierprep": _wannierprep_artifacts,
    "pw2wannier": _pw2wannier_artifacts,
    "wannier": _wannier_artifacts,
    "bands": _bands_artifacts,
}


def get_step_artifacts(
    step_type_spec: str,
    params: Dict[str, Any],
    raw_dir: Path,
) -> List[str]:
    """
    Get list of artifact filenames for a step type.
    
    Args:
        step_type_spec: Spec step type (e.g., "w90_wannier", "qe_bands")
        params: Step parameters (may be nested or flat)
        raw_dir: Raw directory where artifacts are stored
        
    Returns:
        List of artifact filenames (just names, not full paths)
    """
    rule = STEP_ARTIFACT_RULES.get(step_type_spec.lower())
    if not rule:
        return []
    
    try:
        return rule(step_type_spec, params, raw_dir)
    except Exception:
        # If rule fails, return empty list (graceful degradation)
        return []


def get_default_artifact(
    step_type_spec: str,
    params: Dict[str, Any],
    raw_dir: Path,
    artifacts_list: List[str],
) -> Optional[str]:
    """
    Determine the default artifact for GUI display.
    
    Priority:
    1. Primary artifact from step-specific rule (e.g., wannier's .wout, bands' .gnu)
    2. Fallback to {step_type_spec}.out if it exists
    3. None if no suitable default
    
    Args:
        step_type_spec: Spec step type (e.g., "qe_scf", "w90_wannier")
        params: Step parameters
        raw_dir: Raw directory
        artifacts_list: List of artifact filenames that exist
        
    Returns:
        Default artifact filename (or None)
    """
    # Step 1: Get primary artifacts from rule
    rule = STEP_ARTIFACT_RULES.get(step_type_spec.lower())
    if rule:
        try:
            primary_artifacts = rule(step_type_spec, params, raw_dir)
            
            # Special handling for bands: prefer .gnu over .dat
            if step_type_spec.lower() == "bands":
                # First, try to find .gnu file
                for artifact in primary_artifacts:
                    if artifact.endswith(".gnu") and artifact in artifacts_list:
                        artifact_path = raw_dir / artifact
                        if artifact_path.exists() and artifact_path.stat().st_size > 0:
                            return artifact
                # Then try .dat file
                for artifact in primary_artifacts:
                    if artifact.endswith(".dat") and artifact in artifacts_list:
                        artifact_path = raw_dir / artifact
                        if artifact_path.exists() and artifact_path.stat().st_size > 0:
                            return artifact
                # Finally, any other primary artifact
                for artifact in primary_artifacts:
                    if artifact in artifacts_list:
                        artifact_path = raw_dir / artifact
                        if artifact_path.exists() and artifact_path.stat().st_size > 0:
                            return artifact
                # Last resort: any primary artifact even if empty
                for artifact in primary_artifacts:
                    if artifact in artifacts_list:
                        return artifact
            else:
                # For other step types, find first primary artifact that exists and is not empty
                non_empty_primary = None
                for artifact in primary_artifacts:
                    if artifact in artifacts_list:
                        artifact_path = raw_dir / artifact
                        if artifact_path.exists():
                            # Prefer non-empty files
                            if artifact_path.stat().st_size > 0:
                                return artifact
                            # Remember first primary artifact even if empty (as fallback)
                            if non_empty_primary is None:
                                non_empty_primary = artifact
                
                # If we have a primary artifact (even if empty), use it only if no stdout available
                stdout_file = f"{step_type_spec}.out"
                if stdout_file in artifacts_list:
                    stdout_path = raw_dir / stdout_file
                    if stdout_path.exists() and stdout_path.stat().st_size > 0:
                        # Prefer non-empty stdout over empty primary
                        return stdout_file
                
                # Last resort: use primary artifact even if empty
                if non_empty_primary:
                    return non_empty_primary
        except Exception:
            pass
    
    # Step 2: Fallback to {step_type_spec}.out
    stdout_file = f"{step_type_spec}.out"
    if stdout_file in artifacts_list:
        stdout_path = raw_dir / stdout_file
        if stdout_path.exists() and stdout_path.stat().st_size > 0:
            return stdout_file
    
    # Step 3: No default
    return None

