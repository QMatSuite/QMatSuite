# Phase 3: Pseudopotential Settings & Resolution

This document describes the pseudopotential configuration system implemented for dev-friendly SSSP management.

## Overview

The system provides:
1. **Settings UI** - Configure store, seed, and download permissions
2. **Offline Installation** - Install from seed without network access
3. **Resolution Flow** - Find pseudopotentials with fallback chain
4. **SSSP Support** - Structured storage for SSSP libraries

## Non-Negotiables

- `repo/pseudo/` is **committed** and used ONLY for demos/tests - never modified by this system
- Defaults use `repo/temp/` which is gitignored for dev-time storage
- Downloads are **OFF by default** - opt-in only
- Values written to QE input/YAML remain **string-only**

## Configuration

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `store_dir` | `${repoRoot}/temp/pseudo` | Global pseudo store for installed SSSP libraries |
| `seed_dir` | `${repoRoot}/temp/assets/pseudo_seed` | Seed directory for offline installation |
| `allow_download` | `false` | Whether to allow network downloads |

### Persistence

Config is stored in the user config file:
- **macOS**: `~/Library/Application Support/QuantumVITAS/config.json`
- **Linux**: `~/.config/quantumvitas/config.json`
- **Windows**: `%APPDATA%/QuantumVITAS/config.json`

Example config:
```json
{
  "pseudo": {
    "store_dir": "/path/to/QMatSuite/temp/pseudo",
    "seed_dir": "/path/to/QMatSuite/temp/assets/pseudo_seed",
    "allow_download": false
  }
}
```

## SSSP Storage Layout

### Store Layout (installed libraries)

```
${store_dir}/
└── sssp/
    └── 1.3.0/
        ├── efficiency/
        │   ├── library/          # Extracted UPF files
        │   │   ├── Si.pbe-n-kjpaw_psl.1.0.0.UPF
        │   │   ├── C.pbe-n-kjpaw_psl.1.0.0.UPF
        │   │   └── ...
        │   ├── cutoffs.json      # Recommended cutoffs per element
        │   └── manifest.json     # Installation metadata
        └── precision/
            ├── library/
            ├── cutoffs.json
            └── manifest.json
```

**NOTE**: No "PBE" layer in directory structure. The directory layout is:
`sssp/{version}/{flavor}/`

### Seed Layout (source archives)

```
${seed_dir}/
└── sssp/
    └── 1.3.0/
        ├── efficiency/
        │   ├── SSSP_1.3.0_PBE_efficiency.tar.gz  # Archive from Materials Cloud
        │   └── SSSP_1.3.0_PBE_efficiency.json    # Cutoffs JSON
        └── precision/
            ├── SSSP_1.3.0_PBE_precision.tar.gz
            └── SSSP_1.3.0_PBE_precision.json
```

The seed filenames may contain "PBE" (as provided by Materials Cloud), but the directory structure does not.

## Resolution Order

When resolving pseudopotentials for a project:

1. **Project pseudo dir** (`${project}/pseudo/`) - Already copied, use directly
2. **Repo pseudo dir** (`${repo}/pseudo/`) - Committed demos, copy to project
3. **Store library** (`${store_dir}/sssp/{version}/{flavor}/library/`) - Copy to project
4. **Seed** - If store library not present, install from seed first, then copy
5. **Download** (if allowed) - Fetch from network, install to store, copy to project

Each step copies to the project pseudo folder for reproducibility and self-containment.

## RPC Endpoints

### `get_pseudo_config`

Get current configuration.

**Payload**: (none)

**Response**:
```json
{
  "store_dir": "/path/to/store",
  "seed_dir": "/path/to/seed",
  "allow_download": false,
  "repo_pseudo_dir": "/path/to/repo/pseudo",
  "default_store_dir": "/path/to/repo/temp/pseudo",
  "default_seed_dir": "/path/to/repo/temp/assets/pseudo_seed"
}
```

### `set_pseudo_config`

Update configuration.

**Payload**:
```json
{
  "store_dir": "/new/path",
  "seed_dir": "/new/seed/path",
  "allow_download": true
}
```

All fields optional; missing fields keep current values.

