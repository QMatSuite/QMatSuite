/**
 * QEParameterBrowserPanel - Browse Quantum ESPRESSO input parameters with rich metadata
 * 
 * Features:
 * - Global search across all parameters
 * - Module and section selectors
 * - Scrollable parameter list with type/default/enum/description
 * - Array parameter indexing info
 * - Client-side caching for performance
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { QVResult } from '../../types/qv';
import './QEParameterBrowserPanel.css';

type ModuleInfo = QVResult<'list_qe_parameter_metadata'>['modules'] extends Array<infer T> ? T : never;
type SectionInfo = QVResult<'list_qe_parameter_metadata'>['sections'] extends Array<infer T> ? T : never;
type ParameterInfo = QVResult<'list_qe_parameter_metadata'>['parameters'] extends Array<infer T> ? T : never;
type SearchResult = QVResult<'list_qe_parameter_metadata'>['results'] extends Array<infer T> ? T : never;

export function QEParameterBrowserPanel() {
  const qv = useQVClient();
  
  // Request tracking to prevent stale responses
  const modulesRequestIdRef = useRef(0);
  const sectionsRequestIdRef = useRef(0);
  const parametersRequestIdRef = useRef(0);
  const searchRequestIdRef = useRef(0);
  
  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Loading states
  const [isLoadingModules, setIsLoadingModules] = useState(false);
  const [isLoadingSections, setIsLoadingSections] = useState(false);
  const [isLoadingParameters, setIsLoadingParameters] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  
  // Data cache
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [sectionsCache, setSectionsCache] = useState<Record<string, SectionInfo[]>>({});
  const [parametersCache, setParametersCache] = useState<Record<string, ParameterInfo[]>>({});
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  
  // Load modules on mount (only once)
  useEffect(() => {
    const requestId = ++modulesRequestIdRef.current;
    
    console.log('[QEParameterBrowser] effect fired: loadModules', { requestId });
    
    const loadModules = async () => {
      setIsLoadingModules(true);
      setError(null);
      
      try {
        console.log('[IPC] list_qe_parameter_metadata', { operation: 'list_modules', requestId });
        const response = await qv.listQeParameterMetadata('list_modules');
        
        // Ignore stale responses
        if (requestId !== modulesRequestIdRef.current) {
          console.log('[QEParameterBrowser] ignoring stale modules response', { requestId, current: modulesRequestIdRef.current });
          return;
        }
        
        if (response.ok && response.data?.modules) {
          setModules(response.data.modules);
          // Auto-select first module (or 'pw' if available)
          const pwModule = response.data.modules.find(m => m.id === 'pw');
          if (pwModule || response.data.modules.length > 0) {
            setSelectedModule(pwModule?.id || response.data.modules[0].id);
          }
        } else {
          // RPC failed - stop loading and show error
          const errorMsg = response.error?.message || 'Failed to load modules';
          setError(errorMsg);
          console.error('[QEParameterBrowser] Failed to load modules:', response.error);
        }
      } catch (e) {
        // Ignore stale responses
        if (requestId !== modulesRequestIdRef.current) {
          return;
        }
        // Network or unexpected error - stop loading and show error
        const errorMsg = e instanceof Error ? e.message : 'Failed to load modules';
        setError(errorMsg);
        console.error('[QEParameterBrowser] Exception loading modules:', e);
      } finally {
        // Only update loading state if this is still the current request
        if (requestId === modulesRequestIdRef.current) {
          setIsLoadingModules(false);
        }
      }
    };
    
    loadModules();
  }, [qv]); // Only depend on qv client, modules list loads once on mount
  
  // Load sections when module changes (with caching)
  useEffect(() => {
    if (!selectedModule) {
      // No module selected: clear section
      setSelectedSection(null);
      return;
    }
    
    const requestId = ++sectionsRequestIdRef.current;
    
    console.log('[QEParameterBrowser] effect fired: loadSections', { 
      module: selectedModule, 
      requestId 
    });
    
    // Check cache first
    const cachedSections = sectionsCache[selectedModule];
    if (cachedSections) {
      console.log('[QEParameterBrowser] using cached sections', { module: selectedModule });
      // Auto-select first section if none selected
      if (!selectedSection && cachedSections.length > 0) {
        setSelectedSection(cachedSections[0].id);
      }
      return;
    }
    
    const loadSections = async () => {
      setIsLoadingSections(true);
      setError(null);
      
      try {
        console.log('[IPC] list_qe_parameter_metadata', { 
          operation: 'list_sections', 
          module: selectedModule,
          requestId 
        });
        const response = await qv.listQeParameterMetadata('list_sections', { module: selectedModule });
        
        // Ignore stale responses
        if (requestId !== sectionsRequestIdRef.current) {
          console.log('[QEParameterBrowser] ignoring stale sections response', { requestId, current: sectionsRequestIdRef.current });
          return;
        }
        
        if (response.ok && response.data?.sections) {
          setSectionsCache(prev => ({ ...prev, [selectedModule]: response.data!.sections! }));
          // Auto-select first section
          if (response.data.sections.length > 0) {
            setSelectedSection(response.data.sections[0].id);
          }
        } else {
          // RPC failed - stop loading and show error
          const errorMsg = response.error?.message || 'Failed to load sections';
          setError(errorMsg);
          console.error('[QEParameterBrowser] Failed to load sections:', response.error);
        }
      } catch (e) {
        // Ignore stale responses
        if (requestId !== sectionsRequestIdRef.current) {
          return;
        }
        // Network or unexpected error - stop loading and show error
        const errorMsg = e instanceof Error ? e.message : 'Failed to load sections';
        setError(errorMsg);
        console.error('[QEParameterBrowser] Exception loading sections:', e);
      } finally {
        // Only update loading state if this is still the current request
        if (requestId === sectionsRequestIdRef.current) {
          setIsLoadingSections(false);
        }
      }
    };
    
    loadSections();
    // CRITICAL: Only depend on selectedModule and qv - NOT sectionsCache or selectedSection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModule, qv]);
  
  // Load parameters when module/section changes (with caching)
  useEffect(() => {
    if (!selectedModule || !selectedSection) {
      // Clear parameters if no module/section selected
      return;
    }
    
    const requestId = ++parametersRequestIdRef.current;
    const cacheKey = `${selectedModule}:${selectedSection}`;
    
    console.log('[QEParameterBrowser] effect fired: loadParameters', { 
      module: selectedModule, 
      section: selectedSection,
      cacheKey,
      requestId 
    });
    
    // Check cache first
    const cachedParameters = parametersCache[cacheKey];
    if (cachedParameters) {
      console.log('[QEParameterBrowser] using cached parameters', { cacheKey });
      return;
    }
    
    const loadParameters = async () => {
      setIsLoadingParameters(true);
      setError(null);
      
      try {
        console.log('[IPC] list_qe_parameter_metadata', { 
          operation: 'list_parameters', 
          module: selectedModule,
          section: selectedSection,
          requestId 
        });
        const response = await qv.listQeParameterMetadata('list_parameters', {
          module: selectedModule,
          section: selectedSection,
        });
        
        // Ignore stale responses
        if (requestId !== parametersRequestIdRef.current) {
          console.log('[QEParameterBrowser] ignoring stale parameters response', { requestId, current: parametersRequestIdRef.current });
          return;
        }
        
        if (response.ok && response.data?.parameters) {
          setParametersCache(prev => ({ ...prev, [cacheKey]: response.data!.parameters! }));
        } else {
          // RPC failed - stop loading and show error
          const errorMsg = response.error?.message || 'Failed to load parameters';
          setError(errorMsg);
          console.error('[QEParameterBrowser] Failed to load parameters:', response.error);
        }
      } catch (e) {
        // Ignore stale responses
        if (requestId !== parametersRequestIdRef.current) {
          return;
        }
        // Network or unexpected error - stop loading and show error
        const errorMsg = e instanceof Error ? e.message : 'Failed to load parameters';
        setError(errorMsg);
        console.error('[QEParameterBrowser] Exception loading parameters:', e);
      } finally {
        // Only update loading state if this is still the current request
        if (requestId === parametersRequestIdRef.current) {
          setIsLoadingParameters(false);
        }
      }
    };
    
    loadParameters();
    // CRITICAL: Only depend on selectedModule, selectedSection, and qv - NOT parametersCache
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModule, selectedSection, qv]);
  
  // Handle search
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    
    const requestId = ++searchRequestIdRef.current;
    
    console.log('[QEParameterBrowser] handleSearch called', { 
      query: searchQuery,
      requestId 
    });
    
    setIsSearching(true);
    setError(null);
    
    try {
      console.log('[IPC] list_qe_parameter_metadata', { 
        operation: 'search', 
        query: searchQuery,
        requestId 
      });
      const response = await qv.listQeParameterMetadata('search', { query: searchQuery });
      
      // Ignore stale responses
      if (requestId !== searchRequestIdRef.current) {
        console.log('[QEParameterBrowser] ignoring stale search response', { requestId, current: searchRequestIdRef.current });
        return;
      }
      
      if (response.ok && response.data?.results) {
        setSearchResults(response.data.results);
      } else {
        // RPC failed - stop loading and show error
        const errorMsg = response.error?.message || 'Search failed';
        setError(errorMsg);
        setSearchResults([]);
        console.error('[QEParameterBrowser] Search failed:', response.error);
      }
    } catch (e) {
      // Ignore stale responses
      if (requestId !== searchRequestIdRef.current) {
        return;
      }
      // Network or unexpected error - stop loading and show error
      const errorMsg = e instanceof Error ? e.message : 'Search failed';
      setError(errorMsg);
      setSearchResults([]);
      console.error('[QEParameterBrowser] Exception during search:', e);
    } finally {
      // Only update loading state if this is still the current request
      if (requestId === searchRequestIdRef.current) {
        setIsSearching(false);
      }
    }
  }, [searchQuery, qv]);
  
  // Handle search result click
  const handleSearchResultClick = useCallback((result: SearchResult) => {
    setSelectedModule(result.module);
    setSelectedSection(result.section);
    setSearchQuery('');
    setSearchResults(null);
  }, []);
  
  // Get current sections and parameters from cache
  const currentSections = selectedModule ? sectionsCache[selectedModule] || [] : [];
  const currentParameters = selectedModule && selectedSection
    ? parametersCache[`${selectedModule}:${selectedSection}`] || []
    : [];
  
  // Check if search is active
  const isSearchActive = searchQuery.trim() && searchResults !== null;
  
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
            disabled={isSearching || !searchQuery.trim()}
          >
            {isSearching ? '⏳ Searching...' : '🔍 Search'}
          </button>
        </div>
      </div>
      
      {/* Error Display */}
      {error && (
        <div className="qe-parameter-browser__error">
          <span className="qe-parameter-browser__error-icon">⚠️</span>
          <div className="qe-parameter-browser__error-content">
            <span className="qe-parameter-browser__error-message">{error}</span>
            {process.env.NODE_ENV === 'development' && (
              <details className="qe-parameter-browser__error-details">
                <summary>Debug Info</summary>
                <pre>{JSON.stringify({ error, isLoadingModules, isLoadingSections, isLoadingParameters, isSearching }, null, 2)}</pre>
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
              <label className="qe-parameter-browser__filter-label">Module</label>
              <select
                className="qe-parameter-browser__filter-select"
                value={selectedModule || ''}
                onChange={(e) => {
                  setSelectedModule(e.target.value || null);
                  setSelectedSection(null); // Clear section when module changes
                }}
                disabled={isLoadingModules}
              >
                <option value="">Select module...</option>
                {modules.map(module => (
                  <option key={module.id} value={module.id}>
                    {module.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="qe-parameter-browser__filter-group">
              <label className="qe-parameter-browser__filter-label">Section</label>
              <select
                className="qe-parameter-browser__filter-select"
                value={selectedSection || ''}
                onChange={(e) => setSelectedSection(e.target.value || null)}
                disabled={isLoadingSections || !selectedModule}
              >
                <option value="">Select section...</option>
                {currentSections.map(section => (
                  <option key={section.id} value={section.id}>
                    {section.label} ({section.kind})
                  </option>
                ))}
              </select>
            </div>
          </div>
          
          {/* Parameter List */}
          <div className="qe-parameter-browser__parameters">
            {isLoadingParameters ? (
              <div className="qe-parameter-browser__loading">
                <div className="loading-spinner" />
                <p>Loading QE parameters...</p>
              </div>
            ) : error && !isLoadingParameters ? (
              <div className="qe-parameter-browser__empty">
                <p>Error loading parameters: {error}</p>
                <p className="qe-parameter-browser__empty-hint">
                  Module: {selectedModule || 'none'}, Section: {selectedSection || 'none'}
                </p>
              </div>
            ) : !selectedModule || !selectedSection ? (
              <div className="qe-parameter-browser__empty">
                Select a module and section to view parameters.
              </div>
            ) : currentParameters.length === 0 ? (
              <div className="qe-parameter-browser__empty">
                No parameters found for this section.
              </div>
            ) : (
              <div className="qe-parameter-browser__parameters-table-container">
                <table className="qe-parameter-browser__parameters-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Default</th>
                      <th>Enum / Range</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentParameters.map((param, i) => (
                      <tr key={i}>
                        <td className="qe-parameter-browser__param-name">
                          <strong>{param.name}</strong>
                          {param.indexing && (
                            <span className="qe-parameter-browser__array-badge">
                              Array [{param.indexing.index_name} = {param.indexing.start || '?'}
                              {param.indexing.end ? `…${param.indexing.end}` : ''}]
                            </span>
                          )}
                        </td>
                        <td className="qe-parameter-browser__param-type">
                          <code>{param.type || 'UNKNOWN'}</code>
                        </td>
                        <td className="qe-parameter-browser__param-default">
                          {param.default !== null && param.default !== undefined
                            ? <code>{String(param.default)}</code>
                            : <span className="qe-parameter-browser__param-empty">—</span>
                          }
                        </td>
                        <td className="qe-parameter-browser__param-enum">
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
                        <td className="qe-parameter-browser__param-description">
                          {param.description
                            ? <span title={param.description}>{param.description.substring(0, 150)}{param.description.length > 150 ? '...' : ''}</span>
                            : <span className="qe-parameter-browser__param-empty">—</span>
                          }
                        </td>
                      </tr>
                    ))}
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
