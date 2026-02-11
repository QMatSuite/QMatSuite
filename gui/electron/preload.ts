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

interface DaemonStatus {
  connected: boolean;
  startupError: string | null;
  pythonPath: string | null;
  projectRoot: string | null;
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
   * Open a native directory picker dialog
   * 
   * @returns Promise<string | null> - Selected path or null if cancelled
   */
  openDirectory: async (): Promise<string | null> => {
    return ipcRenderer.invoke('qv-open-directory');
  },
  
  /**
   * Open a native file picker dialog
   * 
   * @param options - Dialog options (title, filters)
   * @returns Promise<string | null> - Selected path or null if cancelled
   */
  openFile: async (options?: {
    title?: string;
    filters?: { name: string; extensions: string[] }[];
  }): Promise<string | null> => {
    return ipcRenderer.invoke('qv-open-file', options);
  },
  
  /**
   * Get detailed daemon status including any startup errors
   * 
   * @returns Promise<DaemonStatus>
   */
  getDaemonStatus: async (): Promise<DaemonStatus> => {
    return ipcRenderer.invoke('qv-daemon-status');
  },
  
  /**
   * Subscribe to daemon status changes
   * 
   * @param callback - Function to call with status updates
   * @returns Unsubscribe function
   */
  onDaemonStatus: (callback: (status: DaemonStatus) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, status: DaemonStatus) => {
      callback(status);
    };
    
    ipcRenderer.on('daemon-status', handler);
    
    return () => {
      ipcRenderer.removeListener('daemon-status', handler);
    };
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
  
  /**
   * Set the current project path for log file storage
   * Logs will be saved to .qv-daemon.log in the project directory
   * 
   * @param projectPath - Project root path or null to disable
   */
  setProject: async (projectPath: string | null): Promise<void> => {
    return ipcRenderer.invoke('qv-set-project', projectPath);
  },
  
  /**
   * Read logs from a project's log file
   * 
   * @param projectPath - Project root path
   * @param tailLines - Number of lines to read from end (default 500)
   * @returns Array of log lines
   */
  readLogs: async (projectPath: string, tailLines?: number): Promise<string[]> => {
    return ipcRenderer.invoke('qv-read-logs', projectPath, tailLines);
  },
  
  /**
   * Reveal a file or folder in the native file manager (Finder/Explorer)
   * 
   * @param targetPath - Path to reveal
   * @returns true if successful
   */
  revealPath: async (targetPath: string): Promise<boolean> => {
    return ipcRenderer.invoke('qv-reveal-path', targetPath);
  },
  
  /**
   * Set E2E test directory (for testing only)
   * This allows E2E tests to bypass the native file dialog
   * 
   * @param directory - Directory path to use for file dialogs
   */
  setE2ETestDirectory: async (directory: string): Promise<void> => {
    return ipcRenderer.invoke('qv-set-e2e-test-directory', directory);
  },
  
  /**
   * Read binary blob file (secure, via index.json allowlist)
   *
   * @param blobId - Blob ID to read
   * @param calcDir - Calculation directory (for blob store)
   * @returns ArrayBuffer with blob data
   */
  readBlob: async (blobId: string, calcDir: string): Promise<ArrayBuffer> => {
    return ipcRenderer.invoke('qv-read-blob', blobId, calcDir);
  },

  /**
   * Read a file from the .scratch/ directory (secure, path-validated)
   *
   * @param calcDir - Calculation directory containing .scratch/
   * @param relativePath - Path relative to calcDir (must start with .scratch/)
   * @returns ArrayBuffer with file contents
   */
  readScratchFile: async (calcDir: string, relativePath: string): Promise<ArrayBuffer> => {
    return ipcRenderer.invoke('qv-read-scratch-file', calcDir, relativePath);
  },
};

// Expose to renderer via contextBridge
contextBridge.exposeInMainWorld('qv', qvApi);

// Type declaration for window.qv (for TypeScript)
export type QVApiType = typeof qvApi;
