/**
 * Sidebar - Navigation and controls for QuantumVITAS
 * 
 * Simplified design:
 * - Project path input with Browse button
 * - Load Project / Create Project actions
 * - View tabs for navigation
 * - Connection status
 * - Running jobs indicator
 * - Collapsible to show only icons
 */

import { useState, useCallback, useEffect } from 'react';
import type { QVClient } from '../../hooks/useQVClient';
import type { DaemonStatus, JobCounts } from '../../types/qv';
import './Sidebar.css';

export type ViewType = 'home' | 'structures' | 'workflows' | 'jobs' | 'analysis' | 'settings' | 'debug';

interface SidebarProps {
  qv: QVClient;
  projectRoot: string;
  projectLoaded: boolean;
  projectError: string | null;
  onProjectRootChange: (path: string) => void;
  onLoadProject: () => void;
  onBrowseAndLoad: () => void;
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
  onBrowseAndLoad,
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
  
  // Collapsed state (persisted in localStorage)
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem('qv-sidebar-collapsed') === 'true';
    } catch {
      return false;
    }
  });
  
  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem('qv-sidebar-collapsed', String(isCollapsed));
  }, [isCollapsed]);
  
  const handleToggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev);
  }, []);
  
  return (
    <div className={`sidebar ${isCollapsed ? 'sidebar--collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar__header">
        <h1 className="sidebar__title">
          <span className="sidebar__logo">⚛</span>
          {!isCollapsed && <span className="sidebar__title-text">QuantumVITAS</span>}
        </h1>
        {!isCollapsed && (
          <div className={`sidebar__status ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="sidebar__status-dot" />
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
        )}
        {!isCollapsed && daemonStatus?.startupError && (
          <div className="sidebar__status-error">
            Daemon Error
          </div>
        )}
      </div>
      
      {/* Project Path Input - hidden when collapsed */}
      {!isCollapsed && (
        <div className="sidebar__section">
          <label className="sidebar__label">
            Project Root
            <div className="sidebar__input-group">
              <input
                type="text"
                className={`sidebar__input sidebar__input--with-button ${projectError ? 'sidebar__input--error' : ''}`}
                value={projectRoot}
                onChange={(e) => onProjectRootChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && projectRoot.trim()) {
                    onLoadProject();
                  }
                }}
                placeholder="/path/to/project (press Enter to load)"
                disabled={isLoading}
              />
              <button
                className="sidebar__browse-button"
                onClick={onBrowseAndLoad}
                disabled={isLoading}
                title="Browse and load project"
              >
                📂
              </button>
            </div>
            {projectError && (
              <span className="sidebar__input-error">{projectError}</span>
            )}
          </label>
        </div>
      )}
      
      {/* Project Actions - icon-only when collapsed */}
      <div className="sidebar__section">
        <div className="sidebar__actions">
          {isCollapsed ? (
            <>
              <button
                className="sidebar__icon-button"
                onClick={onBrowseAndLoad}
                disabled={isLoading}
                title="Open Project"
              >
                📂
              </button>
              <button
                className="sidebar__icon-button"
                onClick={onCreateProject}
                disabled={isLoading}
                title="Create Project"
              >
                ✨
              </button>
            </>
          ) : (
            <button
              className="sidebar__button"
              onClick={onCreateProject}
              disabled={isLoading}
            >
              ✨ Create Project
            </button>
          )}
        </div>
      </div>
      
      {/* View Tabs */}
      <div className="sidebar__section">
        {!isCollapsed && <h2 className="sidebar__section-title">Navigation</h2>}
        <div className="sidebar__tabs">
          <button
            className={`sidebar__tab ${currentView === 'home' ? 'active' : ''}`}
            onClick={() => onViewChange('home')}
            title="Home - project overview and quick actions"
          >
            <span className="sidebar__tab-icon">🏠</span>
            {!isCollapsed && 'Home'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'structures' ? 'active' : ''}`}
            onClick={() => onViewChange('structures')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'View and manage crystal structures' : 'Load a project first'}
          >
            <span className="sidebar__tab-icon">🔬</span>
            {!isCollapsed && 'Structures'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'workflows' ? 'active' : ''}`}
            onClick={() => onViewChange('workflows')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'Configure and run QE workflows' : 'Load a project first'}
          >
            <span className="sidebar__tab-icon">📊</span>
            {!isCollapsed && 'Workflows'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'jobs' ? 'active' : ''}`}
            onClick={() => onViewChange('jobs')}
            title={activeJobsCount > 0 ? `${runningCount} running, ${pendingCount} pending` : 'View job queue and logs'}
          >
            <span className="sidebar__tab-icon">⚡</span>
            {!isCollapsed && 'Jobs'}
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
            {!isCollapsed && 'Analysis'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'settings' ? 'active' : ''}`}
            onClick={() => onViewChange('settings')}
            title="Configure QE paths and app settings"
          >
            <span className="sidebar__tab-icon">⚙️</span>
            {!isCollapsed && 'Settings'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'debug' ? 'active' : ''}`}
            onClick={() => onViewChange('debug')}
            title="View daemon logs and debug info"
          >
            <span className="sidebar__tab-icon">🔧</span>
            {!isCollapsed && 'Debug'}
          </button>
        </div>
      </div>
      
      {/* Footer spacer */}
      <div className="sidebar__spacer" />
      
      {/* Footer with collapse toggle */}
      <div className="sidebar__footer">
        {!isCollapsed && <span className="sidebar__version">QuantumVITAS v2.0.0</span>}
        <button
          className="sidebar__collapse-btn"
          onClick={handleToggleCollapse}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? '»' : '«'}
        </button>
      </div>
    </div>
  );
}
