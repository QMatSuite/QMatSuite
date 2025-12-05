# QuantumVITAS GUI Architecture

## Overview

The QuantumVITAS GUI is a desktop application built with Electron + React + TypeScript. It communicates with the Python backend via a stdio-based JSON-RPC daemon.

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Desktop Framework | Electron 39.x | Cross-platform desktop app |
| UI Framework | React 18.x | Component-based UI |
| Language | TypeScript 5.x | Type safety |
| Build Tool | electron-vite | Fast HMR, optimized builds |
| Styling | CSS Variables | Theming, design tokens |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RENDERER PROCESS                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                         React App                            │   │
│  │                                                              │   │
│  │  ┌──────────────┐   ┌─────────────┐   ┌────────────────┐   │   │
│  │  │  Sidebar     │   │ ResultPanel │   │  DebugPanel    │   │   │
│  │  │  - Actions   │   │ - JSON View │   │  - Daemon Logs │   │   │
│  │  │  - Path Input│   │ - Status    │   │                │   │   │
│  │  └──────────────┘   └─────────────┘   └────────────────┘   │   │
│  │                            │                                 │   │
│  │                     useQVClient Hook                        │   │
│  │                            │                                 │   │
│  └────────────────────────────┼─────────────────────────────────┘   │
│                               │                                      │
│                        window.qv.request()                          │
│                               │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│                         PRELOAD (contextBridge)                      │
│                               │                                      │
│                      ipcRenderer.invoke()                           │
│                               │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│                         MAIN PROCESS                                 │
│                               │                                      │
│                   ipcMain.handle('qv-request')                      │
│                               │                                      │
│              ┌────────────────┴────────────────┐                    │
│              │         Request Map             │                    │
│              │    id → {resolve, reject}       │                    │
│              └────────────────┬────────────────┘                    │
│                               │                                      │
│                    stdin.write(JSON + '\n')                         │
│                               │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│                        PYTHON DAEMON                                 │
│                               │                                      │
│              ┌────────────────┴────────────────┐                    │
│              │          QVDaemon               │                    │
│              │     - Parse JSON request        │                    │
│              │     - Route to handler          │                    │
│              │     - Call QVService            │                    │
│              │     - Return JSON response      │                    │
│              └────────────────┬────────────────┘                    │
│                               │                                      │
│                          QVService                                   │
│                               │                                      │
│                    Core Python Backend                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
gui/
├── electron/
│   ├── main.ts              # Main process - daemon spawning, IPC
│   ├── preload.ts           # Context bridge - safe API exposure
│   └── electron-env.d.ts    # Electron type declarations
│
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Root application component
│   ├── App.css              # App-specific styles
│   ├── index.css            # Global styles, design tokens
│   │
│   ├── components/
│   │   ├── index.ts         # Re-exports all components
│   │   ├── layout/
│   │   │   ├── index.ts
│   │   │   ├── AppShell.tsx     # Main layout container
│   │   │   ├── AppShell.css
│   │   │   ├── Sidebar.tsx      # Navigation & actions
│   │   │   └── Sidebar.css
│   │   └── panels/
│   │       ├── index.ts
│   │       ├── ResultPanel.tsx  # JSON result viewer
│   │       ├── ResultPanel.css
│   │       ├── DebugPanel.tsx   # Daemon log viewer
│   │       └── DebugPanel.css
│   │
│   ├── hooks/
│   │   ├── index.ts
│   │   └── useQVClient.ts   # Daemon communication hook
│   │
│   └── types/
│       ├── index.ts
│       └── qv.ts            # RPC types matching daemon protocol
│
├── public/                  # Static assets
├── dist/                    # Built renderer (generated)
├── dist-electron/           # Built main/preload (generated)
├── release/                 # Packaged app (generated)
│
├── index.html               # HTML template
├── package.json             # Dependencies
├── tsconfig.json            # TypeScript config (renderer)
├── tsconfig.node.json       # TypeScript config (node/electron)
├── vite.config.ts           # Vite configuration
└── electron-builder.json5   # Packaging configuration
```

## Component Architecture

### Layout Components

```
┌────────────────────────────────────────────────────────────────┐
│                         AppShell                               │
│  ┌──────────────┐  ┌───────────────────────────────────────┐  │
│  │   Sidebar    │  │              Main Content              │  │
│  │              │  │                                        │  │
│  │  - Header    │  │  ┌──────────────────────────────────┐ │  │
│  │  - Path      │  │  │         ResultPanel              │ │  │
│  │  - Actions   │  │  │                                  │ │  │
│  │  - Status    │  │  │         (JSON Viewer)            │ │  │
│  │              │  │  │                                  │ │  │
│  │              │  │  └──────────────────────────────────┘ │  │
│  │              │  │                                        │  │
│  │              │  └───────────────────────────────────────┘  │
│  │              │  ┌───────────────────────────────────────┐  │
│  │              │  │            DebugPanel                 │  │
│  │              │  │          (Daemon Logs)                │  │
│  └──────────────┘  └───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### Hooks

#### `useQVClient`

The main hook for daemon communication.

