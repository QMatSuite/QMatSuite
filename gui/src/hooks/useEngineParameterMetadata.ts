/**
 * Shared hook for engine parameter metadata access.
 *
 * This hook provides access to parameter metadata for any engine family.
 * All engines (including QE) use the generic list_engine_parameter_metadata RPC.
 * The backend routes QE requests to its specialized metadata infrastructure.
 */

import { useState, useCallback, useRef } from 'react';
import { useQVClient } from './useQVClient';

// QE metadata types (defined inline since QE-specific RPC type was removed)
export interface QEModuleMeta {
  id: string;
  label: string;
  doc_url?: string;
}

export interface QESectionMeta {
  id: string;
  name: string;
  kind: 'namelist' | 'card';
  label: string;
}

export interface QEParameterMeta {
  name: string;
  type: string | null;
  default: string | number | null;
  enum: string[] | null;
  description: string | null;
  section: string;
  module: string;
  indexing?: {
    kind: 'bounded' | 'unbounded';
    index_name: string;
    start?: number;
    end?: number;
    keyword_pattern: string;
  };
}

export interface QESearchResult {
  module: string;
  section: string;
  name: string;
  key: string;
  type: string | null;
  default: string | number | null;
  enum: string[] | null;
  description: string | null;
  indexing?: {
    kind: 'bounded' | 'unbounded';
    index_name: string;
    start?: number;
    end?: number;
    keyword_pattern: string;
  };
}

export interface QEMetadataInfo {
  pathAbs: string | null;
  schemaVersion: number | null;
}

export interface UseEngineParameterMetadataResult {
  // Modules/categories
  modules: QEModuleMeta[];
  modulesLoading: boolean;
  modulesError: string | null;
  loadModules: () => Promise<void>;

  // Sections (QE 3-level hierarchy)
  sections: QESectionMeta[];
  sectionsLoading: boolean;
  sectionsError: string | null;
  loadSections: (module: string) => Promise<void>;

  // Parameters/tags
  parameters: QEParameterMeta[];
  parametersLoading: boolean;
  parametersError: string | null;
  loadParameters: (module: string, section: string) => Promise<void>;

  // Search
  searchResults: QESearchResult[];
  searchLoading: boolean;
  searchError: string | null;
  search: (query: string) => Promise<void>;

  // Metadata info
  metadataInfo: QEMetadataInfo;

  // Reload (clear cache + reload)
  reloadMetadata: () => Promise<void>;
  isReloading: boolean;

  // Refresh (clear frontend cache, allow fresh loads)
  refresh: () => void;
}

/**
 * Hook for accessing engine parameter metadata.
 *
 * All engines use the generic list_engine_parameter_metadata RPC.
 * The daemon routes QE requests to its specialized metadata infrastructure.
 *
 * @param engineFamily - Engine family identifier (e.g., 'qe', 'vasp'). Defaults to 'qe'.
 */
