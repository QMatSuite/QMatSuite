# Debug Notes: QE Detection and Pseudo Scanning

## QE Detection Flow

### Initialization Path

QE detection uses a **two-state model**:

1. **External QE**: If `settings.qe.bin_dir` is set (non-null), use that directory
2. **Internal QE**: If `settings.qe.bin_dir` is null, auto-select from `.qmatsuite/engines/qe/**/bin`

### Key Functions

- `resolve_qe_bin_dir(settings)`: Main resolver (two-state model)
  - Location: `src/qmatsuite/core/engines/qe_resolver.py`
  - Logs: `[QE_INIT]`, `[QE_STATE]`
  
- `preflight_check()`: Uses `resolve_qe_bin_dir()` to ensure QE is initialized
  - Location: `src/qmatsuite/api.py`
  - Logs: `[PREFLIGHT]`
  - **Fix**: Now uses two-state resolver instead of legacy `get_qe_home()`

### Log Markers

- `[QE_INIT]`: QE resolution attempt (settings source, bin_dir value)
- `[QE_STATE]`: QE state after resolution (source, bin_dir, mode, executables found)
- `[PREFLIGHT]`: Preflight QE check (detected status, reason, bin_dir, mode)

### Settings Storage

- Location: `~/.qmatsuite/settings.json` (machine-local)
- Schema: `{"version": "1.0", "qe": {"bin_dir": null | "<absolute_path>"}}`
- `bin_dir=null`: Use internal QE (auto-selected)
- `bin_dir="<path>"`: Use external QE (must contain pw.x)

### Bug Fix: QE Not Detected Until Settings Visit

**Root Cause**: `preflight_check()` was using legacy `get_qe_home()` which relies on environment variables and PATH, not the two-state resolver.

**Fix**: Updated `preflight_check()` to use `resolve_qe_bin_dir()` which:
1. Loads settings from disk
2. Checks `settings.qe.bin_dir`
3. Falls back to internal QE if `bin_dir` is null
4. Validates executables exist

**Result**: First Run now works without visiting Settings, assuming QE is installed in internal location.

## Pseudo Scanning Flow

### Directory Sources

Pseudo options are scanned from:

1. **Project pseudo dir**: `<project_root>/pseudo/` (after run, contains copied pseudos)
2. **Internal pseudo dir**: `resources/pseudo/` (built-in repo pseudos)
3. **Library archives**: Installed SSSP libraries (if available)

### Key Functions

- `get_pseudo_options_for_elements(project_root, elements)`: Main scanner
  - Location: `src/qmatsuite/core/pseudo_options.py`
  - Logs: `[PSEUDO_SCAN]`
  
- `_scan_pseudo_dir_cached(dir_path, element, ...)`: Cached directory scanner
  - Scans case-insensitively: `.UPF`, `.upf`, `.Upf`, etc.
  - Returns: `(file_path, sha256, basename)` tuples

### Log Markers

- `[PSEUDO_SCAN]`: Pseudo scanning operations
  - `Starting scan`: Initial scan with directories and elements
  - `Scanning directory`: Per-directory scan start
  - `Found N pseudo files`: Scan results per directory
  - `Scan complete`: Final summary (total variants, elements with options)

### Bug Fix: Empty Pseudo Dropdown

**Root Cause**: 
1. Case-sensitive extension matching (only `.UPF` and `.upf` patterns)
2. Missing logging made debugging difficult

**Fix**:
1. Updated `_scan_pseudo_dir_cached()` to scan all case variations (8 patterns)
2. Added deduplication by lowercase filename
3. Added comprehensive logging at all scan stages
4. Updated internal pseudo scan to use same case-insensitive logic

**Result**: Dropdown now shows pseudos from both project and internal directories, regardless of file extension case.

## Where to Look in Logs

### QE Detection Issues

1. Check `[QE_INIT]` logs: Shows settings source and `bin_dir` value
2. Check `[QE_STATE]` logs: Shows resolved bin_dir, mode (external/internal), executables found
3. Check `[PREFLIGHT]` logs: Shows QE check result and reason

**Example log sequence**:
```
[QE_INIT] Resolving QE bin directory: settings.qe.bin_dir=None, source=loaded
[QE_STATE] source=internal_scan qe_bin_dir=/Users/.../.qmatsuite/engines/qe/q-e-qe-7.5/bin mode=internal executables_found=['pw.x', 'ph.x', ...]
[PREFLIGHT] qe_detected=true reason='Found pw.x at ...' qe_bin_dir=... mode=internal
```

### Pseudo Scanning Issues

1. Check `[PSEUDO_SCAN] Starting scan`: Shows directories and elements
2. Check `[PSEUDO_SCAN] Scanning directory`: Per-directory scans
3. Check `[PSEUDO_SCAN] Found N pseudo files`: File counts per directory
4. Check `[PSEUDO_SCAN] Scan complete`: Final summary

**Example log sequence**:
```
[PSEUDO_SCAN] Starting scan: project_pseudo_dir=/path/to/project/pseudo, internal_pseudo_dir=/path/to/resources/pseudo, elements=['Si', 'O']
[PSEUDO_SCAN] Scanning directory: /path/to/project/pseudo
[PSEUDO_SCAN] Found 2 pseudo files in /path/to/project/pseudo: ['Si.UPF', 'O.upf']
[PSEUDO_SCAN] Scanning internal pseudo directory: /path/to/resources/pseudo
[PSEUDO_SCAN] Found 5 internal pseudo files in /path/to/resources/pseudo
[PSEUDO_SCAN] Scan complete: total_variants=7, elements_with_options=['Si', 'O']
```

## UI Fixes

### Bug 2: Calculation Overview Panel Clipping

**Fix**: Added padding-bottom to scroll containers and ensured last section has margin:
- `.calculation-overview-tab__scroll-container`: Added `padding-bottom: var(--space-4)`
- `.calculation-detail-panel .panel-content`: Added `padding-bottom: var(--space-6)` and `min-height: fit-content`
- `.detail-section:last-child`: Changed from `margin-bottom: 0` to `margin-bottom: var(--space-4)`

### Bug 3: Workflow Indicator Unreadable

**Fix**: Updated workflow badge to use theme CSS variables:
- Background: `var(--bg-secondary)` (was hardcoded `#f0f0f0`)
- Border: `var(--border-color)`
- Text: `var(--text-primary)` (was implicit white)
- Button: Uses `var(--bg-button)` and `var(--text-secondary)` with hover states

