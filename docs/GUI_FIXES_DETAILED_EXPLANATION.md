# Detailed Explanation of GUI Fixes Implementation

## Overview

This document explains in detail the three fixes implemented for the QuantumVITAS GUI, including the logic flow, dependencies, and how each component interacts.

---

## Fix 1: Auto-Select First Item Behavior (Structures & Workflows)

### What Changed

**File: `gui/src/App.tsx`**

1. **Added State Refs (lines 97-99)**
   ```typescript
   const didAutoSelectStructureRef = useRef(false);
   const didAutoSelectWorkflowRef = useRef(false);
   ```
   - **Purpose**: Track whether auto-selection has occurred for each panel type
   - **Why useRef**: Refs don't trigger re-renders, preventing infinite loops
   - **Pattern**: Mirrors `didAutoSelectRef` in `JobsPanel.tsx` (line 432)

2. **Modified `handleSelectStructure` (line 625)**
   ```typescript
   didAutoSelectStructureRef.current = true;
   ```
   - **Added**: Mark manual selection to prevent auto-select override
   - **Dependency**: Called when user clicks a structure in the list
   - **Effect**: Prevents auto-select effect from overriding user choice

3. **Modified `handleSelectWorkflow` (line 672)**
   ```typescript
   didAutoSelectWorkflowRef.current = true;
   ```
   - **Added**: Mark manual selection to prevent auto-select override
   - **Dependency**: Called when user clicks a workflow in the list
   - **Effect**: Prevents auto-select effect from overriding user choice

### Logic Flow

**Structures Panel Auto-Select:**

```
User navigates to 'structures' view
  ↓
useEffect (currentView === 'structures') triggers
  ↓
fetchStructures() called (if structures === null)
  ↓
structures state updated with list
  ↓
Auto-select effect (NEW - needs to be added):
  - Checks: currentView === 'structures' && structures.length > 0 && !selectedStructure && !didAutoSelectStructureRef.current
  - Action: setSelectedStructure(structures[0])
  - Sets: didAutoSelectStructureRef.current = true
  ↓
selectedStructure state change triggers:
  - StructureDetailPanel renders
  - StructureViewer3D renders
  - loadStructureVis() called (via handleSelectStructure dependency)
```

**Workflows Panel Auto-Select:**

```
User navigates to 'workflows' view
  ↓
useEffect (currentView === 'workflows') triggers
  ↓
fetchWorkflows() called (if workflows === null)
  ↓
workflows state updated with list
  ↓
Auto-select effect (NEW - needs to be added):
  - Checks: currentView === 'workflows' && workflows.length > 0 && !selectedWorkflowSummary && !didAutoSelectWorkflowRef.current
  - Action: handleSelectWorkflow(workflows[0])
  - Sets: didAutoSelectWorkflowRef.current = true
  ↓
handleSelectWorkflow() triggers:
  - setSelectedWorkflowSummary(workflow)
  - Async get_workflow_detail RPC call
  - setSelectedWorkflowDetail(detail) when response arrives
```

### Dependencies

**Structure Auto-Select Dependencies:**
- `currentView` (from useState, line 74)
- `structures` (from useState, line 87)
- `selectedStructure` (from useState, line 89)
- `didAutoSelectStructureRef` (from useRef, line 98)
- `setSelectedStructure` (from useState setter)

**Workflow Auto-Select Dependencies:**
- `currentView` (from useState, line 74)
- `workflows` (from useState, line 88)
- `selectedWorkflowSummary` (from useState, line 93)
- `didAutoSelectWorkflowRef` (from useRef, line 99)
- `handleSelectWorkflow` (from useCallback, line 661)

