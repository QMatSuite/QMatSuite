/**
 * ProjectContext — Project data + CRUD
 *
 * Owns: projectRoot, summary, structures/calculations lists,
 * loading flags, rename/delete dialog state, CRUD handlers.
 *
 * Dependency: reads AppShellContext (currentView, showNotification, addToRecentProjects).
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import { normalizeProjectRoot } from '../utils/pathUtils';
import { useQMSClient } from '../hooks';
import { useAppShell } from './AppShellContext';
import type {
  ProjectSummary,
  StructureInfo,
  CalculationInfo,
} from '../types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProjectContextValue {
  // Project
  projectRoot: string;
  setProjectRoot: (v: string) => void;
  projectSummary: ProjectSummary | null;
  projectLoaded: boolean;
  projectError: string | null;
  setProjectError: (v: string | null) => void;

  // Lists
  structures: StructureInfo[] | null;
  setStructures: React.Dispatch<React.SetStateAction<StructureInfo[] | null>>;
  calculations: CalculationInfo[] | null;
  setCalculations: React.Dispatch<React.SetStateAction<CalculationInfo[] | null>>;

  // Loading
  isLoadingProject: boolean;
  isLoadingStructures: boolean;
  isLoadingCalculations: boolean;

  // Fetch
  refreshSummary: () => Promise<void>;
  fetchStructures: () => Promise<void>;
  fetchCalculations: () => Promise<CalculationInfo[] | null>;
  handleRefreshProjectRegistry: () => Promise<void>;

  // Project open/create/close
  handleOpenRecentProject: (path: string) => Promise<void>;
  handleBrowseAndLoad: () => Promise<void>;
  handleCreateProjectSuccess: (newProjectRoot: string) => Promise<void>;
  handleCloseProject: () => void;

  // CRUD dialog state
  renameStructure: StructureInfo | null;
  setRenameStructure: (v: StructureInfo | null) => void;
  deleteStructure: StructureInfo | null;
  setDeleteStructure: (v: StructureInfo | null) => void;
  renameCalculation: CalculationInfo | null;
  setRenameCalculation: (v: CalculationInfo | null) => void;
  deleteCalculation: CalculationInfo | null;
  setDeleteCalculation: (v: CalculationInfo | null) => void;
  isRenaming: boolean;
  isDeleting: boolean;

  // CRUD actions
  handleRenameStructure: (newName: string) => Promise<boolean>;
  handleDeleteStructure: (force: boolean) => Promise<boolean>;
  handleRenameCalculation: (newName: string) => Promise<boolean>;
  handleDeleteCalculation: (force: boolean) => Promise<boolean>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used within <ProjectProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { currentView, showNotification, addToRecentProjects } = useAppShell();
  const qms = useQMSClient();

  // --- Project state --------------------------------------------------------
  const [projectRoot, setProjectRoot] = useState<string>(() => {
    return localStorage.getItem('qms-project-root') || '';
  });
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);

  // --- Lists ----------------------------------------------------------------
  const [structures, setStructures] = useState<StructureInfo[] | null>(null);
  const [calculations, setCalculations] = useState<CalculationInfo[] | null>(null);

  // --- Loading flags --------------------------------------------------------
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  const [isLoadingCalculations, setIsLoadingCalculations] = useState(false);

  // --- CRUD dialog state ----------------------------------------------------
  const [renameStructure, setRenameStructure] = useState<StructureInfo | null>(null);
  const [deleteStructure, setDeleteStructure] = useState<StructureInfo | null>(null);
  const [renameCalculation, setRenameCalculation] = useState<CalculationInfo | null>(null);
  const [deleteCalculation, setDeleteCalculation] = useState<CalculationInfo | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // --- Fetch callbacks ------------------------------------------------------

  const refreshSummary = useCallback(async () => {
    if (!projectRoot || !projectLoaded) return;
    const response = await qms.getProjectSummary(projectRoot);
    if (response.ok && response.data) {
      setProjectSummary(response.data);
    }
  }, [qms, projectRoot, projectLoaded]);

  const fetchStructures = useCallback(async () => {
    if (!projectRoot || !projectLoaded) {
      console.log('[Project] fetchStructures skipped', { projectRoot: !!projectRoot, projectLoaded });
      return;
    }
    console.log('[Project] fetchStructures called', { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1), projectLoaded });
    setIsLoadingStructures(true);
    try {
      const response = await qms.listStructures(projectRoot);
      if (response.ok && response.data) {
        setStructures(response.data.structures);
      } else {
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
  }, [qms, projectRoot, projectLoaded]);

  const fetchCalculations = useCallback(async (): Promise<CalculationInfo[] | null> => {
    if (!projectRoot || !projectLoaded) {
      console.log('[Project] fetchCalculations skipped', { projectRoot: !!projectRoot, projectLoaded });
      return null;
    }
    console.log('[Project] fetchCalculations called', { projectRoot: projectRoot.substring(projectRoot.lastIndexOf('/') + 1), projectLoaded });
    setIsLoadingCalculations(true);
    try {
      const response = await qms.listCalculations(projectRoot);
      if (response.ok && response.data) {
        const calculationsList = response.data.calculations;
        setCalculations(calculationsList);
        return calculationsList;
      } else {
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
  }, [qms, projectRoot, projectLoaded]);

  const handleRefreshProjectRegistry = useCallback(async () => {
    if (!projectRoot) {
      console.warn('[Project] Refresh requested but no project root');
      return;
    }
    const normalized = normalizeProjectRoot(projectRoot);
    if (!normalized) {
      console.warn('[Project] Cannot refresh: project root normalization failed');
      return;
    }
    console.log('[Project] Refreshing project registry', { projectRoot: normalized });

    try {
      const response = await qms.rebuildProjectRegistry(normalized);

      if (response.ok && response.data) {
        const { index_stats, dag_diff } = response.data;
        console.log('[Project] Registry refreshed', index_stats);

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

        console.log('[Project]', message);
        await fetchStructures();
        await fetchCalculations();
      } else {
        console.error('[Project] Failed to refresh project registry', response.error);
        if (response.error?.code === 'project_not_found') {
          setProjectError(response.error.message || 'Project not found');
        }
      }
    } catch (err: any) {
      console.error('[Project] Failed to refresh project registry', err);
      setProjectError(err.message || 'Failed to refresh project registry');
    }
  }, [projectRoot, qms, fetchStructures, fetchCalculations]);

  // --- Auto-fetch on view change --------------------------------------------
  // CRITICAL: Intentionally excludes fetch functions and list state from deps to prevent loops.
  useEffect(() => {
    console.log('[Project] view change effect triggered', { currentView, hasStructures: !!structures, hasCalculations: !!calculations, projectLoaded });
    if (!projectLoaded) return;

    if (currentView === 'structures' && !structures) {
      fetchStructures();
    } else if (currentView === 'calculations' && !calculations) {
      fetchCalculations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentView, projectLoaded]); // Intentionally exclude structures/calculations/fetchStructures/fetchCalculations to prevent loops

  // --- Helper: load project from path ---------------------------------------
  const loadProject = useCallback(async (path: string): Promise<boolean> => {
    setProjectRoot(path);
    localStorage.setItem('qms-project-root', path);
    setIsLoadingProject(true);
    setProjectError(null);

    const response = await qms.getProjectSummary(path);
    setIsLoadingProject(false);

    if (response.ok && response.data) {
      setProjectSummary(response.data);
      setProjectLoaded(true);
      setProjectError(null);
      setStructures(null);
      setCalculations(null);
      addToRecentProjects(path);
      window.qms?.setProject?.(path);
      return true;
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
      return false;
    }
  }, [qms, addToRecentProjects]);

  // --- Project open/create/close handlers -----------------------------------

  const handleOpenRecentProject = useCallback(async (path: string) => {
    await loadProject(path);
  }, [loadProject]);

  const handleBrowseAndLoad = useCallback(async () => {
    if (!window.qms?.openDirectory) return;

    const selectedPath = await window.qms.openDirectory();
    if (!selectedPath) return;

    setIsLoadingProject(true);
    setProjectError(null);

    // First, check if selected directory is a project
    const directResponse = await qms.getProjectSummary(selectedPath);

    if (directResponse.ok && directResponse.data) {
      setProjectRoot(selectedPath);
      localStorage.setItem('qms-project-root', selectedPath);
      setProjectSummary(directResponse.data);
      setProjectLoaded(true);
      setStructures(null);
      setCalculations(null);
      addToRecentProjects(selectedPath);
      window.qms?.setProject?.(selectedPath);
      setIsLoadingProject(false);
      return;
    }

    // Not a project — search up for project root
    const findResponse = await qms.call('find_project_root', { start_dir: selectedPath });

    if (findResponse.ok && findResponse.data?.found && findResponse.data?.project_root) {
      const projectPath = findResponse.data.project_root;
      setProjectRoot(projectPath);
      localStorage.setItem('qms-project-root', projectPath);

      const parentResponse = await qms.getProjectSummary(projectPath);

      if (parentResponse.ok && parentResponse.data) {
        setProjectSummary(parentResponse.data);
        setProjectLoaded(true);
        setStructures(null);
        setCalculations(null);
        addToRecentProjects(projectPath);
        window.qms?.setProject?.(projectPath);
        setIsLoadingProject(false);
        showNotification(`Loaded project from: ${projectPath}`, 'success');
        return;
      }
    }

    setIsLoadingProject(false);

    // No project found — ask user if they want to create one
    const shouldCreate = window.confirm(
      `This folder is not a QMatSuite project.\n\nWould you like to create a new project here?\n\n${selectedPath}`
    );

    if (shouldCreate) {
      setIsLoadingProject(true);
      const createResponse = await qms.call('create_project', {
        target_dir: selectedPath,
      });

      if (createResponse.ok && createResponse.data) {
        const loadResponse = await qms.getProjectSummary(selectedPath);
        setIsLoadingProject(false);

        if (loadResponse.ok && loadResponse.data) {
          setProjectRoot(selectedPath);
          localStorage.setItem('qms-project-root', selectedPath);
          setProjectSummary(loadResponse.data);
          setProjectLoaded(true);
          setStructures(null);
          setCalculations(null);
          addToRecentProjects(selectedPath);
          showNotification('Project created successfully!', 'success');
          window.qms?.setProject?.(selectedPath);
        } else {
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
      localStorage.removeItem('qms-project-root');
    }
  }, [qms, addToRecentProjects, showNotification]);

  const handleCreateProjectSuccess = useCallback(async (newProjectRoot: string) => {
    setProjectRoot(newProjectRoot);
    localStorage.setItem('qms-project-root', newProjectRoot);
    setIsLoadingProject(true);
    setProjectError(null);

    const response = await qms.getProjectSummary(newProjectRoot);
    setIsLoadingProject(false);

    if (response.ok && response.data) {
      setProjectSummary(response.data);
      setProjectLoaded(true);
      setProjectError(null);
      setStructures(null);
      setCalculations(null);
      addToRecentProjects(newProjectRoot);
      window.qms?.setProject?.(newProjectRoot);
    } else {
      setProjectSummary(null);
      setProjectLoaded(false);
      setProjectError(response.error?.message || 'Failed to load project');
    }
  }, [qms, addToRecentProjects]);

  const handleCloseProject = useCallback(() => {
    setProjectRoot('');
    setProjectSummary(null);
    setProjectLoaded(false);
    setProjectError(null);
    setStructures(null);
    setCalculations(null);
    localStorage.removeItem('qms-project-root');
  }, []);

  // --- CRUD: Rename/Delete --------------------------------------------------

  const handleRenameStructure = useCallback(async (newName: string): Promise<boolean> => {
    if (!renameStructure) return false;
    setIsRenaming(true);
    const response = await qms.call('rename_structure', {
      project_root: projectRoot,
      selector: renameStructure.slug,
      new_name: newName,
    });
    setIsRenaming(false);

    if (response.ok) {
      showNotification(`Renamed structure to "${newName}"`, 'success');
      await fetchStructures();
      return true;
    } else {
      showNotification(`Failed to rename: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qms, projectRoot, renameStructure, fetchStructures, showNotification]);

  const handleDeleteStructure = useCallback(async (force: boolean): Promise<boolean> => {
    if (!deleteStructure) return false;
    setIsDeleting(true);
    const response = await qms.call('delete_structure', {
      project_root: projectRoot,
      selector: deleteStructure.slug,
      force: force,
    });
    setIsDeleting(false);

    if (response.ok) {
      showNotification(`Deleted structure "${deleteStructure.name}"`, 'success');
      await fetchStructures();
      await refreshSummary();
      return true;
    } else {
      showNotification(`Failed to delete: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qms, projectRoot, deleteStructure, fetchStructures, refreshSummary, showNotification]);

  const handleRenameCalculation = useCallback(async (newName: string): Promise<boolean> => {
    if (!renameCalculation) return false;
    setIsRenaming(true);
    const response = await qms.call('rename_calculation', {
      project_root: projectRoot,
      calculation_ulid: renameCalculation.calc_ulid,
      new_name: newName,
    });
    setIsRenaming(false);

    if (response.ok) {
      showNotification(`Renamed calculation to "${newName}"`, 'success');
      await fetchCalculations();
      return true;
    } else {
      showNotification(`Failed to rename: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qms, projectRoot, renameCalculation, fetchCalculations, showNotification]);

  const handleDeleteCalculation = useCallback(async (force: boolean): Promise<boolean> => {
    if (!deleteCalculation) return false;
    setIsDeleting(true);
    const response = await qms.call('delete_calculation', {
      project_root: projectRoot,
      calculation_ulid: deleteCalculation.calc_ulid,
      force: force,
    });
    setIsDeleting(false);

    if (response.ok) {
      showNotification(`Deleted calculation "${deleteCalculation.name}"`, 'success');
      await fetchCalculations();
      await refreshSummary();
      return true;
    } else {
      showNotification(`Failed to delete: ${response.error?.message || 'Unknown error'}`, 'error');
      return false;
    }
  }, [qms, projectRoot, deleteCalculation, fetchCalculations, refreshSummary, showNotification]);

  // --- Memoised context value -----------------------------------------------
  const value = useMemo<ProjectContextValue>(() => ({
    projectRoot,
    setProjectRoot,
    projectSummary,
    projectLoaded,
    projectError,
    setProjectError,
    structures,
    setStructures,
    calculations,
    setCalculations,
    isLoadingProject,
    isLoadingStructures,
    isLoadingCalculations,
    refreshSummary,
    fetchStructures,
    fetchCalculations,
    handleRefreshProjectRegistry,
    handleOpenRecentProject,
    handleBrowseAndLoad,
    handleCreateProjectSuccess,
    handleCloseProject,
    renameStructure,
    setRenameStructure,
    deleteStructure,
    setDeleteStructure,
    renameCalculation,
    setRenameCalculation,
    deleteCalculation,
    setDeleteCalculation,
    isRenaming,
    isDeleting,
    handleRenameStructure,
    handleDeleteStructure,
    handleRenameCalculation,
    handleDeleteCalculation,
  }), [
    projectRoot,
    projectSummary,
    projectLoaded,
    projectError,
    structures,
    calculations,
    isLoadingProject,
    isLoadingStructures,
    isLoadingCalculations,
    refreshSummary,
    fetchStructures,
    fetchCalculations,
    handleRefreshProjectRegistry,
    handleOpenRecentProject,
    handleBrowseAndLoad,
    handleCreateProjectSuccess,
    handleCloseProject,
    renameStructure,
    deleteStructure,
    renameCalculation,
    deleteCalculation,
    isRenaming,
    isDeleting,
    handleRenameStructure,
    handleDeleteStructure,
    handleRenameCalculation,
    handleDeleteCalculation,
  ]);

  return (
    <ProjectContext.Provider value={value}>
      {children}
    </ProjectContext.Provider>
  );
}
