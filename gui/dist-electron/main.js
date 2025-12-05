import { ipcMain, app, BrowserWindow } from "electron";
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
let daemonConnected = false;
const pendingRequests = /* @__PURE__ */ new Map();
const REQUEST_TIMEOUT_MS = 6e4;
function findPythonPath() {
  const projectRoot = path.resolve(__dirname$1, "..", "..");
  const candidates = [
    path.join(projectRoot, ".venv", "bin", "python"),
    path.join(projectRoot, ".venv", "Scripts", "python.exe"),
    // Windows
    path.join(projectRoot, "venv", "bin", "python"),
    path.join(projectRoot, "venv", "Scripts", "python.exe")
    // Windows
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  console.warn("[main] No venv found, falling back to system python");
  return "python";
}
function getProjectRoot() {
  return path.resolve(__dirname$1, "..", "..");
}
function spawnDaemon() {
  const pythonPath = findPythonPath();
  const projectRoot = getProjectRoot();
  console.log(`[main] Starting daemon with Python: ${pythonPath}`);
  console.log(`[main] Project root: ${projectRoot}`);
  daemonProcess = spawn(pythonPath, ["-m", "quantumvitas.daemon.server"], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1"
      // Ensure unbuffered output
    },
    stdio: ["pipe", "pipe", "pipe"]
  });
  if (!daemonProcess.stdout || !daemonProcess.stdin) {
    console.error("[main] Failed to create daemon stdio pipes");
    return;
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
    win?.webContents.send("daemon-log", message);
  });
  daemonProcess.on("error", (err) => {
    console.error("[main] Daemon process error:", err);
    daemonConnected = false;
  });
  daemonProcess.on("exit", (code, signal) => {
    console.log(`[main] Daemon exited with code ${code}, signal ${signal}`);
    daemonConnected = false;
    daemonProcess = null;
    daemonReadline = null;
    for (const [_id, pending] of pendingRequests) {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error("Daemon process exited"));
    }
    pendingRequests.clear();
  });
  daemonConnected = true;
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
  if (!daemonProcess || !daemonProcess.stdin || !daemonConnected) {
    return {
      id: request.id,
      ok: false,
      error: {
        code: "daemon_not_connected",
        message: "Daemon process is not running"
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
async function shutdownDaemon() {
  if (!daemonProcess || !daemonConnected) return;
  try {
    await sendDaemonRequest({
      id: `shutdown-${Date.now()}`,
      type: "shutdown",
      payload: {}
    });
  } catch (e) {
  }
  setTimeout(() => {
    if (daemonProcess) {
      daemonProcess.kill("SIGTERM");
    }
  }, 2e3);
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
  return daemonConnected && daemonProcess !== null;
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
    // Modern frameless window with custom titlebar (optional)
    // titleBarStyle: 'hiddenInset',
    // frame: false,
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString(),
      daemonConnected
    });
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }
}
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
  if (!daemonProcess) return;
  event.preventDefault();
  await shutdownDaemon();
  app.quit();
});
app.whenReady().then(() => {
  spawnDaemon();
  createWindow();
});
export {
  MAIN_DIST,
  RENDERER_DIST,
  VITE_DEV_SERVER_URL
};