```typescript
const qv = useQVClient();

// State
qv.state.isConnected   // boolean - daemon connection status
qv.state.isLoading     // boolean - request in progress
qv.state.lastError     // string | null - last error message

// System
qv.ping()              // Test daemon connection

// Project
qv.getProjectSummary(projectRoot)
qv.listStructures(projectRoot)
qv.listWorkflows(projectRoot)

// Visualization
qv.getStructureVis(payload)
qv.getScfConvergence(payload)
qv.getDosData(payload)
qv.getBandStructureData(payload)

// Jobs
qv.runWorkflow(payload)
qv.runStep(payload)
qv.getJobStatus(jobId)
qv.listJobs(payload?)
qv.cancelJob(jobId)

// Raw request
qv.request<T>(type, payload)
```

#### `useQVLogs`

Subscribe to daemon log output.

```typescript
const logs = useQVLogs(maxLines);  // string[]
```

## IPC Communication

### Preload API (`window.qv`)

```typescript
interface QVApi {
  // Send request to daemon
  request: <T>(type: string, payload?: object) => Promise<QVResponse<T>>;
  
  // Subscribe to daemon logs (stderr)
  onLog: (callback: (message: string) => void) => () => void;
  
  // Check daemon connection
  isConnected: () => Promise<boolean>;
  
  // Subscribe to main process messages
  onMainMessage: (callback: (data: unknown) => void) => () => void;
}
```

### Request/Response Format

**Request (sent to daemon):**
```json
{
  "id": "req-1733370000-1",
  "type": "list_structures",
  "payload": {
    "project_root": "/path/to/project"
  }
}
```

**Response (from daemon):**
```json
{
  "id": "req-1733370000-1",
  "ok": true,
  "data": {
    "structures": [...],
    "count": 2
  }
}
```

**Error Response:**
```json
{
  "id": "req-1733370000-1",
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "Project not found: /invalid/path"
  }
}
```

## Daemon Management

### Spawning

The main process spawns the Python daemon on startup:

```typescript
// Find Python in project .venv
const pythonPath = findPythonPath();  // ../..venv/bin/python

// Spawn daemon
daemonProcess = spawn(pythonPath, ['-m', 'quantumvitas.daemon.server'], {
  cwd: projectRoot,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
  stdio: ['pipe', 'pipe', 'pipe'],
});
```

### Communication

- **stdin**: JSON requests (one per line)
- **stdout**: JSON responses (one per line)
- **stderr**: Log messages (forwarded to DebugPanel)

### Request Tracking

```typescript
const pendingRequests = new Map<string, {
  resolve: (response: QVResponse) => void;
  reject: (error: Error) => void;
  timeoutId: NodeJS.Timeout;
}>();
```

### Shutdown

1. Send `shutdown` command to daemon
2. Wait 2 seconds
3. SIGTERM if still running

## Design System

### CSS Variables

```css
:root {
  /* Typography */
  --font-sans: 'IBM Plex Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', 'Consolas', monospace;
  
  /* Colors - Midnight Blue Theme */
  --color-primary: #6366f1;
  --color-success: #10b981;
  --color-error: #ef4444;
  
  /* Backgrounds */
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-sidebar: #0f172a;
  --bg-card: #1e293b;
  
  /* Text */
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
  --text-muted: #64748b;
  
  /* JSON Syntax */
  --json-key: #93c5fd;
  --json-string: #86efac;
  --json-number: #fcd34d;
}
```

### Typography

- **Display/Headings**: IBM Plex Sans (weights: 600, 700)
- **Body**: IBM Plex Sans (weights: 400, 500)
- **Code/Mono**: IBM Plex Mono (weights: 400, 500, 600)

## Development

### Commands

```bash
# Install dependencies
npm install

# Development mode (hot reload, DevTools open)
npm run dev

# Production build
npm run build

# Type checking only
tsc --noEmit
```

### Hot Module Replacement

Vite provides HMR for React components. Changes to:
- `.tsx` files: Hot reload
- `.css` files: Style injection
- `electron/main.ts`: Requires restart
- `electron/preload.ts`: Requires restart

### Debugging

1. **DevTools**: Open automatically in dev mode
2. **DebugPanel**: Shows daemon stderr in UI
3. **Console**: `[main]` prefix = Electron main, `[daemon]` prefix = Python

## Extending the GUI

### Adding a New Daemon Command

1. **Types** (`src/types/qv.ts`):
   ```typescript
   export type QVCommandType = ... | 'my_new_command';
   
   export interface MyNewPayload { ... }
   export interface MyNewData { ... }
   ```

2. **Hook** (`src/hooks/useQVClient.ts`):
   ```typescript
   const myNewCommand = useCallback(
     (payload: MyNewPayload) =>
       request<MyNewData>('my_new_command', payload),
     [request]
   );
   ```

3. **Component**: Use the hook method

### Adding a New Panel

1. Create `src/components/panels/MyPanel.tsx`:
   ```typescript
   export function MyPanel({ data }: MyPanelProps) {
     return <div className="my-panel">...</div>;
   }
   ```

2. Export from `src/components/panels/index.ts`

3. Add CSS in `MyPanel.css`

4. Import and use in `App.tsx`

## Known Issues

1. **Autofill Warnings**: Chrome DevTools shows Autofill.enable errors - can be ignored
2. **Python Warning**: "found in sys.modules after import" - harmless warning
3. **Timeout**: Long operations (>60s) will timeout - adjust `REQUEST_TIMEOUT_MS` if needed

## Future Enhancements

- [ ] 3D structure viewer (Three.js)
- [ ] Band structure/DOS plots (Recharts or similar)
- [ ] Workflow builder UI
- [ ] Job progress streaming
- [ ] Multiple project support
- [ ] Theme switching (light/dark)

