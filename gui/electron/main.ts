/**
 * QMatSuite Electron Main Process
 * 
 * Responsibilities:
 * - Create and manage the main window
 * - Spawn and manage the Python daemon process
 * - Handle IPC communication between renderer and daemon
 * - Maintain request/response mapping for async JSON-RPC
 */

import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import { spawn, ChildProcess, spawnSync } from 'node:child_process';
import { createInterface, Interface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { autoUpdater } from 'electron-updater';

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
  resolve: (value: QMSResponse) => void;
  reject: (reason: Error) => void;
  timeoutId: NodeJS.Timeout;
}

interface QMSRequest {
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

interface QMSResponse {
  id: string;
  ok: boolean;
  data?: Record<string, unknown>;
  error?: {
    code: string;
    message: string;
  };
}

type E2ERpcMockResponse = Omit<QMSResponse, 'id'>;

interface DaemonStatus {
  connected: boolean;
  startupError: string | null;
  pythonPath: string | null;
  projectRoot: string | null;
}

interface RuntimeSetupStatus {
  stage: 'idle' | 'checking' | 'extracting' | 'verifying' | 'ready' | 'error';
  progress: number;
  message: string;
  error: string | null;
}

interface UpdaterState {
  state: 'idle' | 'checking' | 'available' | 'not-available' | 'downloading' | 'downloaded' | 'error';
  version: string | null;
  progress: number;
  message: string | null;
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

const runtimeSetupStatus: RuntimeSetupStatus = {
  stage: 'idle',
  progress: 0,
  message: 'Runtime setup not started',
  error: null,
};

const updaterState: UpdaterState = {
  state: 'idle',
  version: null,
  progress: 0,
  message: null,
};

// Map of pending requests: id -> {resolve, reject, timeoutId}
const pendingRequests = new Map<string, PendingRequest>();
const e2eRpcMocks = new Map<string, E2ERpcMockResponse[]>();

// Request timeout in milliseconds
const REQUEST_TIMEOUT_MS = 60000; // 60 seconds for long operations

// Current project path for log file storage
let currentProjectPath: string | null = null;

// Log file name
const LOG_FILE_NAME = '.qms-daemon.log';

/**
 * Safely send a message to the renderer process.
 * Checks if window exists and is not destroyed before sending.
 */
function safeSend(channel: string, ...args: unknown[]): void {
  if (win && !win.isDestroyed() && win.webContents) {
    win.webContents.send(channel, ...args);
  }
}

function setRuntimeSetupStatus(partial: Partial<RuntimeSetupStatus>): void {
  Object.assign(runtimeSetupStatus, partial);
  safeSend('runtime-setup-status', { ...runtimeSetupStatus });
}

function setUpdaterState(partial: Partial<UpdaterState>): void {
  Object.assign(updaterState, partial);
  safeSend('updater-state', { ...updaterState });
}

function isUpdaterEnabled(): boolean {
  if (process.env.QMS_DISABLE_UPDATER === '1') {
    return false;
  }
  if (process.env.E2E_TEST_MODE === 'true' && process.env.QMS_ENABLE_UPDATER !== '1') {
    return false;
  }
  return app.isPackaged || process.env.QMS_ENABLE_UPDATER === '1';
}

function configureAutoUpdater(): void {
  if (!isUpdaterEnabled()) {
    setUpdaterState({
      state: 'idle',
      version: null,
      progress: 0,
      message: app.isPackaged ? null : 'Updater disabled in development build',
    });
    return;
  }

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => {
    setUpdaterState({
      state: 'checking',
      progress: 0,
      message: 'Checking for updates...',
    });
  });

  autoUpdater.on('update-available', (info) => {
    setUpdaterState({
      state: 'available',
      version: info.version || null,
      progress: 0,
      message: `Update ${info.version || 'available'} is ready to download`,
    });
  });

  autoUpdater.on('update-not-available', () => {
    setUpdaterState({
      state: 'not-available',
      progress: 0,
      message: 'No updates available',
    });
  });

  autoUpdater.on('error', (error) => {
    setUpdaterState({
      state: 'error',
      progress: 0,
      message: error.message || 'Update check failed',
    });
  });

