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
| 3D Rendering | react-three-fiber + Three.js | Structure visualization |
| 2D Charts | recharts | Analysis plots (SCF, DOS, bands) |

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
│   ├── main.ts              # Main process - daemon, IPC, file dialogs
│   ├── preload.ts           # Context bridge - safe API exposure
│   └── electron-env.d.ts    # Electron type declarations
│
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Root component with view routing
│   ├── App.css              # App-specific styles
│   ├── index.css            # Global styles, design tokens
│   │
│   ├── components/
│   │   ├── index.ts         # Re-exports all components
│   │   ├── layout/
│   │   │   ├── AppShell.tsx     # Main layout container
│   │   │   └── Sidebar.tsx      # Navigation, view tabs
│   │   ├── panels/
│   │   │   ├── ResultPanel.tsx  # JSON result viewer
│   │   │   ├── DebugPanel.tsx   # Daemon logs + DebugView
│   │   │   ├── ProjectSummaryPanel.tsx   # Welcome + project view
│   │   │   ├── StructureListPanel.tsx    # Structure list + detail
│   │   │   ├── WorkflowListPanel.tsx     # Workflow list + detail
│   │   │   ├── StructureViewer3D.tsx     # 3D ball-and-stick viewer
│   │   │   ├── AnalysisPanel.tsx         # SCF/DOS/Bands charts
│   │   │   ├── JobsPanel.tsx             # Job list + detail + logs
│   │   │   └── DaemonErrorBanner.tsx     # Startup error display
│   │   └── dialogs/
│   │       ├── Modal.tsx                 # Base modal component
│   │       ├── CreateProjectDialog.tsx   # New project creation
│   │       ├── ImportStructureDialog.tsx # Structure import
│   │       └── CreateWorkflowDialog.tsx  # Workflow from template
│   │
│   ├── hooks/
│   │   ├── index.ts
│   │   ├── useQVClient.ts   # Daemon communication hook
│   │   └── useJobs.ts       # Job polling hooks
│   │
│   └── types/
│       ├── index.ts
│       └── qv.ts            # QVCommandMap + all RPC types
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
┌────────────────────────────────────────────────────────────────────────────┐
│                                  AppShell                                   │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────┐   │
│  │   Sidebar    │  │                  Main Content                     │   │
│  │              │  │                                                   │   │
│  │  - Logo      │  │  View: Summary    ┌───────────────────────────┐  │   │
│  │  - Path      │  │                   │   ProjectSummaryPanel     │  │   │
│  │  - Browse    │  │                   │   or Welcome Card         │  │   │
│  │  - Load      │  │                   └───────────────────────────┘  │   │
│  │  - Create    │  │                                                   │   │
│  │              │  │  View: Structures ┌──────────┬────────────────┐  │   │
│  │  ─ Tabs ─    │  │                   │ List     │ Detail + 3D    │  │   │
│  │  Summary     │  │                   │ Panel    │ Viewer         │  │   │
│  │  Structures  │  │                   └──────────┴────────────────┘  │   │
│  │  Workflows   │  │                                                   │   │
│  │  Jobs [2]    │  │  View: Workflows  ┌──────────┬────────────────┐  │   │
│  │  Analysis    │  │                   │ List     │ Detail         │  │   │
│  │  Debug       │  │                   │ Panel    │ + Run button   │  │   │
│  └──────────────┘  │                   └──────────┴────────────────┘  │   │
│                    │                                                   │   │
│                    │  View: Jobs       ┌──────────┬────────────────┐  │   │
│                    │                   │ Job List │ Detail + Logs  │  │   │
│                    │                   │ + Status │ + Cancel       │  │   │
│                    │                   └──────────┴────────────────┘  │   │
│                    │                                                   │   │
│                    │  View: Analysis   ┌───────────────────────────┐  │   │
│                    │                   │ SCF/DOS/Bands Charts      │  │   │
│                    │                   └───────────────────────────┘  │   │
│                    │                                                   │   │
│                    │  View: Debug      ┌───────────────────────────┐  │   │
│                    │                   │ Ping + Status + Full Logs │  │   │
│                    │                   └───────────────────────────┘  │   │
│                    └──────────────────────────────────────────────────┘   │
│                    ┌──────────────────────────────────────────────────┐   │
│                    │                  DebugPanel (Footer)              │   │
│                    │                  (Compact Daemon Logs)            │   │
│                    └──────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
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
qv.state.daemonStatus  // DaemonStatus | null

