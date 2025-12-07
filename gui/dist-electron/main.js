import { ipcMain as d, app as u, BrowserWindow as E, dialog as D } from "electron";
import { spawn as I } from "node:child_process";
import { createInterface as j } from "node:readline";
import { fileURLToPath as M } from "node:url";
import s from "node:path";
import f from "node:fs";
const y = s.dirname(M(import.meta.url));
process.env.APP_ROOT = s.join(y, "..");
const v = process.env.VITE_DEV_SERVER_URL, B = s.join(process.env.APP_ROOT, "dist-electron"), O = s.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = v ? s.join(process.env.APP_ROOT, "public") : O;
let a = null, i = null, h = null;
const r = {
  connected: !1,
  startupError: null,
  pythonPath: null,
  projectRoot: null
}, l = /* @__PURE__ */ new Map(), _ = 6e4;
let g = null;
const R = ".qv-daemon.log";
function m(e, ...n) {
  a && !a.isDestroyed() && a.webContents && a.webContents.send(e, ...n);
}
function N(e) {
  if (!g) return;
  const n = s.join(g, R), o = `[${(/* @__PURE__ */ new Date()).toISOString()}] ${e}
`;
  try {
    f.appendFileSync(n, o);
  } catch {
  }
}
function b(e, n = 500) {
  const t = s.join(e, R);
  try {
    return f.existsSync(t) ? f.readFileSync(t, "utf-8").split(`
`).filter((p) => p.trim()).slice(-n) : [];
  } catch {
    return [];
  }
}
function F(e) {
  g = e;
}
function T() {
  return process.env.QV_PROJECT_ROOT ? process.env.QV_PROJECT_ROOT : s.resolve(y, "..", "..");
}
function L() {
  const e = T();
  if (process.env.QV_DAEMON_PYTHON) {
    const o = process.env.QV_DAEMON_PYTHON;
    if (f.existsSync(o))
      return { path: o, found: !0, source: "QV_DAEMON_PYTHON env var" };
    console.warn(`[main] QV_DAEMON_PYTHON set to ${o} but file not found`);
  }
  const n = process.platform === "win32", t = [
    // .venv (common convention)
    n ? s.join(e, ".venv", "Scripts", "python.exe") : s.join(e, ".venv", "bin", "python"),
    // venv (alternative)
    n ? s.join(e, "venv", "Scripts", "python.exe") : s.join(e, "venv", "bin", "python")
  ];
  for (const o of t)
    if (f.existsSync(o))
      return { path: o, found: !0, source: `venv at ${s.dirname(s.dirname(o))}` };
  return console.warn("[main] No venv found, falling back to system python"), { path: "python", found: !1, source: "system PATH (fallback)" };
}
function x() {
  return process.env.QV_DAEMON_MODULE ? process.env.QV_DAEMON_MODULE : "quantumvitas.daemon.server";
}
function V() {
  const e = L(), n = T(), t = x();
  r.pythonPath = e.path, r.projectRoot = n, r.startupError = null, console.log("[main] Starting daemon:"), console.log(`[main]   Python: ${e.path} (${e.source})`), console.log(`[main]   Module: ${t}`), console.log(`[main]   CWD: ${n}`);
  try {
    i = I(e.path, ["-m", t], {
      cwd: n,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (o) {
    const c = o;
    return r.startupError = `Failed to spawn daemon: ${c.message}`, console.error(`[main] ${r.startupError}`), !1;
  }
  return !i.stdout || !i.stdin ? (r.startupError = "Failed to create daemon stdio pipes", console.error(`[main] ${r.startupError}`), !1) : (h = j({
    input: i.stdout,
    crlfDelay: 1 / 0
  }), h.on("line", (o) => {
    A(o);
  }), i.stderr?.on("data", (o) => {
    const c = o.toString().trim();
    console.log(`[daemon] ${c}`), m("daemon-log", c), N(c);
  }), i.on("error", (o) => {
    console.error("[main] Daemon process error:", o), r.connected = !1, r.startupError = `Daemon error: ${o.message}`, m("daemon-status", { ...r });
  }), i.on("exit", (o, c) => {
    console.log(`[main] Daemon exited with code ${o}, signal ${c}`), r.connected = !1, o !== 0 && o !== null && (r.startupError = `Daemon exited with code ${o}`), i = null, h = null;
    for (const [p, w] of l)
      clearTimeout(w.timeoutId), w.reject(new Error("Daemon process exited"));
    l.clear(), m("daemon-status", { ...r });
  }), r.connected = !0, !0);
}
function A(e) {
  if (e.trim())
    try {
      const n = JSON.parse(e), t = l.get(n.id);
      t ? (clearTimeout(t.timeoutId), l.delete(n.id), t.resolve(n)) : console.warn(`[main] Received response for unknown request: ${n.id}`);
    } catch (n) {
      console.error(`[main] Failed to parse daemon response: ${e}`), console.error(n);
    }
}
async function S(e) {
  return !i || !i.stdin || !r.connected ? {
    id: e.id,
    ok: !1,
    error: {
      code: "daemon_not_connected",
      message: r.startupError || "Daemon process is not running"
    }
  } : new Promise((n, t) => {
    const o = setTimeout(() => {
      l.delete(e.id), t(new Error(`Request ${e.id} timed out after ${_}ms`));
    }, _);
    l.set(e.id, { resolve: n, reject: t, timeoutId: o });
    const c = JSON.stringify(e) + `
`;
    i.stdin.write(c, (p) => {
      p && (clearTimeout(o), l.delete(e.id), t(p));
    });
  });
}
function C(e) {
  return new Promise((n) => setTimeout(n, e));
}
async function U() {
  if (!i || !r.connected) return;
  const e = i;
  try {
    await S({
      id: `shutdown-${Date.now()}`,
      type: "shutdown",
      payload: {}
    });
  } catch {
    console.log("[main] Shutdown command failed (may already be stopped)");
  }
  await C(2e3), e && !e.killed && (console.log("[main] Force killing daemon"), e.kill("SIGTERM"));
}
d.handle("qv-request", async (e, n) => {
  console.log(`[main] IPC request: ${n.type} (${n.id})`);
  try {
    const t = await S(n);
    return console.log(`[main] IPC response: ${n.type} ok=${t.ok}`), t;
  } catch (t) {
    const o = t;
    return console.error(`[main] IPC error: ${n.type}`, o), {
      id: n.id,
      ok: !1,
      error: {
        code: "ipc_error",
        message: o.message
      }
    };
  }
});
d.handle("qv-is-connected", async () => r.connected && i !== null);
d.handle("qv-daemon-status", async () => ({ ...r }));
d.handle("qv-open-directory", async () => {
  if (!a) return null;
  const e = await D.showOpenDialog(a, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  return e.canceled || e.filePaths.length === 0 ? null : e.filePaths[0];
});
d.handle("qv-open-file", async (e, n) => {
  if (!a) return null;
  const t = await D.showOpenDialog(a, {
    properties: ["openFile"],
    title: n?.title || "Select File",
    buttonLabel: "Select",
    filters: n?.filters || [
      { name: "Structure Files", extensions: ["cif", "json", "in", "xsf", "xyz", "poscar", "vasp"] },
      { name: "All Files", extensions: ["*"] }
    ]
  });
  return t.canceled || t.filePaths.length === 0 ? null : t.filePaths[0];
});
d.handle("qv-set-project", async (e, n) => {
  F(n);
});
d.handle("qv-read-logs", async (e, n, t) => b(n, t || 500));
function $() {
  a = new E({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: s.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: s.join(y, "preload.mjs"),
      contextIsolation: !0,
      nodeIntegration: !1
    }
  }), a.webContents.on("did-finish-load", () => {
    m("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }), m("daemon-status", { ...r });
  }), v ? (a.loadURL(v), a.webContents.openDevTools()) : a.loadFile(s.join(O, "index.html"));
}
let P = !1;
u.on("window-all-closed", () => {
  process.platform !== "darwin" && u.quit();
});
u.on("activate", () => {
  E.getAllWindows().length === 0 && $();
});
u.on("before-quit", async (e) => {
  P || i && (P = !0, e.preventDefault(), await U(), u.quit());
});
u.whenReady().then(() => {
  V() || console.error("[main] Failed to start daemon - continuing with UI"), $();
});
export {
  B as MAIN_DIST,
  O as RENDERER_DIST,
  v as VITE_DEV_SERVER_URL
};
