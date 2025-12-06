import { ipcMain as p, app as d, BrowserWindow as E, dialog as _ } from "electron";
import { spawn as T } from "node:child_process";
import { createInterface as S } from "node:readline";
import { fileURLToPath as $ } from "node:url";
import i from "node:path";
import v from "node:fs";
const h = i.dirname($(import.meta.url));
process.env.APP_ROOT = i.join(h, "..");
const f = process.env.VITE_DEV_SERVER_URL, k = i.join(process.env.APP_ROOT, "dist-electron"), P = i.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = f ? i.join(process.env.APP_ROOT, "public") : P;
let a = null, s = null, m = null;
const r = {
  connected: !1,
  startupError: null,
  pythonPath: null,
  projectRoot: null
}, c = /* @__PURE__ */ new Map(), g = 6e4;
function D() {
  return process.env.QV_PROJECT_ROOT ? process.env.QV_PROJECT_ROOT : i.resolve(h, "..", "..");
}
function I() {
  const e = D();
  if (process.env.QV_DAEMON_PYTHON) {
    const o = process.env.QV_DAEMON_PYTHON;
    if (v.existsSync(o))
      return { path: o, found: !0, source: "QV_DAEMON_PYTHON env var" };
    console.warn(`[main] QV_DAEMON_PYTHON set to ${o} but file not found`);
  }
  const n = process.platform === "win32", t = [
    // .venv (common convention)
    n ? i.join(e, ".venv", "Scripts", "python.exe") : i.join(e, ".venv", "bin", "python"),
    // venv (alternative)
    n ? i.join(e, "venv", "Scripts", "python.exe") : i.join(e, "venv", "bin", "python")
  ];
  for (const o of t)
    if (v.existsSync(o))
      return { path: o, found: !0, source: `venv at ${i.dirname(i.dirname(o))}` };
  return console.warn("[main] No venv found, falling back to system python"), { path: "python", found: !1, source: "system PATH (fallback)" };
}
function b() {
  return process.env.QV_DAEMON_MODULE ? process.env.QV_DAEMON_MODULE : "quantumvitas.daemon.server";
}
function j() {
  const e = I(), n = D(), t = b();
  r.pythonPath = e.path, r.projectRoot = n, r.startupError = null, console.log("[main] Starting daemon:"), console.log(`[main]   Python: ${e.path} (${e.source})`), console.log(`[main]   Module: ${t}`), console.log(`[main]   CWD: ${n}`);
  try {
    s = T(e.path, ["-m", t], {
      cwd: n,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1"
        // Ensure unbuffered output
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
  } catch (o) {
    const l = o;
    return r.startupError = `Failed to spawn daemon: ${l.message}`, console.error(`[main] ${r.startupError}`), !1;
  }
  return !s.stdout || !s.stdin ? (r.startupError = "Failed to create daemon stdio pipes", console.error(`[main] ${r.startupError}`), !1) : (m = S({
    input: s.stdout,
    crlfDelay: 1 / 0
  }), m.on("line", (o) => {
    M(o);
  }), s.stderr?.on("data", (o) => {
    const l = o.toString().trim();
    console.log(`[daemon] ${l}`), a?.webContents.send("daemon-log", l);
  }), s.on("error", (o) => {
    console.error("[main] Daemon process error:", o), r.connected = !1, r.startupError = `Daemon error: ${o.message}`, a?.webContents.send("daemon-status", { ...r });
  }), s.on("exit", (o, l) => {
    console.log(`[main] Daemon exited with code ${o}, signal ${l}`), r.connected = !1, o !== 0 && o !== null && (r.startupError = `Daemon exited with code ${o}`), s = null, m = null;
    for (const [u, w] of c)
      clearTimeout(w.timeoutId), w.reject(new Error("Daemon process exited"));
    c.clear(), a?.webContents.send("daemon-status", { ...r });
  }), r.connected = !0, !0);
}
function M(e) {
  if (e.trim())
    try {
      const n = JSON.parse(e), t = c.get(n.id);
      t ? (clearTimeout(t.timeoutId), c.delete(n.id), t.resolve(n)) : console.warn(`[main] Received response for unknown request: ${n.id}`);
    } catch (n) {
      console.error(`[main] Failed to parse daemon response: ${e}`), console.error(n);
    }
}
async function R(e) {
  return !s || !s.stdin || !r.connected ? {
    id: e.id,
    ok: !1,
    error: {
      code: "daemon_not_connected",
      message: r.startupError || "Daemon process is not running"
    }
  } : new Promise((n, t) => {
    const o = setTimeout(() => {
      c.delete(e.id), t(new Error(`Request ${e.id} timed out after ${g}ms`));
    }, g);
    c.set(e.id, { resolve: n, reject: t, timeoutId: o });
    const l = JSON.stringify(e) + `
`;
    s.stdin.write(l, (u) => {
      u && (clearTimeout(o), c.delete(e.id), t(u));
    });
  });
}
function N(e) {
  return new Promise((n) => setTimeout(n, e));
}
async function C() {
  if (!s || !r.connected) return;
  const e = s;
  try {
    await R({
      id: `shutdown-${Date.now()}`,
      type: "shutdown",
      payload: {}
    });
  } catch {
    console.log("[main] Shutdown command failed (may already be stopped)");
  }
  await N(2e3), e && !e.killed && (console.log("[main] Force killing daemon"), e.kill("SIGTERM"));
}
p.handle("qv-request", async (e, n) => {
  console.log(`[main] IPC request: ${n.type} (${n.id})`);
  try {
    const t = await R(n);
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
p.handle("qv-is-connected", async () => r.connected && s !== null);
p.handle("qv-daemon-status", async () => ({ ...r }));
p.handle("qv-open-directory", async () => {
  if (!a) return null;
  const e = await _.showOpenDialog(a, {
    properties: ["openDirectory", "createDirectory"],
    title: "Select Project Root",
    buttonLabel: "Select"
  });
  return e.canceled || e.filePaths.length === 0 ? null : e.filePaths[0];
});
p.handle("qv-open-file", async (e, n) => {
  if (!a) return null;
  const t = await _.showOpenDialog(a, {
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
function O() {
  a = new E({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: i.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: i.join(h, "preload.mjs"),
      contextIsolation: !0,
      nodeIntegration: !1
    }
  }), a.webContents.on("did-finish-load", () => {
    a?.webContents.send("main-process-message", {
      type: "ready",
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    }), a?.webContents.send("daemon-status", { ...r });
  }), f ? (a.loadURL(f), a.webContents.openDevTools()) : a.loadFile(i.join(P, "index.html"));
}
let y = !1;
d.on("window-all-closed", () => {
  process.platform !== "darwin" && d.quit();
});
d.on("activate", () => {
  E.getAllWindows().length === 0 && O();
});
d.on("before-quit", async (e) => {
  y || s && (y = !0, e.preventDefault(), await C(), d.quit());
});
d.whenReady().then(() => {
  j() || console.error("[main] Failed to start daemon - continuing with UI"), O();
});
export {
  k as MAIN_DIST,
  P as RENDERER_DIST,
  f as VITE_DEV_SERVER_URL
};
