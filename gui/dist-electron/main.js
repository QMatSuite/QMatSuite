import { ipcMain as c, shell as $, app as u, BrowserWindow as E, dialog as D } from "electron";
import { spawn as j } from "node:child_process";
import { createInterface as F } from "node:readline";
import { fileURLToPath as M } from "node:url";
import s from "node:path";
import f from "node:fs";
const g = s.dirname(M(import.meta.url));
process.env.APP_ROOT = s.join(g, "..");
const v = process.env.VITE_DEV_SERVER_URL, J = s.join(process.env.APP_ROOT, "dist-electron"), O = s.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = v ? s.join(process.env.APP_ROOT, "public") : O;
let a = null, i = null, h = null;
const r = {
  connected: !1,
  startupError: null,
  pythonPath: null,
  projectRoot: null
}, d = /* @__PURE__ */ new Map(), _ = 6e4;
let y = null;
const R = ".qv-daemon.log";
function m(e, ...n) {
  a && !a.isDestroyed() && a.webContents && a.webContents.send(e, ...n);
}
function N(e) {
  if (!y) return;
  const n = s.join(y, R), t = `[${(/* @__PURE__ */ new Date()).toISOString()}] ${e}
`;
  try {
    f.appendFileSync(n, t);
  } catch {
  }
}
function b(e, n = 500) {
  const o = s.join(e, R);
  try {
    return f.existsSync(o) ? f.readFileSync(o, "utf-8").split(`
`).filter((p) => p.trim()).slice(-n) : [];
  } catch {
    return [];
  }
}
function L(e) {
  y = e;
}
function T() {
  return process.env.QV_PROJECT_ROOT ? process.env.QV_PROJECT_ROOT : s.resolve(g, "..", "..");
}
function x() {
  const e = T();
  if (process.env.QV_DAEMON_PYTHON) {
    const t = process.env.QV_DAEMON_PYTHON;
    if (f.existsSync(t))
      return { path: t, found: !0, source: "QV_DAEMON_PYTHON env var" };
    console.warn(`[main] QV_DAEMON_PYTHON set to ${t} but file not found`);
  }
  const n = process.platform === "win32", o = [
    // .venv (common convention)
    n ? s.join(e, ".venv", "Scripts", "python.exe") : s.join(e, ".venv", "bin", "python"),
    // venv (alternative)
    n ? s.join(e, "venv", "Scripts", "python.exe") : s.join(e, "venv", "bin", "python")
  ];
  for (const t of o)
    if (f.existsSync(t))
      return { path: t, found: !0, source: `venv at ${s.dirname(s.dirname(t))}` };
  return console.warn("[main] No venv found, falling back to system python"), { path: "python", found: !1, source: "system PATH (fallback)" };
}
function V() {
  return process.env.QV_DAEMON_MODULE ? process.env.QV_DAEMON_MODULE : "quantumvitas.daemon.server";
}
function A() {
  const e = x(), n = T(), o = V();
  r.pythonPath = e.path, r.projectRoot = n, r.startupError = null, console.log("[main] Starting daemon:"), console.log(`[main]   Python: ${e.path} (${e.source})`), console.log(`[main]   Module: ${o}`), console.log(`[main]   CWD: ${n}`);
  try {
    i = j(e.path, ["-m", o], {
      cwd: n,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (t) {
    const l = t;
    return r.startupError = `Failed to spawn daemon: ${l.message}`, console.error(`[main] ${r.startupError}`), !1;
  }
  return !i.stdout || !i.stdin ? (r.startupError = "Failed to create daemon stdio pipes", console.error(`[main] ${r.startupError}`), !1) : (h = F({
    input: i.stdout,
    crlfDelay: 1 / 0
  }), h.on("line", (t) => {
    C(t);
  }), i.stderr?.on("data", (t) => {
    const l = t.toString().trim();
    console.log(`[daemon] ${l}`), m("daemon-log", l), N(l);
  }), i.on("error", (t) => {
    console.error("[main] Daemon process error:", t), r.connected = !1, r.startupError = `Daemon error: ${t.message}`, m("daemon-status", { ...r });
  }), i.on("exit", (t, l) => {
    console.log(`[main] Daemon exited with code ${t}, signal ${l}`), r.connected = !1, t !== 0 && t !== null && (r.startupError = `Daemon exited with code ${t}`), i = null, h = null;
    for (const [p, w] of d)
      clearTimeout(w.timeoutId), w.reject(new Error("Daemon process exited"));
    d.clear(), m("daemon-status", { ...r });
  }), r.connected = !0, !0);
}
function C(e) {
  if (e.trim())
    try {
      const n = JSON.parse(e), o = d.get(n.id);
      o ? (clearTimeout(o.timeoutId), d.delete(n.id), o.resolve(n)) : console.warn(`[main] Received response for unknown request: ${n.id}`);
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
  } : new Promise((n, o) => {
    const t = setTimeout(() => {
      d.delete(e.id), o(new Error(`Request ${e.id} timed out after ${_}ms`));
    }, _);
    d.set(e.id, { resolve: n, reject: o, timeoutId: t });
    const l = JSON.stringify(e) + `
`;
    i.stdin.write(l, (p) => {
      p && (clearTimeout(t), d.delete(e.id), o(p));
    });
  });
}
function U(e) {
  return new Promise((n) => setTimeout(n, e));
}
async function k() {
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
  await U(2e3), e && !e.killed && (console.log("[main] Force killing daemon"), e.kill("SIGTERM"));
}
c.handle("qv-request", async (e, n) => {
  console.log(`[main] IPC request: ${n.type} (${n.id})`);
  try {
    const o = await S(n);
    return console.log(`[main] IPC response: ${n.type} ok=${o.ok}`), o;
  } catch (o) {
    const t = o;
    return console.error(`[main] IPC error: ${n.type}`, t), {
      id: n.id,
      ok: !1,
      error: {
        code: "ipc_error",
        message: t.message
      }
    };
  }
});
c.handle("qv-is-connected", async () => r.connected && i !== null);
c.handle("qv-daemon-status", async () => ({ ...r }));
c.handle("qv-open-directory", async () => {
  if (!a) return null;
  const e = await D.showOpenDialog(a, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  return e.canceled || e.filePaths.length === 0 ? null : e.filePaths[0];
});
c.handle("qv-open-file", async (e, n) => {
  if (!a) return null;
  const o = await D.showOpenDialog(a, {
    properties: ["openFile"],
    title: n?.title || "Select File",
    buttonLabel: "Select",
    filters: n?.filters || [
      { name: "Structure Files", extensions: ["cif", "json", "in", "xsf", "xyz", "poscar", "vasp"] },
      { name: "All Files", extensions: ["*"] }
    ]
  });
  return o.canceled || o.filePaths.length === 0 ? null : o.filePaths[0];
});
c.handle("qv-set-project", async (e, n) => {
  L(n);
});
c.handle("qv-read-logs", async (e, n, o) => b(n, o || 500));
c.handle("qv-reveal-path", async (e, n) => {
  try {
    return $.showItemInFolder(n), !0;
  } catch (o) {
    return console.error("[main] Failed to reveal path:", o), !1;
  }
});
function I() {
  a = new E({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: s.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: s.join(g, "preload.mjs"),
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
  E.getAllWindows().length === 0 && I();
});
u.on("before-quit", async (e) => {
  P || i && (P = !0, e.preventDefault(), await k(), u.quit());
});
u.whenReady().then(() => {
  A() || console.error("[main] Failed to start daemon - continuing with UI"), I();
});
export {
  J as MAIN_DIST,
  O as RENDERER_DIST,
  v as VITE_DEV_SERVER_URL
};
