/**
 * React hooks for communicating with the QuantumVITAS daemon
 * 
 * Provides a fully typed interface for making RPC calls.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type {
  QVCommandType,
  QVPayload,
  QVResult,
  QVResponse,
  DaemonStatus,
  ProjectSummary,
  StructureInfo,
  WorkflowInfo,
  JobSummary,
  JobStatus,
} from '../types/qv';

// =============================================================================
// Types
// =============================================================================

export interface QVClientState {
  isConnected: boolean;
  isLoading: boolean;
  lastError: string | null;
  daemonStatus: DaemonStatus | null;
}

export interface QVClient {
  state: QVClientState;
  
  /**
   * Type-safe RPC call
   * 
   * @example
   * const result = await qv.call('ping', {});
   * // result is typed as { pong: boolean; version: string }
   */
  call: <K extends QVCommandType>(
    type: K,
    payload: QVPayload<K>
  ) => Promise<QVResponse<QVResult<K>>>;
  
  // Convenience methods (typed wrappers around call)
  ping: () => Promise<QVResponse<{ pong: boolean; version: string }>>;
  getProjectSummary: (projectRoot: string) => Promise<QVResponse<ProjectSummary>>;
  listStructures: (projectRoot: string) => Promise<QVResponse<{ structures: StructureInfo[]; count: number }>>;
  listWorkflows: (projectRoot: string) => Promise<QVResponse<{ workflows: WorkflowInfo[]; count: number }>>;
  listJobs: (filter?: { status?: JobStatus; job_type?: string }) => Promise<QVResponse<{ jobs: JobSummary[]; count: number }>>;
  
  // Connection management
  checkConnection: () => Promise<boolean>;
  refreshDaemonStatus: () => Promise<DaemonStatus | null>;
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook for communicating with the QuantumVITAS daemon
 * 
 * @example
 * function MyComponent() {
 *   const qv = useQVClient();
 *   
 *   const handlePing = async () => {
 *     const response = await qv.ping();
 *     if (response.ok) {
 *       console.log('Daemon version:', response.data.version);
 *     }
 *   };
 *   
 *   // Or use the generic call method for full type safety
 *   const handleSummary = async () => {
 *     const response = await qv.call('get_project_summary', { project_root: '/path' });
 *     if (response.ok) {
 *       console.log('Project:', response.data.name);
 *     }
 *   };
 *   
 *   return <button onClick={handlePing}>Ping</button>;
 * }
 */
export function useQVClient(): QVClient {
  const [state, setState] = useState<QVClientState>({
    isConnected: false,
    isLoading: false,
    lastError: null,
    daemonStatus: null,
  });
  
  // Track mounted state to avoid state updates after unmount
  const mountedRef = useRef(true);
  
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // Subscribe to daemon status changes
  useEffect(() => {
    if (!window.qv) return;
    
    const unsubscribe = window.qv.onDaemonStatus((status) => {
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isConnected: status.connected,
          daemonStatus: status,
        }));
      }
    });
    
    return unsubscribe;
  }, []);
  
  /**
   * Type-safe RPC call
   */
  const call = useCallback(async <K extends QVCommandType>(
    type: K,
    payload: QVPayload<K>
  ): Promise<QVResponse<QVResult<K>>> => {
    if (!window.qv) {
      return {
        id: 'no-bridge',
        ok: false,
        error: {
          code: 'no_bridge',
          message: 'QV bridge not available. Are you running in Electron?',
        },
      };
    }
    
    if (mountedRef.current) {
      setState(prev => ({ ...prev, isLoading: true, lastError: null }));
    }
    
    try {
      const response = await window.qv.request<QVResult<K>>(
        type,
        payload as Record<string, unknown>
      );
      
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          lastError: response.ok ? null : (response.error?.message ?? 'Unknown error'),
        }));
      }
      
      return response;
    } catch (e) {
      const error = e as Error;
      
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          lastError: error.message,
        }));
      }
      
      return {
        id: 'exception',
        ok: false,
        error: {
          code: 'exception',
          message: error.message,
        },
      };
    }
  }, []);
  
  /**
   * Check daemon connection status
   */
  const checkConnection = useCallback(async (): Promise<boolean> => {
    if (!window.qv) {
      if (mountedRef.current) {
        setState(prev => ({ ...prev, isConnected: false }));
      }
      return false;
    }
    
    try {
      const connected = await window.qv.isConnected();
      if (mountedRef.current) {
        setState(prev => ({ ...prev, isConnected: connected }));
      }
      return connected;
    } catch {
      if (mountedRef.current) {
        setState(prev => ({ ...prev, isConnected: false }));
      }
      return false;
    }
  }, []);
  
  /**
   * Refresh daemon status
   */
  const refreshDaemonStatus = useCallback(async (): Promise<DaemonStatus | null> => {
    if (!window.qv) return null;
    
    try {
      const status = await window.qv.getDaemonStatus();
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isConnected: status.connected,
          daemonStatus: status,
        }));
      }
      return status;
    } catch {
      return null;
    }
  }, []);
  
  // Check connection on mount
  useEffect(() => {
    checkConnection();
    refreshDaemonStatus();
    
    // Periodically check connection
    const interval = setInterval(() => {
      checkConnection();
    }, 5000);
    
    return () => clearInterval(interval);
  }, [checkConnection, refreshDaemonStatus]);
  
  // =============================================================================
  // Convenience Methods
  // =============================================================================
  
  const ping = useCallback(
    () => call('ping', {} as QVPayload<'ping'>),
    [call]
  );
  
  const getProjectSummary = useCallback(
    (projectRoot: string) => call('get_project_summary', { project_root: projectRoot }),
    [call]
  );
  
  const listStructures = useCallback(
    (projectRoot: string) => call('list_structures', { project_root: projectRoot }),
    [call]
  );
  
  const listWorkflows = useCallback(
    (projectRoot: string) => call('list_workflows', { project_root: projectRoot }),
    [call]
  );
  
  const listJobs = useCallback(
    (filter: { status?: JobStatus; job_type?: string } = {}) => call('list_jobs', filter),
    [call]
  );
  
  return {
    state,
    call,
    ping,
    getProjectSummary,
    listStructures,
    listWorkflows,
    listJobs,
    checkConnection,
    refreshDaemonStatus,
  };
}

// =============================================================================
// Log Subscription Hook
// =============================================================================

/**
 * Hook to subscribe to daemon log messages
 * 
 * @example
 * function DebugPanel() {
 *   const logs = useQVLogs();
 *   return <pre>{logs.join('\n')}</pre>;
 * }
 */
export function useQVLogs(maxLines: number = 100): string[] {
  const [logs, setLogs] = useState<string[]>([]);
  
  useEffect(() => {
    if (!window.qv) return;
    
    const unsubscribe = window.qv.onLog((message) => {
      setLogs(prev => {
        const newLogs = [...prev, message];
        // Keep only the last maxLines
        return newLogs.slice(-maxLines);
      });
    });
    
    return unsubscribe;
  }, [maxLines]);
  
  return logs;
}

// =============================================================================
// Daemon Status Hook
// =============================================================================

/**
 * Hook to subscribe to daemon status
 */
export function useDaemonStatus(): DaemonStatus | null {
  const [status, setStatus] = useState<DaemonStatus | null>(null);
  
  useEffect(() => {
    if (!window.qv) return;
    
    // Get initial status
    window.qv.getDaemonStatus().then(setStatus).catch(() => {});
    
    // Subscribe to updates
    const unsubscribe = window.qv.onDaemonStatus(setStatus);
    
    return unsubscribe;
  }, []);
  
  return status;
}
