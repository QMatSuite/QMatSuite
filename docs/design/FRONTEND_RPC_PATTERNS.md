# Frontend RPC Patterns and Call Count Management

This document describes the patterns used in the QuantumVITAS GUI for making RPC calls to the daemon, with a focus on preventing infinite loops and controlling call frequency. It is essential reading for anyone working on GUI components that interact with the daemon.

## Table of Contents

1. [Stable Client / Memoization Rules](#stable-client--memoization-rules)
2. [Call Count Expectations](#call-count-expectations)
3. [QE Parameter Browser Specific Behavior](#qe-parameter-browser-specific-behavior)
4. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)
5. [Developer Checklist](#developer-checklist)

---

## Stable Client / Memoization Rules

### The Problem

React's `useEffect` hooks re-run whenever their dependencies change. If a component depends on the `qv` client object from `useQVClient()`, and that object is recreated on every render, the effect will run continuously, causing infinite RPC call loops.

### The Solution

The `useQVClient()` hook returns a **stable client reference** that does not change between renders, even though its internal state is updated.

**Implementation in `useQVClient.ts`:**

```typescript
// Use ref to maintain stable client object reference
// This prevents infinite loops in effects that depend on qv
const clientRef = useRef<QVClient | null>(null);

if (!clientRef.current) {
  clientRef.current = {
    state,
    call,
    ping,
    // ... other methods
  };
} else {
  // Update state property in place to maintain reference stability
  // All other properties (callbacks) are already stable due to useCallback
  clientRef.current.state = state;
}

return clientRef.current;
```

### Effect Dependency Rules

**✅ Good Pattern:**
```typescript
useEffect(() => {
  // Load modules once on mount
  qv.call('list_modules', {});
}, [qv]); // qv is stable, so this runs once
```

**✅ Good Pattern:**
```typescript
useEffect(() => {
  if (!selectedModule) return;
  // Load sections when module changes
  qv.call('list_sections', { module: selectedModule });
}, [qv, selectedModule]); // Both are stable/primitives
```

**❌ Bad Pattern:**
```typescript
const modulesCache = useMemo(() => {
  return new Map(modules.map(m => [m.id, m]));
}, [modules]);

useEffect(() => {
  // BAD: cache object changes identity, causing loop
  qv.call('list_modules', {});
}, [qv, modulesCache]); // modulesCache is a new object each render
```

**❌ Bad Pattern:**
```typescript
useEffect(() => {
  // BAD: This effect both reads and writes selectedModule
  if (modules.length > 0 && !selectedModule) {
    setSelectedModule(modules[0].id); // This triggers the effect again!
  }
}, [qv, modules, selectedModule]); // Creates a loop
```

### Memoization Guidelines

- **Do** use `useMemo` for derived data that is expensive to compute (e.g., sorted lists, filtered arrays).
- **Do NOT** put memoized values into effect dependency arrays if those effects trigger RPC calls.
- **Do** use memoized values only for rendering (e.g., `sortedModules.map(...)`).
- **Do** keep effect dependencies limited to:
  - Stable client references (`qv`)
  - Primitive values (strings, numbers, booleans)
  - Stable function references (from `useCallback`)

---

## Call Count Expectations

### General Pattern for "List" RPCs

For any component that displays a list of items (structures, calculations, modules, sections, parameters), the expected pattern is:

1. **Initial Load**: One RPC call on mount (via `useEffect` with stable dependencies).
2. **User-Driven Updates**: RPC calls only triggered by explicit user actions (dropdown changes, button clicks, search submissions).
3. **No Polling**: No automatic refresh loops or polling intervals (except for specific cases like job status, which is documented separately).

### QEParameterBrowserPanel Call Counts

The QE Parameter Browser (`QEParameterBrowserPanel.tsx`) is a reference implementation of the correct pattern.

#### On Mounting the Resources / QE Parameter Browser Tab

- **Exactly one** `list_qe_parameter_metadata` call with `operation: "list_modules"`.
- No other RPC calls should occur.

#### When User Selects a Module

- **One** `list_qe_parameter_metadata` call with `operation: "list_sections"` and `module: <selected_module>`.
- This happens in `handleModuleChange`, which is called from the dropdown's `onChange` handler.

#### When User Selects a Section

- **One** `list_qe_parameter_metadata` call with `operation: "list_parameters"`, `module: <selected_module>`, and `section: <selected_section>`.
- This happens in `handleSectionChange`, which is called from the dropdown's `onChange` handler.

#### Search Operations

- **Only** triggers a `list_qe_parameter_metadata` call when explicitly invoked:
  - User clicks the search button, OR
  - User presses Enter in the search input.
- **No** RPC calls on every keystroke.
- The search input's `onChange` only updates local state (`searchQuery`).

#### Auto-Selection on Mount

The component may auto-select the first module and first section on initial load. This is implemented as a **controlled chain** within event handlers, not as a reactive effect:

```typescript
// In the modules loading effect:
if (moduleList.length > 0) {
  const firstModule = moduleList[0];
  await handleModuleChange(firstModule.id, { autoSelectSection: true });
}

// In handleModuleChange:
if (autoSelectSection && sectionList.length > 0) {
  const firstSection = sectionList[0];
  await handleSectionChange(firstSection.id, { autoLoadParameters: true });
}
```

This is safe because:
- It's a one-time chain triggered by the initial modules load.
- It uses explicit options (`autoSelectSection`, `autoLoadParameters`) rather than reactive state dependencies.
- It does not create a loop because the handlers are stable and the chain completes once.

### No Polling or Repeated Effects

**Critical**: The QE Parameter Browser does **not** have any polling or repeated effects beyond the initial modules load. If you see repeated `list_qe_parameter_metadata` calls in the daemon logs without user interaction, that is a bug.

Common causes:
1. An effect depends on a state value that is updated inside that effect.
2. The `qv` client reference is not stable (should not happen with current `useQVClient` implementation).
3. A memoized value (e.g., `useMemo` result) is in an effect dependency array.

---

## QE Parameter Browser Specific Behavior

### RPC Endpoint

The QE Parameter Browser uses a single RPC endpoint with different operations:

- **RPC**: `list_qe_parameter_metadata`
- **Operations**:
  - `"list_modules"` - Returns all supported QE modules (pw, ph, cp, etc.)
  - `"list_sections"` - Returns sections (namelists/cards) for a given module
  - `"list_parameters"` - Returns parameters for a given (module, section) pair
  - `"search"` - (Optional) Performs a search across parameters

### Component Structure

**State Management:**
- Separate state for modules, sections, parameters (each with loading/error states).
- No cache objects or derived maps in state.
- Selection state (`selectedModule`, `selectedSection`) is primitive strings.

**Event Handlers:**
- `handleModuleChange` - Loads sections for a module, optionally auto-selects first section.
- `handleSectionChange` - Loads parameters for a section, optionally auto-loads parameters.
- `handleSearch` - Explicit search trigger (button/Enter only).

**Effects:**
- **Only one effect**: Loads modules on mount, depends on `[qv, handleModuleChange]`.
- All other data loading is event-driven via handlers.

### Parameter Table UX

The parameter list table has been optimized for compact, readable display:

- **Compact by default**: Non-selected rows show single-line text with ellipsis for overflow.
- **Expanded on selection**: Selected rows allow text wrapping to show full content.
- **Fixed layout**: Table uses `table-layout: fixed` with percentage-based column widths.
- **User-resizable columns**: Column widths can be adjusted by dragging header splitters.
- **Vertical scroll only**: Container has `overflow-x: hidden` to prevent horizontal scrolling.

See `QEParameterBrowserPanel.tsx` and `QEParameterBrowserPanel.css` for implementation details.

---

## Common Pitfalls and How to Avoid Them

### Pitfall 1: Effect Depends on Cache Object

**Symptom**: Infinite loop of RPC calls.

**Example:**
```typescript
const sectionsCache = useMemo(() => {
  return new Map(sections.map(s => [s.id, s]));
}, [sections]);

useEffect(() => {
  // BAD: sectionsCache is a new Map object each time sections changes
  if (sectionsCache.has('CONTROL')) {
    // ...
  }
}, [qv, sectionsCache]);
```

**Fix**: Don't put cache objects in effect dependencies. Use them only for rendering or in event handlers.

### Pitfall 2: Effect Both Reads and Writes State

**Symptom**: Effect runs, updates state, which triggers effect again.

**Example:**
```typescript
useEffect(() => {
  if (modules.length > 0 && !selectedModule) {
    setSelectedModule(modules[0].id); // Triggers effect again!
  }
}, [qv, modules, selectedModule]);
```

**Fix**: Use event handlers for auto-selection, or use a ref to track if auto-selection has already happened.

### Pitfall 3: Unstable Callback References

**Symptom**: Effect re-runs because callback reference changes.

**Example:**
```typescript
const handleLoad = () => {
  qv.call('list_modules', {});
};

useEffect(() => {
  handleLoad();
}, [qv, handleLoad]); // handleLoad is recreated each render
```

**Fix**: Use `useCallback` to memoize the handler:
```typescript
const handleLoad = useCallback(() => {
  qv.call('list_modules', {});
}, [qv]);
```

### Pitfall 4: Search Triggers on Every Keystroke

**Symptom**: RPC calls flood the daemon as user types.

**Example:**
```typescript
useEffect(() => {
  if (searchQuery.trim()) {
    qv.call('search', { query: searchQuery }); // BAD: runs on every keystroke
  }
}, [qv, searchQuery]);
```

**Fix**: Only trigger search on explicit user action (button click, Enter key):
```typescript
const handleSearch = useCallback(async () => {
  if (!searchQuery.trim()) return;
  await qv.call('search', { query: searchQuery.trim() });
}, [qv, searchQuery]);

// In JSX:
<input onChange={(e) => setSearchQuery(e.target.value)} />
<button onClick={handleSearch}>Search</button>
```

---

## Developer Checklist

When working on components that use "list" RPCs, verify:

- [ ] `useQVClient()` returns a stable client reference; effects do not re-run due to client identity changes.
- [ ] "List" RPC effects depend only on stable, primitive inputs (ids / filter values), not on caches or derived objects.
- [ ] Each view that uses `list_*` RPCs has clearly defined expected call counts on mount and per user action.
- [ ] No `useEffect` both depends on and mutates the same state in a way that would cause a loop.
- [ ] QE Parameter Browser does not trigger repeated `list_qe_parameter_metadata` calls without user interaction.
- [ ] Search operations only trigger RPC calls on explicit user action (button/Enter), not on every keystroke.
- [ ] Memoized values (`useMemo`) are used only for rendering, not in effect dependency arrays.
- [ ] Event handlers that trigger RPC calls are memoized with `useCallback` to maintain stable references.

---

## Cross-References

- **GUI Architecture**: See `docs/GUI_ARCHITECTURE.md` for overall GUI structure and `useQVClient` hook overview.
- **Daemon API**: See `docs/DAEMON_API_REFERENCE.md` for RPC endpoint documentation.
- **Registry / ResourceIndex**: See `docs/ARCHITECTURE.md` (to be written) for details on how registry rebuilds and caching are handled. The same philosophy applies: explicit rebuilds on project load or user-triggered refresh, but no automatic loops on read.

---

## Code References

For implementation examples, see:

- **Stable Client Pattern**: `gui/src/hooks/useQVClient.ts` (lines 308-336)
- **QE Parameter Browser**: `gui/src/components/panels/QEParameterBrowserPanel.tsx`
  - See comments in the file for expected call counts and effect dependencies.

---

*Last updated: 2024 (after QE Parameter Browser refactoring to eliminate infinite loops)*
