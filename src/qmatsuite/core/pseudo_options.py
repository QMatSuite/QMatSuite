"""
Pseudo options generation for UI selection (sha256-keyed, filename-first, constitution-compliant).

This module provides functions to generate pseudo options per element,
with sha256 as the primary selection key (not sha_family).

**Selection Model:**
- UI selection key = sha256 (strict bytes identity)
- Default selection priority: project filename → internal filename → lib
- sha_family is secondary: used only for warnings and collision handling

**Options Structure:**
- Grouped by (element, basename)
- Each basename has variants[] keyed by sha256
- sha_family included per variant for warnings/collision detection
- "project_local_unknown" variant when project has basename not in internal/lib index

**Constitution:**
- Only 3 sources (project, internal, lib) - no caches beyond existing LRU
- Family-match edge case: If project has same basename with family-match but sha256 differs,
  show SEPARATE entries (don't merge)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from qmatsuite.core.pseudo import get_system_pseudo_dir
from qmatsuite.core.pseudo_config import load_pseudo_config
from qmatsuite.core.paths import home_pseudo_libraries_dir
from qmatsuite.core.pseudo_libinfo import (
    compute_sha_family_file,
    load_pseudo_libinfo_bundle,
)
from qmatsuite.core.pseudo_provenance import (
    _build_occurrences_index,
    _create_occurrence_ref,
    _extract_element_from_filename,
    compute_sha256_file,
    parse_element_from_upf_text,
)


def _find_upf_in_libraries(filename: str) -> Path | None:
    """Find a UPF file by name in installed pseudo libraries (NEW layout)."""
    from qmatsuite.pseudo.layout import find_upf_in_libraries

    return find_upf_in_libraries(home_pseudo_libraries_dir(), filename)


def _find_upf_by_sha256_in_libraries(sha256: str) -> Path | None:
    """Find a UPF file by SHA256 in installed pseudo libraries (NEW layout)."""
    from qmatsuite.pseudo.layout import iter_installed_libraries

    libraries_root = home_pseudo_libraries_dir()
    for lib in iter_installed_libraries(libraries_root):
        for f in lib.install_dir.iterdir():
            if f.suffix.lower() == ".upf" and f.is_file():
                try:
                    if compute_sha256_file(f) == sha256:
                        return f
                except Exception:
                    continue
    return None


@dataclass
class PseudoSource:
    """A source chip for a pseudo option (constitution: only 3 sources)."""
    kind: str  # "project", "internal", "lib"
    label: str  # Human-readable label
    installed: bool
    corrupt: bool = False  # True if archive exists but SHA256 mismatch
    warning: Optional[str] = None  # Warning message (e.g., "needs reinstall")
    archive_asset: Optional[str] = None  # For library sources
    library_name: Optional[str] = None  # For lib sources
    library_version: Optional[str] = None  # For lib sources


@dataclass
class PseudoVariant:
    """
    A single pseudo variant keyed by sha256 (primary selection identity).
    
    Each variant represents a unique (element, basename, sha256) combination.
    sha_family is included for warnings and collision detection only.
    """
    sha256: str  # Primary selection key
    sha_family: str  # For warnings/collision detection
    basename: str
    element: str
    sources: List[PseudoSource] = field(default_factory=list)
    size_bytes: Optional[int] = None
    upf_format: Optional[str] = None
    is_project_local_unknown: bool = False  # True if project has this basename but sha256 not in index
    family_match_warnings: List[str] = field(default_factory=list)  # Warnings about family matches with different sha256
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "sha_family": self.sha_family,
            "basename": self.basename,
            "element": self.element,
            "sources": [
                {
                    "kind": s.kind,
                    "label": s.label,
                    "installed": s.installed,
                    "corrupt": s.corrupt,
                    "warning": s.warning,
                    "archive_asset": s.archive_asset,
                    "library_name": s.library_name,
                    "library_version": s.library_version,
                }
                for s in self.sources
            ],
            "size_bytes": self.size_bytes,
            "upf_format": self.upf_format,
            "is_project_local_unknown": self.is_project_local_unknown,
            "family_match_warnings": self.family_match_warnings,
            "display_label": self._compute_display_label(),
            "availability": {
                "any_installed": any(s.installed and not s.corrupt for s in self.sources),
            },
        }
    
    def _compute_display_label(self) -> str:
        """Compute display label for this variant."""
        if self.is_project_local_unknown:
            return f"{self.element}: {self.basename} (project-local)"
        return f"{self.element}: {self.basename}"


# Legacy PseudoOption kept for backward compatibility
@dataclass
class PseudoOption:
    """Legacy: A single pseudo option (deduplicated by SHA256)."""
    sha256: str
    sha_family: str
    element: str
    display_basename: str
    all_basenames: List[str]
    sources: List[PseudoSource]
    availability: Dict[str, bool] = field(default_factory=lambda: {"any_installed": False})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "sha_family": self.sha_family,
            "element": self.element,
            "display_basename": self.display_basename,
            "all_basenames": self.all_basenames,
            "sources": [
                {
                    "kind": s.kind,
                    "label": s.label,
                    "installed": s.installed,
                    "corrupt": s.corrupt,
                    "warning": s.warning,
                    "archive_asset": s.archive_asset,
                }
                for s in self.sources
            ],
            "availability": self.availability,
        }


def _format_library_label(occ: Dict) -> str:
    """Format a human-readable label for a library occurrence."""
    library = occ.get("library", {})
    archive = occ.get("archive", {})
    
    library_name = (library.get("library_name") or "").upper()
    library_version = library.get("library_version") or ""
    xc = (library.get("xc") or "").upper()
    quality = library.get("quality") or ""
    type_val = library.get("type", "")
    relativistic = library.get("relativistic", "")
    
    parts = [library_name]
    if library_version:
        parts.append(library_version)
    if xc:
        parts.append(xc)
    if quality:
        parts.append(quality)
    if type_val:
        parts.append(type_val)
    if relativistic:
        parts.append(relativistic)
    
    return " ".join(parts)


@lru_cache(maxsize=32)
def _scan_pseudo_dir_cached(
    dir_path: str,
    element: str,
    dir_mtime: float,
    dir_size: int,
) -> Tuple[Tuple[str, str, str], ...]:
    """
    Cached pseudo directory scan.
    
    Cache key includes mtime and size to invalidate on changes.
    Returns tuple of (file_path, sha256, basename) tuples.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    pseudo_dir = Path(dir_path)
    if not pseudo_dir.exists():
        logger.info(f"[PSEUDO_SCAN] Directory does not exist: {pseudo_dir}")
        return ()
    
    logger.info(f"[PSEUDO_SCAN] Scanning directory: {pseudo_dir}")
    results = []
    
    # Scan case-insensitively: check both .UPF and .upf patterns
    # Also check for any case variation
    found_files = set()
    for pattern in ["*.UPF", "*.upf", "*.Upf", "*.uPf", "*.upF", "*.UPf", "*.uPF", "*.UpF"]:
        for pseudo_file in pseudo_dir.glob(pattern):
            if not pseudo_file.is_file():
                continue
            # Avoid duplicates (case-insensitive matching)
            if pseudo_file.name.lower() in found_files:
                continue
            found_files.add(pseudo_file.name.lower())
            try:
                sha256 = compute_sha256_file(pseudo_file)
                results.append((str(pseudo_file), sha256, pseudo_file.name))
            except Exception as e:
                logger.warning(f"[PSEUDO_SCAN] Failed to compute SHA256 for {pseudo_file}: {e}")
                continue
    
    logger.info(
        f"[PSEUDO_SCAN] Found {len(results)} pseudo files in {pseudo_dir}: "
        f"{[r[2] for r in results]}"
    )
    return tuple(results)


