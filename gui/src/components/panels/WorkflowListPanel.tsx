/**
 * WorkflowListPanel - Displays a list of workflows in a project
 */

import type { WorkflowInfo } from '../../types/qv';
import './WorkflowListPanel.css';

interface WorkflowListPanelProps {
  workflows: WorkflowInfo[] | null;
  isLoading?: boolean;
  selectedId?: string | null;
  onSelect?: (workflow: WorkflowInfo) => void;
  onRename?: (workflow: WorkflowInfo) => void;
  onDelete?: (workflow: WorkflowInfo) => void;
}

export function WorkflowListPanel({ 
  workflows, 
  isLoading, 
  selectedId,
  onSelect,
  onRename,
  onDelete,
}: WorkflowListPanelProps) {
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
    <div className="workflow-list-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📊</span>
          Workflows
        </h2>
        <span className="panel-count">{workflows.length} total</span>
      </div>
      
      <div className="workflow-list">
        {workflows.map((workflow) => (
          <div
            key={workflow.id}
            className={`workflow-item ${selectedId === workflow.id ? 'workflow-item--selected' : ''}`}
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

interface WorkflowDetailPanelProps {
  workflow: WorkflowInfo | null;
  projectRoot: string;
  structures?: StructureInfo[];
  onClose?: () => void;
  onRunWorkflow?: (workflow: WorkflowInfo) => void;
  onSelectStep?: (stepId: string) => void;
  onGoToJobs?: () => void;
  onWorkflowUpdated?: () => void;
}

export function WorkflowDetailPanel({ 
  workflow, 
  projectRoot,
  structures,
  onClose,
  onRunWorkflow,
  onSelectStep,
  onGoToJobs,
  onWorkflowUpdated,
}: WorkflowDetailPanelProps) {
  const [isReordering, setIsReordering] = useState(false);
  const [stepOrder, setStepOrder] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
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
    if (!window.qv || !workflow) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await window.qv.request<WorkflowDetailResult>('reorder_workflow_steps', {
        project_root: projectRoot,
        workflow: workflow.slug,
        new_order: stepOrder,
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
    if (!window.qv || !workflow) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await window.qv.request<WorkflowDetailResult>('change_workflow_structure', {
        project_root: projectRoot,
        workflow: workflow.slug,
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
  }, [workflow, projectRoot, onWorkflowUpdated]);
  
  if (!workflow) {
    return null;
  }
  
  // Get ordered steps for display (use stepOrder if reordering, else workflow.steps)
  const displaySteps = isReordering
    ? stepOrder.map(id => workflow.steps.find(s => s.id === id)!).filter(Boolean)
    : workflow.steps;
  
  return (
    <div className="workflow-detail-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📊</span>
          {workflow.name}
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
        
        <div className="detail-section">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Structure</span>
              {structures && structures.length > 0 ? (
                <select
                  className="structure-selector"
                  value={workflow.structure || ''}
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
            {!isReordering ? (
              <button 
                className="section-action-btn"
                onClick={handleStartReorder}
                disabled={workflow.n_steps < 2}
              >
                ↕️ Reorder
              </button>
            ) : (
              <div className="section-actions">
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
              </div>
            )}
          </div>
          
          <div className="steps-list">
            {displaySteps.map((step, idx) => (
              <div key={step.id} className="step-item-container">
                {isReordering && (
                  <div className="step-reorder-controls">
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
                  onClick={() => !isReordering && onSelectStep?.(step.id)}
                  disabled={isReordering}
                >
                  <span className="step-number">{idx + 1}</span>
                  <div className="step-info">
                    <span className="step-id">{step.id}</span>
                    <span className="step-type-badge">{step.type}</span>
                  </div>
                  <code className="step-file">{step.step_file}</code>
                </button>
              </div>
            ))}
          </div>
        </div>
        
        <div className="detail-section">
          <h3>File Location</h3>
          <code className="detail-path">{workflow.absolute_path}</code>
        </div>
        
        <div className="detail-actions">
          {onRunWorkflow && (
            <button 
              className="action-button action-button--primary"
              onClick={() => onRunWorkflow(workflow)}
              disabled={isReordering || isSaving}
            >
              ▶️ Run Workflow
            </button>
          )}
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

