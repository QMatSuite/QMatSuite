/**
 * QEParameterBrowserPanel - Browse Quantum ESPRESSO input parameters with rich metadata
 * 
 * Event-driven model: Only one effect for initial modules load.
 * All other actions (sections, parameters, search) are explicit user-driven handlers.
 * 
 * NOTE: see docs/FRONTEND_RPC_PATTERNS.md for expected call counts and effect dependencies.
 * This component is a reference implementation of the correct RPC call pattern.
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { QVResult } from '../../types/qv';
import './QEParameterBrowserPanel.css';

// Extract types from QVResult, handling optional arrays
type QEModuleMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['modules']>[number];
type QESectionMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['sections']>[number];
type QEParameterMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['parameters']>[number];
type GlobalSearchResult = NonNullable<QVResult<'list_qe_parameter_metadata'>['results']>[number];

function normalizeError(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  return 'Unknown error';
}

export function QEParameterBrowserPanel() {
  console.debug('[QEParamBrowser] mount');
  
  const qv = useQVClient();
  
  // Simple state model - no caches, no derived objects
  const [modules, setModules] = useState<QEModuleMeta[]>([]);
  const [modulesError, setModulesError] = useState<string | null>(null);
  const [modulesLoading, setModulesLoading] = useState(false);

  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  const [sections, setSections] = useState<QESectionMeta[]>([]);
  const [sectionsError, setSectionsError] = useState<string | null>(null);
  const [sectionsLoading, setSectionsLoading] = useState(false);

  const [selectedSection, setSelectedSection] = useState<string | null>(null);

  const [parameters, setParameters] = useState<QEParameterMeta[]>([]);
  const [parametersError, setParametersError] = useState<string | null>(null);
  const [parametersLoading, setParametersLoading] = useState(false);

  // Reload metadata state
  const [isReloading, setIsReloading] = useState(false);

  // Metadata file info (path and schema version)
  const [metadataInfo, setMetadataInfo] = useState<{
    pathAbs: string | null;
    schemaVersion: number | null;
  }>({
    pathAbs: null,
    schemaVersion: null,
  });

  // Search: global search only (triggered by button/Enter)
  const [searchTerm, setSearchTerm] = useState('');
  const [globalResults, setGlobalResults] = useState<GlobalSearchResult[] | null>(null);
  const [lastGlobalSearchTerm, setLastGlobalSearchTerm] = useState<string | null>(null);
  const [isGlobalSearching, setIsGlobalSearching] = useState(false);
  const [globalSearchError, setGlobalSearchError] = useState<string | null>(null);
  const [isSearchPopoverOpen, setIsSearchPopoverOpen] = useState(false);
  const searchInputGroupRef = useRef<HTMLDivElement>(null);

  // Sorting control
  type SortMode = 'original' | 'asc' | 'desc';
  const [moduleSort, setModuleSort] = useState<SortMode>('original');
  const [sectionSort, setSectionSort] = useState<SortMode>('original');

  // Parameter table sorting
  type ParamSortDirection = 'asc' | 'desc' | 'none';
  type ParamSortState = {
    column: 'name' | 'type' | 'default' | 'enum' | 'description' | null;
    direction: ParamSortDirection;
  };
  const [paramSort, setParamSort] = useState<ParamSortState>({
    column: null,
    direction: 'none',
  });

  // Selected parameter row (for expanding to show full text)
  // When a row is selected, it expands vertically to show full text (wrapping enabled).
  // Non-selected rows remain compact with single-line ellipsis for overflow.
  // Clicking a selected row again deselects it.
  const [selectedParamKey, setSelectedParamKey] = useState<string | null>(null);

  // Column widths for resizable table (percentages, sum to 100)
  // Column resize adjusts two neighboring column widths in percentage space
  // while keeping table width at 100% (no horizontal scrolling).
  type ParamColumnKey = 'name' | 'type' | 'default' | 'enum' | 'description';
  const columnOrder: ParamColumnKey[] = ['name', 'type', 'default', 'enum', 'description'];
  const [columnWidths, setColumnWidths] = useState<Record<ParamColumnKey, number>>({
    name: 18,
    type: 10,
    default: 18,
    enum: 18,
    description: 36,
  });

  // Ref to track current selectedModule to avoid stale closures in callbacks
  const selectedModuleRef = useRef<string | null>(null);
  selectedModuleRef.current = selectedModule;

  // Refs for column resizing
  const tableRef = useRef<HTMLTableElement | null>(null);
  const tableContainerRef = useRef<HTMLDivElement | null>(null);
  type ColumnResizeState = {
    colIndex: number;
    startX: number;
    startWidths: Record<ParamColumnKey, number>;
  } | null;
  const resizeStateRef = useRef<ColumnResizeState>(null);

  // Ref to track pending parameter selection after navigation from global search
  
  // Click outside handler for Popover
  useEffect(() => {
    if (!isSearchPopoverOpen) return;
    
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (searchInputGroupRef.current) {
        // Check if click is inside the search input group (including popover)
        if (!searchInputGroupRef.current.contains(target)) {
          // Click is outside the entire search group, close popover
          setIsSearchPopoverOpen(false);
        }
        // If click is inside searchInputGroupRef, keep popover open
        // (popover content is inside searchInputGroupRef, so this handles it correctly)
      }
    };
    
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsSearchPopoverOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEsc);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [isSearchPopoverOpen]);
  const pendingParamKeyRef = useRef<string | null>(null);

  // Event-driven: handle section selection
  // This needs to be defined before handleModuleChange so it can be called from there
  // NOTE: We don't include selectedModule in dependencies to avoid recreating this callback
  // The module is passed explicitly via options when needed
  const handleSectionChange = useCallback(async (
    newSection: string | null,
    options: { autoLoadParameters?: boolean; module?: string } = {}
  ) => {
    const { autoLoadParameters = false, module: moduleOverride } = options;
    
    console.debug('[QEParamBrowser] handleSectionChange', { newSection, autoLoadParameters });
    
    // Use module from options, or fall back to current selectedModule from ref
    // This allows us to avoid selectedModule in the dependency array
    const moduleToUse = moduleOverride || selectedModuleRef.current;
    
    setSelectedSection(newSection);
    setParameters([]);
    setParametersError(null);
    setSelectedParamKey(null); // Clear parameter selection when section changes
    pendingParamKeyRef.current = null; // Clear pending selection

    if (!moduleToUse || !newSection) {
      return;
    }

    if (!autoLoadParameters) {
      // If we don't want to auto-load, exit here
      return;
    }

    try {
      setParametersLoading(true);
      setParametersError(null);
      
      console.debug('[QEParamBrowser] list_qe_parameter_metadata', {
        operation: 'list_parameters',
        module: moduleToUse,
        section: newSection,
      });

      const response = await qv.call('list_qe_parameter_metadata', {
        operation: 'list_parameters',
        module: moduleToUse,
        section: newSection,
      });

      if (!response.ok) {
        setParametersError(response.error?.message ?? 'Failed to load parameters');
        setParameters([]);
        return;
      }

      if (response.data?.parameters) {
        const params = response.data.parameters;
        setParameters(params);
        console.debug('[QEParamBrowser] parameters loaded', {
          module: moduleToUse,
          section: newSection,
          count: params.length,
        });
        
        // If there's a pending parameter selection, select it now that parameters are loaded
        if (pendingParamKeyRef.current) {
          const paramKey = pendingParamKeyRef.current;
          console.debug('[QEParamBrowser] selecting pending parameter after load', { paramKey });
          setSelectedParamKey(paramKey);
          pendingParamKeyRef.current = null;
        }
      } else {
        setParametersError('No parameters data in response');
        setParameters([]);
      }
    } catch (err: unknown) {
      setParametersError(normalizeError(err));
      setParameters([]);
    } finally {
      setParametersLoading(false);
    }
  }, [qv]); // Only depend on qv, not selectedModule

  // Event-driven: handle module selection
  // Always auto-selects first section when module changes (both initial load and manual selection)
  const handleModuleChange = useCallback(async (
    newModule: string | null,
    options: { autoSelectSection?: boolean } = {}
  ) => {
    // Always auto-select section unless explicitly disabled
    const { autoSelectSection = true } = options;
    
    console.debug('[QEParamBrowser] handleModuleChange', { newModule, autoSelectSection });
    
    setSelectedModule(newModule);
    setSelectedSection(null);
    setSections([]);
    setParameters([]);
    setSectionsError(null);
    setParametersError(null);
    setSelectedParamKey(null); // Clear parameter selection when module changes
    pendingParamKeyRef.current = null; // Clear pending selection

    if (!newModule) {
      return;
    }

    // Load sections when user selects module
    try {
      setSectionsLoading(true);
      setSectionsError(null);
      
      console.debug('[QEParamBrowser] list_qe_parameter_metadata', {
        operation: 'list_sections',
        module: newModule,
      });

      const response = await qv.call('list_qe_parameter_metadata', {
        operation: 'list_sections',
        module: newModule,
      });

      if (!response.ok) {
        setSectionsError(response.error?.message ?? 'Failed to load sections');
        setSections([]);
        return;
      }

      if (response.data?.sections) {
        const sectionList = response.data.sections;
        setSections(sectionList);
        
        // Always auto-select first section and load its parameters
        if (autoSelectSection && sectionList.length > 0) {
          const firstSection = sectionList[0];
          console.debug('[QEParamBrowser] auto-selecting first section', firstSection);
          await handleSectionChange(firstSection.id, { 
            autoLoadParameters: true,
            module: newModule // Pass module explicitly to avoid state timing issues
          });
        }
      } else {
        setSectionsError('No sections data in response');
        setSections([]);
      }
    } catch (err: unknown) {
      setSectionsError(normalizeError(err));
      setSections([]);
    } finally {
      setSectionsLoading(false);
    }
  }, [qv, handleSectionChange]);

  // Exactly one effect: load modules on mount
  useEffect(() => {
    console.debug('[QEParamBrowser] modules effect triggered');
    
    let cancelled = false;
    
    (async () => {
      try {
        setModulesLoading(true);
        setModulesError(null);

        console.debug('[QEParamBrowser] list_qe_parameter_metadata', {
          operation: 'list_modules',
        });

        const response = await qv.call('list_qe_parameter_metadata', {
          operation: 'list_modules',
        });

        if (cancelled) return;

        if (!response.ok) {
          setModulesError(response.error?.message ?? 'Failed to load QE modules');
          setModules([]);
          return;
        }

        const moduleList = response.data?.modules ?? [];
        setModules(moduleList);
        
        // Update metadata info from initial load
        if (response.data) {
          setMetadataInfo({
            pathAbs: response.data.metadata_path_abs ?? null,
            schemaVersion: response.data.schema_version ?? null,
          });
        }

        // Auto-select first module ONCE if none is selected
        if (moduleList.length > 0) {
          const firstModule = moduleList[0];
          console.debug('[QEParamBrowser] auto-selecting first module', firstModule);
          await handleModuleChange(firstModule.id, { autoSelectSection: true });
        }
      } catch (err: unknown) {
        if (cancelled) return;
        setModulesError(normalizeError(err));
        setModules([]);
      } finally {
        if (!cancelled) {
          setModulesLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [qv, handleModuleChange]); // qv is stable; handleModuleChange is stable due to useCallback


  // Clear stale global results when searchTerm changes (user typing without new search)
  useEffect(() => {
    if (lastGlobalSearchTerm !== null && searchTerm !== lastGlobalSearchTerm) {
      console.debug('[QEParamBrowser] searchTerm changed, clearing stale global results', {
        lastGlobalSearchTerm,
        currentSearchTerm: searchTerm,
      });
      setGlobalResults(null);
      setLastGlobalSearchTerm(null);
    }
  }, [searchTerm, lastGlobalSearchTerm]);

  // Global search: RPC call across all modules/sections (explicit trigger only)
  // This handler does NOT mutate module/section selection - it only sets globalResults
  const handleGlobalSearch = useCallback(async () => {
    const query = searchTerm.trim();
    if (!query) {
      setGlobalResults(null);
      setLastGlobalSearchTerm(null);
      setGlobalSearchError(null);
      return;
    }

    console.debug('[QEParamBrowser] handleGlobalSearch', { query });
    setIsGlobalSearching(true);
    setGlobalSearchError(null);

    try {
      const response = await qv.call('list_qe_parameter_metadata', {
        operation: 'search',
        query,
      });

      if (!response.ok) {
        throw new Error(response.error?.message || 'Global search failed');
      }

      const results = response.data?.results ?? [];
      setGlobalResults(results);
      setLastGlobalSearchTerm(query); // Store the term that was searched
      setIsSearchPopoverOpen(true); // Open popover when search completes
      
      if (process.env.NODE_ENV === 'development') {
        console.debug('[QEParamBrowser] global search completed', {
          query,
          resultCount: results.length,
        });
      }
    } catch (err: unknown) {
      console.error('[QEParamBrowser] global search error', err);
      setGlobalResults([]);
      setLastGlobalSearchTerm(null);
      setGlobalSearchError(
        err instanceof Error ? err.message : 'Global search failed',
      );
      setIsSearchPopoverOpen(true); // Open popover even on error so user can see it
    } finally {
      setIsGlobalSearching(false);
    }
  }, [qv, searchTerm]);

  // Rank global search results: prioritize name matches over other field matches
  const rankedResults = useMemo(() => {
    if (!globalResults || globalResults.length === 0) return [];
    
    const q = lastGlobalSearchTerm?.trim().toLowerCase() || '';
    if (!q) return globalResults;

    const primary: GlobalSearchResult[] = [];
    const secondary: GlobalSearchResult[] = [];

    for (const r of globalResults) {
      const name = (r.name ?? '').toLowerCase();
      if (name && name.includes(q)) {
        primary.push(r);
      } else {
        secondary.push(r);
      }
    }

    const ranked = [...primary, ...secondary];
    console.debug('[QEParamBrowser] ranked global results', {
      query: q,
      total: globalResults.length,
      primary: primary.length,
      secondary: secondary.length,
    });
    
    return ranked;
  }, [globalResults, lastGlobalSearchTerm]);

  // Handle global search result click - navigates to the specific module/section/parameter
  const handleGlobalResultClick = useCallback(async (result: GlobalSearchResult) => {
    setIsSearchPopoverOpen(false); // Close popover when result is clicked
    if (process.env.NODE_ENV === 'development') {
      console.debug('[QEParamBrowser] handleGlobalResultClick start', { 
        module: result.module, 
        section: result.section, 
        name: result.name,
        key: result.key,
        currentModule: selectedModule,
        currentSection: selectedSection,
      });
    }
    
    // Hide the global panel once the user has chosen a result
    setGlobalResults(null);
    setLastGlobalSearchTerm(null);
    
    // 1. Ensure correct module (load sections if needed)
    if (selectedModule !== result.module) {
      if (process.env.NODE_ENV === 'development') {
        console.debug('[QEParamBrowser] step 1: changing module', { from: selectedModule, to: result.module });
      }
      await handleModuleChange(result.module, { autoSelectSection: false });
      // After module change, selectedSection will be null, so we'll always need to set section
    }

    // 2. Ensure correct section (load parameters if needed)
    // Check current section after potential module change
    const currentSectionAfterModule = selectedModule === result.module ? selectedSection : null;
    if (currentSectionAfterModule !== result.section) {
      if (process.env.NODE_ENV === 'development') {
        console.debug('[QEParamBrowser] step 2: changing section', { 
          from: currentSectionAfterModule, 
          to: result.section,
          module: result.module,
        });
      }
      await handleSectionChange(result.section, {
        module: result.module,
        autoLoadParameters: true,
      });
    }

    // 3. After parameters are loaded, select that param in the main table
    // Use the key field from the result, or construct it
    const paramKey = result.key || `${result.module}::${result.section}::${result.name}`;
    if (process.env.NODE_ENV === 'development') {
      console.debug('[QEParamBrowser] step 3: selecting parameter row', { 
        paramKey,
        selectedModule: result.module,
        selectedSection: result.section,
      });
    }
    
    // Set pending selection - it will be applied when parameters are loaded
    // (handleSectionChange will trigger parameter load and check this ref)
    pendingParamKeyRef.current = paramKey;
    
    // Also try to set it immediately in case parameters are already loaded
    // (e.g., if we're just changing section within the same module)
    setSelectedParamKey(paramKey);
  }, [selectedModule, selectedSection, handleModuleChange, handleSectionChange]);


  // Helper to reload modules after metadata reload
  // Reuses existing event-driven chain: modules → sections → parameters
  const loadModulesAfterReload = useCallback(async (
    preloadedModules?: QEModuleMeta[]
  ) => {
    // Clear selections and table state
    setSelectedModule(null);
    setSelectedSection(null);
    setSelectedParamKey(null);
    setGlobalResults(null);
    setLastGlobalSearchTerm(null);
    setParameters([]);
    setSections([]);
    setModulesError(null);
    setSectionsError(null);
    setParametersError(null);
    pendingParamKeyRef.current = null;

    // Either use modules returned by reload RPC, or re-call list_modules
    let modulesToUse = preloadedModules ?? null;
    if (!modulesToUse) {
      const res = await qv.call('list_qe_parameter_metadata', {
        operation: 'list_modules',
      });
      if (!res.ok) {
        setModulesError(res.error?.message ?? 'Failed to load modules after reload');
        setModules([]);
        return;
      }
      modulesToUse = res.data?.modules ?? [];
      
      // Update metadata info from response
      if (res.data) {
        setMetadataInfo({
          pathAbs: res.data.metadata_path_abs ?? null,
          schemaVersion: res.data.schema_version ?? null,
        });
      }
    }

    if (modulesToUse && modulesToUse.length > 0) {
      setModules(modulesToUse);
      const first = modulesToUse[0];
      await handleModuleChange(first.id, { autoSelectSection: true });
    } else {
      setModules([]);
    }
  }, [qv, handleModuleChange]);

  // Handle reload metadata button click
  const handleReloadMetadataClick = useCallback(async () => {
    if (!qv) return;

    try {
      setIsReloading(true);
      if (process.env.NODE_ENV === 'development') {
        console.debug('[QEParamBrowser] Reload metadata clicked');
      }

      // Call backend to clear metadata cache and get fresh modules
      const response = await qv.call('reload_qe_parameter_metadata', {});

      if (!response.ok) {
        throw new Error(response.error?.message ?? 'Failed to reload QE metadata');
      }

      // Update metadata info from reload response
      if (response.data) {
        setMetadataInfo({
          pathAbs: response.data.metadata_path_abs ?? null,
          schemaVersion: response.data.schema_version ?? null,
        });
      }

      // After reload, refresh modules using our existing load logic
      if (response.data?.modules) {
        await loadModulesAfterReload(response.data.modules);
      } else {
        // Fallback: reload modules manually
        await loadModulesAfterReload(undefined);
      }
    } catch (err: unknown) {
      console.error('[QEParamBrowser] Failed to reload QE metadata', err);
      // Surface error in global search error (reuse existing error display)
      setGlobalSearchError(
        err instanceof Error ? err.message : 'Failed to reload QE metadata'
      );
    } finally {
      setIsReloading(false);
    }
  }, [qv, loadModulesAfterReload]);

  // Helper to get section label from backend (raw, no extra "&" added)
  const getSectionLabel = useCallback((section: QESectionMeta): string => {
    // Use label from backend if available, fallback to name or id
    // Backend provides label with correct "&" prefix for namelists
    return section.label ?? section.name ?? section.id;
  }, []);

  // Sort modules based on sort mode
  const sortedModules = useMemo(() => {
    if (!modules) return [];
    switch (moduleSort) {
      case 'asc':
        return [...modules].sort((a, b) => a.label.localeCompare(b.label));
      case 'desc':
        return [...modules].sort((a, b) => b.label.localeCompare(a.label));
      case 'original':
      default:
        return modules;
    }
  }, [modules, moduleSort]);

  // Sort sections based on sort mode
  const sortedSections = useMemo(() => {
    if (!sections) return [];
    switch (sectionSort) {
      case 'asc':
        return [...sections].sort((a, b) => {
          const aName = (a.name || a.id).toLowerCase();
          const bName = (b.name || b.id).toLowerCase();
          return aName.localeCompare(bName);
        });
      case 'desc':
        return [...sections].sort((a, b) => {
          const aName = (a.name || a.id).toLowerCase();
          const bName = (b.name || b.id).toLowerCase();
          return bName.localeCompare(aName);
        });
      case 'original':
      default:
        return sections;
    }
  }, [sections, sectionSort]);

  // Debug logging for selection changes (development only)
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[QEParamBrowser] selectedModule changed', selectedModule, new Error().stack);
    }
  }, [selectedModule]);

  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[QEParamBrowser] selectedSection changed', selectedSection, new Error().stack);
    }
  }, [selectedSection]);

  // Log when modules/sections are sorted (must be after sortedModules/sortedSections are defined)
  useEffect(() => {
    console.debug('[QEParamBrowser] module sort changed', moduleSort);
    if (moduleSort === 'original' && sortedModules.length > 0) {
      console.debug('[QEParamBrowser] modules order (original):', sortedModules.map(m => m.id));
    }
  }, [moduleSort, sortedModules]);

  useEffect(() => {
    console.debug('[QEParamBrowser] section sort changed', sectionSort);
    if (sectionSort === 'original' && sortedSections.length > 0) {
      console.debug('[QEParamBrowser] sections order (original):', sortedSections.map(s => s.name));
    }
  }, [sectionSort, sortedSections]);

  useEffect(() => {
    console.debug('[QEParamBrowser] parameter sort changed', paramSort);
  }, [paramSort]);

  // Sort parameters based on column and direction
  // Main table always shows full section parameters (subject to sort, not search)
  const sortedParameters = useMemo(() => {
    if (!parameters || parameters.length === 0) return [];
    const base = [...parameters];

    if (!paramSort.column || paramSort.direction === 'none') {
      return base; // original order
    }

    const dir = paramSort.direction === 'asc' ? 1 : -1;

    return base.sort((a, b) => {
      let va: any;
      let vb: any;

      switch (paramSort.column) {
        case 'name':
          va = a.name ?? '';
          vb = b.name ?? '';
          break;
        case 'type':
          va = a.type ?? '';
          vb = b.type ?? '';
          break;
        case 'default':
          va = a.default ?? '';
          vb = b.default ?? '';
          break;
        case 'description':
          va = a.description ?? '';
          vb = b.description ?? '';
          break;
        case 'enum':
          // Sort by joined enum values, or empty string if no enum
          va = a.enum && a.enum.length > 0 ? a.enum.map(String).join(', ') : '';
          vb = b.enum && b.enum.length > 0 ? b.enum.map(String).join(', ') : '';
          break;
        default:
          return 0;
      }

      return va.toString().localeCompare(vb.toString()) * dir;
    });
  }, [parameters, paramSort]);

  // Cycle sort functions
  const cycleModuleSort = useCallback(() => {
    setModuleSort(prev =>
      prev === 'original' ? 'asc' :
      prev === 'asc' ? 'desc' :
      'original'
    );
  }, []);

  const cycleSectionSort = useCallback(() => {
    setSectionSort(prev =>
      prev === 'original' ? 'asc' :
      prev === 'asc' ? 'desc' :
      'original'
    );
  }, []);

  const cycleParamSort = useCallback((column: ParamSortState['column']) => {
    setParamSort(prev => {
      if (prev.column !== column) {
        // start new column with asc
        return { column, direction: 'asc' };
      }
      // same column: cycle asc -> desc -> none
      if (prev.direction === 'asc') return { column, direction: 'desc' };
      if (prev.direction === 'desc') return { column: null, direction: 'none' };
      return { column, direction: 'asc' };
    });
  }, []);

  // Render sort indicator for parameter table (unified with module/section sort)
  const renderSortIndicator = useCallback((column: ParamSortState['column']) => {
    if (paramSort.column !== column || paramSort.direction === 'none') {
      return null;
    }
    return (
      <span className="qv-sort-indicator">
        {paramSort.direction === 'asc' ? '▲' : '▼'}
      </span>
    );
  }, [paramSort]);

  // Unified sort indicator for module/section (matches table header style)
  const renderSortIndicatorForMode = useCallback((mode: SortMode) => {
    if (mode === 'asc') return <span className="qv-sort-indicator">▲</span>;
    if (mode === 'desc') return <span className="qv-sort-indicator">▼</span>;
    return null; // original mode shows no indicator
  }, []);


  // Handle parameter row click: toggle selection (clicking selected row deselects it)
  const handleParamRowClick = useCallback((rowKey: string) => {
    setSelectedParamKey(prev => prev === rowKey ? null : rowKey);
  }, []);

  // Handle column resize start
  // Column resize adjusts two neighboring column widths in percentage space
  // while keeping table width at 100% (no horizontal scrolling).
  const handleColumnResizeStart = useCallback((
    e: React.MouseEvent<HTMLElement>,
    colKey: ParamColumnKey
  ) => {
    e.preventDefault();
    e.stopPropagation();

    const colIndex = columnOrder.indexOf(colKey);
    if (colIndex === -1 || colIndex >= columnOrder.length - 1) {
      // Invalid column or last column (can't resize right edge)
      return;
    }

    resizeStateRef.current = {
      colIndex,
      startX: e.clientX,
      startWidths: { ...columnWidths },
    };

    console.debug('[ParamTable] resize start', {
      colIndex,
      colKey,
      clientX: e.clientX,
      columnWidths,
    });
  }, [columnWidths]);

  // Global mouse handlers for column resizing (via useEffect)
  // This effect attaches listeners to window to track mouse movement even if cursor leaves the table
  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      const state = resizeStateRef.current;
      if (!state) return;

      const table = tableRef.current;
      if (!table) {
        // Table not mounted, cancel resize
        resizeStateRef.current = null;
        return;
      }

      const tableRect = table.getBoundingClientRect();
      const tableWidthPx = tableRect.width || 1;

      const deltaX = e.clientX - state.startX;
      const deltaPercent = (deltaX / tableWidthPx) * 100;

      console.debug('[ParamTable] resize move', {
        colIndex: state.colIndex,
        deltaX,
        deltaPercent,
        tableWidthPx,
      });

      setColumnWidths(prev => {
        const leftIdx = state.colIndex;
        const rightIdx = state.colIndex + 1;

        if (rightIdx >= columnOrder.length) return prev;

        const leftKey = columnOrder[leftIdx];
        const rightKey = columnOrder[rightIdx];

        const min = 8; // percent
        let left = state.startWidths[leftKey] + deltaPercent;
        let right = state.startWidths[rightKey] - deltaPercent;

        // Enforce minimum widths
        if (left < min) {
          const diff = min - left;
          left = min;
          right -= diff;
        }
        if (right < min) {
          const diff = min - right;
          right = min;
          left -= diff;
        }

        const newWidths = {
          ...prev,
          [leftKey]: left,
          [rightKey]: right,
        };

        // Normalize to sum to 100% (prevent drift)
        const sum = Object.values(newWidths).reduce((a, b) => a + b, 0);
        if (Math.abs(sum - 100) > 0.01) {
          const scale = 100 / sum;
          for (const key of columnOrder) {
            newWidths[key] = newWidths[key] * scale;
          }
        }

        console.debug('[ParamTable] resize update widths', {
          leftKey,
          rightKey,
          left: newWidths[leftKey],
          right: newWidths[rightKey],
          sum: Object.values(newWidths).reduce((a, b) => a + b, 0),
        });

        return newWidths;
      });
    }

    function onMouseUp() {
      const state = resizeStateRef.current;
      if (state) {
        console.debug('[ParamTable] resize end', {
          colIndex: state.colIndex,
        });
      }
      resizeStateRef.current = null;
    }

    // Always attach listeners - they check resizeStateRef internally
    window.addEventListener('mousemove', onMouseMove, { passive: false });
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []); // Empty deps - we use refs for all state, listeners are always active

  // Scroll selected parameter row into view after navigation
  // This effect runs when selectedParamKey changes or when parameters are loaded
  // It finds the corresponding row in the DOM and scrolls it into view if it's offscreen
  useEffect(() => {
    if (!selectedParamKey || !tableContainerRef.current) return;

    // Use a small delay to ensure DOM has updated after parameter load
    const timeoutId = setTimeout(() => {
      const container = tableContainerRef.current;
      if (!container) return;

      const row = container.querySelector<HTMLTableRowElement>(
        `tr[data-param-key="${selectedParamKey}"]`
      );

      if (!row) return;

      const containerRect = container.getBoundingClientRect();
      const rowRect = row.getBoundingClientRect();

      const isAbove = rowRect.top < containerRect.top;
      const isBelow = rowRect.bottom > containerRect.bottom;

      if (isAbove || isBelow) {
        if (process.env.NODE_ENV === 'development') {
          console.debug('[QEParamBrowser] scrolling parameter row into view', {
            paramKey: selectedParamKey,
            isAbove,
            isBelow,
          });
        }
        row.scrollIntoView({
          block: 'center',
          behavior: 'smooth',
        });
      }
    }, 50); // Small delay to ensure DOM is ready

    return () => clearTimeout(timeoutId);
  }, [selectedParamKey, parameters.length]); // Depend on parameters.length to trigger after load

  // Aggregate error for display
  const displayError = globalSearchError || parametersError || sectionsError || modulesError;
  // const isLoading = modulesLoading || sectionsLoading || parametersLoading || isGlobalSearching;

  return (
    <div className="qe-parameter-browser">
      <div className="qe-parameter-browser__header">
        <div className="qe-parameter-browser__header-top">
          <h2 className="qe-parameter-browser__title">QE Parameter Browser</h2>
          <button
            type="button"
            className="qv-param-reload-button"
            onClick={handleReloadMetadataClick}
            disabled={isReloading || !qv || modulesLoading}
            title="Reload QE metadata from disk"
          >
            {isReloading ? '⏳ Reloading…' : '🔄 Reload metadata'}
          </button>
        </div>
        <div className="qe-parameter-browser__subtitle" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <p style={{ flex: 1, margin: 0 }}>
            Browse Quantum ESPRESSO input parameters with rich metadata.
          </p>
          {metadataInfo.pathAbs && (
            <span
              className="qe-parameter-browser__metadata-info"
              style={{
                fontSize: '0.75rem',
                color: 'var(--muted-foreground, #6b7280)',
                marginLeft: 'auto',
                maxWidth: '260px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={metadataInfo.pathAbs}
            >
              {(() => {
                const filename = metadataInfo.pathAbs.split(/[\\/]/).pop() ?? 'metadata';
                const version = metadataInfo.schemaVersion !== null ? `v${metadataInfo.schemaVersion}` : '';
                return version ? `${filename} · ${version}` : filename;
              })()}
            </span>
          )}
        </div>
      </div>
      
      {/* Error Display */}
      {displayError && (
        <div className="qe-parameter-browser__error">
          <span className="qe-parameter-browser__error-icon">⚠️</span>
          <div className="qe-parameter-browser__error-content">
            <span className="qe-parameter-browser__error-message">{displayError}</span>
            {process.env.NODE_ENV === 'development' && (
              <details className="qe-parameter-browser__error-details">
                <summary>Debug Info</summary>
                <pre>{JSON.stringify({ 
                  modulesError, 
                  sectionsError, 
                  parametersError, 
                  globalSearchError,
                  modulesLoading,
                  sectionsLoading,
                  parametersLoading,
                  isGlobalSearching,
                }, null, 2)}</pre>
              </details>
            )}
          </div>
        </div>
      )}
      
      {/* Filters and Parameter List */}
      <div>
          {/* Filter Controls */}
          <div className="qe-parameter-browser__filters">
            <div className="qe-parameter-browser__filters-left">
              <div className="qe-parameter-browser__filter-group qe-parameter-browser__filter-group--module">
              <label 
                htmlFor="qe-module-select"
                className="qv-field-label qv-sortable-header"
                onClick={cycleModuleSort}
                style={{ cursor: 'pointer', margin: 0, display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Click to sort modules"
              >
                <span>Module:</span>
                {renderSortIndicatorForMode(moduleSort)}
              </label>
              <select
                id="qe-module-select"
                className="qe-parameter-browser__filter-select"
                value={selectedModule || ''}
                onChange={(e) => handleModuleChange(e.target.value || null)}
                disabled={modulesLoading}
                style={{ width: '160px' }}
              >
                <option value="">Select module...</option>
                {sortedModules.map(module => (
                  <option key={module.id} value={module.id}>
                    {module.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="qe-parameter-browser__filter-group qe-parameter-browser__filter-group--section">
              <label 
                htmlFor="qe-section-select"
                className="qv-field-label qv-sortable-header"
                onClick={cycleSectionSort}
                style={{ cursor: 'pointer', margin: 0, display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Click to sort sections"
              >
                <span>Section:</span>
                {renderSortIndicatorForMode(sectionSort)}
              </label>
              <select
                id="qe-section-select"
                className="qe-parameter-browser__filter-select"
                value={selectedSection || ''}
                onChange={(e) => handleSectionChange(e.target.value || null, { 
                  autoLoadParameters: true,
                  module: selectedModule || undefined // Pass explicitly to avoid stale closure
                })}
                disabled={sectionsLoading || !selectedModule}
                style={{ flex: '0 1 360px', minWidth: '220px', maxWidth: '520px' }}
              >
                <option value="">Select section...</option>
                {sortedSections.map(section => {
                  const sectionLabel = getSectionLabel(section);
                  // Log sample sections for debugging (especially K_POINTS and SYSTEM)
                  if (sortedSections.indexOf(section) < 3 || section.name === 'K_POINTS' || section.name === 'SYSTEM') {
                    console.debug('[QEParamBrowser] section sample', { 
                      id: section.id, 
                      name: section.name, 
                      label: section.label,
                      kind: section.kind, 
                      computedLabel: sectionLabel 
                    });
                  }
                  return (
                    <option key={section.id} value={section.id}>
                      {sectionLabel} ({section.kind})
                    </option>
                  );
                })}
              </select>
            </div>
            </div>
            
            <div className="qe-parameter-browser__filters-right" ref={searchInputGroupRef} style={{ position: 'relative' }}>
              <input
                type="text"
                className="qe-parameter-browser__search-input"
                placeholder="Search all modules…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleGlobalSearch();
                  }
                }}
              />
              <button
                className="qe-parameter-browser__search-icon-button"
                onClick={handleGlobalSearch}
                disabled={isGlobalSearching || !searchTerm.trim()}
                aria-label="Search all modules"
                title="Search all modules"
              >
                {isGlobalSearching ? '⏳' : '🔍'}
              </button>
              
              {/* Popover for search results */}
              {isSearchPopoverOpen && (
                <div className="qe-search-popover-content">
                  <div className="qe-search-popover-header">
                    <span className="qe-search-popover-title">
                      {isGlobalSearching ? 'Searching…' : globalSearchError ? 'Search Error' : `Search results${lastGlobalSearchTerm ? ` for "${lastGlobalSearchTerm}"` : ''}${rankedResults.length > 0 ? ` (${rankedResults.length} matches)` : ''}`}
                    </span>
                    <button
                      className="qe-search-popover-close"
                      onClick={() => setIsSearchPopoverOpen(false)}
                      aria-label="Close search results"
                      title="Close search results"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="qe-search-popover-body">
                    {isGlobalSearching ? (
                      <div className="qv-global-search-loading">
                        <div className="loading-spinner" />
                        <span>Searching all modules…</span>
                      </div>
                    ) : globalSearchError ? (
                      <div className="qe-parameter-browser__error">
                        <span className="qe-parameter-browser__error-icon">⚠️</span>
                        <span className="qe-parameter-browser__error-message">{globalSearchError}</span>
                      </div>
                    ) : rankedResults.length === 0 ? (
                      <div className="qv-global-search-empty">
                        No matches found across modules.
                      </div>
                    ) : (
                      <div className="qv-global-search-table-container">
                        <table className="qv-global-search-table">
                          <thead>
                            <tr>
                              <th>Module</th>
                              <th>Section</th>
                              <th>Name</th>
                              <th>Type</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rankedResults.map((result) => {
                              const q = lastGlobalSearchTerm?.trim().toLowerCase() || '';
                              const name = (result.name ?? '').toLowerCase();
                              const isPrimaryMatch = name && name.includes(q);
                              
                              return (
                                <tr
                                  key={result.key || `${result.module}::${result.section}::${result.name}`}
                                  className={`qv-global-search-row ${isPrimaryMatch ? 'qv-global-result-primary' : 'qv-global-result-secondary'}`}
                                  onClick={() => handleGlobalResultClick(result)}
                                >
                                  <td>{result.module}</td>
                                  <td>{result.section}</td>
                                  <td><strong>{result.name}</strong></td>
                                  <td><code>{result.type ?? '—'}</code></td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Parameter List */}
          <div className="qe-parameter-browser__parameters">
            {parametersLoading ? (
              <div className="qe-parameter-browser__loading">
                <div className="loading-spinner" />
                <p>Loading QE parameters...</p>
              </div>
            ) : parametersError && !parametersLoading ? (
              <div className="qe-parameter-browser__empty">
                <p>Error loading parameters: {parametersError}</p>
                <p className="qe-parameter-browser__empty-hint">
                  Module: {selectedModule || 'none'}, Section: {selectedSection || 'none'}
                </p>
              </div>
            ) : !selectedModule || !selectedSection ? (
              <div className="qe-parameter-browser__empty">
                {!selectedModule ? (
                  <p>Select a module to begin.</p>
                ) : !selectedSection ? (
                  <p>Select a section to view parameters.</p>
                ) : null}
              </div>
            ) : sortedParameters.length === 0 ? (
              <div className="qe-parameter-browser__empty">
                <p>No parameters found for this section.</p>
              </div>
            ) : (
              <div className="qv-param-table-container">
                <table ref={tableRef} className="qv-param-table">
                  <colgroup>
                    {columnOrder.map((key, idx) => (
                      <col key={idx} style={{ width: `${columnWidths[key]}%` }} />
                    ))}
                  </colgroup>
                  <thead>
                    <tr>
                      <th 
                        onClick={() => cycleParamSort('name')} 
                        className="qv-sortable-header qv-param-col-name"
                        title="Click to sort by name"
                        style={{ position: 'relative' }}
                      >
                        <div className="qv-param-header-content">
                          <span>Name {renderSortIndicator('name')}</span>
                        </div>
                        <div
                          className="qv-param-col-resizer"
                          onMouseDown={(e) => handleColumnResizeStart(e, 'name')}
                          onClick={(e) => e.stopPropagation()}
                          onDragStart={(e) => e.preventDefault()}
                        />
                      </th>
                      <th 
                        onClick={() => cycleParamSort('type')} 
                        className="qv-sortable-header qv-param-col-type"
                        title="Click to sort by type"
                        style={{ position: 'relative' }}
                      >
                        <div className="qv-param-header-content">
                          <span>Type {renderSortIndicator('type')}</span>
                        </div>
                        <div
                          className="qv-param-col-resizer"
                          onMouseDown={(e) => handleColumnResizeStart(e, 'type')}
                          onClick={(e) => e.stopPropagation()}
                          onDragStart={(e) => e.preventDefault()}
                        />
                      </th>
                      <th 
                        onClick={() => cycleParamSort('default')} 
                        className="qv-sortable-header qv-param-col-default"
                        title="Click to sort by default"
                        style={{ position: 'relative' }}
                      >
                        <div className="qv-param-header-content">
                          <span>Default {renderSortIndicator('default')}</span>
                        </div>
                        <div
                          className="qv-param-col-resizer"
                          onMouseDown={(e) => handleColumnResizeStart(e, 'default')}
                          onClick={(e) => e.stopPropagation()}
                          onDragStart={(e) => e.preventDefault()}
                        />
                      </th>
                      <th 
                        onClick={() => cycleParamSort('enum')} 
                        className="qv-sortable-header qv-param-col-enum"
                        title="Click to sort by enum/range"
                        style={{ position: 'relative' }}
                      >
                        <div className="qv-param-header-content">
                          <span>Enum / Range {renderSortIndicator('enum')}</span>
                        </div>
                        <div
                          className="qv-param-col-resizer"
                          onMouseDown={(e) => handleColumnResizeStart(e, 'enum')}
                          onClick={(e) => e.stopPropagation()}
                          onDragStart={(e) => e.preventDefault()}
                        />
                      </th>
                      <th 
                        onClick={() => cycleParamSort('description')} 
                        className="qv-sortable-header qv-param-col-description"
                        title="Click to sort by description"
                        style={{ position: 'relative' }}
                      >
                        <div className="qv-param-header-content">
                          <span>Description {renderSortIndicator('description')}</span>
                        </div>
                        <div
                          className="qv-param-col-resizer"
                          onMouseDown={(e) => handleColumnResizeStart(e, 'description')}
                          onClick={(e) => e.stopPropagation()}
                          onDragStart={(e) => e.preventDefault()}
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedParameters.map((param, i) => {
                      // Generate stable row key for selection
                      const rowKey = `${selectedModule || ''}::${selectedSection || ''}::${param.name}`;
                      const isSelected = rowKey === selectedParamKey;
                      
                      // Get full text for title attributes (for hover tooltips on truncated cells)
                      const defaultText = param.default !== null && param.default !== undefined 
                        ? String(param.default) 
                        : '';
                      const enumText = param.enum && param.enum.length > 0
                        ? param.enum.map(String).join(', ')
                        : '';
                      const descriptionText = param.description || '';

                      return (
                        <tr
                          key={i}
                          data-param-key={rowKey}
                          className={`qv-param-row ${isSelected ? 'qv-param-row--selected' : ''}`}
                          onClick={() => handleParamRowClick(rowKey)}
                        >
                          <td className="qv-param-cell qv-param-col-name">
                            <strong>{param.name}</strong>
                            {param.indexing && (
                              <span className="qe-parameter-browser__array-badge">
                                Array [{param.indexing.index_name} = {param.indexing.start || '?'}
                                {param.indexing.end ? `…${param.indexing.end}` : ''}]
                              </span>
                            )}
                          </td>
                          <td className="qv-param-cell qv-param-col-type" title={param.type || 'UNKNOWN'}>
                            <code>{param.type || 'UNKNOWN'}</code>
                          </td>
                          <td className="qv-param-cell qv-param-col-default" title={defaultText}>
                            {param.default !== null && param.default !== undefined
                              ? <code>{String(param.default)}</code>
                              : <span className="qe-parameter-browser__param-empty">—</span>
                            }
                          </td>
                          <td className="qv-param-cell qv-param-col-enum" title={enumText}>
                            {param.enum && param.enum.length > 0 ? (
                              <div className="qe-parameter-browser__enum-values">
                                 {param.enum.slice(0, 3).map((val: string, j: number) => (
                                  <span key={j} className="qe-parameter-browser__enum-tag">
                                    {String(val)}
                                  </span>
                                ))}
                                {param.enum.length > 3 && (
                                  <span className="qe-parameter-browser__enum-more">
                                    +{param.enum.length - 3} more
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="qe-parameter-browser__param-empty">—</span>
                            )}
                          </td>
                          <td className="qv-param-cell qv-param-col-description" title={descriptionText}>
                            {param.description
                              ? <span>{param.description}</span>
                              : <span className="qe-parameter-browser__param-empty">—</span>
                            }
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
      </div>
    </div>
  );
}