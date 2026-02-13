# Project Bundle Export Specification

**Version**: 1.0  
**Date**: 2026-01-02  
**Status**: Design Specification  
**Constitution Reference**: New Decision B (Project export/serialization levels)

---

## 1. Overview

### 1.1 Purpose

Project bundles enable:
1. **Demo sharing** - Share "golden path" examples for learning
2. **Market ecosystem** - Distribute pre-configured calculation templates
3. **Bug reports** - Include enough data for reproducibility
4. **Archival** - Long-term storage of calculation workflows

### 1.2 Design Principles

Per Constitution:
- **No workflow IDs as execution truth** - Workflow can be inferred from topology
- **Pseudo identity triple required** - filename + sha256 + sha_family
- **Analysis data must be versioned and regenerable**
- **Exclude scratch data** (outdir, large temporary files)

---

## 2. Bundle Levels

### 2.1 Level Definitions

| Level | Name | Contents | Use Case |
|-------|------|----------|----------|
| 1 | `INPUTS_ONLY` | Structure + step.yml + pseudo identity | Minimum reproducible |
| 2 | `INPUTS_ANALYZED` | Level 1 + parsed/analyzed results | Demo sharing |
| 3 | `INPUTS_OUTPUTS` | Level 2 + raw outputs (selective) | Bug reports |

### 2.2 Level 1: INPUTS_ONLY

Minimum data needed to reproduce a calculation on any machine.

**Contents**:
```
bundle/
├── manifest.json
├── project.qv.yml
├── structures/
│   └── *.json
├── calculations/
│   └── {calc_slug}/
│       ├── calculation.yaml
│       └── steps/
│           └── *.step.yaml
```

**Pseudo Handling**:
- Pseudo files are NOT embedded
- `manifest.json` contains pseudo identity triples
- Receiver must have matching pseudos installed

### 2.3 Level 2: INPUTS_ANALYZED

Level 1 plus analyzed/visualization-ready data.

**Additional Contents**:
```
bundle/
├── ... (Level 1 contents)
├── analysis/
│   ├── analysis_meta.json       # Version + staleness info
│   ├── bands/
│   │   └── {calc_slug}_bands.json
│   ├── dos/
│   │   └── {calc_slug}_dos.json
│   └── structures/
│       └── {calc_slug}_relaxed.json
```

**Staleness Tracking**:
```json
// analysis_meta.json
{
  "version": "1.0",
  "qmatsuite_version": "0.5.0",
  "generated_at": "2026-01-02T10:30:00Z",
  "artifacts": [
    {
      "path": "bands/si_bands_bands.json",
      "source_step": "01JGXYZABC",
      "source_output_hash": "sha256:abc123...",
      "is_stale": false
    }
  ]
}
```

### 2.4 Level 3: INPUTS_OUTPUTS

Level 2 plus raw calculation outputs (selective).

**Additional Contents**:
```
bundle/
├── ... (Level 2 contents)
├── raw_outputs/
│   └── {calc_slug}/
│       └── {step_slug}/
│           ├── pw.out
│           ├── data-file-schema.xml
│           └── ... (selected outputs)
```

**Exclusions** (always):
- `outdir/` scratch directory
- Large binary files (> 10MB by default)
- Checkpoint files (*.save)

**Inclusion Control**:
```python
# Export with custom include patterns
export_bundle(
    project_root,
    level=BundleLevel.INPUTS_OUTPUTS,
    output_include=["*.out", "*.xml", "*.dat"],
    output_exclude=["*.wfc*", "*.save"],
    max_file_size_mb=50,
)
```

---

## 3. Manifest Schema

### 3.1 Full Manifest Structure

```json
{
  "version": 1,
  "bundle_level": "inputs_only|inputs_analyzed|inputs_outputs",
  "created_at": "2026-01-02T10:30:00Z",
  "qmatsuite_version": "0.5.0",
  
  "project": {
    "id": "01JGXYZ...",
    "name": "Silicon Band Structure",
    "slug": "si_bands"
  },
  
  "files": [
    {
      "path": "project.qv.yml",
      "sha256": "abc123...",
      "size_bytes": 1234,
      "required": true
    },
    {
      "path": "structures/si.json",
      "sha256": "def456...",
      "size_bytes": 5678,
      "required": true
    }
  ],
  
  "pseudo_identities": {
    "Si": {
      "pseudo_basename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "pseudo_sha256": "789abc...",
      "pseudo_sha_family": "012def..."
    }
  },
  
  "workflow_fingerprint": "scf->bands_pw->bands",
  
  "meta": {
    "title": "Silicon Band Structure Demo",
    "subtitle": "SCF → Bands calculation",
    "tags": ["bands", "Si", "tutorial"],
    "recommended_analysis": "bands",
    "difficulty": "beginner"
  }
}
```