### `validate_pseudo_config`

Validate current configuration.

**Payload**: (none)

**Response**:
```json
{
  "ok": true,
  "repo_pseudo_exists": true,
  "store_dir_exists": true,
  "store_dir_writable": true,
  "seed_dir_exists": true,
  "seed_has_sssp": true,
  "messages": ["✓ Repo pseudo dir: /path", "..."],
  "warnings": [],
  "errors": []
}
```

### `init_pseudo_dirs`

Create store and seed directories if missing.

**Payload**: (none)

**Response**:
```json
{
  "store_dir_created": true,
  "seed_dir_created": true,
  "messages": ["Created store dir: /path"],
  "errors": []
}
```

### `install_seed_to_store`

Install SSSP from seed to store (offline operation).

**Payload**:
```json
{
  "version": "1.3.0",
  "flavor": "efficiency"
}
```

Both fields optional; if omitted, installs all available from seed.

**Response**:
```json
{
  "success": true,
  "installed": [{"version": "1.3.0", "flavor": "efficiency", "files": 85}],
  "skipped": [{"version": "1.3.0", "flavor": "precision"}],
  "failed": [],
  "messages": ["Installed: 1, Skipped: 1, Failed: 0"]
}
```

### `list_installed_sssp`

List installed SSSP libraries in store.

**Payload**: (none)

**Response**:
```json
{
  "libraries": [
    {
      "version": "1.3.0",
      "flavor": "efficiency",
      "installed": true,
      "path": "/path/to/store/sssp/1.3.0/efficiency",
      "file_count": 85,
      "has_cutoffs": true,
      "has_manifest": true
    },
    {
      "version": "1.3.0",
      "flavor": "precision",
      "installed": false,
      "path": null,
      "file_count": 0,
      "has_cutoffs": false,
      "has_manifest": false
    }
  ]
}
```

## Settings UI

The Settings page now includes a "Pseudopotentials" card with:

1. **Store Directory** - Editable path with default
2. **Seed Directory** - Editable path with default
3. **Allow Network Downloads** - Toggle (OFF by default)
4. **Actions**:
   - Apply Changes - Save modified paths
   - Reset to Default - Restore default paths
   - Validate - Check configuration validity
   - Initialize Dirs - Create directories if missing
   - Install from Seed - Install SSSP from seed to store

## Files Created/Modified

### Backend (Python)

- `src/quantumvitas/core/pseudo_config.py` (NEW)
  - `PseudoConfig` dataclass
  - `load_pseudo_config()` / `save_pseudo_config()`
  - `validate_pseudo_config()`
  - `init_pseudo_dirs()`
  - `install_sssp_from_seed()` / `install_all_sssp_from_seed()`
  - `resolve_project_pseudos()`

- `src/quantumvitas/daemon/server.py` (MODIFIED)
  - Added RPC handlers for pseudo config

### Frontend (TypeScript/React)

- `gui/src/hooks/usePseudoConfig.ts` (NEW)
  - `usePseudoConfig()` hook

- `gui/src/components/panels/SettingsPanel.tsx` (MODIFIED)
  - Added `PseudopotentialsSection` component

- `gui/src/components/panels/SettingsPanel.css` (MODIFIED)
  - Added pseudo-specific styles

- `gui/src/types/qv.ts` (MODIFIED)
  - Added RPC types for pseudo config

## Future Work

- **PSEUDO Common Card** - UI in StepDetailPanel for species→pseudo mapping (uses resolution flow)
- **Download Implementation** - Actually fetch SSSP from Materials Cloud when allowed
- **SSSP Library Browser** - UI to select version/flavor and view available elements
- **Cutoff Recommendations** - Use cutoffs.json to suggest ecutwfc/ecutrho values

## Testing

Manual verification:
1. Settings page shows Pseudopotentials card below QE detection
2. Store/Seed dirs default to repo/temp/... paths
3. Allow download toggle defaults to OFF
4. Validate reports correct status for existing/missing dirs
5. Initialize Dirs creates directories
6. Install from Seed extracts SSSP archives (when seed files present)
7. Settings persist across app restart
8. Demos still work (repo/pseudo unchanged)

