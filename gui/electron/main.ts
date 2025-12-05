/**
 * QuantumVITAS Electron Main Process
 * 
 * Responsibilities:
 * - Create and manage the main window
 * - Spawn and manage the Python daemon process
 * - Handle IPC communication between renderer and daemon
 * - Maintain request/response mapping for async JSON-RPC
 */

import { app, BrowserWindow, ipcMain } from 'electron';
import { spawn, ChildProcess } from 'node:child_process';
import { createInterface, Interface } from 'node:readline';
// import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

// const require = createRequire(import.meta.url); // Unused for now
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Build directory structure
process.env.APP_ROOT = path.join(__dirname, '..');

export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL'];
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron');
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist');

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL 
  ? path.join(process.env.APP_ROOT, 'public') 
  : RENDERER_DIST;

// =============================================================================
// Types
// =============================================================================

interface PendingRequest {
  resolve: (value: QVResponse) => void;
  reject: (reason: Error) => void;
  timeoutId: NodeJS.Timeout;
}

interface QVRequest {
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

interface QVResponse {
  id: string;
  ok: boolean;
  data?: Record<string, unknown>;
  error?: {
    code: string;
    message: string;
  };
}

// =============================================================================
// Global State
// =============================================================================

let win: BrowserWindow | null = null;
let daemonProcess: ChildProcess | null = null;
let daemonReadline: Interface | null = null;
let daemonConnected = false;

// Map of pending requests: id -> {resolve, reject, timeoutId}
const pendingRequests = new Map<string, PendingRequest>();

// Request timeout in milliseconds
const REQUEST_TIMEOUT_MS = 60000; // 60 seconds for long operations

// =============================================================================
// Daemon Management
// =============================================================================

/**
 * Find the Python interpreter in the project's .venv
 */
function findPythonPath(): string {
  // Go up from gui/dist-electron to project root
  const projectRoot = path.resolve(__dirname, '..', '..');
  
  // Check common venv locations
  const candidates = [
    path.join(projectRoot, '.venv', 'bin', 'python'),
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'), // Windows
    path.join(projectRoot, 'venv', 'bin', 'python'),
    path.join(projectRoot, 'venv', 'Scripts', 'python.exe'), // Windows
  ];
  
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  
  // Fallback to system python
  console.warn('[main] No venv found, falling back to system python');
  return 'python';
}

/**
 * Get the project root directory
 */
function getProjectRoot(): string {
  return path.resolve(__dirname, '..', '..');
}

/**
 * Spawn the Python daemon process
 */
function spawnDaemon(): void {
  const pythonPath = findPythonPath();
  const projectRoot = getProjectRoot();
  
  console.log(`[main] Starting daemon with Python: ${pythonPath}`);
  console.log(`[main] Project root: ${projectRoot}`);
  
  daemonProcess = spawn(pythonPath, ['-m', 'quantumvitas.daemon.server'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1', // Ensure unbuffered output
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  
  if (!daemonProcess.stdout || !daemonProcess.stdin) {
    console.error('[main] Failed to create daemon stdio pipes');
    return;
  }
  
  // Read daemon stdout line-by-line
  daemonReadline = createInterface({
    input: daemonProcess.stdout,
    crlfDelay: Infinity,
  });
  
  daemonReadline.on('line', (line: string) => {
    handleDaemonLine(line);
  });
  
  // Forward daemon stderr to console and renderer
  daemonProcess.stderr?.on('data', (data: Buffer) => {
    const message = data.toString().trim();
    console.log(`[daemon] ${message}`);
    // Forward to renderer for debug panel
    win?.webContents.send('daemon-log', message);
  });
  
  daemonProcess.on('error', (err: Error) => {
    console.error('[main] Daemon process error:', err);
    daemonConnected = false;
  });
  
  daemonProcess.on('exit', (code: number | null, signal: string | null) => {
    console.log(`[main] Daemon exited with code ${code}, signal ${signal}`);
    daemonConnected = false;
    daemonProcess = null;
    daemonReadline = null;
    
    // Reject all pending requests
    for (const [_id, pending] of pendingRequests) {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error('Daemon process exited'));
    }
    pendingRequests.clear();
  });
  
  daemonConnected = true;
}

/**
 * Handle a line of JSON output from the daemon
 */
function handleDaemonLine(line: string): void {
  // Skip empty lines
  if (!line.trim()) return;
  
  try {
    const response: QVResponse = JSON.parse(line);
    
    const pending = pendingRequests.get(response.id);
    if (pending) {
      clearTimeout(pending.timeoutId);
      pendingRequests.delete(response.id);
      pending.resolve(response);
    } else {
      console.warn(`[main] Received response for unknown request: ${response.id}`);
    }
  } catch (e) {
    console.error(`[main] Failed to parse daemon response: ${line}`);
    console.error(e);
  }
}

/**
 * Send a request to the daemon
 */
async function sendDaemonRequest(request: QVRequest): Promise<QVResponse> {
  if (!daemonProcess || !daemonProcess.stdin || !daemonConnected) {
    return {
      id: request.id,
      ok: false,
      error: {
        code: 'daemon_not_connected',
        message: 'Daemon process is not running',
      },
    };
  }
  
  return new Promise((resolve, reject) => {
    // Set up timeout
    const timeoutId = setTimeout(() => {
      pendingRequests.delete(request.id);
      reject(new Error(`Request ${request.id} timed out after ${REQUEST_TIMEOUT_MS}ms`));
    }, REQUEST_TIMEOUT_MS);
    
    // Store pending request
    pendingRequests.set(request.id, { resolve, reject, timeoutId });
    
    // Send request
    const jsonLine = JSON.stringify(request) + '\n';
    daemonProcess!.stdin!.write(jsonLine, (err) => {
      if (err) {
        clearTimeout(timeoutId);
        pendingRequests.delete(request.id);
        reject(err);
      }
    });
  });
}

/**
 * Shutdown the daemon gracefully
 */
async function shutdownDaemon(): Promise<void> {
  if (!daemonProcess || !daemonConnected) return;
  
  try {
    // Send shutdown command
    await sendDaemonRequest({
      id: `shutdown-${Date.now()}`,
      type: 'shutdown',
      payload: {},
    });
  } catch (e) {
    // Ignore errors during shutdown
  }
  
  // Force kill if still running after 2 seconds
  setTimeout(() => {
    if (daemonProcess) {
      daemonProcess.kill('SIGTERM');
    }
  }, 2000);
}

// =============================================================================
// IPC Handlers
// =============================================================================

/**
 * Handle qv-request IPC from renderer
 */
ipcMain.handle('qv-request', async (_event, request: QVRequest): Promise<QVResponse> => {
  console.log(`[main] IPC request: ${request.type} (${request.id})`);
  
  try {
    const response = await sendDaemonRequest(request);
    console.log(`[main] IPC response: ${request.type} ok=${response.ok}`);
    return response;
  } catch (e) {
    const error = e as Error;
    console.error(`[main] IPC error: ${request.type}`, error);
    return {
      id: request.id,
      ok: false,
      error: {
        code: 'ipc_error',
        message: error.message,
      },
    };
  }
});

/**
 * Check if daemon is connected
 */
ipcMain.handle('qv-is-connected', async (): Promise<boolean> => {
  return daemonConnected && daemonProcess !== null;
});

// =============================================================================
// Window Management
// =============================================================================

function createWindow(): void {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(process.env.VITE_PUBLIC!, 'electron-vite.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    // Modern frameless window with custom titlebar (optional)
    // titleBarStyle: 'hiddenInset',
    // frame: false,
  });

  // Signal when window is ready
  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', {
      type: 'ready',
      timestamp: new Date().toISOString(),
      daemonConnected,
    });
  });

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
    // Open DevTools in development
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html'));
  }
}

// =============================================================================
// App Lifecycle
// =============================================================================

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', async (event) => {
  // Only handle once
  if (!daemonProcess) return;
  
  event.preventDefault();
  await shutdownDaemon();
  app.quit();
});

app.whenReady().then(() => {
  // Spawn daemon first
  spawnDaemon();
  
  // Then create window
  createWindow();
});
