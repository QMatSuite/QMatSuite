/**
 * QuantumVITAS Electron Main Process
 * 
 * Responsibilities:
 * - Create and manage the main window
 * - Spawn and manage the Python daemon process
 * - Handle IPC communication between renderer and daemon
 * - Maintain request/response mapping for async JSON-RPC
 */

import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
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

// Current project path for log file storage
let currentProjectPath: string | null = null;

// Log file name
const LOG_FILE_NAME = '.qv-daemon.log';

/**
 * Safely send a message to the renderer process.
 * Checks if window exists and is not destroyed before sending.
 */
function safeSend(channel: string, ...args: unknown[]): void {
  if (win && !win.isDestroyed() && win.webContents) {
    win.webContents.send(channel, ...args);
  }
}

/**
 * Append a log message to the project's log file
 */
function appendToLogFile(message: string): void {
  if (!currentProjectPath) return;
  
  const logPath = path.join(currentProjectPath, LOG_FILE_NAME);
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] ${message}\n`;
  
  try {
    fs.appendFileSync(logPath, logLine);
  } catch (err) {
    // Silently ignore log file errors
  }
}

/**
 * Read logs from the project's log file
 */
function readLogFile(projectPath: string, tailLines: number = 500): string[] {
  const logPath = path.join(projectPath, LOG_FILE_NAME);
  
  try {
    if (!fs.existsSync(logPath)) {
      return [];
    }
    
    const content = fs.readFileSync(logPath, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    
    // Return last N lines
    return lines.slice(-tailLines);
  } catch (err) {
    return [];
  }
}

/**
 * Set the current project path for log storage
 */
function setCurrentProject(projectPath: string | null): void {
  currentProjectPath = projectPath;
}

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
    // Spawn daemon with independent stdio pipes
    // This ensures the daemon's stdin/stdout/stderr are completely independent
    // from Electron's stdin, which may be ignored in E2E test environments
    daemonProcess = spawn(pythonInfo.path, ['-m', daemonModule], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1', // Ensure unbuffered output
      },
      // Use independent pipes - daemon's stdio is not tied to Electron's stdin
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
  
  // Forward daemon stderr to console, renderer, log file, AND process stderr (for E2E test visibility)
  daemonProcess.stderr?.on('data', (data: Buffer) => {
    const message = data.toString().trim();
    // Log to console (visible in Electron DevTools)
    console.log(`[daemon] ${message}`);
    // Also write to process stderr so E2E tests can capture it
    process.stderr.write(`[daemon stderr] ${message}\n`);
    // Forward to renderer for debug panel
    safeSend('daemon-log', message);
    // Append to log file
    appendToLogFile(message);
  });
  
  // Also capture daemon stdout (Python print statements, tracebacks, etc.)
  // Note: JSON-RPC responses go through stdout but are handled separately via readline
  // This captures any unexpected stdout (errors, warnings, etc.)
  daemonProcess.stdout?.on('data', (data: Buffer) => {
    const message = data.toString().trim();
    // Only log non-empty lines that aren't JSON-RPC responses
    // JSON-RPC responses are handled by readline and start with '{'
    if (message && !message.trim().startsWith('{')) {
      console.log(`[daemon stdout] ${message}`);
      process.stderr.write(`[daemon stdout] ${message}\n`);
    }
  });
  
  daemonProcess.on('error', (err: Error) => {
    const errorMsg = `[main] Daemon process error: ${err.message}`;
    console.error(errorMsg);
    // Write to stderr for E2E test visibility
    process.stderr.write(`${errorMsg}\n`);
    daemonStatus.connected = false;
    daemonStatus.startupError = `Daemon error: ${err.message}`;
    // Notify renderer of daemon error
    safeSend('daemon-status', { ...daemonStatus });
  });
  
  // Monitor daemon exit
  daemonProcess.on('exit', (code: number | null, signal: string | null) => {
    const exitMsg = `[main] Daemon exited with code ${code}, signal ${signal}`;
    console.log(exitMsg);
    // Write to stderr for E2E test visibility
    process.stderr.write(`${exitMsg}\n`);
    
    daemonStatus.connected = false;
    
    if (code !== 0 && code !== null) {
      daemonStatus.startupError = `Daemon exited with code ${code}`;
      process.stderr.write(`[main] Daemon exit error: ${daemonStatus.startupError}\n`);
    }
    
    // Clean up references
    daemonProcess = null;
    daemonReadline = null;
    
    // Reject all pending requests
    for (const [_id, pending] of pendingRequests) {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error('Daemon process exited'));
    }
    pendingRequests.clear();
    
    // Notify renderer (only if window still exists)
    safeSend('daemon-status', { ...daemonStatus });
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
  // Robust guards: check process exists, stdin exists, and stdin is writable
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
  
  // Check if stdin is destroyed or ended before attempting write
  const stdin = daemonProcess.stdin;
  if (stdin.destroyed || stdin.writableEnded) {
    const errorMsg = `[main] Cannot write to daemon: stdin is ${stdin.destroyed ? 'destroyed' : 'ended'}`;
    console.error(errorMsg);
    process.stderr.write(`${errorMsg}\n`);
    return {
      id: request.id,
      ok: false,
      error: {
        code: 'daemon_stdin_closed',
        message: 'Daemon stdin pipe is closed',
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
    
    // Send request with error handling
    const jsonLine = JSON.stringify(request) + '\n';
    try {
      stdin.write(jsonLine, (err) => {
      if (err) {
        clearTimeout(timeoutId);
        pendingRequests.delete(request.id);
          const errorMsg = `[main] Failed to write to daemon stdin: ${err.message}`;
          console.error(errorMsg);
          process.stderr.write(`${errorMsg}\n`);
          // Don't crash - return error response instead
          resolve({
            id: request.id,
            ok: false,
            error: {
              code: 'write_error',
              message: err.message,
            },
          });
        }
      });
    } catch (err) {
      // Handle synchronous errors (e.g., if stdin was closed between check and write)
      clearTimeout(timeoutId);
      pendingRequests.delete(request.id);
      const error = err as Error;
      const errorMsg = `[main] Exception writing to daemon stdin: ${error.message}`;
      console.error(errorMsg);
      process.stderr.write(`${errorMsg}\n`);
      resolve({
        id: request.id,
        ok: false,
        error: {
          code: 'write_exception',
          message: error.message,
        },
      });
    }
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
  if (!daemonProcess) {
    console.log('[main] No daemon process to shutdown');
    return;
  }
  
  const processToKill = daemonProcess;
  console.log('[main] Shutting down daemon...');
  
  try {
    // Try to send shutdown command if daemon is still connected
    if (daemonStatus.connected && processToKill.stdin && !processToKill.stdin.destroyed && !processToKill.stdin.writableEnded) {
      try {
    await sendDaemonRequest({
      id: `shutdown-${Date.now()}`,
      type: 'shutdown',
      payload: {},
    });
  } catch (e) {
        // Ignore errors during shutdown (daemon may have already exited)
        console.log('[main] Shutdown command failed (daemon may already be stopped)');
  }
  
  // Wait for graceful shutdown
  await delay(2000);
    } else {
      console.log('[main] Daemon stdin not available, skipping graceful shutdown');
    }
  } catch (e) {
    // Ignore errors during shutdown
    console.log('[main] Error during graceful shutdown, proceeding to kill');
  }
  
  // Force kill if still running
  if (processToKill && !processToKill.killed && processToKill.pid) {
    console.log('[main] Force killing daemon');
    try {
    processToKill.kill('SIGTERM');
      // Wait a bit for SIGTERM to take effect
      await delay(1000);
      // If still running, use SIGKILL
      if (!processToKill.killed && processToKill.pid) {
        console.log('[main] Daemon still running, using SIGKILL');
        processToKill.kill('SIGKILL');
      }
    } catch (err) {
      const error = err as Error;
      console.error(`[main] Failed to kill daemon: ${error.message}`);
      process.stderr.write(`[main] Failed to kill daemon: ${error.message}\n`);
    }
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

/**
 * Open a directory picker dialog
 * 
 * @returns Selected directory path or null if cancelled
 */
// Store E2E test directory (set via IPC from renderer in test mode)
let e2eTestDirectory: string | null = null;

/**
 * Set E2E test directory (for testing only)
 */
ipcMain.handle('qv-set-e2e-test-directory', async (_event, dir: string): Promise<void> => {
  if (process.env.E2E_TEST_MODE === 'true') {
    e2eTestDirectory = dir;
  }
});

ipcMain.handle('qv-open-directory', async (): Promise<string | null> => {
  if (!win) return null;
  
  // In E2E test mode, check for a test directory set via IPC
  // This allows tests to bypass the native file dialog
  if (process.env.E2E_TEST_MODE === 'true' && e2eTestDirectory) {
    const testDir = e2eTestDirectory;
    e2eTestDirectory = null; // Clear after use
    if (fs.existsSync(testDir)) {
      return testDir;
    }
  }
  
  const result = await dialog.showOpenDialog(win, {
    properties: ['openDirectory', 'createDirectory'],
    title: 'Select Project Root',
    buttonLabel: 'Select',
  });
  
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  
  return result.filePaths[0];
});

/**
 * Open a file picker dialog for importing structures
 * 
 * @returns Selected file path or null if cancelled
 */
ipcMain.handle('qv-open-file', async (_event, options?: {
  title?: string;
  filters?: { name: string; extensions: string[] }[];
}): Promise<string | null> => {
  if (!win) return null;
  
  const result = await dialog.showOpenDialog(win, {
    properties: ['openFile'],
    title: options?.title || 'Select File',
    buttonLabel: 'Select',
    filters: options?.filters || [
      { name: 'Structure Files', extensions: ['cif', 'json', 'in', 'xsf', 'xyz', 'poscar', 'vasp'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  
  return result.filePaths[0];
});

/**
 * Set current project path for log file storage
 */
ipcMain.handle('qv-set-project', async (_event, projectPath: string | null): Promise<void> => {
  setCurrentProject(projectPath);
});

/**
 * Read logs from the project's log file
 */
ipcMain.handle('qv-read-logs', async (_event, projectPath: string, tailLines?: number): Promise<string[]> => {
  return readLogFile(projectPath, tailLines || 500);
});

/**
 * Reveal a file or folder in the native file manager (Finder/Explorer)
 */
ipcMain.handle('qv-reveal-path', async (_event, targetPath: string): Promise<boolean> => {
  try {
    // showItemInFolder works on all platforms (macOS, Windows, Linux)
    shell.showItemInFolder(targetPath);
    return true;
  } catch (e) {
    console.error('[main] Failed to reveal path:', e);
    return false;
  }
});

/**
 * Read binary blob file (secure, via index.json allowlist)
 * 
 * Security:
 * 1. Read index.json from <calcDir>/analysis/blobs/index.json
 * 2. Lookup blobId -> relative_path
 * 3. Validate relative_path (no ../ traversal)
 * 4. Resolve realpath and verify it's within blobs_dir
 * 5. Read file and return ArrayBuffer
 */
ipcMain.handle('qv-read-blob', async (_event, blobId: string, calcDir: string): Promise<ArrayBuffer> => {
  try {
    const calcPath = path.resolve(calcDir);
    const blobsDir = path.join(calcPath, 'analysis', 'blobs');
    const indexPath = path.join(blobsDir, 'index.json');
    
    // Read index.json
    if (!fs.existsSync(indexPath)) {
      throw new Error(`Blob index not found: ${indexPath}`);
    }
    
    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    const index: Record<string, string> = JSON.parse(indexContent);
    
    // Lookup blob_id
    if (!(blobId in index)) {
      throw new Error(`Blob ID not found in index: ${blobId}`);
    }
    
    const relativePath = index[blobId];
    
    // Validate relative path (no traversal)
    if (relativePath.includes('..') || path.isAbsolute(relativePath)) {
      throw new Error(`Invalid blob path (traversal detected): ${relativePath}`);
    }
    
    // Resolve absolute path
    const blobPath = path.resolve(blobsDir, relativePath);
    
    // Security check: ensure resolved path is within blobs_dir
    const blobsDirResolved = path.resolve(blobsDir);
    if (!blobPath.startsWith(blobsDirResolved)) {
      throw new Error(`Path traversal detected: ${blobPath} is outside ${blobsDirResolved}`);
    }
    
    // Verify file exists
    if (!fs.existsSync(blobPath)) {
      throw new Error(`Blob file not found: ${blobPath}`);
    }
    
    // Read file as ArrayBuffer
    const buffer = fs.readFileSync(blobPath);
    return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    
  } catch (error) {
    console.error('[main] Failed to read blob:', error);
    throw error;
  }
});

// =============================================================================
// Remote Debugging for E2E Tests
// =============================================================================

// Enable remote debugging for E2E tests if requested via environment variable
if (process.env.ELECTRON_REMOTE_DEBUG_PORT) {
  const port = parseInt(process.env.ELECTRON_REMOTE_DEBUG_PORT, 10);
  if (!isNaN(port)) {
    // Enable remote debugging on the specified port
    // This must be called before app.whenReady()
    app.commandLine.appendSwitch('remote-debugging-port', port.toString());
  }
}

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
    safeSend('main-process-message', {
      type: 'ready',
      timestamp: new Date().toISOString(),
    });
    // Also send daemon status
    safeSend('daemon-status', { ...daemonStatus });
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
  if (!daemonProcess) {
    // No daemon to clean up, allow quit
    return;
  }
  
  isQuitting = true;
  event.preventDefault();
  
  console.log('[main] App quitting, shutting down daemon...');
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
