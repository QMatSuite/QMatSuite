/**
 * Sidebar - Navigation and controls for QuantumVITAS
 * 
 * Contains:
 * - Project path input
 * - Action buttons (Ping, List Structures, etc.)
 * - Connection status
 */

import { useState, useCallback } from 'react';
import type { QVClient } from '../../hooks/useQVClient';
import './Sidebar.css';

interface SidebarProps {
  qv: QVClient;
  projectRoot: string;
  onProjectRootChange: (path: string) => void;
  onResult: (result: unknown) => void;
}

export function Sidebar({ qv, projectRoot, onProjectRootChange, onResult }: SidebarProps) {
  const [activeAction, setActiveAction] = useState<string | null>(null);
  
  const handleAction = useCallback(async (
    actionName: string,
    action: () => Promise<unknown>
  ) => {
    setActiveAction(actionName);
    try {
      const result = await action();
      onResult(result);
    } finally {
      setActiveAction(null);
    }
  }, [onResult]);
  
  const isLoading = qv.state.isLoading || activeAction !== null;
  
  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar__header">
        <h1 className="sidebar__title">
          <span className="sidebar__logo">⚛</span>
          QuantumVITAS
        </h1>
        <div className={`sidebar__status ${qv.state.isConnected ? 'connected' : 'disconnected'}`}>
          <span className="sidebar__status-dot" />
          {qv.state.isConnected ? 'Connected' : 'Disconnected'}
        </div>
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
      
      {/* Actions */}
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">System</h2>
        <div className="sidebar__actions">
          <button
            className="sidebar__button sidebar__button--primary"
            onClick={() => handleAction('ping', qv.ping)}
            disabled={isLoading}
          >
            {activeAction === 'ping' ? '⏳' : '🏓'} Ping Daemon
          </button>
        </div>
      </div>
      
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">Project</h2>
        <div className="sidebar__actions">
          <button
            className="sidebar__button"
            onClick={() => handleAction('summary', () => qv.getProjectSummary(projectRoot))}
            disabled={isLoading || !projectRoot}
          >
            {activeAction === 'summary' ? '⏳' : '📋'} Project Summary
          </button>
          
          <button
            className="sidebar__button"
            onClick={() => handleAction('structures', () => qv.listStructures(projectRoot))}
            disabled={isLoading || !projectRoot}
          >
            {activeAction === 'structures' ? '⏳' : '🔬'} List Structures
          </button>
          
          <button
            className="sidebar__button"
            onClick={() => handleAction('workflows', () => qv.listWorkflows(projectRoot))}
            disabled={isLoading || !projectRoot}
          >
            {activeAction === 'workflows' ? '⏳' : '📊'} List Workflows
          </button>
        </div>
      </div>
      
      <div className="sidebar__section">
        <h2 className="sidebar__section-title">Jobs</h2>
        <div className="sidebar__actions">
          <button
            className="sidebar__button"
            onClick={() => handleAction('jobs', () => qv.listJobs({}))}
            disabled={isLoading}
          >
            {activeAction === 'jobs' ? '⏳' : '📝'} List Jobs
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

