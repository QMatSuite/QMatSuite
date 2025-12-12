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
import { normalizeProjectRoot } from './utils/pathUtils';
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
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateWorkflowDialog,
  RenameDialog,
  DeleteConfirmDialog,
  JobsPanel,
  SettingsPanel,
  QEParameterBrowserPanel,
  ErrorBoundary,
} from './components';
import type { ViewType } from './components/layout/Sidebar';
import { useQVClient, useDaemonStatus } from './hooks';
import { useJobs } from './hooks/useJobs';
import type { 
  ProjectSummary, 
  StructureInfo, 
  WorkflowInfo,
  WorkflowDetailResult,
  StructureVisData,
  ScfConvergenceData,
  DosData,
  BandStructureData,
  QVResponse,
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
  
  // Home mode (welcome vs demo-gallery)
  type HomeMode = 'welcome' | 'demo-gallery';
  const [homeMode, setHomeMode] = useState<HomeMode>('welcome');
  
  // Project state
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [recommendedAnalysis, setRecommendedAnalysis] = useState<string | null>(null); // Used in handleCreateProjectSuccess
  
  // Data state
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  
  // CRITICAL: Separate workflow summary (from list_workflows) from workflow detail (from get_workflow_detail)
  // The detail's steps array is the canonical source of truth (built from workflow.yaml)
  const [selectedWorkflowSummary, setSelectedWorkflowSummary] = useState<WorkflowInfo | null>(null);
  const [selectedWorkflowDetail, setSelectedWorkflowDetail] = useState<WorkflowDetailResult | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  
  // Legacy alias for backwards compatibility (will be removed)
  const selectedWorkflow = selectedWorkflowDetail || selectedWorkflowSummary;
  const [structureVisData, setStructureVisData] = useState<StructureVisData | null>(null);
  
  // Debug state
  const [, setDebugResult] = useState<QVResponse | null>(null);
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
  
  // Job counts for sidebar badge (get from useJobs hook)
  const { counts: jobCounts } = useJobs({ autoStart: true, pollInterval: 5000 });
  
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
  // NOTE: Job counts are now polled by useJobs hook (used in JobsPanel)
  // and StatusBar. We don't need to poll here to avoid duplicate requests.
  // We'll get job counts from the JobsPanel when needed.
  
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
    // Clear selected workflow and step when opening a new project (fixes stale step selection)
    setSelectedWorkflowSummary(null);
    setSelectedWorkflowDetail(null);
    setSelectedStepId(null);
    setSelectedStructure(null);
    
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
      // Clear selected workflow and step when opening a new project (fixes stale step selection)
      setSelectedWorkflowSummary(null);
      setSelectedWorkflowDetail(null);
      setSelectedStepId(null);
      setSelectedStructure(null);
      
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
      
      // Clear selected workflow and step when opening a new project (fixes stale step selection)
      setSelectedWorkflowSummary(null);
      setSelectedWorkflowDetail(null);
      setSelectedStepId(null);
      setSelectedStructure(null);
      
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
          // Check for legacy_project error
        if (loadResponse.error?.code === 'legacy_project') {
          const migrationCmd = loadResponse.error?.details?.hint || loadResponse.error?.message || '';
          setProjectError(
            `This project uses a legacy workflow format. Please migrate it using:\n${migrationCmd}`
          );
        } else {
          setProjectError(loadResponse.error?.message || 'Failed to load created project');
        }
        }
      } else {
        setIsLoadingProject(false);
        // Check for legacy_project error
        if (createResponse.error?.code === 'legacy_project') {
          const migrationCmd = createResponse.error?.details?.hint || createResponse.error?.message || '';
          setProjectError(
            `This project uses a legacy workflow format. Please migrate it using:\n${migrationCmd}`
          );
        } else {
          setProjectError(createResponse.error?.message || 'Failed to create project');
        }
      }
    } else {
      setProjectError(null);
      setProjectRoot('');
      localStorage.removeItem('qv-project-root');
    }
  }, [qv, addToRecentProjects, showNotification]);
  
  const handleCreateProjectSuccess = useCallback(async (newProjectRoot: string, recommendedAnalysis?: string | null) => {
    // Clear selected workflow and step when opening a new project (fixes stale step selection)
    setSelectedWorkflowSummary(null);
    setSelectedWorkflowDetail(null);
    setSelectedStepId(null);
    setSelectedStructure(null);
    
    setRecommendedAnalysis(recommendedAnalysis || null);
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
      setSelectedWorkflowSummary(null);
      setSelectedWorkflowDetail(null);
      addToRecentProjects(newProjectRoot);
      
      // Set project path for log file storage
      window.qv?.setProject?.(newProjectRoot);
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
    }
  }, [qv, addToRecentProjects]);
  
  // Open demo gallery - can be triggered from sidebar or welcome screen
  const handleOpenDemoGallery = useCallback(() => {
    setHomeMode('demo-gallery');
    setCurrentView('home');
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
    if (!projectRoot || !projectLoaded) {
      console.log('[App] fetchStructures skipped', { projectRoot: !!projectRoot, projectLoaded });
      return;
    }
    
    console.log('[App] fetchStructures called', { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1), projectLoaded });
    setIsLoadingStructures(true);
    try {
      const response = await qv.listStructures(projectRoot);
      if (response.ok && response.data) {
        setStructures(response.data.structures);
      } else {
        // Check for registry_out_of_sync error
        if (response.error?.code === 'registry_out_of_sync') {
          setProjectError(
            response.error.message || 
            'Registry is out of sync. Click "Refresh" in the Structures panel to rebuild the project registry.'
          );
        }
      }
    } finally {
      setIsLoadingStructures(false);
    }
  }, [qv, projectRoot, projectLoaded]);
  
  const fetchWorkflows = useCallback(async () => {
    if (!projectRoot || !projectLoaded) {
      console.log('[App] fetchWorkflows skipped', { projectRoot: !!projectRoot, projectLoaded });
      return;
    }
    
    console.log('[App] fetchWorkflows called', { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1), projectLoaded });
    setIsLoadingWorkflows(true);
    try {
      const response = await qv.listWorkflows(projectRoot);
      if (response.ok && response.data) {
        setWorkflows(response.data.workflows);
      } else {
        // Check for registry_out_of_sync error
        if (response.error?.code === 'registry_out_of_sync') {
          setProjectError(
            response.error.message || 
            'Registry is out of sync. Click "Refresh" in the Workflows panel to rebuild the project registry.'
          );
        }
      }
    } finally {
      setIsLoadingWorkflows(false);
    }
  }, [qv, projectRoot, projectLoaded]);
  
  // Refresh project registry handler
  const handleRefreshProjectRegistry = useCallback(async () => {
    if (!projectRoot) {
      console.warn('[App] Refresh requested but no project root');
      return;
    }
    
    const normalized = normalizeProjectRoot(projectRoot);
    if (!normalized) {
      console.warn('[App] Cannot refresh: project root normalization failed');
      return;
    }
    console.log('[App] Refreshing project registry', { projectRoot: normalized });
    
    try {
      const response = await qv.rebuildProjectRegistry(normalized);
      
      if (response.ok && response.data) {
        const { index_stats, dag_diff } = response.data;
        console.log('[App] Registry refreshed', index_stats);
        
        // Build user-friendly message from DAG diff
        const diff = dag_diff;
        const hasChanges = 
          diff.structures_added.length > 0 ||
          diff.structures_removed.length > 0 ||
          diff.workflows_added.length > 0 ||
          diff.workflows_removed.length > 0 ||
          diff.workflows_changed.length > 0;
        
        let message = 'Registry refreshed. ';
        if (!hasChanges) {
          message += 'No DAG changes detected.';
        } else {
          const parts: string[] = [];
          
          if (diff.structures_added.length > 0 || diff.structures_removed.length > 0) {
            parts.push(`Structures: +${diff.structures_added.length}, -${diff.structures_removed.length}`);
          }
          
          if (diff.workflows_added.length > 0 || diff.workflows_removed.length > 0) {
            parts.push(`Workflows: +${diff.workflows_added.length}, -${diff.workflows_removed.length}`);
          }
          
          if (diff.workflows_changed.length > 0) {
            for (const wf of diff.workflows_changed) {
              const stepChanges: string[] = [];
              if (wf.steps_added.length > 0) {
                stepChanges.push(`+${wf.steps_added.length} step${wf.steps_added.length > 1 ? 's' : ''} (${wf.steps_added.map((s: { id: string; suffix: string }) => `…${s.suffix}`).join(', ')})`);
              }
              if (wf.steps_removed.length > 0) {
                stepChanges.push(`-${wf.steps_removed.length} step${wf.steps_removed.length > 1 ? 's' : ''} (${wf.steps_removed.map((s: { id: string; suffix: string }) => `…${s.suffix}`).join(', ')})`);
              }
              if (stepChanges.length > 0) {
                parts.push(`Workflow '${wf.workflow_name}': ${stepChanges.join(', ')}`);
              }
            }
          }
          
          message += parts.join('. ');
        }
        
        // Show notification (you can replace this with a toast system if you have one)
        console.log('[App]', message);
        
        // After registry is rebuilt, reload workflows / structures once
        await fetchStructures();
        await fetchWorkflows();
      } else {
        console.error('[App] Failed to refresh project registry', response.error);
        if (response.error?.code === 'project_not_found') {
          // Show visible error banner
          setProjectError(response.error.message || 'Project not found');
        }
      }
    } catch (err: any) {
      console.error('[App] Failed to refresh project registry', err);
      setProjectError(err.message || 'Failed to refresh project registry');
    }
  }, [projectRoot, qv, fetchStructures, fetchWorkflows]);
  
  // Auto-fetch data when switching views
  useEffect(() => {
    console.log('[App] view change effect triggered', { currentView, hasStructures: !!structures, hasWorkflows: !!workflows, projectLoaded });
    if (!projectLoaded) return;
    
    if (currentView === 'structures' && !structures) {
      fetchStructures();
    } else if (currentView === 'workflows' && !workflows) {
      fetchWorkflows();
    } else if (currentView === 'analysis' && !workflows) {
      fetchWorkflows();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentView, projectLoaded]); // Intentionally exclude structures/workflows/fetchStructures/fetchWorkflows to prevent loops
  
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
    console.log('[App] handleSelectWorkflow called', {
      workflowSlug: workflow.slug,
      workflowId: workflow.id,
      stepCount: workflow.steps?.length ?? 0,
    });
    
    // CRITICAL: Clear detail and step selection when switching workflows
    // We will fetch the detail separately, which has the canonical steps array from workflow.yaml
    setSelectedWorkflowSummary(workflow);
    setSelectedWorkflowDetail(null);
    setSelectedStepId(null);
    
    // Fire and forget async detail fetch
    // The detail's steps array is the ONLY source of truth for step order and IDs
    (async () => {
      if (!projectRoot || !window.qv) return;
      
      try {
        const normalizedRoot = normalizeProjectRoot(projectRoot);
        if (!normalizedRoot) return;
        
        console.log('[App] fetching workflow detail', {
          workflowSlug: workflow.slug,
          workflowId: workflow.id,
        });
        
        const response = await qv.call('get_workflow_detail', {
          project_root: normalizedRoot,
          workflow: workflow.slug ?? workflow.id,
        });
        
        if (response.ok && response.data) {
          const detail = response.data as WorkflowDetailResult;
          console.log('[App] got workflow detail', {
            workflowSlug: detail.slug,
            stepCount: detail.steps?.length ?? 0,
            stepIds: detail.steps?.map(s => s.id) ?? [],
            stepOrder: detail.steps?.map((s, i) => ({ index: i, id: s.id, type: s.type })) ?? [],
          });
          setSelectedWorkflowDetail(detail);
        } else {
          console.error('[App] get_workflow_detail error', response.error);
          // Check for registry_out_of_sync error
          if (response.error?.code === 'registry_out_of_sync') {
            setProjectError(
              response.error.message || 
              'Registry is out of sync. Click "Refresh" in the Workflows panel to rebuild the project registry.'
            );
          }
          setSelectedWorkflowDetail(null);
        }
      } catch (err) {
        console.error('[App] get_workflow_detail exception', err);
        setSelectedWorkflowDetail(null);
      }
    })();
  }, [projectRoot, qv]);
  
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
    
    // Normalize project_root to absolute path (backend expects normalized paths)
    // NOTE: Backend expects project_root as normalized absolute path, see tests/daemon/test_gui_job_and_step_flows.py
    const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedProjectRoot) {
      showNotification('Project root is required', 'error');
      return;
    }
    
    // Submit the workflow run
    // Backend contract: { project_root: string (normalized absolute), workflow: string (slug), strict?: bool, verbose?: bool }
    // GUI sends: workflow.slug (from selectedWorkflow.slug)
    // See tests/daemon/test_gui_job_and_step_flows.py for RPC contract details
    const response = await qv.call('run_workflow', {
      project_root: normalizedProjectRoot,
      workflow: workflow.slug, // Backend expects workflow selector (slug)
    });
    
    if (response.ok && response.data) {
      const result = response.data as JobSubmitResult;
      const shortId = result.job_id.slice(0, 8);
      showNotification(`Job #${shortId} started: ${result.target_name}`, 'success');
      
      // Job counts will be refreshed by StatusBar and JobsPanel polling
    } else {
      showNotification(`Failed to start job: ${response.error?.message || 'Unknown error'}`, 'error');
    }
    
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot, showNotification]);
  
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
      handleSelectWorkflow(wf);
    }
  }, [workflows, fetchWorkflows]);
  
  const handleSelectStep = useCallback((stepId: string) => {
    console.log('[App] handleSelectStep called with:', stepId);
    setSelectedStepId(stepId);
  }, []);
  
  const handleDeleteStep = useCallback(async (stepId: string) => {
    console.log('[App] handleDeleteStep called with:', stepId);
    // Clear selection if the deleted step was selected
    if (selectedStepId === stepId) {
      setSelectedStepId(null);
    }
    // Refresh workflow detail to show updated steps list
    if (selectedWorkflowSummary) {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (normalizedRoot && window.qv) {
        const response = await qv.call('get_workflow_detail', {
          project_root: normalizedRoot,
          workflow: selectedWorkflowSummary.slug,
        });
        if (response.ok && response.data) {
          const updatedDetail = response.data as WorkflowDetailResult;
          setSelectedWorkflowDetail(updatedDetail);
        }
      }
    }
  }, [selectedStepId, selectedWorkflowSummary, projectRoot, qv]);
  
  const handleRunStepSuccess = useCallback((result: JobSubmitResult) => {
    const shortId = result.job_id.slice(0, 8);
    showNotification(`Step job #${shortId} started: ${result.target_name}`, 'success');
    // Job counts will be refreshed by StatusBar and JobsPanel polling
  }, [showNotification]);
  
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
        setSelectedWorkflowSummary(null);
        setSelectedWorkflowDetail(null);
        setSelectedStepId(null);
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
        setSelectedWorkflowSummary(null);
        setSelectedWorkflowDetail(null);
        setSelectedStepId(null);
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
    // Clear all state to prevent stale data
    setProjectRoot('');
    setProjectSummary(null);
    setProjectLoaded(false);
    setProjectError(null);
    setStructures(null);
    setWorkflows(null);
    setSelectedStructure(null);
    setSelectedWorkflowSummary(null);
    setSelectedWorkflowDetail(null);
    setSelectedStepId(null); // Clear step selection
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
            homeMode={homeMode}
            onHomeModeChange={setHomeMode}
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => setShowCreateProject(true)}
            onOpenDemoGallery={handleOpenDemoGallery}
            onOpenRecentProject={handleOpenRecentProject}
            onRemoveRecentProject={removeFromRecentProjects}
            onNavigateToStructure={handleNavigateToStructure}
            onNavigateToWorkflow={handleNavigateToWorkflow}
            onCloseProject={handleCloseProject}
            onProjectCreated={handleCreateProjectSuccess}
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
                onRefreshProjectRegistry={handleRefreshProjectRegistry}
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
                onRefreshProjectRegistry={handleRefreshProjectRegistry}
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
                        workflowSummary={selectedWorkflowSummary}
                        workflowDetail={selectedWorkflowDetail}
                        projectRoot={projectRoot}
                        structures={structures || undefined}
                        onClose={() => {
                          setSelectedWorkflowSummary(null);
                          setSelectedWorkflowDetail(null);
                          setSelectedStepId(null);
                        }}
                        onRunWorkflow={handleRunWorkflow}
                        onSelectStep={handleSelectStep}
                        onDeleteStep={handleDeleteStep}
                        onGoToJobs={handleGoToJobs}
                        onWorkflowUpdated={async () => {
                          // CRITICAL: After adding a step, refresh workflow detail to show the new step
                          // This ensures the step list updates immediately without needing to reopen the project
                          console.log('[App] onWorkflowUpdated: refreshing workflow detail after step creation');
                          
                          // Refresh workflows list to get updated step counts
                          await fetchWorkflows();
                          
                          // Also refresh the selected workflow detail if it exists
                          // This updates selectedWorkflowDetail.steps with the new step entry
                          if (selectedWorkflowSummary) {
                            const response = await qv.call('get_workflow_detail', {
                              project_root: projectRoot,
                              workflow: selectedWorkflowSummary.slug,
                            });
                            if (response.ok && response.data) {
                              // Update selectedWorkflowDetail with fresh data including new steps
                              const updatedDetail = response.data as WorkflowDetailResult;
                              console.log('[App] Workflow detail refreshed', {
                                workflowSlug: updatedDetail.slug,
                                stepCount: updatedDetail.steps.length,
                                stepIds: updatedDetail.steps.map(s => s.id),
                                stepOrder: updatedDetail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                              });
                              setSelectedWorkflowDetail(updatedDetail);
                            } else {
                              console.error('[App] Failed to refresh workflow detail', response.error);
                            }
                          }
                        }}
                        onWorkflowDetailUpdated={(detail) => {
                          // CRITICAL: Directly update workflowDetail from reorder_workflow_steps response
                          // This ensures UI reflects the new step order immediately without re-fetching
                          console.log('[App] Workflow detail updated from reorder', {
                            workflowSlug: detail.slug,
                            stepCount: detail.steps.length,
                            stepOrder: detail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                          });
                          setSelectedWorkflowDetail(detail);
                        }}
                      />
                    </VerticalResizablePane>
                    <StepDetailPanel
                      projectRoot={projectRoot}
                      selectedWorkflow={selectedWorkflowDetail}
                      selectedStepId={selectedStepId}
                      onClose={() => setSelectedStepId(null)}
                      onRunStep={handleRunStepSuccess}
                      onStepDeleted={handleDeleteStep}
                    />
                  </>
                ) : (
                  <WorkflowDetailPanel
                    workflowSummary={selectedWorkflowSummary}
                    workflowDetail={selectedWorkflowDetail}
                    projectRoot={projectRoot}
                    structures={structures || undefined}
                    onClose={() => {
                      setSelectedWorkflowSummary(null);
                      setSelectedWorkflowDetail(null);
                      setSelectedStepId(null);
                    }}
                    onRunWorkflow={handleRunWorkflow}
                    onSelectStep={handleSelectStep}
                    onDeleteStep={handleDeleteStep}
                    onGoToJobs={handleGoToJobs}
                    onWorkflowUpdated={fetchWorkflows}
                    onWorkflowDetailUpdated={(detail) => {
                      // CRITICAL: Directly update workflowDetail from reorder_workflow_steps response
                      // This ensures UI reflects the new step order immediately without re-fetching
                      console.log('[App] Workflow detail updated from reorder', {
                        workflowSlug: detail.slug,
                        stepCount: detail.steps.length,
                        stepOrder: detail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                      });
                      setSelectedWorkflowDetail(detail);
                    }}
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
            selectedWorkflow={selectedWorkflowSummary}
            projectRoot={projectRoot}
            onSelectWorkflow={handleSelectWorkflow}
            onLoadScf={handleLoadScf}
            onLoadDos={handleLoadDos}
            onLoadBands={handleLoadBands}
            autoAnalysis={appSettings.autoAnalysis}
            defaultAnalysis={recommendedAnalysis}
          />
        );
        
      case 'resources':
        return <QEParameterBrowserPanel />;
        
      case 'settings':
        return (
          <SettingsPanel 
            settings={appSettings}
            onSettingsChange={setAppSettings}
          />
        );
        
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
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => setShowCreateProject(true)}
            onOpenDemoGallery={handleOpenDemoGallery}
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
              {currentView === 'resources' && 'Resources'}
              {currentView === 'settings' && 'Settings'}
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
