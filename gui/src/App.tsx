/**
 * QuantumVITAS GUI - Main Application Component
 * 
 * Provides the main application layout with:
 * - Sidebar for navigation and actions
 * - Main panel with structured views (Project Summary, Structures, Debug)
 * - Debug panel for daemon logs
 */

import { useState, useCallback } from 'react';
import { 
  AppShell, 
  Sidebar, 
  ProjectSummaryPanel, 
  StructureListPanel,
  StructureDetailPanel,
  DebugPanel,
  ResultPanel,
  DaemonErrorBanner,
} from './components';
import type { ViewType } from './components/layout/Sidebar';
import { useQVClient, useDaemonStatus } from './hooks';
import type { ProjectSummary, StructureInfo, QVResponse } from './types';
import './App.css';

function App() {
  // Project root path state (persisted in localStorage)
  const [projectRoot, setProjectRoot] = useState<string>(() => {
    return localStorage.getItem('qv-project-root') || '';
  });
  
  // View state
  const [currentView, setCurrentView] = useState<ViewType>('summary');
  
  // Data state
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  
  // Debug state
  const [debugResult, setDebugResult] = useState<QVResponse | null>(null);
  const [showDebugFooter, setShowDebugFooter] = useState(true);
  
  // Loading states
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  
  // Hooks
  const qv = useQVClient();
  const daemonStatus = useDaemonStatus();
  
  // Handle project root change
  const handleProjectRootChange = useCallback((path: string) => {
    setProjectRoot(path);
    localStorage.setItem('qv-project-root', path);
  }, []);
  
  // Load project summary
  const handleLoadProject = useCallback(async () => {
    setIsLoadingProject(true);
    const response = await qv.getProjectSummary(projectRoot);
    setIsLoadingProject(false);
    
    if (response.ok && response.data) {
      setProjectSummary(response.data);
      setCurrentView('summary');
    }
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot]);
  
  // List structures
  const handleListStructures = useCallback(async () => {
    setIsLoadingStructures(true);
    const response = await qv.listStructures(projectRoot);
    setIsLoadingStructures(false);
    
    if (response.ok && response.data) {
      setStructures(response.data.structures);
      setCurrentView('structures');
    }
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot]);
  
  // List workflows (for future use)
  const handleListWorkflows = useCallback(async () => {
    const response = await qv.listWorkflows(projectRoot);
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot]);
  
  // Handle structure selection
  const handleSelectStructure = useCallback((structure: StructureInfo) => {
    setSelectedStructure(structure);
  }, []);
  
  // Render main content based on current view
  const renderMainContent = () => {
    switch (currentView) {
      case 'summary':
        return (
          <ProjectSummaryPanel 
            summary={projectSummary} 
            isLoading={isLoadingProject}
          />
        );
        
      case 'structures':
        return (
          <div className="structures-view">
            <div className="structures-view__list">
              <StructureListPanel
                structures={structures}
                isLoading={isLoadingStructures}
                selectedId={selectedStructure?.id}
                onSelect={handleSelectStructure}
              />
            </div>
            {selectedStructure && (
              <div className="structures-view__detail">
                <StructureDetailPanel
                  structure={selectedStructure}
                  onClose={() => setSelectedStructure(null)}
                />
              </div>
            )}
          </div>
        );
        
      case 'debug':
        return <ResultPanel result={debugResult} />;
        
      default:
        return null;
    }
  };
  
  return (
    <AppShell
      sidebar={
        <Sidebar
          qv={qv}
          projectRoot={projectRoot}
          onProjectRootChange={handleProjectRootChange}
          onLoadProject={handleLoadProject}
          onListStructures={handleListStructures}
          onListWorkflows={handleListWorkflows}
          currentView={currentView}
          onViewChange={setCurrentView}
          daemonStatus={daemonStatus}
        />
      }
      footer={showDebugFooter ? <DebugPanel /> : null}
    >
      <div className="main-content">
        {/* Daemon Error Banner */}
        <DaemonErrorBanner status={daemonStatus} />
        
        {/* Header */}
        <div className="app-header">
          <h2 className="app-header__title">
            {currentView === 'summary' && 'Project Summary'}
            {currentView === 'structures' && 'Structures'}
            {currentView === 'workflows' && 'Workflows'}
            {currentView === 'debug' && 'Debug Output'}
          </h2>
          <div className="app-header__actions">
            <button
              className="app-header__toggle"
              onClick={() => setShowDebugFooter(!showDebugFooter)}
            >
              {showDebugFooter ? '🔽 Hide Logs' : '🔼 Show Logs'}
            </button>
          </div>
        </div>
        
        {/* Main Content */}
        <div className="main-content__body">
          {renderMainContent()}
        </div>
      </div>
    </AppShell>
  );
}

export default App;