def get_pseudo_options_for_elements(
    project_root: Path,
    elements: List[str],
    config: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get deduplicated pseudo options for a list of elements (sha256-keyed, filename-first).
    
    Options are keyed by sha256. Each variant shows:
    - Basename
    - Sources (project/internal/lib) with installed/corrupt status
    - sha_family for warnings/collision detection
    - Family-match warnings when project has same basename with family-match but sha256 differs
    
    Default selection priority: project filename → internal filename → lib
    
    Args:
        project_root: Project root path
        elements: List of element symbols
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict mapping element -> List[PseudoVariant dict] (sha256-keyed)
    """
    from qmatsuite.core.pseudo_config import PseudoConfig

    if config is None:
        config = load_pseudo_config()

    import logging
    logger = logging.getLogger(__name__)

    project_root = Path(project_root).resolve()
    project_pseudo_dir = project_root / "pseudo"
    internal_pseudo_dir = get_system_pseudo_dir()

    logger.info(
        f"[PSEUDO_SCAN] Starting scan: project_pseudo_dir={project_pseudo_dir}, "
        f"internal_pseudo_dir={internal_pseudo_dir}, elements={elements}"
    )

    # Load bundle and build indices
    bundle = load_pseudo_libinfo_bundle()
    occurrences_index = _build_occurrences_index(bundle)
    files_index = {f.get("sha256"): f for f in bundle.index.get("files", [])}
    
    # Build variants by element -> sha256 (primary key)
    variants_by_element: Dict[str, Dict[str, PseudoVariant]] = {}
    
    # Track project files by (element, basename) for family-match detection
    project_files_by_element_basename: Dict[Tuple[str, str], Tuple[str, str, Path]] = {}  # (element, basename) -> (sha256, sha_family, path)
    
    # Initialize per element
    for element in elements:
        variants_by_element[element] = {}
    
    # Helper: Get or create variant for sha256
    def get_or_create_variant(element: str, sha256: str, basename: str, sha_family: str) -> PseudoVariant:
        if sha256 not in variants_by_element[element]:
            variants_by_element[element][sha256] = PseudoVariant(
                sha256=sha256,
                sha_family=sha_family,
                basename=basename,
                element=element,
            )
        return variants_by_element[element][sha256]
    
    # Scan project pseudos (with caching)
    if project_pseudo_dir.exists():
        try:
            dir_stat = project_pseudo_dir.stat()
            cached_files = _scan_pseudo_dir_cached(
                str(project_pseudo_dir),
                "",
                dir_stat.st_mtime,
                dir_stat.st_size,
            )
        except Exception:
            cached_files = []
        
        for file_path_str, sha256, basename in cached_files:
            pseudo_file = Path(file_path_str)
            if not pseudo_file.exists():
                continue
            
            try:
                # Compute sha_family (not cached)
                sha_family = compute_sha_family_file(pseudo_file)
                
                # Parse element
                try:
                    text = pseudo_file.read_text(encoding="utf-8", errors="replace")
                    element = parse_element_from_upf_text(text)
                except Exception:
                    element = None
                
                if element is None:
                    element = _extract_element_from_filename(basename)
                
                if not element or element not in elements:
                    continue
                
                # Track project file for family-match detection
                project_files_by_element_basename[(element, basename)] = (sha256, sha_family, pseudo_file)
                
                # Check if sha256 is in index (known variant)
                if sha256 in files_index:
                    # Known variant: create/update variant
                    variant = get_or_create_variant(element, sha256, basename, sha_family)
                    
                    # Add project source chip
                    project_source = PseudoSource(
                        kind="project",
                        label="Project",
                        installed=True,  # Always installed if file exists
                    )
                    variant.sources.append(project_source)
                    
                    # Add library chips from occurrences
                    if sha256 in occurrences_index:
                        for occ in occurrences_index[sha256]:
                            library = occ.get("library", {})
                            path_in_archive = occ.get("path_in_archive", "")
                            occ_basename = Path(path_in_archive).name if path_in_archive else ""

                            # Check if this file exists in installed libraries
                            lib_file = _find_upf_in_libraries(occ_basename) if occ_basename else None
                            installed = lib_file is not None

                            label = _format_library_label(occ)
                            lib_source = PseudoSource(
                                kind="lib",
                                label=label,
                                installed=installed,
                                library_name=library.get("library_name"),
                                library_version=library.get("library_version"),
                            )
                            variant.sources.append(lib_source)
                else:
                    # Unknown variant: project-local file not in index
                    variant = get_or_create_variant(element, sha256, basename, sha_family)
                    variant.is_project_local_unknown = True
                    
                    # Add project source chip
                    project_source = PseudoSource(
                        kind="project",
                        label="Project",
                        installed=True,
                        warning="not recognized by internal/lib (no provenance)",
                    )
                    variant.sources.append(project_source)
                
            except Exception:
                continue
    
    # Scan internal pseudos
    if internal_pseudo_dir and internal_pseudo_dir.exists():
        logger.info(f"[PSEUDO_SCAN] Scanning internal pseudo directory: {internal_pseudo_dir}")
        found_files = set()
        # Scan case-insensitively: check all case variations
        for pattern in ["*.UPF", "*.upf", "*.Upf", "*.uPf", "*.upF", "*.UPf", "*.uPF", "*.UpF"]:
            for pseudo_file in internal_pseudo_dir.glob(pattern):
                if not pseudo_file.is_file():
                    continue
                # Avoid duplicates (case-insensitive matching)
                if pseudo_file.name.lower() in found_files:
                    continue
                found_files.add(pseudo_file.name.lower())
                
                try:
                    sha256 = compute_sha256_file(pseudo_file)
                    sha_family = compute_sha_family_file(pseudo_file)
                    
                    try:
                        text = pseudo_file.read_text(encoding="utf-8", errors="replace")
                        element = parse_element_from_upf_text(text)
                    except Exception:
                        element = None
                    
                    if element is None:
                        element = _extract_element_from_filename(pseudo_file.name)
                    
                    if not element or element not in elements:
                        continue
                    
                    # Create/update variant
                    variant = get_or_create_variant(element, sha256, pseudo_file.name, sha_family)
                    
                    # Add internal source chip (if not already present)
                    has_internal = any(s.kind == "internal" for s in variant.sources)
                    if not has_internal:
                        internal_source = PseudoSource(
                            kind="internal",
                            label="Internal",
                            installed=True,  # Always installed if file exists
                        )
                        variant.sources.append(internal_source)
                    
                    # Check for family-match with project file (different sha256)
                    project_key = (element, pseudo_file.name)
                    if project_key in project_files_by_element_basename:
                        proj_sha256, proj_sha_family, proj_path = project_files_by_element_basename[project_key]
                        if proj_sha_family == sha_family and proj_sha256 != sha256:
                            # Family match but sha256 differs: add warning to internal variant
                            variant.family_match_warnings.append(
                                f"project has same filename with family-match but different bytes; selecting this will overwrite on Run"
                            )
                            # Also add warning to project variant if it exists
                            if proj_sha256 in variants_by_element[element]:
                                proj_variant = variants_by_element[element][proj_sha256]
                                proj_variant.family_match_warnings.append(
                                    f"family matches internal (bytes differ)"
                                )
                except Exception as e:
                    logger.warning(f"[PSEUDO_SCAN] Failed to process {pseudo_file}: {e}")
                    continue
        logger.info(
            f"[PSEUDO_SCAN] Found {len(found_files)} internal pseudo files in {internal_pseudo_dir}"
        )
    else:
        logger.info(f"[PSEUDO_SCAN] Internal pseudo directory does not exist: {internal_pseudo_dir}")
    
    # Add library chips for all variants (after scanning project and internal)
    for element in elements:
        for sha256, variant in variants_by_element[element].items():
            # Add library chips if sha256 matches index
            if sha256 in occurrences_index:
                for occ in occurrences_index[sha256]:
                    library = occ.get("library", {})
                    path_in_archive = occ.get("path_in_archive", "")
                    occ_basename = Path(path_in_archive).name if path_in_archive else ""

                    # Check if file exists in installed libraries
                    lib_file = _find_upf_in_libraries(occ_basename) if occ_basename else None
                    installed = lib_file is not None

                    label = _format_library_label(occ)
                    lib_source = PseudoSource(
                        kind="lib",
                        label=label,
                        installed=installed,
                        library_name=library.get("library_name"),
                        library_version=library.get("library_version"),
                    )
                    variant.sources.append(lib_source)
    
    # Add library-only variants (from index, not in project/internal)
    for file_entry in bundle.index.get("files", []):
        file_sha256 = file_entry.get("sha256")
        file_sha_family = file_entry.get("sha_family", "")
        basenames = file_entry.get("basenames", [])
        
        if not file_sha256 or not file_sha_family:
            continue
        
        # Try to infer element from basenames
        element = None
        for basename in basenames:
            inferred = _extract_element_from_filename(basename)
            if inferred and inferred in elements:
                element = inferred
                break
        
        if not element:
            continue
        
        # Check if this sha256 is already in variants (from project/internal scan)
        if file_sha256 not in variants_by_element[element]:
            # New library-only variant
            canonical_basename = basenames[0] if basenames else f"{element}.upf"
            variant = get_or_create_variant(element, file_sha256, canonical_basename, file_sha_family)
            
            # Add library chips
            if file_sha256 in occurrences_index:
                for occ in occurrences_index[file_sha256]:
                    library = occ.get("library", {})
                    path_in_archive = occ.get("path_in_archive", "")
                    occ_basename = Path(path_in_archive).name if path_in_archive else ""

                    lib_file = _find_upf_in_libraries(occ_basename) if occ_basename else None
                    installed = lib_file is not None

                    label = _format_library_label(occ)
                    lib_source = PseudoSource(
                        kind="lib",
                        label=label,
                        installed=installed,
                        library_name=library.get("library_name"),
                        library_version=library.get("library_version"),
                    )
                    variant.sources.append(lib_source)
    
    # Finalize: sort variants by default selection priority (project → internal → lib)
    result: Dict[str, List[Dict[str, Any]]] = {}
    
    for element in elements:
        variants = list(variants_by_element[element].values())
        
        # Sort by default selection priority:
        # 1. Project source (if present)
        # 2. Internal source (if present)
        # 3. Installed lib sources
        # 4. Available lib sources
        def sort_key(v: PseudoVariant) -> tuple:
            has_project = any(s.kind == "project" and s.installed for s in v.sources)
            has_internal = any(s.kind == "internal" and s.installed for s in v.sources)
            any_installed_lib = any(s.kind == "lib" and s.installed and not s.corrupt for s in v.sources)
            any_available_lib = any(s.kind == "lib" for s in v.sources)
            
            return (
                not has_project,  # Project first
                not has_internal,  # Then internal
                not any_installed_lib,  # Then installed lib
                not any_available_lib,  # Then available lib
                v.basename,  # Then by basename
            )
        
        variants.sort(key=sort_key)
        result[element] = [v.to_dict() for v in variants]
    
    # Final summary log
    total_variants = sum(len(variants) for variants in result.values())
    logger.info(
        f"[PSEUDO_SCAN] Scan complete: total_variants={total_variants}, "
        f"elements_with_options={[e for e, v in result.items() if len(v) > 0]}"
    )
    
    return result


def materialize_pseudo_file(
    project_root: Path,
    element: str,
    sha256: str,
    preferred_basename: Optional[str] = None,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Materialize a pseudo file from sha256 selection to actual file path.
    
    Resolution order:
    1. project_root/pseudo (if file exists and sha256 matches)
    2. resources/pseudo (internal) (if file exists and sha256 matches)
    3. Installed archive extraction (if archive is installed and extracted)
    
    Args:
        project_root: Project root path
        element: Element symbol
        sha256: SHA256 hash of the pseudo file
        preferred_basename: Preferred basename (for display/filename)
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict with:
        - success: bool
        - file_path: Optional[str] - Path to materialized file
        - source: Optional[str] - "project", "internal", or "library"
        - error: Optional[str] - Error message if materialization failed
        - needs_install: bool - True if archive needs to be installed
        - archive_asset: Optional[str] - Archive that needs installation
    """
    from qmatsuite.core.pseudo_config import PseudoConfig, load_pseudo_config
    
    if config is None:
        config = load_pseudo_config()
    
    result: Dict[str, Any] = {
        "success": False,
        "file_path": None,
        "source": None,
        "error": None,
        "needs_install": False,
        "archive_asset": None,
    }
    
    project_root = Path(project_root).resolve()
    project_pseudo_dir = project_root / "pseudo"
    internal_pseudo_dir = get_system_pseudo_dir()
    
    # Load bundle to find occurrences
    bundle = load_pseudo_libinfo_bundle()
    occurrences_index = _build_occurrences_index(bundle)
    
    # 1. Check project pseudo dir
    if project_pseudo_dir.exists():
        for pseudo_file in project_pseudo_dir.glob("*.UPF"):
            if not pseudo_file.is_file():
                continue
            try:
                file_sha256 = compute_sha256_file(pseudo_file)
                if file_sha256 == sha256:
                    result["success"] = True
                    result["file_path"] = str(pseudo_file)
                    result["source"] = "project"
                    return result
            except Exception:
                continue
        
        for pseudo_file in project_pseudo_dir.glob("*.upf"):
            if not pseudo_file.is_file():
                continue
            try:
                file_sha256 = compute_sha256_file(pseudo_file)
                if file_sha256 == sha256:
                    result["success"] = True
                    result["file_path"] = str(pseudo_file)
                    result["source"] = "project"
                    return result
            except Exception:
                continue
    
    # 2. Check internal pseudo dir
    if internal_pseudo_dir and internal_pseudo_dir.exists():
        for pseudo_file in internal_pseudo_dir.glob("*.UPF"):
            if not pseudo_file.is_file():
                continue
            try:
                file_sha256 = compute_sha256_file(pseudo_file)
                if file_sha256 == sha256:
                    result["success"] = True
                    result["file_path"] = str(pseudo_file)
                    result["source"] = "internal"
                    return result
            except Exception:
                continue
        
        for pseudo_file in internal_pseudo_dir.glob("*.upf"):
            if not pseudo_file.is_file():
                continue
            try:
                file_sha256 = compute_sha256_file(pseudo_file)
                if file_sha256 == sha256:
                    result["success"] = True
                    result["file_path"] = str(pseudo_file)
                    result["source"] = "internal"
                    return result
            except Exception:
                continue
    
    # 3. Check installed libraries (NEW layout: three-level walk)
    lib_file = _find_upf_by_sha256_in_libraries(sha256)
    if lib_file:
        result["success"] = True
        result["file_path"] = str(lib_file)
        result["source"] = "library"
        return result

    # If sha256 is in index but not found in installed libraries, mark as needs install
    if sha256 in occurrences_index:
        for occ in occurrences_index[sha256]:
            archive_name = occ.get("archive", {}).get("name", "")
            result["needs_install"] = True
            result["archive_asset"] = archive_name
            break
    
    # If we get here, materialization failed
    if not result["error"]:
        if result["needs_install"]:
            result["error"] = f"Archive {result['archive_asset']} needs to be installed. Go to Settings → Pseudopotential Archives to install."
        else:
            result["error"] = f"Could not materialize pseudo file for {element} (sha256: {sha256[:16]}...). File not found in project, internal, or installed archives."
    
    return result
