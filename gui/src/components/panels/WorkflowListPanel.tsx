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
}

export function WorkflowListPanel({ 
  workflows, 
  isLoading, 
  selectedId,
  onSelect 
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
          <button
            key={workflow.id}
            className={`workflow-item ${selectedId === workflow.id ? 'workflow-item--selected' : ''}`}
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
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Workflow Detail View
// =============================================================================

interface WorkflowDetailPanelProps {
  workflow: WorkflowInfo | null;
  onClose?: () => void;
  onRunWorkflow?: (workflow: WorkflowInfo) => void;
  onSelectStep?: (stepId: string) => void;
}

export function WorkflowDetailPanel({ 
  workflow, 
  onClose,
  onRunWorkflow,
  onSelectStep,
}: WorkflowDetailPanelProps) {
  if (!workflow) {
    return null;
  }
  
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
        <div className="detail-section">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Structure</span>
              <code className="detail-value">{workflow.structure || 'None'}</code>
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
          <h3>Calculation Steps</h3>
          <div className="steps-list">
            {workflow.steps.map((step, idx) => (
              <button 
                key={step.id} 
                className="step-item"
                onClick={() => onSelectStep?.(step.id)}
              >
                <span className="step-number">{idx + 1}</span>
                <div className="step-info">
                  <span className="step-id">{step.id}</span>
                  <span className="step-type-badge">{step.type}</span>
                </div>
                <code className="step-file">{step.step_file}</code>
              </button>
            ))}
          </div>
        </div>
        
        <div className="detail-section">
          <h3>File Location</h3>
          <code className="detail-path">{workflow.absolute_path}</code>
        </div>
        
        {onRunWorkflow && (
          <div className="detail-actions">
            <button 
              className="action-button action-button--primary"
              onClick={() => onRunWorkflow(workflow)}
            >
              ▶️ Run Workflow
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