export function useEngineParameterMetadata(engineFamily: string = 'qe'): UseEngineParameterMetadataResult {
  const qv = useQVClient();

  // Modules state
  const [modules, setModules] = useState<QEModuleMeta[]>([]);
  const [modulesLoading, setModulesLoading] = useState(false);
  const [modulesError, setModulesError] = useState<string | null>(null);

  // Sections state
  const [sections, setSections] = useState<QESectionMeta[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [sectionsError, setSectionsError] = useState<string | null>(null);

  // Parameters state
  const [parameters, setParameters] = useState<QEParameterMeta[]>([]);
  const [parametersLoading, setParametersLoading] = useState(false);
  const [parametersError, setParametersError] = useState<string | null>(null);

  // Search state
  const [searchResults, setSearchResults] = useState<QESearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Metadata info
  const [metadataInfo, setMetadataInfo] = useState<QEMetadataInfo>({
    pathAbs: null,
    schemaVersion: null,
  });

  // Reload state
  const [isReloading, setIsReloading] = useState(false);

  // Track loaded sections and in-flight requests to prevent duplicate loads
  const loadedSectionsRef = useRef<Set<string>>(new Set());
  const inFlightRef = useRef<Map<string, Promise<void>>>(new Map());

  // Helper to extract metadata info from response
  const updateMetadataFromResponse = useCallback((data: Record<string, unknown>) => {
    if (data) {
      setMetadataInfo({
        pathAbs: (data.metadata_path_abs as string) ?? null,
        schemaVersion: (data.schema_version as number) ?? null,
      });
    }
  }, []);

  // Load modules/categories
  const loadModules = useCallback(async () => {
    setModulesLoading(true);
    setModulesError(null);

    try {
      const response = await qv.listEngineParameterMetadata(engineFamily, 'list_categories');

      if (!response.ok) {
        setModulesError(response.error?.message ?? 'Failed to load modules');
        setModules([]);
        return;
      }

      if (response.data) {
        // QE returns 'modules', generic engines return 'categories'
        const items = (response.data as Record<string, unknown>).modules ?? (response.data as Record<string, unknown>).categories;
        if (Array.isArray(items)) {
          setModules(items.map((item: { id: string; label: string; doc_url?: string }) => ({
            id: item.id,
            label: item.label,
            doc_url: item.doc_url,
          })));
        } else {
          setModules([]);
        }
        updateMetadataFromResponse(response.data as Record<string, unknown>);
      }
    } catch (err) {
      setModulesError(err instanceof Error ? err.message : 'Unknown error');
      setModules([]);
    } finally {
      setModulesLoading(false);
    }
  }, [qv, engineFamily, updateMetadataFromResponse]);

  // Load sections for a module (QE 3-level hierarchy; other engines map to flat)
  const loadSections = useCallback(async (module: string) => {
    setSectionsLoading(true);
    setSectionsError(null);

    try {
      if (engineFamily === 'qe') {
        // QE has sections within modules
        const response = await qv.listEngineParameterMetadata(engineFamily, 'list_sections' as 'list_categories', { category: module });

        if (!response.ok) {
          setSectionsError(response.error?.message ?? 'Failed to load sections');
          setSections([]);
          return;
        }

        if (response.data) {
          const data = response.data as Record<string, unknown>;
          if (Array.isArray(data.sections)) {
            setSections(data.sections as QESectionMeta[]);
          } else {
            setSections([]);
          }
          updateMetadataFromResponse(data);
        }
      } else {
        // Non-QE: list tags for category and derive unique sections
        const response = await qv.listEngineParameterMetadata(engineFamily, 'list_tags', { category: module });

        if (!response.ok) {
          setSectionsError(response.error?.message ?? 'Failed to load sections');
          setSections([]);
          return;
        }

        if (response.data) {
          const data = response.data as Record<string, unknown>;
          if (Array.isArray(data.tags)) {
            const uniqueSections = new Map<string, QESectionMeta>();
            (data.tags as Array<{ category: string }>).forEach((tag) => {
              if (!uniqueSections.has(tag.category)) {
                uniqueSections.set(tag.category, {
                  id: tag.category,
                  name: tag.category,
                  kind: 'namelist' as const,
                  label: tag.category,
                });
              }
            });
            setSections(Array.from(uniqueSections.values()));
          } else {
            setSections([]);
          }
        }
      }
    } catch (err) {
      setSectionsError(err instanceof Error ? err.message : 'Unknown error');
      setSections([]);
    } finally {
      setSectionsLoading(false);
    }
  }, [qv, engineFamily, updateMetadataFromResponse]);

  // Load parameters for a module and section
  // CRITICAL: This must ACCUMULATE parameters, not replace them, because multiple sections
  // are loaded (e.g., &CONTROL, &SYSTEM, &ELECTRONS). Each call should add to the existing array.
  // IDEMPOTENT: Uses loadedSectionsRef and inFlightRef to prevent duplicate RPC calls.
  const loadParameters = useCallback(async (module: string, section: string) => {
    const key = `${module}::${section}`;

    // Early return if already loaded
    if (loadedSectionsRef.current.has(key)) {
      return;
    }

    // Return existing promise if already in flight
    const existingPromise = inFlightRef.current.get(key);
    if (existingPromise) {
      return existingPromise;
    }

    setParametersLoading(true);
    setParametersError(null);

    const loadPromise = (async () => {
      try {
        const response = await qv.listEngineParameterMetadata(engineFamily, 'list_tags', { category: module, section });

        if (!response.ok) {
          setParametersError(response.error?.message ?? 'Failed to load parameters');
          return;
        }

        if (response.data) {
          const data = response.data as Record<string, unknown>;
          // QE returns 'parameters', generic engines return 'tags'
          const items = data.parameters ?? data.tags;
          if (Array.isArray(items)) {
            const mappedParams: QEParameterMeta[] = items.map((item: Record<string, unknown>) => ({
              name: item.name as string,
              type: (item.type as string) ?? null,
              default: (item.default as string | number) ?? null,
              enum: (item.enum as string[]) ?? null,
              description: (item.description as string) ?? null,
              section: (item.section as string) ?? (item.category as string) ?? section,
              module: (item.module as string) ?? module,
              indexing: item.indexing as QEParameterMeta['indexing'],
            }));

            // ACCUMULATE: Add new parameters to existing array, avoiding duplicates
            setParameters(prev => {
              const existingMap = new Map<string, QEParameterMeta>();
              prev.forEach(p => {
                const paramKey = `${p.module}::${p.section}::${p.name}`;
                existingMap.set(paramKey, p);
              });

              const prevSize = existingMap.size;

              mappedParams.forEach(p => {
                const paramKey = `${p.module}::${p.section}::${p.name}`;
                existingMap.set(paramKey, p);
              });

              if (existingMap.size === prevSize) {
                return prev;
              }

              return Array.from(existingMap.values());
            });
          }

          // Mark as loaded only on success
          loadedSectionsRef.current.add(key);

          updateMetadataFromResponse(data);
        }
      } catch (err) {
        setParametersError(err instanceof Error ? err.message : 'Unknown error');
        // Don't mark as loaded on error - allow retry
      } finally {
        setParametersLoading(false);
        inFlightRef.current.delete(key);
      }
    })();

    inFlightRef.current.set(key, loadPromise);

    return loadPromise;
  }, [qv, engineFamily, updateMetadataFromResponse]);

  // Search parameters
  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    setSearchLoading(true);
    setSearchError(null);

    try {
      const response = await qv.listEngineParameterMetadata(engineFamily, 'search', { query });

      if (!response.ok) {
        setSearchError(response.error?.message ?? 'Search failed');
        setSearchResults([]);
        return;
      }

      if (response.data) {
        const data = response.data as Record<string, unknown>;
        if (Array.isArray(data.results)) {
          setSearchResults(data.results.map((r: Record<string, unknown>) => ({
            module: (r.module as string) ?? (r.category as string) ?? '',
            section: (r.section as string) ?? (r.category as string) ?? '',
            name: r.name as string,
            key: (r.key as string) ?? `${r.category ?? r.module}::${r.section ?? r.category}::${r.name}`,
            type: (r.type as string) ?? null,
            default: (r.default as string | number) ?? null,
            enum: (r.enum as string[]) ?? null,
            description: (r.description as string) ?? null,
            indexing: r.indexing as QESearchResult['indexing'],
          })));
        } else {
          setSearchResults([]);
        }

        updateMetadataFromResponse(data);
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Unknown error');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [qv, engineFamily, updateMetadataFromResponse]);

  // Reload metadata (clear frontend cache + reload modules)
  const reloadMetadata = useCallback(async () => {
    setIsReloading(true);

    try {
      // Clear loaded sections cache to allow fresh loads
      loadedSectionsRef.current.clear();
      inFlightRef.current.clear();

      // Reload modules
      await loadModules();
    } catch (err) {
      console.error('[useEngineParameterMetadata] Failed to reload metadata', err);
      throw err;
    } finally {
      setIsReloading(false);
    }
  }, [loadModules]);

  // Refresh frontend cache only
  const refresh = useCallback(() => {
    loadedSectionsRef.current.clear();
    inFlightRef.current.clear();
  }, []);

  return {
    modules,
    modulesLoading,
    modulesError,
    loadModules,
    sections,
    sectionsLoading,
    sectionsError,
    loadSections,
    parameters,
    parametersLoading,
    parametersError,
    loadParameters,
    searchResults,
    searchLoading,
    searchError,
    search,
    metadataInfo,
    reloadMetadata,
    isReloading,
    refresh,
  };
}
