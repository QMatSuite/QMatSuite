# GUI History Panel & Resources Tab — Review and Roadmap

**Date:** 2026-02-11
**Scope:** Problem 1 (History/Provenance viewer), Problem 2 (Resources/Knowledge Center), CLI provenance

---

## Table of Contents

1. [Current Situation](#1-current-situation)
2. [Gap Analysis](#2-gap-analysis)
3. [Problem 1: History Panel — Provenance Viewer](#3-problem-1-history-panel--provenance-viewer)
4. [Problem 2: Resources Tab — Engine Knowledge Center](#4-problem-2-resources-tab--engine-knowledge-center)
5. [Problem 3: CLI `qv history`](#5-problem-3-cli-qv-history)
6. [UX Vision: What a New User Sees](#6-ux-vision-what-a-new-user-sees)
7. [Naming and Navigation](#7-naming-and-navigation)
8. [Implementation Phases](#8-implementation-phases)
9. [File Inventory](#9-file-inventory)

---

## 1. Current Situation

### 1.1 History Panel (GUI)

**Status: Functional but showing only partial provenance data.**

The HistoryPanel (`gui/src/components/panels/HistoryPanel.tsx`, 448 lines) is a notebook-style
timeline view. It renders:

- **Run cards** (run_finished): expandable, with status (✓/✗), duration, step digests, energy chips
- **Run started** events: compact inline markers
- **Edit events**: summary + doc_path
- **Pin events**: analysis kind label
- **Baseline events**: project init marker

Controls:
- Limit selector (All / Last 50 / Last 200)
- Refresh button
- Delete history button (with confirmation modal)

The backend flow:
```
HistoryPanel → RPC get_project_history → QVService.History.get_timeline()
    → provenance.query.query_runs() → SQLite .provenance/provenance.db
```

**What works:**
- Timeline fetching and rendering
- Run card expansion with step digests
- Delete with confirmation (removes `.provenance/`)
- Pinned analysis events

**What's missing or stale:**
- Delete modal text still says `.history` directory (line 419: `"delete the .history directory"`)
- No operation events shown (only runs + pins). The `operations` table in SQLite records every
  YAML write (step_add, preset_apply, structure_import, etc.) but `get_timeline()` only builds
  entries from `runs` — not from `operations`.
- No CAS/snapshot viewer (cannot inspect what was captured at a checkpoint)
- No tiered storage info (Tier-0/1/2/3 usage, sizes, counts)
- No per-run detail drill-down (snapshot contents, artifact list)
- No rollback/restore controls (even "view checkpoint" is missing)
- No operation-level timeline (preset applications, parameter edits, structure changes)

### 1.2 Resources Tab (GUI)

**Status: Fully functional but hardcoded to QE only.**

The EngineParameterBrowserPanel (`gui/src/components/panels/EngineParameterBrowserPanel.tsx`,
1032 lines) is a well-built parameter browser with:

- Category dropdown with sort options
- Global search with popover results
- Parameter table (Name, Type, Default, Description)
- Column resizing, sorting, row selection with full-text expansion

The backend routing (`api/utils.py` → `_get_engine_metadata_module()`) supports 8 engines:
QE, VASP, ORCA, LAMMPS, Gaussian, ABINIT, CP2K, QMCPACK.

**Three engines have metadata modules but are NOT wired in `_get_engine_metadata_module()`:**
Yambo, Wannier90, xTB.

**Four engines have no metadata JSON at all:**
GPAW, Psi4, PySCF (Python-script engines), Siesta.

**The critical wiring problem** is in `App.tsx` line 2467:
```tsx
return <EngineParameterBrowserPanel engineFamily="qe" />;
```
It's hardcoded to `"qe"`. No UI to switch engines. The sidebar tooltip also says
"Browse QE parameter metadata" (Sidebar.tsx line 267).

### 1.3 CLI

**Status: No `qv history` command exists.**

The CLI (`src/quantumvitas/cli/main.py`, ~4800 lines) has no history/provenance commands.
The only metadata-related command is `qv params <module>` which is QE-specific:

```
qv params pw --section SYSTEM    # lists QE pw module parameters
```

No equivalent for VASP, ORCA, etc.

### 1.4 Provenance API (Backend)

**Status: Complete and well-structured. Ready to be consumed by both GUI and CLI.**

The provenance system is fully implemented:

| Layer | Location | What it provides |
|-------|----------|-----------------|
| Core provenance | `src/quantumvitas/provenance/` (13 files, ~3200 LOC) | OperationContext, SQLite schema v3, CAS, recording, query, pins, snapshots, restore, policy, scanner |
| Service API | `src/quantumvitas/api/service.py` → `QVService.History` | `get_timeline()`, `get_run_revision()`, `list_runs()`, `pin_analysis()`, `delete()` |
| Daemon RPC | `src/quantumvitas/daemon/server.py` | 8 endpoints: `get_project_history`, `get_run_revision`, `list_project_runs`, `pin_analysis_to_history`, `can_pin_to_run`, `get_pin_data`, `get_latest_run_for_step`, `delete_project_history` |
| Query module | `src/quantumvitas/provenance/query.py` | `query_operations()`, `query_runs()`, `get_run_details()`, `get_latest_run_ulid()`, `build_timeline_entry()` |

Key: `query_operations()` exists in the provenance layer but is **not exposed** through
`QVService.History` or any RPC endpoint. This is the main missing link for showing operation
events (edits, preset applications, etc.) in the GUI timeline.

---

## 2. Gap Analysis

### 2.1 History Panel Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No operation events** in timeline | HIGH | `query_operations()` exists but isn't wired to GUI. Users can't see when they changed parameters, applied presets, imported structures, etc. |
| **No run detail view** | MEDIUM | Can expand run to see step digests, but no link to view the full snapshot (what YAML looked like at that moment) |
| **No tiered storage info** | LOW-MEDIUM | `cas_objects` table tracks tier/size but nothing displays it. Users should know how much provenance storage they're using |
| **No rollback controls** | LOW (viewer first) | `restore.py` and `opctx_for_restore()` exist. But UI has no "restore to this checkpoint" button. Per the request: viewer first, rollback later |
| **Stale `.history` reference** | LOW | Delete modal mentions `.history` but the actual directory is `.provenance/` |
| **No artifact browsing** | LOW | Can't see what files were captured at Tier-2/3 for a given run |
| **No filtering by calc** | LOW | `get_timeline()` accepts `calc_ulid` filter but GUI doesn't use it |

### 2.2 Resources Tab Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **Hardcoded to QE** | CRITICAL | `engineFamily="qe"` in App.tsx — all other engines inaccessible |
| **3 engines not wired** | MEDIUM | Yambo, W90, xTB metadata modules exist but not in `_get_engine_metadata_module()` |
| **4 engines have no metadata** | LOW | GPAW, Psi4, PySCF, Siesta — Python-script engines by nature have no input-file parameter dictionary |
| **Tab name "Resources" is confusing** | MEDIUM | "Resources" could mean structures, pseudopotentials, potentials, or files. For a parameter encyclopedia, "Reference" or "Knowledge" is clearer |
| **No cross-engine search** | LOW | Can search within one engine but not across all engines |
| **CSS class names say `qe-`** | LOW | `.qe-parameter-browser` class namespace reflects QE-only origin |

### 2.3 CLI Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No `qv history` command** | HIGH | Provenance query API is fully built but not CLI-accessible |
| **`qv params` is QE-only** | MEDIUM | Only QE parameters browsable from CLI |

---

## 3. Problem 1: History Panel — Provenance Viewer

### 3.1 What to Keep (the notebook look)

The current notebook-style timeline is good and should stay:
- Vertical scrolling timeline with event cards
- Expandable run cards with step digests
- Color-coded status indicators (green success, red failure)
- Time-formatted labels with duration chips
- "Latest" badge on most recent run

### 3.2 What to Add

#### A. Operation Events in Timeline

Currently only `run_started` and `run_finished` appear. Add:

| Event Type | Icon | What it shows |
|-----------|------|--------------|
| `step_add` | `＋` | "Added scf step to Si_bulk" |
| `step_update` | `✎` | "Updated scf parameters (ECUTWFC: 30→50)" |
| `preset_apply` | `🎯` | "Applied preset 'high_accuracy' to scf" |
| `structure_import` | `📐` | "Imported structure from POSCAR" |
| `calc_create` | `📁` | "Created calculation 'Si_bands'" |
| `species_map_update` | `⚛` | "Updated pseudopotential: Si → Si.pbe-n-rrkjus.UPF" |

These are all in the `operations` table already. Need:
1. Add `query_operations()` call to `QVService.History.get_timeline()`
2. Merge operation events + run events by timestamp
3. New `renderOperationEvent()` in HistoryPanel

#### B. Run Detail Drawer / Modal

When user clicks a run card, show a detail panel:

- **Snapshot viewer**: Show the YAML content at that checkpoint (from CAS via `snapshot_sha`)
- **Step details**: Per-step status, timing, energy metrics
- **Artifacts**: List of captured files (if `artifact_collection_sha` is set), with tier labels
- **Pinned analyses**: Thumbnails of pinned plots (bands, DOS, etc.)

#### C. Tiered Storage Summary

A small footer or collapsible section showing:

```
Provenance Storage: 12.3 MB
├── Tier-0 (snapshots):     2.1 MB  (42 objects)
├── Tier-1 (analyses):      3.8 MB  (15 objects)
├── Tier-2 (raw artifacts): 5.2 MB  (28 objects)
└── Tier-3 (large files):   1.2 MB  (3 objects)
```

This comes from `SELECT tier, COUNT(*), SUM(size_bytes) FROM cas_objects GROUP BY tier`.

#### D. Advanced Controls

- **Clear provenance** (already exists — fix the modal text from `.history` to `.provenance/`)
- **Clear tier-3 only**: Remove large rolling-window artifacts to save space
- **Export timeline**: Download as JSON or CSV for external analysis
- Future: **Restore to checkpoint** button (per run card) — disabled for now, placeholder

#### E. Filtering and Grouping

- **Filter by calculation**: Dropdown of calc names, passes `calc_ulid` to `get_timeline()`
- **Filter by event type**: Toggle checkboxes for runs/edits/presets/structure changes
- **Collapse run pairs**: Merge `run_started` + `run_finished` into one card (currently separate)

### 3.3 Architecture Constraint

Per Law P1: the History panel is purely a **viewer**. It reads from `.provenance/provenance.db`
and CAS. It never writes to SSOT. The only write action is "delete provenance" which removes the
entire `.provenance/` directory. Future rollback will write to SSOT through the existing
`restore.py` → `save_yaml_doc(opctx=opctx_for_restore())` path.

---

## 4. Problem 2: Resources Tab — Engine Knowledge Center

### 4.1 The Naming Problem

"Resources" is ambiguous. In materials science software:
- "Resources" could mean computational resources (CPU, memory)
- "Resources" could mean project resources (structures, pseudopotentials)
- "Resources" could mean reference materials (documentation, parameters)

For an end user who knows nothing about QMatSuite, "Resources" next to "Settings" gives no
indication that it's a parameter encyclopedia.

**Recommended name: "Reference"** — or more specifically, the tab could be named "Reference"
with the panel title being "Engine Parameter Reference".

Alternatives considered:
- "Encyclopedia" — too academic-sounding for a sidebar tab
- "Knowledge" — vague
- "Docs" — implies external documentation links
- "Reference" — concise, universally understood, matches what it does (look up parameter definitions)

### 4.2 What to Build

#### A. Engine Selector

Add an engine selector at the top of the panel. Two options:

**Option 1 — Horizontal tab bar** (recommended for ≤15 engines):
```
[QE] [VASP] [ORCA] [LAMMPS] [Gaussian] [ABINIT] [CP2K] [QMCPACK] [W90] [xTB] [Yambo]
```
Engines without metadata (GPAW, Psi4, PySCF, Siesta) show a placeholder:
"This engine uses Python API — parameters are documented in the Python code."

**Option 2 — Dropdown**:
Less discoverable but more compact. Show engine name + parameter count:
```
▾ VASP (238 parameters)
```

Recommendation: Horizontal tab bar with scrolling if needed. The visual presence of all engine
names immediately communicates "this tool supports many engines."

#### B. Engine Overview Card

When an engine is selected, show a brief header card before the parameter table:

```
╔══════════════════════════════════════════════════════╗
║  VASP                                                ║
║  Vienna Ab initio Simulation Package                 ║
║  Format: Namelist (INCAR key-value)                  ║
║  Parameters: 238 across 12 categories                ║
║  Input files: INCAR, POSCAR, KPOINTS, POTCAR         ║
╚══════════════════════════════════════════════════════╝
```

This gives the user instant context about what they're browsing.

#### C. Unified Search Across Engines

The existing search works within one engine. Add a "Search all engines" mode:

```
🔍 [ENCUT                    ] [Search all engines ☑]

Results:
  VASP  → ENCUT (REAL) — Plane-wave energy cutoff in eV
  ABINIT → ecut (REAL) — Kinetic energy cutoff in Hartree
  QE    → ecutwfc (REAL) — Kinetic energy cutoff for wavefunctions in Ry
  CP2K  → CUTOFF (REAL) — Plane-wave cutoff for auxiliary PW grid
```

This is extremely valuable for users migrating between engines — they can find the equivalent
parameter instantly.

#### D. Additional Reference Content

The "Reference" tab should grow beyond just parameters. Future additions:

1. **Pseudopotential library browser**: Browse available pseudos by element, show metadata
   (who generated it, cutoff recommendations, valence electrons)
2. **Basis set browser**: For molecular codes (Gaussian, ORCA, Psi4) — list available basis sets
3. **Step type reference**: What step types are available for each engine, what they do, what
   parameters they typically need
4. **Unit conversion table**: Ry ↔ eV ↔ Ha ↔ kcal/mol ↔ kJ/mol — always useful
5. **Quick-reference cards**: Common workflows per engine (SCF → Bands → DOS pipeline)

These don't all need to come at once, but the tab should be designed to accommodate sub-sections.

### 4.3 Metadata Inventory

| Engine | Tags/Keywords | Categories | Status in `_get_engine_metadata_module()` |
|--------|--------------|-----------|------------------------------------------|
| QE | 1,081 | 22 modules × N sections | Wired (special QE path) |
| VASP | 238 | 12 | Wired |
| ABINIT | 249 | 20+ | Wired |
| CP2K | 215 | 28 | Wired |
| ORCA | 136 | 24 | Wired |
| Gaussian | 130 | ~10 | Wired |
| LAMMPS | 114 | ~10 | Wired |
| W90 | 140 | ~8 | **NOT wired** — module exists |
| xTB | 82 | ~10 | **NOT wired** — module exists |
| Yambo | 73 | ~10 | **NOT wired** — module exists |
| QMCPACK | 65 | 11 | Wired |
| GPAW | — | — | Python-script engine, no metadata JSON |
| Psi4 | — | — | Python-script engine, no metadata JSON |
| PySCF | — | — | Python-script engine, no metadata JSON |
| Siesta | — | — | No metadata yet |

**Total displayable parameters: ~2,523 across 11 engines.**

### 4.4 Consistent Field Display

All metadata modules provide a consistent API (`get_tag_info`, `list_tags`, `list_categories`).
The displayable fields per parameter are:

| Field | Available in |
|-------|-------------|
| name | All 11 engines |
| type | All 11 engines |
| default | All 11 engines |
| description | All 11 engines |
| category | All 11 engines |
| see_also | VASP, ABINIT, LAMMPS, xTB |
| status | VASP, ABINIT, ORCA, Gaussian, LAMMPS, W90, xTB, Yambo |
| aliases | ORCA, Gaussian |
| units | QE, W90 |
| section | CP2K, QE |

The existing parameter table (Name, Type, Default, Description) covers the universal fields.
`see_also` could be rendered as clickable cross-references. `aliases` as chips below the name.

---

## 5. Problem 3: CLI `qv history`

### 5.1 The Opportunity

The provenance query API (`src/quantumvitas/provenance/query.py`) is complete and CLI-ready:

```python
from quantumvitas.provenance.query import (
    query_operations,  # All YAML write events
    query_runs,        # All calculation runs
    get_run_details,   # Full run with steps + snapshot
    get_latest_run_ulid,
    get_run_step_ulids,
)
```

And `QVService.History` provides a higher-level API:

```python
svc = get_service(project_root)
svc.history.get_timeline(limit=50)
svc.history.get_run_revision(run_ulid="...")
svc.history.list_runs(calc_ulid="...")
```

These are the **same APIs** the daemon uses for GUI. A CLI command can call them directly
(no daemon needed — just `get_service(project_root)`).

### 5.2 Proposed CLI Commands

```bash
# Show recent history (runs + operations) as a timeline
qv history [--limit 20] [--calc CALC_NAME]

# Show details of a specific run
qv history show <RUN_ULID>

# List all runs (compact table format)
qv history runs [--limit 20] [--status success|failed]

# Show provenance storage usage
qv history storage

# Delete provenance data
qv history clear [--confirm] [--tier3-only]

# Future: restore to a checkpoint
qv history restore <RUN_ULID> [--dry-run]
```

### 5.3 Example Output

```
$ qv history --limit 5

Project: Si_bulk_study (/path/to/project)

Timeline (5 most recent):
─────────────────────────────────────────────────────────
  Feb 11, 14:32  ✓ Run completed — Si_scf (3 steps, 42.1s)
                   E = -15.8543 Ry, Ef = 6.23 eV
  Feb 11, 14:31  ▶ Run started — Si_scf
  Feb 11, 14:30  ✎ Applied preset 'high_accuracy' to scf
  Feb 11, 14:28  ✎ Updated scf: ecutwfc 30→50, conv_thr 1e-6→1e-8
  Feb 11, 14:25  ＋ Added nscf step to Si_scf
─────────────────────────────────────────────────────────

Storage: 12.3 MB (42 snapshots, 15 analyses, 28 artifacts)
```

```
$ qv history show 01JKXYZ...

Run 01JKXYZ...  Status: success
Calculation: Si_scf
Started:  2026-02-11 14:31:02
Finished: 2026-02-11 14:32:14  (72.3s)
Engine:   qe

Steps:
  1. scf      ✓  E = -15.8543 Ry  (42.1s)
  2. nscf     ✓  (18.7s)
  3. bands    ✓  (11.5s)

Snapshot: abc123... (Tier-0, 4.2 KB)
Artifacts: 12 files (Tier-2, 8.1 MB)
Pins: bands_plot (PNG + JSON)
```

### 5.4 Also: Multi-Engine `qv params`

Extend the existing `qv params` command beyond QE:

```bash
# Current (QE only):
qv params pw --section SYSTEM

# Extended:
qv params vasp --category electronic
qv params orca --category method_dft_hybrid
qv params lammps --category potential

# Cross-engine search:
qv params search cutoff
```

---

## 6. UX Vision: What a New User Sees

### 6.1 The Problem with "Resources"

A new user opens QMatSuite and sees this sidebar:

```
📁 Project
📊 Analysis
⚡ Jobs
📜 History
📚 Resources   ← ???
⚙️ Settings
```

"Resources" gives no hint about what's inside. A physics student might click it expecting
to find their structure files or pseudopotentials. Instead they find a QE parameter table
with no way to switch engines. Confusing on multiple levels.

### 6.2 Proposed Sidebar

```
📁 Project
📊 Analysis
⚡ Jobs
📜 History        — "What happened" (provenance timeline)
📖 Reference      — "Look things up" (parameter encyclopedia)
⚙️ Settings       — "Configure the app"
```

The rename from "Resources" to "Reference" immediately signals "this is for looking things up."

### 6.3 First-Time Experience: Reference Tab

When a new user clicks "Reference" with no project loaded:

```
╔═══════════════════════════════════════════════════════════════╗
║  📖 Engine Parameter Reference                                ║
║                                                               ║
║  Browse input parameters for all supported simulation engines ║
║                                                               ║
║  [QE] [VASP] [ABINIT] [ORCA] [Gaussian] [CP2K] [LAMMPS]    ║
║  [QMCPACK] [W90] [xTB] [Yambo]  [GPAW°] [Psi4°] [PySCF°]  ║
║                                                    ° = API    ║
║                                                               ║
║  🔍 [Search across all engines...                          ]  ║
╚═══════════════════════════════════════════════════════════════╝
```

No project needed. This is a standalone reference tool. The engine tabs + search bar make
it instantly clear what this panel does.

### 6.4 First-Time Experience: History Tab

When a user clicks "History" with a project loaded but no runs yet:

```
╔═══════════════════════════════════════════════════════════════╗
║  📜 Project History                                           ║
║                                                               ║
║     📭 No History Yet                                         ║
║                                                               ║
║     Run a calculation to start recording history.             ║
║     Every run, parameter change, and structure edit           ║
║     will appear here as a timeline.                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

After some activity:

```
╔═══════════════════════════════════════════════════════════════╗
║  📜 Project History        [All ▾] [Calc: All ▾] [↻] [🗑]   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Feb 11, 14:32                                                ║
║  ┌─────────────────────────────────────────────────────────┐  ║
║  │ ✓ Run completed — Si_scf                     Latest  ▶ │  ║
║  │   [3/3 steps] [E = -15.854 Ry] [Ef = 6.23 eV]         │  ║
║  └─────────────────────────────────────────────────────────┘  ║
║                                                               ║
║  Feb 11, 14:30                                                ║
║  │ 🎯 Applied preset 'high_accuracy' to scf                  ║
║                                                               ║
║  Feb 11, 14:28                                                ║
║  │ ✎ Updated scf parameters (2 changes)                      ║
║                                                               ║
║  Feb 11, 14:25                                                ║
║  │ ＋ Added nscf step                                         ║
║                                                               ║
║  Feb 11, 14:20                                                ║
║  │ 📐 Imported structure from POSCAR                          ║
║                                                               ║
║  ─── Provenance Storage: 12.3 MB (88 objects) ───            ║
╚═══════════════════════════════════════════════════════════════╝
```

Key UX wins:
1. **Everything visible**: Not just runs, but every operation that changed the project
2. **Natural narrative**: Reads like a lab notebook — "imported structure, added step, tweaked params, ran calculation, got results"
3. **Actionable**: Each run card is expandable for details; future: click to restore
4. **Storage awareness**: User sees how much provenance data exists

---

## 7. Naming and Navigation

### 7.1 Tab Rename Summary

| Current | Proposed | Rationale |
|---------|----------|-----------|
| Resources | **Reference** | Unambiguous. "Look up parameter definitions" |
| History | History (keep) | Already clear. "What happened to my project" |

### 7.2 Sidebar Tooltip Updates

| Tab | Current tooltip | Proposed tooltip |
|-----|----------------|-----------------|
| History | "View project history timeline" | "View project history — runs, edits, and checkpoints" |
| Resources | "Browse QE parameter metadata and resources" | "Engine parameter reference — browse input parameters for all engines" |
| Settings | "Configure QE paths and app settings" | "Configure engine paths and app settings" |

### 7.3 Should Reference Be Inside Settings?

No. The parameter reference is used **during work** (while editing parameters), not just during
setup. It deserves its own top-level tab. However, future sub-sections of Reference (unit converter,
step type guide, etc.) should be accessible from within the editing panels too — e.g., a "?" icon
next to each parameter that opens its Reference entry.

---

## 8. Implementation Phases

### Phase 1: Quick Wins (wiring fixes)

1. **Wire 3 missing engines** in `api/utils.py:_get_engine_metadata_module()`: Yambo, W90, xTB
2. **Add engine selector** to EngineParameterBrowserPanel (replace hardcoded `"qe"`)
3. **Fix delete modal text**: `.history` → `.provenance/`
4. **Rename sidebar**: "Resources" → "Reference", update tooltips
5. **Update CSS class prefix**: `qe-parameter-browser` → `engine-parameter-browser` (or leave, cosmetic)

### Phase 2: Operation Events in History

1. Add `get_operations_timeline()` to `QVService.History` (wraps `query_operations()`)
2. Merge operations + runs into unified timeline, sorted by timestamp
3. Add `renderOperationEvent()` to HistoryPanel for each OperationType
4. Add calculation filter dropdown
5. Add event type filter toggles

### Phase 3: CLI `qv history`

1. Add `qv history` command (calls `svc.history.get_timeline()`)
2. Add `qv history show <RUN_ULID>` (calls `svc.history.get_run_revision()`)
3. Add `qv history runs` (calls `svc.history.list_runs()`)
4. Add `qv history storage` (queries `cas_objects` table)
5. Extend `qv params` to support all engines (not just QE)

### Phase 4: Enhanced History Viewer

1. Run detail drawer (snapshot viewer, artifact list, pin thumbnails)
2. Tiered storage summary in History panel footer
3. CAS object browser (advanced, under expandable section)
4. Clear tier-3 only option

### Phase 5: Cross-Engine Search & Reference Expansion

1. "Search all engines" mode in Reference tab
2. Engine overview cards (name, format, file list, parameter count)
3. Placeholder cards for Python-script engines (GPAW, Psi4, PySCF)
4. Foundation for future reference sub-sections (pseudos, basis sets, workflows)

---

## 9. File Inventory

### Frontend (GUI)

| File | Lines | Current State |
|------|-------|--------------|
| `gui/src/components/panels/HistoryPanel.tsx` | 448 | Functional, needs operation events |
| `gui/src/components/panels/HistoryPanel.css` | 446 | Complete dark/light CSS |
| `gui/src/components/panels/EngineParameterBrowserPanel.tsx` | 1032 | Functional, needs engine selector |
| `gui/src/components/panels/EngineParameterBrowserPanel.css` | 933 | Complete, CSS class naming is QE-centric |
| `gui/src/components/settings/JournalHistoryPanel.tsx` | — | Debug-only YAML journal viewer (separate concern) |
| `gui/src/components/layout/Sidebar.tsx` | — | Navigation, needs tooltip updates |
| `gui/src/App.tsx` | — | Routing, has hardcoded `engineFamily="qe"` |
| `gui/src/types/qv.ts` | — | Types: `HistoryTimelineEntry`, needs operation event fields |
| `gui/src/hooks/useEngineParameterMetadata.ts` | 439 | Legacy hook, unused — can be removed |

### Backend (Python)

| File | Lines | Current State |
|------|-------|--------------|
| `src/quantumvitas/provenance/query.py` | 378 | Complete, has `query_operations()` (not exposed in service) |
| `src/quantumvitas/provenance/recording.py` | 451 | Complete |
| `src/quantumvitas/provenance/cas.py` | 220 | Complete |
| `src/quantumvitas/provenance/snapshots.py` | 130 | Complete |
| `src/quantumvitas/provenance/restore.py` | 158 | Complete (rollback) |
| `src/quantumvitas/provenance/schema.py` | 289 | SQLite v3 schema |
| `src/quantumvitas/api/service.py` | — | `QVService.History` class, needs `get_operations_timeline()` |
| `src/quantumvitas/api/utils.py` | — | `_get_engine_metadata_module()` needs W90, xTB, Yambo |
| `src/quantumvitas/daemon/server.py` | — | 8 RPC endpoints, may need operations endpoint |
| `src/quantumvitas/cli/main.py` | ~4800 | Needs `qv history` commands and multi-engine `qv params` |

### Engine Metadata JSON (11 files)

| File | Tags |
|------|------|
| `src/quantumvitas/data/qe_module_parameters.json` | 1,081 |
| `src/quantumvitas/drivers/vasp/data/vasp_incar_tags.json` | 238 |
| `src/quantumvitas/drivers/abinit/data/abinit_tags.json` | 249 |
| `src/quantumvitas/drivers/cp2k/data/cp2k_tags.json` | 215 |
| `src/quantumvitas/drivers/w90/data/w90_tags.json` | 140 |
| `src/quantumvitas/drivers/orca/data/orca_keywords.json` | 136 |
| `src/quantumvitas/drivers/gaussian/data/gaussian_route_keywords.json` | 130 |
| `src/quantumvitas/drivers/lammps/data/lammps_commands.json` | 114 |
| `src/quantumvitas/drivers/xtb/data/xtb_tags.json` | 82 |
| `src/quantumvitas/drivers/yambo/data/yambo_tags.json` | 73 |
| `src/quantumvitas/drivers/qmcpack/data/qmcpack_tags.json` | 65 |

---

*End of review.*
