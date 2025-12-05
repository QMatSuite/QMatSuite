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
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

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

interface DaemonStatus {
  connected: boolean;
  startupError: string | null;
  pythonPath: string | null;
  projectRoot: string | null;
}

// =============================================================================
// Global State
// =============================================================================

let win: BrowserWindow | null = null;
let daemonProcess: ChildProcess | null = null;
let daemonReadline: Interface | null = null;

// Daemon status tracking
const daemonStatus: DaemonStatus = {
  connected: false,
  startupError: null,
  pythonPath: null,
  projectRoot: null,
};

// Map of pending requests: id -> {resolve, reject, timeoutId}
const pendingRequests = new Map<string, PendingRequest>();

// Request timeout in milliseconds
const REQUEST_TIMEOUT_MS = 60000; // 60 seconds for long operations

// =============================================================================
// Daemon Management - Python Path Resolution
// =============================================================================

/**
 * Get the project root directory
 */
function getProjectRoot(): string {
  // Check environment variable first
  if (process.env.QV_PROJECT_ROOT) {
    return process.env.QV_PROJECT_ROOT;
  }
  // Go up from gui/dist-electron to project root
  return path.resolve(__dirname, '..', '..');
}

/**
 * Find the Python interpreter
 * 
 * Search order:
 * 1. QV_DAEMON_PYTHON environment variable (if set)
 * 2. .venv/bin/python (Unix/macOS) or .venv/Scripts/python.exe (Windows)
 * 3. venv/bin/python or venv/Scripts/python.exe
 * 4. Fallback to 'python' on PATH
 * 
 * @returns Object with path and whether it was found
 */
function findPythonPath(): { path: string; found: boolean; source: string } {
  const projectRoot = getProjectRoot();
  
  // 1. Check environment variable first
  if (process.env.QV_DAEMON_PYTHON) {
    const envPath = process.env.QV_DAEMON_PYTHON;
    if (fs.existsSync(envPath)) {
      return { path: envPath, found: true, source: 'QV_DAEMON_PYTHON env var' };
    }
    console.warn(`[main] QV_DAEMON_PYTHON set to ${envPath} but file not found`);
  }
  
  // 2. Check .venv in project root
  const isWindows = process.platform === 'win32';
  const venvCandidates = [
    // .venv (common convention)
    isWindows 
      ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
      : path.join(projectRoot, '.venv', 'bin', 'python'),
    // venv (alternative)
    isWindows
      ? path.join(projectRoot, 'venv', 'Scripts', 'python.exe')
      : path.join(projectRoot, 'venv', 'bin', 'python'),
  ];
  
  for (const candidate of venvCandidates) {
    if (fs.existsSync(candidate)) {
      return { path: candidate, found: true, source: `venv at ${path.dirname(path.dirname(candidate))}` };
    }
  }
  
  // 3. Fallback to system python
  console.warn('[main] No venv found, falling back to system python');
  return { path: 'python', found: false, source: 'system PATH (fallback)' };
}

/**
 * Get the daemon module path
 * 
 * @returns Module path to run
 */
function getDaemonModule(): string {
  // Allow override via environment variable
  if (process.env.QV_DAEMON_MODULE) {
    return process.env.QV_DAEMON_MODULE;
  }
  return 'quantumvitas.daemon.server';
}

// =============================================================================
// Daemon Management - Spawning and Communication
// =============================================================================

/**
 * Spawn the Python daemon process
 * 
 * @returns true if spawn was successful, false otherwise
 */
function spawnDaemon(): boolean {
  const pythonInfo = findPythonPath();
  const projectRoot = getProjectRoot();
  const daemonModule = getDaemonModule();
  
  // Store for status reporting
  daemonStatus.pythonPath = pythonInfo.path;
  daemonStatus.projectRoot = projectRoot;
  daemonStatus.startupError = null;
  
  console.log(`[main] Starting daemon:`);
  console.log(`[main]   Python: ${pythonInfo.path} (${pythonInfo.source})`);
  console.log(`[main]   Module: ${daemonModule}`);
  console.log(`[main]   CWD: ${projectRoot}`);
  
  try {
    daemonProcess = spawn(pythonInfo.path, ['-m', daemonModule], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1', // Ensure unbuffered output
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (err) {
    const error = err as Error;
    daemonStatus.startupError = `Failed to spawn daemon: ${error.message}`;
    console.error(`[main] ${daemonStatus.startupError}`);
    return false;
  }
  
  if (!daemonProcess.stdout || !daemonProcess.stdin) {
    daemonStatus.startupError = 'Failed to create daemon stdio pipes';
    console.error(`[main] ${daemonStatus.startupError}`);
    return false;
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
    daemonStatus.connected = false;
    daemonStatus.startupError = `Daemon error: ${err.message}`;
    // Notify renderer of daemon error
    win?.webContents.send('daemon-status', { ...daemonStatus });
  });
  
  daemonProcess.on('exit', (code: number | null, signal: string | null) => {
    console.log(`[main] Daemon exited with code ${code}, signal ${signal}`);
    daemonStatus.connected = false;
    
    if (code !== 0 && code !== null) {
      daemonStatus.startupError = `Daemon exited with code ${code}`;
    }
    
    daemonProcess = null;
    daemonReadline = null;
    
    // Reject all pending requests
    for (const [_id, pending] of pendingRequests) {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error('Daemon process exited'));
    }
    pendingRequests.clear();
    
    // Notify renderer
    win?.webContents.send('daemon-status', { ...daemonStatus });
  });
  
  daemonStatus.connected = true;
  return true;
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
  if (!daemonProcess || !daemonProcess.stdin || !daemonStatus.connected) {
    return {
      id: request.id,
      ok: false,
      error: {
        code: 'daemon_not_connected',
        message: daemonStatus.startupError || 'Daemon process is not running',
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
 * Wait for a specified duration
 */
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Shutdown the daemon gracefully
 * 
 * Sends shutdown command and waits, then force kills if necessary.
 */
async function shutdownDaemon(): Promise<void> {
  if (!daemonProcess || !daemonStatus.connected) return;
  
  const processToKill = daemonProcess;
  
  try {
    // Send shutdown command
    await sendDaemonRequest({
      id: `shutdown-${Date.now()}`,
      type: 'shutdown',
      payload: {},
    });
  } catch (e) {
    // Ignore errors during shutdown
    console.log('[main] Shutdown command failed (may already be stopped)');
  }
  
  // Wait for graceful shutdown
  await delay(2000);
  
  // Force kill if still running
  if (processToKill && !processToKill.killed) {
    console.log('[main] Force killing daemon');
    processToKill.kill('SIGTERM');
  }
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
  return daemonStatus.connected && daemonProcess !== null;
});

/**
 * Get daemon status including any startup errors
 */
ipcMain.handle('qv-daemon-status', async (): Promise<DaemonStatus> => {
  return { ...daemonStatus };
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
  });

  // Signal when window is ready
  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', {
      type: 'ready',
      timestamp: new Date().toISOString(),
    });
    // Also send daemon status
    win?.webContents.send('daemon-status', { ...daemonStatus });
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

let isQuitting = false;

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
  // Only handle once - prevent infinite loop
  if (isQuitting) return;
  if (!daemonProcess) return;
  
  isQuitting = true;
  event.preventDefault();
  
  await shutdownDaemon();
  app.quit();
});

app.whenReady().then(() => {
  // Spawn daemon first
  const daemonStarted = spawnDaemon();
  
  if (!daemonStarted) {
    console.error('[main] Failed to start daemon - continuing with UI');
  }
  
  // Then create window
  createWindow();
});
