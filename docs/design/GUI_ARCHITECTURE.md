# QMatSuite GUI Architecture

## Overview

The QMatSuite GUI is a desktop application built with Electron + React + TypeScript. It communicates with the Python backend via a stdio-based JSON-RPC daemon.

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
│  │                     useQMSClient Hook                        │   │
│  │                            │                                 │   │
│  └────────────────────────────┼─────────────────────────────────┘   │
│                               │                                      │
│                        window.qms.request()                          │
│                               │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│                         PRELOAD (contextBridge)                      │
│                               │                                      │
│                      ipcRenderer.invoke()                           │
│                               │                                      │
├───────────────────────────────┼──────────────────────────────────────┤
│                         MAIN PROCESS                                 │
│                               │                                      │
│                   ipcMain.handle('qms-request')                      │
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
│              │          QMSDaemon               │                    │
│              │     - Parse JSON request        │                    │
│              │     - Route to handler          │                    │
│              │     - Call QMSService            │                    │
│              │     - Return JSON response      │                    │
│              └────────────────┬────────────────┘                    │
│                               │                                      │
│                          QMSService                                   │
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
│   │   │   ├── AppShell.tsx           # Main layout container
│   │   │   ├── Sidebar.tsx            # Navigation, view tabs
│   │   │   ├── StatusBar.tsx          # Bottom status bar
│   │   │   ├── ResizablePane.tsx      # Horizontal draggable resize (width)
│   │   │   └── VerticalResizablePane.tsx # Vertical draggable resize (height)
│   │   ├── panels/
│   │   │   ├── ResultPanel.tsx  # JSON result viewer
│   │   │   ├── DebugPanel.tsx   # Daemon logs + DebugView
│   │   │   ├── ProjectSummaryPanel.tsx   # Welcome + project view
│   │   │   ├── StructureListPanel.tsx    # Structure list + detail
│   │   │   ├── CalculationListPanel.tsx     # Calculation list + detail
│   │   │   ├── StructureViewer3D.tsx     # 3D ball-and-stick viewer
│   │   │   ├── AnalysisPanel.tsx         # SCF/DOS/Bands charts with auto-selection
│   │   │                              # - Auto-detects analysis type from calculation
│   │   │                              # - Energy range controls for band plots
│   │   │                              # - Automatic loading when enabled
│   │   │   ├── JobsPanel.tsx             # Job list + detail + logs
│   │   ├── SettingsPanel.tsx        # QE detection + theme + auto-analysis settings
│   │   └── DaemonErrorBanner.tsx     # Startup error display
│   │   └── dialogs/
│   │       ├── Modal.tsx                 # Base modal component
│   │       ├── CreateProjectDialog.tsx   # New project creation
│   │       ├── ImportStructureDialog.tsx # Structure import
│   │       └── CreateWorkflowDialog.tsx  # Calculation from template
│   │
│   ├── hooks/
│   │   ├── index.ts
│   │   ├── useQMSClient.ts   # Daemon communication hook
│   │   └── useJobs.ts       # Job polling hooks
│   │
│   └── types/
│       ├── index.ts
│       └── qms.ts            # QMSCommandMap + all RPC types
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
│  │  Calculations   │  │                                                   │   │
│  │  Jobs [2]    │  │  View: Calculations  ┌──────────┬────────────────┐  │   │
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

#### `useQMSClient`

The main hook for daemon communication.

