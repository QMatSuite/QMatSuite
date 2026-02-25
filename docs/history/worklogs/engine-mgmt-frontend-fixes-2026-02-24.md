# Engine Management Frontend Fixes — Worklog

**Date**: 2026-02-24
**Branch**: v2-python
**Status**: Complete

## Context

Session 1 (backend) added progress infrastructure to the engine install pipeline:
- `Job` dataclass gained `progress_pct`, `progress_bytes`, `progress_total`, `progress_stage` fields
- `get_job_status` returns all these fields via `job.to_dict()`
- Download functions report byte progress; `run_micromamba` streams stdout as `log_line` events
- Install functions emit stage events (Bootstrapping, Installing, Verifying, Extracting, Registering)

The frontend was ignoring all of this — showing static "install in progress..." text for 5-20 minutes with no visual feedback.

## Changes

### Fix 1: Progress Bar for Engine Install

**Files modified:**
- `gui/src/types/qms.ts` — Added `progress_pct`, `progress_bytes`, `progress_total`, `progress_stage` to `JobInfo` interface
- `gui/src/components/panels/SettingsPanel.tsx` — Major UI improvements
- `gui/src/components/panels/SettingsPanel.css` — Progress bar and notice styles

**SettingsPanel.tsx changes:**
1. **Expanded `pendingJobs` state type** — Added `progressPct`, `progressBytes`, `progressTotal`, `progressStage`, `startedAt` fields (all nullable)
2. **Helper functions** — `formatBytes()` (human-readable byte sizes) and `formatElapsed()` (elapsed time from ISO timestamp)
3. **Tick timer** — 1-second `setInterval` while jobs are active, triggers re-render so `formatElapsed()` updates smoothly
4. **Polling handler split** — `pending` status shows "Waiting for current task..." with indeterminate bar; `running` status shows actual progress data
5. **Progress bar JSX** — Determinate bar (width%) when `progressPct` is available, indeterminate animation otherwise. Shows: stage name, percentage, byte counter, elapsed time, log line
6. **EngineNotice component** — Expandable error text (truncates at 150 chars with "Show more" toggle)

**CSS additions:**
- `.engine-progress-bar` — 4px height, rounded, with fill transition
- `.engine-progress-bar__fill--indeterminate` — Sliding animation via `@keyframes engine-progress-indeterminate`
- `.engine-progress-info` — Flexbox layout for stage + stats
- `.engine-progress-log` — Monospace log line display
- `.engine-notice-toggle` — Underlined button for expand/collapse

### Fix 2: Queue Position Display

When a job is in `pending` status (waiting behind another job), the UI now shows "Waiting for current task to complete..." with an indeterminate progress bar, instead of the generic "Install queued..." text.

### Fix 3: Error Display Improvements

Added `EngineNotice` component that truncates long error messages (>150 chars) with a "Show more"/"Show less" toggle button.

### E2E Test Updates

**File:** `gui/tests/e2e/engine_manager.spec.ts`

1. **Updated existing mock** — `get_job_status` mock now includes `progress_pct`, `progress_bytes`, `progress_total`, `progress_stage`, `started_at`
2. **Enhanced install test** — Verifies `.engine-progress-bar` element exists and stage text matches `/Installing|Waiting/`
3. **New flow test** — `pending → running → completed` state machine test:
   - Phase 1: pending → indeterminate bar, "Waiting" text
   - Phase 2: running with progress → determinate bar, "Installing" text
   - Phase 3: completed → progress disappears, notice appears with "completed"

## Verification

- `tsc --noEmit` — 0 errors
- `tsc && vite build` — Clean build