### 3.2 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | int | ✓ | Manifest schema version |
| `bundle_level` | string | ✓ | One of the three levels |
| `created_at` | ISO8601 | ✓ | Bundle creation timestamp |
| `qmatsuite_version` | string | ✓ | Creating software version |
| `project` | object | ✓ | Project metadata |
| `files` | array | ✓ | List of included files with hashes |
| `pseudo_identities` | object | ✓ | Element → pseudo triplet map |
| `workflow_fingerprint` | string | ✗ | Inferred workflow topology |
| `meta` | object | ✗ | Gallery/market metadata |

### 3.3 Pseudo Identity Format

```json
{
  "pseudo_basename": "string",    // Filename (used in QE input)
  "pseudo_sha256": "string",      // Exact byte hash (64 hex chars)
  "pseudo_sha_family": "string"   // Physical equivalence hash
}
```

**Resolution Priority** (at import):
1. Match by `pseudo_sha256` in installed libraries
2. Fallback to `pseudo_sha_family` match (warn if sha256 differs)
3. Fallback to `pseudo_basename` match (warn if hashes differ)
4. Error if no match found

---

## 4. Directory Structure

### 4.1 Bundle Root Structure

```
{bundle_name}.qvbundle/
├── manifest.json              # Always first, always present
├── project.qv.yml             # Project configuration
├── structures/
│   └── *.json                 # Structure files
├── calculations/
│   └── {calc_slug}/
│       ├── calculation.yaml
│       └── steps/
│           └── *.step.yaml
├── analysis/                  # Level 2+
│   ├── analysis_meta.json
│   └── {type}/
│       └── {artifact}.json
└── raw_outputs/               # Level 3 only
    └── {calc_slug}/
        └── {step_slug}/
            └── {output_files}
```

### 4.2 Single-File Distribution

Bundles can be distributed as:
1. **Directory** - For development/inspection
2. **ZIP archive** - `.qvbundle.zip` for sharing
3. **Tarball** - `.qvbundle.tar.gz` for Linux distribution

---

## 5. Analysis Staleness Rules

### 5.1 Staleness Detection

An analysis artifact is **stale** if:
1. Source step's output hash differs from recorded hash
2. QMatSuite version has breaking analysis changes
3. Structure has changed since analysis generation

### 5.2 Staleness Markers

```json
// In analysis_meta.json
{
  "artifacts": [
    {
      "path": "bands/si_bands.json",
      "source_step": "01JGXYZ",
      "source_output_hash": "sha256:original_hash",
      "current_output_hash": "sha256:new_hash",  // If rechecked
      "is_stale": true,
      "stale_reason": "output_changed"
    }
  ]
}
```

### 5.3 UI Behavior

When loading a bundle with stale analysis:
1. Display warning indicator on analysis views
2. Offer "Regenerate Analysis" action
3. Show last-good analysis data until regenerated

---

## 6. Import/Export API

### 6.1 Export API

```python
def export_bundle(
    project_root: Path,
    output_path: Path,
    level: BundleLevel = BundleLevel.INPUTS_ANALYZED,
    *,
    # Level 3 options
    output_include: Optional[List[str]] = None,
    output_exclude: Optional[List[str]] = None,
    max_file_size_mb: float = 10.0,
    # Meta options
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compress: bool = True,
) -> Path:
    """
    Export project as distributable bundle.
    
    Args:
        project_root: Path to project directory
        output_path: Path for output bundle (directory or .zip)
        level: Bundle level (INPUTS_ONLY, INPUTS_ANALYZED, INPUTS_OUTPUTS)
        output_include: Glob patterns for raw outputs to include (Level 3)
        output_exclude: Glob patterns for raw outputs to exclude
        max_file_size_mb: Maximum file size for individual outputs
        title: Optional display title for gallery
        subtitle: Optional subtitle
        tags: Optional list of tags
        compress: If True, create .zip; else create directory
    
    Returns:
        Path to created bundle
    """
```

### 6.2 Import API

```python
def import_bundle(
    bundle_path: Path,
    target_dir: Path,
    *,
    project_name: Optional[str] = None,
    resolve_pseudos: bool = True,
    skip_analysis: bool = False,
) -> Path:
    """
    Import project from bundle.
    
    Args:
        bundle_path: Path to bundle (.zip, .tar.gz, or directory)
        target_dir: Directory where project will be created
        project_name: Optional override for project name
        resolve_pseudos: If True, attempt to resolve pseudos from libraries
        skip_analysis: If True, don't import analysis data
    
    Returns:
        Path to created project root
    
    Raises:
        BundlePseudoMissingError: If required pseudos not available
        BundleVersionError: If bundle format not supported
    """
```

### 6.3 Validation API

```python
def validate_bundle(
    bundle_path: Path,
) -> BundleValidation:
    """
    Validate bundle integrity and compatibility.
    
    Returns:
        BundleValidation with:
        - is_valid: bool
        - warnings: List[str]
        - errors: List[str]
        - missing_pseudos: Dict[str, PseudoIdentity]
        - stale_artifacts: List[str]
    """
```

