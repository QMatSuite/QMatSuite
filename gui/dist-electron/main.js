import { ipcMain as l, shell as N, app as p, BrowserWindow as $, dialog as S } from "electron";
import { spawn as F } from "node:child_process";
import { createInterface as b } from "node:readline";
import { fileURLToPath as x } from "node:url";
import i from "node:path";
import g from "node:fs";
const _ = i.dirname(x(import.meta.url));
process.env.APP_ROOT = i.join(_, "..");
const E = process.env.VITE_DEV_SERVER_URL, z = i.join(process.env.APP_ROOT, "dist-electron"), R = i.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = E ? i.join(process.env.APP_ROOT, "public") : R;
let c = null, a = null, y = null;
const s = {
  connected: !1,
  startupError: null,
  pythonPath: null,
  projectRoot: null
}, m = /* @__PURE__ */ new Map(), P = 6e4;
let v = null;
const I = ".qv-daemon.log";
function h(e, ...n) {
  c && !c.isDestroyed() && c.webContents && c.webContents.send(e, ...n);
}
function k(e) {
  if (!v) return;
  const n = i.join(v, I), t = `[${(/* @__PURE__ */ new Date()).toISOString()}] ${e}
`;
  try {
    g.appendFileSync(n, t);
  } catch {
  }
}
function C(e, n = 500) {
  const o = i.join(e, I);
  try {
    return g.existsSync(o) ? g.readFileSync(o, "utf-8").split(`
`).filter((u) => u.trim()).slice(-n) : [];
  } catch {
    return [];
  }
}
function A(e) {
  v = e;
}
function M() {
  return process.env.QV_PROJECT_ROOT ? process.env.QV_PROJECT_ROOT : i.resolve(_, "..", "..");
}
function V() {
  const e = M();
  if (process.env.QV_DAEMON_PYTHON) {
    const t = process.env.QV_DAEMON_PYTHON;
    if (g.existsSync(t))
      return { path: t, found: !0, source: "QV_DAEMON_PYTHON env var" };
    console.warn(`[main] QV_DAEMON_PYTHON set to ${t} but file not found`);
  }
  const n = process.platform === "win32", o = [
    // .venv (common convention)
    n ? i.join(e, ".venv", "Scripts", "python.exe") : i.join(e, ".venv", "bin", "python"),
    // venv (alternative)
    n ? i.join(e, "venv", "Scripts", "python.exe") : i.join(e, "venv", "bin", "python")
  ];
  for (const t of o)
    if (g.existsSync(t))
      return { path: t, found: !0, source: `venv at ${i.dirname(i.dirname(t))}` };
  return console.warn("[main] No venv found, falling back to system python"), { path: "python", found: !1, source: "system PATH (fallback)" };
}
function U() {
  return process.env.QV_DAEMON_MODULE ? process.env.QV_DAEMON_MODULE : "quantumvitas.daemon.server";
}
function Q() {
  const e = V(), n = M(), o = U();
  s.pythonPath = e.path, s.projectRoot = n, s.startupError = null, console.log("[main] Starting daemon:"), console.log(`[main]   Python: ${e.path} (${e.source})`), console.log(`[main]   Module: ${o}`), console.log(`[main]   CWD: ${n}`);
  try {
    a = F(e.path, ["-m", o], {
      cwd: n,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      // Use independent pipes - daemon's stdio is not tied to Electron's stdin
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (t) {
    const r = t;
    return s.startupError = `Failed to spawn daemon: ${r.message}`, console.error(`[main] ${s.startupError}`), !1;
  }
  return !a.stdout || !a.stdin ? (s.startupError = "Failed to create daemon stdio pipes", console.error(`[main] ${s.startupError}`), !1) : (y = b({
    input: a.stdout,
    crlfDelay: 1 / 0
  }), y.on("line", (t) => {
    q(t);
  }), a.stderr?.on("data", (t) => {
    const r = t.toString().trim();
    console.log(`[daemon] ${r}`), process.stderr.write(`[daemon stderr] ${r}
`), h("daemon-log", r), k(r);
  }), a.stdout?.on("data", (t) => {
    const r = t.toString().trim();
    r && !r.trim().startsWith("{") && (console.log(`[daemon stdout] ${r}`), process.stderr.write(`[daemon stdout] ${r}
`));
  }), a.on("error", (t) => {
    const r = `[main] Daemon process error: ${t.message}`;
    console.error(r), process.stderr.write(`${r}
`), s.connected = !1, s.startupError = `Daemon error: ${t.message}`, h("daemon-status", { ...s });
  }), a.on("exit", (t, r) => {
    const u = `[main] Daemon exited with code ${t}, signal ${r}`;
    console.log(u), process.stderr.write(`${u}
`), s.connected = !1, t !== 0 && t !== null && (s.startupError = `Daemon exited with code ${t}`, process.stderr.write(`[main] Daemon exit error: ${s.startupError}
`)), a = null, y = null;
    for (const [f, d] of m)
      clearTimeout(d.timeoutId), d.reject(new Error("Daemon process exited"));
    m.clear(), h("daemon-status", { ...s });
  }), s.connected = !0, !0);
}
function q(e) {
  if (e.trim())
    try {
      const n = JSON.parse(e), o = m.get(n.id);
      o ? (clearTimeout(o.timeoutId), m.delete(n.id), o.resolve(n)) : console.warn(`[main] Received response for unknown request: ${n.id}`);
    } catch (n) {
      console.error(`[main] Failed to parse daemon response: ${e}`), console.error(n);
    }
}
async function j(e) {
  if (!a || !a.stdin || !s.connected)
    return {
      id: e.id,
      ok: !1,
      error: {
        code: "daemon_not_connected",
        message: s.startupError || "Daemon process is not running"
      }
    };
  const n = a.stdin;
  if (n.destroyed || n.writableEnded) {
    const o = `[main] Cannot write to daemon: stdin is ${n.destroyed ? "destroyed" : "ended"}`;
    return console.error(o), process.stderr.write(`${o}
`), {
      id: e.id,
      ok: !1,
      error: {
        code: "daemon_stdin_closed",
        message: "Daemon stdin pipe is closed"
      }
    };
  }
  return new Promise((o, t) => {
    const r = setTimeout(() => {
      m.delete(e.id), t(new Error(`Request ${e.id} timed out after ${P}ms`));
    }, P);
    m.set(e.id, { resolve: o, reject: t, timeoutId: r });
    const u = JSON.stringify(e) + `
`;
    try {
      n.write(u, (f) => {
        if (f) {
          clearTimeout(r), m.delete(e.id);
          const d = `[main] Failed to write to daemon stdin: ${f.message}`;
          console.error(d), process.stderr.write(`${d}
`), o({
            id: e.id,
            ok: !1,
            error: {
              code: "write_error",
              message: f.message
            }
          });
        }
      });
    } catch (f) {
      clearTimeout(r), m.delete(e.id);
      const d = f, D = `[main] Exception writing to daemon stdin: ${d.message}`;
      console.error(D), process.stderr.write(`${D}
`), o({
        id: e.id,
        ok: !1,
        error: {
          code: "write_exception",
          message: d.message
        }
      });
    }
  });
}
function T(e) {
  return new Promise((n) => setTimeout(n, e));
}
async function H() {
  if (!a) {
    console.log("[main] No daemon process to shutdown");
    return;
  }
  const e = a;
  console.log("[main] Shutting down daemon...");
  try {
    if (s.connected && e.stdin && !e.stdin.destroyed && !e.stdin.writableEnded) {
      try {
        await j({
          id: `shutdown-${Date.now()}`,
          type: "shutdown",
          payload: {}
        });
      } catch {
        console.log("[main] Shutdown command failed (daemon may already be stopped)");
      }
      await T(2e3);
    } else
      console.log("[main] Daemon stdin not available, skipping graceful shutdown");
  } catch {
    console.log("[main] Error during graceful shutdown, proceeding to kill");
  }
  if (e && !e.killed && e.pid) {
    console.log("[main] Force killing daemon");
    try {
      e.kill("SIGTERM"), await T(1e3), !e.killed && e.pid && (console.log("[main] Daemon still running, using SIGKILL"), e.kill("SIGKILL"));
    } catch (n) {
      const o = n;
      console.error(`[main] Failed to kill daemon: ${o.message}`), process.stderr.write(`[main] Failed to kill daemon: ${o.message}
`);
    }
  }
}
l.handle("qv-request", async (e, n) => {
  console.log(`[main] IPC request: ${n.type} (${n.id})`);
  try {
    const o = await j(n);
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
l.handle("qv-is-connected", async () => s.connected && a !== null);
l.handle("qv-daemon-status", async () => ({ ...s }));
let w = null;
l.handle("qv-set-e2e-test-directory", async (e, n) => {
  process.env.E2E_TEST_MODE === "true" && (w = n);
});
l.handle("qv-open-directory", async () => {
  if (!c) return null;
  if (process.env.E2E_TEST_MODE === "true" && w) {
    const n = w;
    if (w = null, g.existsSync(n))
      return n;
  }
  const e = await S.showOpenDialog(c, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  return e.canceled || e.filePaths.length === 0 ? null : e.filePaths[0];
});
l.handle("qv-open-file", async (e, n) => {
  if (!c) return null;
  const o = await S.showOpenDialog(c, {
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
  A(n);
});
l.handle("qv-read-logs", async (e, n, o) => C(n, o || 500));
l.handle("qv-reveal-path", async (e, n) => {
  try {
    return N.showItemInFolder(n), !0;
  } catch (o) {
    return console.error("[main] Failed to reveal path:", o), !1;
  }
});
if (process.env.ELECTRON_REMOTE_DEBUG_PORT) {
  const e = parseInt(process.env.ELECTRON_REMOTE_DEBUG_PORT, 10);
  isNaN(e) || p.commandLine.appendSwitch("remote-debugging-port", e.toString());
}
function L() {
  c = new $({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: i.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: i.join(_, "preload.mjs"),
      contextIsolation: !0,
      nodeIntegration: !1
    }
  }), c.webContents.on("did-finish-load", () => {
    h("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }), h("daemon-status", { ...s });
  }), E ? (c.loadURL(E), c.webContents.openDevTools()) : c.loadFile(i.join(R, "index.html"));
}
let O = !1;
p.on("window-all-closed", () => {
  process.platform !== "darwin" && p.quit();
});
p.on("activate", () => {
  $.getAllWindows().length === 0 && L();
});
p.on("before-quit", async (e) => {
  O || a && (O = !0, e.preventDefault(), console.log("[main] App quitting, shutting down daemon..."), await H(), p.quit());
});
p.whenReady().then(() => {
  Q() || console.error("[main] Failed to start daemon - continuing with UI"), L();
});
export {
  z as MAIN_DIST,
  R as RENDERER_DIST,
  E as VITE_DEV_SERVER_URL
};
