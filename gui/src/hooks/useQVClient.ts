/**
 * React hook for communicating with the QuantumVITAS daemon
 * 
 * Provides a typed interface for making RPC calls and tracking state.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type {
  QVCommandType,
  QVResponse,
  PingData,
  ProjectSummaryData,
  ListStructuresData,
  ListWorkflowsData,
  StructureVisData,
  ScfConvergenceData,
  DosData,
  BandStructureData,
  JobSubmitData,
  JobInfo,
  ListJobsData,
  CancelJobData,
  StructureVisPayload,
  WorkflowStepPayload,
  RunWorkflowPayload,
  RunStepPayload,
  ListJobsPayload,
} from '../types/qv';

// =============================================================================
// Types
// =============================================================================

export interface QVClientState {
  isConnected: boolean;
  isLoading: boolean;
  lastError: string | null;
}

export interface QVClient {
  state: QVClientState;
  
  // System commands
  ping: () => Promise<QVResponse<PingData>>;
  
  // Project commands
  getProjectSummary: (projectRoot: string) => Promise<QVResponse<ProjectSummaryData>>;
  listStructures: (projectRoot: string) => Promise<QVResponse<ListStructuresData>>;
  listWorkflows: (projectRoot: string) => Promise<QVResponse<ListWorkflowsData>>;
  
  // Visualization data
  getStructureVis: (payload: StructureVisPayload) => Promise<QVResponse<StructureVisData>>;
  getScfConvergence: (payload: WorkflowStepPayload) => Promise<QVResponse<ScfConvergenceData>>;
  getDosData: (payload: WorkflowStepPayload) => Promise<QVResponse<DosData>>;
  getBandStructureData: (payload: WorkflowStepPayload) => Promise<QVResponse<BandStructureData>>;
  
  // Job management
  runWorkflow: (payload: RunWorkflowPayload) => Promise<QVResponse<JobSubmitData>>;
  runStep: (payload: RunStepPayload) => Promise<QVResponse<JobSubmitData>>;
  getJobStatus: (jobId: string) => Promise<QVResponse<JobInfo>>;
  listJobs: (payload?: ListJobsPayload) => Promise<QVResponse<ListJobsData>>;
  cancelJob: (jobId: string) => Promise<QVResponse<CancelJobData>>;
  
  // Raw request (for advanced usage)
  request: <T = Record<string, unknown>>(
    type: QVCommandType,
    payload?: Record<string, unknown>
  ) => Promise<QVResponse<T>>;
  
  // Connection management
  checkConnection: () => Promise<boolean>;
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
 *   return <button onClick={handlePing}>Ping</button>;
 * }
 */
export function useQVClient(): QVClient {
  const [state, setState] = useState<QVClientState>({
    isConnected: false,
    isLoading: false,
    lastError: null,
  });
  
  // Track mounted state to avoid state updates after unmount
  const mountedRef = useRef(true);
  
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  /**
   * Make a request to the daemon with state management
   */
  const request = useCallback(async <T = Record<string, unknown>>(
    type: QVCommandType,
    payload: Record<string, unknown> = {}
  ): Promise<QVResponse<T>> => {
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
      const response = await window.qv.request<T>(type, payload);
      
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
  
  // Check connection on mount
  useEffect(() => {
    checkConnection();
    
    // Periodically check connection
    const interval = setInterval(checkConnection, 5000);
    return () => clearInterval(interval);
  }, [checkConnection]);
  
  // =============================================================================
  // Command Wrappers
  // =============================================================================
  
  const ping = useCallback(
    () => request<PingData>('ping', {}),
    [request]
  );
  
  const getProjectSummary = useCallback(
    (projectRoot: string) => 
      request<ProjectSummaryData>('get_project_summary', { project_root: projectRoot }),
    [request]
  );
  
  const listStructures = useCallback(
    (projectRoot: string) => 
      request<ListStructuresData>('list_structures', { project_root: projectRoot }),
    [request]
  );
  
  const listWorkflows = useCallback(
    (projectRoot: string) => 
      request<ListWorkflowsData>('list_workflows', { project_root: projectRoot }),
    [request]
  );
  
  const getStructureVis = useCallback(
    (payload: StructureVisPayload) => 
      request<StructureVisData>('get_structure_vis', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const getScfConvergence = useCallback(
    (payload: WorkflowStepPayload) => 
      request<ScfConvergenceData>('get_scf_convergence', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const getDosData = useCallback(
    (payload: WorkflowStepPayload) => 
      request<DosData>('get_dos_data', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const getBandStructureData = useCallback(
    (payload: WorkflowStepPayload) => 
      request<BandStructureData>('get_band_structure_data', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const runWorkflow = useCallback(
    (payload: RunWorkflowPayload) => 
      request<JobSubmitData>('run_workflow', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const runStep = useCallback(
    (payload: RunStepPayload) => 
      request<JobSubmitData>('run_step', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const getJobStatus = useCallback(
    (jobId: string) => 
      request<JobInfo>('get_job_status', { job_id: jobId }),
    [request]
  );
  
  const listJobs = useCallback(
    (payload: ListJobsPayload = {}) => 
      request<ListJobsData>('list_jobs', payload as unknown as Record<string, unknown>),
    [request]
  );
  
  const cancelJob = useCallback(
    (jobId: string) => 
      request<CancelJobData>('cancel_job', { job_id: jobId }),
    [request]
  );
  
  return {
    state,
    ping,
    getProjectSummary,
    listStructures,
    listWorkflows,
    getStructureVis,
    getScfConvergence,
    getDosData,
    getBandStructureData,
    runWorkflow,
    runStep,
    getJobStatus,
    listJobs,
    cancelJob,
    request,
    checkConnection,
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

