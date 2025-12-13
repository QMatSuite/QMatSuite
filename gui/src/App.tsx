/**
 * QuantumVITAS GUI - Main Application Component
 * 
 * Provides the main application layout with:
 * - Sidebar for navigation and actions
 * - Main panel with structured views
 * - Auto-fetching data on view change
 * - Dialogs for project/structure/calculation creation
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
  CalculationListPanel,
  CalculationDetailPanel,
  StepDetailPanel,
  StructureViewer3D,
  AnalysisPanel,
  DebugPanel,
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateCalculationDialog,
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
  CalculationInfo,
  CalculationDetailResult,
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
  const [calculations, setCalculations] = useState<CalculationInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  
  // CRITICAL: Separate calculation summary (from list_calculations) from calculation detail (from get_calculation_detail)
  // The detail's steps array is the canonical source of truth (built from calculation.yaml)
  const [selectedCalculationSummary, setSelectedCalculationSummary] = useState<CalculationInfo | null>(null);
  const [selectedCalculationDetail, setSelectedCalculationDetail] = useState<CalculationDetailResult | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  
  // Auto-select refs for Structures and Calculations (mirror JobsPanel pattern)
  const didAutoSelectStructureRef = useRef(false);
  const didAutoSelectCalculationRef = useRef(false);
  
  // Legacy alias for backwards compatibility (will be removed)
  const selectedCalculation = selectedCalculationDetail || selectedCalculationSummary;
  const [structureVisData, setStructureVisData] = useState<StructureVisData | null>(null);
  
  // Debug state
  const [, setDebugResult] = useState<QVResponse | null>(null);
  const [showDebugFooter, setShowDebugFooter] = useState(true);
  
  // Loading states
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  const [isLoadingCalculations, setIsLoadingCalculations] = useState(false);
  const [isLoading3D, setIsLoading3D] = useState(false);
  
  // Dialog states
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [showCreateDemoProject, setShowCreateDemoProject] = useState(false);
  const [showImportStructure, setShowImportStructure] = useState(false);
  const [showCreateCalculation, setShowCreateCalculation] = useState(false);
  
  // Rename/delete dialog states
  const [renameStructure, setRenameStructure] = useState<StructureInfo | null>(null);
  const [deleteStructure, setDeleteStructure] = useState<StructureInfo | null>(null);
  const [renameCalculation, setRenameCalculation] = useState<CalculationInfo | null>(null);
  const [deleteCalculation, setDeleteCalculation] = useState<CalculationInfo | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Job counts for sidebar badge (get from useJobs hook)
  // Poll at slower rate since JobsPanel (when open) polls more frequently
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
    // Clear selected calculation and step when opening a new project (fixes stale step selection)
    setSelectedCalculationSummary(null);
    setSelectedCalculationDetail(null);
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
      setCalculations(null);
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
      // Clear selected calculation and step when opening a new project (fixes stale step selection)
      setSelectedCalculationSummary(null);
      setSelectedCalculationDetail(null);
      setSelectedStepId(null);
      setSelectedStructure(null);
      
      setProjectRoot(selectedPath);
      localStorage.setItem('qv-project-root', selectedPath);
      setProjectSummary(directResponse.data);
      setProjectLoaded(true);
      setStructures(null);
      setCalculations(null);
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
      
      // Clear selected calculation and step when opening a new project (fixes stale step selection)
      setSelectedCalculationSummary(null);
      setSelectedCalculationDetail(null);
      setSelectedStepId(null);
      setSelectedStructure(null);
      
      setProjectRoot(projectPath);
      localStorage.setItem('qv-project-root', projectPath);
      
      const parentResponse = await qv.getProjectSummary(projectPath);
      
      if (parentResponse.ok && parentResponse.data) {
        setProjectSummary(parentResponse.data);
        setProjectLoaded(true);
        setStructures(null);
        setCalculations(null);
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
          setCalculations(null);
          addToRecentProjects(selectedPath);
          showNotification('Project created successfully!', 'success');
          window.qv?.setProject?.(selectedPath);
        } else {
          // Check for legacy_project error
        if (loadResponse.error?.code === 'legacy_project') {
          const migrationCmd = loadResponse.error?.details?.hint || loadResponse.error?.message || '';
          setProjectError(
            `This project uses a legacy calculation format. Please migrate it using:\n${migrationCmd}`
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
            `This project uses a legacy calculation format. Please migrate it using:\n${migrationCmd}`
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
    // Clear selected calculation and step when opening a new project (fixes stale step selection)
    setSelectedCalculationSummary(null);
    setSelectedCalculationDetail(null);
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
      setCalculations(null);
      setSelectedStructure(null);
      setSelectedCalculationSummary(null);
      setSelectedCalculationDetail(null);
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
  
  // Refresh project summary (after adding/deleting structures/calculations)
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
  
  const fetchCalculations = useCallback(async () => {
    if (!projectRoot || !projectLoaded) {
      console.log('[App] fetchCalculations skipped', { projectRoot: !!projectRoot, projectLoaded });
      return;
    }
    
    console.log('[App] fetchCalculations called', { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1), projectLoaded });
    setIsLoadingCalculations(true);
    try {
      const response = await qv.listCalculations(projectRoot);
      if (response.ok && response.data) {
        const calculationsList = response.data.calculations;
        setCalculations(calculationsList);
        // Return the calculations list so callers can use it immediately
        return calculationsList;
      } else {
        // Check for registry_out_of_sync error
        if (response.error?.code === 'registry_out_of_sync') {
          setProjectError(
            response.error.message || 
            'Registry is out of sync. Click "Refresh" in the Calculations panel to rebuild the project registry.'
          );
        }
        return null;
      }
    } finally {
      setIsLoadingCalculations(false);
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
          diff.calculations_added.length > 0 ||
          diff.calculations_removed.length > 0 ||
          diff.calculations_changed.length > 0;
        
        let message = 'Registry refreshed. ';
        if (!hasChanges) {
          message += 'No DAG changes detected.';
        } else {
          const parts: string[] = [];
          
          if (diff.structures_added.length > 0 || diff.structures_removed.length > 0) {
            parts.push(`Structures: +${diff.structures_added.length}, -${diff.structures_removed.length}`);
          }
          
          if (diff.calculations_added.length > 0 || diff.calculations_removed.length > 0) {
            parts.push(`Calculations: +${diff.calculations_added.length}, -${diff.calculations_removed.length}`);
          }
          
          if (diff.calculations_changed.length > 0) {
            for (const wf of diff.calculations_changed) {
              const stepChanges: string[] = [];
              if (wf.steps_added.length > 0) {
                stepChanges.push(`+${wf.steps_added.length} step${wf.steps_added.length > 1 ? 's' : ''} (${wf.steps_added.map((s: { id: string; suffix: string }) => `…${s.suffix}`).join(', ')})`);
              }
              if (wf.steps_removed.length > 0) {
                stepChanges.push(`-${wf.steps_removed.length} step${wf.steps_removed.length > 1 ? 's' : ''} (${wf.steps_removed.map((s: { id: string; suffix: string }) => `…${s.suffix}`).join(', ')})`);
              }
              if (stepChanges.length > 0) {
                parts.push(`Calculation '${wf.calculation_name}': ${stepChanges.join(', ')}`);
              }
            }
          }
          
          message += parts.join('. ');
        }
        
        // Show notification (you can replace this with a toast system if you have one)
        console.log('[App]', message);
        
        // After registry is rebuilt, reload calculations / structures once
        await fetchStructures();
        await fetchCalculations();
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
  }, [projectRoot, qv, fetchStructures, fetchCalculations]);
  
  // Auto-fetch data when switching views
  useEffect(() => {
    console.log('[App] view change effect triggered', { currentView, hasStructures: !!structures, hasCalculations: !!calculations, projectLoaded });
    if (!projectLoaded) return;
    
    if (currentView === 'structures' && !structures) {
      fetchStructures();
    } else if (currentView === 'calculations' && !calculations) {
      fetchCalculations();
    } else if (currentView === 'analysis' && !calculations) {
      fetchCalculations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentView, projectLoaded]); // Intentionally exclude structures/calculations/fetchStructures/fetchCalculations to prevent loops
  
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
    // Mark that user has manually selected (prevent auto-select override)
    didAutoSelectStructureRef.current = true;
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
  // Calculation Handling
  // ==========================================================================
  
  const handleSelectCalculation = useCallback((calculation: CalculationInfo) => {
    console.log('[App] handleSelectCalculation called', {
      calculationSlug: calculation.slug,
      calculationId: calculation.id,
      stepCount: calculation.steps?.length ?? 0,
    });
    
    // CRITICAL: Clear detail and step selection when switching calculations
    // We will fetch the detail separately, which has the canonical steps array from calculation.yaml
    setSelectedCalculationSummary(calculation);
    // Mark that user has manually selected (prevent auto-select override)
    didAutoSelectCalculationRef.current = true;
    setSelectedCalculationDetail(null);
    setSelectedStepId(null);
    
    // Fire and forget async detail fetch
    // The detail's steps array is the ONLY source of truth for step order and IDs
    (async () => {
      if (!projectRoot || !window.qv) return;
      
      try {
        const normalizedRoot = normalizeProjectRoot(projectRoot);
        if (!normalizedRoot) return;
        
        console.log('[App] fetching calculation detail', {
          calculationSlug: calculation.slug,
          calculationId: calculation.id,
        });
        
        const response = await qv.call('get_calculation_detail', {
          project_root: normalizedRoot,
          calculation: calculation.slug ?? calculation.id,
        });
        
        if (response.ok && response.data) {
          const detail = response.data as CalculationDetailResult;
          console.log('[App] got calculation detail', {
            calculationSlug: detail.slug,
            stepCount: detail.steps?.length ?? 0,
            stepIds: detail.steps?.map(s => s.id) ?? [],
            stepOrder: detail.steps?.map((s, i) => ({ index: i, id: s.id, type: s.type })) ?? [],
          });
          setSelectedCalculationDetail(detail);
        } else {
          console.error('[App] get_calculation_detail error', response.error);
          // Check for registry_out_of_sync error
          if (response.error?.code === 'registry_out_of_sync') {
            setProjectError(
              response.error.message || 
              'Registry is out of sync. Click "Refresh" in the Calculations panel to rebuild the project registry.'
            );
          } else if (response.error?.code === 'resource_not_found' && response.error?.kind === 'calculation') {
            // Calculation not found - this can happen right after creation if registry hasn't synced yet
            // Don't show error immediately, wait a bit and retry
            console.warn('[App] Calculation not found, will retry after delay', { calculationSlug: calculation.slug });
            setTimeout(async () => {
              // Retry once after a short delay
              const retryResponse = await qv.call('get_calculation_detail', {
                project_root: normalizedRoot,
                calculation: calculation.slug ?? calculation.id,
              });
              if (retryResponse.ok && retryResponse.data) {
                setSelectedCalculationDetail(retryResponse.data as CalculationDetailResult);
              }
            }, 500);
          }
          // Don't set detail to null immediately - keep summary visible while retrying
        }
      } catch (err) {
        console.error('[App] get_calculation_detail exception', err);
        setSelectedCalculationDetail(null);
      }
    })();
  }, [projectRoot, qv]);
  
  // Reset auto-select flags when switching views or project changes
  useEffect(() => {
    if (currentView !== 'structures') {
      didAutoSelectStructureRef.current = false;
    }
    if (currentView !== 'calculations') {
      didAutoSelectCalculationRef.current = false;
    }
  }, [currentView]);
  
  // Auto-select first structure when entering structures view (mirror JobsPanel pattern)
  useEffect(() => {
    // Only auto-select if:
    // 1. We're in structures view
    // 2. Structures list is non-empty
    // 3. No structure is currently selected
    // 4. We haven't auto-selected yet (one-time per mount)
    if (currentView === 'structures' && structures && structures.length > 0 && !selectedStructure && !didAutoSelectStructureRef.current) {
      // Use the structure from the list to ensure ID consistency
      const firstStructure = structures[0];
      setSelectedStructure(firstStructure);
      didAutoSelectStructureRef.current = true;
    }
    
    // If selected structure disappeared from list, fall back to first element
    // Also sync selectedStructure with list if ID matches but object reference differs
    if (selectedStructure && structures) {
      const foundInList = structures.find(s => s.id === selectedStructure.id);
      if (!foundInList) {
        // Structure disappeared, fall back to first
        if (structures.length > 0) {
          setSelectedStructure(structures[0]);
        } else {
          setSelectedStructure(null);
        }
      } else if (foundInList !== selectedStructure) {
        // Structure exists but object reference differs - sync to ensure consistency
        setSelectedStructure(foundInList);
      }
    }
  }, [currentView, structures, selectedStructure]);
  
  // Load 3D view when selectedStructure changes in structures view
  // This ensures 3D view loads for both auto-selected and manually selected structures
  useEffect(() => {
    if (currentView === 'structures' && selectedStructure && projectRoot && qv) {
      // Check if we already have data for this structure ID
      // Compare by ID to avoid unnecessary reloads
      const currentStructureId = structureVisData?.structure_id;
      const needsLoad = !currentStructureId || currentStructureId !== selectedStructure.id;
      
      if (needsLoad) {
        // Load 3D view data - this will update structureVisData when complete
        loadStructureVis(selectedStructure, currentSupercell, currentRepeatBoundary).catch(err => {
          console.error('[App] Failed to load structure 3D view', err);
        });
      }
    } else if (currentView !== 'structures' && structureVisData) {
      // Clear 3D data when leaving structures view
      setStructureVisData(null);
    }
  }, [currentView, selectedStructure?.id, projectRoot, qv, structureVisData?.structure_id, currentSupercell, currentRepeatBoundary, loadStructureVis]);
  
  // Auto-select first calculation when entering calculations view (mirror JobsPanel pattern)
  useEffect(() => {
    // Only auto-select if:
    // 1. We're in calculations view
    // 2. Calculations list is non-empty
    // 3. No calculation is currently selected
    // 4. We haven't auto-selected yet (one-time per mount)
    if (currentView === 'calculations' && calculations && calculations.length > 0 && !selectedCalculationSummary && !didAutoSelectCalculationRef.current) {
      const firstCalculation = calculations[0];
      didAutoSelectCalculationRef.current = true;
      // Use handleSelectCalculation to set state and trigger detail fetch
      handleSelectCalculation(firstCalculation);
    }
    
    // If selected calculation disappeared from list, fall back to first element
    if (selectedCalculationSummary && calculations && !calculations.find(w => w.id === selectedCalculationSummary.id)) {
      if (calculations.length > 0) {
        const firstCalculation = calculations[0];
        handleSelectCalculation(firstCalculation);
      } else {
        setSelectedCalculationSummary(null);
        setSelectedCalculationDetail(null);
      }
    }
  }, [currentView, calculations, selectedCalculationSummary, handleSelectCalculation]);
  
  const handleCreateCalculationSuccess = useCallback(async (calculationId: string) => {
    // Refresh calculations list and summary
    await refreshSummary();
    const calculationsList = await fetchCalculations();
    
    // CRITICAL: Wait for calculations list to update before selecting
    // Find the newly created calculation by ID from the fresh list
    let newWf = calculationsList?.find(w => w.id === calculationId);
    
    // If not found immediately, wait a bit for registry to update (max 3 retries)
    if (!newWf) {
      for (let i = 0; i < 3; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        const retryList = await fetchCalculations();
        newWf = retryList?.find(w => w.id === calculationId);
        if (newWf) break;
      }
    }
    
    if (newWf) {
      // Select the calculation - this will trigger get_calculation_detail
      // The calculation is now in the list, so get_calculation_detail should succeed
      handleSelectCalculation(newWf);
    } else {
      console.error('[App] Created calculation not found after refresh', { calculationId });
      // Don't show error - calculation might still be syncing, user can manually select it
    }
  }, [fetchCalculations, refreshSummary, handleSelectCalculation]);
  
  const handleRunCalculation = useCallback(async (calculation: CalculationInfo) => {
    // Perform preflight checks first
    const preflightResponse = await qv.call('preflight_check', {
      project_root: projectRoot,
      calculation: calculation.slug,
    });
    
    if (preflightResponse.ok && preflightResponse.data) {
      const preflight = preflightResponse.data as PreflightCheckResult;
      
      if (!preflight.ok) {
        // Show preflight errors
        const errorMsg = preflight.errors.join('; ') || 'Pre-flight check failed';
        showNotification(`Cannot run calculation: ${errorMsg}`, 'error');
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
    
    // Submit the calculation run
    // Backend contract: { project_root: string (normalized absolute), calculation: string (slug), strict?: bool, verbose?: bool }
    // GUI sends: calculation.slug (from selectedCalculation.slug)
    // See tests/daemon/test_gui_job_and_step_flows.py for RPC contract details
    const response = await qv.call('run_calculation', {
      project_root: normalizedProjectRoot,
      calculation: calculation.slug, // Backend expects calculation selector (slug)
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
  const handleViewAnalysisFromJob = useCallback(async (calculationSlug: string) => {
    // Switch to analysis view
    setCurrentView('analysis');
    
    // If calculations aren't loaded, fetch them first
    if (!calculations) {
      await fetchCalculations();
    }
    
    // Try to find and select the calculation
    const wf = calculations?.find(w => w.slug === calculationSlug || w.name === calculationSlug);
    if (wf) {
      handleSelectCalculation(wf);
    }
  }, [calculations, fetchCalculations]);
  
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
    // Refresh calculation detail to show updated steps list
    if (selectedCalculationSummary) {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (normalizedRoot && window.qv) {
        const response = await qv.call('get_calculation_detail', {
          project_root: normalizedRoot,
          calculation: selectedCalculationSummary.slug,
        });
        if (response.ok && response.data) {
          const updatedDetail = response.data as CalculationDetailResult;
          setSelectedCalculationDetail(updatedDetail);
        }
      }
    }
  }, [selectedStepId, selectedCalculationSummary, projectRoot, qv]);
  
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
  // Calculation Rename/Delete
  // ==========================================================================
  
  const handleRenameCalculation = useCallback(async (newName: string): Promise<boolean> => {
    if (!renameCalculation) return false;
    
    setIsRenaming(true);
    const response = await qv.call('rename_calculation', {
      project_root: projectRoot,
      selector: renameCalculation.slug,
      new_name: newName,
    });
    setIsRenaming(false);
    
    if (response.ok) {
      showNotification(`Renamed calculation to "${newName}"`, 'success');
      await fetchCalculations();
      // Update selected calculation if it was the one being renamed
      if (selectedCalculation?.id === renameCalculation.id) {
        setSelectedCalculationSummary(null);
        setSelectedCalculationDetail(null);
        setSelectedStepId(null);
      }
      return true;
    } else {
      showNotification(`Failed to rename: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, renameCalculation, fetchCalculations, selectedCalculation, showNotification]);
  
  const handleDeleteCalculation = useCallback(async (force: boolean): Promise<boolean> => {
    if (!deleteCalculation) return false;
    
    setIsDeleting(true);
    const response = await qv.call('delete_calculation', {
      project_root: projectRoot,
      selector: deleteCalculation.slug,
      force: force,
    });
    setIsDeleting(false);
    
    if (response.ok) {
      showNotification(`Deleted calculation "${deleteCalculation.name}"`, 'success');
      await fetchCalculations();
      await refreshSummary();
      // Clear selection if the deleted calculation was selected
      if (selectedCalculation?.id === deleteCalculation.id) {
        setSelectedCalculationSummary(null);
        setSelectedCalculationDetail(null);
        setSelectedStepId(null);
      }
      return true;
    } else {
      showNotification(`Failed to delete: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qv, projectRoot, deleteCalculation, fetchCalculations, refreshSummary, selectedCalculation, showNotification]);
  
  // ==========================================================================
  // Analysis Data Loading
  // ==========================================================================
  
  const handleLoadScf = useCallback(async (calculation: CalculationInfo, step: string): Promise<ScfConvergenceData | null> => {
    const response = await qv.call('get_scf_convergence', {
      project_root: projectRoot,
      calculation: calculation.slug,
      step: step,
    });
    return response.ok ? response.data as ScfConvergenceData : null;
  }, [qv, projectRoot]);
  
  const handleLoadDos = useCallback(async (calculation: CalculationInfo): Promise<DosData | null> => {
    const response = await qv.call('get_dos_data', {
      project_root: projectRoot,
      calculation: calculation.slug,
    });
    return response.ok ? response.data as DosData : null;
  }, [qv, projectRoot]);
  
  const handleLoadBands = useCallback(async (calculation: CalculationInfo): Promise<BandStructureData | null> => {
    const response = await qv.call('get_band_structure_data', {
      project_root: projectRoot,
      calculation: calculation.slug,
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
  
  // Navigate to a specific calculation
  const handleNavigateToCalculation = useCallback(async (calculationName: string) => {
    setCurrentView('calculations');
    
    // If no specific calculation requested, just switch view
    if (!calculationName) return;
    
    // After switching view, try to select the calculation
    // First ensure calculations are loaded
    let currentCalculations = calculations;
    if (!currentCalculations) {
      setIsLoadingCalculations(true);
      const response = await qv.listCalculations(projectRoot);
      setIsLoadingCalculations(false);
      if (response.ok && response.data) {
        currentCalculations = response.data.calculations;
        setCalculations(currentCalculations);
      }
    }
    
    if (currentCalculations) {
      const wf = currentCalculations.find(w => w.name === calculationName || w.slug === calculationName);
      if (wf) {
        handleSelectCalculation(wf);
      }
    }
  }, [calculations, handleSelectCalculation, qv, projectRoot]);
  
  // Close the current project
  const handleCloseProject = useCallback(() => {
    // Clear all state to prevent stale data
    setProjectRoot('');
    setProjectSummary(null);
    setProjectLoaded(false);
    setProjectError(null);
    setStructures(null);
    setCalculations(null);
    setSelectedStructure(null);
    setSelectedCalculationSummary(null);
    setSelectedCalculationDetail(null);
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
            onNavigateToCalculation={handleNavigateToCalculation}
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
        
      case 'calculations':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <div className="calculations-view">
            <ResizablePane
              defaultWidth={420}
              minWidth={320}
              maxWidth={600}
              storageKey="qv-calculations-list-width"
              className="calculations-view__list"
            >
              <CalculationListPanel
                onRefreshProjectRegistry={handleRefreshProjectRegistry}
                calculations={calculations}
                isLoading={isLoadingCalculations}
                selectedId={selectedCalculation?.id}
                onSelect={handleSelectCalculation}
                onRename={setRenameCalculation}
                onDelete={setDeleteCalculation}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowCreateCalculation(true)}
              >
                ➕ New Calculation
              </button>
            </ResizablePane>
            {selectedCalculation && (
              <div className="calculations-view__detail">
                {selectedStepId ? (
                  <>
                    <VerticalResizablePane
                      defaultHeight={350}
                      minHeight={200}
                      maxHeight={500}
                      storageKey="qv-calculation-detail-height"
                      className="calculation-detail-resizable"
                    >
                      <CalculationDetailPanel
                        calculationSummary={selectedCalculationSummary}
                        calculationDetail={selectedCalculationDetail}
                        projectRoot={projectRoot}
                        structures={structures || undefined}
                        onClose={() => {
                          setSelectedCalculationSummary(null);
                          setSelectedCalculationDetail(null);
                          setSelectedStepId(null);
                        }}
                        onRunCalculation={handleRunCalculation}
                        onSelectStep={handleSelectStep}
                        onDeleteStep={handleDeleteStep}
                        onGoToJobs={handleGoToJobs}
                        onCalculationUpdated={async () => {
                          // CRITICAL: After adding a step, refresh calculation detail to show the new step
                          // This ensures the step list updates immediately without needing to reopen the project
                          console.log('[App] onCalculationUpdated: refreshing calculation detail after step creation');
                          
                          // Refresh calculations list to get updated step counts
                          await fetchCalculations();
                          
                          // Also refresh the selected calculation detail if it exists
                          // This updates selectedCalculationDetail.steps with the new step entry
                          if (selectedCalculationSummary) {
                            const response = await qv.call('get_calculation_detail', {
                              project_root: projectRoot,
                              calculation: selectedCalculationSummary.slug,
                            });
                            if (response.ok && response.data) {
                              // Update selectedCalculationDetail with fresh data including new steps
                              const updatedDetail = response.data as CalculationDetailResult;
                              console.log('[App] Calculation detail refreshed', {
                                calculationSlug: updatedDetail.slug,
                                stepCount: updatedDetail.steps.length,
                                stepIds: updatedDetail.steps.map(s => s.id),
                                stepOrder: updatedDetail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                              });
                              setSelectedCalculationDetail(updatedDetail);
                            } else {
                              console.error('[App] Failed to refresh calculation detail', response.error);
                            }
                          }
                        }}
                        onCalculationDetailUpdated={(detail) => {
                          // CRITICAL: Directly update calculationDetail from reorder_calculation_steps response
                          // This ensures UI reflects the new step order immediately without re-fetching
                          console.log('[App] Calculation detail updated from reorder', {
                            calculationSlug: detail.slug,
                            stepCount: detail.steps.length,
                            stepOrder: detail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                          });
                          setSelectedCalculationDetail(detail);
                        }}
                      />
                    </VerticalResizablePane>
                    <StepDetailPanel
                      projectRoot={projectRoot}
                      selectedCalculation={selectedCalculationDetail}
                      selectedStepId={selectedStepId}
                      onClose={() => setSelectedStepId(null)}
                      onRunStep={handleRunStepSuccess}
                      onStepDeleted={handleDeleteStep}
                    />
                  </>
                ) : (
                  <CalculationDetailPanel
                    calculationSummary={selectedCalculationSummary}
                    calculationDetail={selectedCalculationDetail}
                    projectRoot={projectRoot}
                    structures={structures || undefined}
                    onClose={() => {
                      setSelectedCalculationSummary(null);
                      setSelectedCalculationDetail(null);
                      setSelectedStepId(null);
                    }}
                    onRunCalculation={handleRunCalculation}
                    onSelectStep={handleSelectStep}
                    onDeleteStep={handleDeleteStep}
                    onGoToJobs={handleGoToJobs}
                    onCalculationUpdated={fetchCalculations}
                    onCalculationDetailUpdated={(detail) => {
                      // CRITICAL: Directly update calculationDetail from reorder_calculation_steps response
                      // This ensures UI reflects the new step order immediately without re-fetching
                      console.log('[App] Calculation detail updated from reorder', {
                        calculationSlug: detail.slug,
                        stepCount: detail.steps.length,
                        stepOrder: detail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                      });
                      setSelectedCalculationDetail(detail);
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
            calculations={calculations}
            selectedCalculation={selectedCalculationSummary}
            projectRoot={projectRoot}
            onSelectCalculation={handleSelectCalculation}
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
              {currentView === 'calculations' && 'Calculations'}
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
      
      <CreateCalculationDialog
        isOpen={showCreateCalculation}
        projectRoot={projectRoot}
        structures={structures || []}
        onClose={() => setShowCreateCalculation(false)}
        onSuccess={handleCreateCalculationSuccess}
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
        isOpen={!!renameCalculation}
        onClose={() => setRenameCalculation(null)}
        currentName={renameCalculation?.name || ''}
        title="Rename Calculation"
        onRename={handleRenameCalculation}
        isLoading={isRenaming}
      />
      
      {/* Delete Dialogs */}
      <DeleteConfirmDialog
        isOpen={!!deleteStructure}
        onClose={() => setDeleteStructure(null)}
        resourceName={deleteStructure?.name || ''}
        resourceType="Structure"
        warningMessage="This structure may be used by one or more calculations."
        onConfirm={handleDeleteStructure}
        isLoading={isDeleting}
        forceDeleteOption={true}
      />
      
      <DeleteConfirmDialog
        isOpen={!!deleteCalculation}
        onClose={() => setDeleteCalculation(null)}
        resourceName={deleteCalculation?.name || ''}
        resourceType="Calculation"
        warningMessage="This will permanently delete the calculation and all its step files."
        onConfirm={handleDeleteCalculation}
        isLoading={isDeleting}
        forceDeleteOption={false}
      />
    </>
  );
}

export default App;
