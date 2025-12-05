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
  }
};
electron.contextBridge.exposeInMainWorld("qv", qvApi);
