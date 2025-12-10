"use strict";
const electron = require("electron");
let requestIdCounter = 0;
function generateRequestId() {
  requestIdCounter += 1;
  return `req-${Date.now()}-${requestIdCounter}`;
}
const qvApi = {
  /**
   * Send a request to the Python daemon
   * 
   * @param type - Command type (e.g., 'ping', 'list_structures')
   * @param payload - Command payload (optional)
   * @returns Promise with the daemon response
   * 
   * @example
   * const response = await window.qv.request('ping', {});
   * if (response.ok) {
   *   console.log('Daemon version:', response.data.version);
   * }
   */
  request: async (type, payload = {}) => {
    const request = {
      id: generateRequestId(),
      type,
      payload
    };
    return electron.ipcRenderer.invoke("qv-request", request);
  },
  /**
   * Subscribe to daemon log messages (from stderr)
   * 
   * @param callback - Function to call with each log message
   * @returns Unsubscribe function
   * 
   * @example
   * const unsubscribe = window.qv.onLog((msg) => console.log('[daemon]', msg));
   * // Later: unsubscribe();
   */
  onLog: (callback) => {
    const handler = (_event, message) => {
      callback(message);
    };
    electron.ipcRenderer.on("daemon-log", handler);
    return () => {
      electron.ipcRenderer.removeListener("daemon-log", handler);
    };
  },
  /**
   * Check if the daemon is currently connected
   * 
   * @returns Promise<boolean> - true if daemon is connected
   */
  isConnected: async () => {
    return electron.ipcRenderer.invoke("qv-is-connected");
  },
  /**
   * Open a native directory picker dialog
   * 
   * @returns Promise<string | null> - Selected path or null if cancelled
   */
  openDirectory: async () => {
    return electron.ipcRenderer.invoke("qv-open-directory");
  },
  /**
   * Open a native file picker dialog
   * 
   * @param options - Dialog options (title, filters)
   * @returns Promise<string | null> - Selected path or null if cancelled
   */
  openFile: async (options) => {
    return electron.ipcRenderer.invoke("qv-open-file", options);
  },
  /**
   * Get detailed daemon status including any startup errors
   * 
   * @returns Promise<DaemonStatus>
   */
  getDaemonStatus: async () => {
    return electron.ipcRenderer.invoke("qv-daemon-status");
  },
  /**
   * Subscribe to daemon status changes
   * 
   * @param callback - Function to call with status updates
   * @returns Unsubscribe function
   */
  onDaemonStatus: (callback) => {
    const handler = (_event, status) => {
      callback(status);
    };
    electron.ipcRenderer.on("daemon-status", handler);
    return () => {
      electron.ipcRenderer.removeListener("daemon-status", handler);
    };
  },
  /**
   * Listen for main process messages (e.g., 'ready')
   */
  onMainMessage: (callback) => {
    const handler = (_event, data) => {
      callback(data);
    };
    electron.ipcRenderer.on("main-process-message", handler);
    return () => {
      electron.ipcRenderer.removeListener("main-process-message", handler);
    };
  },
  /**
   * Set the current project path for log file storage
   * Logs will be saved to .qv-daemon.log in the project directory
   * 
   * @param projectPath - Project root path or null to disable
   */
  setProject: async (projectPath) => {
    return electron.ipcRenderer.invoke("qv-set-project", projectPath);
  },
  /**
   * Read logs from a project's log file
   * 
   * @param projectPath - Project root path
   * @param tailLines - Number of lines to read from end (default 500)
   * @returns Array of log lines
   */
  readLogs: async (projectPath, tailLines) => {
    return electron.ipcRenderer.invoke("qv-read-logs", projectPath, tailLines);
  },
  /**
   * Reveal a file or folder in the native file manager (Finder/Explorer)
   * 
   * @param targetPath - Path to reveal
   * @returns true if successful
   */
  revealPath: async (targetPath) => {
    return electron.ipcRenderer.invoke("qv-reveal-path", targetPath);
  },
  /**
   * Set E2E test directory (for testing only)
   * This allows E2E tests to bypass the native file dialog
   * 
   * @param directory - Directory path to use for file dialogs
   */
  setE2ETestDirectory: async (directory) => {
    return electron.ipcRenderer.invoke("qv-set-e2e-test-directory", directory);
  }
};
electron.contextBridge.exposeInMainWorld("qv", qvApi);
