# Performance: App.tsx State Extraction — Worklog

## Goal
Extract 51 useState from monolithic App.tsx (3079 lines) into 4 React contexts + AppLayout.

## Phases
| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Create worklog | DONE |
| 1a | AppShellContext (12 state, 4 effects) | DONE |
| 1b | ProjectContext (15 state, 1 effect) | DONE |
| 1c | StructureContext (18 state, 5 effects) | DONE |
| 1d | CalculationContext (6 state, 4 effects) | DONE |
| 1e | AppLayout + slim App.tsx | DONE |
| 2 | React.memo on 9 components | DONE |
| 4 | Inline style extraction (F027) | DONE |
| 5 | Verification (build, type-check, E2E) | DONE |

## Before → After

| Metric | Before | After |
|--------|--------|-------|
| App.tsx lines | 3079 | 35 |
| useState in App.tsx | 51 | 0 |
| useEffect in App.tsx | 11 | 0 |
| useCallback in App.tsx | 43 | 0 |
| useMemo count | 0 | 4 (context values) |
| React.memo count | 0 | 9 |
| Context providers | 0 | 4 |

## New Files (6)
| File | Lines | Purpose |
|------|-------|---------|
| `gui/src/contexts/AppShellContext.tsx` | 305 | UI chrome state |
| `gui/src/contexts/ProjectContext.tsx` | 599 | Project data + CRUD |
| `gui/src/contexts/StructureContext.tsx` | 985 | Structure viewer + import |
| `gui/src/contexts/CalculationContext.tsx` | 554 | Calculation selection + detail |
| `gui/src/contexts/index.ts` | 11 | Barrel exports |
| `gui/src/components/AppLayout.tsx` | 976 | View rendering + orchestration |

## React.memo Components (9)
1. StructureViewer3D (Three.js — most expensive)
2. CalculationListPanel
3. StructureListPanel
4. Sidebar
5. StatusBar
6. StructureDetailPanel
7. CalculationOverviewTab
8. CalculationRunTab
9. CalculationAnalysisTab

## Verification Results
- TypeScript: 0 errors
- Vite production build: OK (3 bundles)
- E2E tests: **21 passed**, 0 failed, no timeouts
- Backend tests: 6534 passed (1 pre-existing gate failure unrelated to changes)

## Effect Chain Safety
All effect chains verified safe (no infinite loops):
- AppShell: 4 effects, all terminal (theme, updater, dismiss, cleanup)
- Project: 1 effect (auto-fetch), intentional deps exclusion preserved with eslint-disable
- Structure: 5 effects (auto-select reset, auto-select first, project load, online load, project-root clear)
  - Load effects guarded by leftMode, loadTokenRef, timeouts
- Calculation: 4 effects (auto-select reset, auto-select first, install polling, project-root clear)

## Log
- 2026-02-25: Completed all phases. App.tsx reduced from 3079 to 35 lines. All E2E tests pass.
