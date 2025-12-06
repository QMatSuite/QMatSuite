/**
 * Sidebar - Navigation and controls for QuantumVITAS
 * 
 * Simplified design:
 * - Project path input with Browse button
 * - Load Project / Create Project actions
 * - View tabs for navigation
 * - Connection status
 * - Running jobs indicator
 */

import type { QVClient } from '../../hooks/useQVClient';
import type { DaemonStatus, JobCounts } from '../../types/qv';
import './Sidebar.css';

export type ViewType = 'summary' | 'structures' | 'workflows' | 'jobs' | 'analysis' | 'settings' | 'debug';

interface SidebarProps {
  qv: QVClient;
  projectRoot: string;
  projectLoaded: boolean;
  projectError: string | null;
  onProjectRootChange: (path: string) => void;
  onLoadProject: () => void;
  onCreateProject: () => void;
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  daemonStatus: DaemonStatus | null;
  jobCounts: JobCounts | null;
}

export function Sidebar({ 
  qv, 
  projectRoot,
  projectLoaded,
  projectError,
  onProjectRootChange,
  onLoadProject,
  onCreateProject,
  currentView,
  onViewChange,
  daemonStatus,
  jobCounts,
}: SidebarProps) {
  const isLoading = qv.state.isLoading;
  const isConnected = qv.state.isConnected;
  
  const runningCount = jobCounts?.running || 0;
  const pendingCount = jobCounts?.pending || 0;
  const activeJobsCount = runningCount + pendingCount;
  
  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar__header">
        <h1 className="sidebar__title">
          <span className="sidebar__logo">⚛</span>
          QuantumVITAS
        </h1>
        <div className={`sidebar__status ${isConnected ? 'connected' : 'disconnected'}`}>
          <span className="sidebar__status-dot" />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
        {daemonStatus?.startupError && (
          <div className="sidebar__status-error">
            Daemon Error
          </div>
        )}
      </div>
      
      {/* Project Path Input */}
      <div className="sidebar__section">
        <label className="sidebar__label">
          Project Root
          <div className="sidebar__input-group">
            <input
              type="text"
              className={`sidebar__input sidebar__input--with-button ${projectError ? 'sidebar__input--error' : ''}`}
              value={projectRoot}
              onChange={(e) => onProjectRootChange(e.target.value)}
              placeholder="/path/to/project"
              disabled={isLoading}
            />
            <button
              className="sidebar__browse-button"
              onClick={async () => {
                if (window.qv?.openDirectory) {
                  const path = await window.qv.openDirectory();
                  if (path) {
                    onProjectRootChange(path);
                  }
                }
              }}
              disabled={isLoading}
              title="Browse for project directory"
            >
              📂
            </button>
          </div>
          {projectError && (
            <span className="sidebar__input-error">{projectError}</span>
          )}
        </label>
      </div>
      
      {/* Project Actions */}
      <div className="sidebar__section">
        <div className="sidebar__actions">
          <button
            className="sidebar__button sidebar__button--primary"
            onClick={onLoadProject}
            disabled={isLoading || !projectRoot}
          >
            📁 Load Project
          </button>
          
          <button
            className="sidebar__button"
            onClick={onCreateProject}
            disabled={isLoading}
          >
            ✨ Create Project
          </button>
        </div>
      </div>
      
      {/* View Tabs */}
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">Navigation</h2>
        <div className="sidebar__tabs">
          <button
            className={`sidebar__tab ${currentView === 'summary' ? 'active' : ''}`}
            onClick={() => onViewChange('summary')}
            title="Project overview and quick actions"
          >
            <span className="sidebar__tab-icon">📋</span>
            Summary
          </button>
          <button
            className={`sidebar__tab ${currentView === 'structures' ? 'active' : ''}`}
            onClick={() => onViewChange('structures')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'View and manage crystal structures' : 'Load a project first'}
          >
            <span className="sidebar__tab-icon">🔬</span>
            Structures
          </button>
          <button
            className={`sidebar__tab ${currentView === 'workflows' ? 'active' : ''}`}
            onClick={() => onViewChange('workflows')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'Configure and run QE workflows' : 'Load a project first'}
          >
            <span className="sidebar__tab-icon">📊</span>
            Workflows
          </button>
          <button
            className={`sidebar__tab ${currentView === 'jobs' ? 'active' : ''}`}
            onClick={() => onViewChange('jobs')}
            title={activeJobsCount > 0 ? `${runningCount} running, ${pendingCount} pending` : 'View job queue and logs'}
          >
            <span className="sidebar__tab-icon">⚡</span>
            Jobs
            {activeJobsCount > 0 && (
              <span className={`sidebar__tab-badge ${runningCount > 0 ? 'sidebar__tab-badge--running' : ''}`}>
                {activeJobsCount}
              </span>
            )}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'analysis' ? 'active' : ''}`}
            onClick={() => onViewChange('analysis')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'Analyze SCF convergence, DOS, and band structures' : 'Load a project first'}
          >
            <span className="sidebar__tab-icon">📈</span>
            Analysis
          </button>
          <button
            className={`sidebar__tab ${currentView === 'settings' ? 'active' : ''}`}
            onClick={() => onViewChange('settings')}
            title="Configure QE paths and app settings"
          >
            <span className="sidebar__tab-icon">⚙️</span>
            Settings
          </button>
          <button
            className={`sidebar__tab ${currentView === 'debug' ? 'active' : ''}`}
            onClick={() => onViewChange('debug')}
            title="View daemon logs and debug info"
          >
            <span className="sidebar__tab-icon">🔧</span>
            Debug
          </button>
        </div>
      </div>
      
      {/* Footer spacer */}
      <div className="sidebar__spacer" />
      
      {/* Version info */}
      <div className="sidebar__footer">
        <span className="sidebar__version">QuantumVITAS v2.0.0</span>
      </div>
    </div>
  );
}
