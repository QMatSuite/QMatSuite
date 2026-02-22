/**
 * Sidebar - Navigation and controls for QMatSuite
 * 
 * Design:
 * - Read-only project path display with Reveal button
 * - Always-visible project action buttons (Open/Create/Demo)
 * - View tabs for navigation
 * - Connection status
 * - Running jobs indicator
 * - Collapsible to show only icons
 */

import { useState, useCallback, useEffect } from 'react';
import type { QMSClient } from '../../hooks/useQMSClient';
import type { DaemonStatus, JobCounts } from '../../types/qms';
import './Sidebar.css';

export type ViewType = 'home' | 'structures' | 'calculations' | 'jobs' | 'history' | 'resources' | 'settings' | 'dev-volume';

interface SidebarProps {
  qms: QMSClient;
  projectRoot: string;
  projectLoaded: boolean;
  projectError: string | null;
  onBrowseAndLoad: () => void;
  onCreateProject: () => void;
  onOpenDemoGallery: () => void;
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  daemonStatus: DaemonStatus | null;
  jobCounts: JobCounts | null;
}

export function Sidebar({ 
  qms, 
  projectRoot,
  projectLoaded,
  projectError,
  onBrowseAndLoad,
  onCreateProject,
  onOpenDemoGallery,
  currentView,
  onViewChange,
  daemonStatus,
  jobCounts,
}: SidebarProps) {
  const isLoading = qms.state.isLoading;
  const isConnected = qms.state.isConnected;
  
  const runningCount = jobCounts?.running || 0;
  const pendingCount = jobCounts?.pending || 0;
  const activeJobsCount = runningCount + pendingCount;
  
  // Collapsed state (persisted in localStorage)
  // collapsed: narrow icon-only strip (~64px), main content expands to fill remaining width
  // expanded: fixed narrow width (~230px) with icons + labels, Project Root truncated if needed
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem('qms-sidebar-collapsed') === 'true';
    } catch {
      return false;
    }
  });
  
  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem('qms-sidebar-collapsed', String(isCollapsed));
  }, [isCollapsed]);
  
  const handleToggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev);
  }, []);
  
  // Reveal project folder in system file manager
  const handleRevealProject = useCallback(() => {
    if (projectRoot && projectLoaded) {
      window.qms?.revealPath?.(projectRoot);
    }
  }, [projectRoot, projectLoaded]);
  
  // Get display path (truncated for long paths)
  const displayPath = projectRoot 
    ? (projectRoot.length > 35 ? '...' + projectRoot.slice(-32) : projectRoot)
    : 'No project loaded';
  
  return (
    <div className={`sidebar ${isCollapsed ? 'sidebar--collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar__header">
        <h1 className="sidebar__title">
          <span className="sidebar__logo">⚛</span>
          {!isCollapsed && <span className="sidebar__title-text">QMatSuite</span>}
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
      
      {/* Project Path Display - read-only with reveal button */}
      {!isCollapsed && (
        <div className="sidebar__section">
          <label className="sidebar__label">
            Project Root
            <div className="sidebar__path-display">
              <span 
                className={`sidebar__path-text ${!projectLoaded ? 'sidebar__path-text--empty' : ''} ${projectError ? 'sidebar__path-text--error' : ''}`}
                title={projectRoot || 'No project loaded'}
              >
                {displayPath}
              </span>
              <button
                className="sidebar__reveal-button"
                onClick={handleRevealProject}
                disabled={!projectLoaded || !projectRoot}
                title={projectLoaded ? 'Reveal in Finder/Explorer' : 'No project loaded'}
                data-testid="qms-btn-reveal-project"
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
      
      {/* Project Actions - always visible */}
      <div className="sidebar__section">
        {!isCollapsed && <h2 className="sidebar__section-title">Project</h2>}
        <div className="sidebar__actions">
          {isCollapsed ? (
            <>
              <button
                className="sidebar__icon-button"
                onClick={onBrowseAndLoad}
                disabled={isLoading}
                title="Open Project"
                data-testid="qms-sidebar-btn-open-project"
              >
                📂
              </button>
              <button
                className="sidebar__icon-button"
                onClick={onCreateProject}
                disabled={isLoading}
                title="Create New Project"
                data-testid="qms-sidebar-btn-create-new-project"
              >
                ✨
              </button>
              <button
                className="sidebar__icon-button"
                onClick={onOpenDemoGallery}
                disabled={isLoading}
                title="Browse Demo Gallery"
                data-testid="qms-sidebar-btn-demo-gallery"
              >
                🎨
              </button>
            </>
          ) : (
            <div className="sidebar__action-buttons">
              <button
                className="sidebar__action-btn"
                onClick={onBrowseAndLoad}
                disabled={isLoading}
                title="Browse and load an existing project"
                data-testid="qms-sidebar-btn-open-project"
              >
                <span className="sidebar__action-icon">📂</span>
                Open Project…
              </button>
            <button
                className="sidebar__action-btn"
              onClick={onCreateProject}
              disabled={isLoading}
                title="Create a new QE project"
                data-testid="qms-sidebar-btn-create-new-project"
              >
                <span className="sidebar__action-icon">✨</span>
                Create New…
              </button>
              <button
                className="sidebar__action-btn"
                onClick={onOpenDemoGallery}
                disabled={isLoading}
                title="Browse ready-to-run demo projects"
                data-testid="qms-sidebar-btn-demo-gallery"
              >
                <span className="sidebar__action-icon">🎨</span>
                Demo Gallery…
            </button>
            </div>
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
            data-testid="qms-nav-home"
          >
            <span className="sidebar__tab-icon">🏠</span>
            {!isCollapsed && 'Home'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'structures' ? 'active' : ''}`}
            onClick={() => onViewChange('structures')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'View and manage crystal structures' : 'Load a project first'}
            data-testid="qms-nav-structures"
          >
            <span className="sidebar__tab-icon">🔬</span>
            {!isCollapsed && 'Structures'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'calculations' ? 'active' : ''}`}
            onClick={() => onViewChange('calculations')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'Configure and run QE calculations' : 'Load a project first'}
            data-testid="qms-nav-calculations"
          >
            <span className="sidebar__tab-icon">📊</span>
            {!isCollapsed && 'Calculations'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'jobs' ? 'active' : ''}`}
            onClick={() => onViewChange('jobs')}
            title={activeJobsCount > 0 ? `${runningCount} running, ${pendingCount} pending` : 'View job queue and logs'}
            data-testid="qms-nav-jobs"
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
            className={`sidebar__tab ${currentView === 'history' ? 'active' : ''}`}
            onClick={() => onViewChange('history')}
            disabled={!projectLoaded}
            title={projectLoaded ? 'View project history timeline' : 'Load a project first'}
            data-testid="qms-nav-history"
          >
            <span className="sidebar__tab-icon">📜</span>
            {!isCollapsed && 'History'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'resources' ? 'active' : ''}`}
            onClick={() => onViewChange('resources')}
            title="Browse engine parameter reference"
            data-testid="qms-nav-resources"
          >
            <span className="sidebar__tab-icon">📚</span>
            {!isCollapsed && 'Resources'}
          </button>
          <button
            className={`sidebar__tab ${currentView === 'settings' ? 'active' : ''}`}
            onClick={() => onViewChange('settings')}
            title="Configure QE paths and app settings"
            data-testid="qms-nav-settings"
          >
            <span className="sidebar__tab-icon">⚙️</span>
            {!isCollapsed && 'Settings'}
          </button>
          {/* DEV ONLY: Volume Viewer Sandbox */}
          <button
            className={`sidebar__tab ${currentView === 'dev-volume' ? 'active' : ''}`}
            onClick={() => onViewChange('dev-volume')}
            title="[DEV] Volume Viewer Sandbox"
            data-testid="qms-nav-dev-volume"
            style={{ borderTop: '2px solid #f0f0f0', marginTop: '8px', paddingTop: '8px' }}
          >
            <span className="sidebar__tab-icon">🧊</span>
            {!isCollapsed && 'Volume (DEV)'}
          </button>
        </div>
      </div>
      
      {/* Footer spacer */}
      <div className="sidebar__spacer" />
      
      {/* Footer with collapse toggle */}
      <div className="sidebar__footer">
        {!isCollapsed && <span className="sidebar__version">QMatSuite v2.0.0</span>}
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
