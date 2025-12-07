/**
 * ProjectSummaryPanel - Displays project overview in a structured format
 */

import type { ProjectSummary } from '../../types/qv';
import './ProjectSummaryPanel.css';

interface ProjectSummaryPanelProps {
  summary: ProjectSummary | null;
  isLoading?: boolean;
  error?: string | null;
  recentProjects?: string[];
  onBrowseAndLoad?: () => void;
  onCreateProject?: () => void;
  onCreateDemoProject?: () => void;
  onOpenRecentProject?: (path: string) => void;
  onRemoveRecentProject?: (path: string) => void;
  onNavigateToStructure?: (name: string) => void;
  onNavigateToWorkflow?: (name: string) => void;
  onCloseProject?: () => void;
}

export function ProjectSummaryPanel({ 
  summary, 
  isLoading,
  error,
  recentProjects,
  onBrowseAndLoad,
  onCreateProject,
  onCreateDemoProject,
  onOpenRecentProject,
  onRemoveRecentProject,
  onNavigateToStructure,
  onNavigateToWorkflow,
  onCloseProject,
}: ProjectSummaryPanelProps) {
  if (isLoading) {
    return (
      <div className="project-summary-panel project-summary-panel--loading">
        <div className="loading-spinner" />
        <p>Loading project...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="project-summary-panel project-summary-panel--error">
        <div className="error-card">
          <span className="error-icon">⚠️</span>
          <h3>Failed to Load Project</h3>
          <p className="error-message">{error}</p>
          <div className="error-actions">
            {onBrowseAndLoad && (
              <button className="action-button" onClick={onBrowseAndLoad}>
                📂 Browse & Load
              </button>
            )}
            {onCreateProject && (
              <button className="action-button action-button--secondary" onClick={onCreateProject}>
                ✨ Create New Project
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }
  
  if (!summary) {
    return (
      <div className="project-summary-panel project-summary-panel--empty">
        <div className="welcome-card">
          <div className="welcome-icon">⚛️</div>
          <h2 className="welcome-title">Welcome to QuantumVITAS</h2>
          <p className="welcome-subtitle">
            Manage Quantum ESPRESSO workflows with ease
          </p>
          
          <div className="welcome-actions">
            {onBrowseAndLoad && (
              <button className="welcome-button welcome-button--primary" onClick={onBrowseAndLoad}>
                <span className="welcome-button__icon">📂</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Open Project</span>
                  <span className="welcome-button__desc">Browse and load an existing project</span>
                </span>
              </button>
            )}
            {onCreateProject && (
              <button className="welcome-button" onClick={onCreateProject}>
                <span className="welcome-button__icon">✨</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Create New Project</span>
                  <span className="welcome-button__desc">Start a new QE calculation project</span>
                </span>
              </button>
            )}
            {onCreateDemoProject && (
              <button className="welcome-button welcome-button--demo" onClick={onCreateDemoProject}>
                <span className="welcome-button__icon">🚀</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Create Demo Project</span>
                  <span className="welcome-button__desc">Start with a ready-to-run Si workflow</span>
                </span>
              </button>
            )}
          </div>
          
          {/* Recent Projects */}
          {recentProjects && recentProjects.length > 0 && (
            <div className="recent-projects">
              <h3 className="recent-projects__title">Recent Projects</h3>
              <div className="recent-projects__list">
                {recentProjects.map((path) => (
                  <div key={path} className="recent-project-item">
                    <button 
                      className="recent-project-item__path"
                      onClick={() => onOpenRecentProject?.(path)}
                      title={path}
                    >
                      <span className="recent-project-item__icon">📁</span>
                      <span className="recent-project-item__name">{getProjectName(path)}</span>
                      <span className="recent-project-item__dir">{getParentDir(path)}</span>
                    </button>
                    {onRemoveRecentProject && (
                      <button 
                        className="recent-project-item__remove"
                        onClick={() => onRemoveRecentProject(path)}
                        title="Remove from recent"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="welcome-hint">
            <span className="hint-icon">💡</span>
            <span>Or enter a project path in the sidebar and click "Load Project"</span>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="project-summary-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📁</span>
          {summary.name}
        </h2>
        <div className="panel-header__actions">
          <span className="panel-badge">{summary.slug}</span>
          {onCloseProject && (
            <button 
              className="close-project-btn"
              onClick={onCloseProject}
              title="Close this project"
            >
              ✕ Close
            </button>
          )}
        </div>
      </div>
      
      <div className="panel-content">
        <div className="summary-grid">
          <div className="summary-card summary-card--clickable">
            <div className="summary-card__value">{summary.n_structures}</div>
            <div className="summary-card__label">Structures</div>
            <div className="summary-card__list">
              {summary.structure_names.length === 0 ? (
                <span className="summary-empty">No structures yet</span>
              ) : (
                <>
                  {summary.structure_names.slice(0, 5).map(name => (
                    <button 
                      key={name} 
                      className="summary-tag summary-tag--clickable"
                      onClick={() => onNavigateToStructure?.(name)}
                      title={`Open structure: ${name}`}
                    >
                      {name}
                    </button>
                  ))}
                  {summary.structure_names.length > 5 && (
                    <span className="summary-tag summary-tag--more">
                      +{summary.structure_names.length - 5} more
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
          
          <div className="summary-card summary-card--clickable">
            <div className="summary-card__value">{summary.n_workflows}</div>
            <div className="summary-card__label">Workflows</div>
            <div className="summary-card__list">
              {summary.workflow_names.length === 0 ? (
                <span className="summary-empty">No workflows yet</span>
              ) : (
                <>
                  {summary.workflow_names.slice(0, 5).map(name => (
                    <button 
                      key={name} 
                      className="summary-tag summary-tag--clickable"
                      onClick={() => onNavigateToWorkflow?.(name)}
                      title={`Open workflow: ${name}`}
                    >
                      {name}
                    </button>
                  ))}
                  {summary.workflow_names.length > 5 && (
                    <span className="summary-tag summary-tag--more">
                      +{summary.workflow_names.length - 5} more
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
        
        <div className="summary-details">
          <div className="detail-row">
            <span className="detail-label">Project ID</span>
            <code className="detail-value">{summary.id}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Path</span>
            <code className="detail-value detail-value--path">{summary.path}</code>
          </div>
        </div>
        
        {/* Quick Actions */}
        <div className="quick-actions">
          <h3 className="quick-actions__title">Quick Actions</h3>
          <div className="quick-actions__grid">
            <button 
              className="quick-action-btn"
              onClick={() => onNavigateToStructure?.('')}
              title="View all structures"
            >
              <span className="quick-action-btn__icon">🔬</span>
              <span>View Structures</span>
            </button>
            <button 
              className="quick-action-btn"
              onClick={() => onNavigateToWorkflow?.('')}
              title="View all workflows"
            >
              <span className="quick-action-btn__icon">📊</span>
              <span>View Workflows</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper to extract project name from path
function getProjectName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

// Helper to get parent directory
function getParentDir(path: string): string {
  const parts = path.split(/[/\\]/);
  parts.pop();
  return parts.slice(-2).join('/') || '/';
}
