# GUI-CLI Feature Parity Plan

> This document maps CLI capabilities to GUI features and defines the implementation roadmap.

## 1. CLI → GUI Capability Mapping

### 1.1 Project Operations

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv init project` | ✅ Done | - | CreateProjectDialog |
| `qv init project --template` | ✅ Done | - | Template selector in dialog |
| Project load/browse | ✅ Done | - | Sidebar + file dialog |
| `qv delete project` | ❌ Missing | P2 | Context menu → confirm → trash |
| `qv configure project --name` | ❌ Missing | P3 | Settings in project summary |

### 1.2 Structure Operations

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv import-structure` | ✅ Done | - | ImportStructureDialog |
| `qv list` (structures) | ✅ Done | - | StructureListPanel |
| `qv configure structure --name` | ❌ Missing | P1 | Rename context menu |
| `qv delete structure` | ❌ Missing | P1 | Delete with cascade warning |
| Structure 3D viewer | ✅ Done | - | StructureViewer3D |

### 1.3 Calculation Operations

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv init calculation` | ✅ Done | - | CreateWorkflowDialog |
| `qv init calculation --template` | ✅ Done | - | Template selector |
| `qv list` (calculations) | ✅ Done | - | CalculationListPanel |
| `qv run calculation` | ✅ Done | - | CalculationDetailPanel → Run |
| `qv configure calculation --name` | ❌ Missing | P1 | Rename context menu |
| `qv configure calculation --structure` | ❌ Missing | P2 | Structure dropdown |
| `qv configure calculation --reorder` | ❌ Missing | P2 | Step drag-and-drop |
| `qv delete calculation` | ❌ Missing | P1 | Delete with cascade warning |
| Duplicate calculation | ❌ Missing | P3 | Clone with new name |

### 1.4 Step Operations

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv init step` | ❌ Missing | P1 | AddStepDialog |
| `qv run step` | ❌ Missing | P1 | StepDetailPanel → Run |
| Step detail view | ❌ Missing | P1 | StepDetailPanel |
| `qv configure step` (params) | ❌ Missing | P2 | Parameter form |
| `qv delete step` | ❌ Missing | P2 | Delete with calculation update |

### 1.5 Analysis Operations

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv analyze scf` | ✅ Done | - | AnalysisPanel SCF chart |
| `qv analyze dos` | ✅ Done | - | AnalysisPanel DOS chart |
| `qv analyze band` | ✅ Done | - | AnalysisPanel bands chart |
| `qv analyze structure` | ✅ Done | - | 3D viewer already exists |
| Link analysis to jobs | ❌ Missing | P2 | "View in Analysis" from job |

### 1.6 Environment/Settings

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| `qv detect-qe` | ❌ Missing | P1 | SettingsPanel |
| QE path display | ❌ Missing | P1 | SettingsPanel |
| Python/daemon info | ❌ Missing | P1 | SettingsPanel |
| Default project root | ❌ Missing | P3 | User preferences |
| `qv params` | ❌ Missing | P3 | Parameter reference panel |

### 1.7 Job Management

| CLI Command | GUI Status | Priority | Implementation Notes |
|-------------|------------|----------|---------------------|
| Job list | ✅ Done | - | JobsPanel |
| Job detail + logs | ✅ Done | - | JobDetailPanel |
| Cancel job | ✅ Done | - | Cancel button |
| Running indicator | ✅ Done | - | Sidebar badge |

---

## 2. Implementation Priority

### P1 - Must Have (First User Testing)

These features are essential for basic usability:

1. **Settings/Environment Panel**
   - Show QE detection status
   - Show Python/daemon info
   - Re-detect QE button
   - Clear error messaging for missing QE

2. **Structure Rename/Delete**
   - Context menu on structure list item
   - Rename dialog
   - Delete with confirmation (warns about calculations)

3. **Calculation Rename/Delete**
   - Context menu on calculation list item
   - Rename dialog
   - Delete with cascade warning

4. **Step Detail View**
   - Show step parameters (read-only initially)
   - Run individual step button
   - Step type and structure info

### P2 - Nice to Have

1. **Add Step to Calculation**
   - Dialog with step type dropdown
   - Template selector
   - Structure selector (defaults to calculation's)

2. **Change Calculation Structure**
   - Dropdown in calculation detail

3. **Reorder Steps**
   - Up/down buttons or simple drag

4. **Parameter Editing**
   - Edit ecutwfc, k-points, smearing
   - Structured forms, not raw YAML

5. **Analysis → Jobs Integration**
   - "View in Analysis" from completed job
   - Auto-populate calculation selection

### P3 - Later/Expert Features

1. Delete project
2. Recent projects list
3. Parameter reference (`qv params`)
4. Step templates browser
5. Advanced parameter editing
6. Import calculation from QE input files

---

## 3. Technical Implementation Notes

### 3.1 New Daemon RPCs Required

```typescript
// Settings/Environment
detect_qe: {
  payload: Record<string, never>;
  result: { found: boolean; qe_home: string | null; version: string | null; executables: string[] };
};
get_env_info: {
  payload: Record<string, never>;
  result: { python_version: string; qv_version: string; qe_home: string | null };
};

