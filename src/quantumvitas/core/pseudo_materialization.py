"""
Pseudo materialization for calculation execution.

This module provides deterministic materialization of pseudopotentials
from sha256-pinned selections into working_dir/pseudo for QE execution.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.core.pseudo_options import materialize_pseudo_file
from quantumvitas.core.pseudo_provenance import (
    compute_sha256_file,
    compute_sha_family_file,
)
from quantumvitas.core.pseudo_libinfo import load_pseudo_libinfo_bundle


def materialize_calc_pseudos(
    *,
    project_root: Optional[Path],
    working_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
    repo_root: Optional[Path] = None,
) -> Path:
    """
    Materialize pseudopotentials for a calculation into working_dir/pseudo.
    
    This is the canonical function for preparing pseudos before QE execution.
    It ensures deterministic execution by:
    1. Using sha256-pinned selections when available
    2. Resolving legacy filename-only selections deterministically
    3. Copying files to working_dir/pseudo (never project_root/pseudo during run)
    4. Verifying SHA256 matches after copy
    
    Args:
        project_root: Optional project root (for resolving project/pseudo source)
        working_dir: Working directory for this calculation run (e.g., raw_dir)
        species_map: Species mapping from calculation (element -> {pseudopot, pseudo_sha256, ...})
        repo_root: Optional repo root (for testing; auto-detected if None)
        
    Returns:
        Path to pseudo_dir (working_dir / "pseudo")
        
    Raises:
        RuntimeError: If required pseudo cannot be materialized
        ValueError: If sha256 mismatch detected after copy
    """
    from quantumvitas.core.pseudo_config import load_pseudo_config
    from quantumvitas.core.pseudo_provenance import _build_occurrences_index
    from quantumvitas.core.pseudo_installs import (
        check_archive_status,
        get_archives_dir,
        get_pseudo_install_root,
        load_manifest_archives,
    )
    from quantumvitas.core.pseudo import get_system_pseudo_dir
    import tarfile
    import zipfile
    
    # GUARD: Never use repo_root/pseudo
    if repo_root is None:
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root
        repo_root = _find_quantumvitas_root()
    
    if repo_root:
        repo_pseudo = (repo_root / "pseudo").resolve()
        working_pseudo = (working_dir / "pseudo").resolve()
        if working_pseudo == repo_pseudo:
            raise RuntimeError(
                f"BUG: materialize_calc_pseudos attempted to use repo_root/pseudo at {working_pseudo}. "
                f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo."
            )
    
    # Create working_dir/pseudo (always)
    pseudo_dir = working_dir / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    config = load_pseudo_config()
    internal_pseudo_dir = get_system_pseudo_dir()
    
    # Load bundle for legacy resolution
    bundle = load_pseudo_libinfo_bundle(repo_root=repo_root)
    occurrences_index = _build_occurrences_index(bundle)
    files_index = {f.get("sha256"): f for f in bundle.index.get("files", [])}
    
    # Process each element in species_map
    for element, settings in species_map.items():
        pseudo_sha256 = settings.get("pseudo_sha256")
        pseudo_basename = settings.get("pseudo_basename")
        legacy_pseudopot = settings.get("pseudopot")  # Legacy filename field
        
        # Determine target filename
        target_filename = pseudo_basename or legacy_pseudopot or f"{element}.upf"
        target_path = pseudo_dir / target_filename
        
        # If sha256 is pinned, use it
        if pseudo_sha256:
            # Materialize using sha256
            result = materialize_pseudo_file(
                project_root=project_root or working_dir,  # Fallback to working_dir if no project
                element=element,
                sha256=pseudo_sha256,
                preferred_basename=pseudo_basename or target_filename,
                config=config,
            )
            
            if not result["success"]:
                # Check if archive needs installation
                if result["needs_install"]:
                    archive_name = result.get("archive_asset", "unknown")
                    raise RuntimeError(
                        f"Pseudo archive required but not installed for {element}. "
                        f"Go to Settings → Pseudopotentials to install: {archive_name}"
                    )
                else:
                    raise RuntimeError(
                        f"Could not materialize pseudo for {element}: {result.get('error', 'Unknown error')}"
                    )
            
            # Copy to working_dir/pseudo with target filename
            source_path = Path(result["file_path"])
            if source_path != target_path:
                shutil.copy2(source_path, target_path)
            
            # Verify copied file sha256 matches
            copied_sha256 = compute_sha256_file(target_path)
            if copied_sha256 != pseudo_sha256:
                raise ValueError(
                    f"SHA256 mismatch after copy for {element}: "
                    f"expected {pseudo_sha256[:16]}..., got {copied_sha256[:16]}..."
                )
        
        # Legacy path: resolve filename deterministically
        else:
            if not legacy_pseudopot:
                # No pseudo specified for this element - skip
                continue
            
            # Resolution order: project/pseudo -> internal -> installed archives
            source_path = None
            resolved_sha256 = None
            resolved_sha_family = None
            
            # 1. Check project/pseudo
            if project_root:
                project_pseudo_dir = project_root / "pseudo"
                if project_pseudo_dir.exists():
                    for pseudo_file in project_pseudo_dir.glob(f"{legacy_pseudopot}"):
                        if pseudo_file.is_file():
                            source_path = pseudo_file
                            resolved_sha256 = compute_sha256_file(pseudo_file)
                            resolved_sha_family = compute_sha_family_file(pseudo_file)
                            break
                    if source_path:
                        break
                    
                    # Try case-insensitive
                    for pseudo_file in project_pseudo_dir.glob("*.UPF"):
                        if pseudo_file.name.lower() == legacy_pseudopot.lower():
                            source_path = pseudo_file
                            resolved_sha256 = compute_sha256_file(pseudo_file)
                            resolved_sha_family = compute_sha_family_file(pseudo_file)
                            break
                    if source_path:
                        break
            
            # 2. Check internal
            if not source_path and internal_pseudo_dir and internal_pseudo_dir.exists():
                for pseudo_file in internal_pseudo_dir.glob(f"{legacy_pseudopot}"):
                    if pseudo_file.is_file():
                        source_path = pseudo_file
                        resolved_sha256 = compute_sha256_file(pseudo_file)
                        resolved_sha_family = compute_sha_family_file(pseudo_file)
                        break
                if not source_path:
                    # Try case-insensitive
                    for pseudo_file in internal_pseudo_dir.glob("*.UPF"):
                        if pseudo_file.name.lower() == legacy_pseudopot.lower():
                            source_path = pseudo_file
                            resolved_sha256 = compute_sha256_file(pseudo_file)
                            resolved_sha_family = compute_sha_family_file(pseudo_file)
                            break
            
            # 3. Check installed archives (by basename match in occurrences)
            if not source_path:
                install_root = get_pseudo_install_root(config)
                if install_root:
                    archives_dir = get_archives_dir(install_root)
                    manifest_archives = load_manifest_archives()
                    
                    # Find occurrences that match this basename
                    for file_entry in bundle.index.get("files", []):
                        basenames = file_entry.get("basenames", [])
                        if legacy_pseudopot in basenames:
                            file_sha256 = file_entry.get("sha256")
                            if file_sha256 in occurrences_index:
                                # Find installed archive containing this file
                                for occ in occurrences_index[file_sha256]:
                                    archive_name = occ.get("archive", {}).get("name", "")
                                    path_in_archive = occ.get("path_in_archive", "")
                                    
                                    # Find archive in manifest
                                    archive_status = None
                                    for arch in manifest_archives:
                                        if arch.asset_name == archive_name:
                                            archive_status = arch
                                            break
                                    
                                    if archive_status:
                                        # Check if installed and not corrupt
                                        status = check_archive_status(
                                            archive_status.asset_name,
                                            archive_status.sha256,
                                            install_root=install_root,
                                            config=config,
                                        )
                                        
                                        if status["installed"] and not status["corrupt"]:
                                            # Extract from archive
                                            archive_path = archives_dir / archive_status.asset_name
                                            
                                            try:
                                                # Extract to temp location first
                                                temp_extract = pseudo_dir / f".temp_{legacy_pseudopot}"
                                                
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
                                                                temp_extract.write_bytes(extracted.read())
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
                                                                temp_extract.write_bytes(extracted.read())
                                                elif archive_path.suffix == ".zip":
                                                    with zipfile.ZipFile(archive_path, "r") as zipf:
                                                        try:
                                                            zipf.extract(path_in_archive, pseudo_dir)
                                                            extracted_path = pseudo_dir / path_in_archive
                                                            if extracted_path.exists():
                                                                extracted_path.rename(temp_extract)
                                                        except KeyError:
                                                            for name in zipf.namelist():
                                                                if name.endswith(path_in_archive) or name.endswith(legacy_pseudopot):
                                                                    zipf.extract(name, pseudo_dir)
                                                                    extracted_path = pseudo_dir / name
                                                                    if extracted_path.exists():
                                                                        extracted_path.rename(temp_extract)
                                                                    break
                                                
                                                if temp_extract.exists():
                                                    resolved_sha256 = compute_sha256_file(temp_extract)
                                                    resolved_sha_family = compute_sha_family_file(temp_extract)
                                                    source_path = temp_extract
                                                    break
                                            except Exception:
                                                continue
                                
                                if source_path:
                                    break
            
            if not source_path:
                raise RuntimeError(
                    f"Could not resolve legacy pseudo '{legacy_pseudopot}' for {element}. "
                    f"File not found in project/pseudo, internal resources, or installed archives."
                )
            
            # Copy to target
            if source_path != target_path:
                shutil.copy2(source_path, target_path)
            
            # Verify and optionally upgrade mapping
            if resolved_sha256:
                copied_sha256 = compute_sha256_file(target_path)
                if copied_sha256 != resolved_sha256:
                    raise ValueError(
                        f"SHA256 mismatch after copy for {element}: "
                        f"expected {resolved_sha256[:16]}..., got {copied_sha256[:16]}..."
                    )
                
                # Note: We could upgrade the mapping here, but for now we just materialize
                # The upgrade can happen lazily on next edit/save
    
    return pseudo_dir

