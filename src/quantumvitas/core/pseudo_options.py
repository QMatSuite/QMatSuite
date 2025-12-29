"""
Pseudo options generation for UI selection (sha256-keyed, filename-first, constitution-compliant).

This module provides functions to generate pseudo options per element,
with sha256 as the primary selection key (not sha_token).

**Selection Model:**
- UI selection key = sha256 (strict bytes identity)
- Default selection priority: project filename → internal filename → lib
- sha_token is secondary: used only for warnings and collision handling

**Options Structure:**
- Grouped by (element, basename)
- Each basename has variants[] keyed by sha256
- sha_token included per variant for warnings/collision detection
- "project_local_unknown" variant when project has basename not in internal/lib index

**Constitution:**
- Only 3 sources (project, internal, lib) - no caches beyond existing LRU
- Token-match edge case: If project has same basename with token-match but sha256 differs,
  show SEPARATE entries (don't merge)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from quantumvitas.core.pseudo import get_system_pseudo_dir
from quantumvitas.core.pseudo_config import load_pseudo_config
from quantumvitas.core.pseudo_installs import (
    is_archive_installed,
    load_manifest_archives,
)
from quantumvitas.core.pseudo_libinfo import (
    compute_sha_token_file,
    load_pseudo_libinfo_bundle,
)
from quantumvitas.core.pseudo_provenance import (
    _build_occurrences_index,
    _create_occurrence_ref,
    _extract_element_from_filename,
    compute_sha256_file,
    parse_element_from_upf_text,
)


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
    sha_token is included for warnings and collision detection only.
    """
    sha256: str  # Primary selection key
    sha_token: str  # For warnings/collision detection
    basename: str
    element: str
    sources: List[PseudoSource] = field(default_factory=list)
    size_bytes: Optional[int] = None
    upf_format: Optional[str] = None
    is_project_local_unknown: bool = False  # True if project has this basename but sha256 not in index
    token_match_warnings: List[str] = field(default_factory=list)  # Warnings about token matches with different sha256
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "sha_token": self.sha_token,
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
            "token_match_warnings": self.token_match_warnings,
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
    sha_token: str
    element: str
    display_basename: str
    all_basenames: List[str]
    sources: List[PseudoSource]
    availability: Dict[str, bool] = field(default_factory=lambda: {"any_installed": False})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "sha_token": self.sha_token,
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
    
    library_name = library.get("library_name", "").upper()
    library_version = library.get("library_version", "")
    xc = library.get("xc", "").upper()
    quality = library.get("quality", "")
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
    pseudo_dir = Path(dir_path)
    if not pseudo_dir.exists():
        return ()
    
    results = []
    for pseudo_file in pseudo_dir.glob("*.UPF"):
        if not pseudo_file.is_file():
            continue
        try:
            sha256 = compute_sha256_file(pseudo_file)
            results.append((str(pseudo_file), sha256, pseudo_file.name))
        except Exception:
            continue
    
    for pseudo_file in pseudo_dir.glob("*.upf"):
        if not pseudo_file.is_file():
            continue
        try:
            sha256 = compute_sha256_file(pseudo_file)
            results.append((str(pseudo_file), sha256, pseudo_file.name))
        except Exception:
            continue
    
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
    - sha_token for warnings/collision detection
    - Token-match warnings when project has same basename with token-match but sha256 differs
    
    Default selection priority: project filename → internal filename → lib
    
    Args:
        project_root: Project root path
        elements: List of element symbols
        config: Optional PseudoConfig (loads if not provided)
        
    Returns:
        Dict mapping element -> List[PseudoVariant dict] (sha256-keyed)
    """
    from quantumvitas.core.pseudo_config import PseudoConfig
    from quantumvitas.core.pseudo_installs import check_archive_status
    
    if config is None:
        config = load_pseudo_config()
    
    project_root = Path(project_root).resolve()
    project_pseudo_dir = project_root / "pseudo"
    internal_pseudo_dir = get_system_pseudo_dir()
    
    # Load bundle and build indices
    bundle = load_pseudo_libinfo_bundle()
    occurrences_index = _build_occurrences_index(bundle)
    files_index = {f.get("sha256"): f for f in bundle.index.get("files", [])}
    
    # Load manifest archives for installed status
    manifest_archives = load_manifest_archives()
    archive_map = {arch.asset_name: arch for arch in manifest_archives}
    
    # Build variants by element -> sha256 (primary key)
    variants_by_element: Dict[str, Dict[str, PseudoVariant]] = {}
    
    # Track project files by (element, basename) for token-match detection
    project_files_by_element_basename: Dict[Tuple[str, str], Tuple[str, str, Path]] = {}  # (element, basename) -> (sha256, sha_token, path)
    
    # Initialize per element
    for element in elements:
        variants_by_element[element] = {}
    
    # Helper: Get or create variant for sha256
    def get_or_create_variant(element: str, sha256: str, basename: str, sha_token: str) -> PseudoVariant:
        if sha256 not in variants_by_element[element]:
            variants_by_element[element][sha256] = PseudoVariant(
                sha256=sha256,
                sha_token=sha_token,
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
                # Compute sha_token (not cached)
                sha_token = compute_sha_token_file(pseudo_file)
                
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
                
                # Track project file for token-match detection
                project_files_by_element_basename[(element, basename)] = (sha256, sha_token, pseudo_file)
                
                # Check if sha256 is in index (known variant)
                if sha256 in files_index:
                    # Known variant: create/update variant
                    variant = get_or_create_variant(element, sha256, basename, sha_token)
                    
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
                            archive_name = occ.get("archive", {}).get("name", "")
                            archive_sha256 = occ.get("archive", {}).get("sha256", "")
                            library = occ.get("library", {})
                            
                            # Find archive in manifest
                            archive_status = None
                            for arch in manifest_archives:
                                if arch.asset_name == archive_name:
                                    archive_status = arch
                                    break
                                if arch.sha256 == archive_sha256:
                                    archive_status = arch
                                    break
                            
                            if not archive_status:
                                relative_path = occ.get("archive", {}).get("relative_path", "")
                                if relative_path:
                                    for arch in manifest_archives:
                                        if arch.relative_path == relative_path:
                                            archive_status = arch
                                            break
                            
                            # Check installed/corrupt status
                            installed = False
                            corrupt = False
                            warning = None
                            if archive_status:
                                status = check_archive_status(
                                    archive_status.asset_name,
                                    archive_status.sha256,
                                    config=config,
                                )
                                installed = status["installed"] and not status["corrupt"]
                                corrupt = status["corrupt"]
                                if corrupt:
                                    warning = status.get("error") or "Archive corrupt, needs reinstall"
                            
                            # Add library chip
                            label = _format_library_label(occ)
                            lib_source = PseudoSource(
                                kind="lib",
                                label=label,
                                installed=installed,
                                corrupt=corrupt,
                                warning=warning,
                                archive_asset=archive_name,
                                library_name=library.get("library_name"),
                                library_version=library.get("library_version"),
                            )
                            variant.sources.append(lib_source)
                else:
                    # Unknown variant: project-local file not in index
                    variant = get_or_create_variant(element, sha256, basename, sha_token)
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
        # Scan both .UPF and .upf files
        for pattern in ["*.UPF", "*.upf"]:
            for pseudo_file in internal_pseudo_dir.glob(pattern):
                if not pseudo_file.is_file():
                    continue
                
                try:
                    sha256 = compute_sha256_file(pseudo_file)
                    sha_token = compute_sha_token_file(pseudo_file)
                    
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
                    variant = get_or_create_variant(element, sha256, pseudo_file.name, sha_token)
                    
                    # Add internal source chip (if not already present)
                    has_internal = any(s.kind == "internal" for s in variant.sources)
                    if not has_internal:
                        internal_source = PseudoSource(
                            kind="internal",
                            label="Internal",
                            installed=True,  # Always installed if file exists
                        )
                        variant.sources.append(internal_source)
                    
                    # Check for token-match with project file (different sha256)
                    project_key = (element, pseudo_file.name)
                    if project_key in project_files_by_element_basename:
                        proj_sha256, proj_sha_token, proj_path = project_files_by_element_basename[project_key]
                        if proj_sha_token == sha_token and proj_sha256 != sha256:
                            # Token match but sha256 differs: add warning
                            variant.token_match_warnings.append(
                                f"project has same filename with token-match but different bytes; selecting this will overwrite on Run"
                            )
                            # Also add warning to project variant if it exists
                            if proj_sha256 in variants_by_element[element]:
                                proj_variant = variants_by_element[element][proj_sha256]
                                proj_variant.token_match_warnings.append(
                                    f"token matches internal (bytes differ)"
                                )
                    
                    # Add library chips if sha256 matches index
                    if sha256 in occurrences_index:
                        for occ in occurrences_index[sha256]:
                            archive_name = occ.get("archive", {}).get("name", "")
                            archive_sha256 = occ.get("archive", {}).get("sha256", "")
                            library = occ.get("library", {})
                            
                            archive_status = None
                            for arch in manifest_archives:
                                if arch.asset_name == archive_name:
                                    archive_status = arch
                                    break
                                if arch.sha256 == archive_sha256:
                                    archive_status = arch
                                    break
                            
                            if not archive_status:
                                relative_path = occ.get("archive", {}).get("relative_path", "")
                                if relative_path:
                                    for arch in manifest_archives:
                                        if arch.relative_path == relative_path:
                                            archive_status = arch
                                            break
                            
                            installed = False
                            corrupt = False
                            warning = None
                            if archive_status:
                                status = check_archive_status(
                                    archive_status.asset_name,
                                    archive_status.sha256,
                                    config=config,
                                )
                                installed = status["installed"] and not status["corrupt"]
                                corrupt = status["corrupt"]
                                if corrupt:
                                    warning = status.get("error") or "Archive corrupt, needs reinstall"
                            
                            label = _format_library_label(occ)
                            lib_source = PseudoSource(
                                kind="lib",
                                label=label,
                                installed=installed,
                                corrupt=corrupt,
                                warning=warning,
                                archive_asset=archive_name,
                                library_name=library.get("library_name"),
                                library_version=library.get("library_version"),
                            )
                            variant.sources.append(lib_source)
                
                except Exception:
                    continue
    
    # Add library-only variants (from index, not in project/internal)
    for file_entry in bundle.index.get("files", []):
        file_sha256 = file_entry.get("sha256")
        file_sha_token = file_entry.get("sha_token", "")
        basenames = file_entry.get("basenames", [])
        
        if not file_sha256 or not file_sha_token:
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
            variant = get_or_create_variant(element, file_sha256, canonical_basename, file_sha_token)
            
            # Add library chips
            if file_sha256 in occurrences_index:
                for occ in occurrences_index[file_sha256]:
                    archive_name = occ.get("archive", {}).get("name", "")
                    library = occ.get("library", {})
                    
                    archive_status = None
                    for arch in manifest_archives:
                        if arch.asset_name == archive_name:
                            archive_status = arch
                            break
                    
                    installed = False
                    corrupt = False
                    warning = None
                    if archive_status:
                        status = check_archive_status(
                            archive_status.asset_name,
                            archive_status.sha256,
                            config=config,
                        )
                        installed = status["installed"] and not status["corrupt"]
                        corrupt = status["corrupt"]
                        if corrupt:
                            warning = status.get("error") or "Archive corrupt, needs reinstall"
                    
                    label = _format_library_label(occ)
                    lib_source = PseudoSource(
                        kind="lib",
                        label=label,
                        installed=installed,
                        corrupt=corrupt,
                        warning=warning,
                        archive_asset=archive_name,
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
    from quantumvitas.core.pseudo_config import PseudoConfig, load_pseudo_config
    
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
    
    # 3. Check installed archives
    # Find which archive(s) contain this sha256
    if sha256 in occurrences_index:
        from quantumvitas.core.pseudo_installs import (
            check_archive_status,
            get_archives_dir,
            get_pseudo_install_root,
            load_manifest_archives,
        )
        import tarfile
        import zipfile
        
        install_root = get_pseudo_install_root(config)
        if install_root:
            archives_dir = get_archives_dir(install_root)
            manifest_archives = load_manifest_archives()
            
            for occ in occurrences_index[sha256]:
                archive_name = occ.get("archive", {}).get("name", "")
                path_in_archive = occ.get("path_in_archive", "")
                
                # Find archive in manifest
                archive_status = None
                for arch in manifest_archives:
                    if arch.asset_name == archive_name:
                        archive_status = arch
                        break
                
                if not archive_status:
                    continue
                
                # Check if archive is installed
                status = check_archive_status(
                    archive_status.asset_name,
                    archive_status.sha256,
                    install_root=install_root,
                    config=config,
                )
                
                # CRITICAL: Only use archive if installed AND NOT corrupt
                if status["installed"] and not status["corrupt"]:
                    # Archive is installed, try to extract the file
                    archive_path = archives_dir / archive_status.asset_name
                    try:
                        # Extract to project/pseudo
                        project_pseudo_dir.mkdir(parents=True, exist_ok=True)
                        
                        basename = preferred_basename or Path(path_in_archive).name
                        dest_path = project_pseudo_dir / basename
                        
                        # Handle tar.gz/tgz/tar
                        if archive_path.suffixes[-2:] == [".tar", ".gz"] or archive_path.suffix == ".tgz":
                            with tarfile.open(archive_path, "r:gz") as tar:
                                member = None
                                for m in tar.getmembers():
                                    if m.name == path_in_archive or m.name.endswith(path_in_archive):
                                        member = m
                                        break
                                if member:
                                    extracted = tar.extractfile(member)
                                    if extracted:
                                        dest_path.write_bytes(extracted.read())
                        # Handle .tar
                        elif archive_path.suffix == ".tar":
                            with tarfile.open(archive_path, "r") as tar:
                                member = None
                                for m in tar.getmembers():
                                    if m.name == path_in_archive or m.name.endswith(path_in_archive):
                                        member = m
                                        break
                                if member:
                                    extracted = tar.extractfile(member)
                                    if extracted:
                                        dest_path.write_bytes(extracted.read())
                        # Handle .zip
                        elif archive_path.suffix == ".zip":
                            with zipfile.ZipFile(archive_path, "r") as zipf:
                                try:
                                    zipf.extract(path_in_archive, project_pseudo_dir)
                                    # Move to desired basename if different
                                    extracted_path = project_pseudo_dir / path_in_archive
                                    if extracted_path.exists() and extracted_path != dest_path:
                                        if dest_path.exists():
                                            dest_path.unlink()
                                        extracted_path.rename(dest_path)
                                except KeyError:
                                    # Try to find by basename
                                    for name in zipf.namelist():
                                        if name.endswith(path_in_archive) or name.endswith(basename):
                                            zipf.extract(name, project_pseudo_dir)
                                            extracted_path = project_pseudo_dir / name
                                            if extracted_path.exists() and extracted_path != dest_path:
                                                if dest_path.exists():
                                                    dest_path.unlink()
                                                extracted_path.rename(dest_path)
                                            break
                        
                        # Verify extracted file sha256
                        if dest_path.exists():
                            extracted_sha256 = compute_sha256_file(dest_path)
                            if extracted_sha256 == sha256:
                                result["success"] = True
                                result["file_path"] = str(dest_path)
                                result["source"] = "library"
                                return result
                            else:
                                dest_path.unlink()  # Remove incorrect file
                    except Exception as e:
                        result["error"] = f"Failed to extract from archive: {e}"
                        continue
                elif status["exists"] and status["corrupt"]:
                    # Archive exists but corrupt - DO NOT USE IT
                    result["error"] = (
                        f"Archive {archive_status.asset_name} exists but failed SHA256 verification. "
                        f"Reinstall from Settings → Pseudopotentials."
                    )
                    result["needs_install"] = True
                    result["archive_asset"] = archive_status.asset_name
                else:
                    # Archive not installed
                    result["needs_install"] = True
                    result["archive_asset"] = archive_status.asset_name
    
    # If we get here, materialization failed
    if not result["error"]:
        if result["needs_install"]:
            result["error"] = f"Archive {result['archive_asset']} needs to be installed. Go to Settings → Pseudopotential Archives to install."
        else:
            result["error"] = f"Could not materialize pseudo file for {element} (sha256: {sha256[:16]}...). File not found in project, internal, or installed archives."
    
    return result