// Structure management
rename_structure: {
  payload: { project_root: string; selector: string; new_name: string };
  result: { success: boolean; old_name: string; new_name: string };
};
delete_structure: {
  payload: { project_root: string; selector: string; force?: boolean };
  result: { success: boolean; name: string; using_calculations?: string[] };
};

// Calculation management
rename_calculation: {
  payload: { project_root: string; selector: string; new_name: string };
  result: { success: boolean; old_name: string; new_name: string };
};
delete_calculation: {
  payload: { project_root: string; selector: string; force?: boolean };
  result: { success: boolean; name: string };
};

// Step operations
get_step_detail: {
  payload: { project_root: string; calculation: string; step: string };
  result: StepDetailData;
};
create_step: {
  payload: { project_root: string; calculation: string; step_type: string; template?: string };
  result: { step_id: string; name: string; type: string };
};
delete_step: {
  payload: { project_root: string; calculation: string; step: string };
  result: { success: boolean };
};
```

### 3.2 New React Components Required

```
components/
├── panels/
│   ├── SettingsPanel.tsx      # QE detection, env info
│   ├── StepDetailPanel.tsx    # Step parameters display
│   └── StepListPanel.tsx      # Steps within calculation
├── dialogs/
│   ├── RenameDialog.tsx       # Generic rename dialog
│   ├── DeleteConfirmDialog.tsx # Confirm delete with warnings
│   └── CreateStepDialog.tsx   # Add step to calculation
└── ui/
    └── ContextMenu.tsx        # Right-click context menus
```

### 3.3 Component Architecture Changes

1. **CalculationDetailPanel** should show expandable step list
2. **StepDetailPanel** as child/accordion within calculation detail
3. **ContextMenu** component for rename/delete actions
4. **SettingsPanel** as new view in sidebar

---

## 4. Phased Implementation Plan

### Phase 1: Settings & QE Detection (Day 1)

1. Add `detect_qe` and `get_env_info` to QVService
2. Add daemon handlers
3. Create SettingsPanel component
4. Add "Settings" view to sidebar
5. Display QE status prominently

### Phase 2: Structure CRUD (Day 1-2)

1. Add `rename_structure` and `delete_structure` to QVService
2. Add daemon handlers
3. Create RenameDialog and DeleteConfirmDialog
4. Add context menu to StructureListPanel
5. Handle cascade warnings for delete

### Phase 3: Calculation CRUD (Day 2)

1. Add `rename_calculation` and `delete_calculation` to QVService
2. Add daemon handlers
3. Add context menu to CalculationListPanel
4. Wire up dialogs

### Phase 4: Step Operations (Day 2-3)

1. Add `get_step_detail` and `run_step` to daemon
2. Create StepDetailPanel
3. Expand calculation detail to show steps
4. Add "Run Step" button

### Phase 5: Polish (Day 3)

1. Error handling improvements
2. Empty states for missing QE
3. Loading skeletons
4. Persist last view state

---

## 5. Success Criteria

A user should be able to:

1. ✅ Open QV GUI without any CLI knowledge
2. ✅ Understand if QE is properly configured (new)
3. ✅ Create a new project
4. ✅ Import a structure file
5. ✅ Create a calculation from template
6. ⬜ Add/remove steps from calculation (new)
7. ✅ Run a calculation
8. ✅ Monitor job progress
9. ✅ View analysis results
10. ⬜ Rename/delete structures and calculations (new)

---

*Created: 2025-12-06*
*For: GUI-CLI Feature Parity Implementation*

