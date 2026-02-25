/**
 * CalculationContext — Calculation selection + detail
 *
 * Owns: calculation selection, detail, step selection, tab state,
 * engine guidance, run/delete handlers.
 *
 * Dependency: reads AppShellContext (currentView, showNotification, setCurrentView);
 *             reads ProjectContext (projectRoot, calculations, fetchCalculations, projectLoaded).
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  type ReactNode,
} from 'react';
import { normalizeProjectRoot } from '../utils/pathUtils';
import { useQMSClient } from '../hooks';
import { useAppShell } from './AppShellContext';
import { useProject } from './ProjectContext';
import type {
  CalculationInfo,
  CalculationDetailResult,
  QMSResponse,
  JobSubmitResult,
  PreflightCheckResult,
} from '../types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const ENGINE_DISPLAY_NAMES: Record<string, string> = {
  qe: 'Quantum ESPRESSO',
  vasp: 'VASP',
  xtb: 'xTB',
  lammps: 'LAMMPS',
  orca: 'ORCA',
  gaussian: 'Gaussian',
  abinit: 'ABINIT',
  cp2k: 'CP2K',
  siesta: 'Siesta',
  w90: 'Wannier90',
  yambo: 'Yambo',
  qmcpack: 'QMCPACK',
  pyscf: 'PySCF',
  psi4: 'Psi4',
  gpaw: 'GPAW',
};

export type MissingEngineGuidanceState = {
  engineFamily: string;
  message: string;
  installJobId: string | null;
  installStatus: string;
  installError: string | null;
  installed: boolean;
};

export interface CalculationContextValue {
  // Selection
  selectedCalculationSummary: CalculationInfo | null;
  selectedCalculationDetail: CalculationDetailResult | null;
  selectedCalculation: CalculationInfo | CalculationDetailResult | null;
  selectedStepId: string | null;
  activeCalcTab: 'overview' | 'run' | 'analysis';
  setActiveCalcTab: (tab: 'overview' | 'run' | 'analysis') => void;

  // Engine guidance
  missingEngineGuidance: MissingEngineGuidanceState | null;
  clearMissingEngineGuidance: () => void;
  handleInstallMissingEngine: () => Promise<void>;
  handleConfigureMissingEnginePath: () => Promise<void>;

  // Debug
  setDebugResult: React.Dispatch<React.SetStateAction<QMSResponse | null>>;

  // Handlers
  handleSelectCalculation: (calculation: CalculationInfo) => void;
  handleSelectStep: (stepId: string) => void;
  handleDeleteStep: (stepId: string) => Promise<void>;
  handleRunCalculation: (calculation: CalculationInfo, runMode?: 'incremental' | 'full') => Promise<void>;
  handleGoToJobs: () => void;

  // Setters (for cross-context orchestration in AppLayout)
  setSelectedCalculationSummary: React.Dispatch<React.SetStateAction<CalculationInfo | null>>;
  setSelectedCalculationDetail: React.Dispatch<React.SetStateAction<CalculationDetailResult | null>>;
  setSelectedStepId: React.Dispatch<React.SetStateAction<string | null>>;

  // ENGINE_DISPLAY_NAMES for UI
  ENGINE_DISPLAY_NAMES: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CalculationContext = createContext<CalculationContextValue | null>(null);

export function useCalculation(): CalculationContextValue {
  const ctx = useContext(CalculationContext);
  if (!ctx) throw new Error('useCalculation must be used within <CalculationProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CalculationProvider({ children }: { children: ReactNode }) {
  const { currentView, showNotification, setCurrentView } = useAppShell();
  const { projectRoot, calculations } = useProject();
  const qms = useQMSClient();

  // --- Selection state ------------------------------------------------------
  const [selectedCalculationSummary, setSelectedCalculationSummary] = useState<CalculationInfo | null>(null);
  const [selectedCalculationDetail, setSelectedCalculationDetail] = useState<CalculationDetailResult | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [activeCalcTab, setActiveCalcTab] = useState<'overview' | 'run' | 'analysis'>('overview');
  const [, setDebugResult] = useState<QMSResponse | null>(null);

  // Legacy alias
  const selectedCalculation = selectedCalculationDetail || selectedCalculationSummary;

  // --- Engine guidance ------------------------------------------------------
  const [missingEngineGuidance, setMissingEngineGuidance] = useState<MissingEngineGuidanceState | null>(null);

  // Auto-select ref
  const didAutoSelectCalculationRef = useRef(false);

  const inferMissingEngineFamily = useCallback((message: string): string | null => {
    const normalized = (message || '').toLowerCase();
    if (
      normalized.includes('quantum espresso') ||
      normalized.includes('pw.x') ||
      normalized.includes('qe')
    ) {
      return 'qe';
    }
    for (const family of Object.keys(ENGINE_DISPLAY_NAMES)) {
      if (normalized.includes(family)) {
        return family;
      }
    }
    return null;
  }, []);

  const openMissingEngineGuidance = useCallback((engineFamily: string, message: string) => {
    setMissingEngineGuidance({
      engineFamily,
      message,
      installJobId: null,
      installStatus: '',
      installError: null,
      installed: false,
    });
    setActiveCalcTab('overview');
  }, []);

  const clearMissingEngineGuidance = useCallback(() => {
    setMissingEngineGuidance(null);
  }, []);

  // --- Selection handlers ---------------------------------------------------

  const handleSelectCalculation = useCallback((calculation: CalculationInfo) => {
    console.log('[Calc] handleSelectCalculation called', {
      calculationSlug: calculation.slug,
      calculationId: calculation.calc_ulid,
      stepCount: calculation.steps?.length ?? 0,
    });

    setSelectedCalculationSummary(calculation);
    didAutoSelectCalculationRef.current = true;
    setSelectedCalculationDetail(null);
    setSelectedStepId(null);
    clearMissingEngineGuidance();

    // Fire and forget async detail fetch
    (async () => {
      if (!projectRoot || !window.qms) return;

      try {
        const normalizedRoot = normalizeProjectRoot(projectRoot);
        if (!normalizedRoot) return;

        console.log('[Calc] fetching calculation detail', {
          calculationSlug: calculation.slug,
          calculationId: calculation.calc_ulid,
        });

        const response = await qms.call('get_calculation_detail', {
          project_root: normalizedRoot,
          calculation: calculation.calc_ulid,
        });

        if (response.ok && response.data) {
          const detail = response.data as CalculationDetailResult;
          console.log('[Calc] got calculation detail', {
            calculationSlug: detail.slug,
            stepCount: detail.steps?.length ?? 0,
            stepUlids: detail.steps?.map(s => s.ulid) ?? [],
            stepOrder: detail.steps?.map((s, i) => ({ index: i, ulid: s.ulid, step_type_gen: s.step_type_gen })) ?? [],
          });
          setSelectedCalculationDetail(detail);
        } else {
          console.error('[Calc] get_calculation_detail error', response.error);
          if (response.error?.code === 'registry_out_of_sync') {
            // Let project context handle this
          } else if (response.error?.code === 'resource_not_found' && response.error?.kind === 'calculation') {
            console.warn('[Calc] Calculation not found, will retry after delay', { calculationSlug: calculation.slug });
            setTimeout(async () => {
              const retryResponse = await qms.call('get_calculation_detail', {
                project_root: normalizedRoot,
                calculation: calculation.calc_ulid,
              });
              if (retryResponse.ok && retryResponse.data) {
                setSelectedCalculationDetail(retryResponse.data as CalculationDetailResult);
              }
            }, 500);
          }
        }
      } catch (err) {
        console.error('[Calc] get_calculation_detail exception', err);
        setSelectedCalculationDetail(null);
      }
    })();
  }, [projectRoot, qms, clearMissingEngineGuidance]);

  const handleSelectStep = useCallback((stepId: string) => {
    console.log('[Calc] handleSelectStep called with:', stepId);
    setSelectedStepId(stepId || null);
  }, []);

  const handleDeleteStep = useCallback(async (stepId: string) => {
    console.log('[Calc] handleDeleteStep called with:', stepId);
    if (selectedStepId === stepId) {
      setSelectedStepId(null);
    }
    if (selectedCalculationSummary) {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (normalizedRoot && window.qms) {
        const response = await qms.call('get_calculation_detail', {
          project_root: normalizedRoot,
          calculation: selectedCalculationSummary.slug,
        });
        if (response.ok && response.data) {
          const updatedDetail = response.data as CalculationDetailResult;
          setSelectedCalculationDetail(updatedDetail);
        }
      }
    }
  }, [selectedStepId, selectedCalculationSummary, projectRoot, qms]);

  const handleGoToJobs = useCallback(() => {
    setCurrentView('jobs');
  }, [setCurrentView]);

  // --- Run calculation handler ----------------------------------------------

  const handleRunCalculation = useCallback(async (calculation: CalculationInfo, runMode: 'incremental' | 'full' = 'incremental') => {
    const selectedEngineFamily = selectedCalculationDetail?.engine_family || null;

    const preflightResponse = await qms.call('preflight_check', {
      project_root: projectRoot,
      calculation: calculation.slug,
    });

    if (preflightResponse.ok && preflightResponse.data) {
      const preflight = preflightResponse.data as PreflightCheckResult;

      if (!preflight.ok) {
        // If a bundled engine is still being staged (full variant, first launch),
        // show a non-blocking message instead of the missing engine guidance.
        if (preflight.bundled_engine_staging) {
          showNotification(preflight.bundled_engine_staging.message, 'success');
          return;
        }
        const errorMsg = preflight.errors.join('; ') || 'Pre-flight check failed';
        const inferred = selectedEngineFamily || inferMissingEngineFamily(errorMsg);
        if (inferred) {
          openMissingEngineGuidance(inferred, errorMsg);
        } else {
          showNotification(`Cannot run calculation: ${errorMsg}`, 'error');
        }
        return;
      }

      if (preflight.warnings.length > 0) {
        console.warn('Preflight warnings:', preflight.warnings);
      }
    }

    const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedProjectRoot) {
      showNotification('Project root is required', 'error');
      return;
    }

    const response = await qms.call('run_calculation', {
      project_root: normalizedProjectRoot,
      calculation: calculation.slug,
      run_mode: runMode || 'incremental',
    });

    if (response.ok && response.data) {
      const result = response.data as JobSubmitResult;
      const shortId = result.job_id.slice(0, 8);
      showNotification(`Job #${shortId} started: ${result.target_name}`, 'success');
      clearMissingEngineGuidance();
      setActiveCalcTab('run');
    } else {
      const error = response.error as any;
      if (error?.code === 'CALCULATION_LOCKED') {
        showNotification(
          'Calculation is currently running. Please wait for the current run to complete or stop it first.',
          'error'
        );
      } else if (error?.code === 'ENGINE_NOT_INSTALLED' || inferMissingEngineFamily(error?.message || '')) {
        const inferred = selectedEngineFamily || inferMissingEngineFamily(error?.message || '');
        if (inferred) {
          openMissingEngineGuidance(inferred, error?.message || 'Engine is not installed');
        } else {
          showNotification(`Failed to start job: ${error?.message || 'Unknown error'}`, 'error');
        }
      } else {
        showNotification(`Failed to start job: ${error?.message || 'Unknown error'}`, 'error');
      }
    }

    setDebugResult(response as QMSResponse);
  }, [
    qms,
    projectRoot,
    showNotification,
    selectedCalculationDetail,
    inferMissingEngineFamily,
    openMissingEngineGuidance,
    clearMissingEngineGuidance,
  ]);

  // --- Engine install handlers ----------------------------------------------

  const handleInstallMissingEngine = useCallback(async () => {
    if (!missingEngineGuidance) return;
    const engineFamily = missingEngineGuidance.engineFamily;
    const response = await qms.installEngine(engineFamily, { async: true, source: 'auto' });
    if (!response.ok) {
      setMissingEngineGuidance((prev) => prev ? {
        ...prev,
        installError: response.error?.message || 'Failed to start engine install',
      } : prev);
      return;
    }

    const jobId = response.data?.job_id || null;
    if (!jobId) {
      setMissingEngineGuidance((prev) => prev ? {
        ...prev,
        installed: true,
        installStatus: 'Installed successfully',
        installError: null,
      } : prev);
      return;
    }

    setMissingEngineGuidance((prev) => prev ? {
      ...prev,
      installJobId: jobId,
      installStatus: 'Install queued...',
      installError: null,
    } : prev);
  }, [missingEngineGuidance, qms]);

  const handleConfigureMissingEnginePath = useCallback(async () => {
    if (!missingEngineGuidance) return;
    if (!window.qms?.openDirectory) {
      setMissingEngineGuidance((prev) => prev ? {
        ...prev,
        installError: 'Path picker is unavailable',
      } : prev);
      return;
    }
    const selectedPath = await window.qms.openDirectory();
    if (!selectedPath) return;

    const response = await qms.registerEnginePath(missingEngineGuidance.engineFamily, selectedPath, {
      source: 'user_path',
    });
    if (!response.ok) {
      setMissingEngineGuidance((prev) => prev ? {
        ...prev,
        installError: response.error?.message || 'Failed to register engine path',
      } : prev);
      return;
    }

    setMissingEngineGuidance((prev) => prev ? {
      ...prev,
      installed: true,
      installStatus: 'Path configured',
      installError: null,
      installJobId: null,
    } : prev);
  }, [missingEngineGuidance, qms]);

  // --- Effects --------------------------------------------------------------

  // Effect 1: Reset auto-select ref when leaving calculations view
  useEffect(() => {
    if (currentView !== 'calculations') {
      didAutoSelectCalculationRef.current = false;
    }
  }, [currentView]);

  // Effect 2: Auto-select first calculation + sync list
  useEffect(() => {
    if (currentView === 'calculations' && calculations && calculations.length > 0 && !selectedCalculationSummary && !didAutoSelectCalculationRef.current) {
      const firstCalculation = calculations[0];
      didAutoSelectCalculationRef.current = true;
      handleSelectCalculation(firstCalculation);
    }

    if (selectedCalculationSummary && calculations && !calculations.find(w => w.calc_ulid === selectedCalculationSummary.calc_ulid)) {
      if (calculations.length > 0) {
        const firstCalculation = calculations[0];
        handleSelectCalculation(firstCalculation);
      } else {
        setSelectedCalculationSummary(null);
        setSelectedCalculationDetail(null);
      }
    }
  }, [currentView, calculations, selectedCalculationSummary, handleSelectCalculation]);

  // Effect 3: Engine install polling
  useEffect(() => {
    if (!missingEngineGuidance?.installJobId) return;
    let cancelled = false;

    const pollInstallStatus = async () => {
      const statusResponse = await qms.call('get_job_status', { job_id: missingEngineGuidance.installJobId! });
      if (cancelled) return;
      if (!statusResponse.ok || !statusResponse.data) {
        setMissingEngineGuidance((prev) => prev ? {
          ...prev,
          installError: statusResponse.error?.message || 'Failed to poll install status',
          installJobId: null,
        } : prev);
        return;
      }

      const statusData = statusResponse.data;
      if (!statusData) {
        setMissingEngineGuidance((prev) => prev ? {
          ...prev,
          installError: 'Missing install status payload',
          installJobId: null,
        } : prev);
        return;
      }

      const status = statusData.status;
      const installStatus = statusData.last_log_line || status;

      if (status === 'pending' || status === 'running') {
        setMissingEngineGuidance((prev) => prev ? {
          ...prev,
          installStatus,
          installError: null,
        } : prev);
        return;
      }

      if (status === 'completed') {
        setMissingEngineGuidance((prev) => prev ? {
          ...prev,
          installJobId: null,
          installStatus: 'Installed successfully',
          installError: null,
          installed: true,
        } : prev);
        return;
      }

      setMissingEngineGuidance((prev) => prev ? {
        ...prev,
        installJobId: null,
        installError: statusData.error || installStatus || 'Engine install failed',
      } : prev);
    };

    const timer = setInterval(() => {
      void pollInstallStatus();
    }, 2000);
    void pollInstallStatus();

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [missingEngineGuidance?.installJobId, qms]);

  // Effect 4: Clear all on project root change
  useEffect(() => {
    setSelectedCalculationSummary(null);
    setSelectedCalculationDetail(null);
    setSelectedStepId(null);
    setMissingEngineGuidance(null);
    didAutoSelectCalculationRef.current = false;
  }, [projectRoot]);

  // --- Memoised context value -----------------------------------------------
  const value = useMemo<CalculationContextValue>(() => ({
    selectedCalculationSummary,
    selectedCalculationDetail,
    selectedCalculation,
    selectedStepId,
    activeCalcTab,
    setActiveCalcTab,
    missingEngineGuidance,
    clearMissingEngineGuidance,
    handleInstallMissingEngine,
    handleConfigureMissingEnginePath,
    setDebugResult,
    handleSelectCalculation,
    handleSelectStep,
    handleDeleteStep,
    handleRunCalculation,
    handleGoToJobs,
    setSelectedCalculationSummary,
    setSelectedCalculationDetail,
    setSelectedStepId,
    ENGINE_DISPLAY_NAMES,
  }), [
    selectedCalculationSummary,
    selectedCalculationDetail,
    selectedCalculation,
    selectedStepId,
    activeCalcTab,
    missingEngineGuidance,
    clearMissingEngineGuidance,
    handleInstallMissingEngine,
    handleConfigureMissingEnginePath,
    handleSelectCalculation,
    handleSelectStep,
    handleDeleteStep,
    handleRunCalculation,
    handleGoToJobs,
  ]);

  return (
    <CalculationContext.Provider value={value}>
      {children}
    </CalculationContext.Provider>
  );
}
