/**
 * WorkflowListPanel - Displays a list of workflows in a project
 */

import { useState, useCallback } from 'react';
import type { WorkflowInfo } from '../../types/qv';
import './WorkflowListPanel.css';

interface WorkflowListPanelProps {
  workflows: WorkflowInfo[] | null;
  isLoading?: boolean;
  selectedId?: string | null;
  onSelect?: (workflow: WorkflowInfo) => void;
  onRename?: (workflow: WorkflowInfo) => void;
  onDelete?: (workflow: WorkflowInfo) => void;
  onRefreshProjectRegistry?: () => void;
}

export function WorkflowListPanel({ 
  workflows, 
  isLoading, 
  selectedId,
  onSelect,
  onRename,
  onDelete,
  onRefreshProjectRegistry,
}: WorkflowListPanelProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const handleRefresh = useCallback(async () => {
    if (!onRefreshProjectRegistry) return;
    setIsRefreshing(true);
    try {
      await onRefreshProjectRegistry();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefreshProjectRegistry]);
  if (isLoading) {
    return (
      <div className="workflow-list-panel workflow-list-panel--loading">
        <div className="loading-spinner" />
        <p>Loading workflows...</p>
      </div>
    );
  }
  
  if (!workflows) {
    return (
      <div className="workflow-list-panel workflow-list-panel--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Workflows Loaded</h3>
          <p>Click "List Workflows" to view workflows in this project.</p>
        </div>
      </div>
    );
  }
  
  if (workflows.length === 0) {
    return (
      <div className="workflow-list-panel workflow-list-panel--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Workflows Found</h3>
          <p>This project doesn't have any workflows yet.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="workflow-list-panel" data-testid="qv-workflows-view">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📊</span>
          Workflows
        </h2>
        <div className="panel-header__actions">
          {onRefreshProjectRegistry && (
            <button
              className="panel-refresh-btn"
              onClick={handleRefresh}
              disabled={isRefreshing}
              title="Refresh project registry"
            >
              {isRefreshing ? '⟳' : '🔄'} Refresh
            </button>
          )}
          <span className="panel-count">{workflows.length} total</span>
        </div>
      </div>
      
      <div className="workflow-list" data-testid="qv-workflows-list">
        {workflows.map((workflow) => (
          <div
            key={workflow.id}
            className={`workflow-item ${selectedId === workflow.id ? 'workflow-item--selected' : ''}`}
            data-testid="qv-workflow-row"
            data-workflow-slug={workflow.slug}
          >
            <button
              className="workflow-item__content"
              onClick={() => onSelect?.(workflow)}
            >
              <div className="workflow-item__main">
                <div className="workflow-item__name">{workflow.name}</div>
                <div className="workflow-item__structure">
                  Structure: <code>{workflow.structure || 'none'}</code>
                </div>
              </div>
              
              <div className="workflow-item__details">
                <div className="workflow-item__stat">
                  <span className="stat-value">{workflow.n_steps}</span>
                  <span className="stat-label">steps</span>
                </div>
                <div className="workflow-item__mode">
                  <span className={`mode-badge mode-badge--${workflow.mode}`}>
                    {workflow.mode}
                  </span>
                </div>
              </div>
              
              <div className="workflow-item__steps">
                {workflow.steps.map((step, idx) => (
                  <span key={step.id} className="step-chip">
                    {idx > 0 && <span className="step-arrow">→</span>}
                    <span className="step-type">{step.type}</span>
                  </span>
                ))}
              </div>
              
              <div className="workflow-item__path">
                <code>{workflow.path}</code>
              </div>
            </button>
            
            {(onRename || onDelete) && (
              <div className="workflow-item__actions">
                {onRename && (
                  <button
                    className="item-action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRename(workflow);
                    }}
                    title="Rename workflow"
                  >
                    ✏️
                  </button>
                )}
                {onDelete && (
                  <button
                    className="item-action-btn item-action-btn--danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(workflow);
                    }}
                    title="Delete workflow"
                  >
                    🗑️
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Workflow Detail View
// =============================================================================

import { useState, useCallback } from 'react';
import type { StructureInfo, WorkflowDetailResult } from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';

interface WorkflowDetailPanelProps {
  workflowSummary: WorkflowInfo | null;  // Summary from list_workflows (for high-level fields)
  workflowDetail: WorkflowDetailResult | null;  // Detail from get_workflow_detail (canonical steps array)
  projectRoot: string;
  structures?: StructureInfo[];
  onClose?: () => void;
  onRunWorkflow?: (workflow: WorkflowInfo) => void;
  onSelectStep?: (stepId: string) => void;
  onDeleteStep?: (stepId: string) => void;  // Callback when step is deleted
  onGoToJobs?: () => void;
  onWorkflowUpdated?: () => void;
}

export function WorkflowDetailPanel({ 
  workflowSummary,
  workflowDetail,
  projectRoot,
  structures,
  onClose,
  onRunWorkflow,
  onSelectStep,
  onDeleteStep,
  onGoToJobs,
  onWorkflowUpdated,
}: WorkflowDetailPanelProps) {
  // IMPORTANT: When workflowDetail is available, we MUST use its steps array
  // as the canonical source of step order, since it is built from workflow.yaml.
  // Fall back to summary only if detail is still loading.
  const workflowForSteps = workflowDetail ?? workflowSummary;
  // Both WorkflowInfo and WorkflowDetailResult have compatible fields (id, name, slug, structure, mode, n_steps)
  const workflow = workflowForSteps as WorkflowInfo | null;
  const [isReordering, setIsReordering] = useState(false);
  const [stepOrder, setStepOrder] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Add step state
  const [showAddStep, setShowAddStep] = useState(false);
  const [newStepType, setNewStepType] = useState('');
  const [newStepName, setNewStepName] = useState('');
  const [isAddingStep, setIsAddingStep] = useState(false);
  
  // Import step state
  const [isImportingStep, setIsImportingStep] = useState(false);
  
  // Delete step state
  const [isDeletingStep, setIsDeletingStep] = useState(false);
  
  // Handle deleting a step
  const handleDeleteStep = useCallback(async (stepId: string, stepType: string) => {
    if (!window.qv || !workflowForSteps || isDeletingStep) return;
    
    // Show confirmation dialog
    const confirmed = window.confirm(
      `Delete step "${stepType}" (${stepId.substring(0, 8)}...) from workflow "${workflowForSteps.name}"?\n\n` +
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
        workflow: workflowForSteps.slug,
        step: stepId, // ULID from workflow.yaml
      });
      
      if (response.ok) {
        // Step deleted successfully
        // Clear selection if the deleted step was selected
        if (onDeleteStep) {
          onDeleteStep(stepId);
        }
        // Refresh workflow detail to show updated steps list
        await onWorkflowUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to delete step');
        // Still refresh workflow detail to avoid stale entries
        await onWorkflowUpdated?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      // Still refresh workflow detail to avoid stale entries
      await onWorkflowUpdated?.();
    } finally {
      setIsDeletingStep(false);
    }
  }, [workflowForSteps, projectRoot, isDeletingStep, onDeleteStep, onWorkflowUpdated]);
  
  // Handle showing add step form
  const handleShowAddStep = useCallback(() => {
    setShowAddStep(true);
    setNewStepType('');
    setNewStepName('');
    setError(null);
  }, []);
  
  // Handle adding a new step
  const handleAddStep = useCallback(async () => {
    if (!window.qv || !workflowForSteps || !newStepType) return;
    
    setIsAddingStep(true);
    setError(null);
    
    try {
      const stepName = newStepName.trim() || newStepType;
      
      const response = await window.qv.request<WorkflowDetailResult>('add_step_to_workflow', {
        project_root: projectRoot,
        workflow: workflowForSteps.slug,
        step_type: newStepType,
        step_name: stepName,
      });
      
      if (response.ok && response.data) {
        setShowAddStep(false);
        setNewStepType('');
        setNewStepName('');
        // CRITICAL: Wait for workflow detail to refresh before allowing step selection.
        // This ensures the new step is available in the workflow.steps list before
        // the user can click it, preventing "Step not found" errors from race conditions.
        // The onWorkflowUpdated callback will trigger a refetch of workflow detail.
        // We also update the local workflow prop optimistically with the returned data
        // to ensure the new step appears immediately in the UI.
        await onWorkflowUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to add step');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsAddingStep(false);
    }
  }, [workflow, projectRoot, newStepType, newStepName, onWorkflowUpdated]);
  
  // Handle importing QE input as step
  const handleImportStep = useCallback(async () => {
    if (!window.qv || !workflowForSteps) return;
    
    // Use window.qv.openFile to pick file
    const inputFile = await window.qv.openFile({
      title: 'Import QE Input File',
      filters: [
        { name: 'QE Input Files', extensions: ['in'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    
    if (!inputFile) {
      return; // User cancelled
    }
    
    setIsImportingStep(true);
    setError(null);
    
    try {
      const response = await window.qv.request<WorkflowDetailResult>('import_step_from_qe_input', {
        project_root: projectRoot,
        workflow: workflowForSteps.slug,
        input_file: inputFile,
      });
      
      if (response.ok) {
        onWorkflowUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to import step');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsImportingStep(false);
    }
  }, [workflow, projectRoot, onWorkflowUpdated]);
  
  // Drag-and-drop state
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  
  // Handle step reorder - move step up
  const handleMoveUp = useCallback((index: number) => {
    if (index === 0) return;
    setStepOrder(prev => {
      const newOrder = [...prev];
      [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
      return newOrder;
    });
  }, []);
  
  // Handle step reorder - move step down
  const handleMoveDown = useCallback((index: number, total: number) => {
    if (index >= total - 1) return;
    setStepOrder(prev => {
      const newOrder = [...prev];
      [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
      return newOrder;
    });
  }, []);
  
  // Drag-and-drop handlers
  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index.toString());
    // Make the dragged element semi-transparent
    const target = e.target as HTMLElement;
    target.style.opacity = '0.5';
  }, []);
  
  const handleDragEnd = useCallback((e: React.DragEvent) => {
    setDraggedIndex(null);
    setDragOverIndex(null);
    const target = e.target as HTMLElement;
    target.style.opacity = '1';
  }, []);
  
  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  }, []);
  
  const handleDragLeave = useCallback(() => {
    setDragOverIndex(null);
  }, []);
  
  const handleDrop = useCallback((e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    const dragIndex = draggedIndex;
    
    if (dragIndex === null || dragIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    
    setStepOrder(prev => {
      const newOrder = [...prev];
      const [removed] = newOrder.splice(dragIndex, 1);
      newOrder.splice(dropIndex, 0, removed);
      return newOrder;
    });
    
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, [draggedIndex]);
  
  // Start reorder mode
  const handleStartReorder = useCallback(() => {
    if (!workflow) return;
    setStepOrder(workflow.steps.map(s => s.id));
    setIsReordering(true);
    setError(null);
  }, [workflow]);
  
  // Cancel reorder
  const handleCancelReorder = useCallback(() => {
    setIsReordering(false);
    setStepOrder([]);
  }, []);
  
  // Save reorder
  const handleSaveReorder = useCallback(async () => {
    if (!window.qv || !workflowForSteps) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      // new_order must be array of step ULIDs (from step.id) in the desired order
      const response = await window.qv.request<WorkflowDetailResult>('reorder_workflow_steps', {
        project_root: projectRoot,
        workflow: workflowForSteps.slug, // workflow selector: slug
        new_order: stepOrder, // array of step ULIDs (from step.id)
      });
      
      if (response.ok) {
        setIsReordering(false);
        setStepOrder([]);
        onWorkflowUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to reorder steps');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [workflow, projectRoot, stepOrder, onWorkflowUpdated]);
  
  // Handle structure change
  const handleStructureChange = useCallback(async (newStructure: string) => {
    if (!window.qv || !workflowForSteps) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await window.qv.request<WorkflowDetailResult>('change_workflow_structure', {
        project_root: projectRoot,
        workflow: workflowForSteps.slug,
        new_structure: newStructure,
        update_steps: true,
      });
      
      if (response.ok) {
        onWorkflowUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to change structure');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [workflowForSteps, projectRoot, onWorkflowUpdated]);
  
  if (!workflowForSteps) {
    // Show loading state if we have summary but detail is still loading
    if (workflowSummary && !workflowDetail) {
      return (
        <div className="workflow-detail-panel" data-testid="qv-workflow-detail">
          <div className="panel-header">
            <h2 className="panel-title">Loading workflow details...</h2>
          </div>
        </div>
      );
    }
    return null;
  }
  
  // CRITICAL: Use workflowDetail.steps if available (canonical from workflow.yaml),
  // otherwise fall back to workflowSummary.steps (may have wrong order, but better than nothing)
  // The steps array from get_workflow_detail is the canonical source of step order and IDs.
  // Each step.id is a ULID (26 chars) that must be used as the step selector for RPC calls.
  const displaySteps = workflowDetail?.steps ?? workflowSummary?.steps ?? [];
  
  // INSTRUMENTATION: Log steps to verify order matches workflow.yaml
  console.log('[WorkflowDetailPanel] displaySteps', {
    workflowSlug: workflowForSteps.slug,
    hasDetail: !!workflowDetail,
    hasSummary: !!workflowSummary,
    stepCount: displaySteps.length,
    steps: displaySteps.map((s, i) => ({
      index: i,
      id: s.id,
      type: s.type,
      idLength: s.id?.length ?? 0,
    })),
  });
  
  // Early return if no workflow data
  if (!workflow) {
    return (
      <div className="workflow-detail-panel">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Workflow Selected</h3>
          <p>Select a workflow to view its details.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="workflow-detail-panel" data-testid="qv-workflow-detail">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📊</span>
          {workflow.name}
        </h2>
        <div className="panel-header-actions">
          {onRunWorkflow && (
            <button 
              className="panel-header-btn panel-header-btn--primary"
              onClick={() => onRunWorkflow(workflow)}
              disabled={isReordering || isSaving}
              title="Run all steps in this workflow"
              data-testid="qv-btn-run-workflow"
            >
              ▶️ Run Workflow
            </button>
          )}
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
        
        <div className="detail-section">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Structure</span>
              {structures && structures.length > 0 ? (
                <select
                  className="structure-selector"
                  value={
                    // Match workflow.structure (name) to structure slug for dropdown value
                    // Backend returns structure name, but dropdown uses slug as value
                    workflow.structure 
                      ? (structures.find(s => s.name === workflow.structure)?.slug || '')
                      : ''
                  }
                  onChange={(e) => handleStructureChange(e.target.value)}
                  disabled={isSaving}
                >
                  <option value="">-- None --</option>
                  {structures.map(s => (
                    <option key={s.id} value={s.slug}>{s.name} ({s.formula})</option>
                  ))}
                </select>
              ) : (
                <code className="detail-value">{workflow.structure || 'None'}</code>
              )}
            </div>
            <div className="detail-item">
              <span className="detail-label">Mode</span>
              <span className={`detail-value mode-badge mode-badge--${workflow.mode}`}>
                {workflow.mode}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Steps</span>
              <span className="detail-value">{workflow.n_steps}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">ID</span>
              <code className="detail-value detail-value--id">{workflow.id}</code>
            </div>
          </div>
        </div>
        
        <div className="detail-section">
          <div className="section-header-row">
            <h3>Calculation Steps</h3>
            <div className="section-actions">
              {!isReordering ? (
                <>
                  <button 
                    className="section-action-btn section-action-btn--add"
                    onClick={handleShowAddStep}
                    title="Add a new step to this workflow"
                    data-testid="qv-add-step-btn"
                  >
                    ➕ Add Step
                  </button>
                  <button 
                    className="section-action-btn"
                    onClick={handleImportStep}
                    disabled={isImportingStep}
                    title="Import QE input file as step (preserves original parameters)"
                    data-testid="qv-import-step-btn"
                  >
                    {isImportingStep ? 'Importing...' : '📥 Import QE Input'}
                  </button>
                  <button 
                    className="section-action-btn"
                    onClick={handleStartReorder}
                    disabled={workflow.n_steps < 2}
                    title="Reorder steps"
                  >
                    ↕️ Reorder
                  </button>
                </>
              ) : (
                <>
                  <button 
                    className="section-action-btn section-action-btn--secondary"
                    onClick={handleCancelReorder}
                    disabled={isSaving}
                  >
                    Cancel
                  </button>
                  <button 
                    className="section-action-btn section-action-btn--primary"
                    onClick={handleSaveReorder}
                    disabled={isSaving}
                  >
                    {isSaving ? 'Saving...' : 'Save Order'}
                  </button>
                </>
              )}
            </div>
          </div>
          
          {/* Add Step Form - positioned right after the Add Step button for better UX */}
          {showAddStep && (
            <div className="add-step-form" data-testid="qv-add-step-form">
              <div className="add-step-header">
                <h4>Add New Step</h4>
                <button 
                  className="add-step-close"
                  onClick={() => setShowAddStep(false)}
                  title="Cancel adding step"
                >×</button>
              </div>
              <div className="add-step-content">
                <div className="form-group">
                  <label htmlFor="step-type">Step Type</label>
                  <select
                    id="step-type"
                    value={newStepType}
                    onChange={(e) => setNewStepType(e.target.value)}
                    autoFocus
                  >
                    <option value="">-- Select Type --</option>
                    <option value="scf">SCF (pw.x)</option>
                    <option value="nscf">NSCF (pw.x)</option>
                    <option value="relax">Relax (pw.x)</option>
                    <option value="vc-relax">VC-Relax (pw.x)</option>
                    <option value="bands_pw">Bands PW (pw.x)</option>
                    <option value="bands">Bands PP (bands.x)</option>
                    <option value="dos">DOS (dos.x)</option>
                    <option value="projwfc">PDOS (projwfc.x)</option>
                    <option value="ph">Phonon (ph.x)</option>
                    <option value="pp">Post-Process (pp.x)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="step-name">Step Name (optional)</label>
                  <input
                    id="step-name"
                    type="text"
                    placeholder={newStepType || 'step name'}
                    value={newStepName}
                    onChange={(e) => setNewStepName(e.target.value)}
                  />
                </div>
                <div className="add-step-actions">
                  <button
                    className="add-step-btn add-step-btn--cancel"
                    onClick={() => setShowAddStep(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="add-step-btn add-step-btn--confirm"
                    onClick={handleAddStep}
                    disabled={!newStepType || isAddingStep}
                    data-testid="qv-confirm-add-step"
                  >
                    {isAddingStep ? 'Adding...' : 'Add Step'}
                  </button>
                </div>
              </div>
            </div>
          )}
          
          <div className="steps-list" data-testid="qv-steps-list">
            {displaySteps.map((step, idx) => (
              <div 
                key={step.id} 
                className={`step-item-container ${
                  isReordering ? 'step-item-container--reordering' : ''
                } ${
                  draggedIndex === idx ? 'step-item-container--dragging' : ''
                } ${
                  dragOverIndex === idx ? 'step-item-container--drag-over' : ''
                }`}
                draggable={isReordering && !isSaving}
                onDragStart={isReordering ? (e) => handleDragStart(e, idx) : undefined}
                onDragEnd={isReordering ? handleDragEnd : undefined}
                onDragOver={isReordering ? (e) => handleDragOver(e, idx) : undefined}
                onDragLeave={isReordering ? handleDragLeave : undefined}
                onDrop={isReordering ? (e) => handleDrop(e, idx) : undefined}
                data-testid={`qv-step-row-${step.id}`}
                data-step-id={step.id}
              >
                {isReordering && (
                  <div className="step-reorder-controls">
                    <span className="drag-handle" title="Drag to reorder">⋮⋮</span>
                    <button
                      className="reorder-btn"
                      onClick={() => handleMoveUp(idx)}
                      disabled={idx === 0 || isSaving}
                      title="Move up"
                    >
                      ↑
                    </button>
                    <button
                      className="reorder-btn"
                      onClick={() => handleMoveDown(idx, displaySteps.length)}
                      disabled={idx >= displaySteps.length - 1 || isSaving}
                      title="Move down"
                    >
                      ↓
                    </button>
                  </div>
                )}
                <button 
                  className="step-item"
                  onClick={() => {
                    if (!isReordering) {
                      // CRITICAL: step.id is ULID from backend (get_workflow_detail returns step.id from workflow.yaml)
                      // This is the ONLY correct selector for get_step_detail RPC
                      // We MUST use step.id directly, NOT derived from index or any other source
                      console.log('[WorkflowDetailPanel] step clicked', {
                        workflowSlug: workflowForSteps.slug,
                        stepIndex: idx,
                        stepId: step.id,
                        stepType: step.type,
                      });
                      // CRITICAL: Pass step.id (ULID) directly to onSelectStep
                      // This will be stored as selectedStepId in App.tsx and passed to StepDetailPanel
                      onSelectStep?.(step.id);
                    }
                  }}
                  disabled={isReordering}
                  data-testid={`qv-step-button-${step.id}`}
                >
                  <span className="step-number">{idx + 1}</span>
                  <div className="step-info">
                    {/* step.id is ULID (26 chars) from backend - used as step selector */}
                    <span className="step-id">{step.id}</span>
                    <span className="step-type-badge">{step.type}</span>
                  </div>
                  <code className="step-file">{step.step_file}</code>
                </button>
                {!isReordering && onDeleteStep && (
                  <button
                    className="step-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteStep(step.id, step.type);
                    }}
                    disabled={isDeletingStep}
                    title={`Delete step "${step.type}"`}
                    data-testid={`qv-delete-step-${step.id}`}
                  >
                    🗑️
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <div className="detail-section">
          <h3>File Location</h3>
          <div className="file-location">
            <code className="file-location__path" title={workflow.absolute_path}>
              {workflow.absolute_path}
            </code>
            <button 
              className="file-location__reveal-btn"
              onClick={() => window.qv?.revealPath?.(workflow.absolute_path)}
              title="Reveal in Finder"
            >
              📂 Reveal
            </button>
          </div>
        </div>
        
        <div className="detail-actions">
          {onGoToJobs && (
            <button 
              className="action-button action-button--secondary"
              onClick={onGoToJobs}
            >
              📋 View Jobs
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

