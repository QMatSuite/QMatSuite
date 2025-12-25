/**
 * StepDetailPanel - Displays detailed information about a calculation step
 * 
 * Shows step metadata, QE parameters (namelists), and provides
 * parameter editing and the ability to run an individual step.
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type { StepDetail, JobSubmitResult, CalculationDetailResult, QVError } from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import { useQVClient } from '../../hooks/useQVClient';
import { useQEParameterMetadata, type QEParameterMeta } from '../../hooks/useQEParameterMetadata';
import { ActiveParametersPanel } from '../step_parameters/ActiveParametersPanel';
import { AddParameterPalette } from '../step_parameters/AddParameterPalette';
import './StepDetailPanel.css';

interface StepDetailPanelProps {
  /** Project root path */
  projectRoot: string | null;
  /** Selected calculation detail (from get_calculation_detail) - canonical source for step order */
  selectedCalculation: CalculationDetailResult | null;
  /** Selected step ID (ULID from calculation.yaml) */
  selectedStepId: string | null;
  /** Calculation name for breadcrumb display */
  calculationName?: string | null;
  /** Step index (0-based) for breadcrumb display */
  stepIndex?: number;
  /** Total step count for breadcrumb display */
  stepCount?: number;
  /** Whether this panel is in focus mode (expanded as main workspace) */
  isFocusMode?: boolean;
  /** Calculation absolute path for reveal button in focus mode */
  calculationAbsolutePath?: string | null;
  /** Step YAML absolute path (directory) for reveal button in focus mode */
  stepYamlAbsolutePath?: string | null;
  /** Called to close the panel */
  onClose?: () => void;
  /** Called when a step run is submitted */
  onRunStep?: (result: JobSubmitResult) => void;
  /** Called when parameters are updated */
  onParametersUpdated?: () => void;
  /** Called when a step is deleted */
  onStepDeleted?: (stepId: string) => void;
}

/**
 * Map step_type to QE module for UI parameter fetching.
 * Most pw.x-based steps use module "pw", but bands.x uses module "bands".
 */
function stepTypeToModule(stepType: string): string | null {
  const stepTypeLower = stepType.toLowerCase();
  
  // pw.x-based steps
  if (['scf', 'nscf', 'relax', 'vc-relax', 'md', 'bands_pw', 'dos'].includes(stepTypeLower)) {
    return 'pw';
  }
  
  // bands.x post-processing
  if (stepTypeLower === 'bands') {
    return 'bands';
  }
  
  // Other modules map 1:1
  const moduleMap: Record<string, string> = {
    'ph': 'ph',
    'projwfc': 'projwfc',
    'pp': 'pp',
  };
  
  return moduleMap[stepTypeLower] || null;
}

// Legacy fallback parameters (used if UI metadata is not available)
const LEGACY_EDITABLE_PARAMS: Record<string, Array<{
  namelist: string;
  key: string;
  label: string;
  type: 'number' | 'text' | 'select';
  options?: string[];
  unit?: string;
  description?: string;
}>> = {
  scf: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry', description: 'Kinetic energy cutoff for wavefunctions' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry', description: 'Kinetic energy cutoff for charge density (default: 4×ecutwfc)' },
    { namelist: 'SYSTEM', key: 'occupations', label: 'Occupations', type: 'select', options: ['smearing', 'fixed', 'tetrahedra', 'tetrahedra_lin', 'tetrahedra_opt'] },
    { namelist: 'SYSTEM', key: 'smearing', label: 'Smearing Type', type: 'select', options: ['gaussian', 'gauss', 'methfessel-paxton', 'm-p', 'mp', 'marzari-vanderbilt', 'cold', 'm-v', 'mv', 'fermi-dirac', 'f-d', 'fd'] },
    { namelist: 'SYSTEM', key: 'degauss', label: 'Smearing Width', type: 'number', unit: 'Ry', description: 'Gaussian spreading for Brillouin-zone integration' },
    { namelist: 'ELECTRONS', key: 'conv_thr', label: 'Convergence Threshold', type: 'number', description: 'Convergence threshold for self-consistency' },
  ],
  nscf: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'occupations', label: 'Occupations', type: 'select', options: ['smearing', 'fixed', 'tetrahedra', 'tetrahedra_lin', 'tetrahedra_opt'] },
    { namelist: 'SYSTEM', key: 'smearing', label: 'Smearing Type', type: 'select', options: ['gaussian', 'methfessel-paxton', 'marzari-vanderbilt', 'fermi-dirac'] },
    { namelist: 'SYSTEM', key: 'degauss', label: 'Smearing Width', type: 'number', unit: 'Ry' },
    { namelist: 'ELECTRONS', key: 'conv_thr', label: 'Convergence Threshold', type: 'number' },
  ],
  relax: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'CONTROL', key: 'forc_conv_thr', label: 'Force Convergence', type: 'number', unit: 'Ry/au', description: 'Convergence threshold on forces' },
    { namelist: 'ELECTRONS', key: 'conv_thr', label: 'SCF Convergence', type: 'number' },
  ],
  bands_pw: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry', description: 'Kinetic energy cutoff for wavefunctions' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry', description: 'Kinetic energy cutoff for charge density (default: 4×ecutwfc)' },
    { namelist: 'SYSTEM', key: 'nbnd', label: 'Number of Bands', type: 'number', description: 'Number of bands to compute' },
    { namelist: 'ELECTRONS', key: 'conv_thr', label: 'Convergence Threshold', type: 'number', description: 'Convergence threshold for self-consistency' },
  ],
  bands: [
    { namelist: 'BANDS', key: 'filband', label: 'Output File', type: 'text', description: 'Name of output file for band data' },
    { namelist: 'BANDS', key: 'lsym', label: 'Use Symmetry', type: 'select', options: ['.true.', '.false.'], description: 'Use symmetry to reduce k-points' },
  ],
  dos: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry' },
  ],
};