```typescript
const qms = useQMSClient();

// State
qms.state.isConnected   // boolean - daemon connection status
qms.state.isLoading     // boolean - request in progress
qms.state.lastError     // string | null - last error message
qms.state.daemonStatus  // DaemonStatus | null

// System
qms.ping()              // Test daemon connection
qms.openDirectoryDialog() // Native folder picker
window.qms.revealPath(path) // Reveal file/folder in Finder/Explorer

// Project operations
qms.getProjectSummary(projectRoot)
qms.listStructures(projectRoot)
qms.listWorkflows(projectRoot)

// Generic call (fully typed via QMSCommandMap)
qms.call('command_name', payload)  // Returns Promise<QMSResponse<ResultType>>

// Visualization data
qms.call('get_structure_vis', { project_root, selector, supercell?, repeat_boundary? })
qms.call('get_scf_convergence', { project_root, calculation, step })
qms.call('get_dos_data', { project_root, calculation, step? })
qms.call('get_band_structure_data', { project_root, calculation, step? })

// Project creation
qms.call('create_project', { target_dir, name?, template? })
qms.call('import_structure', { project_root, source_file, name? })

// Calculation creation
qms.call('list_calculation_templates', {})
qms.call('create_calculation', { project_root, name, structure?, template? })

// Jobs
qms.call('run_calculation', { project_root, calculation, strict?, verbose? })
qms.call('run_step', { project_root, calculation, step, verbose? })
qms.call('get_job_status', { job_id })
qms.call('get_job_logs', { job_id, tail_lines?, offset? })
qms.call('list_jobs', { status?, job_type?, project_root?, limit? })
qms.call('job_counts', {})
qms.call('cancel_job', { job_id })
```

#### `useQMSLogs`

Subscribe to daemon log output.

```typescript
const logs = useQMSLogs(maxLines);  // string[]
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

### Preload API (`window.qms`)

```typescript
interface QMSApi {
  // Send request to daemon
  request: <T>(type: string, payload?: object) => Promise<QMSResponse<T>>;
  
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
  
