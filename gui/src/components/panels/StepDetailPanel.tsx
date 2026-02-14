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
import { useEngineParameterMetadata, type QEParameterMeta } from '../../hooks/useEngineParameterMetadata';
import { ActiveParametersPanel } from '../step_parameters/ActiveParametersPanel';
import { AddParameterPalette } from '../step_parameters/AddParameterPalette';
import { CommonCardKPoints, type CommonCardKPointsRef } from '../common_cards/CommonCardKPoints';
import { isScanRef, getScanId, generateScanId, findReferencedScanIds, makeScanToken } from '../../utils/scanUtils';
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

  // Get engine_family from calculation detail (must be declared before useEngineParameterMetadata)
  const engineFamily = selectedCalculation?.engine_family ?? null;

  // Store stable reference to listEngineUiParameters to avoid including qv object in dependencies
  // The function is memoized in useQVClient, so this ref will be stable across renders
  const listEngineUiParametersRef = useRef(qv.listEngineUiParameters);
  listEngineUiParametersRef.current = qv.listEngineUiParameters;

  // QE parameter metadata hook (shared with Resources view)
  // For QE, pass engineFamily='qe' to maintain backwards compatibility
  const qeMetadata = useEngineParameterMetadata(engineFamily || 'qe');
  // Extract stable function references to avoid effect re-runs
  const { loadSections, loadParameters } = qeMetadata;

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
  const [editedParameterScan, setEditedParameterScan] = useState<Record<string, { values: unknown[] }>>({});
  const [hasChanges, setHasChanges] = useState(false);
  
  // Common cards view model state
  const [commonCards, setCommonCards] = useState<{
    k_points?: {
      raw: string;
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
    };
  } | null>(null);
  const [isLoadingCommonCards, setIsLoadingCommonCards] = useState(false);
  
  // Ref for K_POINTS card to access apply method
  const kPointsRef = useRef<CommonCardKPointsRef>(null);
  const [kPointsDirty, setKPointsDirty] = useState(false);
  const [kPointsApplying, setKPointsApplying] = useState(false);
  
  // Pseudopotential mapping state (read-only, from calculation-level)
  const [pseudoMapping, setPseudoMapping] = useState<{
    species: string[];
    mapping: Record<string, string>;
    pseudo_dir: string;
    available_pseudos: string[];
    warnings: string[];
  } | null>(null);
  const [isLoadingPseudoMapping, setIsLoadingPseudoMapping] = useState(false);
  
  // Relax structure preview state
  const [relaxPreview, setRelaxPreview] = useState<{
    cell: number[][];
    species: string[];
    positions: number[][];
    volume: number;
    n_atoms: number;
  } | null>(null);
  const [isLoadingRelaxPreview, setIsLoadingRelaxPreview] = useState(false);
  const [relaxPreviewError, setRelaxPreviewError] = useState<string | null>(null);
  const [isSavingRelaxStructure, setIsSavingRelaxStructure] = useState(false);
  const [relaxSaveMessage, setRelaxSaveMessage] = useState<string | null>(null);
  
  // Delete step state
  const [isDeletingStep, setIsDeletingStep] = useState(false);
  
  // Get module for current step (for QE metadata loading - still needed for parameter metadata)
  // Note: This is only used for QE parameter metadata (loadSections, loadParameters)
  // UI parameters now use generic list_engine_ui_parameters RPC
  const module = stepDetail && engineFamily === 'qe' ? (() => {
    const stepTypeLower = stepDetail.step_type_gen.toLowerCase();
    if (['scf', 'nscf', 'relax', 'vc-relax', 'md', 'bands_pw', 'dos'].includes(stepTypeLower)) {
      return 'pw';
    }
    if (stepTypeLower === 'bands') {
      return 'bands';
    }
    const moduleMap: Record<string, string> = {
      'ph': 'ph',
      'projwfc': 'projwfc',
      'pp': 'pp',
    };
    return moduleMap[stepTypeLower] || null;
  })() : null;
  
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
  
  // UI parameter metadata (from daemon) - using generic EngineUIParameter type
  const [uiParams, setUiParams] = useState<Array<{
    section?: string;  // Generic section name (replaces namelist for QE)
    key: string;       // Generic key (replaces name for QE)
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
        const stepExists = selectedCalculation.steps.some(step => step.ulid === stepSelector);
        if (!stepExists) {
          console.log('[StepDetailPanel] Step not found in calculation steps list, waiting for refresh...', {
            stepSelector,
            availableSteps: selectedCalculation.steps.map(s => s.ulid),
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
              id: response.data.ulid,
              name: response.data.name,
              step_type: response.data.step_type_gen,
            },
          });
          setStepDetail(response.data);
          setError(null);
          // Initialize edited params from current values (include ALL parameters, not just editable ones)
          setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
          // Initialize edited parameter_scan
          setEditedParameterScan(JSON.parse(JSON.stringify(response.data.parameter_scan || {})));
          setHasChanges(false);
          
          // Load common cards view model
          if (projectRoot && calculationSelector && stepSelector) {
            setIsLoadingCommonCards(true);
            qv.getCommonCards(projectRoot, calculationSelector, stepSelector)
              .then(cardsResponse => {
                if (cardsResponse.ok && cardsResponse.data) {
                  setCommonCards(cardsResponse.data);
                }
              })
              .catch(err => {
                console.error('[StepDetailPanel] Failed to load common cards', err);
              })
              .finally(() => {
                setIsLoadingCommonCards(false);
              });
            
            // Load pseudopotential mapping (calculation-level, read-only reference)
            setIsLoadingPseudoMapping(true);
            qv.getCalculationPseudoMapping(projectRoot, calculationSelector)
              .then(mappingResponse => {
                if (mappingResponse.ok && mappingResponse.data) {
                  setPseudoMapping(mappingResponse.data);
                }
              })
              .catch(err => {
                console.error('[StepDetailPanel] Failed to load pseudo mapping', err);
              })
              .finally(() => {
                setIsLoadingPseudoMapping(false);
              });
          }
          
          // Load relax structure preview for relax/vc-relax steps (preview only, no side effects)
          const stepType = response.data.step_type_gen?.toLowerCase();
          if ((stepType === 'relax' || stepType === 'vc-relax') && projectRoot && calculationSelector && stepSelector) {
            setIsLoadingRelaxPreview(true);
            setRelaxPreviewError(null);
            qv.getRelaxFinalStructurePreview(projectRoot, calculationSelector, stepSelector)
              .then(previewResponse => {
                if (previewResponse.ok && previewResponse.data) {
                  setRelaxPreview(previewResponse.data);
                } else {
                  setRelaxPreviewError(previewResponse.error?.message || 'Failed to load structure preview');
                }
              })
              .catch(err => {
                console.error('[StepDetailPanel] Failed to load relax structure preview', err);
                setRelaxPreviewError(err instanceof Error ? err.message : 'Failed to load structure preview');
              })
              .finally(() => {
                setIsLoadingRelaxPreview(false);
              });
          } else {
            // Clear preview for non-relax steps
            setRelaxPreview(null);
            setRelaxPreviewError(null);
          }
          
          // Load parameter metadata for all sections that have parameters (QE only, for metadata lookup)
          const parameters = response.data.parameters;
          if (module && qeMetadata && parameters && engineFamily === 'qe') {
            // Load sections first, then parameters for each section
            qeMetadata.loadSections(module).then(() => {
              const sectionsToLoad = new Set<string>();
              for (const namelist of Object.keys(parameters)) {
                const sectionKey = namelist.startsWith('&') ? namelist : `&${namelist}`;
                sectionsToLoad.add(sectionKey);
              }
              sectionsToLoad.forEach(section => {
                qeMetadata.loadParameters(module, section);
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
  // Generic engine UI params are fetched via list_engine_ui_parameters RPC.
  // CRITICAL: Do not include `qv` in dependencies - it's a new object reference on every render.
  // Instead, extract engineFamily and stepType as primitive values and depend only on those.
  useEffect(() => {
    if (!stepDetail || !window.qv || !engineFamily) {
      setUiParams([]);
      return;
    }
    
    const stepTypeGen = stepDetail.step_type_gen;
    
    // Track if component is still mounted to prevent state updates after unmount
    let cancelled = false;
    
    // Fetch UI parameters (static metadata, no need to refetch on every render)
    // Use ref to avoid including qv object in dependencies
    listEngineUiParametersRef.current(engineFamily, stepTypeGen)
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
            console.log(`[StepDetailPanel] Loaded ${sorted.length} UI parameters for ${engineFamily}/${stepTypeGen}`, sorted.slice(0, 3).map(p => p.key));
          }
        } else {
          // No parameters available for this engine/step type
          setUiParams([]);
        }
      })
      .catch(err => {
        // Only log if component is still mounted
        if (!cancelled) {
          console.warn('[StepDetailPanel] Failed to load UI parameters', err);
          setUiParams([]);
        }
      });
    
    // Cleanup: mark as cancelled when component unmounts or dependencies change
    return () => {
      cancelled = true;
    };
  }, [stepDetail?.step_type_gen, stepDetail?.ulid, engineFamily]); // Only depend on primitive values - engineFamily and stepType determine when to refetch
  
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
    // Check if parameter being reset is a scan token
    const paramValue = (isEditing ? editedParams : stepDetail?.parameters)?.[namelist]?.[paramName];
    const scanId = isScanRef(paramValue) ? getScanId(paramValue) : null;
    
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
    
    // Prune scan definition if this was the only reference
    if (scanId) {
      const updatedParams = { ...editedParams };
      if (updatedParams[namelist]) {
        updatedParams[namelist] = { ...updatedParams[namelist] };
        delete updatedParams[namelist][paramName];
      }
      const stillReferenced = findReferencedScanIds(
        updatedParams,
        stepDetail?.cards
      ).has(scanId);
      
      if (!stillReferenced) {
        setEditedParameterScan(prev => {
          const updated = JSON.parse(JSON.stringify(prev));
          delete updated[scanId];
          return updated;
        });
      }
    }
    
    setHasChanges(true);
  }, [isEditing, editedParams, stepDetail]);
  
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
      
      // DETERMINISTIC APPLY ORDERING:
      // 1. Apply K_POINTS (common card) FIRST - this updates step.yaml with K_POINTS card
      // 2. Then apply normal parameters - this updates step.yaml with namelist parameters
      // This ensures no interleaving or YAML overwrites
      // Both operations are sequential and atomic (each RPC call is atomic)
      
      if (kPointsRef.current?.isDirty) {
        await kPointsRef.current.apply();
        // K_POINTS apply updates stepDetail via onUpdate callback
        // We need to refresh stepDetail before applying normal params to avoid stale data
        // The onUpdate callback already refreshes stepDetail, so we're good
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
          // CRITICAL: Use deep equality check for arrays/objects, but for scan tokens and scalars, !== is sufficient
          else if (editedValue !== currentValue) {
            if (!paramUpdates[namelist]) {
              paramUpdates[namelist] = {};
            }
            paramUpdates[namelist][paramName] = editedValue;
          }
        }
      }
      
      // INSTRUMENTATION: Log paramUpdates construction
      console.log('[StepDetailPanel] handleSaveParams paramUpdates', {
        paramUpdates_keys: Object.keys(paramUpdates),
        paramUpdates,
        editedParams_keys: Object.keys(editedParams),
        stepDetail_parameters_keys: Object.keys(stepDetail.parameters || {}),
      });
      
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
      
      // Prune parameter_scan to only referenced scan_ids before sending
      const referencedScanIds = findReferencedScanIds(editedParams, stepDetail.cards);
      const prunedParameterScan: Record<string, { values: unknown[] }> = {};
      for (const scanId of referencedScanIds) {
        // CRITICAL: Prefer editedParameterScan (user's changes) over stepDetail.parameter_scan (original)
        // If editedParameterScan has the scanId, use it (even if values are the same - backend does full replace)
        // Otherwise, fall back to stepDetail.parameter_scan to preserve existing values
        if (editedParameterScan[scanId]) {
          prunedParameterScan[scanId] = editedParameterScan[scanId];
        } else if (stepDetail.parameter_scan?.[scanId]) {
          prunedParameterScan[scanId] = stepDetail.parameter_scan[scanId];
        }
      }
      
      // Include parameter_scan updates (send empty {} if no scans to clear orphans, undefined if never had scans)
      // Backend will do full replace, so we must send the complete pruned map
      // IMPORTANT: If user removed all scan refs, send {} explicitly so backend deletes old scans
      // CRITICAL: Always send parameter_scan if there are referenced scans, even if paramUpdates is empty
      // This ensures scan value changes are persisted even when no parameter values changed
      const hasReferencedScans = referencedScanIds.size > 0;
      const stepHadScans = stepDetail.parameter_scan && Object.keys(stepDetail.parameter_scan).length > 0;
      const parameterScanPayload = hasReferencedScans
        ? prunedParameterScan
        : (stepHadScans ? {} : undefined);
      
      // INSTRUMENTATION: Log the exact RPC payload being sent
      console.log('[StepDetailPanel] handleSaveParams RPC payload', {
        step_selector: stepSelector,
        calculation_selector: calculationSelector,
        param_patch: paramUpdates,
        parameter_scan: parameterScanPayload,
        editedParams_keys: Object.keys(editedParams),
        editedParameterScan_keys: Object.keys(editedParameterScan),
        referencedScanIds: Array.from(referencedScanIds),
        prunedParameterScan_keys: Object.keys(prunedParameterScan),
        hasReferencedScans,
        stepHadScans,
      });
      
      const response = await window.qv.request<StepDetail>('update_step_params', {
        project_root: normalizedProjectRoot,
        calculation: calculationSelector,
        step: stepSelector,
        parameters: paramUpdates,
        parameter_scan: parameterScanPayload,
      });
      
      // INSTRUMENTATION: Log the response
      console.log('[StepDetailPanel] handleSaveParams RPC response', {
        ok: response.ok,
        error: response.error,
        data_id: response.data?.ulid,
        data_parameter_scan_keys: response.data ? Object.keys(response.data.parameter_scan || {}) : null,
      });
      
      if (response.ok && response.data) {
        setStepDetail(response.data);
        // Initialize edited params from current values (include ALL parameters, not just editable ones)
        setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
        // Initialize edited parameter_scan
        setEditedParameterScan(JSON.parse(JSON.stringify(response.data.parameter_scan || {})));
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
  }, [projectRoot, calculationSelector, stepSelector, stepDetail, editedParams, editedParameterScan, onParametersUpdated]);
  
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
        setEditedParameterScan(JSON.parse(JSON.stringify(response.data.parameter_scan || {})));
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
      setEditedParameterScan(JSON.parse(JSON.stringify(stepDetail.parameter_scan || {})));
    }
    setHasChanges(false);
    setIsEditing(false);
  }, [stepDetail]);
  
  // Handle scan toggle
  const handleScanToggle = useCallback((namelist: string, paramName: string, enabled: boolean) => {
    if (!stepDetail) return;
    
    // CRITICAL: Capture previous value BEFORE replacing it with token
    const currentValue = (isEditing ? editedParams : stepDetail.parameters)[namelist]?.[paramName];
    const currentScanId = isScanRef(currentValue) ? getScanId(currentValue) : null;
    const prevValue = currentValue; // Capture for initialization
    
    if (enabled) {
      // Turn scan ON: convert value to scan_ref
      // Reuse existing scan_id if already scanned, otherwise generate new one
      const existingScanIds = new Set([
        ...Object.keys(editedParameterScan),
        ...Object.keys(stepDetail.parameter_scan || {}),
      ]);
      const scanId = currentScanId || generateScanId(Array.from(existingScanIds));
      
      // Set parameter to scan_ref
      setEditedParams(prev => {
        const updated = JSON.parse(JSON.stringify(prev));
        if (!updated[namelist]) {
          updated[namelist] = {};
        }
        updated[namelist][paramName] = makeScanToken(scanId);
        return updated;
      });
      
      // Create scan definition ONLY if it does not exist (idempotent)
      // Never overwrite existing arrays
      setEditedParameterScan(prev => {
        const updated = JSON.parse(JSON.stringify(prev));
        if (!updated[scanId]) {
          // Initialize with previous value (captured before token replacement)
          // Only initialize if prevValue is a scalar leaf
          const initialValues = (prevValue !== null && prevValue !== undefined && 
            !isScanRef(prevValue) && // Don't initialize from token
            (typeof prevValue === 'string' || typeof prevValue === 'number' || typeof prevValue === 'boolean' || 
             (Array.isArray(prevValue) && prevValue.every((item: any) => 
               item === null || typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean'
             ))))
            ? [prevValue]
            : [];
          updated[scanId] = { values: initialValues };
        }
        // If scanId already exists, do NOT overwrite (preserve existing values array)
        return updated;
      });
      
      setHasChanges(true);
    } else {
      // Turn scan OFF: convert scan_ref back to concrete value
      if (currentScanId) {
        // Get first value from scan definition, or use null
        const scanDef = editedParameterScan[currentScanId];
        const firstValue = scanDef?.values?.[0] ?? null;
        
        // Set parameter to concrete value
        setEditedParams(prev => {
          const updated = JSON.parse(JSON.stringify(prev));
          if (!updated[namelist]) {
            updated[namelist] = {};
          }
          updated[namelist][paramName] = firstValue;
          return updated;
        });
        
        // Check if scan_id is still referenced by other parameters
        // Build updated params with this param removed
        const updatedParams = { ...editedParams };
        if (updatedParams[namelist]) {
          updatedParams[namelist] = { ...updatedParams[namelist] };
          delete updatedParams[namelist][paramName];
        }
        const stillReferenced = findReferencedScanIds(
          updatedParams,
          stepDetail.cards
        ).has(currentScanId);
        
        // Remove scan definition if not referenced
        if (!stillReferenced) {
          setEditedParameterScan(prev => {
            const updated = JSON.parse(JSON.stringify(prev));
            delete updated[currentScanId];
            return updated;
          });
        } else {
          // Warn if other params still reference it (UI-level warning, non-blocking)
          console.debug(`[ScanToggle] Scan ID '${currentScanId}' still referenced by other parameters, keeping definition`);
        }
        
        setHasChanges(true);
      }
    }
  }, [stepDetail, editedParams, editedParameterScan, isEditing]);
  
  // Handle scan values change
  const handleScanValuesChange = useCallback((scanId: string, values: unknown[]) => {
    setEditedParameterScan(prev => {
      const updated = JSON.parse(JSON.stringify(prev));
      updated[scanId] = { values };
      return updated;
    });
    setHasChanges(true);
  }, []);
  
  // Update hasChanges to include K_POINTS dirty state
  useEffect(() => {
    const paramsDirty = Object.keys(editedParams).length > 0;
    setHasChanges(kPointsDirty || paramsDirty);
  }, [editedParams, kPointsDirty]);
  
  // Ensure metadata is loaded when entering edit mode
  // This is critical: metadata must be available before ParameterValueEditor renders
  // CRITICAL: Use stable dependencies to prevent infinite loops
  // - Track previous isEditing state to detect false->true transition
  // - Use stable namelists key (sorted string) instead of stepDetail object
  const prevIsEditingRef = useRef(false);
  const stableNamelistsKey = useMemo(() => {
    if (!stepDetail?.parameters) return '';
    return Object.keys(stepDetail.parameters)
      .map(n => n.startsWith('&') ? n : `&${n}`)
      .sort()
      .join('|');
  }, [stepDetail?.parameters]);
  
  useEffect(() => {
    // Only run when isEditing transitions from false to true, or when module/namelists change
    const isEnteringEdit = !prevIsEditingRef.current && isEditing;
    prevIsEditingRef.current = isEditing;
    
    // stableNamelistsKey is derived from stepDetail.parameters, so we don't need stepDetail in deps
    if (isEnteringEdit && module && stableNamelistsKey) {
      // Parse namelists from stable key (sorted, pipe-separated)
      const sectionsToLoad = new Set(stableNamelistsKey.split('|').filter(Boolean));
      
      if (sectionsToLoad.size > 0) {
        // Load sections first, then parameters for each section
        // loadParameters is now idempotent, so calling it multiple times is safe
        loadSections(module).then(() => {
          sectionsToLoad.forEach(section => {
            loadParameters(module, section);
          });
        });
      }
    }
  }, [isEditing, module, stableNamelistsKey, loadSections, loadParameters]);
  
  // Handle deleting the step
  const handleDeleteStep = useCallback(async () => {
    if (!window.qv || !selectedCalculation || !selectedStepId || isDeletingStep) return;
    
    // Show confirmation dialog
    const stepType = stepDetail?.step_type_gen || 'step';
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
  
  // Get editable parameters from generic UI metadata
  // For QE, section maps to namelist (e.g., "SYSTEM" -> "SYSTEM")
  // For other engines, section may be different (e.g., "general")
  const editableParams = uiParams.length > 0
    ? uiParams.map(p => ({
        namelist: p.section || 'CONTROL',  // Use section as namelist (QE compatibility), fallback to CONTROL
        key: p.key,
        label: p.label,
        type: (p.type === 'float' ? 'number' : p.type) as 'number' | 'text' | 'select',
        options: p.options || undefined,
        unit: p.unit,
        description: p.description,
      }))
    : [];
  const hasEditableParams = editableParams.length > 0;
  
  // Extract card keys for display, filtering out K_POINTS (handled separately in Common Cards)
  const cards = Object.keys(stepDetail.cards).filter(card => {
    // K_POINTS is ALWAYS handled by CommonCardKPoints, never shown in raw QE Cards section
    if (card === 'K_POINTS' && module === 'pw') {
      return false;
    }
    return true;
  });
  
  // Check if we have a K_POINTS card at all (either parsed or raw)
  const hasKPointsCard = stepDetail.cards?.K_POINTS != null;
  
  // Show breadcrumb if we have calculation name and step position info
  const showBreadcrumb = calculationName && stepIndex != null && stepIndex >= 0 && stepCount != null && stepCount > 0;
  
  return (
    <div className={`step-detail-panel ${isFocusMode ? 'step-detail-panel--focus' : ''}`} data-testid="qv-step-detail">
      {/* Focus mode header: breadcrumb + run button */}
      {isFocusMode && showBreadcrumb && (
        <div className="step-detail-panel__focus-header">
          <div className="step-detail-panel__focus-breadcrumb">
            {calculationName} › Step {stepIndex + 1} · {stepDetail?.step_type_gen?.toUpperCase() || 'STEP'}
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
      
      <div className="panel-header panel-header--sticky">
        <div className="qv-step-header-content">
          {!isFocusMode && showBreadcrumb && (
            <div className="qv-step-breadcrumb">
              {calculationName} · Step {stepIndex + 1} of {stepCount}
            </div>
          )}
          <div className="qv-step-header-main">
            <h2 className="panel-title qv-step-title">
              <span className="panel-icon">📋</span>
              {stepDetail.name || stepDetail.ulid}
            </h2>
            {!isFocusMode && stepDetail.step_type_gen && (
              <div className="qv-step-type-chip">
                {stepDetail.step_type_gen.toUpperCase()}
              </div>
            )}
          </div>
        </div>
        <div className="panel-header-actions">
          {/* Edit/Apply/Cancel/Reset buttons - always visible in header */}
          {!isEditing ? (
            <button
              className="panel-action-btn"
              onClick={() => setIsEditing(true)}
              title="Edit step parameters"
              data-testid="qv-btn-edit-step-params"
            >
              ✏️ Edit
            </button>
          ) : (
            <>
              <button 
                className="panel-action-btn panel-action-btn--secondary"
                onClick={handleCancelEdit}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button 
                className="panel-action-btn panel-action-btn--warning"
                onClick={handleResetParams}
                disabled={isSaving}
              >
                Reset
              </button>
              <button
                className="panel-action-btn panel-action-btn--primary"
                onClick={handleSaveParams}
                disabled={!hasChanges || isSaving || kPointsApplying}
                data-testid="qv-btn-apply-step-params"
              >
                {isSaving || kPointsApplying ? 'Saving...' : 'Apply'}
              </button>
            </>
          )}
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
              <span className="detail-value step-type-badge">{stepDetail.step_type_gen}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">ID</span>
              <code className="detail-value detail-value--id" data-testid="qv-step-id">{stepDetail.ulid}</code>
            </div>
            {stepDetail.structure && (
              <div className="detail-item">
                <span className="detail-label">Structure</span>
                <code className="detail-value">{stepDetail.structure}</code>
              </div>
            )}
          </div>
        </div>
        
        {/* Common Parameters Section (includes K_POINTS) */}
        {(hasEditableParams || hasKPointsCard) && (
          <div className="detail-section">
            <div className="section-header">
              <h3>Common Parameters</h3>
            </div>
            
            {/* Editable params */}
            {hasEditableParams && (
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
            )}
            
            {/* Show message if no guided parameters available */}
            {!hasEditableParams && (
              <div className="step-detail__no-params">
                <p>No guided parameters available for this engine/step type.</p>
                <p>Use the raw parameter editor below to edit parameters directly.</p>
              </div>
            )}
            
            {/* K_POINTS editor (inline with Common Parameters) */}
            {hasKPointsCard && module === 'pw' && (
              isLoadingCommonCards ? (
                <div className="common-cards-loading">
                  <p>Loading K_POINTS...</p>
                </div>
              ) : (
                <CommonCardKPoints
                  ref={kPointsRef}
                  viewModel={commonCards?.k_points || null}
                  rawCardData={stepDetail.cards?.K_POINTS}
                  isEditing={isEditing}
                  onDirtyChange={setKPointsDirty}
                  onApplyingChange={setKPointsApplying}
                  onUpdate={async (viewModel) => {
                    if (!projectRoot || !calculationSelector || !stepSelector) return;
                    
                    const response = await qv.setCommonCard(
                      projectRoot,
                      calculationSelector,
                      stepSelector,
                      'K_POINTS',
                      viewModel
                    );
                    
                    if (response.ok && response.data) {
                      setStepDetail(response.data);
                      const cardsResponse = await qv.getCommonCards(
                        projectRoot,
                        calculationSelector,
                        stepSelector
                      );
                      if (cardsResponse.ok && cardsResponse.data) {
                        setCommonCards(cardsResponse.data);
                      }
                      setKPointsDirty(false);
                      onParametersUpdated?.();
                    } else {
                      setError(response.error?.message || 'Failed to update K_POINTS card');
                    }
                  }}
                />
              )
            )}
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
            </div>
          </div>
          
          {/* Active Parameters Panel */}
          {stepDetail && (
            <ActiveParametersPanel
              stepDetail={{
                ...stepDetail,
                parameters: isEditing ? editedParams : stepDetail.parameters,
                parameter_scan: isEditing ? editedParameterScan : stepDetail.parameter_scan,
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
              onScanToggle={handleScanToggle}
              onScanValuesChange={handleScanValuesChange}
              editedParameterScan={isEditing ? editedParameterScan : undefined}
            />
          )}
        </div>
        
        {/* Pseudopotentials Section - Read-only reference */}
        {module === 'pw' && stepDetail && (
          <div className="detail-section">
            <div className="section-header">
              <h3>Pseudopotentials</h3>
              <div className="section-actions">
                <button
                  className="section-action-btn"
                  onClick={() => {
                    // Navigate back to calculation overview
                    // This will be handled by parent component
                    if (onClose) {
                      onClose();
                    }
                  }}
                  title="Edit pseudopotentials in Calculation Overview"
                >
                  Edit in Calculation Overview →
                </button>
              </div>
            </div>
            
            {isLoadingPseudoMapping ? (
              <div className="common-cards-loading">
                <p>Loading pseudopotential mapping...</p>
              </div>
            ) : pseudoMapping ? (
              <div className="pseudo-reference">
                {pseudoMapping.warnings && pseudoMapping.warnings.length > 0 && (
                  <div className="pseudo-warnings">
                    {pseudoMapping.warnings.map((w, i) => (
                      <div key={i} className="pseudo-warning">
                        ⚠️ {w}
                      </div>
                    ))}
                  </div>
                )}
                
                {pseudoMapping.species.length > 0 ? (
                  <div className="pseudo-reference-list">
                    {pseudoMapping.species.map((species) => {
                      const pseudo = pseudoMapping.mapping[species] || '—';
                      return (
                        <div key={species} className="pseudo-reference-item">
                          <strong>{species}</strong>: <code className="pseudo-filename">{pseudo}</code>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="pseudo-empty">No species found in structure.</p>
                )}
                
                <div className="pseudo-info">
                  <small>
                    Pseudopotentials are managed at the calculation level and shared across all steps.
                    Click "Edit in Calculation Overview" to modify mappings.
                  </small>
                </div>
              </div>
            ) : (
              <p className="common-cards-empty">No pseudopotential mapping available</p>
            )}
          </div>
        )}
        
        {/* Relaxed Structure Section (for relax/vc-relax steps) */}
        {stepDetail && (stepDetail.step_type_gen?.toLowerCase() === 'relax' || stepDetail.step_type_gen?.toLowerCase() === 'vc-relax') && (
          <div className="detail-section">
            <div className="section-header">
              <h3>Relaxed Structure</h3>
            </div>
            
            {isLoadingRelaxPreview ? (
              <div className="common-cards-loading">
                <p>Loading final structure preview...</p>
              </div>
            ) : relaxPreviewError ? (
              <div className="common-cards-error">
                <p>⚠️ {relaxPreviewError}</p>
                <p className="common-cards-empty" style={{ fontSize: '0.9em', marginTop: '8px' }}>
                  Step may not have completed successfully, or output file may be missing.
                </p>
              </div>
            ) : relaxPreview ? (
              <div className="relax-structure-preview">
                <div className="relax-preview-info">
                  <p><strong>Final structure detected</strong></p>
                  <p style={{ fontSize: '0.9em', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {relaxPreview.n_atoms} atoms, Volume: {relaxPreview.volume.toFixed(2)} Å³
                  </p>
                </div>
                
                {relaxSaveMessage && (
                  <div className={`relax-save-message ${relaxSaveMessage.includes('Success') || relaxSaveMessage.includes('✅') ? 'relax-save-message--success' : ''}`}>
                    {relaxSaveMessage}
                  </div>
                )}
                
                <div className="relax-structure-actions" style={{ marginTop: '12px' }}>
                  <button
                    className="action-button action-button--primary"
                    disabled={isSavingRelaxStructure || !selectedCalculation?.structure_ulid}
                    onClick={async () => {
                      if (!projectRoot || !calculationSelector || !stepSelector || !selectedCalculation?.structure_ulid) return;
                      
                      setIsSavingRelaxStructure(true);
                      setRelaxSaveMessage(null);
                      
                      try {
                        const response = await qv.saveRelaxFinalStructure(
                          projectRoot,
                          calculationSelector,
                          stepSelector,
                          selectedCalculation.structure_ulid,
                          stepDetail.name ? `${stepDetail.name} relaxed` : undefined
                        );
                        
                        if (response.ok && response.data) {
                          if (response.data.already_exists) {
                            setRelaxSaveMessage(`Structure already exists: ${response.data.structure_ulid.slice(0, 8)}...`);
                          } else {
                            setRelaxSaveMessage(`✅ Saved as new structure: ${response.data.structure_ulid.slice(0, 8)}...`);
                          }
                          // Clear message after 5 seconds
                          setTimeout(() => setRelaxSaveMessage(null), 5000);
                          onParametersUpdated?.(); // Trigger refresh to show new structure
                        } else {
                          setRelaxSaveMessage(`❌ Failed: ${response.error?.message || 'Unknown error'}`);
                          setTimeout(() => setRelaxSaveMessage(null), 5000);
                        }
                      } catch (e) {
                        setRelaxSaveMessage(`❌ Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
                        setTimeout(() => setRelaxSaveMessage(null), 5000);
                      } finally {
                        setIsSavingRelaxStructure(false);
                      }
                    }}
                  >
                    {isSavingRelaxStructure ? 'Saving...' : 'Save as new Structure'}
                  </button>
                  {!selectedCalculation?.structure_ulid && (
                    <p className="common-cards-empty" style={{ fontSize: '0.85em', marginTop: '8px' }}>
                      ⚠️ Calculation has no structure reference. Cannot save relaxed structure.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <p className="common-cards-empty">No structure preview available</p>
            )}
          </div>
        )}
        
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
