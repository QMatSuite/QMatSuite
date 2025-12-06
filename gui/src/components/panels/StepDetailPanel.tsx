/**
 * StepDetailPanel - Displays detailed information about a workflow step
 * 
 * Shows step metadata, QE parameters (namelists), and provides
 * parameter editing and the ability to run an individual step.
 */

import { useState, useCallback, useEffect } from 'react';
import type { StepDetail, JobSubmitResult } from '../../types/qv';
import './StepDetailPanel.css';

interface StepDetailPanelProps {
  /** Project root path */
  projectRoot: string;
  /** Workflow selector (slug or name) */
  workflowSelector: string;
  /** Step selector (id, slug, or name) */
  stepSelector: string;
  /** Called to close the panel */
  onClose?: () => void;
  /** Called when a step run is submitted */
  onRunStep?: (result: JobSubmitResult) => void;
  /** Called when parameters are updated */
  onParametersUpdated?: () => void;
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
  bands: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry' },
  ],
  dos: [
    { namelist: 'SYSTEM', key: 'ecutwfc', label: 'Wavefunction Cutoff', type: 'number', unit: 'Ry' },
    { namelist: 'SYSTEM', key: 'ecutrho', label: 'Charge Density Cutoff', type: 'number', unit: 'Ry' },
  ],
};

export function StepDetailPanel({
  projectRoot,
  workflowSelector,
  stepSelector,
  onClose,
  onRunStep,
  onParametersUpdated,
}: StepDetailPanelProps) {
  const [stepDetail, setStepDetail] = useState<StepDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editedParams, setEditedParams] = useState<Record<string, Record<string, unknown>>>({});
  const [hasChanges, setHasChanges] = useState(false);
  
  // Fetch step detail on mount and when selector changes
  useEffect(() => {
    const fetchStepDetail = async () => {
      if (!window.qv) return;
      
      setIsLoading(true);
      setError(null);
      
      try {
        const response = await window.qv.request<StepDetail>('get_step_detail', {
          project_root: projectRoot,
          workflow: workflowSelector,
          step: stepSelector,
        });
        
        if (response.ok && response.data) {
          setStepDetail(response.data);
          // Initialize edited params from current values
          setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
          setHasChanges(false);
        } else {
          setError(response.error?.message || 'Failed to load step details');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchStepDetail();
  }, [projectRoot, workflowSelector, stepSelector]);
  
  // Handle running the step
  const handleRunStep = useCallback(async () => {
    if (!window.qv || !stepDetail) return;
    
    setIsRunning(true);
    
    try {
      const response = await window.qv.request<JobSubmitResult>('run_step', {
        project_root: projectRoot,
        workflow: workflowSelector,
        step: stepSelector,
      });
      
      if (response.ok && response.data) {
        onRunStep?.(response.data);
      } else {
        setError(response.error?.message || 'Failed to run step');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
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
        project_root: projectRoot,
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
      const response = await window.qv.request<StepDetail>('reset_step_params', {
        project_root: projectRoot,
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
  
  if (isLoading) {
    return (
      <div className="step-detail-panel step-detail-panel--loading">
        <div className="loading-spinner" />
        <p>Loading step details...</p>
      </div>
    );
  }
  
  if (error && !stepDetail) {
    return (
      <div className="step-detail-panel step-detail-panel--error">
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
        {onClose && (
          <button className="action-button" onClick={onClose}>
            Close
          </button>
        )}
      </div>
    );
  }
  
  if (!stepDetail) {
    return null;
  }
  
  // Get editable parameters for this step type
  const editableParams = EDITABLE_PARAMS[stepDetail.step_type] || [];
  const hasEditableParams = editableParams.length > 0;
  
  // Extract namelist keys for display
  const namelists = Object.keys(stepDetail.parameters);
  const cards = Object.keys(stepDetail.cards);
  
  return (
    <div className="step-detail-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📋</span>
          {stepDetail.name || stepDetail.id}
        </h2>
        {onClose && (
          <button className="panel-close" onClick={onClose}>×</button>
        )}
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
              <code className="detail-value detail-value--id">{stepDetail.id}</code>
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
