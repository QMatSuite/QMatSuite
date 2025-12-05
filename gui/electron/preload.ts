/**
 * QuantumVITAS Preload Script
 * 
 * Exposes a safe API to the renderer process for communicating
 * with the Python daemon via IPC.
 * 
 * Security: Uses contextBridge to expose only specific functions,
 * not the entire ipcRenderer.
 */

import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

// Unique ID counter for requests
let requestIdCounter = 0;

/**
 * Generate a unique request ID
 */
function generateRequestId(): string {
  requestIdCounter += 1;
  return `req-${Date.now()}-${requestIdCounter}`;
}

// Type definitions for the API (mirrored in src/types/qv.ts)
interface QVRequest {
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

interface QVResponse<T = Record<string, unknown>> {
  id: string;
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}

/**
 * Exposed API for communicating with the daemon
 */
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
  request: async <T = Record<string, unknown>>(
    type: string,
    payload: Record<string, unknown> = {}
  ): Promise<QVResponse<T>> => {
    const request: QVRequest = {
      id: generateRequestId(),
      type,
      payload,
    };
    
    return ipcRenderer.invoke('qv-request', request);
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
  onLog: (callback: (message: string) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, message: string) => {
      callback(message);
    };
    
    ipcRenderer.on('daemon-log', handler);
    
    // Return unsubscribe function
    return () => {
      ipcRenderer.removeListener('daemon-log', handler);
    };
  },
  
  /**
   * Check if the daemon is currently connected
   * 
   * @returns Promise<boolean> - true if daemon is connected
   */
  isConnected: async (): Promise<boolean> => {
    return ipcRenderer.invoke('qv-is-connected');
  },
  
  /**
   * Listen for main process messages (e.g., 'ready')
   */
  onMainMessage: (callback: (data: unknown) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, data: unknown) => {
      callback(data);
    };
    
    ipcRenderer.on('main-process-message', handler);
    
    return () => {
      ipcRenderer.removeListener('main-process-message', handler);
    };
  },
};

// Expose to renderer via contextBridge
contextBridge.exposeInMainWorld('qv', qvApi);

// Type declaration for window.qv (for TypeScript)
export type QVApiType = typeof qvApi;
