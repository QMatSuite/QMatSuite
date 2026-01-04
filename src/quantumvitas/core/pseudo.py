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
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> PseudoResolutionResult:
    """
    Canonical entry point for QE pseudopotential resolution.
    
    This is the single, authoritative function for all pseudopotential resolution logic.
    All new code should use this function directly.
    
    This function handles all pseudopotential resolution logic:
    1. Determines required pseudopotential filenames:
       - PRIMARY SOURCE: If species_map is provided, use it as source of truth (calculation-level authority)
       - FALLBACK: Extract from QE input ATOMIC_SPECIES (for standalone/legacy cases)
    2. For each required pseudo:
       - First checks project_pseudo_dir (use if exists)
       - Then checks system_pseudo_dir (copy to project if found)
       - Then checks additional_search_dirs (test fixtures, env vars, etc.)
       - Downloads if not found (unless strict=True, then fails early)
    3. Returns result with project_pseudo_dir path and resolved pseudo mapping
    
    Args:
        qe_input_file: Path to QE input file (parsed to extract required pseudos if species_map not provided)
        project_pseudo_dir: Directory for project/run-specific pseudos (e.g., project_root/pseudo or workdir/pseudo)
        system_pseudo_dir: Optional system-wide pseudo cache directory. If None, uses quantumvitas resources/pseudo
        strict: If True, do not attempt network download; fail early if pseudo not found locally
        additional_search_dirs: Optional list of additional directories to search (e.g., test fixtures)
        species_map: Optional calculation-level species_map (element -> {pseudopot/pseudo_basename, mass, ...}).
                    If provided, this is used as the PRIMARY source for pseudo filenames, and QE input parsing
                    is only used as a fallback/legacy path. This ensures calculation.yaml species_map is honored.
    
    Returns:
        PseudoResolutionResult with project_pseudo_dir, resolved pseudos, and availability status
    
    The project_pseudo_dir should be used to set pseudo_dir in the QE input file.
    All required pseudopotentials will be copied into this directory, making the project/run self-contained.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Safety check: ensure qe_input_file is a valid file, not '.' or directory
    qe_input_path = Path(qe_input_file)
    qe_input_path_resolved = qe_input_path.resolve()
    
    logger.debug(f"[ENSURE_QE_PSEUDOS] qe_input_file: {qe_input_file}")
    logger.debug(f"[ENSURE_QE_PSEUDOS] qe_input_path_resolved: {qe_input_path_resolved}")
    
    # Check for invalid paths
    if str(qe_input_path) in (".", "./", "..") or str(qe_input_path_resolved) == ".":
        logger.error(f"[ENSURE_QE_PSEUDOS] ERROR: qe_input_file is '.' or invalid: '{qe_input_file}'")
        raise ValueError(
            f"Invalid qe_input_file for ensure_qe_pseudos: '{qe_input_file}'. "
            f"Cannot be '.' or a directory. This usually indicates a path resolution bug."
        )
    
    if qe_input_path_resolved.exists() and qe_input_path_resolved.is_dir():
        logger.error(f"[ENSURE_QE_PSEUDOS] ERROR: qe_input_file is a directory: {qe_input_path_resolved}")
        raise ValueError(
            f"qe_input_file is a directory: {qe_input_path_resolved}. "
            f"Must be a file path. This usually indicates a path resolution bug."
        )
    
    # Parse QE input to extract required elements from ATOMIC_SPECIES
    # Only parse if species_map is not provided (use QE input as fallback)
    qe_input = None
    atomic_species = None
    if not species_map:
        logger.debug(f"[ENSURE_QE_PSEUDOS] Parsing QE input file (no species_map provided)")
        qe_input = QEInputParser.parse_file(qe_input_path_resolved)
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    else:
        logger.debug(f"[ENSURE_QE_PSEUDOS] Using species_map as primary source (skipping QE input parsing)")
        # For Wannier90 steps (pw2wannier90, etc.), we may not have a valid QE input file to parse
        # Only parse if file exists and is not a Wannier90 file (for fallback element detection)
        # But species_map takes precedence, so parsing is optional here
        try:
            if qe_input_path_resolved.exists() and qe_input_path_resolved.is_file():
                # Only try to parse if it looks like a QE input file
                if qe_input_path_resolved.suffix in (".in", "") and "wannier90" not in str(qe_input_path_resolved).lower():
                    qe_input = QEInputParser.parse_file(qe_input_path_resolved)
                    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
                    logger.debug(f"[ENSURE_QE_PSEUDOS] Parsed QE input for fallback (species_map provided)")
        except Exception as e:
            logger.debug(f"[ENSURE_QE_PSEUDOS] Could not parse QE input (non-fatal, using species_map): {e}")
    
    # Extract required elements from ATOMIC_SPECIES
    required_elements: List[str] = []
    if atomic_species and atomic_species.data:
        for line in atomic_species.data:
            if isinstance(line, list) and len(line) >= 1:
                element_symbol = str(line[0]).strip()
                if element_symbol and element_symbol not in required_elements:
                    required_elements.append(element_symbol)
    
    # Determine required pseudopotential filenames
    # RESOLUTION PRECEDENCE:
    # 1. If species_map is provided, use it as PRIMARY source (calculation-level authority)
    # 2. Otherwise, parse from QE input ATOMIC_SPECIES (legacy/standalone path)
    required_pps: List[str] = []  # element -> pseudo filename mapping
    element_to_pseudo: Dict[str, str] = {}
    missing_placeholders: List[str] = []
    
    if species_map and required_elements:
        # PRIMARY PATH: Use calculation-level species_map as source of truth
        for element in required_elements:
            entry = species_map.get(element)
            if not isinstance(entry, dict):
                missing_placeholders.append(element)
                continue
            
            # Get pseudo filename from species_map (prefer pseudo_basename, fallback to pseudopot)
            pseudo_filename = entry.get("pseudo_basename") or entry.get("pseudopot")
            if not pseudo_filename:
                missing_placeholders.append(element)
            elif is_missing_pseudo_placeholder(pseudo_filename):
                # Placeholder in species_map - treat as missing configuration
                missing_placeholders.append(element)
            else:
                # Valid pseudo filename from species_map
                element_to_pseudo[element] = pseudo_filename
                if pseudo_filename not in required_pps:
                    required_pps.append(pseudo_filename)
    else:
        # FALLBACK PATH: Parse from QE input ATOMIC_SPECIES (legacy/standalone)
        if atomic_species and atomic_species.data:
            for line in atomic_species.data:
                if isinstance(line, list) and len(line) >= 3:
                    pp_name = str(line[2]).strip() if line[2] else ""
                    element_symbol = str(line[0]).strip() if line[0] else "unknown"
                    
                    if not pp_name:
                        # Empty or missing pseudopotential - treat as missing configuration
                        missing_placeholders.append(element_symbol)
                    elif is_missing_pseudo_placeholder(pp_name):
                        # Explicit placeholder indicating missing configuration
                        element_symbol_from_placeholder = pp_name.replace("__MISSING_PSEUDO__", "")
                        missing_placeholders.append(element_symbol_from_placeholder)
                    else:
                        # Real pseudopotential filename from QE input
                        element_to_pseudo[element_symbol] = pp_name
                        if pp_name not in required_pps:
                            required_pps.append(pp_name)
    
    # Fail early with clear configuration error if placeholders or empty pseudos are found
    if missing_placeholders:
        elements_str = ", ".join(sorted(set(missing_placeholders)))
        first_element = elements_str.split(",")[0].strip()
        
        # Diagnostic logging before raise
        import logging
        logger = logging.getLogger(__name__)
        
        # Try to extract calculation context from qe_input_file path
        # Pattern: calculations/<calc>/raw/... or calculations/<calc>/steps/...
        calc_context = {}
        try:
            qe_input_path = Path(qe_input_file).resolve()
            parts = qe_input_path.parts
            if "calculations" in parts:
                calc_idx = parts.index("calculations")
                if calc_idx + 1 < len(parts):
                    calc_dir = Path(*parts[:calc_idx+2])
                    calc_yaml = calc_dir / "calculation.yaml"
                    if calc_yaml.exists():
                        # Try to load calculation for context
                        repo_root = _find_quantumvitas_root()
                        if repo_root:
                            project_root = None
                            # Find project root (parent of calculations)
                            if calc_idx > 0:
                                potential_project = Path(*parts[:calc_idx])
                                if (potential_project / "project.qv.yml").exists():
                                    project_root = potential_project
                            
                            if project_root:
                                from quantumvitas.core.models import load_calculation
                                from quantumvitas.core.resolution import make_structure_selector_resolver
                                from quantumvitas.core.project_utils import load_project_config
                                try:
                                    config = load_project_config(project_root)
                                    resolver = make_structure_selector_resolver(project_root, config=config)
                                    calc_model = load_calculation(calc_yaml, project_root=project_root, resolve_structure_selector=resolver)
                                    calc_context["calculation_path"] = str(calc_yaml)
                                    if calc_model.species_map:
                                        calc_context["species_map_keys"] = list(calc_model.species_map.keys())
                                        calc_context["element_pseudopot_values"] = {
                                            elem: entry.get("pseudopot", "") if isinstance(entry, dict) else ""
                                            for elem, entry in calc_model.species_map.items()
                                        }
                                    if calc_model.structure_id:
                                        from quantumvitas.core.resolution import resolve_structure
                                        try:
                                            struct_resolved = resolve_structure(project_root, calc_model.structure_id, config=config)
                                            calc_context["structure_path"] = str(struct_resolved.absolute_path)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
        except Exception:
            pass
        
        # Diagnostic logging before raise
        source_type = "species_map (PRIMARY)" if species_map else "QE input ATOMIC_SPECIES (legacy/standalone)"
        logger.error(
            f"[PSEUDO_CONFIG_ERROR] Pseudopotential not configured for element(s): {elements_str}\n"
            f"  Resolution source: {source_type}\n"
            f"  qe_input_file={qe_input_file}\n"
            f"  project_pseudo_dir={project_pseudo_dir}\n"
            f"  system_pseudo_dir={system_pseudo_dir}\n"
            f"  required_pps={required_pps}\n"
            f"  required_elements={required_elements}\n"
            f"  missing_placeholders={missing_placeholders}\n"
            f"  element_to_pseudo={element_to_pseudo}\n"
            f"  project_pseudo_dir.exists()={project_pseudo_dir.exists()}\n"
            f"  calculation_path={calc_context.get('calculation_path', 'N/A')}\n"
            f"  structure_path={calc_context.get('structure_path', 'N/A')}\n"
            f"  species_map_keys={calc_context.get('species_map_keys', [])}\n"
            f"  element_pseudopot_values={calc_context.get('element_pseudopot_values', {})}\n"
            f"  species_map_provided={'Yes' if species_map else 'No'}\n"
            f"  species_map_keys_provided={list(species_map.keys()) if species_map else []}"
        )
        
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
            system_pseudo_dir = qv_root / "resources" / "pseudo"
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
    # GUARD: Never create repo_root/pseudo for project_pseudo_dir
    qv_root = _find_quantumvitas_root()
    if qv_root:
        project_resolved = project_pseudo_dir.resolve()
        repo_pseudo = (qv_root / "pseudo").resolve()
        if project_resolved == repo_pseudo:
            raise RuntimeError(
                f"BUG: ensure_qe_pseudos attempted to create repo_root/pseudo at {project_pseudo_dir}. "
                f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo. "
                f"Caller should use output_dir/pseudo or a temp directory instead."
            )
    
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    # system_pseudo_dir (resources/pseudo) should already exist in repo - don't mkdir it
    # Only mkdir if it's a user-configured system directory outside the repo
    if system_pseudo_dir:
        # GUARD: Never create repo_root/pseudo for system_pseudo_dir
        if qv_root and system_pseudo_dir.resolve() == (qv_root / "pseudo").resolve():
            raise RuntimeError(
                f"BUG: Attempted to create repo_root/pseudo at {system_pseudo_dir}. "
                f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo."
            )
        # Only mkdir system_pseudo_dir if it's outside the repo (user-configured)
        # The repo-internal resources/pseudo should already exist and should not be created
        if not qv_root or not system_pseudo_dir.resolve().is_relative_to(qv_root.resolve()):
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
    
    # After resolution, if any required pseudos are missing and we're in strict mode, raise error
    if strict and not all_available:
        missing_files = [pp_name for pp_name in required_pps if pp_name not in resolved_pseudos]
        if missing_files:
            # Extract element symbols from filenames for better error message
            missing_elements = set()
            for pp_name in missing_files:
                element = pp_name.split(".")[0] if "." in pp_name else "unknown"
                missing_elements.add(element)
            
            elements_str = ", ".join(sorted(missing_elements))
            files_str = ", ".join(missing_files)
            search_locations = [str(project_pseudo_dir)]
            if system_pseudo_dir:
                search_locations.append(str(system_pseudo_dir))
            if search_dirs:
                search_locations.extend(str(d) for d in search_dirs)
            locations_str = ", ".join(search_locations)
            
            raise FileNotFoundError(
                f"Pseudopotential file(s) not found for element(s): {elements_str}. "
                f"Missing files: {files_str}. "
                f"Searched in: {locations_str}. "
                f"Please ensure the pseudopotential files are available in one of these locations."
            )
    
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
        Path to quantumvitas resources/pseudo, or None if quantumvitas root not found
    """
    qv_root = _find_quantumvitas_root()
    if qv_root:
        return qv_root / "resources" / "pseudo"
    return None

