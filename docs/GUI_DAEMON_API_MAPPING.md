# GUI → Daemon → Backend API Mapping

This document maps the GUI components to daemon endpoints and backend functions, ensuring consistency with the DAG + ID-only model.

## Job Submission & Listing

### Flow: GUI → Daemon → Backend

1. **GUI**: `handleRunWorkflow()` in `App.tsx`
   - Calls: `qv.call('run_calculation', { project_root: projectRoot, calculation: calculation.slug })`
   - Uses: `calculation.slug` (not ULID) for calculation selector
   - Uses: `projectRoot` (string from state)

2. **Daemon**: `_handle_run_calculation()` in `server.py`
   - Normalizes: `project_root` to `Path(project_root).resolve()`
   - Stores: `project_root_display=str(project_root.resolve())` in job
   - Calls: `QVService.run_calculation()` with normalized paths

3. **Backend**: `QVService.run_calculation()`
   - Resolves calculation via registry using selector
   - Executes calculation via `CalculationRunner`

### Job Listing

1. **GUI**: `useJobs` hook in `hooks/useJobs.ts`
   - Calls: `list_jobs` with `{ project_root: projectRoot, status, limit }`
   - Polls every 3 seconds when `isPolling` is true
   - Handles empty state: Shows "No Jobs" when `!isLoading && jobs.length === 0`

2. **Daemon**: `_handle_list_jobs()` in `server.py`
   - Normalizes: `project_root` to absolute path string for filtering
   - Calls: `JobManager.list_jobs()` with normalized `project_root`

3. **Backend**: `JobManager.list_jobs()` in `jobs.py`
   - Filters jobs by normalized `project_root` (string comparison after normalization)
   - Returns job summaries sorted by `created_at` (newest first)

### Key Fix: Path Normalization

**Problem**: Jobs were not appearing because `project_root` strings didn't match exactly (trailing slashes, relative vs absolute).

**Solution**: 
- Normalize `project_root` in `_handle_list_jobs()` before filtering
- Normalize `project_root_display` in `_handle_run_calculation()` when storing job
- Normalize both sides in `JobManager.list_jobs()` for comparison

## Step Detail Retrieval

### Flow: GUI → Daemon → Backend

1. **GUI**: `StepDetailPanel` component
   - Calls: `get_step_detail` with `{ project_root, calculation: workflowSelector, step: stepSelector }`
   - Uses: `workflowSelector = selectedWorkflow.slug` (from calculation list)
   - Uses: `stepSelector = selectedStepId` (from `step.id` which is ULID)

2. **Daemon**: `_handle_get_step_detail()` in `server.py`
   - Resolves step via registry with cache fallback
   - Calls: `QVService.get_step_detail()`

3. **Backend**: `QVService.get_step_detail()` in `api.py`
   - Resolves step via `resolve_step()` (handles ULID, slug, name, path)
   - Loads step spec from YAML
   - Returns step metadata, parameters, cards

### Key Fix: Step Detail Panel Visibility

**Problem**: Step detail panel was stuck in loading state because test ID was only set when `stepDetail` existed.

**Solution**: 
- Added `data-testid="qv-step-detail"` to loading, error, and empty states
- Panel is now always visible to tests, even during loading/errors

## Selector Format Summary

### Calculation Selectors
- **GUI uses**: `calculation.slug` (e.g., "si-dos", "si-bands")
- **Backend accepts**: ULID, slug, name, or path
- **Resolution**: Via `ResourceIndex` → `resolve_calculation()`

### Step Selectors
- **GUI uses**: `step.id` (ULID, 26 chars) from `calculation.steps[]`
- **Backend accepts**: ULID, slug, name, step_type, or path
- **Resolution**: Via `ResourceIndex` → `resolve_step()` within calculation context

### Project Root
- **GUI sends**: String from state (may be relative or absolute)
- **Daemon normalizes**: Always converts to absolute path string
- **Job filtering**: Uses normalized absolute path for exact matching

## DAG + ID-only Invariants

### Calculation YAML
- Contains: `structure_id` (ULID)
- Does NOT contain: `structure_name`, `structure` selector (cosmetic only)
- Steps: `step_id` (ULID) references only

### Step YAML
- Does NOT contain: `structure_id`, `parent_workflow_id`, `structure` selector
- Structure: Inherited from `calculation.structure_id` at runtime
- Calculation: Resolved via registry using `step_id` → calculation mapping

### Cross-Resource References
- All references use ULIDs (26-char alphanumeric)
- Resolution via `ResourceIndex` (built from resource file meta blocks)
- `project.qv.yml` stores only IDs, not duplicated name/slug/path

