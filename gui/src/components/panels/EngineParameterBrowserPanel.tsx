/**
 * EngineParameterBrowserPanel - Browse engine input parameters with rich metadata
 * 
 * Event-driven model: Only one effect for initial categories load.
 * All other actions (tags, search) are explicit user-driven handlers.
 * 
 * NOTE: see docs/FRONTEND_RPC_PATTERNS.md for expected call counts and effect dependencies.
 * This component is a reference implementation of the correct RPC call pattern.
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { QVResult } from '../../types/qv';
import './EngineParameterBrowserPanel.css';

// Extract types from QVResult, handling optional arrays
type EngineCategoryMeta = NonNullable<QVResult<'list_engine_parameter_metadata'>['categories']>[number];
type EngineTagMeta = NonNullable<QVResult<'list_engine_parameter_metadata'>['tags']>[number];
type GlobalSearchResult = NonNullable<QVResult<'list_engine_parameter_metadata'>['results']>[number];

interface EngineParameterBrowserPanelProps {
  engineFamily?: string;  // optional initial hint; panel derives its own default
  projectRoot?: string;
}

function normalizeError(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  return 'Unknown error';
}

const STORAGE_KEY = 'qv-reference-engine';

export function EngineParameterBrowserPanel({ engineFamily: engineFamilyProp }: EngineParameterBrowserPanelProps) {
  const qv = useQVClient();

  // Engine selection state — panel owns this, prop is just an initial hint
  const [selectedEngine, setSelectedEngine] = useState<string>(() => {
    if (engineFamilyProp) return engineFamilyProp;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return stored;
    } catch { /* ignore */ }
    return 'qe';
  });
  const [engineList, setEngineList] = useState<Array<{ engine_family: string; display_name: string }>>([]);

  // Fetch engine list on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await qv.listEngineFamilies();
        if (cancelled) return;
        if (res.ok && res.data?.engines) {
          setEngineList(res.data.engines);
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [qv]);

  // Derive engineFamily from internal state
  const engineFamily = selectedEngine;

  const handleEngineChange = useCallback((engine: string) => {
    setSelectedEngine(engine);
    try { localStorage.setItem(STORAGE_KEY, engine); } catch { /* ignore */ }
    // Reset panel state on engine change
    setCategories([]);
    setTags([]);
    setSelectedCategory(null);
    setSelectedTagKey(null);
    setSearchTerm('');
    setGlobalResults(null);
    setLastGlobalSearchTerm(null);
  }, []);

  console.debug('[EngineParamBrowser] mount', { engineFamily });

  // Simple state model - no caches, no derived objects
  const [categories, setCategories] = useState<EngineCategoryMeta[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [categoriesLoading, setCategoriesLoading] = useState(false);

  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const [tags, setTags] = useState<EngineTagMeta[]>([]);
  const [tagsError, setTagsError] = useState<string | null>(null);
  const [tagsLoading, setTagsLoading] = useState(false);

  // Reload metadata state
  const [_isReloading, _setIsReloading] = useState(false);

  // Metadata file info (path and schema version)
  const [_metadataInfo, _setMetadataInfo] = useState<{
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
  const [categorySort, setCategorySort] = useState<SortMode>('original');

  // Tag table sorting
  type TagSortDirection = 'asc' | 'desc' | 'none';
  type TagSortState = {
    column: 'name' | 'type' | 'default' | 'description' | null;
    direction: TagSortDirection;
  };
  const [tagSort, setTagSort] = useState<TagSortState>({
    column: null,
    direction: 'none',
  });

  // Selected tag row (for expanding to show full text)
  // When a row is selected, it expands vertically to show full text (wrapping enabled).
  // Non-selected rows remain compact with single-line ellipsis for overflow.
  // Clicking a selected row again deselects it.
  const [selectedTagKey, setSelectedTagKey] = useState<string | null>(null);

  // Column widths for resizable table (percentages, sum to 100)
  // Column resize adjusts two neighboring column widths in percentage space
  // while keeping table width at 100% (no horizontal scrolling).
  type TagColumnKey = 'name' | 'type' | 'default' | 'description';
  const columnOrder: TagColumnKey[] = ['name', 'type', 'default', 'description'];
  const [columnWidths, setColumnWidths] = useState<Record<TagColumnKey, number>>({
    name: 25,
    type: 15,
    default: 20,
    description: 40,
  });

  // Ref to track current selectedCategory to avoid stale closures in callbacks
  const selectedCategoryRef = useRef<string | null>(null);
  selectedCategoryRef.current = selectedCategory;

  // Refs for column resizing
  const tableRef = useRef<HTMLTableElement | null>(null);
  const tableContainerRef = useRef<HTMLDivElement | null>(null);
  type ColumnResizeState = {
    colIndex: number;
    startX: number;
    startWidths: Record<TagColumnKey, number>;
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

  // Event-driven: handle category selection and load tags
  // NOTE: We don't include selectedCategory in dependencies to avoid recreating this callback
  // The category is passed explicitly via options when needed
  const handleCategoryChange = useCallback(async (
    newCategory: string | null,
    options: { autoLoadTags?: boolean; category?: string } = {}
  ) => {
    const { autoLoadTags = false, category: categoryOverride } = options;
    
    console.debug('[EngineParamBrowser] handleCategoryChange', { newCategory, autoLoadTags, engineFamily });
        
    // Use category from options, or fall back to current selectedCategory from ref
    // This allows us to avoid selectedCategory in the dependency array
    const categoryToUse = categoryOverride || selectedCategoryRef.current;
    
    setSelectedCategory(newCategory);
    setTags([]);
    setTagsError(null);
    setSelectedTagKey(null); // Clear tag selection when category changes
    pendingParamKeyRef.current = null; // Clear pending selection

    if (!categoryToUse || !newCategory) {
      return;
    }

    if (!autoLoadTags) {
      // If we don't want to auto-load, exit here
      return;
    }

    try {
      setTagsLoading(true);
      setTagsError(null);
      
      console.debug('[EngineParamBrowser] list_engine_parameter_metadata', {
        operation: 'list_tags',
        engine_family: engineFamily,
        category: categoryToUse,
      });

      const response = await qv.listEngineParameterMetadata(engineFamily, 'list_tags', {
        category: categoryToUse,
      });

      if (!response.ok) {
        setTagsError(response.error?.message ?? 'Failed to load tags');
        setTags([]);
          return;
        }
        
      if (response.data?.tags) {
        const tagList = response.data.tags;
        setTags(tagList);
        console.debug('[EngineParamBrowser] tags loaded', {
          engineFamily,
          category: categoryToUse,
          count: tagList.length,
        });
        
        // If there's a pending tag selection, select it now that tags are loaded
        if (pendingParamKeyRef.current) {
          const tagKey = pendingParamKeyRef.current;
          console.debug('[EngineParamBrowser] selecting pending tag after load', { tagKey });
          setSelectedTagKey(tagKey);
          pendingParamKeyRef.current = null;
          }
        } else {
        setTagsError('No tags data in response');
        setTags([]);
        }
    } catch (err: unknown) {
      setTagsError(normalizeError(err));
      setTags([]);
      } finally {
      setTagsLoading(false);
        }
  }, [qv, engineFamily]); // Only depend on qv and engineFamily, not selectedCategory

        
  // Exactly one effect: load categories on mount
  useEffect(() => {
    console.debug('[EngineParamBrowser] categories effect triggered', { engineFamily });
    
    if (!engineFamily) {
      setCategories([]);
      setCategoriesError('Engine family is required');
      return;
    }
    
    let cancelled = false;
    
    (async () => {
      try {
        setCategoriesLoading(true);
        setCategoriesError(null);

        console.debug('[EngineParamBrowser] list_engine_parameter_metadata', {
          operation: 'list_categories',
          engine_family: engineFamily,
        });

        const response = await qv.listEngineParameterMetadata(engineFamily, 'list_categories');

        if (cancelled) return;

        if (!response.ok) {
          setCategoriesError(response.error?.message ?? 'Failed to load categories');
          setCategories([]);
          return;
        }
        
        const categoryList = response.data?.categories ?? [];
        setCategories(categoryList);

        // Auto-select first category ONCE if none is selected
        if (categoryList.length > 0) {
          const firstCategory = categoryList[0];
          console.debug('[EngineParamBrowser] auto-selecting first category', firstCategory);
          await handleCategoryChange(firstCategory.id, { autoLoadTags: true });
        }
      } catch (err: unknown) {
        if (cancelled) return;
        setCategoriesError(normalizeError(err));
        setCategories([]);
      } finally {
        if (!cancelled) {
          setCategoriesLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [qv, engineFamily, handleCategoryChange]); // qv is stable; handleCategoryChange is stable due to useCallback
    
  
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

  // Global search: RPC call across all categories (explicit trigger only)
  // This handler does NOT mutate category selection - it only sets globalResults
  const handleGlobalSearch = useCallback(async () => {
    const query = searchTerm.trim();
    if (!query) {
      setGlobalResults(null);
      setLastGlobalSearchTerm(null);
      setGlobalSearchError(null);
      return;
    }
    
    console.debug('[EngineParamBrowser] handleGlobalSearch', { query, engineFamily });
    setIsGlobalSearching(true);
    setGlobalSearchError(null);

    try {
      const response = await qv.listEngineParameterMetadata(engineFamily, 'search', {
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
        console.debug('[EngineParamBrowser] global search completed', {
          query,
          engineFamily,
          resultCount: results.length,
        });
      }
    } catch (err: unknown) {
      console.error('[EngineParamBrowser] global search error', err);
      setGlobalResults([]);
      setLastGlobalSearchTerm(null);
      setGlobalSearchError(
        err instanceof Error ? err.message : 'Global search failed',
      );
      setIsSearchPopoverOpen(true); // Open popover even on error so user can see it
    } finally {
      setIsGlobalSearching(false);
    }
  }, [qv, searchTerm, engineFamily]);
    
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

  // Handle global search result click - navigates to the specific category/tag
  const handleGlobalResultClick = useCallback(async (result: GlobalSearchResult) => {
    setIsSearchPopoverOpen(false); // Close popover when result is clicked
    // Construct a unique key for the result
    const resultKey = `${result.category}::${result.name}`;
    if (process.env.NODE_ENV === 'development') {
      console.debug('[EngineParamBrowser] handleGlobalResultClick start', {
        category: result.category,
        name: result.name,
        key: resultKey,
        currentCategory: selectedCategory,
      });
    }

    // Hide the global panel once the user has chosen a result
    setGlobalResults(null);
    setLastGlobalSearchTerm(null);

    // 1. Ensure correct category (load tags if needed)
    if (selectedCategory !== result.category) {
      if (process.env.NODE_ENV === 'development') {
        console.debug('[EngineParamBrowser] step 1: changing category', { from: selectedCategory, to: result.category });
      }
      await handleCategoryChange(result.category, { autoLoadTags: true });
    }

    // 2. After tags are loaded, select that tag in the main table
    const tagKey = resultKey;
    if (process.env.NODE_ENV === 'development') {
      console.debug('[EngineParamBrowser] step 2: selecting tag row', { 
        tagKey,
        selectedCategory: result.category,
        });
    }
    
    // Set pending selection - it will be applied when tags are loaded
    // (handleCategoryChange will trigger tag load and check this ref)
    pendingParamKeyRef.current = tagKey;
    
    // Also try to set it immediately in case tags are already loaded
    // (e.g., if we're just changing category)
    setSelectedTagKey(tagKey);
  }, [selectedCategory, handleCategoryChange]);


  // Note: Metadata reload functionality removed for generic engines
  // QE-specific reload can be added back if needed via engine-specific handling

  // Sort categories based on sort mode
  const sortedCategories = useMemo(() => {
    if (!categories) return [];
    switch (categorySort) {
      case 'asc':
        return [...categories].sort((a, b) => a.label.localeCompare(b.label));
      case 'desc':
        return [...categories].sort((a, b) => b.label.localeCompare(a.label));
      case 'original':
      default:
        return categories;
    }
  }, [categories, categorySort]);
  
  // Debug logging for selection changes (development only)
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[EngineParamBrowser] selectedCategory changed', selectedCategory);
    }
  }, [selectedCategory]);

  useEffect(() => {
    console.debug('[EngineParamBrowser] category sort changed', categorySort);
  }, [categorySort, sortedCategories]);

  useEffect(() => {
    console.debug('[EngineParamBrowser] tag sort changed', tagSort);
  }, [tagSort]);

  // Sort tags based on column and direction
  // Main table always shows full category tags (subject to sort, not search)
  const sortedTags = useMemo(() => {
    if (!tags || tags.length === 0) return [];
    const base = [...tags];

    if (!tagSort.column || tagSort.direction === 'none') {
      return base; // original order
    }

    const dir = tagSort.direction === 'asc' ? 1 : -1;

    return base.sort((a, b) => {
      let va: any;
      let vb: any;

      switch (tagSort.column) {
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
  }, [tags, tagSort]);

  // Cycle sort functions
  const cycleCategorySort = useCallback(() => {
    setCategorySort(prev =>
      prev === 'original' ? 'asc' :
      prev === 'asc' ? 'desc' :
      'original'
    );
  }, []);

  const cycleTagSort = useCallback((column: TagSortState['column']) => {
    setTagSort(prev => {
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

  // Render sort indicator for tag table
  const renderSortIndicator = useCallback((column: TagSortState['column']) => {
    if (tagSort.column !== column || tagSort.direction === 'none') {
      return null;
      }
    return (
      <span className="qv-sort-indicator">
        {tagSort.direction === 'asc' ? '▲' : '▼'}
      </span>
    );
  }, [tagSort]);

  // Unified sort indicator for category (matches table header style)
  const renderSortIndicatorForMode = useCallback((mode: SortMode) => {
    if (mode === 'asc') return <span className="qv-sort-indicator">▲</span>;
    if (mode === 'desc') return <span className="qv-sort-indicator">▼</span>;
    return null; // original mode shows no indicator
  }, []);


  // Handle tag row click: toggle selection (clicking selected row deselects it)
  const handleTagRowClick = useCallback((rowKey: string) => {
    setSelectedTagKey(prev => prev === rowKey ? null : rowKey);
  }, []);

  // Handle column resize start
  // Column resize adjusts two neighboring column widths in percentage space
  // while keeping table width at 100% (no horizontal scrolling).
  const handleColumnResizeStart = useCallback((
    e: React.MouseEvent<HTMLElement>,
    colKey: TagColumnKey
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

  // Scroll selected tag row into view after navigation
  // This effect runs when selectedTagKey changes or when tags are loaded
  // It finds the corresponding row in the DOM and scrolls it into view if it's offscreen
  useEffect(() => {
    if (!selectedTagKey || !tableContainerRef.current) return;

    // Use a small delay to ensure DOM has updated after tag load
    const timeoutId = setTimeout(() => {
      const container = tableContainerRef.current;
      if (!container) return;

      const row = container.querySelector<HTMLTableRowElement>(
        `tr[data-tag-key="${selectedTagKey}"]`
      );

      if (!row) return;

      const containerRect = container.getBoundingClientRect();
      const rowRect = row.getBoundingClientRect();

      const isAbove = rowRect.top < containerRect.top;
      const isBelow = rowRect.bottom > containerRect.bottom;

      if (isAbove || isBelow) {
        if (process.env.NODE_ENV === 'development') {
          console.debug('[EngineParamBrowser] scrolling tag row into view', {
            tagKey: selectedTagKey,
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
  }, [selectedTagKey, tags.length]); // Depend on tags.length to trigger after load

  // Aggregate error for display
  const displayError = globalSearchError || tagsError || categoriesError;
  
  return (
    <div className="qe-parameter-browser">
      <div className="qe-parameter-browser__header">
        <div className="qe-parameter-browser__header-top">
        <h2 className="qe-parameter-browser__title">Parameter Browser</h2>
        </div>
        <div className="qe-parameter-browser__subtitle" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <select
            value={selectedEngine}
            onChange={(e) => handleEngineChange(e.target.value)}
            className="qe-parameter-browser__engine-select"
            title="Select engine"
          >
            {engineList.length > 0 ? (
              engineList.map((eng) => (
                <option key={eng.engine_family} value={eng.engine_family}>
                  {eng.display_name}
                </option>
              ))
            ) : (
              <option value={selectedEngine}>{selectedEngine.toUpperCase()}</option>
            )}
          </select>
          <p style={{ flex: 1, margin: 0 }}>
          Browse {engineFamily.toUpperCase()} input parameters with rich metadata.
        </p>
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
                  categoriesError,
                  tagsError,
                  globalSearchError,
                  categoriesLoading,
                  tagsLoading,
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
              <div className="qe-parameter-browser__filter-group qe-parameter-browser__filter-group--category">
              <label 
                htmlFor="engine-category-select"
                className="qv-field-label qv-sortable-header"
                onClick={cycleCategorySort}
                style={{ cursor: 'pointer', margin: 0, display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Click to sort categories"
              >
                <span>Category:</span>
                {renderSortIndicatorForMode(categorySort)}
              </label>
              <select
                id="engine-category-select"
                className="qe-parameter-browser__filter-select"
                value={selectedCategory || ''}
                onChange={(e) => handleCategoryChange(e.target.value || null, { 
                  autoLoadTags: true,
                  category: e.target.value || undefined
                })}
                disabled={categoriesLoading}
                style={{ width: '200px' }}
              >
                <option value="">Select category...</option>
                {sortedCategories.map(category => (
                  <option key={category.id} value={category.id}>
                    {category.label}
                  </option>
                ))}
              </select>
            </div>
            </div>
            
            <div className="qe-parameter-browser__filters-right" ref={searchInputGroupRef} style={{ position: 'relative' }}>
              <input
                type="text"
                className="qe-parameter-browser__search-input"
                placeholder="Search all categories…"
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
                aria-label="Search all categories"
                title="Search all categories"
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
                              <th>Category</th>
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
                                  key={`${result.category}::${result.name}`}
                                  className={`qv-global-search-row ${isPrimaryMatch ? 'qv-global-result-primary' : 'qv-global-result-secondary'}`}
                                  onClick={() => handleGlobalResultClick(result)}
                                >
                                  <td>{result.category}</td>
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
          
          {/* Tag List */}
          <div className="qe-parameter-browser__parameters">
            {tagsLoading ? (
              <div className="qe-parameter-browser__loading">
                <div className="loading-spinner" />
                <p>Loading parameters...</p>
              </div>
            ) : tagsError && !tagsLoading ? (
              <div className="qe-parameter-browser__empty">
                <p>Error loading parameters: {tagsError}</p>
                <p className="qe-parameter-browser__empty-hint">
                  Category: {selectedCategory || 'none'}
                </p>
              </div>
            ) : !selectedCategory ? (
              <div className="qe-parameter-browser__empty">
                <p>Select a category to begin.</p>
              </div>
            ) : sortedTags.length === 0 ? (
              <div className="qe-parameter-browser__empty">
                <p>No parameters found for this category.</p>
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
                        onClick={() => cycleTagSort('name')} 
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
                        onClick={() => cycleTagSort('type')} 
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
                        onClick={() => cycleTagSort('default')} 
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
                        onClick={() => cycleTagSort('description')} 
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
                    {sortedTags.map((tag, i) => {
                      // Generate stable row key for selection
                      const rowKey = `${selectedCategory || ''}::${tag.name}`;
                      const isSelected = rowKey === selectedTagKey;
                      
                      // Get full text for title attributes (for hover tooltips on truncated cells)
                      const defaultText = tag.default !== null && tag.default !== undefined 
                        ? String(tag.default) 
                        : '';
                      const descriptionText = tag.description || '';

                      return (
                        <tr
                          key={i}
                          data-tag-key={rowKey}
                          className={`qv-param-row ${isSelected ? 'qv-param-row--selected' : ''}`}
                          onClick={() => handleTagRowClick(rowKey)}
                        >
                          <td className="qv-param-cell qv-param-col-name">
                          <strong>{tag.name}</strong>
                        </td>
                          <td className="qv-param-cell qv-param-col-type" title={tag.type || 'UNKNOWN'}>
                          <code>{tag.type || 'UNKNOWN'}</code>
                        </td>
                          <td className="qv-param-cell qv-param-col-default" title={defaultText}>
                          {tag.default !== null && tag.default !== undefined
                            ? <code>{String(tag.default)}</code>
                            : <span className="qe-parameter-browser__param-empty">—</span>
                          }
                        </td>
                          <td className="qv-param-cell qv-param-col-description" title={descriptionText}>
                          {tag.description
                              ? <span>{tag.description}</span>
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