// System
qv.ping()              // Test daemon connection
qv.openDirectoryDialog() // Native folder picker

// Project operations
qv.getProjectSummary(projectRoot)
qv.listStructures(projectRoot)
qv.listWorkflows(projectRoot)

// Generic call (fully typed via QVCommandMap)
qv.call('command_name', payload)  // Returns Promise<QVResponse<ResultType>>

// Visualization data
qv.call('get_structure_vis', { project_root, selector, supercell?, repeat_boundary? })
qv.call('get_scf_convergence', { project_root, workflow, step })
qv.call('get_dos_data', { project_root, workflow, step? })
qv.call('get_band_structure_data', { project_root, workflow, step? })

// Project creation
qv.call('create_project', { target_dir, name?, template? })
qv.call('import_structure', { project_root, source_file, name? })

// Workflow creation
qv.call('list_workflow_templates', {})
qv.call('create_workflow', { project_root, name, structure?, template? })

// Jobs
qv.call('run_workflow', { project_root, workflow, strict?, verbose? })
qv.call('run_step', { project_root, workflow, step, verbose? })
qv.call('get_job_status', { job_id })
qv.call('get_job_logs', { job_id, tail_lines?, offset? })
qv.call('list_jobs', { status?, job_type?, project_root?, limit? })
qv.call('job_counts', {})
qv.call('cancel_job', { job_id })
```

#### `useQVLogs`

Subscribe to daemon log output.

```typescript
const logs = useQVLogs(maxLines);  // string[]
```

#### `useJobs`

Poll and manage job list.

```typescript
const {
  jobs,          // JobSummary[] - List of jobs
  counts,        // JobCounts | null - Counts by status
  isLoading,     // boolean
  error,         // string | null
  refresh,       // () => Promise<void> - Manual refresh
  isPolling,     // boolean
  startPolling,  // () => void
  stopPolling,   // () => void
} = useJobs({
  pollInterval: 3000,     // Poll every 3s (default)
  projectRoot?: string,   // Filter by project
  status?: JobStatus,     // Filter by status
  limit: 50,              // Max jobs to fetch
});
```

#### `useJobDetail`

Poll single job with logs.

```typescript
const {
  job,          // JobInfo | null - Full job details
  logs,         // JobLogs | null - Output logs
  isLoading,    // boolean
  error,        // string | null
  refresh,      // () => Promise<void>
  refreshLogs,  // () => Promise<void>
  cancelJob,    // () => Promise<boolean>
} = useJobDetail({
  jobId: 'abc-123',
  pollInterval: 2000,    // Poll while running
  autoStart: true,
});
```

#### `useDaemonStatus`

Subscribe to daemon status changes.

```typescript
const status = useDaemonStatus();  // DaemonStatus | null
// status.isConnected, status.pythonPath, status.startupError, etc.
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
  
  // Get daemon status
  getDaemonStatus: () => Promise<DaemonStatus>;
  
  // Subscribe to daemon status changes
  onDaemonStatus: (callback: (status: DaemonStatus) => void) => () => void;
  
  // Subscribe to main process messages
  onMainMessage: (callback: (data: unknown) => void) => () => void;
  
  // Native file dialogs
  openDirectory: () => Promise<string | null>;
  openFile: (options?: {
    title?: string;
    filters?: { name: string; extensions: string[] }[];
  }) => Promise<string | null>;
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

### Adding a Dialog

