/**
 * ProjectSummaryPanel - Displays project overview in a structured format
 */

import type { ProjectSummary } from '../../types/qv';
import { DemoGalleryPanel } from './DemoGalleryPanel';
import './ProjectSummaryPanel.css';

export type HomeMode = 'welcome' | 'demo-gallery';

interface ProjectSummaryPanelProps {
  summary: ProjectSummary | null;
  isLoading?: boolean;
  error?: string | null;
  recentProjects?: string[];
  homeMode?: HomeMode;
  onHomeModeChange?: (mode: HomeMode) => void;
  onBrowseAndLoad?: () => void;
  onCreateProject?: () => void;
  onOpenDemoGallery?: () => void;
  onOpenRecentProject?: (path: string) => void;
  onRemoveRecentProject?: (path: string) => void;
  onNavigateToStructure?: (name: string) => void;
  onNavigateToWorkflow?: (name: string) => void;
  onCloseProject?: () => void;
  onProjectCreated?: (projectRoot: string, recommendedAnalysis?: string | null) => void;
}

export function ProjectSummaryPanel({ 
  summary, 
  isLoading,
  error,
  recentProjects,
  homeMode = 'welcome',
  onHomeModeChange,
  onBrowseAndLoad,
  onCreateProject,
  onOpenDemoGallery,
  onOpenRecentProject,
  onRemoveRecentProject,
  onNavigateToStructure,
  onNavigateToWorkflow,
  onCloseProject,
  onProjectCreated,
}: ProjectSummaryPanelProps) {
  // If we're in demo gallery mode, show gallery (regardless of project state)
  if (homeMode === 'demo-gallery') {
    return (
      <DemoGalleryPanel
        onBack={() => onHomeModeChange?.('welcome')}
        onCreateProject={(projectRoot, recommendedAnalysis) => {
          onHomeModeChange?.('welcome');
          onProjectCreated?.(projectRoot, recommendedAnalysis);
        }}
      />
    );
  }
  if (isLoading) {
    return (
      <div className="project-summary-panel project-summary-panel--loading">
        <div className="loading-spinner" />
        <p>Loading project...</p>
      </div>
    );
  }
  
  if (error) {
    // Check if this is a legacy project error (contains migration command)
    const isLegacyError = error.includes('legacy workflow format') || error.includes('migrate it using');
    
    return (
      <div className="project-summary-panel project-summary-panel--error">
        <div className="error-card">
          <span className="error-icon">⚠️</span>
          <h3>{isLegacyError ? 'Legacy Project Detected' : 'Failed to Load Project'}</h3>
          <p className="error-message" style={{ whiteSpace: 'pre-line' }}>{error}</p>
          {isLegacyError && (
            <div className="error-hint">
              <p>This project uses an older format that needs to be migrated before it can be used.</p>
            </div>
          )}
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
      <div className="project-summary-panel project-summary-panel--empty" data-testid="qv-welcome">
        <div className="welcome-card">
          <div className="welcome-icon">⚛️</div>
          <h2 className="welcome-title" data-testid="qv-welcome-title">Welcome to QuantumVITAS</h2>
          <p className="welcome-subtitle">
            Manage Quantum ESPRESSO workflows with ease
          </p>
          
          <div className="welcome-actions">
            {onBrowseAndLoad && (
              <button 
                className="welcome-button welcome-button--primary" 
                onClick={onBrowseAndLoad}
                data-testid="qv-welcome-btn-open-project"
              >
                <span className="welcome-button__icon">📂</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Open Project</span>
                  <span className="welcome-button__desc">Browse and load an existing project</span>
                </span>
              </button>
            )}
            {onCreateProject && (
              <button 
                className="welcome-button" 
                onClick={onCreateProject}
                data-testid="qv-welcome-btn-create-new-project"
              >
                <span className="welcome-button__icon">✨</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Create New Project</span>
                  <span className="welcome-button__desc">Start a new QE calculation project</span>
                </span>
              </button>
            )}
            {onOpenDemoGallery && (
              <button 
                className="welcome-button welcome-button--demo" 
                onClick={onOpenDemoGallery}
                data-testid="qv-welcome-btn-demo-gallery"
              >
                <span className="welcome-button__icon">🎨</span>
                <span className="welcome-button__content">
                  <span className="welcome-button__title">Browse Demo Gallery</span>
                  <span className="welcome-button__desc">Explore ready-to-run demo projects</span>
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
            <span>Use the sidebar buttons to open, create, or explore demo projects</span>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="project-summary-panel" data-testid="qv-home-project">
      <div className="panel-header">
        <h2 className="panel-title" data-testid="qv-project-name">
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
              data-testid="qv-btn-close-project"
            >
              ✕ Close
            </button>
          )}
        </div>
      </div>
      
      {(() => {
        // Derive workspace from project path (parent directory)
        const pathParts = summary.path.split(/[/\\]/);
        pathParts.pop(); // Remove project name
        const workspace = pathParts.join('/') || '/';
        return (
          <div className="project-summary-panel__context" data-testid="qv-project-context">
            <span className="context-label">Workspace:</span>
            <code className="context-value">{workspace}</code>
            <span className="context-separator">·</span>
            <span className="context-label">Current project:</span>
            <code className="context-value">{summary.name}</code>
          </div>
        );
      })()}
      
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
            <div className="detail-path-container">
              <code className="detail-value detail-value--path" title={summary.path} data-testid="qv-project-path">{summary.path}</code>
              <button 
                className="reveal-btn"
                onClick={() => window.qv?.revealPath?.(summary.path)}
                title="Reveal in Finder"
                data-testid="qv-btn-project-reveal"
              >
                📂 Reveal
              </button>
            </div>
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
