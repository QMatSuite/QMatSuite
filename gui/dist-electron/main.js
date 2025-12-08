import { ipcMain as l, shell as j, app as u, BrowserWindow as T, dialog as D } from "electron";
import { spawn as M } from "node:child_process";
import { createInterface as N } from "node:readline";
import { fileURLToPath as L } from "node:url";
import s from "node:path";
import p from "node:fs";
const g = s.dirname(L(import.meta.url));
process.env.APP_ROOT = s.join(g, "..");
const E = process.env.VITE_DEV_SERVER_URL, J = s.join(process.env.APP_ROOT, "dist-electron"), O = s.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = E ? s.join(process.env.APP_ROOT, "public") : O;
let a = null, i = null, v = null;
const r = {
  connected: !1,
  startupError: null,
  pythonPath: null,
  projectRoot: null
}, d = /* @__PURE__ */ new Map(), w = 6e4;
let y = null;
const R = ".qv-daemon.log";
function f(e, ...n) {
  a && !a.isDestroyed() && a.webContents && a.webContents.send(e, ...n);
}
function F(e) {
  if (!y) return;
  const n = s.join(y, R), t = `[${(/* @__PURE__ */ new Date()).toISOString()}] ${e}
`;
  try {
    p.appendFileSync(n, t);
  } catch {
  }
}
function b(e, n = 500) {
  const o = s.join(e, R);
  try {
    return p.existsSync(o) ? p.readFileSync(o, "utf-8").split(`
`).filter((m) => m.trim()).slice(-n) : [];
  } catch {
    return [];
  }
}
function x(e) {
  y = e;
}
function S() {
  return process.env.QV_PROJECT_ROOT ? process.env.QV_PROJECT_ROOT : s.resolve(g, "..", "..");
}
function C() {
  const e = S();
  if (process.env.QV_DAEMON_PYTHON) {
    const t = process.env.QV_DAEMON_PYTHON;
    if (p.existsSync(t))
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
    if (p.existsSync(t))
      return { path: t, found: !0, source: `venv at ${s.dirname(s.dirname(t))}` };
  return console.warn("[main] No venv found, falling back to system python"), { path: "python", found: !1, source: "system PATH (fallback)" };
}
function V() {
  return process.env.QV_DAEMON_MODULE ? process.env.QV_DAEMON_MODULE : "quantumvitas.daemon.server";
}
function A() {
  const e = C(), n = S(), o = V();
  r.pythonPath = e.path, r.projectRoot = n, r.startupError = null, console.log("[main] Starting daemon:"), console.log(`[main]   Python: ${e.path} (${e.source})`), console.log(`[main]   Module: ${o}`), console.log(`[main]   CWD: ${n}`);
  try {
    i = M(e.path, ["-m", o], {
      cwd: n,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (t) {
    const c = t;
    return r.startupError = `Failed to spawn daemon: ${c.message}`, console.error(`[main] ${r.startupError}`), !1;
  }
  return !i.stdout || !i.stdin ? (r.startupError = "Failed to create daemon stdio pipes", console.error(`[main] ${r.startupError}`), !1) : (v = N({
    input: i.stdout,
    crlfDelay: 1 / 0
  }), v.on("line", (t) => {
    U(t);
  }), i.stderr?.on("data", (t) => {
    const c = t.toString().trim();
    console.log(`[daemon] ${c}`), f("daemon-log", c), F(c);
  }), i.on("error", (t) => {
    console.error("[main] Daemon process error:", t), r.connected = !1, r.startupError = `Daemon error: ${t.message}`, f("daemon-status", { ...r });
  }), i.on("exit", (t, c) => {
    console.log(`[main] Daemon exited with code ${t}, signal ${c}`), r.connected = !1, t !== 0 && t !== null && (r.startupError = `Daemon exited with code ${t}`), i = null, v = null;
    for (const [m, _] of d)
      clearTimeout(_.timeoutId), _.reject(new Error("Daemon process exited"));
    d.clear(), f("daemon-status", { ...r });
  }), r.connected = !0, !0);
}
function U(e) {
  if (e.trim())
    try {
      const n = JSON.parse(e), o = d.get(n.id);
      o ? (clearTimeout(o.timeoutId), d.delete(n.id), o.resolve(n)) : console.warn(`[main] Received response for unknown request: ${n.id}`);
    } catch (n) {
      console.error(`[main] Failed to parse daemon response: ${e}`), console.error(n);
    }
}
async function I(e) {
  return !i || !i.stdin || !r.connected ? {
    id: e.id,
    ok: !1,
    error: {
      code: "daemon_not_connected",
      message: r.startupError || "Daemon process is not running"
    }
  } : new Promise((n, o) => {
    const t = setTimeout(() => {
      d.delete(e.id), o(new Error(`Request ${e.id} timed out after ${w}ms`));
    }, w);
    d.set(e.id, { resolve: n, reject: o, timeoutId: t });
    const c = JSON.stringify(e) + `
`;
    i.stdin.write(c, (m) => {
      m && (clearTimeout(t), d.delete(e.id), o(m));
    });
  });
}
function k(e) {
  return new Promise((n) => setTimeout(n, e));
}
async function q() {
  if (!i || !r.connected) return;
  const e = i;
  try {
    await I({
      id: `shutdown-${Date.now()}`,
      type: "shutdown",
      payload: {}
    });
  } catch {
    console.log("[main] Shutdown command failed (may already be stopped)");
  }
  await k(2e3), e && !e.killed && (console.log("[main] Force killing daemon"), e.kill("SIGTERM"));
}
l.handle("qv-request", async (e, n) => {
  console.log(`[main] IPC request: ${n.type} (${n.id})`);
  try {
    const o = await I(n);
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
l.handle("qv-is-connected", async () => r.connected && i !== null);
l.handle("qv-daemon-status", async () => ({ ...r }));
let h = null;
l.handle("qv-set-e2e-test-directory", async (e, n) => {
  process.env.E2E_TEST_MODE === "true" && (h = n);
});
l.handle("qv-open-directory", async () => {
  if (!a) return null;
  if (process.env.E2E_TEST_MODE === "true" && h) {
    const n = h;
    if (h = null, p.existsSync(n))
      return n;
  }
  const e = await D.showOpenDialog(a, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  return e.canceled || e.filePaths.length === 0 ? null : e.filePaths[0];
});
l.handle("qv-open-file", async (e, n) => {
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
l.handle("qv-set-project", async (e, n) => {
  x(n);
});
l.handle("qv-read-logs", async (e, n, o) => b(n, o || 500));
l.handle("qv-reveal-path", async (e, n) => {
  try {
    return j.showItemInFolder(n), !0;
  } catch (o) {
    return console.error("[main] Failed to reveal path:", o), !1;
  }
});
if (process.env.ELECTRON_REMOTE_DEBUG_PORT) {
  const e = parseInt(process.env.ELECTRON_REMOTE_DEBUG_PORT, 10);
  isNaN(e) || u.commandLine.appendSwitch("remote-debugging-port", e.toString());
}
function $() {
  a = new T({
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
    f("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }), f("daemon-status", { ...r });
  }), E ? (a.loadURL(E), a.webContents.openDevTools()) : a.loadFile(s.join(O, "index.html"));
}
let P = !1;
u.on("window-all-closed", () => {
  process.platform !== "darwin" && u.quit();
});
u.on("activate", () => {
  T.getAllWindows().length === 0 && $();
});
u.on("before-quit", async (e) => {
  P || i && (P = !0, e.preventDefault(), await q(), u.quit());
});
u.whenReady().then(() => {
  A() || console.error("[main] Failed to start daemon - continuing with UI"), $();
});
export {
  J as MAIN_DIST,
  O as RENDERER_DIST,
  E as VITE_DEV_SERVER_URL
};
