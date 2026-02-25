/**
 * React hooks for communicating with the QMatSuite daemon
 * 
 * Provides a fully typed interface for making RPC calls.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type {
  QMSCommandType,
  QMSPayload,
  QMSResult,
  QMSResponse,
  DaemonStatus,
  ProjectSummary,
  StructureInfo,
  CalculationInfo,
  JobSummary,
  JobStatus,
} from '../types/qms';

// =============================================================================
// Types
// =============================================================================

export interface QMSClientState {
  isConnected: boolean;
  isLoading: boolean;
  lastError: string | null;
  daemonStatus: DaemonStatus | null;
}

export interface QMSClient {
  state: QMSClientState;
  
  /**
   * Type-safe RPC call
   * 
   * @example
   * const result = await qms.call('ping', {});
   * // result is typed as { pong: boolean; version: string }
   */
  call: <K extends QMSCommandType>(
    type: K,
    payload: QMSPayload<K>
  ) => Promise<QMSResponse<QMSResult<K>>>;
  
  // Convenience methods (typed wrappers around call)
  ping: () => Promise<QMSResponse<{ pong: boolean; version: string }>>;
  getProjectSummary: (projectRoot: string) => Promise<QMSResponse<ProjectSummary>>;
  listStructures: (projectRoot: string) => Promise<QMSResponse<{ structures: StructureInfo[]; count: number }>>;
  listCalculations: (projectRoot: string) => Promise<QMSResponse<{ calculations: CalculationInfo[]; count: number }>>;
  rebuildProjectRegistry: (projectRoot: string) => Promise<QMSResponse<QMSResult<'rebuild_project_registry'>>>;
  listJobs: (filter?: { status?: JobStatus; job_type?: string }) => Promise<QMSResponse<{ jobs: JobSummary[]; count: number }>>;
  listEngineFamilies: () => Promise<QMSResponse<QMSResult<'list_engine_families'>>>;
  listEngines: (installedOnly?: boolean) => Promise<QMSResponse<QMSResult<'engine.list'>>>;
  listInstallableEngines: () => Promise<QMSResponse<QMSResult<'engine.list_installable'>>>;
  installEngine: (
    engineFamily: string,
    options?: { version?: string; source?: string; async?: boolean }
  ) => Promise<QMSResponse<QMSResult<'engine.install'>>>;
  uninstallEngine: (
    engineFamily: string,
    options?: { installationId?: string; async?: boolean }
  ) => Promise<QMSResponse<QMSResult<'engine.uninstall'>>>;
  verifyEngine: (engineFamily: string) => Promise<QMSResponse<QMSResult<'engine.verify'>>>;
  setActiveEngineInstallation: (engineFamily: string, installationId: string) => Promise<QMSResponse<QMSResult<'engine.set_active'>>>;
  registerEnginePath: (
    engineFamily: string,
    installPath: string,
    options?: { source?: string; envVars?: Record<string, string> }
  ) => Promise<QMSResponse<QMSResult<'engine.register_path'>>>;
  unregisterEngine: (engineFamily: string, installationId: string) => Promise<QMSResponse<QMSResult<'engine.unregister'>>>;
  listStepPalette: (engineFamily: string | null) => Promise<QMSResponse<QMSResult<'list_step_palette'>>>;
  setEngineFamily: (projectRoot: string, calculation: string, engineFamily: string) => Promise<QMSResponse<QMSResult<'set_engine_family'>>>;
  listEngineUiParameters: (engineFamily: string, stepTypeGen: string) => Promise<QMSResponse<QMSResult<'list_engine_ui_parameters'>>>;
  listEngineParameterMetadata: (
    engineFamily: string,
    operation: 'list_categories' | 'list_tags' | 'search',
    params?: { category?: string; section?: string; query?: string }
  ) => Promise<QMSResponse<QMSResult<'list_engine_parameter_metadata'>>>;
  getCommonCards: (projectRoot: string, calculation: string, step: string) => Promise<QMSResponse<QMSResult<'get_common_cards'>>>;
  setCommonCard: (
    projectRoot: string,
    calculation: string,
    step: string,
    cardName: string,
    viewModel: {
      raw?: string;
      mode: string;
      automatic?: {
        nk1: number;
        nk2: number;
        nk3: number;
        sk1: number;
        sk2: number;
        sk3: number;
      };
      points?: Array<{
        x: number;
        y: number;
        z: number;
        w: number;
      }>;
      warnings?: string[];
    }
  ) => Promise<QMSResponse<QMSResult<'set_common_card'>>>;
  getPseudoMapping: (projectRoot: string, calculation: string, step: string) => Promise<QMSResponse<QMSResult<'get_pseudo_mapping'>>>;
  setPseudoMapping: (
    projectRoot: string,
    calculation: string,
    step: string,
    mapping: Record<string, string>,
    libraryPreference?: 'precision' | 'efficiency'
  ) => Promise<QMSResponse<QMSResult<'set_pseudo_mapping'>>>;
  // Calculation-level pseudo mapping (authoritative)
  getCalculationPseudoMapping: (projectRoot: string, calculation: string) => Promise<QMSResponse<QMSResult<'get_calculation_pseudo_mapping'>>>;
  getPseudoOptionsForCalculation: (projectRoot: string, calculation: string) => Promise<QMSResponse<QMSResult<'get_pseudo_options_for_calculation'>>>;
  materializePseudoFile: (projectRoot: string, element: string, sha256: string, preferredBasename?: string) => Promise<QMSResponse<QMSResult<'materialize_pseudo_file'>>>;
  listPseudoArchivesStatus: () => Promise<QMSResponse<QMSResult<'list_pseudo_archives_status'>>>;
  installPseudoArchive: (assetName: string) => Promise<QMSResponse<QMSResult<'install_pseudo_archive'>>>;
  analyzeProjectPseudoEffects: (
    projectRoot: string,
    selections: Array<{
      element: string;
      requested_basename: string;
      requested_sha256?: string;
      requested_sha_family?: string;
      source_kind?: 'project' | 'internal' | 'lib';
      source_path?: string;
    }>
  ) => Promise<QMSResponse<QMSResult<'analyze_project_pseudo_effects'>>>;
  updateCalculationSpeciesMap: (
    projectRoot: string,
    calculation: string,
    speciesMap: Record<string, { pseudopot?: string; mass?: number }>
  ) => Promise<QMSResponse<QMSResult<'update_calculation_species_map'>>>;
  importPseudoFiles: (
    projectRoot: string,
    filePaths: string[]
  ) => Promise<QMSResponse<QMSResult<'import_pseudo_files'>>>;
  searchLegacyPseudos: (
    element: string,
    projectRoot?: string
  ) => Promise<QMSResponse<QMSResult<'search_legacy_pseudos'>>>;
  downloadPseudoByFilename: (
    projectRoot: string,
    filename: string,
    destDir?: string
  ) => Promise<QMSResponse<QMSResult<'download_pseudo_by_filename'>>>;
  downloadPseudoCandidate: (
    projectRoot: string,
    candidate: { filename?: string; url?: string },
    destDir?: string
  ) => Promise<QMSResponse<QMSResult<'download_pseudo_candidate'>>>;
  getRelaxFinalStructurePreview: (
    projectRoot: string,
    calculation: string,
    step: string
  ) => Promise<QMSResponse<QMSResult<'get_relax_final_structure_preview'>>>;
  saveRelaxFinalStructure: (
    projectRoot: string,
    calculation: string,
    step: string,
    parentStructureUlid: string,
    slugHint?: string
  ) => Promise<QMSResponse<QMSResult<'save_relax_final_structure'>>>;
  
  // Connection management
  checkConnection: () => Promise<boolean>;
  refreshDaemonStatus: () => Promise<DaemonStatus | null>;
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook for communicating with the QMatSuite daemon
 * 
 * @example
 * function MyComponent() {
 *   const qms = useQMSClient();
 *   
 *   const handlePing = async () => {
 *     const response = await qms.ping();
 *     if (response.ok) {
 *       console.log('Daemon version:', response.data.version);
 *     }
 *   };
 *   
 *   // Or use the generic call method for full type safety
 *   const handleSummary = async () => {
 *     const response = await qms.call('get_project_summary', { project_root: '/path' });
 *     if (response.ok) {
 *       console.log('Project:', response.data.name);
 *     }
 *   };
 *   
 *   return <button onClick={handlePing}>Ping</button>;
 * }
 */
