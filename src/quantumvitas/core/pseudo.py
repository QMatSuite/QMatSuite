"""
Central pseudopotential resolution and management for QE runs.

This module provides a single, well-defined entry point for pseudopotential
handling used by both project-based and standalone QE runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict

from quantumvitas.io import QEInputParser, QECardType
from quantumvitas.core.engines.qe_pseudopotentials import (
    download_pseudopotential,
    _find_quantumvitas_root,
)


def make_missing_pseudo_placeholder(symbol: str) -> str:
    """
    Create an obvious placeholder name for missing pseudopotentials.
    
    This placeholder clearly indicates that no pseudopotential was configured,
    distinguishing configuration errors from missing file errors.
    
    Args:
        symbol: Element symbol (e.g., "Si", "C")
        
    Returns:
        Placeholder filename like "__MISSING_PSEUDO__Si"
    """
    return f"__MISSING_PSEUDO__{symbol}"


def is_missing_pseudo_placeholder(pp_name: str) -> bool:
    """
    Check if a pseudopotential name is a missing placeholder.
    
    Args:
        pp_name: Pseudopotential filename to check
        
    Returns:
        True if this is a placeholder indicating missing configuration
    """
    return pp_name.startswith("__MISSING_PSEUDO__")


@dataclass
class PseudoResolutionResult:
    """
    Result of pseudopotential resolution.
    
    Attributes:
        project_pseudo_dir: Path to the project/run pseudo directory (where pseudos are copied)
        system_pseudo_dir: Path to the system-wide pseudo cache directory
        resolved_pseudos: Mapping of pseudo filename -> path in project_pseudo_dir
        all_available: True if all required pseudos were successfully resolved
    """
    project_pseudo_dir: Path
    system_pseudo_dir: Optional[Path]
    resolved_pseudos: Dict[str, Path]
    all_available: bool


def ensure_qe_pseudos(
    qe_input_file: Path,
    project_pseudo_dir: Path,
    system_pseudo_dir: Optional[Path] = None,
    strict: bool = False,
    additional_search_dirs: Optional[List[Path]] = None,
) -> PseudoResolutionResult:
    """
    Canonical entry point for QE pseudopotential resolution.
    
    This is the single, authoritative function for all pseudopotential resolution logic.
    All new code should use this function directly.
    
    This function handles all pseudopotential resolution logic:
    1. Extracts required pseudopotential filenames from QE input
    2. For each required pseudo:
       - First checks project_pseudo_dir (use if exists)
       - Then checks system_pseudo_dir (copy to project if found)
       - Then checks additional_search_dirs (test fixtures, env vars, etc.)
       - Downloads if not found (unless strict=True, then fails early)
    3. Returns result with project_pseudo_dir path and resolved pseudo mapping
    
    Args:
        qe_input_file: Path to QE input file (parsed to extract required pseudos)
        project_pseudo_dir: Directory for project/run-specific pseudos (e.g., project_root/pseudo or workdir/pseudo)
        system_pseudo_dir: Optional system-wide pseudo cache directory. If None, uses quantumvitas root/pseudo
        strict: If True, do not attempt network download; fail early if pseudo not found locally
        additional_search_dirs: Optional list of additional directories to search (e.g., test fixtures)
    
    Returns:
        PseudoResolutionResult with project_pseudo_dir, resolved pseudos, and availability status
    
    The project_pseudo_dir should be used to set pseudo_dir in the QE input file.
    All required pseudopotentials will be copied into this directory, making the project/run self-contained.
    """
    # Parse QE input to extract required pseudopotentials
    qe_input = QEInputParser.parse_file(qe_input_file)
    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    
    required_pps: List[str] = []
    missing_placeholders: List[str] = []
    if atomic_species and atomic_species.data:
        for line in atomic_species.data:
            if isinstance(line, list) and len(line) >= 3:
                pp_name = str(line[2]).strip() if line[2] else ""
                element_symbol = str(line[0]).strip() if line[0] else "unknown"
                
                if not pp_name:
                    # Empty or missing pseudopotential - treat as missing configuration
                    # Placeholder semantics: __MISSING_PSEUDO__X = configuration error (not a file error)
                    missing_placeholders.append(element_symbol)
                elif is_missing_pseudo_placeholder(pp_name):
                    # Explicit placeholder indicating missing configuration
                    # Placeholder semantics: __MISSING_PSEUDO__X = configuration error (not a file error)
                    element_symbol = pp_name.replace("__MISSING_PSEUDO__", "")
                    missing_placeholders.append(element_symbol)
                else:
                    # Real pseudopotential filename (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF")
                    # If this filename cannot be found, it's a missing-file error (not configuration)
                    required_pps.append(pp_name)
    
    # Fail early with clear configuration error if placeholders or empty pseudos are found
    if missing_placeholders:
        elements_str = ", ".join(sorted(set(missing_placeholders)))
        first_element = elements_str.split(",")[0].strip()
        raise ValueError(
            f"Pseudopotential not configured for element(s): {elements_str}. "
            f"This is a configuration error, not a missing file. "
            f"Please configure pseudopotentials using:\n"
            f"  - CLI: --SPECIES.{first_element}.pseudopot=<filename>\n"
            f"  - Step spec: species_overrides['{first_element}'] = {{'pseudopot': '<filename>'}}\n"
            f"  - Or import from existing QE input that has ATOMIC_SPECIES with pseudopotential filenames"
        )
    
    # If no pseudos needed, return success
    if not required_pps:
        project_pseudo_dir.mkdir(parents=True, exist_ok=True)
        return PseudoResolutionResult(
            project_pseudo_dir=project_pseudo_dir,
            system_pseudo_dir=system_pseudo_dir,
            resolved_pseudos={},
            all_available=True,
        )
    
    # Resolve system pseudo directory if not provided
    if system_pseudo_dir is None:
        qv_root = _find_quantumvitas_root()
        if qv_root:
            system_pseudo_dir = qv_root / "pseudo"
        else:
            system_pseudo_dir = None
    
    # Build additional search directories list
    search_dirs: List[Path] = []
    
    # Add test fixture directories if quantumvitas root is found
    if additional_search_dirs:
        search_dirs.extend(additional_search_dirs)
    else:
        # Auto-detect test fixture directories
        qv_root = _find_quantumvitas_root()
        if qv_root:
            # Check for tests/data/pseudo or tests/data/pseudos
            test_data_pseudo = qv_root / "tests" / "data" / "pseudo"
            test_data_pseudos = qv_root / "tests" / "data" / "pseudos"
            if test_data_pseudo.exists():
                search_dirs.append(test_data_pseudo)
            if test_data_pseudos.exists():
                search_dirs.append(test_data_pseudos)
            # Also check tests/data for loose pseudo files
            test_data_dir = qv_root / "tests" / "data"
            if test_data_dir.exists():
                search_dirs.append(test_data_dir)
    
    # Check environment variable QV_PSEUDO_PATH
    import os
    env_pseudo_path = os.environ.get("QV_PSEUDO_PATH")
    if env_pseudo_path:
        env_path = Path(env_pseudo_path)
        if env_path.exists() and env_path.is_dir():
            search_dirs.append(env_path)
    
    # Ensure directories exist
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    if system_pseudo_dir:
        system_pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    # Resolve each required pseudopotential
    resolved_pseudos: Dict[str, Path] = {}
    all_available = True
    
    for pp_name in required_pps:
        project_pp_path = project_pseudo_dir / pp_name
        
        # 1. Check project pseudo directory first
        if project_pp_path.exists():
            resolved_pseudos[pp_name] = project_pp_path
            continue
        
        # 2. Check system pseudo directory, copy to project if found
        if system_pseudo_dir and system_pseudo_dir.exists():
            system_pp_path = system_pseudo_dir / pp_name
            if system_pp_path.exists():
                # Copy to project pseudo directory for self-containment
                import shutil
                shutil.copy2(system_pp_path, project_pp_path)
                resolved_pseudos[pp_name] = project_pp_path
                continue
        
        # 3. Check additional search directories (test fixtures, env vars, etc.)
        found_in_search = False
        for search_dir in search_dirs:
            if search_dir.exists():
                candidate = search_dir / pp_name
                if candidate.exists():
                    # Copy to project pseudo directory for self-containment
                    import shutil
                    shutil.copy2(candidate, project_pp_path)
                    resolved_pseudos[pp_name] = project_pp_path
                    found_in_search = True
                    break
        
        if found_in_search:
            continue
        
        # 4. Download if not found in any location (unless strict mode)
        if strict:
            # In strict mode, fail early if pseudo not found locally
            all_available = False
            continue
        
        # Download to system cache first (if available), then copy to project
        download_target = system_pseudo_dir if system_pseudo_dir else project_pseudo_dir
        
        if download_pseudopotential(pp_name, download_target):
            # Copy to project pseudo directory for self-containment
            if download_target != project_pseudo_dir:
                source_pp = download_target / pp_name
                if source_pp.exists():
                    import shutil
                    shutil.copy2(source_pp, project_pp_path)
                    resolved_pseudos[pp_name] = project_pp_path
                else:
                    # Download went to project_pseudo_dir directly
                    resolved_pseudos[pp_name] = project_pp_path
            else:
                # Downloaded directly to project_pseudo_dir
                resolved_pseudos[pp_name] = project_pp_path
        else:
            # Download failed - this is a missing file error (not configuration)
            # The pseudopotential was configured (real filename present) but the file
            # cannot be found locally or downloaded. This is different from a configuration
            # error (which would have __MISSING_PSEUDO__ placeholder or empty pseudo name).
            all_available = False
    
    return PseudoResolutionResult(
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=system_pseudo_dir,
        resolved_pseudos=resolved_pseudos,
        all_available=all_available,
    )


def get_system_pseudo_dir() -> Optional[Path]:
    """
    Get the system-wide pseudopotential cache directory.
    
    Returns:
        Path to quantumvitas root/pseudo, or None if quantumvitas root not found
    """
    qv_root = _find_quantumvitas_root()
    if qv_root:
        return qv_root / "pseudo"
    return None

