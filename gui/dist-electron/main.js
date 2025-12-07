import { ipcMain, shell, app, BrowserWindow, dialog } from "electron";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
const __dirname$1 = path.dirname(fileURLToPath(import.meta.url));
process.env.APP_ROOT = path.join(__dirname$1, "..");
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const MAIN_DIST = path.join(process.env.APP_ROOT, "dist-electron");
const RENDERER_DIST = path.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, "public") : RENDERER_DIST;
let win = null;
let daemonProcess = null;
let daemonReadline = null;
const daemonStatus = {
  connected: false,
  startupError: null,
  pythonPath: null,
  projectRoot: null
};
const pendingRequests = /* @__PURE__ */ new Map();
const REQUEST_TIMEOUT_MS = 6e4;
let currentProjectPath = null;
const LOG_FILE_NAME = ".qv-daemon.log";
function safeSend(channel, ...args) {
  if (win && !win.isDestroyed() && win.webContents) {
    win.webContents.send(channel, ...args);
  }
}
function appendToLogFile(message) {
  if (!currentProjectPath) return;
  const logPath = path.join(currentProjectPath, LOG_FILE_NAME);
  const timestamp = (/* @__PURE__ */ new Date()).toISOString();
  const logLine = `[${timestamp}] ${message}
`;
  try {
    fs.appendFileSync(logPath, logLine);
  } catch (err) {
  }
}
function readLogFile(projectPath, tailLines = 500) {
  const logPath = path.join(projectPath, LOG_FILE_NAME);
  try {
    if (!fs.existsSync(logPath)) {
      return [];
    }
    const content = fs.readFileSync(logPath, "utf-8");
    const lines = content.split("\n").filter((line) => line.trim());
    return lines.slice(-tailLines);
  } catch (err) {
    return [];
  }
}
function setCurrentProject(projectPath) {
  currentProjectPath = projectPath;
}
function getProjectRoot() {
  if (process.env.QV_PROJECT_ROOT) {
    return process.env.QV_PROJECT_ROOT;
  }
  return path.resolve(__dirname$1, "..", "..");
}
function findPythonPath() {
  const projectRoot = getProjectRoot();
  if (process.env.QV_DAEMON_PYTHON) {
    const envPath = process.env.QV_DAEMON_PYTHON;
    if (fs.existsSync(envPath)) {
      return { path: envPath, found: true, source: "QV_DAEMON_PYTHON env var" };
    }
    console.warn(`[main] QV_DAEMON_PYTHON set to ${envPath} but file not found`);
  }
  const isWindows = process.platform === "win32";
  const venvCandidates = [
    // .venv (common convention)
    isWindows ? path.join(projectRoot, ".venv", "Scripts", "python.exe") : path.join(projectRoot, ".venv", "bin", "python"),
    // venv (alternative)
    isWindows ? path.join(projectRoot, "venv", "Scripts", "python.exe") : path.join(projectRoot, "venv", "bin", "python")
  ];
  for (const candidate of venvCandidates) {
    if (fs.existsSync(candidate)) {
      return { path: candidate, found: true, source: `venv at ${path.dirname(path.dirname(candidate))}` };
    }
  }
  console.warn("[main] No venv found, falling back to system python");
  return { path: "python", found: false, source: "system PATH (fallback)" };
}
function getDaemonModule() {
  if (process.env.QV_DAEMON_MODULE) {
    return process.env.QV_DAEMON_MODULE;
  }
  return "quantumvitas.daemon.server";
}
function spawnDaemon() {
  const pythonInfo = findPythonPath();
  const projectRoot = getProjectRoot();
  const daemonModule = getDaemonModule();
  daemonStatus.pythonPath = pythonInfo.path;
  daemonStatus.projectRoot = projectRoot;
  daemonStatus.startupError = null;
  console.log(`[main] Starting daemon:`);
  console.log(`[main]   Python: ${pythonInfo.path} (${pythonInfo.source})`);
  console.log(`[main]   Module: ${daemonModule}`);
  console.log(`[main]   CWD: ${projectRoot}`);
  try {
    daemonProcess = spawn(pythonInfo.path, ["-m", daemonModule], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (err) {
    const error = err;
    daemonStatus.startupError = `Failed to spawn daemon: ${error.message}`;
    console.error(`[main] ${daemonStatus.startupError}`);
    return false;
  }
  if (!daemonProcess.stdout || !daemonProcess.stdin) {
    daemonStatus.startupError = "Failed to create daemon stdio pipes";
    console.error(`[main] ${daemonStatus.startupError}`);
    return false;
  }
  daemonReadline = createInterface({
    input: daemonProcess.stdout,
    crlfDelay: Infinity
  });
  daemonReadline.on("line", (line) => {
    handleDaemonLine(line);
  });
  daemonProcess.stderr?.on("data", (data) => {
    const message = data.toString().trim();
    console.log(`[daemon] ${message}`);
    safeSend("daemon-log", message);
    appendToLogFile(message);
  });
  daemonProcess.on("error", (err) => {
    console.error("[main] Daemon process error:", err);
    daemonStatus.connected = false;
    daemonStatus.startupError = `Daemon error: ${err.message}`;
    safeSend("daemon-status", { ...daemonStatus });
  });
  daemonProcess.on("exit", (code, signal) => {
    console.log(`[main] Daemon exited with code ${code}, signal ${signal}`);
    daemonStatus.connected = false;
    if (code !== 0 && code !== null) {
      daemonStatus.startupError = `Daemon exited with code ${code}`;
    }
    daemonProcess = null;
    daemonReadline = null;
    for (const [_id, pending] of pendingRequests) {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error("Daemon process exited"));
    }
    pendingRequests.clear();
    safeSend("daemon-status", { ...daemonStatus });
  });
  daemonStatus.connected = true;
  return true;
}
function handleDaemonLine(line) {
  if (!line.trim()) return;
  try {
    const response = JSON.parse(line);
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
async function sendDaemonRequest(request) {
  if (!daemonProcess || !daemonProcess.stdin || !daemonStatus.connected) {
    return {
      id: request.id,
      ok: false,
      error: {
        code: "daemon_not_connected",
        message: daemonStatus.startupError || "Daemon process is not running"
      }
    };
  }
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      pendingRequests.delete(request.id);
      reject(new Error(`Request ${request.id} timed out after ${REQUEST_TIMEOUT_MS}ms`));
    }, REQUEST_TIMEOUT_MS);
    pendingRequests.set(request.id, { resolve, reject, timeoutId });
    const jsonLine = JSON.stringify(request) + "\n";
    daemonProcess.stdin.write(jsonLine, (err) => {
      if (err) {
        clearTimeout(timeoutId);
        pendingRequests.delete(request.id);
        reject(err);
      }
    });
  });
}
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
async function shutdownDaemon() {
  if (!daemonProcess || !daemonStatus.connected) return;
  const processToKill = daemonProcess;
  try {
    await sendDaemonRequest({
      id: `shutdown-${Date.now()}`,
      type: "shutdown",
      payload: {}
    });
  } catch (e) {
    console.log("[main] Shutdown command failed (may already be stopped)");
  }
  await delay(2e3);
  if (processToKill && !processToKill.killed) {
    console.log("[main] Force killing daemon");
    processToKill.kill("SIGTERM");
  }
}
ipcMain.handle("qv-request", async (_event, request) => {
  console.log(`[main] IPC request: ${request.type} (${request.id})`);
  try {
    const response = await sendDaemonRequest(request);
    console.log(`[main] IPC response: ${request.type} ok=${response.ok}`);
    return response;
  } catch (e) {
    const error = e;
    console.error(`[main] IPC error: ${request.type}`, error);
    return {
      id: request.id,
      ok: false,
      error: {
        code: "ipc_error",
        message: error.message
      }
    };
  }
});
ipcMain.handle("qv-is-connected", async () => {
  return daemonStatus.connected && daemonProcess !== null;
});
ipcMain.handle("qv-daemon-status", async () => {
  return { ...daemonStatus };
});
ipcMain.handle("qv-open-directory", async () => {
  if (!win) return null;
  const result = await dialog.showOpenDialog(win, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});
ipcMain.handle("qv-open-file", async (_event, options) => {
  if (!win) return null;
  const result = await dialog.showOpenDialog(win, {
    properties: ["openFile"],
    title: options?.title || "Select File",
    buttonLabel: "Select",
    filters: options?.filters || [
      { name: "Structure Files", extensions: ["cif", "json", "in", "xsf", "xyz", "poscar", "vasp"] },
      { name: "All Files", extensions: ["*"] }
    ]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});
ipcMain.handle("qv-set-project", async (_event, projectPath) => {
  setCurrentProject(projectPath);
});
ipcMain.handle("qv-read-logs", async (_event, projectPath, tailLines) => {
  return readLogFile(projectPath, tailLines || 500);
});
ipcMain.handle("qv-reveal-path", async (_event, targetPath) => {
  try {
    shell.showItemInFolder(targetPath);
    return true;
  } catch (e) {
    console.error("[main] Failed to reveal path:", e);
    return false;
  }
});
function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: path.join(__dirname$1, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  win.webContents.on("did-finish-load", () => {
    safeSend("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    });
    safeSend("daemon-status", { ...daemonStatus });
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }
}
let isQuitting = false;
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
app.on("before-quit", async (event) => {
  if (isQuitting) return;
  if (!daemonProcess) return;
  isQuitting = true;
  event.preventDefault();
  await shutdownDaemon();
  app.quit();
});
app.whenReady().then(() => {
  const daemonStarted = spawnDaemon();
  if (!daemonStarted) {
    console.error("[main] Failed to start daemon - continuing with UI");
  }
  createWindow();
});
export {
  MAIN_DIST,
  RENDERER_DIST,
  VITE_DEV_SERVER_URL
};