  // Reveal in file manager
  revealPath: (targetPath: string) => Promise<boolean>;
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
daemonProcess = spawn(pythonPath, ['-m', 'qmatsuite.daemon.server'], {
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
  resolve: (response: QMSResponse) => void;
  reject: (error: Error) => void;
  timeoutId: NodeJS.Timeout;
}>();
```

### Shutdown

1. Send `shutdown` command to daemon
2. Wait 2 seconds
3. SIGTERM if still running

## Design System

### CSS Variables and Theming

The GUI supports both dark (default) and light themes using CSS custom properties. Theme is controlled via `data-theme` attribute on the document root.

**Dark Theme** (default):
```css
:root {
  /* Typography */
  --font-sans: 'Inter', 'SF Pro Display', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', monospace;
  
  /* Colors - Indigo/Slate Theme */
  --color-primary: #6366f1;
  --color-success: #10b981;
  --color-error: #ef4444;
  
  /* Backgrounds */
  --bg-app: #0c0f1a;
  --bg-primary: #111827;
  --bg-secondary: #1f2937;
  --bg-sidebar: #0f1525;
  --bg-card: #1f2937;
  
  /* Text */
  --text-primary: #f9fafb;
  --text-secondary: #d1d5db;
  --text-muted: #6b7280;
}
```

**Light Theme** (VS Code-inspired):
```css
[data-theme="light"] {
  /* Backgrounds */
  --bg-app: #f3f3f3;
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-sidebar: #f8f8f8;
  --bg-card: #ffffff;
  
  /* Text */
  --text-primary: #1f1f1f;
  --text-secondary: #424242;
  --text-muted: #9e9e9e;
  
  /* Primary color adjusted for light theme */
  --color-primary: #0066b8;
}
```

Theme switching is available in Settings → Appearance section.

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

1. **Types** (`src/types/qms.ts`):
   ```typescript
   export type QMSCommandType = ... | 'my_new_command';
   
   export interface MyNewPayload { ... }
   export interface MyNewData { ... }
   ```

2. **Hook** (`src/hooks/useQMSClient.ts`):
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
       const response = await qms.call('my_command', formData);
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

## Design System

### CSS Custom Properties

All styling uses CSS variables defined in `gui/src/index.css`:

| Category | Examples |
|----------|----------|
| Typography | `--font-sans`, `--font-mono`, `--text-xs` to `--text-3xl` |
| Colors | `--color-primary`, `--color-success`, `--color-error`, `--color-warning` |
| Backgrounds | `--bg-app`, `--bg-primary`, `--bg-secondary`, `--bg-card` |
| Text | `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-muted` |
| Spacing | `--space-1` to `--space-16` (4px to 64px scale) |
| Radius | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl` |
| Shadows | `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-xl` |
| Transitions | `--transition-fast`, `--transition-normal`, `--transition-slow` |

### Layout Components

| Component | Purpose |
|-----------|---------|
| `AppShell` | Main layout with sidebar, content area, and status bar |
| `StatusBar` | Bottom bar showing project, QE status, running jobs |
| `ErrorBoundary` | Catches render errors with friendly fallback UI |

### Standard Panel Structure

All panels follow a consistent structure:

```
<div className="*-panel">
  <div className="panel-header">      <!-- bg-secondary, title + actions -->
  <div className="panel-content">     <!-- scrollable body -->
</div>
```

### Button Classes

Global CSS classes for buttons:

- `.btn` - Base button styles
- `.btn-primary` - Primary action (indigo)
- `.btn-secondary` - Secondary action (gray)
- `.btn-ghost` - Minimal styling
- `.btn-danger` - Destructive action (red)
- Size: `.btn-sm`, `.btn-lg`, `.btn-icon`

### Tooltips

CSS-only tooltips using `data-tooltip` attribute:

```html
<button data-tooltip="Description here">Click me</button>
<button data-tooltip="Below" data-tooltip-position="bottom">Hover</button>
```

## Feature Status

### Implemented ✓

- [x] Project browser (open, create, load, recent projects)
- [x] Demo project creation (one-click Si calculation)
- [x] 3D structure viewer (react-three-fiber + Three.js)
  - Ball-and-stick rendering
  - Orbit controls
  - Unit cell display
  - Bond detection
  - Element colors
  - Supercell visualization controls
  - Boundary atom repetition
  - Context-aware element legend (only shows present elements)
- [x] Structure import (CIF, XSF, QE input, etc.)
- [x] Calculation management (list, detail, run)
- [x] Calculation creation from templates
- [x] Calculation editing (reorder steps, change structure)
- [x] Step parameter editing (ecutwfc, smearing, etc.)
- [x] Add step to calculation (with type selection)
- [x] Pre-flight checks before job submission
- [x] Analysis plots (Recharts)
  - SCF convergence (energy + accuracy)
  - DOS plot
  - Band structure with k-path labels
- [x] Jobs → Analysis integration (View Analysis button)
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
- [x] Settings panel (QE detection, default paths)
- [x] Status bar (project, QE, jobs)
- [x] Error boundary with recovery
- [x] Comprehensive design system
- [x] Resizable panels
  - Daemon logs panel (draggable height)
  - Structures/Calculations list panels (draggable width)
  - Calculation/Step detail separator (draggable)
  - ResizablePane and VerticalResizablePane components
- [x] Drag-and-drop step reordering
- [x] Summary panel auto-refresh on structure/calculation changes
- [x] 3D viewer camera state preservation (zoom/rotation remembered during supercell changes)
- [x] Log file persistence
  - Logs saved to `.qms-daemon.log` in project directory
  - Persisted across sessions
  - setProject/readLogs IPC methods
- [x] Theme switching (light/dark)
  - VS Code-inspired light theme
  - Dark theme (default)
  - Theme toggle in Settings panel
  - Persisted in localStorage
- [x] Reveal in Finder/Explorer
  - OS-native file manager integration
  - `window.qms.revealPath(path)` API
  - Works on macOS (Finder), Windows (Explorer), Linux
- [x] Automatic analysis selection
  - Auto-detects analysis type based on calculation's last step
  - DOS step → DOS analysis
  - Bands step → Bands analysis
  - Otherwise → SCF analysis
- [x] Automatic analysis loading
  - Setting in Settings → Analysis section
  - When enabled, automatically loads analysis when selecting calculation
  - Default: enabled
- [x] Band structure plot controls
  - Energy range inputs update ylim dynamically
  - Real-time chart updates

### Planned

- [ ] Real-time log streaming (websocket or SSE)
- [ ] Calculation builder UI (visual graph)
- [ ] Multiple project tabs
- [ ] Keyboard shortcuts
- [ ] Load previous logs on project open

