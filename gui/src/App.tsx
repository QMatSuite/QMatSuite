/**
 * QuantumVITAS GUI - Main Application Component
 * 
 * Provides the main application layout with:
 * - Sidebar for navigation and actions
 * - Main panel with structured views
 * - Auto-fetching data on view change
 * - Dialogs for project/structure/workflow creation
 * - Jobs panel for managing QE runs
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { 
  AppShell, 
  Sidebar, 
  ProjectSummaryPanel, 
  StructureListPanel,
  StructureDetailPanel,
  WorkflowListPanel,
  WorkflowDetailPanel,
  StructureViewer3D,
  AnalysisPanel,
  DebugPanel,
  DebugView,
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateWorkflowDialog,
  JobsPanel,
} from './components';
import type { ViewType } from './components/layout/Sidebar';
import { useQVClient, useDaemonStatus } from './hooks';
import type { 
  ProjectSummary, 
  StructureInfo, 
  WorkflowInfo,
  StructureVisData,
  ScfConvergenceData,
  DosData,
  BandStructureData,
  QVResponse,
  JobCounts,
  JobSubmitResult,
} from './types';
import './App.css';

function App() {
  // Project root path state (persisted in localStorage)
  const [projectRoot, setProjectRoot] = useState<string>(() => {
    return localStorage.getItem('qv-project-root') || '';
  });
  
  // View state
  const [currentView, setCurrentView] = useState<ViewType>('summary');
  
  // Project state
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  
  // Data state
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowInfo | null>(null);
  const [structureVisData, setStructureVisData] = useState<StructureVisData | null>(null);
  
  // Debug state
  const [debugResult, setDebugResult] = useState<QVResponse | null>(null);
  const [showDebugFooter, setShowDebugFooter] = useState(true);
  
  // Loading states
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false);
  const [isLoading3D, setIsLoading3D] = useState(false);
  
  // Dialog states
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [showImportStructure, setShowImportStructure] = useState(false);
  const [showCreateWorkflow, setShowCreateWorkflow] = useState(false);
  
  // Job counts for sidebar badge
  const [jobCounts, setJobCounts] = useState<JobCounts | null>(null);
  
  // Toast/notification state for job submissions
  const [jobNotification, setJobNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const notificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Hooks
  const qv = useQVClient();
  const daemonStatus = useDaemonStatus();
  
  // ==========================================================================
  // Job Counts Polling
  // ==========================================================================
  
  const fetchJobCounts = useCallback(async () => {
    if (!window.qv) return;
    
    try {
      const response = await window.qv.request<JobCounts>('job_counts', {});
      if (response.ok && response.data) {
        setJobCounts(response.data);
      }
    } catch {
      // Ignore errors
    }
  }, []);
  
  // Poll job counts
  useEffect(() => {
    fetchJobCounts();
    const interval = setInterval(fetchJobCounts, 5000);
    return () => clearInterval(interval);
  }, [fetchJobCounts]);
  
  // ==========================================================================
  // Notification Helper
  // ==========================================================================
  
  const showNotification = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    // Clear any existing timeout
    if (notificationTimeoutRef.current) {
      clearTimeout(notificationTimeoutRef.current);
    }
    
    setJobNotification({ message, type });
    
    // Auto-hide after 5 seconds
    notificationTimeoutRef.current = setTimeout(() => {
      setJobNotification(null);
    }, 5000);
  }, []);
  
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (notificationTimeoutRef.current) {
        clearTimeout(notificationTimeoutRef.current);
      }
    };
  }, []);
  
  // ==========================================================================
  // Project Management
  // ==========================================================================
  
  const handleProjectRootChange = useCallback((path: string) => {
    setProjectRoot(path);
    setProjectError(null);
    localStorage.setItem('qv-project-root', path);
  }, []);
  
  const handleLoadProject = useCallback(async () => {
    if (!projectRoot) return;
    
    setIsLoadingProject(true);
    setProjectError(null);
    
    const response = await qv.getProjectSummary(projectRoot);
    
    setIsLoadingProject(false);
    
    if (response.ok && response.data) {
      setProjectSummary(response.data);
      setProjectLoaded(true);
      setProjectError(null);
      setDebugResult(response as QVResponse);
      
      // Clear cached data to force refetch
      setStructures(null);
      setWorkflows(null);
      setSelectedStructure(null);
      setSelectedWorkflow(null);
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
      setDebugResult(response as QVResponse);
    }
  }, [qv, projectRoot]);
  
  const handleBrowseAndLoad = useCallback(async () => {
    if (window.qv?.openDirectory) {
      const path = await window.qv.openDirectory();
      if (path) {
        setProjectRoot(path);
        localStorage.setItem('qv-project-root', path);
        
        // Auto-load the project
        setIsLoadingProject(true);
        setProjectError(null);
        
        const response = await qv.getProjectSummary(path);
        
        setIsLoadingProject(false);
        
        if (response.ok && response.data) {
          setProjectSummary(response.data);
          setProjectLoaded(true);
          setProjectError(null);
          setStructures(null);
          setWorkflows(null);
        } else {
          setProjectError(response.error?.message || 'Failed to load project');
        }
      }
    }
  }, [qv]);
  
  const handleCreateProjectSuccess = useCallback((newProjectRoot: string) => {
    setProjectRoot(newProjectRoot);
    localStorage.setItem('qv-project-root', newProjectRoot);
    // Load the newly created project
    setTimeout(() => handleLoadProject(), 100);
  }, [handleLoadProject]);
  
  // ==========================================================================
  // Data Fetching
  // ==========================================================================
  
  const fetchStructures = useCallback(async () => {
    if (!projectRoot || !projectLoaded) return;
    
    setIsLoadingStructures(true);
    const response = await qv.listStructures(projectRoot);
    setIsLoadingStructures(false);
    
    if (response.ok && response.data) {
      setStructures(response.data.structures);
    }
  }, [qv, projectRoot, projectLoaded]);
  
  const fetchWorkflows = useCallback(async () => {
    if (!projectRoot || !projectLoaded) return;
    
    setIsLoadingWorkflows(true);
    const response = await qv.listWorkflows(projectRoot);
    setIsLoadingWorkflows(false);
    
    if (response.ok && response.data) {
      setWorkflows(response.data.workflows);
    }
  }, [qv, projectRoot, projectLoaded]);
  
  // Auto-fetch data when switching views
  useEffect(() => {
    if (currentView === 'structures' && !structures && projectLoaded) {
      fetchStructures();
    } else if (currentView === 'workflows' && !workflows && projectLoaded) {
      fetchWorkflows();
    } else if (currentView === 'analysis' && !workflows && projectLoaded) {
      fetchWorkflows();
    }
  }, [currentView, structures, workflows, projectLoaded, fetchStructures, fetchWorkflows]);
  
  // ==========================================================================
  // Structure Handling
  // ==========================================================================
  
  const handleSelectStructure = useCallback(async (structure: StructureInfo) => {
    setSelectedStructure(structure);
    
    // Load 3D visualization data
    setIsLoading3D(true);
    const response = await qv.call('get_structure_vis', {
      project_root: projectRoot,
      selector: structure.slug,
      supercell: [1, 1, 1],
      repeat_boundary: false,
    });
    setIsLoading3D(false);
    
    if (response.ok && response.data) {
      setStructureVisData(response.data as StructureVisData);
    } else {
      setStructureVisData(null);
    }
  }, [qv, projectRoot]);
  
  const handleImportStructureSuccess = useCallback(async (structureId: string) => {
    // Refresh structures list
    await fetchStructures();
    
    // Select the newly imported structure
    if (structures) {
      const newStruct = structures.find(s => s.id === structureId);
      if (newStruct) {
        handleSelectStructure(newStruct);
      }
    }
  }, [fetchStructures, structures, handleSelectStructure]);
  
  // ==========================================================================
  // Workflow Handling
  // ==========================================================================
  
  const handleSelectWorkflow = useCallback((workflow: WorkflowInfo) => {
    setSelectedWorkflow(workflow);
  }, []);
  
  const handleCreateWorkflowSuccess = useCallback(async (workflowId: string) => {
    // Refresh workflows list
    await fetchWorkflows();
    
    // Select the newly created workflow
    if (workflows) {
      const newWf = workflows.find(w => w.id === workflowId);
      if (newWf) {
        handleSelectWorkflow(newWf);
      }
    }
  }, [fetchWorkflows, workflows, handleSelectWorkflow]);
  
  const handleRunWorkflow = useCallback(async (workflow: WorkflowInfo) => {
    const response = await qv.call('run_workflow', {
      project_root: projectRoot,
      workflow: workflow.slug,
    });
    
    if (response.ok && response.data) {
      const result = response.data as JobSubmitResult;
      const shortId = result.job_id.slice(0, 8);
      showNotification(`Job #${shortId} started: ${result.target_name}`, 'success');
      
      // Refresh job counts
      fetchJobCounts();
    } else {
      showNotification(`Failed to start job: ${response.error?.message || 'Unknown error'}`, 'error');
    }
    
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot, showNotification, fetchJobCounts]);
  
  const handleGoToJobs = useCallback(() => {
    setCurrentView('jobs');
  }, []);
  
  // ==========================================================================
  // Analysis Data Loading
  // ==========================================================================
  
  const handleLoadScf = useCallback(async (workflow: WorkflowInfo, step: string): Promise<ScfConvergenceData | null> => {
    const response = await qv.call('get_scf_convergence', {
      project_root: projectRoot,
      workflow: workflow.slug,
      step: step,
    });
    return response.ok ? response.data as ScfConvergenceData : null;
  }, [qv, projectRoot]);
  
  const handleLoadDos = useCallback(async (workflow: WorkflowInfo): Promise<DosData | null> => {
    const response = await qv.call('get_dos_data', {
      project_root: projectRoot,
      workflow: workflow.slug,
    });
    return response.ok ? response.data as DosData : null;
  }, [qv, projectRoot]);
  
  const handleLoadBands = useCallback(async (workflow: WorkflowInfo): Promise<BandStructureData | null> => {
    const response = await qv.call('get_band_structure_data', {
      project_root: projectRoot,
      workflow: workflow.slug,
    });
    return response.ok ? response.data as BandStructureData : null;
  }, [qv, projectRoot]);
  
  // ==========================================================================
  // View Rendering
  // ==========================================================================
  
  const renderNoProjectMessage = () => (
    <div className="no-project-message">
      <div className="no-project-content">
        <span className="no-project-icon">📦</span>
        <h3>No Project Loaded</h3>
        <p>Load or create a project to view this section.</p>
        <div className="no-project-actions">
          <button className="action-btn" onClick={handleBrowseAndLoad}>
            📂 Browse & Load
          </button>
          <button className="action-btn action-btn--secondary" onClick={() => setShowCreateProject(true)}>
            ✨ Create Project
          </button>
        </div>
      </div>
    </div>
  );
  
  const renderMainContent = () => {
    switch (currentView) {
      case 'summary':
        return (
          <ProjectSummaryPanel 
            summary={projectSummary} 
            isLoading={isLoadingProject}
            error={projectError}
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => setShowCreateProject(true)}
          />
        );
        
      case 'structures':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <div className="structures-view">
            <div className="structures-view__list">
              <StructureListPanel
                structures={structures}
                isLoading={isLoadingStructures}
                selectedId={selectedStructure?.id}
                onSelect={handleSelectStructure}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowImportStructure(true)}
              >
                ➕ Import Structure
              </button>
            </div>
            {selectedStructure && (
              <div className="structures-view__detail">
                <StructureDetailPanel
                  structure={selectedStructure}
                  onClose={() => {
                    setSelectedStructure(null);
                    setStructureVisData(null);
                  }}
                />
                <div className="structures-view__3d">
                  <StructureViewer3D
                    data={structureVisData}
                    isLoading={isLoading3D}
                    showBonds={true}
                    showUnitCell={true}
                  />
                </div>
              </div>
            )}
          </div>
        );
        
      case 'workflows':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <div className="workflows-view">
            <div className="workflows-view__list">
              <WorkflowListPanel
                workflows={workflows}
                isLoading={isLoadingWorkflows}
                selectedId={selectedWorkflow?.id}
                onSelect={handleSelectWorkflow}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowCreateWorkflow(true)}
              >
                ➕ New Workflow
              </button>
            </div>
            {selectedWorkflow && (
              <div className="workflows-view__detail">
                <WorkflowDetailPanel
                  workflow={selectedWorkflow}
                  onClose={() => setSelectedWorkflow(null)}
                  onRunWorkflow={handleRunWorkflow}
                  onGoToJobs={handleGoToJobs}
                />
              </div>
            )}
          </div>
        );
        
      case 'jobs':
        return (
          <JobsPanel projectRoot={projectLoaded ? projectRoot : undefined} />
        );
        
      case 'analysis':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <AnalysisPanel
            workflows={workflows}
            selectedWorkflow={selectedWorkflow}
            onSelectWorkflow={handleSelectWorkflow}
            onLoadScf={handleLoadScf}
            onLoadDos={handleLoadDos}
            onLoadBands={handleLoadBands}
          />
        );
        
      case 'debug':
        return <DebugView lastResult={debugResult} />;
        
      default:
        return null;
    }
  };
  
  return (
    <>
      <AppShell
        sidebar={
          <Sidebar
            qv={qv}
            projectRoot={projectRoot}
            projectLoaded={projectLoaded}
            projectError={projectError}
            onProjectRootChange={handleProjectRootChange}
            onLoadProject={handleLoadProject}
            onCreateProject={() => setShowCreateProject(true)}
            currentView={currentView}
            onViewChange={setCurrentView}
            daemonStatus={daemonStatus}
            jobCounts={jobCounts}
          />
        }
        footer={showDebugFooter ? <DebugPanel /> : null}
      >
        <div className="main-content">
          {/* Daemon Error Banner */}
          <DaemonErrorBanner status={daemonStatus} />
          
          {/* Job Notification Toast */}
          {jobNotification && (
            <div className={`job-notification job-notification--${jobNotification.type}`}>
              <span className="job-notification__message">{jobNotification.message}</span>
              <button 
                className="job-notification__close"
                onClick={() => setJobNotification(null)}
              >
                ×
              </button>
            </div>
          )}
          
          {/* Header */}
          <div className="app-header">
            <h2 className="app-header__title">
              {currentView === 'summary' && 'Project Summary'}
              {currentView === 'structures' && 'Structures'}
              {currentView === 'workflows' && 'Workflows'}
              {currentView === 'jobs' && 'Jobs'}
              {currentView === 'analysis' && 'Analysis'}
              {currentView === 'debug' && 'Debug'}
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
      
      {/* Dialogs */}
      <CreateProjectDialog
        isOpen={showCreateProject}
        onClose={() => setShowCreateProject(false)}
        onSuccess={handleCreateProjectSuccess}
      />
      
      <ImportStructureDialog
        isOpen={showImportStructure}
        projectRoot={projectRoot}
        onClose={() => setShowImportStructure(false)}
        onSuccess={handleImportStructureSuccess}
      />
      
      <CreateWorkflowDialog
        isOpen={showCreateWorkflow}
        projectRoot={projectRoot}
        structures={structures || []}
        onClose={() => setShowCreateWorkflow(false)}
        onSuccess={handleCreateWorkflowSuccess}
      />
    </>
  );
}

export default App;
