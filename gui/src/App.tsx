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
  type ResizablePaneRef,
  ResizableSplitPane,
  ProjectSummaryPanel, 
  StructureListPanel,
  StructureDetailPanel,
  CalculationListPanel,
  StructureViewer3D,
  DebugPanel,
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateCalculationDialog,
  RenameDialog,
  DeleteConfirmDialog,
  JobsPanel,
  SettingsPanel,
  HistoryPanel,
  QEParameterBrowserPanel,
  ErrorBoundary,
  CalculationOverviewTab,
  CalculationRunTab,
  CalculationAnalysisTab,
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
  StructureModel,
  RightSelection,
  Provenance,
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
  
  // Data state
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [calculations, setCalculations] = useState<CalculationInfo[] | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  
  // Calculations pane collapse state (for syncing ResizablePane width)
  const calculationsPaneRef = useRef<ResizablePaneRef>(null);
  
  const handleToggleCalculationsPane = useCallback(() => {
    calculationsPaneRef.current?.toggle();
  }, []);
  
  // Online import mode state
  const [leftMode, setLeftMode] = useState<'project' | 'import'>('project');
  const [returnProjectSelectionId, setReturnProjectSelectionId] = useState<string | null>(null);
  const [onlineSessionId, setOnlineSessionId] = useState<string | null>(null);
  const [onlineCandidates, setOnlineCandidates] = useState<any[]>([]);
  const [selectedOnlineCandidateId, setSelectedOnlineCandidateId] = useState<string | null>(null);
  // DEPRECATED: onlineCandidateData - no longer used, kept for backward compatibility
  // const [onlineCandidateData, setOnlineCandidateData] = useState<any>(null);
  
  // CRITICAL: Separate calculation summary (from list_calculations) from calculation detail (from get_calculation_detail)
  // The detail's steps array is the canonical source of truth (built from calculation.yaml)
  const [selectedCalculationSummary, setSelectedCalculationSummary] = useState<CalculationInfo | null>(null);
  const [selectedCalculationDetail, setSelectedCalculationDetail] = useState<CalculationDetailResult | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  
  // Top-level tab state for Calculations view
  const [activeCalcTab, setActiveCalcTab] = useState<'overview' | 'run' | 'analysis'>('overview');
  
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
  
  const handleCreateProjectSuccess = useCallback(async (newProjectRoot: string) => {
    // Clear selected calculation and step when opening a new project (fixes stale step selection)
    setSelectedCalculationSummary(null);
    setSelectedCalculationDetail(null);
    setSelectedStepId(null);
    setSelectedStructure(null);
    
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentView, projectLoaded]); // Intentionally exclude structures/calculations/fetchStructures/fetchCalculations to prevent loops
  
  // ==========================================================================
  // Structure Handling
  // ==========================================================================
  
  // Unified structure model state (replaces separate project/online states)
  const [currentStructureModel, setCurrentStructureModel] = useState<StructureModel | null>(null);
  const [rightSelection, setRightSelection] = useState<RightSelection | null>(null);
  const [structureLoadError, setStructureLoadError] = useState<string | null>(null);
  
  // Viewer settings (shared for both project and online)
  const [viewerSettings, setViewerSettings] = useState({
    supercell: [1, 1, 1] as [number, number, number],
    repeatBoundary: true,
    displayMode: 'primitive' as 'primitive' | 'supercell' | 'conventional' | 'box',
    boxBounds: null as [number, number, number, number, number, number] | null,
    showBonds: true,
    showUnitCell: true,
    showLabels: false,
    atomScale: 0.4,
    bondScale: 1.0,
  });
  
  // Saved viewer settings for project mode (restored on exit import)
  const savedProjectViewerSettingsRef = useRef<typeof viewerSettings | null>(null);
  
  // Legacy state (kept for compatibility during refactor)
  const [currentSupercell, setCurrentSupercell] = useState<[number, number, number]>([1, 1, 1]);
  const [currentRepeatBoundary, setCurrentRepeatBoundary] = useState(true);
  const [currentDisplayMode, setCurrentDisplayMode] = useState<'primitive' | 'supercell' | 'conventional' | 'box'>('primitive');
  const [currentBoxBounds, setCurrentBoxBounds] = useState<[number, number, number, number, number, number] | null>(null);
  
  // Generate trace_id for performance logging
  const generateTraceId = useCallback(() => {
    return Date.now().toString(36).slice(-4) + Math.random().toString(36).slice(2, 6);
  }, []);
  
  // Track current trace_id for viewer callback
  const currentTraceIdRef = useRef<string | null>(null);
  const viewerStartTimeRef = useRef<number | null>(null);
  
  // Load token to prevent race conditions - each load gets a unique token
  const loadTokenRef = useRef(0);
  
  // Runtime validator for StructureModel
  function validateStructureModel(m: any): { ok: true } | { ok: false; msg: string } {
    if (!m) {
      return { ok: false, msg: 'Model is null or undefined' };
    }
    if (!m.id || typeof m.id !== 'string') {
      return { ok: false, msg: 'Missing or invalid id field' };
    }
    if (!m.lattice || !Array.isArray(m.lattice) || m.lattice.length !== 3) {
      return { ok: false, msg: 'Missing or invalid lattice (must be 3x3 matrix)' };
    }
    for (const row of m.lattice) {
      if (!Array.isArray(row) || row.length !== 3) {
        return { ok: false, msg: 'Lattice must be 3x3 matrix' };
      }
      for (const val of row) {
        if (typeof val !== 'number' || !isFinite(val)) {
          return { ok: false, msg: 'Lattice contains non-numeric values' };
        }
      }
    }
    if (!m.atoms || !Array.isArray(m.atoms)) {
      return { ok: false, msg: 'Missing or invalid atoms array' };
    }
    for (const atom of m.atoms) {
      if (!atom.element || typeof atom.element !== 'string') {
        return { ok: false, msg: 'Atom missing element field' };
      }
      if (!atom.frac || !Array.isArray(atom.frac) || atom.frac.length !== 3) {
        return { ok: false, msg: 'Atom missing or invalid frac_coords' };
      }
    }
    // bonds are optional, but if present must be valid
    if (m.bonds && !Array.isArray(m.bonds)) {
      return { ok: false, msg: 'bonds must be an array if present' };
    }
    return { ok: true };
  }
  
  // Unified structure loader (project and online)
  const loadStructureModel = useCallback(async (
    selection: RightSelection,
    viewerSettingsOverride?: Partial<typeof viewerSettings>
  ): Promise<StructureModel> => {
    if (!projectRoot || !qv) {
      throw new Error('Project root or QV client not available');
    }
    
    // Frontend timing: RPC start
    const rpcStart = performance.now();
    
    const traceId = generateTraceId();
    currentTraceIdRef.current = traceId;
    
    let visData: StructureVisData | null = null;
    let provenance: Provenance | null = null;
    let formula = '';
    let nsites = 0;
    // let nSpecies = 0;  // Unused, removed to fix lint warning
    let rpcMs: number | null = null; // Declare in outer scope to avoid ReferenceError
    
    try {
      if (selection.kind === 'project') {
        // Project structure path
        const structure = structures?.find(s => s.id === selection.structureId);
        if (!structure) {
          throw new Error(`Structure not found: ${selection.structureId}`);
        }
        
        const settings = viewerSettingsOverride || viewerSettings;
        const response = await qv.call('get_structure_vis', {
          project_root: projectRoot,
          selector: structure.slug,
          supercell: settings.supercell,
          repeat_boundary: settings.repeatBoundary,
          display_mode: settings.displayMode,
          box_bounds: settings.boxBounds ?? undefined,  // Convert null to undefined for type safety
          trace_id: traceId,
        });
        
        // Frontend timing: RPC end
        const rpcEnd = performance.now();
        rpcMs = rpcEnd - rpcStart;
        
        if (response.ok && response.data) {
          try {
            visData = response.data as StructureVisData;
            formula = visData.formula || '';
            nsites = visData.n_atoms || 0;
            // nSpecies = structure.n_species;  // Unused, removed to fix lint warning
            
            // Get backend perf metrics if available
            const perf = (response.data as any).perf;
            const backendTotalMs = perf?.total_ms || 0;
            
            // Log structure load success (one line per load)
            const kind = 'project';
            const atomsCount = visData.atoms?.length || 0;
            const bondsCount = visData.bonds?.length || 0;
            const hasProvenance = !!(response.data as any).provenance;
            console.log(
              `[structure_vis] kind=${kind} structureId=${selection.structureId} ` +
              `atoms=${atomsCount} bonds=${bondsCount} provenance=${hasProvenance}`
            );
            
            // Frontend timing: Render start (setState triggers render)
            const renderStart = performance.now();
            
            // Store render start time for onFirstFrame callback
            viewerStartTimeRef.current = renderStart;
            
            // Log frontend timing (will be completed in onFirstFrame callback)
            // Format: [ui] kind=project rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell
            const mode = settings.displayMode;
            
            // Note: render_ms will be logged in handleViewerFirstFrame
            // Log timing immediately (do not store in model)
            const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;
            console.log(
              `[ui] kind=${kind} rpc=${rpcMsStr} backend=${Math.round(backendTotalMs)}ms ` +
              `atoms=${atomsCount} bonds=${bondsCount} mode=${mode} (render pending)`
            );
          } catch (err) {
            console.error('[structure_vis_parse_failed] project path', err, response.data);
            throw err; // Re-throw to be caught by outer catch
          }
        } else {
          const errorMsg = response.error || 'Unknown error';
          throw new Error(`Backend error loading structure: ${errorMsg}`);
        }
      } else {
        // Online candidate path
        const settings = viewerSettingsOverride || viewerSettings;
        const response = await qv.call('structure_get_online_candidate', {
          project_root: projectRoot,
          session_id: selection.sessionId,
          candidate_id: selection.candidateId,
          supercell: settings.supercell,
          repeat_boundary: settings.repeatBoundary,
          display_mode: settings.displayMode,
          box_bounds: settings.boxBounds ?? undefined,  // Convert null to undefined for type safety
          trace_id: traceId,
        });
        
        // Frontend timing: RPC end
        const rpcEnd = performance.now();
        rpcMs = rpcEnd - rpcStart;
        
        if (response.ok && response.data) {
          try {
            const data = response.data as any;
            formula = data.formula || '';
            nsites = data.n_atoms || 0;
            // nSpecies = data.n_species || 0;  // Unused, removed to fix lint warning
            provenance = data.provenance || null;
            
            // Log structure load success (one line per load)
            const kind = 'online';
            const atomsCount = data.structure_vis?.atoms?.length || 0;
            const bondsCount = data.structure_vis?.bonds?.length || 0;
            const hasProvenance = !!provenance;
            console.log(
              `[structure_vis] kind=${kind} candidateId=${selection.candidateId} ` +
              `atoms=${atomsCount} bonds=${bondsCount} provenance=${hasProvenance}`
            );
            
            // Convert to StructureVisData format
            if (data.structure_vis) {
              // Use frac_coords from payload if available, otherwise compute from cart
              const atoms = data.structure_vis.atoms.map((atom: any, idx: number) => {
                // Backend should provide both cart_coords and frac_coords
                const cart = atom.cart_coords || atom.position;
                const frac = atom.frac_coords || atom.position; // Fallback to cart if missing (shouldn't happen)
                
                return {
                  index: idx,
                  element: atom.symbol,
                  cart_coords: cart,
                  frac_coords: frac,  // Use actual fractional coords from backend
                  color: atom.color,
                  radius: atom.radius,
                };
              });
            
              const boundary_atoms = (data.structure_vis.boundary_atoms || []).map((atom: any, idx: number) => {
                const cart = atom.cart_coords || atom.position;
                const frac = atom.frac_coords || atom.position;
                
                return {
                  index: atoms.length + idx,
                  element: atom.symbol,
                  cart_coords: cart,
                  frac_coords: frac,
                  color: atom.color,
                  radius: atom.radius,
                };
              });
              
              visData = {
                structure_id: `online:${selection.candidateId}`,
                structure_name: formula,
                formula: formula,
                n_atoms: atoms.length,
                n_boundary_atoms: boundary_atoms.length,
                n_bonds: data.structure_vis.bonds?.length || 0,
                supercell: data.structure_vis.supercell || [1, 1, 1],
                
                // Get backend perf metrics if available (perf is optional in StructureVisData)
                perf: data.structure_vis.perf,
                display_mode: data.structure_vis.display_mode || 'primitive',
                lattice: data.structure_vis.lattice,
                atoms: atoms,
                boundary_atoms: boundary_atoms,
                bonds: (data.structure_vis.bonds || []).map((bond: any) => ({
                  idx1: bond.idx1 ?? 0,
                  idx2: bond.idx2 ?? 0,
                  coord1: bond.coord1 || atoms[bond.idx1 ?? 0]?.cart_coords || [0, 0, 0],
                  coord2: bond.coord2 || atoms[bond.idx2 ?? 0]?.cart_coords || [0, 0, 0],
                  distance: bond.distance || 0,
                })),
                element_colors: {},
              };
              
              // Get backend perf metrics if available
              const perf = (data.structure_vis as any).perf;
              const backendTotalMs = perf?.total_ms || 0;
              
              // Frontend timing: Render start (setState triggers render)
              const renderStart = performance.now();
              
              // Store render start time for onFirstFrame callback
              viewerStartTimeRef.current = renderStart;
              
              // Log frontend timing (will be completed in onFirstFrame callback)
              // Format: [ui] kind=online rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell
              const kind = 'online';
              const mode = settings.displayMode;
              const atomsCount = atoms.length;
              const bondsCount = data.structure_vis.bonds?.length || 0;
              
              // Note: render_ms will be logged in handleViewerFirstFrame
              // Log timing immediately (do not store in model)
              const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;
              console.log(
                `[ui] kind=${kind} rpc=${rpcMsStr} backend=${Math.round(backendTotalMs)}ms ` +
                `atoms=${atomsCount} bonds=${bondsCount} mode=${mode} (render pending)`
              );
            } else {
              console.error('[structure_vis_parse_failed] online path - missing structure_vis', data);
            }
          } catch (err) {
            console.error('[structure_vis_parse_failed] online path', err, response.data);
            throw err; // Re-throw to be caught by outer catch
          }
        } else {
          const errorMsg = response.error || 'Unknown error';
          throw new Error(`Backend error loading online candidate: ${errorMsg}`);
        }
      }
      
      if (!visData) {
        throw new Error('No visualization data received from backend');
      }
      
      // rpcEnd and rpcMs already calculated above for both project and online paths
      
      try {
        // Step 3: Species should be derived from primary atoms (non-boundary), never from boundary atoms
        const speciesSet = new Set<string>();
        const primaryAtoms = visData.atoms.filter((a: any) => !a.is_boundary);
        // Use primary atoms for species, fallback to all atoms if no is_boundary flag
        const sourceAtoms = primaryAtoms.length > 0 ? primaryAtoms : visData.atoms;
        if (sourceAtoms && Array.isArray(sourceAtoms)) {
          sourceAtoms.forEach((atom: any) => speciesSet.add(atom.element));
        }
        // Legacy fallback: if old payload has boundary_atoms but no is_boundary, use only canonical atoms
        if (primaryAtoms.length === 0 && visData.boundary_atoms && Array.isArray(visData.boundary_atoms) && visData.boundary_atoms.length > 0) {
          // Old payload: use only canonical atoms (not boundary_atoms) for species
          if (visData.atoms && Array.isArray(visData.atoms)) {
            visData.atoms.forEach((atom: any) => speciesSet.add(atom.element));
          }
          if (process.env.NODE_ENV === 'development') {
            console.warn('[App] Legacy payload: using all atoms for species (no is_boundary flag)');
          }
        }
        const species = Array.from(speciesSet).sort();
        
        // Validate required fields - bonds are optional, but ensure defaults
        if (!visData.lattice || !visData.lattice.matrix) {
          throw new Error('Missing lattice data in response');
        }
        if (!visData.atoms || !Array.isArray(visData.atoms)) {
          throw new Error('Missing or invalid atoms array in response');
        }
        // bonds are optional - use empty array if missing
        if (visData.bonds && !Array.isArray(visData.bonds)) {
          throw new Error('bonds must be an array if present');
        }
        
        // Build StructureModel with defaults for optional fields
        const model: StructureModel = {
          id: selection.kind === 'project' ? selection.structureId : `online:${selection.candidateId}`,
          name: visData.structure_name || formula,
          formula: formula,
          nsites: nsites,
          species: species,
          lattice: visData.lattice.matrix,
          atoms: visData.atoms.map(atom => ({
            element: atom.element,
            frac: atom.frac_coords,
            cart: atom.cart_coords,
            index: atom.index,
          })),
          bonds: (visData.bonds || []).map(bond => ({
            i: bond.idx1 ?? 0,
            j: bond.idx2 ?? 0,
            distance: bond.distance ?? 0,
          })),
          vis: visData,
          provenance: provenance || null, // Explicitly set to null if missing
          // P1-2: Calculate n_boundary_atoms from atoms.filter(a=>a.is_boundary)
          n_boundary_atoms: visData.atoms.filter((a: any) => a.is_boundary === true).length || visData.n_boundary_atoms || 0,
          supercell: visData.supercell || [1, 1, 1],
          display_mode: visData.display_mode || 'primitive',
          element_colors: visData.element_colors || {},
        };
        
        // P1-2: Runtime assertion for development (only log on failure)
        if (process.env.NODE_ENV === 'development') {
          const selectionKey = selection.kind === 'project' 
            ? `project:${selection.structureId}` 
            : `online:${selection.sessionId}:${selection.candidateId}`;
          const atomsLen = model.atoms.length;
          const bondsLen = model.bonds.length;
          const boundaryAtomsCount = visData.atoms.filter((a: any) => a.is_boundary === true).length;
          const hasBoundaryAtoms = boundaryAtomsCount > 0;
          const repeatBoundary = viewerSettingsOverride?.repeatBoundary ?? (selection.kind === 'project' ? currentRepeatBoundary : viewerSettings.repeatBoundary);
          
          // Assert: if repeat_boundary=true, must have boundary atoms
          if (repeatBoundary && !hasBoundaryAtoms && visData.boundary_atoms?.length === 0) {
            console.warn('[FRONTEND] P1-2 ASSERTION: repeat_boundary=true but no boundary atoms found in atoms array');
          }
          
          // Assert: bonds must reference valid atom indices
          if (bondsLen > 0) {
            const maxBondIndex = Math.max(...model.bonds.map(b => Math.max(b.i, b.j)));
            if (maxBondIndex >= atomsLen) {
              const firstBondKeys = Object.keys(visData.bonds[0]);
              const firstBond = visData.bonds[0];
              const secondBond = visData.bonds[1] || null;
              console.error(
                `[FRONTEND] PAYLOAD_EVIDENCE selectionKey=${selectionKey} ` +
                `atoms.length=${atomsLen} bonds.length=${bondsLen} ` +
                `maxBondIndex=${maxBondIndex} maxBondIndex_valid=false ` +
                `firstBondKeys=${JSON.stringify(firstBondKeys)} ` +
                `firstBond=${JSON.stringify(firstBond)} secondBond=${JSON.stringify(secondBond)}`
              );
              console.error(`[FRONTEND] P1-2 ASSERTION FAILED: maxBondIndex=${maxBondIndex} >= atoms.length=${atomsLen}`);
            }
          }
        }
        
        // Store perf data for viewer callback (do not store rpcMs - timing is logged immediately)
        (model.vis as any).__traceId = traceId;
        (model.vis as any).__backendTotalMs = (visData as any).perf?.total_ms || '?';
        (model.vis as any).__atoms = (visData as any).perf?.atoms || nsites;
        (model.vis as any).__bonds = (visData as any).perf?.bonds || visData.n_bonds;
        if (selection.kind === 'online') {
          (model.vis as any).__candidateId = selection.candidateId;
        }
        
        // Validate the model before returning
        const validation = validateStructureModel(model);
        if (!validation.ok) {
          throw new Error(`Invalid structure model: ${validation.msg}`);
        }
        
        return model;
      } catch (e) {
        console.error('[structure_vis_parse_failed] model construction', e, { visData, selection });
        throw e instanceof Error ? e : new Error(`Failed to construct structure model: ${String(e)}`);
      }
    } catch (e) {
      console.error('[structure_vis_parse_failed] outer catch', e, { selection });
      throw e instanceof Error ? e : new Error(`Failed to load structure: ${String(e)}`);
    }
  }, [qv, projectRoot, structures, viewerSettings, generateTraceId]);
  
  // Viewer first frame callback
  const handleViewerFirstFrame = useCallback((traceId: string) => {
    // Only log if this is still the current trace
    if (traceId !== currentTraceIdRef.current) {
      return;
    }
    
    const viewerStart = viewerStartTimeRef.current;
    if (viewerStart === null) {
      return;
    }
    
    const viewerEnd = performance.now();
    const renderMs = viewerEnd - viewerStart;
    
    // Get perf data from structure data
    const data = structureVisData as any;
    if (!data) {
      return;
    }
    
    // Check trace ID matches (for both project and online)
    if (data.__traceId !== traceId) {
      return;
    }
    
    // rpcMs may not be present if data came from loadStructureModel (timing logged immediately)
    // Only read if present (legacy loadStructureVis still stores it)
    const rpcMs = data.__rpcMs;
    const backendTotalMs = data.__backendTotalMs || '?';
    const atoms = data.__atoms || 0;
    const bonds = data.__bonds || 0;
    
    // Determine source from data
    const source = data.__candidateId ? 'online' : 'project';
    const id = data.__candidateId || data.structure_id || 'unknown';
    
    // Emit frontend timing log (one line summary)
    // Format: [ui] kind=project rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell
    const mode = (data.display_mode || 'primitive') as string;
    const kind = source;
    
    // Safe string conversion for rpcMs (may be undefined)
    const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;
    
    console.log(
      `[ui] kind=${kind} rpc=${rpcMsStr} render=${Math.round(renderMs)}ms ` +
      `atoms=${atoms} bonds=${bonds} mode=${mode}`
    );
    
    // Also emit detailed perf log (for compatibility)
    const rpcMsDetail = rpcMs == null ? "n/a" : rpcMs.toFixed(1);
    console.log(
      `[PERF] structure_view trace=${traceId} rpc=${rpcMsDetail}ms backend=${backendTotalMs}ms render=${renderMs.toFixed(1)}ms atoms=${atoms} bonds=${bonds} source=${source} id=${id}`
    );
    
    // Clear refs
    viewerStartTimeRef.current = null;
  }, [structureVisData]);
  
  const handleSelectStructure = useCallback(async (structure: StructureInfo) => {
    // Only allow selection in project mode
    if (leftMode !== 'project') {
      return;
    }
    
    const selectionKey = `project:${structure.id}`;
    // P0: Always increment refresh token to force reload (refresh semantics)
    setStructureRefreshToken(t => {
      const newToken = t + 1;
      console.log('[UI_CLICK]', { selectionKey, refreshToken: newToken, ts: Date.now() });
      return newToken;
    });
    
    setSelectedStructure(structure);
    // Mark that user has manually selected (prevent auto-select override)
    didAutoSelectStructureRef.current = true;
    setCurrentSupercell([1, 1, 1]);
    setCurrentRepeatBoundary(true);
    setCurrentDisplayMode('primitive');
    setCurrentBoxBounds(null);
    
    // Log selection
    console.log(`[PERF] selection mode=project source=project id=${structure.id}`);
    
    // CRITICAL: Do NOT call loadStructureModel here - only useEffect should call it
    // This prevents double trigger while ensuring refresh on same selection
  }, [leftMode]);
  
  // Online import mode handlers
  const handleEnterImportMode = useCallback(() => {
    // Save current selection and viewer settings
    setReturnProjectSelectionId(selectedStructure?.id || null);
    savedProjectViewerSettingsRef.current = { ...viewerSettings };
    
    // Reset viewer settings to defaults for online preview
    setViewerSettings({
      supercell: [1, 1, 1],
      repeatBoundary: true,
      displayMode: 'primitive',
      boxBounds: null,
      showBonds: true,
      showUnitCell: true,
      showLabels: false,
      atomScale: 0.4,
      bondScale: 1.0,
    });
    
    setLeftMode('import');
  }, [selectedStructure, viewerSettings]);
  
  const handleExitImportMode = useCallback(async () => {
    // Clear online state first
    setOnlineSessionId(null);
    setOnlineCandidates([]);
    setSelectedOnlineCandidateId(null);
    // setOnlineCandidateData(null);  // DEPRECATED: onlineCandidateData no longer used
    currentOnlineCandidateIdRef.current = null;
    setRightSelection(null);
    setCurrentStructureModel(null);
    
    // Switch back to project mode
    setLeftMode('project');
    
    // Restore saved viewer settings
    if (savedProjectViewerSettingsRef.current) {
      setViewerSettings(savedProjectViewerSettingsRef.current);
      savedProjectViewerSettingsRef.current = null;
    }
    
    // Clear viewer data - it will be reloaded by project useEffect
    setStructureVisData(null);
    setIsLoading3D(false);
    
    // Restore previous project selection
    if (returnProjectSelectionId && structures) {
      const structureToRestore = structures.find(s => s.id === returnProjectSelectionId);
      if (structureToRestore) {
        setSelectedStructure(structureToRestore);
        // The project useEffect will handle loading the vis data
      }
    }
    setReturnProjectSelectionId(null);
  }, [returnProjectSelectionId, structures]);
  
  const handleSelectOnlineCandidate = useCallback((sessionId: string, candidateId: string) => {
    const selectionKey = `online:${sessionId}:${candidateId}`;
    // P0: Always increment refresh token to force reload (refresh semantics)
    setStructureRefreshToken(t => {
      const newToken = t + 1;
      console.log('[UI_CLICK]', { selectionKey, refreshToken: newToken, ts: Date.now() });
      return newToken;
    });
    
    // Immediately update selection state - the useEffect will handle fetching
    // This ensures UI updates immediately and prevents stale data
    setSelectedOnlineCandidateId(candidateId);
    setOnlineSessionId(sessionId);
    
    // Clear current viewer data immediately to show loading state
    setIsLoading3D(true);
    setStructureVisData(null);
    
    // The useEffect hook will handle the actual fetching
  }, []);
  
  const handleImportOnlineCandidate = useCallback(async () => {
    if (!projectRoot || !onlineSessionId || !selectedOnlineCandidateId) return;
    
    try {
      const response = await qv.call('structure_import_online_candidate', {
        project_root: projectRoot,
        session_id: onlineSessionId,
        candidate_id: selectedOnlineCandidateId,
      });
      
      if (response.ok && response.data) {
        // Refresh structures list
        await fetchStructures();
        
        // Find and select the newly imported structure
        const newStructures = await qv.call('list_structures', { project_root: projectRoot });
        if (newStructures.ok && newStructures.data) {
          // list_structures returns { structures: StructureInfo[]; count: number }
          const structuresList = newStructures.data.structures || [];
          const newStructure = structuresList.find((s: StructureInfo) => s.id === (response.data as any).new_structure_id);
          if (newStructure) {
            await handleSelectStructure(newStructure);
          }
        }
        
        // Exit import mode
        await handleExitImportMode();
      }
    } catch (e) {
      console.error('Failed to import online candidate:', e);
    }
  }, [projectRoot, onlineSessionId, selectedOnlineCandidateId, qv, handleExitImportMode, handleSelectStructure]);
  
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
    // DO NOT change activeCalcTab - user stays in current tab
    
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
          calculation: calculation.id,  // Use ULID to avoid slug collisions
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
                calculation: calculation.id,  // Use ULID to avoid slug collisions
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
      didAutoSelectStructureRef.current = true;
      console.log(`[App] Auto-selecting first structure: ${firstStructure.id}`);
      // Set selection and immediately load 3D view (same as manual selection)
      setSelectedStructure(firstStructure);
      // Set rightSelection for consistency
      setRightSelection({
        kind: 'project',
        structureId: firstStructure.id,
      });
      // Note: The useEffect for project structure loading will handle the StructureModel loading
      // No need to call legacy loadStructureVis - the unified loadStructureModel handles everything
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
  
  // Loading state for structure model
  const [isStructureLoading, setIsStructureLoading] = useState(false);
  
  // P0: Refresh token to force reload on same selection (refresh semantics)
  const [structureRefreshToken, setStructureRefreshToken] = useState(0);
  
  // P0: Single source of truth for structure loading (PROJECT MODE ONLY)
  // This is the ONLY place that calls loadStructureModel for project structures
  // Dependencies include: selectionKey (via selectedStructure.id), refreshToken, and all viewer settings
  useEffect(() => {
    // Guard: only run in project mode
    if (leftMode !== 'project') {
      return;
    }
    
    if (currentView === 'structures' && selectedStructure && projectRoot && qv) {
      const selectionKey = `project:${selectedStructure.id}`;
      const refreshToken = structureRefreshToken;
      
      console.log('[LOAD_START]', { 
        selectionKey, 
        refreshToken, 
        mode: currentDisplayMode,
        sc: currentSupercell,
        repeat: currentRepeatBoundary,
        ts: Date.now() 
      });
      
      // Generate load token for concurrent request handling
      const token = ++loadTokenRef.current;
      const selection: RightSelection = {
        kind: 'project',
        structureId: selectedStructure.id,
      };
        
        // Set loading state and clear errors
        setIsStructureLoading(true);
        setStructureLoadError(null);
        setRightSelection(selection);
        
        // Set timeout to prevent infinite loading (10 seconds)
        const timeoutId = setTimeout(() => {
          if (token === loadTokenRef.current) {
            console.error('[App] Project structure load timeout after 10s');
            setStructureLoadError('Failed to load structure: Request timed out after 10 seconds');
            setIsStructureLoading(false);
          }
        }, 10000);
        
        loadStructureModel(selection, {
          supercell: currentSupercell,
          repeatBoundary: currentRepeatBoundary,
          displayMode: currentDisplayMode,
          boxBounds: currentBoxBounds,
        }).then(model => {
          // Clear timeout on success
          clearTimeout(timeoutId);
          // Check if this load is still current (prevent stale overwrite)
          if (token !== loadTokenRef.current) {
            console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale response discarded`);
            return;
          }
          
          // Validate we're still in the right mode and selection
          const currentLeftMode = leftMode;
          const currentSelectedId = selectedStructure?.id;
          
          if (currentLeftMode === 'project' && selection.kind === 'project' && selection.structureId === currentSelectedId) {
            const loadStartTime = viewerStartTimeRef.current || performance.now();
            const rpcMs = performance.now() - loadStartTime;
            const atomsCount = model.vis?.n_atoms || 0;
            const bondsCount = model.vis?.n_bonds || 0;
            console.log('[LOAD_DONE]', { 
              selectionKey: `project:${currentSelectedId}`, 
              refreshToken,
              rpcMs: Math.round(rpcMs),
              atoms: atomsCount,
              bonds: bondsCount,
              ts: Date.now()
            });
            
            setCurrentStructureModel(model);
            setRightSelection(selection);
            setStructureLoadError(null);
            setIsStructureLoading(false);
            if (model.vis) {
              setStructureVisData(model.vis);
              viewerStartTimeRef.current = performance.now();
            }
          } else {
            console.warn(`[App] Skipping model update: mode=${currentLeftMode} selectedId=${currentSelectedId} selectionId=${selection.structureId}`);
            setIsStructureLoading(false);
          }
        }).catch(err => {
          // Clear timeout on error
          clearTimeout(timeoutId);
          
          // Check if this load is still current
          if (token !== loadTokenRef.current) {
            console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale error discarded`);
            return;
          }
          
          console.error('[App] Failed to load structure model', err);
          setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
          setIsStructureLoading(false);
        });
    } else if (currentView !== 'structures' && structureVisData) {
      // Clear 3D data when leaving structures view
      setStructureVisData(null);
      setIsStructureLoading(false);
    }
  }, [
    currentView, 
    leftMode, 
    selectedStructure?.id,  // selectionKey
    structureRefreshToken,  // P0: refresh token forces reload on same selection
    projectRoot, 
    qv, 
    loadStructureModel,
    currentSupercell,  // P0: viewer settings must trigger reload
    currentRepeatBoundary,
    currentDisplayMode,
    currentBoxBounds,
  ]);
  // P0: All viewer settings are dependencies - changing them MUST trigger reload
  // Refresh token ensures same selection still triggers reload (refresh semantics)
  
  // Track current online candidate ID to prevent stale overwrites
  const currentOnlineCandidateIdRef = useRef<string | null>(null);
  
  // Load 3D view when online candidate is selected (IMPORT MODE ONLY)
  // Separate effect to handle online candidate fetching
  useEffect(() => {
    // Guard: only run in import mode
    if (leftMode !== 'import') {
      return;
    }
    
    if (currentView === 'structures' && selectedOnlineCandidateId && onlineSessionId && projectRoot && qv) {
      const selectionKey = `online:${onlineSessionId}:${selectedOnlineCandidateId}`;
      const refreshToken = structureRefreshToken;
      
      console.log('[LOAD_START]', { 
        selectionKey, 
        refreshToken, 
        mode: viewerSettings.displayMode || 'primitive',
        sc: viewerSettings.supercell,
        repeat: viewerSettings.repeatBoundary,
        ts: Date.now() 
      });
      
      // Generate load token for concurrent request handling
      const token = ++loadTokenRef.current;
      const capturedCandidateId = selectedOnlineCandidateId;
      const selection: RightSelection = {
        kind: 'online',
        sessionId: onlineSessionId!,
        candidateId: capturedCandidateId,
      };
        
      // Set loading state and clear errors
      setIsStructureLoading(true);
      setStructureLoadError(null);
      currentOnlineCandidateIdRef.current = capturedCandidateId;
      setStructureVisData(null);
      viewerStartTimeRef.current = performance.now();  // Track load start time
      
      // Set timeout to prevent infinite loading (10 seconds)
      const timeoutId = setTimeout(() => {
          if (token === loadTokenRef.current) {
            console.error('[App] Online candidate load timeout after 10s');
            setStructureLoadError('Failed to load structure: Request timed out after 10 seconds');
            setIsStructureLoading(false);
            setIsLoading3D(false);
          }
        }, 10000);
        
        loadStructureModel(selection, {
          supercell: viewerSettings.supercell,
          repeatBoundary: viewerSettings.repeatBoundary,
          displayMode: viewerSettings.displayMode || 'primitive',
          boxBounds: viewerSettings.boxBounds,
          showBonds: true,
          showUnitCell: true,
          showLabels: false,
          atomScale: 0.4,
          bondScale: 1.0,
        }).then(model => {
          // Clear timeout on success
          clearTimeout(timeoutId);
          
          // Check if this load is still current (prevent stale overwrite)
          if (token !== loadTokenRef.current) {
            console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale response discarded`);
            return;
          }
          
          // Validate we're still in the right mode and selection
          if (leftMode === 'import' && capturedCandidateId === currentOnlineCandidateIdRef.current) {
            const rpcMs = performance.now() - (viewerStartTimeRef.current || performance.now());
            const atomsCount = model.vis?.n_atoms || 0;
            const bondsCount = model.vis?.n_bonds || 0;
            console.log('[LOAD_DONE]', { 
              selectionKey: `online:${onlineSessionId}:${capturedCandidateId}`, 
              refreshToken,
              rpcMs: Math.round(rpcMs),
              atoms: atomsCount,
              bonds: bondsCount,
              ts: Date.now()
            });
            
            setCurrentStructureModel(model);
            setRightSelection(selection);
            setStructureLoadError(null);
            setIsStructureLoading(false);
            setIsLoading3D(false);
            if (model.vis) {
              setStructureVisData(model.vis);
              viewerStartTimeRef.current = performance.now();
            }
          } else {
            console.warn(`[App] Skipping online model update: mode=${leftMode} candidateId=${capturedCandidateId}`);
            setIsStructureLoading(false);
            setIsLoading3D(false);
          }
        }).catch(err => {
          // Clear timeout on error
          clearTimeout(timeoutId);
          
          // Check if this load is still current
          if (token !== loadTokenRef.current) {
            console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale error discarded`);
            return;
          }
          
          console.error('[App] Failed to load online candidate model', err);
          setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
          setIsStructureLoading(false);
          setIsLoading3D(false);
        });
    } else if (currentView !== 'structures' && structureVisData) {
      // Clear 3D data when leaving structures view
      setStructureVisData(null);
    }
  }, [
    currentView, 
    leftMode, 
    selectedOnlineCandidateId,  // selectionKey
    onlineSessionId,
    structureRefreshToken,  // P0: refresh token forces reload on same selection
    projectRoot, 
    qv, 
    loadStructureModel,
    viewerSettings.supercell,  // P0: viewer settings must trigger reload
    viewerSettings.repeatBoundary,
    viewerSettings.displayMode,
    viewerSettings.boxBounds,
  ]);
  // P0: All viewer settings are dependencies - changing them MUST trigger reload
  // Refresh token ensures same selection still triggers reload (refresh semantics)
  
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
    // CRITICAL: Rebuild registry FIRST to ensure the new calculation is indexed
    const rebuildResponse = await qv.call('rebuild_project_registry', {
      project_root: projectRoot,
    });
    
    if (!rebuildResponse.ok) {
      console.error('[App] Failed to rebuild registry after calculation creation', rebuildResponse.error);
      // Continue anyway - might still work
    }
    
    // Refresh calculations list and summary
    await refreshSummary();
    const calculationsList = await fetchCalculations();
    
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
  }, [qv, projectRoot, fetchCalculations, refreshSummary, handleSelectCalculation]);
  
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
      
      // Auto-switch to Run & Logs tab after successful submission
      setActiveCalcTab('run');
      
      // Job counts will be refreshed by StatusBar and JobsPanel polling
    } else {
      showNotification(`Failed to start job: ${response.error?.message || 'Unknown error'}`, 'error');
      // Do NOT change tabs on error - stay in Overview
    }
    
    setDebugResult(response as QVResponse);
  }, [qv, projectRoot, showNotification]);
  
  const handleGoToJobs = useCallback(() => {
    setCurrentView('jobs');
  }, []);
  
  // Handle "View Analysis" from Jobs panel
  // Navigate to Calculations view and select the calculation, user can then click Analysis tab
  const handleViewAnalysisFromJob = useCallback(async (calculationSlug: string) => {
    // Switch to calculations view
    setCurrentView('calculations');
    
    // If calculations aren't loaded, fetch them first
    if (!calculations) {
      await fetchCalculations();
    }
    
    // Try to find and select the calculation
    const wf = calculations?.find(w => w.slug === calculationSlug || w.name === calculationSlug);
    if (wf) {
      handleSelectCalculation(wf);
      // Auto-switch to Analysis tab after selecting calculation
      setActiveCalcTab('analysis');
    }
  }, [calculations, fetchCalculations, handleSelectCalculation]);
  
  const handleSelectStep = useCallback((stepId: string) => {
    console.log('[App] handleSelectStep called with:', stepId);
    // Empty string means clear selection
    setSelectedStepId(stepId || null);
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
      calculation_ulid: renameCalculation.id,  // Use ULID, not slug
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
      calculation_ulid: deleteCalculation.id,  // Use ULID, not slug
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
  // Note: Analysis data loading is now handled by CalculationAnalysisPanel component
  
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
                selectedId={leftMode === 'project' ? selectedStructure?.id : null}
                onSelect={leftMode === 'project' ? handleSelectStructure : undefined}
                onRename={setRenameStructure}
                onDelete={setDeleteStructure}
                projectRoot={projectRoot}
                leftMode={leftMode}
                onEnterImportMode={handleEnterImportMode}
                onExitImportMode={handleExitImportMode}
                onSelectOnlineCandidate={handleSelectOnlineCandidate}
                selectedOnlineCandidateId={selectedOnlineCandidateId}
                onlineSessionId={onlineSessionId}
                onlineCandidates={onlineCandidates}
              />
              {leftMode === 'project' && (
                <button 
                  className="view-action-btn"
                  onClick={() => setShowImportStructure(true)}
                >
                  ➕ Import Structure
                </button>
              )}
            </ResizablePane>
            {currentStructureModel ? (
              <div className="structures-view__detail">
                <ResizableSplitPane
                  storageKey="qv.structures.detailsHeightPx"
                  defaultTopHeight={260}
                  minTopHeight={180}
                  minBottomHeight={360}
                  top={
                    <div className="structures-view__detail-panel-wrapper" data-testid="qv-structure-detail">
                      <StructureDetailPanel
                        model={currentStructureModel}
                        onClose={leftMode === 'project' ? () => {
                          setSelectedStructure(null);
                          setStructureVisData(null);
                          setCurrentStructureModel(null);
                          setRightSelection(null);
                          setStructureLoadError(null);
                        } : undefined}
                      />
                    </div>
                  }
                  bottom={
                    <div className="structures-view__3d-wrapper" data-testid="qv-structure-viewer">
                      <StructureViewer3D
                        data={currentStructureModel.vis || null}
                        isLoading={isLoading3D || isStructureLoading}
                        showBonds={viewerSettings.showBonds}
                        showUnitCell={viewerSettings.showUnitCell}
                        showLabels={viewerSettings.showLabels}
                        atomScale={viewerSettings.atomScale}
                        bondScale={viewerSettings.bondScale}
                        structureId={currentStructureModel.id}
                    onSupercellChange={(supercell) => {
                      // P0: Only update state - useEffect will handle reload (prevents double trigger)
                      setViewerSettings(prev => ({ ...prev, supercell }));
                      if (leftMode === 'project') {
                        setCurrentSupercell(supercell);
                      }
                      // useEffect watching currentSupercell/viewerSettings will trigger reload
                    }}
                    onRepeatBoundaryChange={(repeat) => {
                      // P0: Only update state - useEffect will handle reload (prevents double trigger)
                      setViewerSettings(prev => ({ ...prev, repeatBoundary: repeat }));
                      if (leftMode === 'project') {
                        setCurrentRepeatBoundary(repeat);
                      }
                      // useEffect watching currentRepeatBoundary/viewerSettings will trigger reload
                    }}
                    onDisplayModeChange={(mode) => {
                      const selectionKey = rightSelection ? (rightSelection.kind === 'project' ? `project:${rightSelection.structureId}` : `online:${rightSelection.sessionId}:${rightSelection.candidateId}`) : 'none';
                      console.log('[LOAD_TRIGGER]', { reason: 'onDisplayModeChange', selectionKey, ts: Date.now() });
                      setViewerSettings(prev => ({ ...prev, displayMode: mode }));
                      setCurrentDisplayMode(mode);
                      // Reload structure with new display mode (both project and online)
                      if (rightSelection) {
                        const token = ++loadTokenRef.current;
                        setIsStructureLoading(true);
                        loadStructureModel(rightSelection, {
                          ...viewerSettings,
                          displayMode: mode,
                        }).then(model => {
                          if (token === loadTokenRef.current) {
                            setCurrentStructureModel(model);
                            setIsStructureLoading(false);
                            if (model.vis) {
                              setStructureVisData(model.vis);
                              viewerStartTimeRef.current = performance.now();
                            }
                          }
                        }).catch(err => {
                          if (token === loadTokenRef.current) {
                            console.error('[App] Failed to reload structure with new display mode', err);
                            setStructureLoadError(`Failed to reload: ${err instanceof Error ? err.message : String(err)}`);
                            setIsStructureLoading(false);
                          }
                        });
                      }
                    }}
                        onBoxBoundsChange={(bounds) => {
                          // P0: Only update state - useEffect will handle reload (prevents double trigger)
                          setViewerSettings(prev => ({ ...prev, boxBounds: bounds }));
                          if (leftMode === 'project') {
                            setCurrentBoxBounds(bounds);
                          }
                          // useEffect watching currentBoxBounds/viewerSettings will trigger reload
                        }}
                        currentDisplayMode={viewerSettings.displayMode}
                        currentBoxBounds={viewerSettings.boxBounds}
                        onFirstFrame={handleViewerFirstFrame}
                        traceId={currentTraceIdRef.current || undefined}
                      />
                    </div>
                  }
                />
                {leftMode === 'import' && (
                  <div className="structures-view__import-actions">
                    <button
                      className="qv-button qv-button--primary"
                      onClick={handleImportOnlineCandidate}
                      style={{ flex: 1, padding: '10px 20px', fontSize: '14px', fontWeight: '500' }}
                    >
                      Import
                    </button>
                    <button
                      className="qv-button qv-button--secondary"
                      onClick={handleExitImportMode}
                      style={{ flex: 1, padding: '10px 20px', fontSize: '14px', fontWeight: '500' }}
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            ) : structureLoadError ? (
              <div className="structures-view__detail structures-view__detail--error">
                <div className="error-panel">
                  <h3>Failed to Load Structure</h3>
                  {rightSelection && (
                    <p style={{ fontSize: '12px', color: '#888', marginBottom: '8px' }}>
                      Selection: {rightSelection.kind === 'project' 
                        ? `project:${rightSelection.structureId}` 
                        : `online:${rightSelection.sessionId}:${rightSelection.candidateId}`}
                    </p>
                  )}
                  <p>{structureLoadError}</p>
                  <button 
                    className="qv-button qv-button--secondary"
                    onClick={() => {
                      if (rightSelection) {
                        const selectionKey = rightSelection.kind === 'project' ? `project:${rightSelection.structureId}` : `online:${rightSelection.sessionId}:${rightSelection.candidateId}`;
                        console.log('[LOAD_TRIGGER]', { reason: 'retry-button', selectionKey, ts: Date.now() });
                        // Retry loading with load token
                        const token = ++loadTokenRef.current;
                        const selection = rightSelection;
                        setIsStructureLoading(true);
                        setStructureLoadError(null);
                        
                        loadStructureModel(selection, {
                          supercell: currentSupercell,
                          repeatBoundary: currentRepeatBoundary,
                          displayMode: currentDisplayMode,
                          boxBounds: currentBoxBounds,
                        }).then(model => {
                          if (token === loadTokenRef.current) {
                            setCurrentStructureModel(model);
                            setStructureLoadError(null);
                            setIsStructureLoading(false);
                            if (model.vis) {
                              setStructureVisData(model.vis);
                              viewerStartTimeRef.current = performance.now();
                            }
                          }
                        }).catch(err => {
                          if (token === loadTokenRef.current) {
                            console.error('[App] Retry failed', err);
                            setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
                            setIsStructureLoading(false);
                          }
                        });
                      } else if (selectedStructure && leftMode === 'project') {
                        // Fallback: retry with selectedStructure
                        const token = ++loadTokenRef.current;
                        const selection: RightSelection = {
                          kind: 'project',
                          structureId: selectedStructure.id,
                        };
                        setIsStructureLoading(true);
                        setStructureLoadError(null);
                        setRightSelection(selection);
                        
                        loadStructureModel(selection, {
                          supercell: currentSupercell,
                          repeatBoundary: currentRepeatBoundary,
                          displayMode: currentDisplayMode,
                          boxBounds: currentBoxBounds,
                        }).then(model => {
                          if (token === loadTokenRef.current) {
                            setCurrentStructureModel(model);
                            setStructureLoadError(null);
                            setIsStructureLoading(false);
                            if (model.vis) {
                              setStructureVisData(model.vis);
                              viewerStartTimeRef.current = performance.now();
                            }
                          }
                        }).catch(err => {
                          if (token === loadTokenRef.current) {
                            console.error('[App] Retry failed', err);
                            setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
                            setIsStructureLoading(false);
                          }
                        });
                      }
                    }}
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : isStructureLoading || (selectedStructure && !currentStructureModel) ? (
              <div className="structures-view__detail structures-view__detail--loading">
                <div className="loading-panel">
                  <div className="loading-spinner" />
                  <p>Loading structure...</p>
                </div>
              </div>
            ) : null}
          </div>
        );
        
      case 'calculations':
        if (!projectLoaded) return renderNoProjectMessage();
        return (
          <div className="calculations-view">
            {/* Left Column: Calculation List (fixed, like VS Code Explorer) */}
            <ResizablePane
              ref={calculationsPaneRef}
              defaultWidth={200}
              minWidth={56}
              maxWidth={420}
              storageKey="qv-calculations-list-width"
              className="calculations-view__list"
              collapsedWidth={56}
            >
              <CalculationListPanel
                onRefreshProjectRegistry={handleRefreshProjectRegistry}
                calculations={calculations}
                isLoading={isLoadingCalculations}
                selectedId={selectedCalculation?.id}
                onSelect={handleSelectCalculation}
                onRename={setRenameCalculation}
                onDelete={setDeleteCalculation}
                onToggleCollapse={handleToggleCalculationsPane}
                paneRef={calculationsPaneRef}
              />
              <button 
                className="view-action-btn"
                onClick={() => setShowCreateCalculation(true)}
              >
                ➕ New Calculation
              </button>
            </ResizablePane>
            
            {/* Right Workspace: Top-level Tab Bar */}
            <div className="calculations-view__workspace">
              {/* Top-level Tab Bar */}
              <div className="calculations-workspace-tabs">
                <button
                  className={`calculations-workspace-tab ${activeCalcTab === 'overview' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => setActiveCalcTab('overview')}
                  data-testid="qv-calc-tab-overview"
                >
                  Overview & Steps
                </button>
                <button
                  className={`calculations-workspace-tab ${activeCalcTab === 'run' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => setActiveCalcTab('run')}
                  data-testid="qv-calc-tab-run"
                >
                  Run & Logs
                </button>
                <button
                  className={`calculations-workspace-tab ${activeCalcTab === 'analysis' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => setActiveCalcTab('analysis')}
                  data-testid="qv-calc-tab-analysis"
                >
                  Analysis
                </button>
              </div>
              
              {/* Tab Content */}
              <div className="calculations-workspace-content">
                {activeCalcTab === 'overview' && (
                  <CalculationOverviewTab
                    calculationSummary={selectedCalculationSummary}
                    calculationDetail={selectedCalculationDetail}
                    projectRoot={projectRoot}
                    structures={structures || undefined}
                    selectedStepId={selectedStepId}
                    onSelectStep={handleSelectStep}
                    onRunCalculation={handleRunCalculation}
                    onDeleteStep={handleDeleteStep}
                    onGoToJobs={handleGoToJobs}
                    onCalculationUpdated={async () => {
                      // CRITICAL: After adding a step, refresh calculation detail to show the new step
                      console.log('[App] onCalculationUpdated: refreshing calculation detail after step creation');
                      
                      await fetchCalculations();
                      
                      if (selectedCalculationSummary) {
                        // Use calculation ULID (id) instead of slug for subsequent calls
                        const response = await qv.call('get_calculation_detail', {
                          project_root: projectRoot,
                          calculation: selectedCalculationSummary.id,  // Use ULID, not slug
                        });
                        if (response.ok && response.data) {
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
                      console.log('[App] Calculation detail updated from reorder', {
                        calculationSlug: detail.slug,
                        stepCount: detail.steps.length,
                        stepOrder: detail.steps.map((s, i) => ({ index: i, id: s.id, type: s.type })),
                      });
                      setSelectedCalculationDetail(detail);
                    }}
                  />
                )}
                
                {activeCalcTab === 'run' && (
                  <CalculationRunTab
                    projectRoot={projectRoot}
                    calculation={selectedCalculationDetail || selectedCalculationSummary}
                  />
                )}
                
                {activeCalcTab === 'analysis' && (
                  <CalculationAnalysisTab
                    projectRoot={projectRoot}
                    calculation={selectedCalculationDetail || selectedCalculationSummary}
                  />
                )}
              </div>
            </div>
          </div>
        );
        
      case 'jobs':
        return (
          <JobsPanel 
            projectRoot={projectLoaded ? projectRoot : undefined}
            onViewAnalysis={handleViewAnalysisFromJob}
          />
        );
        
      case 'history':
        return (
          <HistoryPanel 
            projectRoot={projectRoot}
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
              {currentView === 'history' && 'History'}
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