export function StepDetailPanel({
  projectRoot,
  selectedCalculation,
  selectedStepId,
  calculationName,
  stepIndex,
  stepCount,
  isFocusMode = false,
  calculationAbsolutePath,
  stepYamlAbsolutePath,
  onClose,
  onRunStep,
  onParametersUpdated,
  onStepDeleted,
}: StepDetailPanelProps) {
  const qv = useQVClient();
  
  // Store stable reference to listQeUiParameters to avoid including qv object in dependencies
  // The function is memoized in useQVClient, so this ref will be stable across renders
  const listQeUiParametersRef = useRef(qv.listQeUiParameters);
  listQeUiParametersRef.current = qv.listQeUiParameters;
  
  // QE parameter metadata hook (shared with Resources view)
  const qeMetadata = useQEParameterMetadata();
  
  // Calculation selector: always use slug (backend expects calculation slug)
  const calculationSelector = selectedCalculation?.slug ?? null;
  // Step selector: always use ULID from selectedStepId (must be ULID from calculation.yaml's steps array)
  const stepSelector = selectedStepId;
  
  // INSTRUMENTATION: Log render props to verify correct step ID is being passed
  console.log('[StepDetailPanel] render', {
    calculationSelector,
    stepSelector,
    stepSelectorType: typeof stepSelector,
    stepSelectorLength: stepSelector ? stepSelector.length : 0,
    hasSelectedCalculation: !!selectedCalculation,
    calculationStepsCount: selectedCalculation?.steps?.length ?? 0,
  });
  
  const [stepDetail, setStepDetail] = useState<StepDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<QVError['details'] | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editedParams, setEditedParams] = useState<Record<string, Record<string, unknown>>>({});
  const [hasChanges, setHasChanges] = useState(false);
  
  // Delete step state
  const [isDeletingStep, setIsDeletingStep] = useState(false);
  
  // Get module for current step (after stepDetail is declared)
  const module = stepDetail ? stepTypeToModule(stepDetail.step_type) : null;
  
  // Build parameter metadata map for quick lookup
  // This map is built from already-loaded parameters in qeMetadata.parameters
  const parameterMetadataMap = useMemo(() => {
    const map = new Map<string, QEParameterMeta>();
    
    if (!module) return map;
    
    // Add parameters from already-loaded data
    for (const param of qeMetadata.parameters) {
      const key = `${param.module}::${param.section}::${param.name}`;
      map.set(key, param);
    }
    
    return map;
  }, [module, qeMetadata.parameters]);
  
  // UI parameter metadata (from daemon)
  const [uiParams, setUiParams] = useState<Array<{
    namelist: string;
    name: string;
    label: string;
    type: string;
    unit?: string;
    description?: string;
    options?: string[] | null;
    importance?: string;
  }>>([]);
  
  // Fetch step detail on mount and when selector changes
  // STATE MACHINE: isLoading -> (success: stepDetail) | (error: error message)
  // Always set isLoading=false in finally block to prevent infinite spinner
  useEffect(() => {
    // Clear previous error and step detail when selectors change
    // This ensures subsequent step selections recover from previous errors
    setError(null);
    setErrorDetails(null);
    setStepDetail(null);
    
    const fetchStepDetail = async () => {
      // INSTRUMENTATION: Log inputs when we start a fetch
      console.log('[StepDetailPanel] fetchStepDetail START', {
        projectRoot: projectRoot ? projectRoot.substring(projectRoot.lastIndexOf('/') + 1) : null,
        calculationSelector,
        stepSelector,
      });
      
      // Early return checks - these should NOT set isLoading=true
      if (!window.qv || !stepSelector) {
        // Don't fetch if stepSelector is missing, but still render the panel
        console.log('[StepDetailPanel] Early return: missing stepSelector or window.qv');
        setIsLoading(false);
        setStepDetail(null);
        setError(null);
        return;
      }
      
      if (!calculationSelector) {
        // Calculation selector missing - show error but still render
        console.log('[StepDetailPanel] Early return: missing calculationSelector');
        setIsLoading(false);
        setStepDetail(null);
        setError('Calculation selector is required');
        return;
      }
      
      if (!projectRoot) {
        // Project root missing
        console.log('[StepDetailPanel] Early return: missing projectRoot');
        setIsLoading(false);
        setStepDetail(null);
        setError('Project root is required');
        return;
      }
      
      // RACE CONDITION PREVENTION: If selectedCalculation is provided, validate that stepSelector
      // exists in the calculation's steps list before attempting to fetch. This prevents
      // "Step not found" errors when a step is clicked before the calculation detail has
      // been refreshed after step creation.
      if (selectedCalculation && selectedCalculation.steps && selectedCalculation.steps.length > 0) {
        const stepExists = selectedCalculation.steps.some(step => step.id === stepSelector);
        if (!stepExists) {
          console.log('[StepDetailPanel] Step not found in calculation steps list, waiting for refresh...', {
            stepSelector,
            availableSteps: selectedCalculation.steps.map(s => s.id),
          });
          setIsLoading(false);
          setStepDetail(null);
          setError('Step not yet available. Please wait for calculation to refresh.');
          return;
        }
      }
      
      // Set loading state before making request
      // CRITICAL: This must be paired with setIsLoading(false) in finally block
      setIsLoading(true);
      setError(null);
      setStepDetail(null);
      
      try {
        // Normalize project_root to absolute path (backend expects normalized paths)
        // NOTE: Backend expects project_root as normalized absolute path, see tests/daemon/test_gui_job_and_step_flows.py
        const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
        if (!normalizedProjectRoot) {
          throw new Error('Project root is required');
        }
        
        // CRITICAL: stepSelector MUST be the ULID from calculation.yaml's steps array
        // This is passed as selectedStepId from App.tsx, which gets it from calculation.steps[].id
        // Backend requires step to be the ULID (26 chars), not slug/name/index
        console.log('[StepDetailPanel] calling get_step_detail RPC', {
          project_root: normalizedProjectRoot,
          calculation: calculationSelector, // slug
          step: stepSelector, // ULID from calculation.yaml - the only supported step selector steps array
        });
        
        const response = await window.qv.request<StepDetail>('get_step_detail', {
          project_root: normalizedProjectRoot,
          calculation: calculationSelector, // slug
          step: stepSelector, // ULID - the only supported step selector
        });
        
        // INSTRUMENTATION: Log success or error separately
        if (response.ok && response.data) {
          // Success: set step detail and clear error
          console.log('[StepDetailPanel] get_step_detail SUCCESS', {
            stepSelector,
            stepDetail: {
              id: response.data.id,
              name: response.data.name,
              step_type: response.data.step_type,
            },
          });
          setStepDetail(response.data);
          setError(null);
          // Initialize edited params from current values (include ALL parameters, not just editable ones)
          setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
          setHasChanges(false);
          
          // Load parameter metadata for all sections that have parameters
          const stepModule = stepTypeToModule(response.data.step_type);
          const parameters = response.data.parameters;
          if (stepModule && qeMetadata && parameters) {
            // Load sections first, then parameters for each section
            qeMetadata.loadSections(stepModule).then(() => {
              const sectionsToLoad = new Set<string>();
              for (const namelist of Object.keys(parameters)) {
                const sectionKey = namelist.startsWith('&') ? namelist : `&${namelist}`;
                sectionsToLoad.add(sectionKey);
              }
              sectionsToLoad.forEach(section => {
                qeMetadata.loadParameters(stepModule, section);
              });
            });
          }
        } else {
          // Error response: set error message and clear step detail
          // Handle structured errors from daemon (resource_not_found, registry_out_of_sync, etc.)
          const errorData = response.error as QVError | undefined;
          let errorMsg = 'Failed to load step details';
          
          if (errorData) {
            // Check for registry_out_of_sync error
            if (errorData.code === 'registry_out_of_sync') {
              errorMsg = errorData.message || 'Registry is out of sync with the filesystem.';
              // Store detailed error information for display
              setErrorDetails({
                ...errorData.details,
                expected_path: errorData.expected_path,
                actual_state: errorData.actual_state,
                reason: errorData.details?.reason || 'registry_out_of_sync',
              });
            }
            // Check for resource_not_found with kind="step" (ghost step or DAG mismatch)
            else if (errorData.code === 'resource_not_found' && errorData.kind === 'step') {
              errorMsg = errorData.message || 'Step not found or step file is missing.';
              // Store detailed error information for display
              if (errorData.details) {
                setErrorDetails(errorData.details);
              } else {
                setErrorDetails(null);
              }
            } else if (errorData.message) {
              errorMsg = errorData.message;
              setErrorDetails(errorData.details || null);
            } else {
              setErrorDetails(null);
            }
          } else {
            setErrorDetails(null);
          }
          
          console.error('[StepDetailPanel] get_step_detail ERROR', {
            stepSelector,
            error: errorData,
            errorMessage: errorMsg,
            errorDetails,
          });
          setError(errorMsg);
          setStepDetail(null);
        }
      } catch (e) {
        // Exception: set error message and clear step detail
        // This handles cases where the RPC client throws an Error
        const errorMsg = e instanceof Error ? e.message : 'Unknown error';
        console.error('[StepDetailPanel] get_step_detail EXCEPTION', {
          stepSelector,
          error: e,
          errorMessage: errorMsg,
        });
        setError(errorMsg);
        setStepDetail(null);
      } finally {
        // CRITICAL: Always set isLoading=false in finally block to prevent infinite spinner
        // This ensures the spinner stops even if there's an error or the component unmounts
        // There must be NO code path where we set isLoading=true but never reach this finally block
        setIsLoading(false);
      }
    };
    
    fetchStepDetail();
  }, [projectRoot, calculationSelector, stepSelector, selectedCalculation]);
  
  // Fetch UI parameters when stepDetail changes
  // QE UI params are static metadata; we only fetch once per module+stepType combination.
  // CRITICAL: Do not include `qv` in dependencies - it's a new object reference on every render.
  // Instead, extract module and stepType as primitive values and depend only on those.
  useEffect(() => {
    if (!stepDetail || !window.qv) {
      setUiParams([]);
      return;
    }
    
    const module = stepTypeToModule(stepDetail.step_type);
    const stepType = stepDetail.step_type;
    
    if (!module) {
      // No module mapping - use legacy params or empty
      setUiParams([]);
      return;
    }
    
    // Track if component is still mounted to prevent state updates after unmount
    let cancelled = false;
    
    // Fetch UI parameters (static metadata, no need to refetch on every render)
    // Use ref to avoid including qv object in dependencies
    listQeUiParametersRef.current(module, stepType)
      .then(response => {
        // Only update state if component is still mounted
        if (cancelled) return;
        
        if (response.ok && response.data?.parameters) {
          // Sort by importance: core first, then advanced
          const sorted = [...response.data.parameters].sort((a, b) => {
            const importanceOrder: Record<string, number> = { 'core': 0, 'high': 0, 'medium': 1, 'advanced': 2, 'low': 2 };
            const aOrder = importanceOrder[a.importance || 'medium'] ?? 1;
            const bOrder = importanceOrder[b.importance || 'medium'] ?? 1;
            return aOrder - bOrder;
          });
          setUiParams(sorted);
          
          // Development logging (can be removed later)
          if (sorted.length > 0) {
            console.log(`[StepDetailPanel] Loaded ${sorted.length} UI parameters for ${module}/${stepType}`, sorted.slice(0, 3).map(p => p.name));
          }
        } else {
          // Fall back to empty (will use legacy params)
          setUiParams([]);
        }
      })
      .catch(err => {
        // Only log if component is still mounted
        if (!cancelled) {
          console.warn('[StepDetailPanel] Failed to load UI parameters, using fallback', err);
          setUiParams([]);
        }
      });
    
    // Cleanup: mark as cancelled when component unmounts or dependencies change
    return () => {
      cancelled = true;
    };
  }, [stepDetail?.step_type, stepDetail?.id]); // Only depend on primitive values - module and stepType determine when to refetch
  
  // Handle running the step
  const handleRunStep = useCallback(async () => {
    if (!window.qv || !stepDetail) return;
    
    setIsRunning(true);
    setError(null);
    
    try {
      // Normalize project_root (same as get_step_detail)
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }
      
      const response = await window.qv.request<JobSubmitResult>('run_step', {
        project_root: normalizedProjectRoot,
        calculation: calculationSelector,
        step: stepSelector,
      });
      
      if (response.ok && response.data) {
        onRunStep?.(response.data);
      } else {
        const errorMsg = response.error?.message || 'Failed to run step';
        setError(errorMsg);
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Unknown error';
      setError(errorMsg);
    } finally {
      setIsRunning(false);
    }
  }, [projectRoot, calculationSelector, stepSelector, stepDetail, onRunStep]);
  
  // Handle parameter change
  const handleParamChange = useCallback((namelist: string, key: string, value: unknown) => {
    setEditedParams(prev => {
      const updated = { ...prev };
      if (!updated[namelist]) {
        updated[namelist] = {};
      }
      updated[namelist] = { ...updated[namelist], [key]: value };
      return updated;
    });
    setHasChanges(true);
  }, []);
  
  // Handle parameter reset (remove user value, fallback to default)
  const handleParameterReset = useCallback((namelist: string, paramName: string) => {
    setEditedParams(prev => {
      const updated = { ...prev };
      if (updated[namelist] && updated[namelist][paramName] !== undefined) {
        updated[namelist] = { ...updated[namelist] };
        delete updated[namelist][paramName];
        if (Object.keys(updated[namelist]).length === 0) {
          delete updated[namelist];
        }
      }
      return updated;
    });
    setHasChanges(true);
  }, []);
  
  // Handle parameter remove (delete from step)
  const handleParameterRemove = useCallback((namelist: string, paramName: string) => {
    setEditedParams(prev => {
      const updated = { ...prev };
      if (!updated[namelist]) {
        updated[namelist] = {};
      }
      // Set to null to mark for removal
      updated[namelist][paramName] = null;
      return updated;
    });
    setHasChanges(true);
  }, []);
  
  // Handle add parameter
  const handleAddParameter = useCallback((section: string, paramName: string) => {
    // Enter edit mode if not already editing
    if (!isEditing) {
      setIsEditing(true);
    }
    
    // Load parameter metadata if needed
    if (module) {
      const sectionKey = section.startsWith('&') ? section : `&${section}`;
      qeMetadata.loadParameters(module, sectionKey).then(() => {
        // After loading, add the parameter with empty string (user will edit it)
        setEditedParams(prev => {
          const updated = { ...prev };
          if (!updated[section]) {
            updated[section] = {};
          }
          // Add parameter with empty string as placeholder (will be edited by user)
          updated[section][paramName] = '';
          return updated;
        });
        setHasChanges(true);
      });
    }
  }, [module, qeMetadata, isEditing]);
  
  // Save parameter changes
  const handleSaveParams = useCallback(async () => {
    if (!window.qv || !stepDetail) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      // Normalize project_root
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }
      
      // Build the parameter update object
      // Include ALL parameters from editedParams (not just editable ones)
      const paramUpdates: Record<string, Record<string, unknown>> = {};
      
      // Process all edited parameters
      for (const [namelist, params] of Object.entries(editedParams)) {
        const currentNamelist = stepDetail.parameters[namelist] || {};
        
        for (const [paramName, editedValue] of Object.entries(params)) {
          const currentValue = currentNamelist[paramName];
          
          // If editedValue is null, mark for removal
          if (editedValue === null) {
            if (!paramUpdates[namelist]) {
              paramUpdates[namelist] = {};
            }
            paramUpdates[namelist][paramName] = null;
          }
          // If value changed, include the update
          else if (editedValue !== currentValue) {
            if (!paramUpdates[namelist]) {
              paramUpdates[namelist] = {};
            }
            paramUpdates[namelist][paramName] = editedValue;
          }
        }
      }
      
      // Also check for removed parameters (present in stepDetail but not in editedParams)
      for (const [namelist, params] of Object.entries(stepDetail.parameters)) {
        const editedNamelist = editedParams[namelist] || {};
        
        for (const paramName of Object.keys(params)) {
          // If parameter was in original but not in edited (and not explicitly set to null), skip
          // (We only remove if explicitly set to null in editedParams)
          if (!(paramName in editedNamelist)) {
            // Parameter not changed, skip
            continue;
          }
        }
      }
      
      const response = await window.qv.request<StepDetail>('update_step_params', {
        project_root: normalizedProjectRoot,
        calculation: calculationSelector,
        step: stepSelector,
        parameters: paramUpdates,
      });
      
      if (response.ok && response.data) {
        setStepDetail(response.data);
        // Initialize edited params from current values (include ALL parameters, not just editable ones)
        setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
        setHasChanges(false);
        setIsEditing(false);
        onParametersUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to save parameters');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [projectRoot, calculationSelector, stepSelector, stepDetail, editedParams, onParametersUpdated]);
  
  // Reset parameters
  const handleResetParams = useCallback(async () => {
    if (!window.qv || !stepDetail) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      // Normalize project_root
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }
      
      const response = await window.qv.request<StepDetail>('reset_step_params', {
        project_root: normalizedProjectRoot,
        calculation: calculationSelector,
        step: stepSelector,
      });
      
      if (response.ok && response.data) {
        setStepDetail(response.data);
        setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
        setHasChanges(false);
        onParametersUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to reset parameters');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [projectRoot, calculationSelector, stepSelector, stepDetail, onParametersUpdated]);
  
  // Cancel editing
  const handleCancelEdit = useCallback(() => {
    if (stepDetail) {
      setEditedParams(JSON.parse(JSON.stringify(stepDetail.parameters)));
    }
    setHasChanges(false);
    setIsEditing(false);
  }, [stepDetail]);
  
  // Handle deleting the step
  const handleDeleteStep = useCallback(async () => {
    if (!window.qv || !selectedCalculation || !selectedStepId || isDeletingStep) return;
    
    // Show confirmation dialog
    const stepType = stepDetail?.step_type || 'step';
    const stepIdShort = selectedStepId.substring(0, 8);
    const confirmed = window.confirm(
      `Delete step "${stepType}" (${stepIdShort}...) from calculation "${selectedCalculation.name}"?\n\n` +
      `This will move the step file to the project's trash folder. It cannot be undone from the GUI.`
    );
    
    if (!confirmed) return;
    
    setIsDeletingStep(true);
    setError(null);
    
    try {
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }
      
      const response = await window.qv.request('delete_step', {
        project_root: normalizedProjectRoot,
        calculation: calculationSelector,
        step: stepSelector, // ULID from calculation.yaml - the only supported step selector
      });
      
      if (response.ok) {
        // Step deleted successfully
        // Clear step detail and selection
        setStepDetail(null);
        setError(null);
        setIsLoading(false);
        
        // Notify parent to clear selection and refresh calculation
        if (onStepDeleted) {
          onStepDeleted(selectedStepId);
        }
        
        // Close panel if onClose is available
        if (onClose) {
          onClose();
        }
      } else {
        const errorMsg = response.error?.message || 'Failed to delete step';
        setError(errorMsg);
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Unknown error';
      setError(errorMsg);
    } finally {
      setIsDeletingStep(false);
    }
  }, [window.qv, selectedCalculation, selectedStepId, stepDetail, calculationSelector, stepSelector, projectRoot, isDeletingStep, onStepDeleted, onClose]);
  
  // STATE MACHINE RENDER LOGIC:
  // 1. No step selected → show "No step selected"
  // 2. Loading → show spinner (NOT error)
  // 3. Error (and not loading) → show error banner (NOT spinner)
  // 4. No stepDetail but not loading and no error → show fallback message
  // 5. stepDetail exists → render step detail
  
  if (!selectedStepId) {
    // No step selected
    return (
      <div className="step-detail-panel" data-testid="qv-step-detail">
        <div className="panel-header">
          <h2 className="panel-title">Step Detail</h2>
          {onClose && (
            <button className="panel-close" onClick={onClose}>×</button>
          )}
        </div>
        <div className="panel-content">
          <p>No step selected</p>
        </div>
      </div>
    );
  }
  
  if (isLoading) {
    // Loading state: show spinner (do NOT show error while loading)
    return (
      <div className="step-detail-panel step-detail-panel--loading" data-testid="qv-step-detail">
        <div className="loading-spinner" />
        <p>Loading step details...</p>
      </div>
    );
  }
  
  if (error) {
    // Error state: show error banner (NOT spinner, NOT step detail)
    // This handles cases like "Step file not found" (ghost step)
    // CRITICAL: isLoading must be false at this point (ensured by finally block)
    // Users can click another step to recover from this error state
    return (
      <div className="step-detail-panel step-detail-panel--error" data-testid="qv-step-detail">
        <div className="panel-header">
          <h2 className="panel-title">Step Detail</h2>
          {onClose && (
            <button className="panel-close" onClick={onClose}>×</button>
          )}
        </div>
        <div className="panel-content">
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <div className="error-message">
              {errorDetails && (
                <div className="error-details" style={{ marginTop: '12px', padding: '12px', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px', fontSize: '0.9em' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>Details:</div>
                  {errorDetails.calculation_path && (
                    <div style={{ marginBottom: '4px' }}>
                      <strong>Calculation file:</strong> <code style={{ fontSize: '0.85em' }}>{errorDetails.calculation_path}</code>
                    </div>
                  )}
                  {(errorDetails.expected_step_path || errorDetails.expected_path) && (
                    <div style={{ marginBottom: '4px' }}>
                      <strong>Expected step YAML:</strong> <code style={{ fontSize: '0.85em' }}>{errorDetails.expected_step_path || errorDetails.expected_path}</code>
                    </div>
                  )}
                  {errorDetails.actual_state && (
                    <div style={{ marginTop: '8px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                      Issue: {errorDetails.actual_state}
                    </div>
                  )}
                  {errorDetails.reason && (
                    <div style={{ marginTop: '8px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                      Reason: {errorDetails.reason === 'step_file_missing' ? 'Step file missing' : errorDetails.reason === 'step_not_in_calculation_dag' ? 'Step not in calculation DAG' : errorDetails.reason === 'registry_out_of_sync' ? 'Registry out of sync' : errorDetails.reason}
                    </div>
                  )}
                  <div style={{ marginTop: '12px', paddingTop: '8px', borderTop: '1px solid var(--border-color)' }}>
                    <em>If you edited files manually, click "Refresh" in the Calculations panel to rebuild the project registry.</em>
                  </div>
                </div>
              )}
              <strong>Error loading step:</strong>
              <p>{error}</p>
            </div>
          </div>
          <div className="error-actions">
            {onClose && (
              <button className="action-button" onClick={onClose}>
                Close
              </button>
            )}
            <p className="error-hint">
              Try selecting a different step, or refresh the calculation to update the step list.
            </p>
          </div>
        </div>
      </div>
    );
  }
  
  if (!stepDetail) {
    // No step detail but not loading and no error → fallback message
    // This should rarely happen, but handle it gracefully
    return (
      <div className="step-detail-panel" data-testid="qv-step-detail">
        <div className="panel-header">
          <h2 className="panel-title">Step Detail</h2>
          {onClose && (
            <button className="panel-close" onClick={onClose}>×</button>
          )}
        </div>
        <div className="panel-content">
          <p>Step detail not available</p>
        </div>
      </div>
    );
  }
  
  // Get editable parameters: prefer UI metadata, fall back to legacy
  const editableParams = uiParams.length > 0
    ? uiParams.map(p => ({
        namelist: p.namelist,
        key: p.name,
        label: p.label,
        type: (p.type === 'float' ? 'number' : p.type) as 'number' | 'text' | 'select',
        options: p.options || undefined,
        unit: p.unit,
        description: p.description,
      }))
    : (LEGACY_EDITABLE_PARAMS[stepDetail.step_type] || []);
  const hasEditableParams = editableParams.length > 0;
  
  // Extract card keys for display
  const cards = Object.keys(stepDetail.cards);
  
  // Show breadcrumb if we have calculation name and step position info
  const showBreadcrumb = calculationName && stepIndex != null && stepIndex >= 0 && stepCount != null && stepCount > 0;
  
  return (
    <div className={`step-detail-panel ${isFocusMode ? 'step-detail-panel--focus' : ''}`} data-testid="qv-step-detail">
      {/* Focus mode header: breadcrumb + run button */}
      {isFocusMode && showBreadcrumb && (
        <div className="step-detail-panel__focus-header">
          <div className="step-detail-panel__focus-breadcrumb">
            {calculationName} › Step {stepIndex + 1} · {stepDetail?.step_type?.toUpperCase() || 'STEP'}
          </div>
          <button
            className="step-detail-panel__focus-run-btn"
            onClick={handleRunStep}
            disabled={isRunning || isEditing}
            title="Run this step"
          >
            <span className="step-detail-panel__focus-run-icon">▶️</span>
            <span>Run step</span>
          </button>
        </div>
      )}
      
      <div className="panel-header">
        <div className="qv-step-header-content">
          {!isFocusMode && showBreadcrumb && (
            <div className="qv-step-breadcrumb">
              {calculationName} · Step {stepIndex + 1} of {stepCount}
            </div>
          )}
          <div className="qv-step-header-main">
            <h2 className="panel-title qv-step-title">
              <span className="panel-icon">📋</span>
              {stepDetail.name || stepDetail.id}
            </h2>
            {!isFocusMode && stepDetail.step_type && (
              <div className="qv-step-type-chip">
                {stepDetail.step_type.toUpperCase()}
              </div>
            )}
          </div>
        </div>
        <div className="panel-header-actions">
          <button
            className="panel-action-btn panel-action-btn--danger"
            onClick={handleDeleteStep}
            disabled={isDeletingStep}
            title="Delete this step"
            data-testid="qv-delete-step-btn"
          >
            {isDeletingStep ? 'Deleting...' : '🗑️ Delete'}
          </button>
          {onClose && !isFocusMode && (
            <button className="panel-close" onClick={onClose}>×</button>
          )}
        </div>
      </div>
      
      <div className="panel-content">
        {/* Error banner */}
        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
            <button className="error-dismiss" onClick={() => setError(null)}>×</button>
          </div>
        )}
        
        {/* Overview Section */}
        <div className="detail-section">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Type</span>
              <span className="detail-value step-type-badge">{stepDetail.step_type}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">ID</span>
              <code className="detail-value detail-value--id" data-testid="qv-step-id">{stepDetail.id}</code>
            </div>
            {stepDetail.structure && (
              <div className="detail-item">
                <span className="detail-label">Structure</span>
                <code className="detail-value">{stepDetail.structure}</code>
              </div>
            )}
          </div>
        </div>
        
        {/* Editable Parameters Section */}
        {hasEditableParams && (
          <div className="detail-section">
            <div className="section-header">
              <h3>Common Parameters</h3>
              {!isEditing ? (
                <button 
                  className="section-action-btn"
                  onClick={() => setIsEditing(true)}
                >
                  ✏️ Edit
                </button>
              ) : (
                <div className="section-actions">
                  <button 
                    className="section-action-btn section-action-btn--secondary"
                    onClick={handleCancelEdit}
                    disabled={isSaving}
                  >
                    Cancel
                  </button>
                  <button 
                    className="section-action-btn section-action-btn--danger"
                    onClick={handleResetParams}
                    disabled={isSaving}
                  >
                    Reset
                  </button>
                  <button 
                    className="section-action-btn section-action-btn--primary"
                    onClick={handleSaveParams}
                    disabled={!hasChanges || isSaving}
                  >
                    {isSaving ? 'Saving...' : 'Apply'}
                  </button>
                </div>
              )}
            </div>
            
            <div className="param-form">
              {editableParams.map((param) => {
                const currentValue = editedParams[param.namelist]?.[param.key] ?? 
                                    stepDetail.parameters[param.namelist]?.[param.key] ?? '';
                
                return (
                  <div key={`${param.namelist}.${param.key}`} className="param-field">
                    <label className="param-field__label">
                      {param.label}
                      {param.unit && <span className="param-field__unit">({param.unit})</span>}
                    </label>
                    
                    {param.type === 'select' ? (
                      <select
                        className="param-field__input"
                        value={String(currentValue || '')}
                        onChange={(e) => handleParamChange(param.namelist, param.key, e.target.value || undefined)}
                        disabled={!isEditing}
                      >
                        <option value="">-- Not set --</option>
                        {param.options?.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={param.type === 'number' ? 'text' : 'text'}
                        className="param-field__input"
                        value={currentValue === undefined || currentValue === null ? '' : String(currentValue)}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (param.type === 'number') {
                            handleParamChange(param.namelist, param.key, val === '' ? undefined : parseFloat(val));
                          } else {
                            handleParamChange(param.namelist, param.key, val || undefined);
                          }
                        }}
                        placeholder={param.description || `Enter ${param.label.toLowerCase()}`}
                        disabled={!isEditing}
                      />
                    )}
                    
                    {param.description && isEditing && (
                      <span className="param-field__description">{param.description}</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        
        {/* Active Parameters Section (VSCode Settings style) */}
        <div className="detail-section">
          <div className="section-header">
            <h3>Active Parameters</h3>
            <div className="section-actions">
              {module && (
                <AddParameterPalette
                  module={module}
                  stepParameters={isEditing ? editedParams : stepDetail.parameters}
                  onAddParameter={handleAddParameter}
                />
              )}
              {!isEditing ? (
                <button 
                  className="section-action-btn"
                  onClick={() => setIsEditing(true)}
                >
                  ✏️ Edit
                </button>
              ) : (
                <>
                  <button 
                    className="section-action-btn section-action-btn--secondary"
                    onClick={handleCancelEdit}
                    disabled={isSaving}
                  >
                    Cancel
                  </button>
                  <button 
                    className="section-action-btn section-action-btn--danger"
                    onClick={handleResetParams}
                    disabled={isSaving}
                  >
                    Reset All
                  </button>
                  <button 
                    className="section-action-btn section-action-btn--primary"
                    onClick={handleSaveParams}
                    disabled={!hasChanges || isSaving}
                  >
                    {isSaving ? 'Saving...' : 'Apply'}
                  </button>
                </>
              )}
            </div>
          </div>
          
          {/* Active Parameters Panel */}
          {stepDetail && (
            <ActiveParametersPanel
              stepDetail={{
                ...stepDetail,
                parameters: isEditing ? editedParams : stepDetail.parameters,
              }}
              module={module}
              metadata={{
                parameters: parameterMetadataMap,
                modules: qeMetadata.modules,
              }}
              isEditing={isEditing}
              onParameterChange={handleParamChange}
              onParameterReset={handleParameterReset}
              onParameterRemove={handleParameterRemove}
            />
          )}
        </div>
        
        {/* Cards Section */}
        {cards.length > 0 && (
          <div className="detail-section">
            <h3>QE Cards</h3>
            <div className="cards-container">
              {cards.map((card) => (
                <CardSection
                  key={card}
                  name={card}
                  data={stepDetail.cards[card]}
                />
              ))}
            </div>
          </div>
        )}
        
        {/* Species Overrides Section */}
        {Object.keys(stepDetail.species_overrides).length > 0 && (
          <div className="detail-section">
            <h3>Species Overrides</h3>
            <div className="species-container">
              {Object.entries(stepDetail.species_overrides).map(([species, overrides]) => (
                <div key={species} className="species-override">
                  <span className="species-name">{species}</span>
                  <code className="species-values">
                    {JSON.stringify(overrides, null, 2)}
                  </code>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* File Location Section */}
        <div className="detail-section">
          <h3>File Location</h3>
          <div className="file-location">
            <code className="file-location__path" title={stepDetail.absolute_path} data-testid="qv-step-file-path">
              {stepDetail.absolute_path}
            </code>
            <button 
              className="file-location__reveal-btn"
              onClick={() => window.qv?.revealPath?.(stepDetail.absolute_path)}
              title="Reveal in Finder"
            >
              📂 Reveal
            </button>
          </div>
        </div>
        
        {/* Actions - hide in focus mode (run button is in header) */}
        {!isFocusMode && (
          <div className="detail-actions">
            <button
              className="action-button action-button--primary"
              onClick={handleRunStep}
              disabled={isRunning || isEditing}
            >
              {isRunning ? '⏳ Running...' : '▶️ Run Step'}
            </button>
          </div>
        )}
      </div>
      
      {/* Focus mode footer: reveal button */}
      {isFocusMode && (stepYamlAbsolutePath || calculationAbsolutePath) && (
        <div className="step-detail-panel__focus-footer">
          <button
            className="step-detail-panel__focus-reveal-btn"
            onClick={() => window.qv?.revealPath?.(stepYamlAbsolutePath || calculationAbsolutePath!)}
            title={stepYamlAbsolutePath ? "Reveal step YAML folder in Finder/Explorer" : "Reveal calculation folder in Finder/Explorer"}
          >
            📂
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

interface CardSectionProps {
  name: string;
  data: Record<string, unknown>;
}

function CardSection({ name, data }: CardSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div className="card-section">
      <button 
        className="card-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="card-toggle">{isExpanded ? '▼' : '▶'}</span>
        <span className="card-name">{name}</span>
      </button>
      
      {isExpanded && (
        <pre className="card-content">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
