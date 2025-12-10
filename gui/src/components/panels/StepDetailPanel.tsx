/**
 * StepDetailPanel - Displays detailed information about a workflow step
 * 
 * Shows step metadata, QE parameters (namelists), and provides
 * parameter editing and the ability to run an individual step.
 */

import { useState, useCallback, useEffect } from 'react';
import type { StepDetail, JobSubmitResult, WorkflowDetailResult, QVError } from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import './StepDetailPanel.css';

interface StepDetailPanelProps {
  /** Project root path */
  projectRoot: string | null;
  /** Selected workflow detail (from get_workflow_detail) - canonical source for step order */
  selectedWorkflow: WorkflowDetailResult | null;
  /** Selected step ID (ULID from workflow.yaml) */
  selectedStepId: string | null;
  /** Called to close the panel */
  onClose?: () => void;
  /** Called when a step run is submitted */
  onRunStep?: (result: JobSubmitResult) => void;
  /** Called when parameters are updated */
  onParametersUpdated?: () => void;
  /** Called when a step is deleted */
  onStepDeleted?: (stepId: string) => void;
}

// Common editable parameters by step type
const EDITABLE_PARAMS: Record<string, Array<{
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
  selectedWorkflow,
  selectedStepId,
  onClose,
  onRunStep,
  onParametersUpdated,
  onStepDeleted,
}: StepDetailPanelProps) {
  // Workflow selector: always use slug (backend expects workflow slug)
  const workflowSelector = selectedWorkflow?.slug ?? null;
  // Step selector: always use ULID from selectedStepId (must be ULID from workflow.yaml's steps array)
  const stepSelector = selectedStepId;
  
  // INSTRUMENTATION: Log render props to verify correct step ID is being passed
  console.log('[StepDetailPanel] render', {
    workflowSelector,
    stepSelector,
    stepSelectorType: typeof stepSelector,
    stepSelectorLength: stepSelector ? stepSelector.length : 0,
    hasSelectedWorkflow: !!selectedWorkflow,
    workflowStepsCount: selectedWorkflow?.steps?.length ?? 0,
  });
  
  const [stepDetail, setStepDetail] = useState<StepDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editedParams, setEditedParams] = useState<Record<string, Record<string, unknown>>>({});
  const [hasChanges, setHasChanges] = useState(false);
  
  // Delete step state
  const [isDeletingStep, setIsDeletingStep] = useState(false);
  
  // Fetch step detail on mount and when selector changes
  // STATE MACHINE: isLoading -> (success: stepDetail) | (error: error message)
  // Always set isLoading=false in finally block to prevent infinite spinner
  useEffect(() => {
    // Clear previous error and step detail when selectors change
    // This ensures subsequent step selections recover from previous errors
    setError(null);
    setStepDetail(null);
    
    const fetchStepDetail = async () => {
      // INSTRUMENTATION: Log inputs when we start a fetch
      console.log('[StepDetailPanel] fetchStepDetail START', {
        projectRoot: projectRoot ? projectRoot.substring(projectRoot.lastIndexOf('/') + 1) : null,
        workflowSelector,
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
      
      if (!workflowSelector) {
        // Workflow selector missing - show error but still render
        console.log('[StepDetailPanel] Early return: missing workflowSelector');
        setIsLoading(false);
        setStepDetail(null);
        setError('Workflow selector is required');
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
      
      // RACE CONDITION PREVENTION: If selectedWorkflow is provided, validate that stepSelector
      // exists in the workflow's steps list before attempting to fetch. This prevents
      // "Step not found" errors when a step is clicked before the workflow detail has
      // been refreshed after step creation.
      if (selectedWorkflow && selectedWorkflow.steps && selectedWorkflow.steps.length > 0) {
        const stepExists = selectedWorkflow.steps.some(step => step.id === stepSelector);
        if (!stepExists) {
          console.log('[StepDetailPanel] Step not found in workflow steps list, waiting for refresh...', {
            stepSelector,
            availableSteps: selectedWorkflow.steps.map(s => s.id),
          });
          setIsLoading(false);
          setStepDetail(null);
          setError('Step not yet available. Please wait for workflow to refresh.');
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
        
        // CRITICAL: stepSelector MUST be the ULID from workflow.yaml's steps array
        // This is passed as selectedStepId from App.tsx, which gets it from workflow.steps[].id
        // Backend requires step to be the ULID (26 chars), not slug/name/index
        console.log('[StepDetailPanel] calling get_step_detail RPC', {
          project_root: normalizedProjectRoot,
          workflow: workflowSelector, // slug
          step: stepSelector, // ULID from workflow.yaml - the only supported step selector steps array
        });
        
        const response = await window.qv.request<StepDetail>('get_step_detail', {
          project_root: normalizedProjectRoot,
          workflow: workflowSelector, // slug
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
          // Initialize edited params from current values
          setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
          setHasChanges(false);
        } else {
          // Error response: set error message and clear step detail
          // Handle structured errors from daemon (resource_not_found, etc.)
          const errorData = response.error as QVError | undefined;
          let errorMsg = 'Failed to load step details';
          
          if (errorData) {
            // Check for resource_not_found with kind="step" (ghost step)
            if (errorData.code === 'resource_not_found' && errorData.kind === 'step') {
              errorMsg = 'Step not found or step file is missing.';
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            } else if (errorData.message) {
              errorMsg = errorData.message;
            }
          }
          
          console.error('[StepDetailPanel] get_step_detail ERROR', {
            stepSelector,
            error: errorData,
            errorMessage: errorMsg,
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
  }, [projectRoot, workflowSelector, stepSelector, selectedWorkflow]);
  
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
        workflow: workflowSelector,
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
  }, [projectRoot, workflowSelector, stepSelector, stepDetail, onRunStep]);
  
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
      const paramUpdates: Record<string, Record<string, unknown>> = {};
      const editableForType = EDITABLE_PARAMS[stepDetail.step_type] || [];
      
      for (const param of editableForType) {
        const currentValue = stepDetail.parameters[param.namelist]?.[param.key];
        const editedValue = editedParams[param.namelist]?.[param.key];
        
        // Only include if changed
        if (editedValue !== currentValue) {
          if (!paramUpdates[param.namelist]) {
            paramUpdates[param.namelist] = {};
          }
          paramUpdates[param.namelist][param.key] = editedValue;
        }
      }
      
      const response = await window.qv.request<StepDetail>('update_step_params', {
        project_root: normalizedProjectRoot,
        workflow: workflowSelector,
        step: stepSelector,
        parameters: paramUpdates,
      });
      
      if (response.ok && response.data) {
        setStepDetail(response.data);
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
  }, [projectRoot, workflowSelector, stepSelector, stepDetail, editedParams, onParametersUpdated]);
  
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
        workflow: workflowSelector,
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
  }, [projectRoot, workflowSelector, stepSelector, stepDetail, onParametersUpdated]);
  
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
    if (!window.qv || !selectedWorkflow || !selectedStepId || isDeletingStep) return;
    
    // Show confirmation dialog
    const stepType = stepDetail?.step_type || 'step';
    const stepIdShort = selectedStepId.substring(0, 8);
    const confirmed = window.confirm(
      `Delete step "${stepType}" (${stepIdShort}...) from workflow "${selectedWorkflow.name}"?\n\n` +
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
        workflow: workflowSelector,
        step: stepSelector, // ULID from workflow.yaml - the only supported step selector
      });
      
      if (response.ok) {
        // Step deleted successfully
        // Clear step detail and selection
        setStepDetail(null);
        setError(null);
        setIsLoading(false);
        
        // Notify parent to clear selection and refresh workflow
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
  }, [window.qv, selectedWorkflow, selectedStepId, stepDetail, workflowSelector, stepSelector, projectRoot, isDeletingStep, onStepDeleted, onClose]);
  
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
              Try selecting a different step, or refresh the workflow to update the step list.
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
  
  // Get editable parameters for this step type
  const editableParams = EDITABLE_PARAMS[stepDetail.step_type] || [];
  const hasEditableParams = editableParams.length > 0;
  
  // Extract namelist keys for display
  const namelists = Object.keys(stepDetail.parameters);
  const cards = Object.keys(stepDetail.cards);
  
  return (
    <div className="step-detail-panel" data-testid="qv-step-detail">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📋</span>
          {stepDetail.name || stepDetail.id}
        </h2>
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
          {onClose && (
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
        
        {/* All Parameters Section (collapsed by default) */}
        {namelists.length > 0 && (
          <div className="detail-section">
            <h3>All QE Parameters (Namelists)</h3>
            <div className="parameters-container">
              {namelists.map((namelist) => (
                <NamelistSection
                  key={namelist}
                  name={namelist}
                  parameters={stepDetail.parameters[namelist]}
                />
              ))}
            </div>
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
        
        {/* Actions */}
        <div className="detail-actions">
          <button
            className="action-button action-button--primary"
            onClick={handleRunStep}
            disabled={isRunning || isEditing}
          >
            {isRunning ? '⏳ Running...' : '▶️ Run Step'}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

interface NamelistSectionProps {
  name: string;
  parameters: Record<string, unknown>;
}

function NamelistSection({ name, parameters }: NamelistSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const paramEntries = Object.entries(parameters);
  
  if (paramEntries.length === 0) return null;
  
  return (
    <div className="namelist-section">
      <button 
        className="namelist-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="namelist-toggle">{isExpanded ? '▼' : '▶'}</span>
        <span className="namelist-name">&{name}</span>
        <span className="namelist-count">{paramEntries.length} params</span>
      </button>
      
      {isExpanded && (
        <div className="namelist-params">
          {paramEntries.map(([key, value]) => (
            <div key={key} className="param-row">
              <span className="param-key">{key}</span>
              <span className="param-value">{formatParamValue(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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

// Format a parameter value for display
function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return value ? '.true.' : '.false.';
  if (typeof value === 'string') return `'${value}'`;
  if (typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.map(formatParamValue).join(', ');
  return JSON.stringify(value);
}