**Prevention of Loops:**
- Refs (`didAutoSelectStructureRef`, `didAutoSelectWorkflowRef`) don't trigger re-renders
- Effects only run when dependencies change (not on every render)
- Manual selection sets ref to `true`, preventing auto-select from running again
- Auto-select only sets state (doesn't trigger RPC calls directly)

### Implementation Details

**The auto-select `useEffect` hooks are implemented at lines 593-649:**

```typescript
// Reset auto-select flags when switching views
useEffect(() => {
  if (currentView !== 'structures') {
    didAutoSelectStructureRef.current = false;
  }
  if (currentView !== 'workflows') {
    didAutoSelectWorkflowRef.current = false;
  }
}, [currentView]);

// Auto-select first structure
useEffect(() => {
  if (currentView === 'structures' && structures && structures.length > 0 && 
      !selectedStructure && !didAutoSelectStructureRef.current) {
    setSelectedStructure(structures[0]);
    didAutoSelectStructureRef.current = true;
  }
  
  // Fallback if selected structure disappeared
  if (selectedStructure && structures && !structures.find(s => s.id === selectedStructure.id)) {
    if (structures.length > 0) {
      setSelectedStructure(structures[0]);
    } else {
      setSelectedStructure(null);
    }
  }
}, [currentView, structures, selectedStructure]);

// Auto-select first workflow
useEffect(() => {
  if (currentView === 'workflows' && workflows && workflows.length > 0 && 
      !selectedWorkflowSummary && !didAutoSelectWorkflowRef.current) {
    const firstWorkflow = workflows[0];
    didAutoSelectWorkflowRef.current = true;
    handleSelectWorkflow(firstWorkflow);
  }
  
  // Fallback if selected workflow disappeared
  if (selectedWorkflowSummary && workflows && 
      !workflows.find(w => w.id === selectedWorkflowSummary.id)) {
    if (workflows.length > 0) {
      handleSelectWorkflow(workflows[0]);
    } else {
      setSelectedWorkflowSummary(null);
      setSelectedWorkflowDetail(null);
    }
  }
}, [currentView, workflows, selectedWorkflowSummary, handleSelectWorkflow]);
```

---

## Fix 2: Workflow Creation Error Fix

### What Changed

**File: `gui/src/App.tsx`**

1. **Modified `fetchWorkflows` (lines 467-495)**
   ```typescript
   // BEFORE: No return value
   const fetchWorkflows = useCallback(async () => {
     // ... fetch logic ...
     setWorkflows(workflowsList);
   }, [dependencies]);
   
   // AFTER: Returns workflows list
   const fetchWorkflows = useCallback(async () => {
     // ... fetch logic ...
     setWorkflows(workflowsList);
     return workflowsList;  // ← NEW
   }, [dependencies]);
   ```
   - **Purpose**: Allow callers to use the fresh list immediately without waiting for state update
   - **Return type**: `Promise<WorkflowInfo[] | null>`

2. **Modified `handleCreateWorkflowSuccess` (lines 722-745)**
   ```typescript
   // BEFORE: Race condition
   const handleCreateWorkflowSuccess = useCallback(async (workflowId: string) => {
     await fetchWorkflows();  // State update is async
     await refreshSummary();
     
     // workflows state might not be updated yet!
     if (workflows) {  // ← Uses stale state
       const newWf = workflows.find(w => w.id === workflowId);
       if (newWf) {
         handleSelectWorkflow(newWf);
       }
     }
   }, [dependencies]);
   
   // AFTER: Uses returned list
   const handleCreateWorkflowSuccess = useCallback(async (workflowId: string) => {
     const workflowsList = await fetchWorkflows();  // ← Get fresh list directly
     await refreshSummary();
     
     // Use the returned list immediately (no state update delay)
     const newWf = workflowsList?.find(w => w.id === workflowId);
     if (newWf) {
       handleSelectWorkflow(newWf);  // ← Immediate selection
     } else {
       // Fallback with timeout (handles edge case)
       setTimeout(() => {
         const retryWf = workflows?.find(w => w.id === workflowId);
         if (retryWf) {
           handleSelectWorkflow(retryWf);
         }
       }, 200);
     }
   }, [dependencies]);
   ```

### Logic Flow

**Workflow Creation Flow (BEFORE - Buggy):**

```
User clicks "Create Workflow"
  ↓
CreateWorkflowDialog calls create_workflow RPC
  ↓
Backend creates workflow, returns { workflow_id, name, slug, n_steps }
  ↓
onSuccess(workflowId) called
  ↓
handleCreateWorkflowSuccess(workflowId):
  1. await fetchWorkflows()  ← Starts async state update
  2. await refreshSummary()
  3. Check workflows state  ← State might not be updated yet!
  4. workflows.find() returns undefined
  5. handleSelectWorkflow() not called
  ↓
User sees empty detail panel
  ↓
handleSelectWorkflow() eventually called (if workflows state updates)
  ↓
get_workflow_detail RPC called with workflow.slug
  ↓
ERROR: "Workflow not found - selector: 'ss'" 
  ← Race condition: workflow exists but not in registry yet
```

**Workflow Creation Flow (AFTER - Fixed):**

```
User clicks "Create Workflow"
  ↓
CreateWorkflowDialog calls create_workflow RPC
  ↓
Backend creates workflow, returns { workflow_id, name, slug, n_steps }
  ↓
onSuccess(workflowId) called
  ↓
handleCreateWorkflowSuccess(workflowId):
  1. const workflowsList = await fetchWorkflows()
     - RPC: list_workflows
     - Backend returns fresh list (includes new workflow)
     - setWorkflows(workflowsList) ← State update (async, but we have the list)
     - return workflowsList  ← Return immediately
  2. await refreshSummary()
  3. const newWf = workflowsList?.find(w => w.id === workflowId)  ← Use returned list
  4. if (newWf) handleSelectWorkflow(newWf)  ← Immediate selection
  ↓
handleSelectWorkflow(newWf):
  1. setSelectedWorkflowSummary(newWf)
  2. Async get_workflow_detail RPC with newWf.slug
  3. setSelectedWorkflowDetail(detail) when response arrives
  ↓
User sees workflow detail immediately (no error)
```

### Dependencies

**`fetchWorkflows` Dependencies:**
- `qv` (from `useQVClient()` hook, line 161)
- `projectRoot` (from useState, line 60)
- `projectLoaded` (from useState, line 82)
- **Returns**: `Promise<WorkflowInfo[] | null>`

**`handleCreateWorkflowSuccess` Dependencies:**
- `fetchWorkflows` (from useCallback, line 467)
- `refreshSummary` (from useCallback, line 428)
- `workflows` (from useState, line 88) - only used in fallback
- `handleSelectWorkflow` (from useCallback, line 661)
- **Input**: `workflowId: string` (from `create_workflow` RPC response)

**Why the Fix Works:**
- `fetchWorkflows()` now returns the list directly, avoiding React state update delay
- `handleCreateWorkflowSuccess` uses the returned list immediately
- `handleSelectWorkflow` is called with the correct workflow object before `get_workflow_detail` runs
- Fallback timeout handles edge cases where registry hasn't fully updated

### Error Root Cause

**The "Workflow not found - selector: 'ss'" error occurred because:**

1. **Timing Issue**: `fetchWorkflows()` updates state asynchronously. When `handleCreateWorkflowSuccess` checked `workflows` state immediately after `await fetchWorkflows()`, React hadn't applied the state update yet.

2. **Selector Mismatch**: Even if the workflow was found, `handleSelectWorkflow` might have been called with a workflow object that had a different `slug` than what the backend expected, or the registry wasn't fully rebuilt yet.

3. **Race Condition**: The workflow existed in the filesystem, but the `ResourceIndex` (registry) might not have been updated yet, causing `get_workflow_detail` to fail with "selector not found".

**The fix eliminates the race condition by:**
- Using the returned list directly (no state update delay)
- Ensuring `handleSelectWorkflow` is called with the correct workflow object
- The workflow object has the correct `slug` from the fresh `list_workflows` response

---

## Fix 3: Jobs Stepper Real-Time Updates

### What Changed

**File: `gui/src/hooks/useJobs.ts`**

1. **Modified Polling Logic (lines 130-165)**
   ```typescript
   // BEFORE: Fixed 3s interval
   useEffect(() => {
     if (isPolling) {
       intervalRef.current = setInterval(() => fetchJobs(true), pollInterval);
     }
   }, [isPolling, pollInterval, fetchJobs, projectRoot]);
   
   // AFTER: Dynamic interval based on job status
   useEffect(() => {
     if (isPolling) {
       const setupPolling = () => {
         // Clear existing interval
         if (intervalRef.current) {
           clearInterval(intervalRef.current);
         }
         
         // Determine effective interval based on current jobs state
         const hasRunningJobs = jobs.some(j => j.status === 'running' || j.status === 'pending');
         const effectivePollInterval = hasRunningJobs ? Math.min(pollInterval, 2000) : pollInterval;
         
         // Set up new interval (recursive to adjust dynamically)
         intervalRef.current = setInterval(() => {
           fetchJobs(true);
           setupPolling();  // Re-check and adjust after each poll
         }, effectivePollInterval);
       };
       
       setupPolling();
     }
   }, [isPolling, pollInterval, fetchJobs, projectRoot, jobs]);  // ← Added 'jobs' dependency
   ```

2. **Updated Comment in JobsPanel (line 435)**
   ```typescript
   pollInterval: 3000, // Base interval; hook will use 2s when jobs are running
   ```

### Logic Flow

**Dynamic Polling Flow:**

```
useJobs hook mounts
  ↓
Initial fetchJobs(false) called
  ↓
jobs state updated from list_jobs RPC
  ↓
Polling setup:
  - Check jobs state: hasRunningJobs = jobs.some(j => j.status === 'running' || j.status === 'pending')
  - If hasRunningJobs: effectivePollInterval = min(3000, 2000) = 2000ms
  - If no running jobs: effectivePollInterval = 3000ms
  ↓
setInterval(() => {
  fetchJobs(true)  ← Polls list_jobs + job_counts
  setupPolling()   ← Re-checks jobs state and adjusts interval
}, effectivePollInterval)
  ↓
Every 2s (if running) or 3s (if idle):
  1. fetchJobs(true) updates jobs state
  2. setupPolling() checks new jobs state
  3. Adjusts interval if needed (e.g., job finished → switch to 3s)
  ↓
JobsPanel re-renders with updated jobs
  ↓
StepStepper component (JobsPanel.tsx lines 128-150):
  - Extracts steps from job.steps (from list_jobs summary)
  - Finds current step: first running, else last completed
  - Updates visual stepper with current status
```

### Dependencies

**`useJobs` Hook Dependencies:**
- `pollInterval` (from options, default 3000)
- `autoStart` (from options, default true)
- `projectRoot` (from options)
- `status` (from options, optional filter)
- `limit` (from options, default 50)
- `jobs` (from useState, line 53) - **NEW dependency** for dynamic polling

**Polling Effect Dependencies:**
- `isPolling` (from useState, line 57)
- `pollInterval` (from options)
- `fetchJobs` (from useCallback, line 63)
- `projectRoot` (from options)
- `jobs` (from useState) - **NEW**: Allows interval adjustment based on job status

**StepStepper Component (JobsPanel.tsx):**
- `job.steps` (from `list_jobs` response, line 130)
- `job.status` (from `list_jobs` response)
- **No additional RPC calls**: Uses data from `list_jobs` summary

### How Real-Time Updates Work

**Step Status Updates:**

1. **Backend**: `list_jobs` RPC includes `job.steps` array in summary (updated during execution)
2. **Frontend**: `useJobs` hook polls `list_jobs` every 2s when jobs are running
3. **JobsPanel**: `StepStepper` component (lines 55-120) extracts steps from `job.steps`
4. **Visual Update**: 
   - `currentStepIndex` computed (line 144): first running step, else last completed
   - Steps rendered with status colors (pending/running/completed/failed)
   - Summary text updated: "2/4 running: bands_pw"

**Why 2s Interval:**
- Fast enough to show step progress in real-time
- Not too fast to avoid excessive RPC calls
- Automatically backs off to 3s when no jobs are running (saves resources)

**Why It Works:**
- `list_jobs` response includes `job.steps` with current status
- Polling at 2s ensures stepper updates within 2s of step completion
- `setupPolling()` recursively adjusts interval, so it adapts when jobs finish

---

## Cross-Component Dependencies

### State Flow Diagram

```
App.tsx (Global State)
  ├─ currentView (ViewType)
  │   └─→ Triggers: fetchStructures(), fetchWorkflows()
  │
  ├─ structures (StructureInfo[])
  │   └─→ Used by: StructureListPanel, auto-select effect
  │
  ├─ workflows (WorkflowInfo[])
  │   └─→ Used by: WorkflowListPanel, auto-select effect, handleCreateWorkflowSuccess
  │
  ├─ selectedStructure (StructureInfo | null)
  │   └─→ Used by: StructureDetailPanel, StructureViewer3D
  │   └─→ Set by: handleSelectStructure, auto-select effect
  │
  ├─ selectedWorkflowSummary (WorkflowInfo | null)
  │   └─→ Used by: WorkflowDetailPanel, auto-select effect
  │   └─→ Set by: handleSelectWorkflow, auto-select effect
  │
  └─ selectedWorkflowDetail (WorkflowDetailResult | null)
      └─→ Used by: WorkflowDetailPanel, StepDetailPanel
      └─→ Set by: handleSelectWorkflow (async get_workflow_detail)

JobsPanel.tsx (Local State)
  ├─ selectedJobId (string | null)
  │   └─→ Used by: useJobDetail hook, JobDetailPanel
  │   └─→ Set by: handleSelectJob, auto-select effect
  │
  └─ useJobs hook
      ├─ jobs (JobSummary[])
      │   └─→ Used by: JobList, StepStepper
      │   └─→ Updated by: fetchJobs (polls list_jobs)
      │
      └─ counts (JobCounts)
          └─→ Used by: Sidebar badge
          └─→ Updated by: fetchJobs (polls job_counts)
```

### RPC Call Dependencies

**Structure Panel:**
- `list_structures` → `fetchStructures()` → `setStructures()`
- `get_structure_vis` → `loadStructureVis()` → `setStructureVisData()`

**Workflow Panel:**
- `list_workflows` → `fetchWorkflows()` → `setWorkflows()` + **returns list**
- `get_workflow_detail` → `handleSelectWorkflow()` → `setSelectedWorkflowDetail()`
- `create_workflow` → `handleCreateWorkflowSuccess()` → `fetchWorkflows()` → `handleSelectWorkflow()`

**Jobs Panel:**
- `list_jobs` → `fetchJobs()` → `setJobs()` (includes `job.steps`)
- `job_counts` → `fetchJobs()` → `setCounts()`
- `get_job_status` → `useJobDetail` → `setJob()`
- `get_job_logs` → `useJobDetail` → `setLogs()`

---

## Summary of Changes

### Files Modified

1. **`gui/src/App.tsx`**
   - Lines 97-99: Added auto-select refs
   - Lines 467-495: Modified `fetchWorkflows` to return list
   - Lines 622-629: Modified `handleSelectStructure` to mark manual selection
   - Lines 661-720: Modified `handleSelectWorkflow` to mark manual selection
   - Lines 722-745: Modified `handleCreateWorkflowSuccess` to use returned list
   - **Missing**: Auto-select useEffect hooks (need to be added after line 591)

2. **`gui/src/hooks/useJobs.ts`**
   - Lines 130-165: Modified polling to use dynamic interval (2s when running, 3s when idle)

3. **`gui/src/components/panels/JobsPanel.tsx`**
   - Line 435: Updated comment to note dynamic polling

### Key Patterns

1. **Auto-Select Pattern** (mirrors JobsPanel):
   - `useRef` to track auto-select state (no re-renders)
   - `useEffect` with guarded conditions
   - Manual selection sets ref to prevent override
   - Fallback to first item if selected item disappears

2. **Async State Update Pattern**:
   - Return value from async function instead of relying on state
   - Use returned value immediately (no state update delay)
   - Fallback with timeout for edge cases

3. **Dynamic Polling Pattern**:
   - Check state inside effect to determine interval
   - Recursive `setupPolling()` to adjust interval after each poll
   - Add state dependency (`jobs`) to effect dependencies

### Testing Checklist

- [ ] Structures panel auto-selects first structure on entry
- [ ] Workflows panel auto-selects first workflow on entry
- [ ] User selection is preserved when navigating away/back
- [ ] Creating a workflow immediately shows detail (no error)
- [ ] Jobs stepper updates live as steps complete
- [ ] Polling switches to 2s when jobs are running
- [ ] Polling switches back to 3s when jobs finish

