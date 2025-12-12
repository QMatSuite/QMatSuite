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

type QEModuleMeta = QVResult<'list_qe_parameter_metadata'>['modules'] extends Array<infer T> ? T : never;
type QESectionMeta = QVResult<'list_qe_parameter_metadata'>['sections'] extends Array<infer T> ? T : never;
type QEParameterMeta = QVResult<'list_qe_parameter_metadata'>['parameters'] extends Array<infer T> ? T : never;
type SearchResult = QVResult<'list_qe_parameter_metadata'>['results'] extends Array<infer T> ? T : never;

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

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<QEParameterMeta[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Sorting control
  type SortMode = 'original' | 'asc' | 'desc';
  const [moduleSort, setModuleSort] = useState<SortMode>('original');
  const [sectionSort, setSectionSort] = useState<SortMode>('original');

  // Parameter table sorting
  type ParamSortDirection = 'asc' | 'desc' | 'none';
  type ParamSortState = {
    column: 'name' | 'type' | 'default' | 'description' | null;
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
        setParameters(response.data.parameters);
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
  const handleModuleChange = useCallback(async (
    newModule: string | null,
    options: { autoSelectSection?: boolean } = {}
  ) => {
    const { autoSelectSection = false } = options;
    
    console.debug('[QEParamBrowser] handleModuleChange', { newModule, autoSelectSection });
    
    setSelectedModule(newModule);
    setSelectedSection(null);
    setSections([]);
    setParameters([]);
    setSectionsError(null);
    setParametersError(null);
    setSelectedParamKey(null); // Clear parameter selection when module changes

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
        
        // Auto-select first section and load its parameters if requested
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


  // Event-driven: handle search
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    console.debug('[QEParamBrowser] handleSearch', searchQuery);

    try {
      setSearchLoading(true);
      setSearchError(null);
      
      console.debug('[QEParamBrowser] list_qe_parameter_metadata', {
        operation: 'search',
        query: searchQuery.trim(),
      });

      const response = await qv.call('list_qe_parameter_metadata', {
        operation: 'search',
        query: searchQuery.trim(),
      });

      if (!response.ok) {
        setSearchError(response.error?.message ?? 'Search failed');
        setSearchResults([]);
        return;
      }

      if (response.data?.results) {
        setSearchResults(response.data.results);
      } else {
        setSearchError('No search results data in response');
        setSearchResults([]);
      }
    } catch (err: unknown) {
      setSearchError(normalizeError(err));
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [qv, searchQuery]);

  // Handle search result click
  const handleSearchResultClick = useCallback((result: SearchResult) => {
    setSelectedModule(result.module);
    setSelectedSection(result.section);
    setSearchQuery('');
    setSearchResults([]);
  }, []);

  // Check if search is active
  const isSearchActive = searchQuery.trim() && searchResults.length > 0;

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
  const sortedParameters = useMemo(() => {
    if (!parameters) return [];
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

  // Render sort indicator for parameter table
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

  // Render sort icon for module/section controls (tri-state: original → asc → desc)
  const renderSortIcon = useCallback((mode: SortMode) => {
    if (mode === 'asc') return '↑';
    if (mode === 'desc') return '↓';
    return '─'; // original
  }, []);

  // Handle parameter row click: toggle selection (clicking selected row deselects it)
  const handleParamRowClick = useCallback((rowKey: string) => {
    setSelectedParamKey(prev => prev === rowKey ? null : rowKey);
  }, []);

  // Handle column resize start
  // Column resize adjusts two neighboring column widths in percentage space
  // while keeping table width at 100% (no horizontal scrolling).
  const handleColumnResizeStart = useCallback((
    e: React.MouseEvent<HTMLSpanElement>,
    colKey: ParamColumnKey
  ) => {
    e.preventDefault();
    e.stopPropagation();

    const startX = e.clientX;
    const startWidths = { ...columnWidths };

    const onMouseMove = (moveEvent: MouseEvent) => {
      const deltaPx = moveEvent.clientX - startX;
      const table = (e.currentTarget as HTMLElement).closest('table') as HTMLTableElement | null;
      if (!table) return;

      const tableRect = table.getBoundingClientRect();
      const tableWidthPx = tableRect.width || 1;

      // Convert pixel delta to percentage
      const deltaPercent = (deltaPx / tableWidthPx) * 100;

      // Resize the target column and the one to its right (if any)
      const order: ParamColumnKey[] = ['name', 'type', 'default', 'enum', 'description'];
      const idx = order.indexOf(colKey);
      const nextColKey = order[idx + 1];

      if (!nextColKey) {
        // No right neighbor, ignore resize
        return;
      }

      let newLeft = startWidths[colKey] + deltaPercent;
      let newRight = startWidths[nextColKey] - deltaPercent;

      const minWidth = 8; // percent
      newLeft = Math.max(minWidth, newLeft);
      newRight = Math.max(minWidth, newRight);

      // Update widths (small drift in total sum is acceptable)
      setColumnWidths((prev) => ({
        ...prev,
        [colKey]: newLeft,
        [nextColKey]: newRight,
      }));
    };

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [columnWidths]);

  // Aggregate error for display
  const displayError = searchError || parametersError || sectionsError || modulesError;
  const isLoading = modulesLoading || sectionsLoading || parametersLoading || searchLoading;

  return (
    <div className="qe-parameter-browser">
      <div className="qe-parameter-browser__header">
        <h2 className="qe-parameter-browser__title">QE Parameter Browser</h2>
        <p className="qe-parameter-browser__subtitle">
          Browse Quantum ESPRESSO input parameters with rich metadata.
        </p>
      </div>
      
      {/* Global Search */}
      <div className="qe-parameter-browser__search">
        <div className="qe-parameter-browser__search-input-group">
          <input
            type="text"
            className="qe-parameter-browser__search-input"
            placeholder="Search parameters (e.g., celldm, ecutwfc)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSearch();
              }
            }}
          />
          <button
            className="qe-parameter-browser__search-button"
            onClick={handleSearch}
            disabled={searchLoading || !searchQuery.trim()}
          >
            {searchLoading ? '⏳ Searching...' : '🔍 Search'}
          </button>
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
                  searchError,
                  modulesLoading,
                  sectionsLoading,
                  parametersLoading,
                  searchLoading,
                }, null, 2)}</pre>
              </details>
            )}
          </div>
        </div>
      )}
      
      {/* Search Results */}
      {isSearchActive && (
        <div className="qe-parameter-browser__search-results">
          <h3 className="qe-parameter-browser__search-results-title">
            Search results for &quot;{searchQuery}&quot; ({searchResults.length} matches)
          </h3>
          {searchResults.length === 0 ? (
            <p className="qe-parameter-browser__empty">No parameters matched your search.</p>
          ) : (
            <div className="qe-parameter-browser__search-results-list">
              {searchResults.map((result, i) => (
                <div
                  key={i}
                  className="qe-parameter-browser__search-result-item"
                  onClick={() => handleSearchResultClick(result)}
                >
                  <div className="qe-parameter-browser__search-result-header">
                    <span className="qe-parameter-browser__search-result-name">{result.name}</span>
                    <span className="qe-parameter-browser__search-result-badge">
                      {result.module} / {result.section}
                    </span>
                  </div>
                  <div className="qe-parameter-browser__search-result-details">
                    <span className="qe-parameter-browser__search-result-type">{result.type || 'UNKNOWN'}</span>
                    {result.description && (
                      <span className="qe-parameter-browser__search-result-description">
                        {result.description.substring(0, 100)}{result.description.length > 100 ? '...' : ''}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      
      {/* Filters and Parameter List */}
      {!isSearchActive && (
        <>
          {/* Filter Controls */}
          <div className="qe-parameter-browser__filters">
            <div className="qe-parameter-browser__filter-group">
              <div className="qv-row-between qv-field-label">
                <span>Module</span>
                <button
                  type="button"
                  className="qv-icon-button qv-sort-button"
                  onClick={cycleModuleSort}
                  title={`Sort modules: ${moduleSort}`}
                >
                  <span className="qv-sort-label">Sort</span>
                  <span className="qv-sort-icon">{renderSortIcon(moduleSort)}</span>
                </button>
              </div>
              <select
                className="qe-parameter-browser__filter-select"
                value={selectedModule || ''}
                onChange={(e) => handleModuleChange(e.target.value || null)}
                disabled={modulesLoading}
              >
                <option value="">Select module...</option>
                {sortedModules.map(module => (
                  <option key={module.id} value={module.id}>
                    {module.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="qe-parameter-browser__filter-group">
              <div className="qv-row-between qv-field-label">
                <span>Section</span>
                <button
                  type="button"
                  className="qv-icon-button qv-sort-button"
                  onClick={cycleSectionSort}
                  title={`Sort sections: ${sectionSort}`}
                >
                  <span className="qv-sort-label">Sort</span>
                  <span className="qv-sort-icon">{renderSortIcon(sectionSort)}</span>
                </button>
              </div>
              <select
                className="qe-parameter-browser__filter-select"
                value={selectedSection || ''}
                onChange={(e) => handleSectionChange(e.target.value || null, { 
                  autoLoadParameters: true,
                  module: selectedModule // Pass explicitly to avoid stale closure
                })}
                disabled={sectionsLoading || !selectedModule}
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
                <table className="qv-param-table">
                  <colgroup>
                    <col style={{ width: `${columnWidths.name}%` }} />
                    <col style={{ width: `${columnWidths.type}%` }} />
                    <col style={{ width: `${columnWidths.default}%` }} />
                    <col style={{ width: `${columnWidths.enum}%` }} />
                    <col style={{ width: `${columnWidths.description}%` }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th 
                        onClick={() => cycleParamSort('name')} 
                        className="qv-sortable-header qv-param-col-name"
                        title="Click to sort by name"
                      >
                        <div className="qv-param-header-inner">
                          <span>Name {renderSortIndicator('name')}</span>
                          <span
                            className="qv-param-col-resizer"
                            onMouseDown={(e) => handleColumnResizeStart(e, 'name')}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      </th>
                      <th 
                        onClick={() => cycleParamSort('type')} 
                        className="qv-sortable-header qv-param-col-type"
                        title="Click to sort by type"
                      >
                        <div className="qv-param-header-inner">
                          <span>Type {renderSortIndicator('type')}</span>
                          <span
                            className="qv-param-col-resizer"
                            onMouseDown={(e) => handleColumnResizeStart(e, 'type')}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      </th>
                      <th 
                        onClick={() => cycleParamSort('default')} 
                        className="qv-sortable-header qv-param-col-default"
                        title="Click to sort by default"
                      >
                        <div className="qv-param-header-inner">
                          <span>Default {renderSortIndicator('default')}</span>
                          <span
                            className="qv-param-col-resizer"
                            onMouseDown={(e) => handleColumnResizeStart(e, 'default')}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      </th>
                      <th className="qv-param-col-enum">
                        <div className="qv-param-header-inner">
                          <span>Enum / Range</span>
                          <span
                            className="qv-param-col-resizer"
                            onMouseDown={(e) => handleColumnResizeStart(e, 'enum')}
                          />
                        </div>
                      </th>
                      <th 
                        onClick={() => cycleParamSort('description')} 
                        className="qv-sortable-header qv-param-col-description"
                        title="Click to sort by description"
                      >
                        <div className="qv-param-header-inner">
                          <span>Description {renderSortIndicator('description')}</span>
                          <span
                            className="qv-param-col-resizer"
                            onMouseDown={(e) => handleColumnResizeStart(e, 'description')}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
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
                                {param.enum.slice(0, 3).map((val, j) => (
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
        </>
      )}
    </div>
  );
}