  autoUpdater.on('download-progress', (progressObj) => {
    const percent = Number.isFinite(progressObj.percent) ? Math.max(0, Math.min(100, progressObj.percent)) : 0;
    setUpdaterState({
      state: 'downloading',
      progress: percent,
      message: `Downloading update... ${percent.toFixed(0)}%`,
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    setUpdaterState({
      state: 'downloaded',
      version: info.version || updaterState.version,
      progress: 100,
      message: 'Update downloaded. Restart to install.',
    });
  });
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
  if (process.env.QMS_PROJECT_ROOT) {
    return process.env.QMS_PROJECT_ROOT;
  }
  // Go up from gui/dist-electron to project root
  return path.resolve(__dirname, '..', '..');
}

function isDevCheckout(projectRoot: string): boolean {
  return (
    fs.existsSync(path.join(projectRoot, 'pyproject.toml')) &&
    fs.existsSync(path.join(projectRoot, 'src', 'qmatsuite'))
  );
}

function ensureDirSync(targetDir: string): string {
  fs.mkdirSync(targetDir, { recursive: true });
  return targetDir;
}

function getElectronPlatformAppDataDir(): string {
  if (process.platform === 'darwin') {
    return ensureDirSync(path.join(os.homedir(), 'Library', 'Application Support', 'QMatSuite'));
  }
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    return ensureDirSync(path.join(localAppData, 'QMatSuite'));
  }
  const xdgDataHome = process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share');
  return ensureDirSync(path.join(xdgDataHome, 'qmatsuite'));
}

function getAppDataDir(): string {
  if (process.env.QMATSUITE_HOME) {
    return ensureDirSync(process.env.QMATSUITE_HOME);
  }

  const projectRoot = getProjectRoot();
  if (isDevCheckout(projectRoot)) {
    return ensureDirSync(path.join(projectRoot, '.qmatsuite'));
  }

  return getElectronPlatformAppDataDir();
}

function getRuntimePythonAt(baseDir: string): string {
  return process.platform === 'win32'
    ? path.join(baseDir, 'python.exe')
    : path.join(baseDir, 'bin', 'python');
}

function getRuntimePythonPath(): string {
  return getRuntimePythonAt(path.join(getAppDataDir(), 'runtime'));
}

function getRuntimeTarballCandidates(): string[] {
  const candidates = [
    process.env.QMS_RUNTIME_TARBALL || '',
    path.join(process.resourcesPath, 'runtime.tar.zst'),
    path.join(process.resourcesPath, 'resources', 'runtime.tar.zst'),
    path.join(process.env.APP_ROOT || '', 'runtime.tar.zst'),
    path.join(getProjectRoot(), 'runtime.tar.zst'),
  ].filter(Boolean);

  return Array.from(new Set(candidates));
}

function locateRuntimeTarball(): string | null {
  for (const candidate of getRuntimeTarballCandidates()) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function getBundledZstdPath(): string | null {
  const platform = process.platform;
  const arch = process.arch;
  
  // Determine platform-specific path
  let platformDir: string;
  let zstdName: string;
  
  if (platform === 'darwin' && arch === 'arm64') {
    platformDir = 'macos-arm64';
    zstdName = 'zstd';
  } else if (platform === 'win32' && arch === 'x64') {
    platformDir = 'windows-x64';
    zstdName = 'zstd.exe';
  } else {
    return null; // Unsupported platform
  }
  
  // Try packaged path first
  const packagedPath = path.join(process.resourcesPath, 'bin', platformDir, zstdName);
  if (fs.existsSync(packagedPath)) {
    return packagedPath;
  }
  
  // Fallback to dev mode path
  const devPath = path.join(getProjectRoot(), 'gui', 'extra', 'bin', platformDir, zstdName);
  if (fs.existsSync(devPath)) {
    return devPath;
  }
  
  return null;
}

async function validateBundledZstd(zstdPath: string): Promise<{ ok: boolean; error: string | null }> {
  if (!fs.existsSync(zstdPath)) {
    return {
      ok: false,
      error: `Bundled zstd not found at: ${zstdPath}`,
    };
  }
  
  // On macOS, check executable permission
  if (process.platform === 'darwin') {
    try {
      fs.accessSync(zstdPath, fs.constants.X_OK);
    } catch {
      return {
        ok: false,
        error: `Bundled zstd is not executable. Run: chmod +x "${zstdPath}"`,
      };
    }
    
    // Check for quarantine attribute (best-effort)
    try {
      const { execSync } = await import('node:child_process');
      const xattrOutput = execSync(`xattr -l "${zstdPath}"`, { encoding: 'utf-8', stdio: 'pipe' }).trim();
      if (xattrOutput.includes('com.apple.quarantine')) {
        return {
          ok: false,
          error: `Bundled zstd is quarantined. Run: xattr -d com.apple.quarantine "${zstdPath}" or xattr -dr com.apple.quarantine "/Applications/QMatSuite.app"`,
        };
      }
    } catch {
      // xattr check failed, but that's okay - continue
    }
  }
  
  return { ok: true, error: null };
}

async function extractWithBundledZstd(zstdPath: string, tarballPath: string, destinationDir: string): Promise<{ ok: boolean; error: string | null; zstdError?: string }> {
  return new Promise((resolve) => {
    try {
      // Spawn zstd to decompress to stdout
      const zstdProcess = spawn(zstdPath, ['-d', '--stdout', tarballPath], {
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      
      // Spawn tar to extract from stdin
      const tarProcess = spawn('tar', ['-x', '-C', destinationDir], {
        stdio: ['pipe', 'inherit', 'pipe'],
      });
      
      // Pipe zstd stdout to tar stdin
      zstdProcess.stdout?.pipe(tarProcess.stdin!);
      
      // Collect stderr from both processes
      let zstdStderr = '';
      let tarStderr = '';
      
      zstdProcess.stderr?.on('data', (chunk: Buffer) => {
        zstdStderr += chunk.toString();
      });
      
      tarProcess.stderr?.on('data', (chunk: Buffer) => {
        tarStderr += chunk.toString();
      });
      
      // Wait for both processes
      let zstdExited = false;
      let tarExited = false;
      let zstdCode: number | null = null;
      let tarCode: number | null = null;
      
      zstdProcess.on('exit', (code) => {
        zstdExited = true;
        zstdCode = code;
        if (tarExited) {
          if (zstdCode === 0 && tarCode === 0) {
            resolve({ ok: true, error: null });
          } else {
            resolve({
              ok: false,
              error: `Extraction failed: zstd exit code ${zstdCode}, tar exit code ${tarCode}`,
              zstdError: zstdStderr || undefined,
            });
          }
        }
      });
      
      tarProcess.on('exit', (code) => {
        tarExited = true;
        tarCode = code;
        if (zstdExited) {
          if (zstdCode === 0 && tarCode === 0) {
            resolve({ ok: true, error: null });
          } else {
            resolve({
              ok: false,
              error: `Extraction failed: zstd exit code ${zstdCode}, tar exit code ${tarCode}`,
              zstdError: zstdStderr || undefined,
            });
          }
        }
      });
      
      zstdProcess.on('error', (err) => {
        resolve({
          ok: false,
          error: `Failed to spawn zstd: ${err.message}`,
          zstdError: err.message,
        });
      });
      
      tarProcess.on('error', (err) => {
        resolve({
          ok: false,
          error: `Failed to spawn tar: ${err.message}`,
        });
      });
      
      // Timeout after 5 minutes
      setTimeout(() => {
        zstdProcess.kill();
        tarProcess.kill();
        resolve({
          ok: false,
          error: 'Extraction timed out after 5 minutes',
        });
      }, 5 * 60 * 1000);
    } catch (err) {
      const error = err as Error;
      resolve({
        ok: false,
        error: `Failed to extract with bundled zstd: ${error.message}`,
      });
    }
  });
}

async function extractRuntimeTarball(tarballPath: string, destinationDir: string): Promise<{ ok: boolean; error: string | null }> {
  // First, try system tar with zstd support
  const attempts: Array<string[]> = [
    ['--zstd', '-xf', tarballPath, '-C', destinationDir],
    ['-I', 'zstd', '-xf', tarballPath, '-C', destinationDir],
  ];

  let systemTarError: string | null = null;
  for (const args of attempts) {
    const result = spawnSync('tar', args, {
      encoding: 'utf-8',
      timeout: 5 * 60 * 1000,
    });
    if (result.status === 0) {
      return { ok: true, error: null };
    }
    if (result.stderr) {
      systemTarError = result.stderr.toString();
    }
  }

  // System tar failed, try fallback with bundled zstd
  const bundledZstdPath = getBundledZstdPath();
  if (!bundledZstdPath) {
    // No bundled zstd available, return comprehensive error
    const platform = process.platform;
    let helpMessage = '';
    if (platform === 'darwin') {
      helpMessage = '\n\nTo fix this:\n' +
        '1. Install zstd via Homebrew: brew install zstd\n' +
        '2. Restart QMatSuite';
    } else if (platform === 'win32') {
      helpMessage = '\n\nTo fix this:\n' +
        '1. Install zstd via winget: winget install Facebook.Zstandard\n' +
        '2. Restart QMatSuite';
    }
    
    return {
      ok: false,
      error: `Failed to extract runtime tarball with system tar: ${tarballPath}${systemTarError ? `\nSystem tar error: ${systemTarError}` : ''}${helpMessage}`,
    };
  }
  
  // Validate bundled zstd
  const validation = await validateBundledZstd(bundledZstdPath);
  if (!validation.ok) {
    return {
      ok: false,
      error: `Bundled zstd validation failed: ${validation.error}\n\nSystem tar error: ${systemTarError || 'unknown'}\n\nTo fix this:\n` +
        (process.platform === 'darwin' 
          ? `1. Remove quarantine: xattr -dr com.apple.quarantine "/Applications/QMatSuite.app"\n` +
            `2. Or install system zstd: brew install zstd\n` +
            `3. Restart QMatSuite`
          : `1. Install zstd: winget install Facebook.Zstandard\n` +
            `2. Restart QMatSuite`),
    };
  }
  
  // Try extraction with bundled zstd
  const fallbackResult = await extractWithBundledZstd(bundledZstdPath, tarballPath, destinationDir);
  if (fallbackResult.ok) {
    return { ok: true, error: null };
  }
  
  // Both methods failed, return comprehensive error
  const platform = process.platform;
  let helpMessage = '';
  if (platform === 'darwin') {
    helpMessage = '\n\nTo fix this:\n' +
      '1. Remove quarantine: xattr -dr com.apple.quarantine "/Applications/QMatSuite.app"\n' +
      '2. Or install system zstd: brew install zstd\n' +
      '3. Restart QMatSuite';
  } else if (platform === 'win32') {
    helpMessage = '\n\nTo fix this:\n' +
      '1. Install zstd: winget install Facebook.Zstandard\n' +
      '2. Restart QMatSuite';
  }
  
  return {
    ok: false,
    error: `Failed to extract runtime tarball.\n` +
      `System tar error: ${systemTarError || 'unknown'}\n` +
      `Bundled zstd error: ${fallbackResult.error || 'unknown'}${fallbackResult.zstdError ? `\nzstd stderr: ${fallbackResult.zstdError}` : ''}${helpMessage}`,
  };
}

function findRuntimeRoot(extractRoot: string): string | null {
  if (fs.existsSync(getRuntimePythonAt(extractRoot))) {
    return extractRoot;
  }
  const children = fs.readdirSync(extractRoot, { withFileTypes: true });
  for (const child of children) {
    if (!child.isDirectory()) continue;
    const candidate = path.join(extractRoot, child.name);
    if (fs.existsSync(getRuntimePythonAt(candidate))) {
      return candidate;
    }
  }
  return null;
}

function verifyRuntimePython(pythonPath: string): { ok: boolean; error: string | null } {
  const result = spawnSync(
    pythonPath,
    ['-c', 'import qmatsuite; print(qmatsuite.__version__)'],
    {
      encoding: 'utf-8',
      timeout: 30_000,
    },
  );
  if (result.status === 0) {
    return { ok: true, error: null };
  }
  return {
    ok: false,
    error: (result.stderr || result.stdout || 'Runtime verification failed').trim(),
  };
}

async function ensureRuntimeReady(): Promise<boolean> {
  const runtimeDir = path.join(getAppDataDir(), 'runtime');
  const runtimePython = getRuntimePythonAt(runtimeDir);

  setRuntimeSetupStatus({
    stage: 'checking',
    progress: 5,
    message: 'Checking runtime environment...',
    error: null,
  });

  if (fs.existsSync(runtimePython)) {
    setRuntimeSetupStatus({
      stage: 'verifying',
      progress: 90,
      message: 'Verifying existing runtime...',
      error: null,
    });
    const verify = verifyRuntimePython(runtimePython);
    if (verify.ok) {
      setRuntimeSetupStatus({
        stage: 'ready',
        progress: 100,
        message: 'Runtime ready',
        error: null,
      });
      return true;
    }
    console.warn(`[main] Existing runtime failed verification: ${verify.error}`);
  }

  const runtimeTarball = locateRuntimeTarball();
  if (!runtimeTarball) {
    setRuntimeSetupStatus({
      stage: 'ready',
      progress: 100,
      message: 'No bundled runtime tarball detected; using development/system Python',
      error: null,
    });
    return false;
  }

  const appDataDir = getAppDataDir();
  const tempRoot = path.join(appDataDir, `runtime-extract-${Date.now()}`);
  fs.rmSync(tempRoot, { recursive: true, force: true });
  fs.mkdirSync(tempRoot, { recursive: true });

  setRuntimeSetupStatus({
    stage: 'extracting',
    progress: 25,
    message: 'Extracting bundled Python runtime...',
    error: null,
  });

  const extract = await extractRuntimeTarball(runtimeTarball, tempRoot);
  if (!extract.ok) {
    fs.rmSync(tempRoot, { recursive: true, force: true });
    setRuntimeSetupStatus({
      stage: 'error',
      progress: 100,
      message: 'Runtime setup failed',
      error: extract.error,
    });
    return false;
  }

  const extractedRuntimeRoot = findRuntimeRoot(tempRoot);
  if (!extractedRuntimeRoot) {
    fs.rmSync(tempRoot, { recursive: true, force: true });
    setRuntimeSetupStatus({
      stage: 'error',
      progress: 100,
      message: 'Runtime setup failed',
      error: 'Extracted runtime does not contain a Python executable',
    });
    return false;
  }

  setRuntimeSetupStatus({
    stage: 'extracting',
    progress: 75,
    message: 'Finalizing runtime files...',
    error: null,
  });

  fs.rmSync(runtimeDir, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(runtimeDir), { recursive: true });
  fs.renameSync(extractedRuntimeRoot, runtimeDir);
  fs.rmSync(tempRoot, { recursive: true, force: true });

  setRuntimeSetupStatus({
    stage: 'verifying',
    progress: 90,
    message: 'Verifying runtime installation...',
    error: null,
  });

  const verify = verifyRuntimePython(getRuntimePythonAt(runtimeDir));
  if (!verify.ok) {
    setRuntimeSetupStatus({
      stage: 'error',
      progress: 100,
      message: 'Runtime verification failed',
      error: verify.error,
    });
    return false;
  }

  setRuntimeSetupStatus({
    stage: 'ready',
    progress: 100,
    message: 'Runtime setup complete',
    error: null,
  });
  return true;
}

/**
 * Find the Python interpreter
 * 
 * Search order:
 * 1. QMS_DAEMON_PYTHON environment variable (if set)
 * 2. .venv/bin/python (Unix/macOS) or .venv/Scripts/python.exe (Windows)
 * 3. [Reserved] compiled daemon binary lookup (future)
 * 4. runtime/bin/python (distribution runtime)
 * 5. Fallback to 'python' on PATH
 * 
 * @returns Object with path and whether it was found
 */
function findPythonPath(): { path: string; found: boolean; source: string } {
  const projectRoot = getProjectRoot();
  
  // 1. Check environment variable first
  if (process.env.QMS_DAEMON_PYTHON) {
    const envPath = process.env.QMS_DAEMON_PYTHON;
    if (fs.existsSync(envPath)) {
      return { path: envPath, found: true, source: 'QMS_DAEMON_PYTHON env var' };
    }
    console.warn(`[main] QMS_DAEMON_PYTHON set to ${envPath} but file not found`);
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

  // 3. Reserved for future compiled daemon binary.

  // 4. Runtime environment path (production distribution)
  const runtimePython = getRuntimePythonPath();
  if (fs.existsSync(runtimePython)) {
    return { path: runtimePython, found: true, source: 'runtime env' };
  }

  // 5. Fallback to system python
  console.warn('[main] No runtime/venv python found, falling back to system python');
  return { path: 'python', found: false, source: 'system PATH (fallback)' };
}

/**
 * Get the daemon module path
 * 
 * @returns Module path to run
 */
function getDaemonModule(): string {
  // Allow override via environment variable
  if (process.env.QMS_DAEMON_MODULE) {
    return process.env.QMS_DAEMON_MODULE;
  }
  return 'qmatsuite.daemon.server';
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
        QMATSUITE_ELECTRON: '1',
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
    const response: QMSResponse = JSON.parse(line);
    
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
async function sendDaemonRequest(request: QMSRequest): Promise<QMSResponse> {
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
 * Handle qms-request IPC from renderer
 */
ipcMain.handle('qms-request', async (_event, request: QMSRequest): Promise<QMSResponse> => {
  console.log(`[main] IPC request: ${request.type} (${request.id})`);

  if (process.env.E2E_TEST_MODE === 'true') {
    const mockedQueue = e2eRpcMocks.get(request.type);
    if (mockedQueue && mockedQueue.length > 0) {
      const mocked = mockedQueue.length > 1 ? mockedQueue.shift()! : mockedQueue[0];
      return {
        id: request.id,
        ok: mocked.ok,
        data: mocked.data,
        error: mocked.error,
      };
    }
  }
  
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
ipcMain.handle('qms-is-connected', async (): Promise<boolean> => {
  return daemonStatus.connected && daemonProcess !== null;
});

/**
 * Get daemon status including any startup errors
 */
ipcMain.handle('qms-daemon-status', async (): Promise<DaemonStatus> => {
  return { ...daemonStatus };
});

ipcMain.handle('qms-runtime-setup-status', async (): Promise<RuntimeSetupStatus> => {
  return { ...runtimeSetupStatus };
});

ipcMain.handle('qms-updater-state', async (): Promise<UpdaterState> => {
  return { ...updaterState };
});

ipcMain.handle('qms-check-for-updates', async (): Promise<{ ok: boolean; message?: string }> => {
  if (!isUpdaterEnabled()) {
    return { ok: false, message: 'Updater is disabled in this build' };
  }
  try {
    await autoUpdater.checkForUpdates();
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to check for updates';
    setUpdaterState({ state: 'error', message });
    return { ok: false, message };
  }
});

ipcMain.handle('qms-download-update', async (): Promise<{ ok: boolean; message?: string }> => {
  if (!isUpdaterEnabled()) {
    return { ok: false, message: 'Updater is disabled in this build' };
  }
  try {
    setUpdaterState({
      state: 'downloading',
      progress: 0,
      message: 'Preparing update download...',
    });
    await autoUpdater.downloadUpdate();
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to download update';
    setUpdaterState({ state: 'error', message });
    return { ok: false, message };
  }
});

ipcMain.handle('qms-quit-and-install-update', async (): Promise<{ ok: boolean; message?: string }> => {
  if (!isUpdaterEnabled()) {
    return { ok: false, message: 'Updater is disabled in this build' };
  }
  if (updaterState.state !== 'downloaded') {
    return { ok: false, message: 'No downloaded update is ready to install' };
  }
  try {
    setUpdaterState({ message: 'Restarting to install update...' });
    autoUpdater.quitAndInstall();
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to install update';
    setUpdaterState({ state: 'error', message });
    return { ok: false, message };
  }
});

ipcMain.handle('qms-e2e-set-updater-state', async (_event, state: Partial<UpdaterState>): Promise<void> => {
  if (process.env.E2E_TEST_MODE === 'true') {
    setUpdaterState(state);
  }
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
ipcMain.handle('qms-set-e2e-test-directory', async (_event, dir: string): Promise<void> => {
  if (process.env.E2E_TEST_MODE === 'true') {
    e2eTestDirectory = dir;
  }
});

ipcMain.handle(
  'qms-set-e2e-rpc-mock',
  async (
    _event,
    method: string,
    payload: E2ERpcMockResponse | E2ERpcMockResponse[] | null,
  ): Promise<void> => {
    if (process.env.E2E_TEST_MODE !== 'true') return;
    if (!method) return;
    if (payload === null) {
      e2eRpcMocks.delete(method);
      return;
    }
    const queue = Array.isArray(payload) ? payload : [payload];
    e2eRpcMocks.set(method, queue);
  },
);

ipcMain.handle('qms-clear-e2e-rpc-mocks', async (): Promise<void> => {
  if (process.env.E2E_TEST_MODE === 'true') {
    e2eRpcMocks.clear();
  }
});

ipcMain.handle('qms-open-directory', async (): Promise<string | null> => {
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
ipcMain.handle('qms-open-file', async (_event, options?: {
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
ipcMain.handle('qms-set-project', async (_event, projectPath: string | null): Promise<void> => {
  setCurrentProject(projectPath);
});

/**
 * Read logs from the project's log file
 */
ipcMain.handle('qms-read-logs', async (_event, projectPath: string, tailLines?: number): Promise<string[]> => {
  return readLogFile(projectPath, tailLines || 500);
});

/**
 * Reveal a file or folder in the native file manager (Finder/Explorer)
 */
ipcMain.handle('qms-reveal-path', async (_event, targetPath: string): Promise<boolean> => {
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
ipcMain.handle('qms-read-blob', async (_event, blobId: string, calcDir: string): Promise<ArrayBuffer> => {
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

/**
 * Read a file from the .scratch/ directory (secure, path-validated)
 *
 * Security:
 * 1. Validate relativePath starts with ".scratch/"
 * 2. Reject path traversal (..)
 * 3. Resolve realpath and verify it's within calcDir/.scratch/
 * 4. Read file and return ArrayBuffer
 */
ipcMain.handle('qms-read-scratch-file', async (_event, calcDir: string, relativePath: string): Promise<ArrayBuffer> => {
  try {
    // Validate relativePath starts with .scratch/
    if (!relativePath.startsWith('.scratch/') && !relativePath.startsWith('.scratch\\')) {
      throw new Error(`Path must start with .scratch/: ${relativePath}`);
    }

    // Reject path traversal
    if (relativePath.includes('..')) {
      throw new Error(`Path traversal detected: ${relativePath}`);
    }

    const calcPath = path.resolve(calcDir);
    const scratchDir = path.join(calcPath, '.scratch');
    const filePath = path.resolve(calcPath, relativePath);

    // Security check: ensure resolved path is within .scratch/
    const scratchDirResolved = path.resolve(scratchDir);
    if (!filePath.startsWith(scratchDirResolved)) {
      throw new Error(`Path traversal detected: ${filePath} is outside ${scratchDirResolved}`);
    }

    if (!fs.existsSync(filePath)) {
      throw new Error(`Scratch file not found: ${filePath}`);
    }

    const buffer = fs.readFileSync(filePath);
    return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  } catch (error) {
    console.error('[main] Failed to read scratch file:', error);
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
    safeSend('runtime-setup-status', { ...runtimeSetupStatus });
    safeSend('updater-state', { ...updaterState });
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
  configureAutoUpdater();
  createWindow();

  void (async () => {
    const runtimePrepared = await ensureRuntimeReady();
    const runtimeSetupFailed = runtimeSetupStatus.stage === 'error';

    if (runtimeSetupFailed && app.isPackaged) {
      const startupError = runtimeSetupStatus.error || 'Runtime setup failed';
      daemonStatus.startupError = startupError;
      daemonStatus.connected = false;
      safeSend('daemon-status', { ...daemonStatus });
      console.error(`[main] Runtime setup failed in packaged mode: ${startupError}`);
      return;
    }

    if (!runtimePrepared && !app.isPackaged) {
      console.log('[main] Runtime not prepared; continuing with development/system Python');
    }

    const daemonStarted = spawnDaemon();
    if (!daemonStarted) {
      console.error('[main] Failed to start daemon - continuing with UI');
    }

    if (isUpdaterEnabled()) {
      autoUpdater.checkForUpdates().catch(() => {
        // Silent by design: offline users should not see startup failures.
      });
    }
  })();
});
