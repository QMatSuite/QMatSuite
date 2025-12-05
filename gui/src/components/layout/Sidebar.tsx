/**
 * Sidebar - Navigation and controls for QuantumVITAS
 * 
 * Contains:
 * - Project path input
 * - Action buttons (Ping, Load Project, List Structures, etc.)
 * - Connection status
 */

import { useState, useCallback } from 'react';
import type { QVClient } from '../../hooks/useQVClient';
import type { DaemonStatus } from '../../types/qv';
import './Sidebar.css';

export type ViewType = 'summary' | 'structures' | 'workflows' | 'debug';

interface SidebarProps {
  qv: QVClient;
  projectRoot: string;
  onProjectRootChange: (path: string) => void;
  onLoadProject: () => void;
  onListStructures: () => void;
  onListWorkflows: () => void;
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  daemonStatus: DaemonStatus | null;
}

export function Sidebar({ 
  qv, 
  projectRoot, 
  onProjectRootChange,
  onLoadProject,
  onListStructures,
  onListWorkflows,
  currentView,
  onViewChange,
  daemonStatus,
}: SidebarProps) {
  const [pingResult, setPingResult] = useState<string | null>(null);
  
  const handlePing = useCallback(async () => {
    const response = await qv.ping();
    if (response.ok && response.data) {
      setPingResult(`✓ Daemon v${response.data.version}`);
      setTimeout(() => setPingResult(null), 3000);
    } else {
      setPingResult(`✗ ${response.error?.message || 'Failed'}`);
    }
  }, [qv]);
  
  const isLoading = qv.state.isLoading;
  const isConnected = qv.state.isConnected;
  
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
          <input
            type="text"
            className="sidebar__input"
            value={projectRoot}
            onChange={(e) => onProjectRootChange(e.target.value)}
            placeholder="/path/to/project"
            disabled={isLoading}
          />
        </label>
      </div>
      
      {/* System Actions */}
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">System</h2>
        <div className="sidebar__actions">
          <button
            className="sidebar__button sidebar__button--small"
            onClick={handlePing}
            disabled={isLoading}
          >
            🏓 Ping
          </button>
          {pingResult && (
            <span className={`sidebar__ping-result ${pingResult.startsWith('✓') ? 'success' : 'error'}`}>
              {pingResult}
            </span>
          )}
        </div>
      </div>
      
      {/* Project Actions */}
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">Project</h2>
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
            onClick={onListStructures}
            disabled={isLoading || !projectRoot}
          >
            🔬 List Structures
          </button>
          
          <button
            className="sidebar__button"
            onClick={onListWorkflows}
            disabled={isLoading || !projectRoot}
          >
            📊 List Workflows
          </button>
        </div>
      </div>
      
      {/* View Tabs */}
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">View</h2>
        <div className="sidebar__tabs">
          <button
            className={`sidebar__tab ${currentView === 'summary' ? 'active' : ''}`}
            onClick={() => onViewChange('summary')}
          >
            📋 Summary
          </button>
          <button
            className={`sidebar__tab ${currentView === 'structures' ? 'active' : ''}`}
            onClick={() => onViewChange('structures')}
          >
            🔬 Structures
          </button>
          <button
            className={`sidebar__tab ${currentView === 'debug' ? 'active' : ''}`}
            onClick={() => onViewChange('debug')}
          >
            🔧 Debug
          </button>
        </div>
      </div>
      
      {/* Error Display */}
      {qv.state.lastError && (
        <div className="sidebar__error">
          <strong>Error:</strong> {qv.state.lastError}
        </div>
      )}
      
      {/* Footer spacer */}
      <div className="sidebar__spacer" />
      
      {/* Version info */}
      <div className="sidebar__footer">
        <span className="sidebar__version">QuantumVITAS v2.0.0</span>
      </div>
    </div>
  );
}
