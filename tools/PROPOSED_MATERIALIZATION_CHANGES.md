# Proposed Changes to materialize_project_from_snapshot

## Summary

Update `materialize_project_from_snapshot()` in `src/quantumvitas/project/snapshot.py` to handle pseudopotential files during demo expansion.

## Current Behavior

Currently, `materialize_project_from_snapshot()` only creates an empty `pseudo/` directory but does not copy or download the pseudopotential files.

## Proposed Changes

### Location
`src/quantumvitas/project/snapshot.py`, function `materialize_project_from_snapshot()`, around line 688-693.

### Current Code
```python
# Create pseudo directory (empty, just the directory structure)
if snapshot.pseudo:
    pseudo_dir = project_dir / snapshot.pseudo.get("directory", "pseudo")
    pseudo_dir.mkdir(exist_ok=True)
    # Note: We do NOT create the pseudo files themselves, only the directory
    # The snapshot format documents which files are expected but doesn't embed content
```

### Proposed Replacement
```python
# Create pseudo directory and copy/download pseudopotentials
if snapshot.pseudo:
    pseudo_dir = project_dir / snapshot.pseudo.get("directory", "pseudo")
    pseudo_dir.mkdir(exist_ok=True)
    
    # Get list of required pseudopotential files from snapshot
    required_pseudos = snapshot.pseudo.get("files", [])
    
    if required_pseudos:
        # Find repo root to check repo/pseudo
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root
        from quantumvitas.api import QVService
        import shutil
        
        repo_root = _find_quantumvitas_root()
        repo_pseudo_dir = repo_root / "pseudo" if repo_root else None
        
        for pseudo_filename in required_pseudos:
            pseudo_dest = pseudo_dir / pseudo_filename
            
            # Skip if already exists in project/pseudo
            if pseudo_dest.exists():
                continue
            
            # First, try to copy from repo/pseudo
            if repo_pseudo_dir and repo_pseudo_dir.exists():
                repo_pseudo_file = repo_pseudo_dir / pseudo_filename
                if repo_pseudo_file.exists():
                    shutil.copy2(repo_pseudo_file, pseudo_dest)
                    continue
            
            # If not in repo/pseudo, try to download
            try:
                result = QVService.download_pseudo_by_filename(
                    project_root=project_dir,
                    filename=pseudo_filename,
                    dest_dir=pseudo_dir,
                    config=None
                )
                
                if result.get("errors"):
                    # Download failed - log warning but continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Could not download pseudopotential {pseudo_filename} for demo project: "
                        f"{', '.join(result.get('errors', []))}"
                    )
            except Exception as e:
                # Download failed - log warning but continue
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Error downloading pseudopotential {pseudo_filename} for demo project: {e}"
                )
```

## Behavior

1. **During demo import** (already implemented in importer):
   - Missing pseudos are downloaded to `repo/pseudo` using `download_pseudo_by_filename()`
   - This ensures all required pseudos are available in the repository

2. **During demo expansion** (proposed change):
   - Pseudos are first copied from `repo/pseudo` to `project/pseudo` (if available)
   - If not in `repo/pseudo`, attempt to download directly to `project/pseudo`
   - Always run `.in` files from `project/pseudo` (this is already handled by the QE engine)

## Benefits

- **Self-contained projects**: Each expanded project has its own `pseudo/` directory
- **Efficient**: Reuses pseudos from `repo/pseudo` when available (no redundant downloads)
- **Resilient**: Falls back to download if pseudo not in repo
- **Non-blocking**: Warnings logged but project creation continues even if some pseudos fail

## Testing

After implementation, test:
1. Import a demo that requires pseudos not in repo
2. Verify pseudos are downloaded to `repo/pseudo` during import
3. Expand the demo to a project
4. Verify pseudos are copied from `repo/pseudo` to `project/pseudo`
5. Verify QE runs use `project/pseudo` as `pseudo_dir`

