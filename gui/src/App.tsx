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
  StatusBar,
  ResizablePane,
  VerticalResizablePane,
  ProjectSummaryPanel, 
  StructureListPanel,
  StructureDetailPanel,
  WorkflowListPanel,
  WorkflowDetailPanel,
  StepDetailPanel,
  StructureViewer3D,
  AnalysisPanel,
  DebugPanel,
  DebugView,
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateWorkflowDialog,
  RenameDialog,
  DeleteConfirmDialog,
  JobsPanel,
  SettingsPanel,
  ErrorBoundary,
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
  PreflightCheckResult,
} from './types';
import './App.css';

function App() {
  // Project root path state (persisted in localStorage)
  const [projectRoot, setProjectRoot] = useState<string>(() => {
    return localStorage.getItem('qv-project-root') || '';
  });
  
  // Recent projects (persisted in localStorage)
  const [recentProjects, setRecentProjects] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('qv-recent-projects') || '[]');
    } catch {
      return [];
    }
  });
  
  // View state
  const [currentView, setCurrentView] = useState<ViewType>('home');
  
  // Project state
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  
  // Data state
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowInfo | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
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
  const [showCreateDemoProject, setShowCreateDemoProject] = useState(false);
  const [showImportStructure, setShowImportStructure] = useState(false);
  const [showCreateWorkflow, setShowCreateWorkflow] = useState(false);
  
  // Rename/delete dialog states
  const [renameStructure, setRenameStructure] = useState<StructureInfo | null>(null);
  const [deleteStructure, setDeleteStructure] = useState<StructureInfo | null>(null);
  const [renameWorkflow, setRenameWorkflow] = useState<WorkflowInfo | null>(null);
  const [deleteWorkflow, setDeleteWorkflow] = useState<WorkflowInfo | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Job counts for sidebar badge
  const [jobCounts, setJobCounts] = useState<JobCounts | null>(null);
  
  // Toast/notification state for job submissions
  const [jobNotification, setJobNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const notificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // App settings (persisted in localStorage)
  const [appSettings, setAppSettings] = useState<{ 
    theme: 'dark' | 'light'; 
    autoAnalysis: boolean;
    defaultProjectsDir: string;
  }>(() => {
    try {
      const saved = localStorage.getItem('qv-app-settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          theme: parsed.theme || 'dark',
          autoAnalysis: parsed.autoAnalysis ?? true,
          defaultProjectsDir: parsed.defaultProjectsDir || '',
        };
      }
    } catch {
      // ignore
    }
    return { theme: 'dark', autoAnalysis: true, defaultProjectsDir: '' };
  });
  
  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', appSettings.theme);
    localStorage.setItem('qv-app-settings', JSON.stringify(appSettings));
  }, [appSettings]);
  
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
  
  // Add to recent projects
  const addToRecentProjects = useCallback((path: string) => {
    setRecentProjects(prev => {
      // Remove if already exists, then add to front
      const filtered = prev.filter(p => p !== path);
      const updated = [path, ...filtered].slice(0, 5); // Keep max 5
      localStorage.setItem('qv-recent-projects', JSON.stringify(updated));
      return updated;
    });
  }, []);
  
  // Remove from recent projects
  const removeFromRecentProjects = useCallback((path: string) => {
    setRecentProjects(prev => {
      const filtered = prev.filter(p => p !== path);
      localStorage.setItem('qv-recent-projects', JSON.stringify(filtered));
      return filtered;
    });
  }, []);
  
  // Open a recent project
  const handleOpenRecentProject = useCallback(async (path: string) => {
    setProjectRoot(path);
    localStorage.setItem('qv-project-root', path);
    
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
      addToRecentProjects(path);
      
      // Set project path for log file storage
      window.qv?.setProject?.(path);
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
    }
  }, [qv, addToRecentProjects]);
  
  const handleLoadProject = useCallback(async () => {
    if (!projectRoot) return;
    
    setIsLoadingProject(true);
    setProjectError(null);
    
    // First try loading directly from the path
    const response = await qv.getProjectSummary(projectRoot);
    
    if (response.ok && response.data) {
      setIsLoadingProject(false);
      setProjectSummary(response.data);
      setProjectLoaded(true);
      setProjectError(null);
      setDebugResult(response as QVResponse);
      setStructures(null);
      setWorkflows(null);
      setSelectedStructure(null);
      setSelectedWorkflow(null);
      addToRecentProjects(projectRoot);
      window.qv?.setProject?.(projectRoot);
      return;
    }
    
    // Not a project directly - search up for project root
    const findResponse = await qv.call('find_project_root', { start_dir: projectRoot });
    
    if (findResponse.ok && findResponse.data?.found && findResponse.data?.project_root) {
      // Found a project in parent directory
      const foundRoot = findResponse.data.project_root;
      setProjectRoot(foundRoot);
      localStorage.setItem('qv-project-root', foundRoot);
      
      const parentResponse = await qv.getProjectSummary(foundRoot);
      
      if (parentResponse.ok && parentResponse.data) {
        setIsLoadingProject(false);
        setProjectSummary(parentResponse.data);
        setProjectLoaded(true);
        setProjectError(null);
        setStructures(null);
        setWorkflows(null);
        setSelectedStructure(null);
        setSelectedWorkflow(null);
        addToRecentProjects(foundRoot);
        window.qv?.setProject?.(foundRoot);
        showNotification(`Loaded project from: ${foundRoot}`, 'success');
        return;
      }
    }
    
    setIsLoadingProject(false);
    
    // No project found - offer to create one
    const shouldCreate = window.confirm(
      `This folder is not a QuantumVITAS project.\n\nWould you like to create a new project here?\n\n${projectRoot}`
    );
    
    if (shouldCreate) {
      setIsLoadingProject(true);
      const createResponse = await qv.call('create_project', {
        target_dir: projectRoot,
      });
      
      if (createResponse.ok && createResponse.data) {
        const loadResponse = await qv.getProjectSummary(projectRoot);
        setIsLoadingProject(false);
        
        if (loadResponse.ok && loadResponse.data) {
          setProjectSummary(loadResponse.data);
          setProjectLoaded(true);
          setProjectError(null);
          setStructures(null);
          setWorkflows(null);
          addToRecentProjects(projectRoot);
          showNotification('Project created successfully!', 'success');
          window.qv?.setProject?.(projectRoot);
        } else {
          setProjectError(loadResponse.error?.message || 'Failed to load created project');
        }
      } else {
        setIsLoadingProject(false);
        setProjectError(createResponse.error?.message || 'Failed to create project');
      }
    } else {
      setProjectError(null);
    }
  }, [qv, projectRoot, addToRecentProjects, showNotification]);
  
  const handleBrowseAndLoad = useCallback(async () => {
    if (!window.qv?.openDirectory) return;
    
    const selectedPath = await window.qv.openDirectory();
    if (!selectedPath) return;
    
    setIsLoadingProject(true);
    setProjectError(null);
    
    // First, check if selected directory is a project
    let projectPath = selectedPath;
    const directResponse = await qv.getProjectSummary(selectedPath);
    
    if (directResponse.ok && directResponse.data) {
      // Selected directory is a valid project
      setProjectRoot(selectedPath);
      localStorage.setItem('qv-project-root', selectedPath);
      setProjectSummary(directResponse.data);
      setProjectLoaded(true);
      setStructures(null);
      setWorkflows(null);
      addToRecentProjects(selectedPath);
      window.qv?.setProject?.(selectedPath);
      setIsLoadingProject(false);
      return;
    }
    
    // Not a project - search up for project root
    const findResponse = await qv.call('find_project_root', { start_dir: selectedPath });
    
    if (findResponse.ok && findResponse.data?.found && findResponse.data?.project_root) {
      // Found a project in parent directory
      projectPath = findResponse.data.project_root;
      
      setProjectRoot(projectPath);
      localStorage.setItem('qv-project-root', projectPath);
      
      const parentResponse = await qv.getProjectSummary(projectPath);
      
      if (parentResponse.ok && parentResponse.data) {
        setProjectSummary(parentResponse.data);
        setProjectLoaded(true);
        setStructures(null);
        setWorkflows(null);
        addToRecentProjects(projectPath);
        window.qv?.setProject?.(projectPath);
        setIsLoadingProject(false);
        showNotification(`Loaded project from: ${projectPath}`, 'success');
        return;
      }
    }
    
    setIsLoadingProject(false);
    
    // No project found - ask user if they want to create one
    const shouldCreate = window.confirm(
      `This folder is not a QuantumVITAS project.\n\nWould you like to create a new project here?\n\n${selectedPath}`
    );
    
    if (shouldCreate) {
      setIsLoadingProject(true);
      const createResponse = await qv.call('create_project', {
        target_dir: selectedPath,
      });
      
      if (createResponse.ok && createResponse.data) {
        const loadResponse = await qv.getProjectSummary(selectedPath);
        setIsLoadingProject(false);
        
        if (loadResponse.ok && loadResponse.data) {
          setProjectRoot(selectedPath);
          localStorage.setItem('qv-project-root', selectedPath);
          setProjectSummary(loadResponse.data);
          setProjectLoaded(true);
          setStructures(null);
          setWorkflows(null);
          addToRecentProjects(selectedPath);
          showNotification('Project created successfully!', 'success');
          window.qv?.setProject?.(selectedPath);
        } else {
          setProjectError(loadResponse.error?.message || 'Failed to load created project');
        }
      } else {
        setIsLoadingProject(false);
        setProjectError(createResponse.error?.message || 'Failed to create project');
      }
    } else {
      setProjectError(null);
      setProjectRoot('');
      localStorage.removeItem('qv-project-root');
    }
  }, [qv, addToRecentProjects, showNotification]);
  
  const handleCreateProjectSuccess = useCallback(async (newProjectRoot: string) => {
    setProjectRoot(newProjectRoot);
    localStorage.setItem('qv-project-root', newProjectRoot);
    
    // Load the newly created project immediately with the new path
    setIsLoadingProject(true);
    setProjectError(null);
    
    const response = await qv.getProjectSummary(newProjectRoot);
    
    setIsLoadingProject(false);
    
    if (response.ok && response.data) {
      setProjectSummary(response.data);
      setProjectLoaded(true);
      setProjectError(null);
      setStructures(null);
      setWorkflows(null);
      setSelectedStructure(null);
      setSelectedWorkflow(null);
      addToRecentProjects(newProjectRoot);
      
      // Set project path for log file storage
      window.qv?.setProject?.(newProjectRoot);
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
    }
  }, [qv, addToRecentProjects]);
  
  // Create demo Si project - now uses dialog
  const handleCreateDemoProject = useCallback(() => {
    setShowCreateDemoProject(true);
  }, []);
  
  // ==========================================================================
  // Data Fetching
  // ==========================================================================
  
  // Refresh project summary (after adding/deleting structures/workflows)
  const refreshSummary = useCallback(async () => {
    if (!projectRoot || !projectLoaded) return;
    
    const response = await qv.getProjectSummary(projectRoot);
    if (response.ok && response.data) {
      setProjectSummary(response.data);
    }
  }, [qv, projectRoot, projectLoaded]);
  
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
  
  // Current supercell and repeat_boundary settings
  const [currentSupercell, setCurrentSupercell] = useState<[number, number, number]>([1, 1, 1]);
  const [currentRepeatBoundary, setCurrentRepeatBoundary] = useState(false);
  
  const loadStructureVis = useCallback(async (
    structure: StructureInfo, 
    supercell: [number, number, number] = [1, 1, 1],
    repeatBoundary: boolean = false
  ) => {
    setIsLoading3D(true);
    const response = await qv.call('get_structure_vis', {
      project_root: projectRoot,
      selector: structure.slug,
      supercell: supercell,
      repeat_boundary: repeatBoundary,
    });
    setIsLoading3D(false);
    
    if (response.ok && response.data) {
      setStructureVisData(response.data as StructureVisData);
    } else {
      setStructureVisData(null);
    }
  }, [qv, projectRoot]);
  
  const handleSelectStructure = useCallback(async (structure: StructureInfo) => {
    setSelectedStructure(structure);
    setCurrentSupercell([1, 1, 1]);
    setCurrentRepeatBoundary(false);
    await loadStructureVis(structure, [1, 1, 1], false);
  }, [loadStructureVis]);
  
  const handleSupercellChange = useCallback(async (supercell: [number, number, number]) => {
    if (!selectedStructure) return;
    setCurrentSupercell(supercell);
    await loadStructureVis(selectedStructure, supercell, currentRepeatBoundary);
  }, [selectedStructure, currentRepeatBoundary, loadStructureVis]);
  
  const handleRepeatBoundaryChange = useCallback(async (repeatBoundary: boolean) => {
    if (!selectedStructure) return;
    setCurrentRepeatBoundary(repeatBoundary);
    await loadStructureVis(selectedStructure, currentSupercell, repeatBoundary);
  }, [selectedStructure, currentSupercell, loadStructureVis]);
  
  const handleImportStructureSuccess = useCallback(async (structureId: string) => {
    // Refresh structures list and summary
    await fetchStructures();
    await refreshSummary();
    
    // Select the newly imported structure
    if (structures) {
      const newStruct = structures.find(s => s.id === structureId);
      if (newStruct) {
        handleSelectStructure(newStruct);
      }
    }
  }, [fetchStructures, refreshSummary, structures, handleSelectStructure]);
  
  // ==========================================================================
  // Workflow Handling
  // ==========================================================================
  
  const handleSelectWorkflow = useCallback((workflow: WorkflowInfo) => {
    setSelectedWorkflow(workflow);
  }, []);
  
  const handleCreateWorkflowSuccess = useCallback(async (workflowId: string) => {
    // Refresh workflows list and summary
    await fetchWorkflows();
    await refreshSummary();
    
    // Select the newly created workflow
    if (workflows) {
      const newWf = workflows.find(w => w.id === workflowId);
      if (newWf) {
        handleSelectWorkflow(newWf);
      }
    }
  }, [fetchWorkflows, refreshSummary, workflows, handleSelectWorkflow]);
  
  const handleRunWorkflow = useCallback(async (workflow: WorkflowInfo) => {
    // Perform preflight checks first
    const preflightResponse = await qv.call('preflight_check', {
      project_root: projectRoot,
      workflow: workflow.slug,
    });
    
    if (preflightResponse.ok && preflightResponse.data) {
      const preflight = preflightResponse.data as PreflightCheckResult;
      
      if (!preflight.ok) {
        // Show preflight errors
        const errorMsg = preflight.errors.join('; ') || 'Pre-flight check failed';
        showNotification(`Cannot run workflow: ${errorMsg}`, 'error');
        return;
      }
      
      // Show warnings if any
      if (preflight.warnings.length > 0) {
        console.warn('Preflight warnings:', preflight.warnings);
      }
    }
    
    // Submit the workflow run
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
  
  // Handle "View Analysis" from Jobs panel
  const handleViewAnalysisFromJob = useCallback(async (workflowSlug: string) => {
    // Switch to analysis view
    setCurrentView('analysis');
    
    // If workflows aren't loaded, fetch them first
    if (!workflows) {
      await fetchWorkflows();
    }
    
    // Try to find and select the workflow
    const wf = workflows?.find(w => w.slug === workflowSlug || w.name === workflowSlug);
    if (wf) {
      setSelectedWorkflow(wf);
    }
  }, [workflows, fetchWorkflows]);
  
  const handleSelectStep = useCallback((stepId: string) => {
    setSelectedStepId(stepId);
  }, []);
  
  const handleRunStepSuccess = useCallback((result: JobSubmitResult) => {
    const shortId = result.job_id.slice(0, 8);
    showNotification(`Step job #${shortId} started: ${result.target_name}`, 'success');
    fetchJobCounts();
  }, [showNotification, fetchJobCounts]);
  
  // ==========================================================================
  // Structure Rename/Delete
  // ==========================================================================
  
  const handleRenameStructure = useCallback(async (newName: string): Promise<boolean> => {
    if (!renameStructure) return false;
    
    setIsRenaming(true);
    const response = await qv.call('rename_structure', {
      project_root: projectRoot,
      selector: renameStructure.slug,
      new_name: newName,
    });
    setIsRenaming(false);
    
    if (response.ok) {
      showNotification(`Renamed structure to "${newName}"`, 'success');
      await fetchStructures();
      // Update selected structure if it was the one being renamed
      if (selectedStructure?.id === renameStructure.id) {
        setSelectedStructure(null);
        setStructureVisData(null);
      }
      return true;
    } else {
      showNotification(`Failed to rename: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, renameStructure, fetchStructures, selectedStructure, showNotification]);
  
  const handleDeleteStructure = useCallback(async (force: boolean): Promise<boolean> => {
    if (!deleteStructure) return false;
    
    setIsDeleting(true);
    const response = await qv.call('delete_structure', {
      project_root: projectRoot,
      selector: deleteStructure.slug,
      force: force,
    });
    setIsDeleting(false);
    
    if (response.ok) {
      showNotification(`Deleted structure "${deleteStructure.name}"`, 'success');
      await fetchStructures();
      await refreshSummary();
      // Clear selection if the deleted structure was selected
      if (selectedStructure?.id === deleteStructure.id) {
        setSelectedStructure(null);
        setStructureVisData(null);
      }
      return true;
    } else {
      showNotification(`Failed to delete: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, deleteStructure, fetchStructures, refreshSummary, selectedStructure, showNotification]);
  
  // ==========================================================================
  // Workflow Rename/Delete
  // ==========================================================================
  
  const handleRenameWorkflow = useCallback(async (newName: string): Promise<boolean> => {
    if (!renameWorkflow) return false;
    
    setIsRenaming(true);
    const response = await qv.call('rename_workflow', {
      project_root: projectRoot,
      selector: renameWorkflow.slug,
      new_name: newName,
    });
    setIsRenaming(false);
    
    if (response.ok) {
      showNotification(`Renamed workflow to "${newName}"`, 'success');
      await fetchWorkflows();
      // Update selected workflow if it was the one being renamed
      if (selectedWorkflow?.id === renameWorkflow.id) {
        setSelectedWorkflow(null);
      }
      return true;
    } else {
      showNotification(`Failed to rename: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, renameWorkflow, fetchWorkflows, selectedWorkflow, showNotification]);
  
  const handleDeleteWorkflow = useCallback(async (force: boolean): Promise<boolean> => {
    if (!deleteWorkflow) return false;
    
    setIsDeleting(true);
    const response = await qv.call('delete_workflow', {
      project_root: projectRoot,
      selector: deleteWorkflow.slug,
      force: force,
    });
    setIsDeleting(false);
    
    if (response.ok) {
      showNotification(`Deleted workflow "${deleteWorkflow.name}"`, 'success');
      await fetchWorkflows();
      await refreshSummary();
      // Clear selection if the deleted workflow was selected
      if (selectedWorkflow?.id === deleteWorkflow.id) {
        setSelectedWorkflow(null);
      }
      return true;
    } else {
      showNotification(`Failed to delete: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, deleteWorkflow, fetchWorkflows, refreshSummary, selectedWorkflow, showNotification]);
  
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
  
  // Navigate to a specific structure
  const handleNavigateToStructure = useCallback(async (structureName: string) => {
    setCurrentView('structures');
    
    // If no specific structure requested, just switch view
    if (!structureName) return;
    
    // After switching view, try to select the structure
    // First ensure structures are loaded
    let currentStructures = structures;
    if (!currentStructures) {
      setIsLoadingStructures(true);
      const response = await qv.listStructures(projectRoot);
      setIsLoadingStructures(false);
      if (response.ok && response.data) {
        currentStructures = response.data.structures;
        setStructures(currentStructures);
      }
    }
    
    if (currentStructures) {
      const struct = currentStructures.find(s => s.name === structureName || s.slug === structureName);
      if (struct) {
        handleSelectStructure(struct);
      }
    }
  }, [structures, handleSelectStructure, qv, projectRoot]);
  
  // Navigate to a specific workflow
  const handleNavigateToWorkflow = useCallback(async (workflowName: string) => {
    setCurrentView('workflows');
    
    // If no specific workflow requested, just switch view
    if (!workflowName) return;
    
    // After switching view, try to select the workflow
    // First ensure workflows are loaded
    let currentWorkflows = workflows;
    if (!currentWorkflows) {
      setIsLoadingWorkflows(true);
      const response = await qv.listWorkflows(projectRoot);
      setIsLoadingWorkflows(false);
      if (response.ok && response.data) {
        currentWorkflows = response.data.workflows;
        setWorkflows(currentWorkflows);
      }
    }
    
    if (currentWorkflows) {
      const wf = currentWorkflows.find(w => w.name === workflowName || w.slug === workflowName);
      if (wf) {
        handleSelectWorkflow(wf);
      }
    }
  }, [workflows, handleSelectWorkflow, qv, projectRoot]);
  
  // Close the current project
  const handleCloseProject = useCallback(() => {
    setProjectRoot('');
    setProjectSummary(null);
    setProjectLoaded(false);
    setProjectError(null);
    setStructures(null);
    setWorkflows(null);
    setSelectedStructure(null);
    setSelectedWorkflow(null);
    setStructureVisData(null);
    localStorage.removeItem('qv-project-root');
    setCurrentView('home');
  }, []);
  
  const renderMainContent = () => {
    switch (currentView) {
      case 'home':
        return (
          <ProjectSummaryPanel 
            summary={projectSummary} 
            isLoading={isLoadingProject}
            error={projectError}
            recentProjects={recentProjects}
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => setShowCreateProject(true)}
            onCreateDemoProject={handleCreateDemoProject}
            onOpenRecentProject={handleOpenRecentProject}
            onRemoveRecentProject={removeFromRecentProjects}
            onNavigateToStructure={handleNavigateToStructure}
            onNavigateToWorkflow={handleNavigateToWorkflow}
            onCloseProject={handleCloseProject}
          />
        );
        
      case 'structures':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <div className="structures-view">
            <ResizablePane
              defaultWidth={400}
              minWidth={300}
              maxWidth={550}
              storageKey="qv-structures-list-width"
              className="structures-view__list"
            >
              <StructureListPanel
                structures={structures}
                isLoading={isLoadingStructures}
                selectedId={selectedStructure?.id}
                onSelect={handleSelectStructure}
                onRename={setRenameStructure}
                onDelete={setDeleteStructure}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowImportStructure(true)}
              >
                ➕ Import Structure
              </button>
            </ResizablePane>
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
                    structureId={selectedStructure?.id}
                    onSupercellChange={handleSupercellChange}
                    onRepeatBoundaryChange={handleRepeatBoundaryChange}
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
            <ResizablePane
              defaultWidth={420}
              minWidth={320}
              maxWidth={600}
              storageKey="qv-workflows-list-width"
              className="workflows-view__list"
            >
              <WorkflowListPanel
                workflows={workflows}
                isLoading={isLoadingWorkflows}
                selectedId={selectedWorkflow?.id}
                onSelect={handleSelectWorkflow}
                onRename={setRenameWorkflow}
                onDelete={setDeleteWorkflow}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowCreateWorkflow(true)}
              >
                ➕ New Workflow
              </button>
            </ResizablePane>
            {selectedWorkflow && (
              <div className="workflows-view__detail">
                {selectedStepId ? (
                  <>
                    <VerticalResizablePane
                      defaultHeight={350}
                      minHeight={200}
                      maxHeight={500}
                      storageKey="qv-workflow-detail-height"
                      className="workflow-detail-resizable"
                    >
                      <WorkflowDetailPanel
                        workflow={selectedWorkflow}
                        projectRoot={projectRoot}
                        structures={structures || undefined}
                        onClose={() => {
                          setSelectedWorkflow(null);
                          setSelectedStepId(null);
                        }}
                        onRunWorkflow={handleRunWorkflow}
                        onSelectStep={handleSelectStep}
                        onGoToJobs={handleGoToJobs}
                        onWorkflowUpdated={fetchWorkflows}
                      />
                    </VerticalResizablePane>
                    <StepDetailPanel
                      projectRoot={projectRoot}
                      workflowSelector={selectedWorkflow.slug}
                      stepSelector={selectedStepId}
                      onClose={() => setSelectedStepId(null)}
                      onRunStep={handleRunStepSuccess}
                    />
                  </>
                ) : (
                  <WorkflowDetailPanel
                    workflow={selectedWorkflow}
                    projectRoot={projectRoot}
                    structures={structures || undefined}
                    onClose={() => {
                      setSelectedWorkflow(null);
                      setSelectedStepId(null);
                    }}
                    onRunWorkflow={handleRunWorkflow}
                    onSelectStep={handleSelectStep}
                    onGoToJobs={handleGoToJobs}
                    onWorkflowUpdated={fetchWorkflows}
                  />
                )}
              </div>
            )}
          </div>
        );
        
      case 'jobs':
        return (
          <JobsPanel 
            projectRoot={projectLoaded ? projectRoot : undefined}
            onViewAnalysis={handleViewAnalysisFromJob}
          />
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
            autoAnalysis={appSettings.autoAnalysis}
          />
        );
        
      case 'settings':
        return (
          <SettingsPanel 
            settings={appSettings}
            onSettingsChange={setAppSettings}
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
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => setShowCreateProject(true)}
            currentView={currentView}
            onViewChange={setCurrentView}
            daemonStatus={daemonStatus}
            jobCounts={jobCounts}
          />
        }
        footer={showDebugFooter ? <DebugPanel /> : null}
        statusBar={
          <StatusBar
            projectRoot={projectLoaded ? projectRoot : null}
            projectName={projectSummary?.name || null}
            daemonConnected={daemonStatus?.connected ?? false}
            onOpenSettings={() => setCurrentView('settings')}
            onOpenJobs={() => setCurrentView('jobs')}
            onNavigateToHome={() => setCurrentView('home')}
          />
        }
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
              {currentView === 'home' && 'Home'}
              {currentView === 'structures' && 'Structures'}
              {currentView === 'workflows' && 'Workflows'}
              {currentView === 'jobs' && 'Jobs'}
              {currentView === 'analysis' && 'Analysis'}
              {currentView === 'settings' && 'Settings'}
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
            <ErrorBoundary 
              fallbackTitle="View Error" 
              onReset={() => setCurrentView('home')}
            >
              {renderMainContent()}
            </ErrorBoundary>
          </div>
        </div>
      </AppShell>
      
      {/* Dialogs */}
      <CreateProjectDialog
        isOpen={showCreateProject}
        onClose={() => setShowCreateProject(false)}
        onSuccess={handleCreateProjectSuccess}
        defaultParentDir={appSettings.defaultProjectsDir}
      />
      
      <CreateProjectDialog
        isOpen={showCreateDemoProject}
        onClose={() => setShowCreateDemoProject(false)}
        onSuccess={handleCreateProjectSuccess}
        isDemoProject={true}
        defaultParentDir={appSettings.defaultProjectsDir}
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
      
      {/* Rename Dialogs */}
      <RenameDialog
        isOpen={!!renameStructure}
        onClose={() => setRenameStructure(null)}
        currentName={renameStructure?.name || ''}
        title="Rename Structure"
        onRename={handleRenameStructure}
        isLoading={isRenaming}
      />
      
      <RenameDialog
        isOpen={!!renameWorkflow}
        onClose={() => setRenameWorkflow(null)}
        currentName={renameWorkflow?.name || ''}
        title="Rename Workflow"
        onRename={handleRenameWorkflow}
        isLoading={isRenaming}
      />
      
      {/* Delete Dialogs */}
      <DeleteConfirmDialog
        isOpen={!!deleteStructure}
        onClose={() => setDeleteStructure(null)}
        resourceName={deleteStructure?.name || ''}
        resourceType="Structure"
        warningMessage="This structure may be used by one or more workflows."
        onConfirm={handleDeleteStructure}
        isLoading={isDeleting}
        forceDeleteOption={true}
      />
      
      <DeleteConfirmDialog
        isOpen={!!deleteWorkflow}
        onClose={() => setDeleteWorkflow(null)}
        resourceName={deleteWorkflow?.name || ''}
        resourceType="Workflow"
        warningMessage="This will permanently delete the workflow and all its step files."
        onConfirm={handleDeleteWorkflow}
        isLoading={isDeleting}
        forceDeleteOption={false}
      />
    </>
  );
}

export default App;
