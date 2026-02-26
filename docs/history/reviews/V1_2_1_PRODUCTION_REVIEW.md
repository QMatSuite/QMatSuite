# QMatSuite v1.2.1 Production Release Review

**Date**: 2026-02-25 / 2026-02-26
**Tested on**: Clean macOS ARM VM (Apple Silicon) + Clean Windows x64 system
**Release**: [v1.2.1](https://github.com/QMatSuite/QMatSuite/releases/tag/v1.2.1)
**Reviewer**: Manual QA + deep code review

---

## Table of Contents

1. [P1 — Auto-Update Fails: "ZIP file not provided"](#p1)
2. [P2 — "Check Updates" Silent When Already Up-to-Date](#p2)
3. [P3 — Sidebar Version Hard-Coded to "v2.0.0"](#p3)
4. [P4 — Welcome Text QE-Centric (Should Be Engine-Agnostic)](#p4)
5. [P5 — "Volume (DEV)" Visible in Production Sidebar](#p5)
6. [P6 — Online Search Parses "titanium" as "TiTaNiUm"](#p6)
7. [P7 — Online Search Filter Buttons Look Ambiguous](#p7)
8. [P8 — Online Search Slow (>8s for "Ti")](#p8)
9. [P9 — Structure Selector Broken for New/Non-Demo Calculations](#p9)
10. [P10 — Pseudopotentials Not Updated After Structure Change](#p10)
11. [P11 — Edit Pseudo Dialog: Wrong Element + SSSP Library Not Found](#p11)
12. [P12 — Add Step Dropdown Confusing (Missing Gen-Type Labels)](#p12)
13. [P13 — Calculation Digest Too Verbose, Pushes Plot Down](#p13)
14. [P14 — No Auto-Select of Plot Tab When Step Clicked](#p14)
15. [P15 — Reference Checkbox Appears Non-Functional](#p15)
16. [P16 — Resources Tab First-Load Shows Empty](#p16)
17. [P17 — Settings Engine Info Panel Chaotic Layout](#p17)
18. [P18 — Electron Scrolling / Rendering Generally Slow](#p18)
19. [P19 — Demo Gallery Slow + Needs Sorting by Engine](#p19)
20. [P20 — xTB Raw Output Error (Exists but Not Displayed)](#p20)
21. [P21 — Raw Output Path Normalization Bug (All Engines)](#p21)
22. [P22 — Calculation Panel Half-Shown / Clipping](#p22)
23. [P23 — Sensitive Path Leak in Settings UI](#p23)
24. [P24 — Wannier90 3D Fixtures Error in Volume Viewer](#p24)
25. [P25 — macOS Music Permission Dialog on Settings Page Load](#p25)
26. [P26 — SSSP Library Install: No Progress Bar](#p26)
27. [P27 — SSSP Library: "Installed (0)" After Successful Download](#p27)

**Windows System Tests (2026-02-26)**

28. [P28 — NSIS Installer Slow and Uninformative](#p28)
29. [P29 — First Startup: matplotlib Font Cache Rebuild Blocks 30+ Seconds](#p29)
30. [P30 — First Startup: OPTIMADE Provider Fetch Blocks 140 Seconds](#p30)
31. [P31 — First Startup: engine.list Times Out at 60s](#p31)
32. [P32 — Demo Gallery Missing 17 Demos Due to UTF-8 Encoding Bug](#p32)
33. [P33 — Demo "0 Si SCF" Step Detail Fails to Load](#p33)
34. [P34 — Engine Install Cannot Be Cancelled](#p34)
35. [P35 — QE Resolver / Engine Registry Dual-System Disconnect](#p35)

---

<a id="p1"></a>
## P1 — Auto-Update Fails: "ZIP file not provided"

**Severity**: CRITICAL
**Category**: Update system
**Screenshots**: Images 1–3

### Observed Behavior

When clicking "Download" on the update banner (correctly detected v1.2.1), the update fails with:
```
ZIP file not provided: [{ "url": "https://github.com/QMatSuite/QMatSuite/releases/download/v1.2.1/QMatSuite-macOS-1.2.1.dmg",
"info": { "url": "QMatSuite-macOS-1.2.1.dmg", "sha512": "QCIXUeqE1baIsSXaC5Z9xN8BsDyr7VaaxHRamOyrEAEGPyZSiKAb...",
"size": 547142790 } }]
```

### Root Cause

**electron-updater** (v6.3.9) expects a `.zip` file alongside the `.dmg` for macOS delta updates. The release workflow only produces `.dmg`, `.dmg.blockmap`, and `latest-mac.yml` — no `.zip`.

**Files involved**:
- `gui/electron-builder.json5` (line 38–48): `mac.target` only lists `"dmg"` — no `"zip"` target
- `.github/workflows/release-macos.yml` (lines 327, 341, 396, 410): Uses `--publish never`, then manually uploads only `.dmg`, `.dmg.blockmap`, `latest-mac.yml` at lines 548–551
- electron-updater's internal differentialDownloadInstaller code checks for a ZIP entry in `latest-mac.yml` and throws when none is found

### Proposed Fix

**Option A (Recommended)**: Add `"zip"` to the macOS build target so electron-builder generates both `.dmg` and `.zip`:

```json5
// gui/electron-builder.json5, mac section
"mac": {
  "target": [
    {
      "target": "dmg",
      "arch": ["arm64"]
    },
    {
      "target": "zip",
      "arch": ["arm64"]
    }
  ],
  // ...
}
```

Then update the release workflow to also upload the `.zip` artifact alongside the `.dmg`.

**Option B**: Disable differential downloads in electron-updater:

```typescript
// gui/electron/main.ts, in configureAutoUpdater()
autoUpdater.autoDownload = false;
autoUpdater.disableDifferentialDownload = true; // <-- add this
```

Option A is preferred because it also enables smaller delta updates for future releases.

---

<a id="p2"></a>
## P2 — "Check Updates" Silent When Already Up-to-Date

**Severity**: HIGH
**Category**: UX
**Screenshots**: Image 4

### Observed Behavior

After manually updating to v1.2.1, clicking "Check Updates" does nothing visible. No message, no banner, no feedback. The user has no way to confirm the check succeeded.

### Root Cause

The `update-not-available` state is not included in the banner visibility check:

```typescript
// gui/src/components/AppLayout.tsx:747-751
const showUpdaterBanner = Boolean(
  shell.updaterState &&
  !shell.updaterDismissed &&
  ['available', 'downloading', 'downloaded', 'error'].includes(shell.updaterState.state),
  //                                                            ^^^ 'not-available' excluded
);
```

The `electron-updater` fires `update-not-available` → state becomes `'not-available'` → banner condition returns false → nothing shown.

Related: `gui/electron/main.ts:167-173`:
```typescript
autoUpdater.on('update-not-available', () => {
  setUpdaterState({
    state: 'not-available',
    progress: 0,
    message: 'No updates available', // ← This message is set but never displayed
  });
});
```

### Proposed Fix

Add a transient "up to date" notification. Two approaches:

**Approach 1 — Include in banner with auto-dismiss**:
```typescript
// AppLayout.tsx:747-751
const showUpdaterBanner = Boolean(
  shell.updaterState &&
  !shell.updaterDismissed &&
  ['available', 'downloading', 'downloaded', 'error', 'not-available'].includes(shell.updaterState.state),
);
```

Add banner title case:
```typescript
: shell.updaterState.state === 'not-available'
  ? 'You are up to date'
```

Add auto-dismiss after 5 seconds for `not-available` state:
```typescript
useEffect(() => {
  if (shell.updaterState?.state === 'not-available') {
    const timer = setTimeout(() => shell.setUpdaterDismissed(true), 5000);
    return () => clearTimeout(timer);
  }
}, [shell.updaterState?.state]);
```

**Approach 2 — Toast notification** (preferred for cleanliness):
Add a toast/snackbar system and display a brief "QMatSuite is up to date" message for 3–5 seconds.

---

<a id="p3"></a>
## P3 — Sidebar Version Hard-Coded to "v2.0.0"

**Severity**: HIGH
**Category**: Bug
**Screenshots**: Images 1, 3, 6 (bottom-left of sidebar shows "QMatSuite v2.0.0")

### Observed Behavior

Sidebar footer shows "QMatSuite v2.0.0" but the actual release is v1.2.1 (package.json `"version": "1.2.1"`).

### Root Cause

Hard-coded version string in sidebar:

```typescript
// gui/src/components/layout/Sidebar.tsx:301
{!isCollapsed && <span className="sidebar__version">QMatSuite v2.0.0</span>}
```

### Proposed Fix

Read version from `package.json` or Electron's `app.getVersion()`:

```typescript
// In Sidebar component, use version from electron
const appVersion = window.qms?.getAppVersion?.() ?? 'unknown';
// ...
{!isCollapsed && <span className="sidebar__version">QMatSuite v{appVersion}</span>}
```

Or import from package.json at build time via a Vite define constant:
```typescript
// vite.config.ts
define: {
  __APP_VERSION__: JSON.stringify(require('./package.json').version),
}
```

---

<a id="p4"></a>
## P4 — Welcome Text QE-Centric (Should Be Engine-Agnostic)

**Severity**: MEDIUM
**Category**: UX / Branding
**Screenshots**: Images 1, 3

### Observed Behavior

- Welcome subtitle: "Manage Quantum ESPRESSO calculations with ease"
- Create New button: "Start a new QE calculation project"
- Settings sidebar tooltip: "Configure QE paths and app settings"

QMatSuite supports 15 engines. QE-specific text misleads users about multi-engine capability.

### Root Cause

Hard-coded strings in:

```typescript
// gui/src/components/panels/ProjectSummaryPanel.tsx:105-107
<p className="welcome-subtitle">
  Manage Quantum ESPRESSO calculations with ease
</p>

// gui/src/components/panels/ProjectSummaryPanel.tsx:132
<span className="welcome-button__desc">Start a new QE calculation project</span>

// gui/src/components/layout/Sidebar.tsx:276
title="Configure QE paths and app settings"
```

### Proposed Fix

Replace with engine-agnostic text:
- "Manage Quantum ESPRESSO calculations with ease" → "Manage computational materials science workflows"
- "Start a new QE calculation project" → "Start a new calculation project"
- "Configure QE paths and app settings" → "Configure engine paths and app settings"

---

<a id="p5"></a>
## P5 — "Volume (DEV)" Visible in Production Sidebar

**Severity**: HIGH
**Category**: Build / Production hygiene
**Screenshots**: Images 1, 6, 7

### Observed Behavior

Sidebar shows "Volume (DEV)" nav item at the bottom with a separator line. This is a developer-only sandbox for the Volume Viewer. Clicking it shows a Wannier90 3D fixtures error (P24).

### Root Cause

Dev-only code unconditionally rendered:

```typescript
// gui/src/components/layout/Sidebar.tsx:282-292
{/* DEV ONLY: Volume Viewer Sandbox */}
<button
  className={`sidebar__tab ${currentView === 'dev-volume' ? 'active' : ''}`}
  onClick={() => onViewChange('dev-volume')}
  title="[DEV] Volume Viewer Sandbox"
  data-testid="qms-nav-dev-volume"
  style={{ borderTop: '2px solid #f0f0f0', marginTop: '8px', paddingTop: '8px' }}
>
  <span className="sidebar__tab-icon">🧊</span>
  {!isCollapsed && 'Volume (DEV)'}
</button>
```

No environment check, no build flag — always visible.

### Proposed Fix

Gate behind environment check:

```typescript
{import.meta.env.DEV && (
  <button className={...} onClick={...} title="[DEV] Volume Viewer Sandbox" ...>
    <span className="sidebar__tab-icon">🧊</span>
    {!isCollapsed && 'Volume (DEV)'}
  </button>
)}
```

`import.meta.env.DEV` is `true` only in Vite dev mode, `false` in production builds.

---

<a id="p6"></a>
## P6 — Online Search Parses "titanium" as "TiTaNiUm"

**Severity**: CRITICAL
**Category**: Backend bug
**Screenshots**: Image 7

### Observed Behavior

Searching "titanium" in the online import panel triggers daemon warnings:
```
Failed to reduce formula TiTaNiUm: Can't parse Element or Species from 'Um'
```
The search fails or returns partial/wrong results.

### Root Cause

Greedy regex in `normalize_formula()`:

```python
# src/qmatsuite/io/online_search.py:81
formula = re.sub(r'([A-Za-z]{1,2})(\d*)', capitalize_element, formula)
```

The regex `([A-Za-z]{1,2})` greedily matches any 1–2 letter combination without validating against the periodic table:
- "titanium" → matches `Ti` `Ta` `Ni` `Um` → "TiTaNiUm"
- "copper" → matches `Co` `Pp` `Er` → "CoPpEr"
- "sodium" → matches `So` `Di` `Um` → "SoDiUm"

The function has no concept of element validity — it just capitalizes letter pairs.

### Proposed Fix

**Multi-layer approach**:

1. **Detect plain-text element names** before attempting formula normalization:

```python
from pymatgen.core import Element

# Common element name → symbol mapping
_ELEMENT_NAME_TO_SYMBOL: dict[str, str] = {}
for z in range(1, 119):
    try:
        elem = Element.from_Z(z)
        _ELEMENT_NAME_TO_SYMBOL[elem.long_name.lower()] = elem.symbol
    except Exception:
        pass

def normalize_formula(formula: str) -> str:
    formula_stripped = formula.strip()

    # Step 1: Check if input is a plain element name (e.g., "titanium", "silicon")
    if formula_stripped.lower() in _ELEMENT_NAME_TO_SYMBOL:
        return _ELEMENT_NAME_TO_SYMBOL[formula_stripped.lower()]

    # Step 2: Remove spaces
    formula_clean = re.sub(r'\s+', '', formula_stripped)

    # Step 3: Validate-then-capitalize using known element symbols
    # Use a regex that prioritizes valid 2-letter symbols, then 1-letter
    _VALID_SYMBOLS = {e.symbol for e in Element}
    # ... validate each match against _VALID_SYMBOLS
```

2. **Validate regex matches** against pymatgen's Element table before accepting them as chemical symbols.

3. **Add a "search by name" fallback**: If formula normalization fails entirely, search by element name in OPTIMADE's `elements` filter instead of `chemical_formula_reduced`.

---

<a id="p7"></a>
## P7 — Online Search Filter Buttons Look Ambiguous

**Severity**: LOW
**Category**: UX / Visual design
**Screenshots**: Image 7

### Observed Behavior

The filter area shows "🔷Crystals🔮Molecules🔬All" crammed together with emoji icons. It's unclear whether these are:
- Toggle buttons (radio-style, mutually exclusive)
- Checkboxes (multi-select)
- Just labels

The emojis visually collide with the text, making the UI feel cluttered.

### Root Cause

```typescript
// gui/src/components/panels/OnlineImportPanel.tsx:132-157
<div className="online-import-panel__mode-tabs">
  <button className={`online-import-panel__mode-tab ${mode === "crystal" ? "..." : ""}`}
    onClick={() => setMode("crystal")}>
    🔷 Crystals
  </button>
  <button className={`online-import-panel__mode-tab ${mode === "molecule" ? "..." : ""}`}
    onClick={() => setMode("molecule")}>
    ⚛️ Molecules
  </button>
  <button className={`online-import-panel__mode-tab ${mode === "auto" ? "..." : ""}`}
    onClick={() => setMode("auto")}>
    🔄 All
  </button>
</div>
```

These ARE proper mutually-exclusive toggle buttons (radio behavior). The problem is purely visual — inadequate spacing, emoji styling, and no clear active-state differentiation.

### Proposed Fix

1. Add explicit gap between buttons via CSS: `gap: 0.5rem`
2. Use a segmented-control pattern (connected buttons with dividers) instead of separate floating buttons
3. Remove emojis and use colored dot indicators or icons from an icon set
4. Add clear `border`, `background`, and `font-weight` differentiation for the active state
5. Consider renaming "All" to "Any type" for clarity

---

<a id="p8"></a>
## P8 — Online Search Slow (>8s for "Ti")

**Severity**: MEDIUM
**Category**: Performance
**Screenshots**: Image 7 (daemon log shows `took 8166.5ms`)

### Observed Behavior

Searching "Ti" takes >8 seconds. The daemon log shows the full round-trip:
```
structure_search_online (req_id=...) took 8166.5ms
```

### Root Cause

The search queries **6 OPTIMADE providers in parallel**, but the total time is bounded by the slowest provider:

```python
# src/qmatsuite/io/providers/optimade.py — CURATED_DEFAULT_PROVIDERS
# Materials Project, COD, Alexandria, OQMD, JARVIS, Materials Cloud
```

- Some providers (OQMD, COD, JARVIS) are known to be slow (3–8s response times)
- The parallel executor uses `ThreadPoolExecutor` with a generous timeout
- Even with parallel queries, the UI blocks until ALL providers respond or timeout
- Per-provider HTTP latency varies from 0.5s (Materials Project) to 8s+ (OQMD)

### Proposed Fix

1. **Progressive results**: Return results as each provider responds, don't wait for all. Use a streaming/chunked approach where the frontend displays partial results immediately.

2. **Aggressive per-provider timeout**: Set a 3-second per-provider timeout. If a provider doesn't respond in 3s, skip it and show results from faster providers.

3. **Provider priority**: Try Materials Project first (fastest, most reliable). Only query other providers if MP returns fewer than `limit` results.

4. **Caching**: Cache successful formula-to-results mappings in memory (TTL: 5 minutes). Subsequent searches for the same formula return instantly.

5. **UI loading states**: Show a spinner immediately and render results as they arrive, with a provider status indicator.

---

<a id="p9"></a>
## P9 — Structure Selector Broken for New/Non-Demo Calculations

**Severity**: CRITICAL
**Category**: Backend/Frontend integration
**Screenshots**: Images 9, 10

### Observed Behavior

- Created a new calculation "ti-scf"
- Cannot select the imported Ti structure from the structure dropdown — shows only "-- None --"
- Cannot select the existing Silicon structure either (from the demo project)
- BUT the demo "Si bands" calculation CAN freely select structures (Image 11)

### Root Cause

The structure dropdown in `CalculationListPanel.tsx` (lines 1220–1240) uses `effectiveStructures` state. When a new calculation is created:

1. Frontend calls `list_structures` RPC to get available structures
2. The response should include all project structures
3. However, the newly created calculation may not have its structure associations refreshed in the project registry

The deeper issue is in the `change_calculation_structure` RPC handler (`src/qmatsuite/daemon/server.py:3264-3374`):
- It resolves non-ULID selectors by looking up in the project registry
- A newly imported structure may not be registered yet in the calculation's structure list
- The daemon log confirms the resolution works (`selector='ti-1-sites' -> ulid=...`) but the frontend dropdown is not populated with available structures

**Frontend gap**: The dropdown options come from `effectiveStructures` which may not be refreshed after a structure import or calculation creation. The structure list fetch may race with the calculation detail fetch.

### Proposed Fix

1. **Backend**: After `create_calculation` and `import_structure`, the daemon should emit a refresh signal for the structures list.

2. **Frontend**: After importing a structure, explicitly re-fetch the structure list and update `effectiveStructures`:
```typescript
// After successful structure import:
const structures = await qms.listStructures(projectRoot);
setLocalStructures(structures);
```

3. **Invalidation**: Add cache invalidation for the structures list when any mutation occurs (import, delete, rename).

---

<a id="p10"></a>
## P10 — Pseudopotentials Not Updated After Structure Change

**Severity**: CRITICAL
**Category**: Backend logic
**Screenshots**: Images 12, 13

### Observed Behavior

In the "Si bands" demo calculation:
- Changed structure from Si to "Ti (1 sites)"
- Pseudopotentials still show: "Si: Si.pbe-n-rrkjus_psl.1.0.0.UPF"
- Should show Ti pseudopotential options

### Root Cause

The `change_calculation_structure` RPC handler does NOT refresh the pseudopotential mapping:

```python
# src/qmatsuite/daemon/server.py:3264-3374
# _handle_change_calculation_structure():
#   1. Resolves calculation and structure ULIDs  ✓
#   2. Calls svc.calculation.set_structure()       ✓
#   3. Returns updated calculation detail           ✓
#   4. Refreshes pseudo mapping                     ✗  ← MISSING
```

The `set_structure()` method (`src/qmatsuite/api/service.py:4579-4667`):
- Updates `calculation.yaml` with new `structure_ulid`
- Updates step structure fields
- Does NOT update `species_map` in calculation.yaml with new elements

The pseudo mapping (`get_pseudo_mapping()` at `service.py:6062-6166`) reads from existing `wf_model.species_map`:
```python
if wf_model.species_map:
    for element, settings in wf_model.species_map.items():
        pseudo = settings.get("pseudopot", "")
        if pseudo:
            mapping[element] = pseudo
```

Since `species_map` still contains `{"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}}`, the old mapping is returned.

### Proposed Fix

1. **In `set_structure()`**: After updating structure_ulid, read the new structure's composition and rebuild `species_map`:

```python
# In set_structure(), after writing new structure_ulid:
new_elements = extract_elements_from_structure(new_structure_ulid, project_root)
new_species_map = {}
for elem in new_elements:
    new_species_map[elem] = {"pseudopot": ""}  # Clear old mapping, prompt user to resolve
wf_model.species_map = new_species_map
# Save updated calculation.yaml
```

2. **In frontend**: After structure change response, re-fetch pseudo mapping and display a prompt for the user to select pseudopotentials for new elements.

---

<a id="p11"></a>
## P11 — Edit Pseudo Dialog: Wrong Element + SSSP Library Not Found

**Severity**: CRITICAL
**Category**: Backend integration
**Screenshots**: Images 13, 14, 15

### Observed Behavior

1. After changing to Ti structure, clicking "Edit" pseudo opens dialog showing "Si" element (not Ti)
2. Daemon log shows scan was performed for Ti:
   ```
   PSEUDO_SCAN Starting scan: ... elements=['Ti']
   Scanning internal pseudo directory: .../site-packages/qmatsuite/resources/pseudo
   Found 28 internal pseudo files in .../site-packages/qmatsuite/resources/pseudo
   Scan complete: total_variants=25, elements_with_options=['Ti']
   ```
3. But the dropdown shows "-- Select --" with no options
4. When switching back to Silicon, also only sees project and internal resources — NOT the external SSSP library at `~/Library/Application Support/QMatSuite/libraries/pseudo/SSSP/efficiency/1.3.0`

### Root Cause (Multi-Layer)

**Layer 1 — Wrong element shown**: The pseudo dialog receives elements from `species_map` (which still has Si, per P10). The dialog's element column shows whatever was in the mapping, not the current structure's composition.

**Layer 2 — SSSP not searched**: The pseudo scanner has three sources:
1. Project pseudo dir (`project_root/pseudo`) ✓ scanned
2. Internal bundled pseudos (`resources/pseudo`) ✓ scanned
3. Installed libraries (`~/Library/Application Support/QMatSuite/libraries/pseudo/`) — **scan may skip or fail**

The library scanning path (`src/qmatsuite/core/pseudo_options.py:470-538`) relies on:
- `find_upf_in_libraries()` in `src/qmatsuite/pseudo/layout.py:82-91`
- This walks `<libraries_root>/<Library>/<variant>/<version>/` looking for `head.json`
- If `head.json` is missing or malformed, the library is invisible to the scanner

**Layer 3 — Dropdown empty despite scan finding options**: The daemon reports `elements_with_options=['Ti']` and `total_variants=25`, but the frontend dropdown shows "-- Select --". This suggests the RPC response format may not match what the frontend expects, or the frontend isn't mapping the response correctly.

### Proposed Fix

1. **Fix element list source**: The pseudo dialog must derive elements from the CURRENT structure, not from `species_map`. Add an explicit parameter `elements` to the `get_pseudo_options_for_calculation` RPC that comes from the structure's composition.

2. **Fix library scanning**: Ensure the library scanner traverses the SSSP directory structure correctly:
   - Verify `head.json` exists in `SSSP/efficiency/1.3.0/`
   - If not, create one during library installation
   - Add fallback: if no `head.json`, scan for `.UPF`/`.upf` files directly

3. **Fix frontend mapping**: Verify the `get_pseudo_options_for_calculation` response DTO matches the frontend's expected format for populating the dropdown.

---

<a id="p12"></a>
## P12 — Add Step Dropdown Confusing (Missing Gen-Type Labels)

**Severity**: MEDIUM
**Category**: UX
**Screenshots**: Image 16

### Observed Behavior

The "Add Step" dropdown shows raw step type identifiers. User has to guess what each step does. No engine prefix or human-readable label visible.

### Root Cause

```typescript
// gui/src/components/panels/CalculationOverviewTab.tsx:473-476
{stepPalette?.base_steps.map((step) => (
  <option key={step.gen} value={step.gen}>
    {step.description || step.gen.toUpperCase()}
  </option>
))}
```

The dropdown shows `step.description` which is defined in step_types.py, e.g.:
```python
# src/qmatsuite/drivers/qe/step_types.py
description="QE SCF calculation"
```

However, the format doesn't include the gen step type in a prominent way. The user sees "QE SCF calculation" but doesn't see the short identifier like "[SCF]" at the beginning.

### Proposed Fix

Format the dropdown options as `[GEN_TYPE] Description`:

```typescript
<option key={step.gen} value={step.gen}>
  {`[${step.gen.toUpperCase()}] ${step.description || step.gen}`}
</option>
```

This would show: `[SCF] QE SCF calculation`, `[RELAX] QE relaxation`, etc.

Also consider grouping base steps and companion steps with clear visual separation.

---

<a id="p13"></a>
## P13 — Calculation Digest Too Verbose, Pushes Plot Down

**Severity**: MEDIUM
**Category**: UX
**Screenshots**: Image 18

### Observed Behavior

The analysis panel shows ALL digest fields in a flat table:
- band_gap_ev, converged, fermi_energy_ev, homo_ev, lumo_ev, n_iterations, total_cpu_time_s, total_energy_ry, total_magnetization, total_wall_time_s

This ~10-row table occupies significant vertical space, pushing the band structure plot far below the fold. Users must scroll to find the visualization.

### Root Cause

```typescript
// gui/src/components/panels/StepDigestPanel.tsx:41-50
<table className="analysis-digest__table">
  <tbody>
    {Object.entries(digest).map(([key, value]) => (
      <tr key={key}>
        <th>{key}</th>
        <td>{formatDigestValue(value)}</td>
      </tr>
    ))}
  </tbody>
</table>
```

No filtering, no collapsing, no priority ordering. Every field is rendered with equal prominence.

### Proposed Fix

**1. Summary line**: Show only the most critical value(s) in a single compact line:
```
Energy: -22.839 Ry | Converged ✓ | Gap: 0.685 eV | 4 iterations
```

**2. Expandable details**: Hide secondary fields (timing, magnetization, etc.) behind an expand/collapse toggle:

```typescript
const PRIMARY_KEYS = ['total_energy_ry', 'converged', 'band_gap_ev', 'fermi_energy_ev'];
const [expanded, setExpanded] = useState(false);

const entries = Object.entries(digest);
const primary = entries.filter(([k]) => PRIMARY_KEYS.includes(k));
const secondary = entries.filter(([k]) => !PRIMARY_KEYS.includes(k));

return (
  <div className="analysis-digest">
    <div className="analysis-digest__summary">
      {primary.map(([key, val]) => <span key={key}>{key}: {formatDigestValue(val)}</span>)}
    </div>
    {secondary.length > 0 && (
      <button onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Hide details' : `Show ${secondary.length} more fields`}
      </button>
    )}
    {expanded && (
      <table>...</table>
    )}
  </div>
);
```

**3. Reorder**: Also place the plot ABOVE the digest section, since the visualization is typically what users want to see first.

---

<a id="p14"></a>
## P14 — No Auto-Select of Plot Tab When Step Clicked

**Severity**: MEDIUM
**Category**: UX
**Screenshots**: Image 19

### Observed Behavior

When clicking a step tab in the Analysis panel, the view mode stays on "Raw" even if plot data is available. User must manually click "Plot" to see visualizations.

### Root Cause

```typescript
// gui/src/components/panels/CalculationAnalysisPanel.tsx:47
const [viewMode, setViewMode] = useState<StepViewMode>('raw');
```

Default is `'raw'` and it never auto-switches when plot data becomes available. The only auto-switch is in reference-only mode (line ~372):
```typescript
setViewMode('analysis');
```

But this doesn't apply when real run data exists.

### Proposed Fix

After fetching analysis objects for a step, check if plot data exists and auto-switch:

```typescript
// In the useEffect that fetches available object types:
useEffect(() => {
  if (availableObjectTypes.length > 0) {
    // Auto-switch to plot view if analysis data is available
    setViewMode('analysis');
    // Auto-select first available object type
    if (!selectedObjectType) {
      setSelectedObjectType(availableObjectTypes[0]);
    }
  } else {
    // No plots available, show raw output
    setViewMode('raw');
  }
}, [availableObjectTypes]);
```

---

<a id="p15"></a>
## P15 — Reference Checkbox Appears Non-Functional

**Severity**: LOW
**Category**: UX
**Screenshots**: Image 19

### Observed Behavior

The "Reference" checkbox in the Analysis panel header doesn't appear to change anything when toggled.

### Root Cause

```typescript
// gui/src/components/panels/CalculationAnalysisPanel.tsx:492-502
{(referenceData || referenceOnlyMode) && (
  <label className="calculation-analysis-panel__ref-toggle">
    <input
      checked={showReference}
      onChange={(e) => setShowReference(e.target.checked)}
      type="checkbox"
    />
    Reference
  </label>
)}
```

The checkbox controls `showReference` state, which conditionally renders reference data overlays (line 554):
```typescript
{referenceOnlyMode && showReference && referenceData && ( ... )}
```

**Issue**: The conditional uses `referenceOnlyMode && showReference` — when real run data exists (not reference-only), `referenceOnlyMode` is false, so the checkbox state has no effect. The reference overlay is only shown in reference-only mode.

### Proposed Fix

The reference checkbox should work as a toggle for overlaying reference data ON TOP of real run data (comparison mode):

```typescript
// When real data AND reference data both exist:
{showReference && referenceData && (
  <ReferenceOverlay data={referenceData} />
)}
```

Remove the `referenceOnlyMode &&` guard so reference data can be shown alongside real data.

---

<a id="p16"></a>
## P16 — Resources Tab First-Load Shows Empty

**Severity**: MEDIUM
**Category**: Frontend race condition
**Screenshots**: Images 21, 22

### Observed Behavior

Opening the Resources tab:
- Engine dropdown shows "Quantum ESPRESSO" (correct)
- Category dropdown shows "pw.x" (correct)
- But the parameter table shows "No parameters found for this category."
- MANUALLY reselecting "pw.x" in the dropdown fixes the issue — parameters load correctly

### Root Cause

Race condition in `EngineParameterBrowserPanel.tsx` (lines 313–318):

```typescript
// After categories load, auto-select first category:
if (categoryList.length > 0) {
  const firstCategory = categoryList[0];
  await handleCategoryChange(firstCategory.id, { autoLoadTags: true });
}
```

The `handleCategoryChange` function (line ~202) updates `selectedCategoryRef.current` and fetches tags. However, the React state update for `selectedCategory` happens asynchronously, and the component may re-render with the old empty state before the tag fetch completes.

The core issue: `setCategories(categoryList)` and the subsequent `handleCategoryChange()` are in the same async block. React may batch the state update for `categories` but the `handleCategoryChange` callback may reference stale state.

### Proposed Fix

Split the auto-select into a separate `useEffect` that fires after categories are populated:

```typescript
// Effect 1: Load categories
useEffect(() => {
  // ... fetch categories, setCategories(categoryList)
}, [qms, engineFamily]);

// Effect 2: Auto-select first category when categories change
useEffect(() => {
  if (categories.length > 0 && !selectedCategory) {
    handleCategoryChange(categories[0].id, { autoLoadTags: true });
  }
}, [categories, selectedCategory, handleCategoryChange]);
```

This ensures React has committed the categories state before attempting the auto-select.

---

<a id="p17"></a>
## P17 — Settings Engine Info Panel Chaotic Layout

**Severity**: MEDIUM
**Category**: UX / Layout
**Screenshots**: Images 23, 24

### Observed Behavior

The Settings panel has two separate sections:
1. **Engine Management panel** — flat list of all engines with Install/Configure Path buttons (Image 23)
2. **Engine info tabs** — separate expandable cards showing each engine's supported gen steps and status (Image 24)

These are displayed sequentially, creating a very long scrollable page with redundant information. Engine Management and Engine Info should be unified.

### Observed Issues (from screenshots)

- Each engine takes 2-3 lines in Engine Management (name + status + buttons)
- Then each engine takes 2-3 more lines in the info section (name + supported steps)
- QE is buried in alphabetical order instead of being first (since it's installed and most used)
- No visual hierarchy — all engines look the same regardless of installation status
- QE HOME path shows real user path (`~/Library/...`) — potential sensitive info leak (see P23)

### Proposed Fix

**Unified engine card layout**:
- One card per engine, sorted by: installed first, then alphabetical
- Each card shows: engine name + installation status on one line
- Click to expand: shows install path, supported steps, re-detect button
- QE (and other installed engines) should be prominently shown at top
- Uninstalled engines should be collapsed to a single line each
- Group by installation type: "Installed", "Available to Install", "Manual Path Only"

---

<a id="p18"></a>
## P18 — Electron Scrolling / Rendering Generally Slow

**Severity**: HIGH
**Category**: Performance
**Screenshots**: Images 5, 6, 20

### Observed Behavior

Multiple panels exhibit slow scrolling and rendering:
- Calculation list scrolling is sluggish
- Daemon log scrolling is slow
- General UI responsiveness is poor on the Mac ARM VM

### Root Cause (Multiple factors)

**1. No virtual scrolling** — All list components use plain `.map()` rendering:

```typescript
// CalculationListPanel.tsx:225-299 — renders ALL items
{calculations.map((calc) => (
  <div className="calculation-card" key={calc.ulid}>
    {/* 8-10 nested elements per card */}
  </div>
))}
```

**2. Daemon log rendering** — Uses array index as React key (anti-pattern):

```typescript
// DebugPanel.tsx:152-156
{messages.map((msg, i) => (
  <div key={i} className={...}>{msg.text}</div>
))}
```

Index keys cause full re-renders on every new log message (all items shift).

**3. No rendering optimization** — No `React.memo`, no `useMemo`, no `useCallback` for child components in hot paths. Every state change re-renders all children.

**4. Excessive DOM nodes** — Each calculation card has ~10 sub-elements. 50 calculations = 500+ DOM nodes. Daemon log can have 500+ entries visible.

### Proposed Fix

**Priority 1 — Virtual scrolling** for all long lists:
- Use `react-window` or `react-virtuoso` for:
  - Calculation list
  - Daemon log
  - Demo gallery
  - Parameter browser tags table
- Only render items visible in viewport + small buffer

**Priority 2 — React.memo** for list items:
```typescript
const CalculationCard = React.memo(({ calc, isSelected, onClick }) => {
  // ... card rendering
});
```

**Priority 3 — Stable keys**:
- Daemon log: Use message ID or timestamp as key instead of array index
- Calculation list: Already uses `calc.ulid` (good)

**Priority 4 — Debounced scroll handlers**:
- Ensure scroll event handlers are debounced/throttled
- Use `requestAnimationFrame` for scroll-triggered updates

---

<a id="p19"></a>
## P19 — Demo Gallery Slow + Needs Sorting by Engine

**Severity**: MEDIUM
**Category**: UX + Performance
**Screenshots**: Image 5

### Observed Behavior

- Demo gallery loads slowly
- Demos are listed in a flat grid with no categorization
- No way to filter/sort by engine type
- Scrolling within the gallery is sluggish

### Root Cause

```typescript
// gui/src/components/panels/DemoGalleryPanel.tsx
// All demos loaded at once with setDemos(demosList) — no chunking/pagination
// CSS grid: repeat(auto-fill, minmax(320px, 1fr)) — no virtualization
```

No `IntersectionObserver` for lazy loading. No category/engine grouping.

### Proposed Fix

1. **Categorize demos by engine**: Add engine tags to demo metadata, then group the gallery:
   - "Quantum ESPRESSO" section → si-bands, si-scf, etc.
   - "VASP" section → vasp demos
   - "ORCA" section → molecular demos

2. **Search/filter**: Add a search box + engine filter chips at the top

3. **Lazy loading**: Use `IntersectionObserver` to only render demo cards in the viewport

4. **Pagination**: If >20 demos, show first 20 with "Load More" button

---

<a id="p20"></a>
## P20 — xTB Raw Output Error (Exists but Not Displayed)

**Severity**: HIGH
**Category**: Backend bug
**Screenshots**: Image 25 (not shown clearly, described in report)

### Observed Behavior

xTB step shows raw output error even though the output file (`xtb.out`) exists in the step's raw directory.

### Root Cause

Path normalization strips directory prefixes:

```python
# src/qmatsuite/api/service.py:798
artifact_path_normalized = artifact_path_obj.name  # ← STRIPS DIRECTORIES
file_path = raw_dir_resolved / artifact_path_normalized
```

`Path("subdir/xtb.out").name` returns only `"xtb.out"`, losing any subdirectory. If the xTB handler writes output to a subdirectory (or if the artifact listing includes a relative path), the read fails.

See also P21 for the systemic version of this bug.

### Proposed Fix

Use the full relative path instead of just the filename:

```python
# Instead of:
artifact_path_normalized = artifact_path_obj.name
# Use:
artifact_path_normalized = str(artifact_path_obj)  # Keep relative path
file_path = raw_dir_resolved / artifact_path_normalized

# Security check still applies:
file_path_resolved = file_path.resolve()
if not file_path_resolved.is_relative_to(raw_dir_resolved):
    raise ValidationError(...)
```

The existing path traversal check (`.is_relative_to()`) already prevents directory escapes, so `.name` normalization is redundant and harmful.

---

<a id="p21"></a>
## P21 — Raw Output Path Normalization Bug (All Engines)

**Severity**: HIGH
**Category**: Backend architecture
**Screenshots**: N/A (systemic)

### Description

The same `.name` normalization bug in P20 affects ALL engines, not just xTB. Any engine that:
- Writes output to a subdirectory of `raw/`
- Lists artifacts with relative paths including directory components

...will fail to have their raw output displayed.

### Root Cause

Mismatch between artifact listing and reading:

```python
# Listing (service.py:712) — stores relative path
"path_relative_to_raw": file_name  # Could be "subdir/output.txt"

# Reading (service.py:798) — strips to just filename
artifact_path_normalized = artifact_path_obj.name  # "output.txt" — WRONG
```

### Engines at Risk

- **xTB**: Simple flat output (may work if no subdirs)
- **QMCPACK**: Multiple `.dat` files, potentially in subdirectories
- **Wannier90**: Seed-based artifacts in multiple directories
- **LAMMPS**: Log files, dump files, potential nested output
- Any engine with multi-job output

### Proposed Fix

Same as P20 — remove the `.name` stripping and use the full relative path, relying on the existing `.is_relative_to()` security check.

---

<a id="p22"></a>
## P22 — Calculation Panel Half-Shown / Clipping

**Severity**: LOW
**Category**: CSS / Layout
**Screenshots**: Image 6

### Observed Behavior

In the calculation list (left panel), the second calculation card ("ti-scf") is partially visible — cut off at the bottom with no visible scrollbar cue that more content exists below.

### Root Cause

The calculation list container likely has `overflow: hidden` or a fixed height that clips content without showing a scrollbar affordance. No scroll shadow or "more items below" indicator.

### Proposed Fix

1. Ensure `overflow-y: auto` on the calculation list container
2. Add a scroll shadow at the bottom when more items exist below the fold:
   ```css
   .calc-list--has-overflow::after {
     content: '';
     position: sticky;
     bottom: 0;
     height: 20px;
     background: linear-gradient(transparent, rgba(0,0,0,0.15));
     pointer-events: none;
   }
   ```
3. Consider adding a total count badge: "2 calculations" at the top

---

<a id="p23"></a>
## P23 — Sensitive Path Leak in Settings UI

**Severity**: MEDIUM
**Category**: Security / Privacy
**Screenshots**: Image 24

### Observed Behavior

The Settings > Engine Info section for QE shows:
```
QE HOME    ~/Library/Application Support/QMatSuite/engines/qe/bundled-7.5
```

This displays a real username (`mac18`) in the UI. While this is the local machine and not committed to git, it's poor practice:
1. Screenshots shared in bug reports (like this one) leak the username
2. CI/automation contexts may expose these paths

### Root Cause

The QE HOME path is read from the filesystem and displayed directly without sanitization.

### Proposed Fix

1. **In the UI**: Replace the home directory prefix with `~`:
   ```typescript
   const displayPath = rawPath.replace(/^(\/Users\/[^/]+|\/home\/[^/]+|C:\\Users\\[^\\]+)/, '~');
   ```

2. **Alternative**: Show relative-to-app-data path:
   ```
   QE HOME    <AppData>/engines/qe/bundled-7.5
   ```

---

<a id="p24"></a>
## P24 — Wannier90 3D Fixtures Error in Volume Viewer

**Severity**: LOW (DEV-only feature)
**Category**: Development artifact
**Screenshots**: Image 17 (Volume Viewer panel)

### Observed Behavior

Clicking "Volume (DEV)" shows:
```
Error: Wannier90 3D fixtures directory not found. Attempted paths: repo_derived:
/Applications/QMatSuite.app/.../tests/data/wannier_3d_test dev_fallback:
~/QMatSuite/tests/data/wannier_3d_test Please set QMATSUITE_WANNIER_3D_FIXTURES
environment variable or ensure fixtures exist.
```

### Root Cause

The Volume Viewer Sandbox is a development tool that expects test fixtures at a hardcoded path. In a production .app bundle, the test data doesn't exist.

### Proposed Fix

This is covered by P5 — remove the "Volume (DEV)" sidebar item from production. The Volume Viewer should only be accessible in development mode.

If the Volume Viewer is intended for production in the future, it needs proper fixture bundling or a user-facing file picker instead of hardcoded test paths.

---

## Additional Observations from Screenshots

### O1 — Status Bar Shows "Unknown" for Job Status
**Screenshots**: Images 7, 8 (bottom-right shows "Unknown")

The status bar shows "Unknown" for the rightmost indicator. Should either show a meaningful status or be hidden when no info is available.

### O2 — Daemon Log RPC Timing Could Be Highlighted
**Screenshots**: Images 20 (daemon logs)

Many RPC calls show timing > 100ms. The daemon logs could benefit from color-coded timing:
- Green: < 50ms
- Yellow: 50-200ms
- Red: > 200ms

### O3 — "Unexpected error" Banner Lacks Detail
**Screenshots**: Image 9

The "Unexpected error" banner in the calculation panel has no description or detail. Should include the error message or at least a "Show Details" link.

### O4 — Workflow Detection Shows "missing: scf"
**Screenshots**: Image 10

The workflow detection bar shows `"SCF (0/1)  missing: scf"` which is confusing. Should say something like "1 step pending: SCF" or show a clearer progress indicator.

---

<a id="p25"></a>
## P25 — macOS Music Permission Dialog on Settings Page Load

**Severity**: HIGH
**Category**: macOS permissions / Build
**Screenshots**: New Image 1 (Apple Music permission dialog)

### Observed Behavior

On a lite install (no bundled QE), navigating to the Settings page triggers a macOS system dialog:
> "QMatSuite" would like to access Apple Music, your music and video activity, and your media library.

The daemon log shows concurrent slow operations:
- `structure_list_providers` took 6326.7ms
- QE resolver: `source=provided, No internal QE found under .qmatsuite/engines/qe/**/bin`

### Root Cause (Multi-Factor)

**Factor 1 — Electron plist contains overly broad permission descriptions**:

The production `Info.plist` (at `gui/release/mac-arm64/QMatSuite.app/Contents/Info.plist`) includes permission strings that are default Electron boilerplate, NOT needed by QMatSuite:

```xml
<key>NSAudioCaptureUsageDescription</key><string>This app needs access to audio capture</string>
<key>NSBluetoothAlwaysUsageDescription</key><string>This app needs access to Bluetooth</string>
<key>NSBluetoothPeripheralUsageDescription</key><string>This app needs access to Bluetooth</string>
<key>NSCameraUsageDescription</key><string>This app needs access to the camera</string>
<key>NSMicrophoneUsageDescription</key><string>This app needs access to the microphone</string>
```

These declare intent to use audio/camera/bluetooth. When combined with broad filesystem access, macOS Gatekeeper may conservatively show the Music/Media permission dialog.

**Factor 2 — QE engine resolver performs `rglob("bin")` on engines directory**:

```python
# src/qmatsuite/drivers/qe/engine/qe_resolver.py:119
for engine_dir in engines_base.rglob("bin"):
```

While this scans `~/.qmatsuite/engines/qe/` (or `~/Library/Application Support/QMatSuite/engines/qe/`), the `rglob` on a lite install with an empty engines directory is fast. But the path resolution via `home_qe_engines_dir()` calls `_ensure_dir()` which creates the directory, potentially triggering TCC (Transparency, Consent, and Control) checks.

**Factor 3 — `structure_list_providers` fetches OPTIMADE registry on page load**:

```python
# src/qmatsuite/io/providers/optimade.py:311-339
# get_providers_with_settings() → fetch_optimade_registry()
```

This makes a network request to `https://providers.optimade.org/v1/links` which takes 6+ seconds. The combination of network access + filesystem creation during Settings page mount may trigger the permission prompt.

**Factor 4 — No entitlements file**:

There are no `.entitlements` files in the project. The app is signed without explicit entitlements, relying on Electron's defaults. Without a proper hardened runtime entitlements file that explicitly declares what the app needs (and excludes what it doesn't), macOS may show overly broad permission requests.

### Proposed Fix

**1. Remove unused permission declarations from Info.plist** (via electron-builder config):

```json5
// gui/electron-builder.json5, mac section
"mac": {
  // ...
  "extendInfo": {
    // Remove all unused permission descriptions
    // Only keep what's actually needed (nothing for QMatSuite)
  }
}
```

Or create a custom `Info.plist` merge that removes `NSAudioCaptureUsageDescription`, `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`, `NSBluetoothAlwaysUsageDescription`, `NSBluetoothPeripheralUsageDescription`.

**2. Create proper entitlements file**:

```xml
<!-- gui/entitlements.mac.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key><true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.allow-dyld-environment-variables</key><true/>
  <key>com.apple.security.network.client</key><true/>
  <key>com.apple.security.files.user-selected.read-write</key><true/>
</dict>
</plist>
```

Reference in electron-builder:
```json5
"mac": {
  "entitlements": "entitlements.mac.plist",
  "entitlementsInherit": "entitlements.mac.plist"
}
```

**3. Defer non-critical operations on Settings load**:

- Don't fetch OPTIMADE registry until user opens Online Structures settings
- Don't run QE engine discovery on page mount — only when user clicks "Re-detect" or the QE section is expanded

---

<a id="p26"></a>
## P26 — SSSP Library Install: No Progress Bar

**Severity**: MEDIUM
**Category**: UX
**Screenshots**: New Image 2

### Observed Behavior

Clicking "Install..." for SSSP shows no download progress. The entire 14+ second download is a silent wait with only a static spinner. There's no indication of download size, speed, or which stage the installation is in (downloading, extracting, verifying, installing).

The daemon log confirms: `install_library` took 14197.8ms — the entire operation is blocking.

### Root Cause

**Backend**: The `install_library` RPC handler (`server.py:1033-1067`) makes a synchronous blocking call to the pipeline:

```python
# src/qmatsuite/daemon/server.py:1033-1067
def _handle_install_library(self, payload):
    result = QMSService.Pseudo.install_library(library_id, variants, source, ...)
    return {"ok": True, "data": result}  # Returns ALL messages at once
```

No streaming, no progress callbacks. Compare with engine installation which uses `progress_cb`:
```python
# src/qmatsuite/daemon/server.py:1545-1570 (engine install)
# Uses job manager with progress_cb for real-time feedback
```

**Download layer**: Uses blocking `shutil.copyfileobj()`:
```python
# src/qmatsuite/core/pseudo_config.py:388-391
with urllib.request.urlopen(req) as resp:
    shutil.copyfileobj(resp, f)  # No chunk callback, no progress
```

**Frontend**: Tries to infer progress from messages AFTER the call returns:
```typescript
// gui/src/hooks/useLibraryManager.ts:212-219
// Stage inference only runs after the blocking call completes
if (allMessages.includes('extract')) setInstallStage('extracting');
```

This means stages are never shown in real-time — only the final state is visible.

### Proposed Fix

**1. Chunked download with progress callback** (backend):

```python
def _download_with_progress(url, dest_path, progress_cb=None):
    with urllib.request.urlopen(url) as resp:
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        with open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(65536)  # 64KB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded / total * 100)
```

**2. WebSocket/SSE progress streaming** (daemon → frontend):

Emit progress events through the existing daemon log channel or a dedicated progress stream:
```python
# During pipeline execution:
self._emit_progress('install_library', {
    'stage': 'downloading',
    'percent': 45.2,
    'message': 'Downloading SSSP precision (23.4 / 52.1 MB)...'
})
```

**3. Frontend progress bar** (same pattern as engine install):

```typescript
// Show download progress bar similar to engine install
<div className="install-progress">
  <div className="install-progress__bar" style={{ width: `${percent}%` }} />
  <span>{stage}: {percent.toFixed(0)}%</span>
</div>
```

---

<a id="p27"></a>
## P27 — SSSP Library: "Installed (0)" After Successful Download

**Severity**: CRITICAL
**Category**: Backend serialization bug
**Screenshots**: New Image 3

### Observed Behavior

After SSSP installation completes successfully:
- Daemon log confirms: `install_library` took 14197.8ms (success)
- Finder confirms: `SSSP/efficiency/` and `SSSP/precision/` directories exist with UPF files
- BUT the Settings UI shows: "Installed (0)" tab selected, "No installed libraries found."
- The status never updates even after refreshing

### Root Cause

**PRIMARY: Missing `to_dict()` serialization in RPC handler**

```python
# src/qmatsuite/daemon/server.py:1021-1026
def _handle_get_library_status(self, payload):
    status = QMSService.Pseudo.get_library_status(library_id)
    return {
        "ok": True,
        "data": status,  # ← BUG: Returns LibraryStatus DATACLASS, not dict!
    }
```

`status` is a `LibraryStatus` dataclass (defined at `core/library_manager.py:52`). When this gets wrapped in `RPCResponse` and serialized via `json.dumps()` at `server.py:87`, it throws:

```
TypeError: Object of type LibraryStatus is not JSON serializable
```

There is NO custom JSON encoder (`json.dumps()` has no `default=` parameter). The `to_json()` method at line 87:
```python
return json.dumps(result)  # result["data"] = LibraryStatus object → CRASH
```

Compare with other handlers that correctly call `.to_dict()`:
```python
# server.py:1804 — structure search
return result_dto.to_dict()  # ✓ Correct

# server.py:1656 — list structures
structures = [dto.to_dict() for dto in structure_dtos]  # ✓ Correct
```

**SECONDARY: Frontend doesn't detect the serialization failure**

The frontend's `loadLibraryStatus` (line 113 in `useLibraryManager.ts`) catches the error silently:
```typescript
} catch (e) {
    console.error(`Failed to load library status for ${libraryId}:`, e);
    // Status remains stale — "Installed (0)" from initial load
}
```

No retry, no error display to user.

### Evidence

The `LibraryStatus` dataclass has a `.to_dict()` method:
```python
# core/library_manager.py:60-67
def to_dict(self) -> Dict[str, Any]:
    return {
        "library_id": self.library_id,
        "name": self.name,
        "installed_variants": self.installed_variants,
        "variant_statuses": [v.to_dict() for v in self.variant_statuses],
        "status": self.status,
    }
```

But it's never called in the RPC handler.

### Impact

This bug cascades to:
- **P11 (SSSP library not found for pseudo resolution)**: If the library can't be recognized as installed via the status API, pseudo scanning may also skip it
- **P10 (pseudo not updated after structure change)**: Even if structure changes correctly, the pseudo options from SSSP are invisible
- All users who install SSSP will see "Installed (0)" and believe the installation failed

### Proposed Fix

**Immediate fix** — add `.to_dict()` call:

```python
# src/qmatsuite/daemon/server.py:1021-1026
def _handle_get_library_status(self, payload):
    status = QMSService.Pseudo.get_library_status(library_id)
    return {
        "ok": True,
        "data": status.to_dict() if status else {},  # ← FIX
    }
```

**Defensive fix** — add a JSON-safe serialization helper to the daemon:

```python
def _safe_serialize(obj):
    """Convert dataclass/DTO objects to dicts for JSON serialization."""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if is_dataclass(obj):
        return asdict(obj)
    return obj
```

And apply it at the `RPCResponse.to_json()` level or as a `json.dumps(default=...)` handler.

**Audit**: Search all `_handle_*` methods for other instances where dataclasses are returned without `.to_dict()`.

---

# Windows System Tests (2026-02-26)

**Test environment**: Clean Windows x64 system (MSI-PC), QMatSuite v1.2.1 NSIS installer.

<a id="p28"></a>
## P28 — NSIS Installer Slow and Uninformative

**Severity**: HIGH
**Category**: Installer / UX
**Platform**: Windows-only
**Originally observed**: Windows

### Observed Behavior

Installation takes several minutes with two progress bar phases and no information about what's happening:
- **Phase 1 (SLOW)**: Green progress bar moves slowly for minutes — no user-visible explanation
- **Phase 2 (QUICKER)**: Second pass moves faster — still no explanation
- The NSIS detail panel only shows generic `DetailPrint` messages not visible in the main installer UI

### Root Cause

The `customInstall` NSIS macro in `gui/installer/conda-unpack.nsh` runs three sequential operations:

1. **conda-unpack (Phase 1, ~minutes)**: `python.exe conda-unpack` patches hardcoded CI paths across ~20,379 files in the 526 MB Python runtime. This is I/O-intensive and slow, especially with Windows antivirus scanning each file.

```nsh
# gui/installer/conda-unpack.nsh:2-3
DetailPrint "Initializing Python runtime..."
nsExec::ExecToLog '"$INSTDIR\resources\runtime\python.exe" "$INSTDIR\resources\runtime\Scripts\conda-unpack"'
```

2. **Engine staging (Phase 2a)**: `xcopy` copies bundled QE from `resources/engines/` to `%LOCALAPPDATA%\QMatSuite\engines\` (lines 20-28)
3. **SSSP staging (Phase 2b)**: `xcopy` copies bundled pseudo library to `%LOCALAPPDATA%\QMatSuite\libraries\` (lines 35-43)

The `DetailPrint` messages ("Initializing Python runtime...", "Staging bundled QE engine to AppData...") are only visible in the NSIS details panel, which users rarely expand. The main progress bar is driven by NSIS file-counting, not by actual operation progress.

### Proposed Fix

1. **Add a custom NSIS page** before `customInstall` runs, showing a message like "Setting up Python environment — this takes a few minutes on first install".
2. **Consider** moving conda-unpack to first-launch (Electron main process already has a fallback for this at `gui/electron/main.ts:429-486`), so the NSIS installer finishes quickly and the app shows a proper setup wizard on first run.
3. **For Phase 2**: These xcopy operations are fast (seconds); the real bottleneck is Phase 1. A "Setting up..." splash at minimum would set user expectations.

---

<a id="p29"></a>
## P29 — First Startup: matplotlib Font Cache Rebuild Blocks 30+ Seconds

**Severity**: HIGH
**Category**: Performance / Startup
**Platform**: Windows-specific on first run (also affects Mac/Linux first run but much faster due to fewer system fonts)
**Originally observed**: Windows

### Observed Behavior

After all 15 engine drivers are registered, there's a very long pause before the log shows:
```
[qms-daemon] [INFO] [matplotlib.font_manager] generated new fontManager
```
This blocks the daemon event loop for 30+ seconds on a typical Windows install.

### Root Cause

matplotlib's `font_manager` module scans the entire system font directory on first import and builds `fontlist-v330.json`. On Windows:
- Typical systems have 200-500 system fonts (vs ~100 on macOS)
- Font enumeration uses Windows GDI APIs which are slower than macOS CoreText
- The cache file may be in a temp directory that gets cleared, forcing rebuilds

matplotlib is correctly lazy-loaded in analysis modules:
- `src/qmatsuite/analysis/plotting.py:65-71` (lazy via `_get_pyplot()`)
- `src/qmatsuite/analysis/structure_viz.py:74-79` (lazy via `_get_matplotlib_modules()`)

However, some import chain (likely through pymatgen or another dependency) triggers matplotlib import during daemon startup. The font cache rebuild then blocks the daemon's single-threaded event loop.

This is a well-documented matplotlib issue (GitHub issues #13071, #30748).

### Proposed Fix

1. **Set `MPLCONFIGDIR`** at daemon startup to a persistent directory (e.g., `<AppData>/QMatSuite/cache/matplotlib/`) so the font cache persists across sessions:

```python
# In daemon startup, before any matplotlib import
import os
os.environ.setdefault("MPLCONFIGDIR", str(get_app_data_dir() / "cache" / "matplotlib"))
```

2. **Move matplotlib import to a background thread**: If font cache doesn't exist, spawn `threading.Thread(target=lambda: __import__('matplotlib'))` during daemon startup so the font enumeration doesn't block RPC handlers.

3. **Trace the eager import chain**: Use `python -v` or `importlib` tracing to find which module triggers the early matplotlib import and break the chain.

---

<a id="p30"></a>
## P30 — First Startup: OPTIMADE Provider Fetch Blocks 140 Seconds

**Severity**: CRITICAL
**Category**: Performance / Startup
**Platform**: Both (observed on Windows; network-dependent on all platforms)
**Originally observed**: Windows

### Observed Behavior

Daemon log shows:
```
[RPC] structure_list_providers (req_id=req-...-29) took 139933.2ms
```
This 140-second blocking call renders the app unusable during first startup. The Settings page shows "Loading environment info..." with a spinner for over 2 minutes.

### Root Cause

The `_handle_structure_list_providers` handler at `server.py:1865` calls `QMSService.OnlineSearch.list_providers()` which calls `fetch_optimade_registry()` in `src/qmatsuite/io/providers/optimade.py:255-257`:

```python
response = requests.get(OPTIMADE_REGISTRY_URL, timeout=10)
```

On first startup, no cache exists (`registry_cache.json`), so the daemon makes an HTTP request to `https://providers.optimade.org/v1/links`. If the OPTIMADE server is slow or the network is unreliable, the 10-second timeout may be hit multiple times (retries or DNS resolution delays). The 140s actual time suggests either:
- Multiple retry attempts within the provider framework
- DNS resolution timeout before the HTTP timeout kicks in
- The request succeeds but the downstream OPTIMADE provider queries (6 providers) each take ~20-30s

The cache has a 24-hour TTL (`REGISTRY_CACHE_TTL_SECONDS` at line 32), so subsequent launches are fast.

**The real problem**: This RPC is called eagerly on Settings page load, blocking the entire UI. It should NOT be required for startup.

### Proposed Fix

1. **Never block startup on OPTIMADE**: The provider fetch should be fully asynchronous and not block the Settings page. Move it to a background task that runs after the UI is responsive.

2. **Ship a bundled fallback provider list**: Include a static copy of `CURATED_DEFAULT_PROVIDERS` so the first render shows cached providers immediately, then refresh in background:

```python
def list_providers(refresh_registry=False):
    # Return curated defaults immediately
    # Schedule background refresh if cache is stale
    ...
```

3. **Add a hard timeout ceiling**: Even with retry, cap the total provider fetch at 15 seconds. If exceeded, return curated defaults.

4. **Separate the Settings page load from provider fetch**: The Settings page should NOT call `structure_list_providers` — that RPC belongs to the Structures/Online Search panel only.

---

<a id="p31"></a>
## P31 — First Startup: engine.list Times Out at 60s

**Severity**: HIGH
**Category**: Performance / Startup
**Platform**: Windows-specific on first run (subsequent calls use cached engines.json)
**Originally observed**: Windows

### Observed Behavior

```
Request req-1772079034153-65 timed out after 60000ms
```
The Engine Management section shows "No engines discovered yet." After manually clicking Refresh, engines load in ~880ms.

### Root Cause

The `_handle_engine_list` handler at `server.py:1410` calls `list_engines()` from `src/qmatsuite/api/engines.py:75` which calls `EngineRegistry().discover(persist=False)` at line 78. Discovery iterates all 15 engines and for each:

1. `_scan_bundled()` — filesystem scan (line 339)
2. `_scan_micromamba()` — filesystem scan (line 382)
3. `_scan_system_path()` — PATH scan (line 400+)
4. `_verify_installation()` — runs version probes via subprocess (line 531-568)

On Windows first run:
- Version probes spawn 15+ subprocesses sequentially (each `subprocess.run()` is slow on Windows due to process creation overhead)
- PATH scanning iterates many directories
- Antivirus may delay subprocess execution
- No cached `engines.json` exists yet

After first discovery and persist, `engines.json` is written and subsequent calls skip the expensive probes.

### Proposed Fix

1. **Increase the frontend RPC timeout for `engine.list`** from 60s to 120s for first-time discovery, or add a retry mechanism.

2. **Parallelize version probes**: Use `concurrent.futures.ThreadPoolExecutor` to run version probes for all 15 engines simultaneously instead of sequentially:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(self._verify_installation, family, inst): family
               for family in ENGINE_META for inst in discovered[family]}
    for future in as_completed(futures):
        ...
```

3. **Lazy discovery**: On startup, load `engines.json` as-is (fast). Only trigger full `discover()` when user navigates to Settings or when explicitly refreshing. The current code calls `discover(persist=False)` on every `engine.list` call, which is unnecessary after first run.

4. **Progressive loading**: Return partial results immediately (from engines.json) and run discovery in background, sending updates via event stream.

---

<a id="p32"></a>
## P32 — Demo Gallery Missing 17 Demos Due to UTF-8 Encoding Bug

**Severity**: CRITICAL
**Category**: Backend / Encoding
**Platform**: Windows-only (macOS defaults to UTF-8)
**Originally observed**: Windows

### Observed Behavior

Demo Gallery shows only 35 of 52 available demos on Windows. Missing demos include "Silicon band structure" (`si_bands_demo.yml`) and "Silicon density of states" (`si_dos_demo.yml`), despite the files existing on disk at `C:\...\resources\runtime\Lib\site-packages\qmatsuite\resources\demo_projects\si_bands_demo.yml`. Even restarting the app does not fix it.

### Root Cause

**The `open()` call at `src/qmatsuite/api/service.py:8665` does not specify `encoding="utf-8"`:**

```python
# service.py:8665
with open(snapshot_path, "r") as f:  # ← BUG: no encoding= on Windows
    data = yaml.safe_load(f)
```

On Windows, Python's `open()` defaults to the system locale encoding (typically `cp1252` or `mbcs`), NOT UTF-8. Exactly **17 demo YAML files** contain non-ASCII UTF-8 characters — Greek `Γ` (U+0393) and arrow `→` (U+2192) in metadata fields like:

```yaml
# si_bands_demo.yml:210
subtitle: PBE band structure along L-Γ-X-U-Γ for diamond Si
# si_bands_demo.yml:231
step_summary: SCF → NSCF → Bands → BandsPW
```

When `open()` with cp1252 encoding encounters these multi-byte UTF-8 sequences, it throws `UnicodeDecodeError`. The `except Exception: continue` block at line 8707-8709 silently swallows the error, dropping the demo from the list.

**All 17 files with non-ASCII characters (= exactly the 17 missing demos)**:
| File | Non-ASCII chars |
|------|----------------|
| `abinit_si_bands.yml` | Γ, → |
| `gpaw_si_bands.yml` | Γ |
| `qe_al_dos.yml` | → |
| `qe_copper_wannier.yml` | Γ, → |
| `qe_diamond_wannier.yml` | Γ, → |
| `qe_graphene_bands.yml` | Γ, → |
| `qe_he_qmcpack_vmc.yml` | Γ, → |
| `qe_lih_qmcpack_vmc.yml` | Γ, → |
| `qe_si_bands_alt.yml` | Γ, → |
| `qe_si_dos_alt.yml` | → |
| `qe_si_yambo_bse.yml` | Γ, → |
| `qe_si_yambo_gw.yml` | Γ, → |
| `si_bands_demo.yml` | Γ, → |
| `si_dos_demo.yml` | → |
| `siesta_si_bands.yml` | Γ |
| `vasp_si_bands.yml` | Γ |
| `vasp_si_dos.yml` | → |

### Proposed Fix

**Immediate** (1-line fix):

```python
# service.py:8665 — add encoding="utf-8"
with open(snapshot_path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)
```

**Systematic audit**: Search the entire codebase for all `open(..., "r")` calls without `encoding=` parameter. On Windows, every text file read should specify `encoding="utf-8"` explicitly. Key hotspots:
- All YAML reading (`yaml.safe_load`)
- All JSON reading
- All config/settings file reading

Consider adding a project-wide lint rule or using `io.open()` wrapper that defaults to UTF-8.

---

<a id="p33"></a>
## P33 — Demo "0 Si SCF" Step Detail Fails to Load

**Severity**: HIGH
**Category**: Demo data integrity
**Platform**: Both (observed on Mac and Windows)
**Originally observed**: Mac (also confirmed on Windows)

### Observed Behavior

The demo "0 Si SCF" appears in the gallery (with an unusual `0` prefix in the title) but when clicking on the step, the Step Detail panel shows:
```
Error loading step: Calculation not found - selector: 'si-scf' - in project: <path>/0-si-scf
```

### Root Cause

The demo file `src/qmatsuite/resources/demo_projects/qe_si_scf.yml` has a **malformed step path** at line 85:

```yaml
# qe_si_scf.yml (line 85, approximate)
path: si.scf.step.yaml
```

The canonical step path format is `calculations/<calc-slug>/steps/<step-slug>.step.yaml`. When the snapshot materializer processes this demo, it creates the calculation directory structure correctly but the step metadata retains the old flat path `si.scf.step.yaml`. The resolution module then fails to map this path back to the calculation, resulting in "Calculation not found".

**Two additional demos have the same issue**:
- `qe_fe_scf.yml` — step path: `fe.scf_noncollin.step.yaml`
- `qe_si_vc_relax.yml` — step path: `si.vc_relax.step.yaml`

**The title issue**: The demo's `meta.title` field is `0 Si Scf` (line 122) and `meta.name` is `00_Si_scf` (line 5). The `0` prefix is intentional (legacy numbering) but confusing in the gallery.

### Proposed Fix

1. **Regenerate** the 3 malformed demo YAML files with correct canonical step paths.
2. **Add a validation gate**: In `list_demo_projects()`, add a quick sanity check that step paths match the canonical format `calculations/*/steps/*.step.yaml`.
3. **Fix the title**: Change `title: 0 Si Scf` to `title: Silicon diamond SCF` (matching the existing `qe_si_scf.yml`'s `description` field) or `title: Silicon SCF (LDA)`.

---

<a id="p34"></a>
## P34 — Engine Install Cannot Be Cancelled

**Severity**: MEDIUM
**Category**: UX / Frontend
**Platform**: Both (design flaw, not platform-specific)
**Originally observed**: Windows

### Observed Behavior

When clicking "Install" for a QE engine download from GitHub, the button changes to "Installing..." and becomes disabled. There is no cancel button. The user must wait for the download + extraction to complete or force-quit the app.

The download does show progress (bytes downloaded / total), but there's no way to abort.

### Root Cause

**Frontend**: `gui/src/components/panels/SettingsPanel.tsx:856-865` renders the Install button as disabled during install with no cancel option:

```tsx
// SettingsPanel.tsx:856-860
<button
  className="settings-btn"
  onClick={() => void handleInstall(engine)}
  disabled={!!pending}  // ← Disabled, no cancel alternative
>
  {pending?.action === 'install' ? 'Installing...' : 'Install'}
</button>
```

The progress bar UI (lines 788-812) shows download progress but no cancel action.

**Backend**: The download function `_download_binary()` in `src/qmatsuite/core/engines/engine_installer.py:57-78` uses blocking `urllib.request.urlopen()` with no cancellation mechanism:

```python
# engine_installer.py:57-78
with urllib.request.urlopen(url, context=_ssl_context(), timeout=180) as response:
    while True:
        chunk = response.read(chunk_size)  # ← No cancel check
        ...
```

The `cancel_job` RPC exists (`server.py:4312-4322`) and `JobManager.cancel_job()` exists (`daemon/jobs.py:633-670`), but:
- It can only cancel **PENDING** jobs (before execution starts)
- Once RUNNING, `ThreadPoolExecutor` cannot kill the thread
- SettingsPanel never calls `cancel_job` anyway

### Proposed Fix

1. **Add cancel button to UI**: When `pending?.action === 'install'`, render a "Cancel" button that calls `cancel_job(jobId)`.

2. **Add cancellation token to download loop**: Pass a threading.Event as a cancel flag:

```python
def _download_binary(url, output_path, on_progress=None, cancel_event=None):
    ...
    while True:
        if cancel_event and cancel_event.is_set():
            raise CancelledError("Download cancelled by user")
        chunk = response.read(chunk_size)
        ...
```

3. **Wire cancel into JobManager**: When `cancel_job()` is called on a RUNNING job, set the cancel event so the download loop checks it on the next chunk iteration.

---

<a id="p35"></a>
## P35 — QE Resolver / Engine Registry Dual-System Disconnect

**Severity**: CRITICAL
**Category**: Architecture / Engine detection
**Platform**: Windows primary (path mismatch), design flaw affects both platforms
**Originally observed**: Windows

### Observed Behavior

Multiple cascading failures on Windows:

1. **Bundled QE not detected on first startup** despite existing at `AppData\Local\QMatSuite\engines\qe\bundled-7.5\`. Log shows: `No internal QE found under .qmatsuite/engines/qe/**/bin`
2. **After GitHub QE download**, `engines.json` writes correctly with `github-7.5-mpi` active
3. **Cannot switch back to bundled QE** — Engine Manager dropdown shows `bundled-7.5 (v7.5)` but selecting it shows `installation_id not found`
4. **Lower "Quantum ESPRESSO" panel** (in Settings) still shows "QE Not Found" even when Engine Manager shows QE installed
5. **"QE is not installed" banner** blocks running calculations even though `engines.json` has a verified QE entry

### Root Cause

**Two competing engine detection systems exist with incompatible search paths:**

| Aspect | QE Resolver (OLD) | Engine Registry (NEW) |
|--------|-------------------|-----------------------|
| **File** | `src/qmatsuite/drivers/qe/engine/qe_resolver.py` | `src/qmatsuite/core/engines/engine_registry.py` |
| **Search root** | `.qmatsuite/engines/qe/` (home-relative) | `<AppData>/engines/<engine>/` |
| **Activation** | `settings.qe.bin_dir` | `engines.json` active field |
| **Windows path** | `~/.qmatsuite/engines/qe/` | `LOCALAPPDATA/QMatSuite/engines/qe/` |
| **Used by** | Preflight checks, `detect_qe` RPC | Settings Engine Manager, `engine.list` RPC |

**The disconnect chain**:

1. **NSIS installer** stages bundled QE to `%LOCALAPPDATA%\QMatSuite\engines\qe\bundled-7.5\` (via xcopy in `conda-unpack.nsh:22`).

2. **QE Resolver** (`qe_resolver.py:193`) tries `_resolve_qe_bin_dir_from_registry()` first, which calls `EngineRegistry().load()` then `registry.get_active("qe")`. On first startup, `engines.json` doesn't exist yet, so this returns `None`.

3. **QE Resolver falls through** to `find_internal_qe_bin_dir()` at line 222, which searches `home_qe_engines_dir()` — this resolves to `~/.qmatsuite/engines/qe/` (via `core/paths.py`). On Windows Electron, this is **NOT** `%LOCALAPPDATA%\QMatSuite\engines\qe\` — it's a different path entirely.

4. **Result**: QE Resolver finds nothing, throws RuntimeError at line 236: `"No internal QE found under .qmatsuite/engines/qe/**/bin"`.

5. **Engine Registry** (`engine_registry.py:339-380`) correctly discovers bundled QE via `_scan_bundled()` because it uses `home_engines_dir()` which resolves to `LOCALAPPDATA/QMatSuite/engines/`. But this only runs when `engine.list` RPC is called, which times out on first startup (see P31).

6. **"installation_id not found"** error: After GitHub download, `engines.json` has `active: "github-7.5-mpi"`. When user selects `bundled-7.5` from dropdown, the daemon calls `engine.set_active("qe", "bundled-7.5")` at `server.py:1463`. The `set_active()` method checks if `bundled-7.5` exists in `engines["qe"]["installations"]`. If the last `discover()` call didn't persist (it uses `persist=False`), bundled-7.5 may not be in the stored registry, causing failure.

**Key code references**:
- `qe_resolver.py:30-36` — `home_qe_engines_dir()` returns a different path than engine registry
- `qe_resolver.py:41-61` — Registry lookup falls through on first startup
- `qe_resolver.py:232-234` — "No internal QE found" error message
- `engine_registry.py:339-380` — `_scan_bundled()` uses correct AppData path
- `server.py:1449-1469` — `engine.set_active` handler returns "installation_id not found"
- `server.py:1410-1435` — `engine.list` calls `discover(persist=False)` — results not persisted!

### Proposed Fix

**Phase 1 — Unify paths (critical)**:

The QE Resolver's `home_qe_engines_dir()` must resolve to the same directory as `home_engines_dir() / "qe"`. Currently, `home_qe_engines_dir` from `core/paths.py` returns a different path than the Engine Registry uses. Fix:

```python
# qe_resolver.py — replace home_qe_engines_dir with engine registry path
def find_internal_qe_bin_dir() -> Optional[Path]:
    from qmatsuite.core.paths import home_engines_dir
    engines_base = home_engines_dir() / "qe"  # ← Use same path as engine registry
    ...
```

**Phase 2 — Persist discovery results**:

Change `engine.list` to call `discover(persist=True)` so that subsequent `set_active` calls find all discovered installations:

```python
# api/engines.py:78 — change persist=False to persist=True
data = registry.discover(persist=True)
```

**Phase 3 — Deprecate dual system**:

The QE Resolver's legacy `find_internal_qe_bin_dir()` scan should be fully replaced by the Engine Registry. The resolver should ONLY consult the registry:

```python
def resolve_qe_bin_dir(settings=None) -> Path:
    # 1. Check engine registry (unified)
    registry_bin_dir = _resolve_qe_bin_dir_from_registry()
    if registry_bin_dir:
        return registry_bin_dir

    # 2. Check settings.qe.bin_dir (user override)
    if settings and settings.qe.bin_dir:
        return validate_and_return(settings.qe.bin_dir)

    # 3. No QE found — raise error directing user to Engine Manager
    raise RuntimeError("No QE installation found. Use Settings → Engine Manager to install or configure QE.")
```

---

## Summary Priority Matrix

| ID | Issue | Severity | Category | Platform | Effort |
|----|-------|----------|----------|----------|--------|
| P1 | Auto-update ZIP missing | CRITICAL | Build | Mac | Low |
| P6 | "titanium" → "TiTaNiUm" | CRITICAL | Backend | Both | Medium |
| P9 | Structure selector broken | CRITICAL | Integration | Both | Medium |
| P10 | Pseudo not updated on structure change | CRITICAL | Backend | Both | Medium |
| P11 | SSSP library not found | CRITICAL | Backend | Both | High |
| P27 | SSSP "Installed (0)" after download | CRITICAL | Backend serialization | Both | Trivial |
| P30 | OPTIMADE provider fetch blocks 140s | CRITICAL | Performance / Startup | Both | Medium |
| P32 | Demo gallery missing 17 demos (UTF-8) | CRITICAL | Backend / Encoding | Windows | Trivial |
| P35 | QE Resolver / Engine Registry disconnect | CRITICAL | Architecture | Windows primary | High |
| P2 | No "up to date" feedback | HIGH | UX | Mac | Low |
| P3 | Version hard-coded "v2.0.0" | HIGH | Bug | Both | Trivial |
| P5 | Volume (DEV) in production | HIGH | Build | Both | Trivial |
| P18 | Electron scrolling slow | HIGH | Performance | Both | High |
| P20 | xTB raw output error | HIGH | Backend | Both | Low |
| P21 | Raw output path bug (all engines) | HIGH | Backend | Both | Low |
| P25 | macOS Music permission dialog | HIGH | Build / macOS | Mac | Medium |
| P28 | NSIS installer slow/uninformative | HIGH | Installer / UX | Windows | Medium |
| P29 | matplotlib font cache blocks 30s+ | HIGH | Performance / Startup | Windows first-run | Low |
| P31 | engine.list times out at 60s | HIGH | Performance / Startup | Windows first-run | Medium |
| P33 | Demo "0 Si SCF" step detail fails | HIGH | Demo data integrity | Both | Low |
| P4 | Welcome text QE-centric | MEDIUM | UX | Both | Trivial |
| P8 | Online search slow (>8s) | MEDIUM | Performance | Both | Medium |
| P12 | Step dropdown labels | MEDIUM | UX | Both | Low |
| P13 | Digest too verbose | MEDIUM | UX | Both | Medium |
| P14 | No auto-select plot | MEDIUM | UX | Both | Low |
| P16 | Resources first-load bug | MEDIUM | Frontend | Both | Low |
| P17 | Settings layout chaotic | MEDIUM | UX | Both | High |
| P19 | Demo gallery slow/unsorted | MEDIUM | UX | Both | Medium |
| P23 | Sensitive path in UI | MEDIUM | Security | Both | Low |
| P26 | SSSP install no progress bar | MEDIUM | UX | Both | Medium |
| P34 | Engine install no cancel button | MEDIUM | UX / Frontend | Both | Medium |
| P7 | Search filter buttons style | LOW | UX | Both | Low |
| P15 | Reference checkbox | LOW | UX | Both | Low |
| P22 | Calc panel clipping | LOW | CSS | Both | Low |
| P24 | Wannier90 fixtures error | LOW | Dev artifact | Both | Trivial |

---

## Recommended Fix Order

### Phase 1 — Critical / Quick Wins (1-2 days)
1. **P27**: Add `.to_dict()` call in `_handle_get_library_status` (1-line fix, cascading unblock for P11)
2. **P32**: Add `encoding="utf-8"` to demo listing `open()` call (1-line fix, restores 17 missing demos on Windows)
3. **P3**: Fix hard-coded version → read from package.json
4. **P5**: Gate Volume (DEV) behind `import.meta.env.DEV`
5. **P4**: Replace QE-centric text with engine-agnostic
6. **P1**: Add ZIP target to macOS build (electron-builder.json5)
7. **P2**: Add "up to date" banner state
8. **P20/P21**: Fix `.name` path stripping in artifact reader
9. **P33**: Regenerate 3 malformed demo YAML files with correct step paths

### Phase 2 — Critical Functional + Architecture Bugs (3-5 days)
10. **P35**: Unify QE Resolver path with Engine Registry path (Windows engine detection)
11. **P6**: Fix `normalize_formula()` — element name detection + valid symbol validation
12. **P10**: Refresh species_map after structure change
13. **P11**: Fix SSSP library scanning pipeline (now unblocked by P27 fix)
14. **P9**: Fix structure list refresh after import/create
15. **P25**: Remove unused permission declarations from Info.plist + add entitlements

### Phase 3 — Windows First-Run Performance (3-5 days)
16. **P30**: Make OPTIMADE provider fetch async + ship bundled fallback list
17. **P29**: Set `MPLCONFIGDIR` to persistent path + move matplotlib import to background thread
18. **P31**: Parallelize engine version probes + lazy discovery with progressive loading
19. **P28**: Add informative splash/message to NSIS installer during conda-unpack

### Phase 4 — UX Improvements (1-2 weeks)
20. **P13**: Collapsible digest with summary line
21. **P14**: Auto-select plot tab
22. **P12**: Add gen-type labels to step dropdown
23. **P16**: Fix resources first-load race condition
24. **P17**: Redesign settings engine info layout
25. **P19**: Categorize demo gallery by engine
26. **P26**: Add progress bar to SSSP library download
27. **P34**: Add cancel button to engine install UI + cancellation token to download

### Phase 5 — Performance (1-2 weeks)
28. **P18**: Add virtual scrolling (react-window/react-virtuoso)
29. **P8**: Progressive search results + provider timeouts