---

## 7. Hashing Rules

### 7.1 File Hashing

All files in manifest use SHA256:
```python
def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents."""
    import hashlib
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### 7.2 Manifest Self-Hash

The manifest includes a `files` array with hashes of all included files.
The manifest itself is NOT hashed (would create circular dependency).

### 7.3 Pseudo Hashing

Uses Constitution §6 rules:
- `pseudo_sha256`: Exact byte hash
- `pseudo_sha_family`: Whitespace-normalized hash (physical equivalence)

---

## 8. Test Requirements

### 8.1 Unit Tests

```python
class TestBundleExport:
    """Bundle export tests."""
    
    def test_inputs_only_excludes_outputs(self, temp_project):
        """Level 1 bundle has no raw outputs."""
        bundle = export_bundle(temp_project, output, level=BundleLevel.INPUTS_ONLY)
        assert not (bundle / "raw_outputs").exists()
        assert not (bundle / "analysis").exists()
    
    def test_manifest_has_pseudo_identities(self, temp_project):
        """Manifest includes pseudo identity triples."""
        bundle = export_bundle(temp_project, output)
        manifest = json.loads((bundle / "manifest.json").read_text())
        
        assert "pseudo_identities" in manifest
        for element, identity in manifest["pseudo_identities"].items():
            assert "pseudo_basename" in identity
            assert "pseudo_sha256" in identity
            assert "pseudo_sha_family" in identity
    
    def test_file_hashes_verify(self, temp_project):
        """All manifest file hashes match actual files."""
        bundle = export_bundle(temp_project, output)
        manifest = json.loads((bundle / "manifest.json").read_text())
        
        for file_entry in manifest["files"]:
            file_path = bundle / file_entry["path"]
            actual_hash = compute_file_hash(file_path)
            assert actual_hash == file_entry["sha256"]


class TestBundleImport:
    """Bundle import tests."""
    
    def test_import_generates_new_ulids(self, temp_bundle):
        """Import creates new ULIDs for all resources."""
        original_manifest = json.loads(...)
        imported = import_bundle(temp_bundle, target_dir)
        
        # All IDs should be different
        new_project = load_project(imported)
        assert new_project.meta.id != original_manifest["project"]["id"]
    
    def test_import_resolves_pseudos(self, temp_bundle, installed_pseudos):
        """Import resolves pseudos from installed libraries."""
        imported = import_bundle(temp_bundle, target_dir, resolve_pseudos=True)
        # Should not raise BundlePseudoMissingError


class TestStalenessDetection:
    """Analysis staleness tests."""
    
    def test_detects_stale_when_output_changed(self, temp_project):
        """Staleness detected when source output hash changes."""
        bundle = export_bundle(temp_project, output, level=BundleLevel.INPUTS_ANALYZED)
        
        # Modify output file
        modify_output_file(temp_project)
        
        validation = validate_bundle(bundle)
        assert len(validation.stale_artifacts) > 0
```

### 8.2 CI Gates

```yaml
- name: Bundle Export Tests
  run: pytest tests/unit/test_bundle.py -v

- name: Bundle Roundtrip Test
  run: |
    python -c "
    from quantumvitas.project.bundle import export_bundle, import_bundle
    # Export demo project
    bundle = export_bundle('resources/demo_projects/si_bands', 'test.qvbundle.zip')
    # Import to new location
    imported = import_bundle(bundle, 'test_import/')
    # Validate structure
    assert (imported / 'project.qv.yml').exists()
    "
```

---

## 9. Implementation Notes

### 9.1 File Locations

| New File | Purpose |
|----------|---------|
| `src/quantumvitas/project/bundle.py` | Bundle export/import |
| `src/quantumvitas/project/bundle_manifest.py` | Manifest dataclass |
| `tests/unit/test_bundle.py` | Bundle tests |

### 9.2 Relationship to Snapshot

- `snapshot.py` - Internal format, full data embedding
- `bundle.py` - Distribution format, pseudo references only

Bundles are built using snapshot as intermediate:
```python
def export_bundle(...):
    # First create snapshot
    snapshot = export_project_to_snapshot(project_root)
    # Then serialize to bundle format
    write_bundle_from_snapshot(snapshot, output_path, level, ...)
```

### 9.3 Backward Compatibility

- Bundles include `version` field for format evolution
- Old bundles can be migrated via version-specific readers
- Core fields are stable; `meta` section is extensible

---

## 10. Gallery Integration

### 10.1 Demo Discovery

Bundles with `meta.tags` can be indexed for gallery:
```python
def discover_demo_bundles(search_paths: List[Path]) -> List[BundleInfo]:
    """Find and index all demo bundles for gallery display."""
```

### 10.2 Market Ecosystem

Future extension: bundles can be published to and fetched from:
- Local bundle cache (`~/.qmatsuite/bundles/`)
- Remote bundle registry (future feature)

---

*This specification is implementation-ready. PR can proceed.*