export function useQMSClient(): QMSClient {
  const [state, setState] = useState<QMSClientState>({
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
    if (!window.qms) return;
    
    const unsubscribe = window.qms.onDaemonStatus((status) => {
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
  const call = useCallback(async <K extends QMSCommandType>(
    type: K,
    payload: QMSPayload<K>
  ): Promise<QMSResponse<QMSResult<K>>> => {
    if (!window.qms) {
      return {
        id: 'no-bridge',
        ok: false,
        error: {
          code: 'no_bridge',
          message: 'QMS bridge not available. Are you running in Electron?',
        },
      };
    }
    
    // Instrumentation: log RPC calls for debugging
    const timerLabel = `rpc:${type}`;
    console.time(timerLabel);
    const projectRoot = (payload as Record<string, unknown>)?.project_root as string | undefined;
    if (projectRoot) {
      console.log(`[RPC] ${type} called`, { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1) });
    } else {
      console.log(`[RPC] ${type} called`);
    }
    
    if (mountedRef.current) {
      setState(prev => ({ ...prev, isLoading: true, lastError: null }));
    }
    
    try {
      const response = await window.qms.request<QMSResult<K>>(
        type,
        payload as Record<string, unknown>
      );
      
      console.timeEnd(timerLabel);
      
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
      console.timeEnd(timerLabel);
      console.error(`[RPC] ${type} failed:`, error);
      
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
    if (!window.qms) {
      if (mountedRef.current) {
        setState(prev => ({ ...prev, isConnected: false }));
      }
      return false;
    }
    
    try {
      const connected = await window.qms.isConnected();
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
    if (!window.qms) return null;
    
    try {
      const status = await window.qms.getDaemonStatus();
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
  
  // Check connection on mount (event-driven updates handle ongoing status)
  useEffect(() => {
    checkConnection();
    refreshDaemonStatus();
  }, [checkConnection, refreshDaemonStatus]);
  
  // =============================================================================
  // Convenience Methods
  // =============================================================================
  
  const ping = useCallback(
    () => call('ping', {} as QMSPayload<'ping'>),
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
  
  const listCalculations = useCallback(
    (projectRoot: string) => call('list_calculations', { project_root: projectRoot }),
    [call]
  );
  
  const rebuildProjectRegistry = useCallback(
    (projectRoot: string) => call('rebuild_project_registry', { project_root: projectRoot }),
    [call]
  );
  
  const listJobs = useCallback(
    (filter: { status?: JobStatus; job_type?: string } = {}) => call('list_jobs', filter),
    [call]
  );
  
  const listEngineFamilies = useCallback(
    () => call('list_engine_families', {}),
    [call]
  );

  const listEngines = useCallback(
    (installedOnly: boolean = false) => call('engine.list', { installed_only: installedOnly }),
    [call]
  );

  const listInstallableEngines = useCallback(
    () => call('engine.list_installable', {}),
    [call]
  );

  const installEngine = useCallback(
    (
      engineFamily: string,
      options: { version?: string; source?: string; async?: boolean } = {}
    ) => call('engine.install', {
      engine_family: engineFamily,
      version: options.version,
      source: options.source,
      async: options.async,
    }),
    [call]
  );

  const uninstallEngine = useCallback(
    (
      engineFamily: string,
      options: { installationId?: string; async?: boolean } = {}
    ) => call('engine.uninstall', {
      engine_family: engineFamily,
      installation_id: options.installationId,
      async: options.async,
    }),
    [call]
  );

  const verifyEngine = useCallback(
    (engineFamily: string) => call('engine.verify', { engine_family: engineFamily }),
    [call]
  );

  const setActiveEngineInstallation = useCallback(
    (engineFamily: string, installationId: string) => call('engine.set_active', {
      engine_family: engineFamily,
      installation_id: installationId,
    }),
    [call]
  );

  const registerEnginePath = useCallback(
    (
      engineFamily: string,
      installPath: string,
      options: { source?: string; envVars?: Record<string, string> } = {}
    ) => call('engine.register_path', {
      engine_family: engineFamily,
      path: installPath,
      source: options.source,
      env_vars: options.envVars,
    }),
    [call]
  );

  const unregisterEngine = useCallback(
    (engineFamily: string, installationId: string) => call('engine.unregister', {
      engine_family: engineFamily,
      installation_id: installationId,
    }),
    [call]
  );

  const listStepPalette = useCallback(
    (engineFamily: string | null) => call('list_step_palette', { engine_family: engineFamily }),
    [call]
  );

  const setEngineFamily = useCallback(
    (projectRoot: string, calculation: string, engineFamily: string) =>
      call('set_engine_family', { project_root: projectRoot, calculation, engine_family: engineFamily }),
    [call]
  );

  const listEngineUiParameters = useCallback(
    (engineFamily: string, stepTypeGen: string) =>
      call('list_engine_ui_parameters', { engine_family: engineFamily, step_type_gen: stepTypeGen }),
    [call]
  );

  const listEngineParameterMetadata = useCallback(
    (engineFamily: string, operation: 'list_categories' | 'list_tags' | 'search', params: { category?: string; section?: string; query?: string } = {}) =>
      call('list_engine_parameter_metadata', { engine_family: engineFamily, operation, ...params }),
    [call]
  );
  
  const getCommonCards = useCallback(
    (projectRoot: string, calculation: string, step: string) =>
      call('get_common_cards', { project_root: projectRoot, calculation, step }),
    [call]
  );
  
  const setCommonCard = useCallback(
    (
      projectRoot: string,
      calculation: string,
      step: string,
      cardName: string,
      viewModel: {
        raw?: string;
        mode: string;
        automatic?: {
          nk1: number;
          nk2: number;
          nk3: number;
          sk1: number;
          sk2: number;
          sk3: number;
        };
        points?: Array<{
          x: number;
          y: number;
          z: number;
          w: number;
        }>;
        warnings?: string[];
      }
    ) => call('set_common_card', {
      project_root: projectRoot,
      calculation,
      step,
      card_name: cardName,
      view_model: viewModel,
    }),
    [call]
  );
  
  const getPseudoMapping = useCallback(
    (projectRoot: string, calculation: string, step: string) =>
      call('get_pseudo_mapping', { project_root: projectRoot, calculation, step }),
    [call]
  );
  
  const setPseudoMapping = useCallback(
    (
      projectRoot: string,
      calculation: string,
      step: string,
      mapping: Record<string, string>,
      libraryPreference?: 'precision' | 'efficiency'
    ) => call('set_pseudo_mapping', {
      project_root: projectRoot,
      calculation,
      step,
      mapping,
      library_preference: libraryPreference,
    }),
    [call]
  );
  
  // Calculation-level pseudo mapping (authoritative source)
  const getCalculationPseudoMapping = useCallback(
    (projectRoot: string, calculation: string) =>
      call('get_calculation_pseudo_mapping', { project_root: projectRoot, calculation }),
    [call]
  );
  
  const getPseudoOptionsForCalculation = useCallback(
    (projectRoot: string, calculation: string) =>
      call('get_pseudo_options_for_calculation', { project_root: projectRoot, calculation }),
    [call]
  );

  const materializePseudoFile = useCallback(
    (projectRoot: string, element: string, sha256: string, preferredBasename?: string) =>
      call('materialize_pseudo_file', {
        project_root: projectRoot,
        element,
        sha256,
        preferred_basename: preferredBasename,
      }),
    [call]
  );
  
  const updateCalculationSpeciesMap = useCallback(
    (
      projectRoot: string,
      calculation: string,
      speciesMap: Record<string, { pseudopot?: string; mass?: number }>
    ) => call('update_calculation_species_map', {
      project_root: projectRoot,
      calculation,
      species_map: speciesMap,
    }),
    [call]
  );
  
  const importPseudoFiles = useCallback(
    (projectRoot: string, filePaths: string[]) =>
      call('import_pseudo_files', { project_root: projectRoot, file_paths: filePaths }),
    [call]
  );
  
  const searchLegacyPseudos = useCallback(
    (element: string, projectRoot?: string) =>
      call('search_legacy_pseudos', { element, project_root: projectRoot }),
    [call]
  );
  
  const downloadPseudoByFilename = useCallback(
    (projectRoot: string, filename: string, destDir?: string) =>
      call('download_pseudo_by_filename', {
        project_root: projectRoot,
        filename,
        dest_dir: destDir,
      }),
    [call]
  );
  
  const downloadPseudoCandidate = useCallback(
    (projectRoot: string, candidate: { filename?: string; url?: string }, destDir?: string) =>
      call('download_pseudo_candidate', {
        project_root: projectRoot,
        candidate,
        dest_dir: destDir,
      }),
    [call]
  );
  
  const getRelaxFinalStructurePreview = useCallback(
    (projectRoot: string, calculation: string, step: string) =>
      call('get_relax_final_structure_preview', {
        project_root: projectRoot,
        calculation,
        step,
      }),
    [call]
  );
  
  const saveRelaxFinalStructure = useCallback(
    (
      projectRoot: string,
      calculation: string,
      step: string,
      parentStructureUlid: string,
      slugHint?: string
    ) =>
      call('save_relax_final_structure', {
        project_root: projectRoot,
        calculation,
        step,
        parent_structure_ulid: parentStructureUlid,
        slug_hint: slugHint,
      }),
    [call]
  );

  const listPseudoArchivesStatus = useCallback(
    () => call('list_pseudo_archives_status', {}),
    [call]
  );

  const installPseudoArchive = useCallback(
    (assetName: string) => call('install_pseudo_archive', { asset_name: assetName }),
    [call]
  );

  const analyzeProjectPseudoEffects = useCallback(
    (
      projectRoot: string,
      selections: Array<{
        element: string;
        requested_basename: string;
        requested_sha256?: string;
        requested_sha_family?: string;
        source_kind?: 'project' | 'internal' | 'lib';
        source_path?: string;
      }>
    ) => call('analyze_project_pseudo_effects', { project_root: projectRoot, selections }),
    [call]
  );
  
  // Use ref to maintain stable client object reference
  // This prevents infinite loops in effects that depend on qms
  // The callbacks are already memoized, so they're stable
  // NOTE: see docs/FRONTEND_RPC_PATTERNS.md for expected call counts and effect dependencies
  const clientRef = useRef<QMSClient | null>(null);
  
  // Create client object once, then update state property in place
  // This maintains reference stability while allowing state to be reactive
  if (!clientRef.current) {
    clientRef.current = {
    state,
    call,
    ping,
    getProjectSummary,
    listStructures,
    listCalculations,
    rebuildProjectRegistry,
    listJobs,
    listEngineFamilies,
    listEngines,
    listInstallableEngines,
    installEngine,
    uninstallEngine,
    verifyEngine,
    setActiveEngineInstallation,
    registerEnginePath,
    unregisterEngine,
    listStepPalette,
    setEngineFamily,
    listEngineUiParameters,
    listEngineParameterMetadata,
    getCommonCards,
    setCommonCard,
    getPseudoMapping,
    setPseudoMapping,
    getCalculationPseudoMapping,
    getPseudoOptionsForCalculation,
      materializePseudoFile,
      listPseudoArchivesStatus,
      installPseudoArchive,
      analyzeProjectPseudoEffects,
    updateCalculationSpeciesMap,
    importPseudoFiles,
    searchLegacyPseudos,
    downloadPseudoByFilename,
    downloadPseudoCandidate,
    getRelaxFinalStructurePreview,
    saveRelaxFinalStructure,
    checkConnection,
    refreshDaemonStatus,
  };
  } else {
    // Update state property in place to maintain reference stability
    // All other properties (callbacks) are already stable due to useCallback
    clientRef.current.state = state;
  }
  
  return clientRef.current!;
}

// =============================================================================
// Log Subscription Hook
// =============================================================================

/**
 * Hook to subscribe to daemon log messages
 * 
 * @example
 * function DebugPanel() {
 *   const logs = useQMSLogs();
 *   return <pre>{logs.join('\n')}</pre>;
 * }
 */
export function useQMSLogs(maxLines: number = 100): string[] {
  const [logs, setLogs] = useState<string[]>([]);
  
  useEffect(() => {
    if (!window.qms) return;
    
    const unsubscribe = window.qms.onLog((message) => {
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
    if (!window.qms) return;
    
    // Get initial status
    window.qms.getDaemonStatus().then(setStatus).catch(() => {});
    
    // Subscribe to updates
    const unsubscribe = window.qms.onDaemonStatus(setStatus);
    
    return unsubscribe;
  }, []);
  
  return status;
}