1. Create dialog using the Modal component:
   ```typescript
   // src/components/dialogs/MyDialog.tsx
   import { Modal } from './Modal';
   
   export function MyDialog({ isOpen, onClose, onSuccess }) {
     const [formData, setFormData] = useState({});
     const [isSubmitting, setIsSubmitting] = useState(false);
     
     const handleSubmit = async () => {
       setIsSubmitting(true);
       const response = await qv.call('my_command', formData);
       if (response.ok) {
         onSuccess(response.data);
         onClose();
       }
       setIsSubmitting(false);
     };
     
     return (
       <Modal
         isOpen={isOpen}
         onClose={onClose}
         title="My Dialog"
         footer={<>
           <button onClick={onClose}>Cancel</button>
           <button onClick={handleSubmit}>Submit</button>
         </>}
       >
         {/* Form content */}
       </Modal>
     );
   }
   ```

2. Export from `src/components/dialogs/index.ts`

3. Add state in App.tsx:
   ```typescript
   const [showMyDialog, setShowMyDialog] = useState(false);
   
   // In render:
   <MyDialog
     isOpen={showMyDialog}
     onClose={() => setShowMyDialog(false)}
     onSuccess={handleSuccess}
   />
   ```

### 3D Visualization with react-three-fiber

The `StructureViewer3D` component uses react-three-fiber for WebGL rendering:

```typescript
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';

// Key patterns:
// 1. Get pure data from daemon (no matplotlib)
// 2. Render atoms as spheres, bonds as cylinders
// 3. Use OrbitControls for camera manipulation

<Canvas camera={{ position: [10, 10, 10], fov: 50 }}>
  <ambientLight intensity={0.5} />
  <directionalLight position={[10, 10, 5]} />
  
  {atoms.map((atom, i) => (
    <mesh key={i} position={atom.cart_coords}>
      <sphereGeometry args={[atom.radius, 32, 32]} />
      <meshStandardMaterial color={atom.color} />
    </mesh>
  ))}
  
  <OrbitControls />
</Canvas>
```

### 2D Charts with Recharts

The `AnalysisPanel` uses Recharts for scientific plots:

```typescript
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer } from 'recharts';

<ResponsiveContainer width="100%" height={300}>
  <LineChart data={scfData.iterations}>
    <XAxis dataKey="iteration" />
    <YAxis yAxisId="left" label="Energy (Ry)" />
    <YAxis yAxisId="right" orientation="right" label="Accuracy" />
    <Line yAxisId="left" dataKey="total_energy_ry" stroke="blue" />
    <Line yAxisId="right" dataKey="scf_accuracy_ry" stroke="green" />
  </LineChart>
</ResponsiveContainer>
```

## Known Issues

1. **Autofill Warnings**: Chrome DevTools shows Autofill.enable errors - can be ignored
2. **Python Warning**: "found in sys.modules after import" - harmless warning
3. **Timeout**: Long operations (>60s) will timeout - adjust `REQUEST_TIMEOUT_MS` if needed
4. **Job Logs Polling**: Logs are polled every 2s (not streamed) - may have slight delay
5. **Running Jobs**: Cannot be cancelled (ThreadPoolExecutor limitation in Python)

## Feature Status

### Implemented ✓

- [x] Project browser (open, create, load)
- [x] 3D structure viewer (react-three-fiber + Three.js)
  - Ball-and-stick rendering
  - Orbit controls
  - Unit cell display
  - Bond detection
  - Element colors
- [x] Structure import (CIF, XSF, QE input, etc.)
- [x] Workflow management (list, detail, run)
- [x] Workflow creation from templates
- [x] Analysis plots (Recharts)
  - SCF convergence (energy + accuracy)
  - DOS plot
  - Band structure with k-path labels
- [x] Auto-fetch on view change
- [x] Empty states with helpful CTAs
- [x] Native file dialogs
- [x] Job management (Jobs view)
  - Job list with status badges
  - Job detail panel
  - Live log viewing (polled)
  - Cancel pending jobs
  - Running jobs indicator in sidebar
  - Job notifications on submission

### Planned

- [ ] Real-time log streaming (websocket or SSE)
- [ ] Step editor (modify parameters)
- [ ] Workflow builder UI (drag-and-drop)
- [ ] Multiple project tabs
- [ ] Theme switching (light/dark)
- [ ] Supercell control in 3D viewer

