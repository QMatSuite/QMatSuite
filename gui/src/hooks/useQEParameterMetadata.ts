/**
 * Shared hook for QE parameter metadata access.
 * 
 * This hook provides access to the same metadata source used by Resources view,
 * ensuring consistency across the application. The backend cache ensures efficient
 * access without duplicate loading.
 */

import { useState, useCallback, useRef } from 'react';
import { useQVClient } from './useQVClient';
import type { QVResult } from '../types/qv';

export type QEModuleMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['modules']>[number];
export type QESectionMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['sections']>[number];
export type QEParameterMeta = NonNullable<QVResult<'list_qe_parameter_metadata'>['parameters']>[number];
export type QESearchResult = NonNullable<QVResult<'list_qe_parameter_metadata'>['results']>[number];

export interface QEMetadataInfo {
  pathAbs: string | null;
  schemaVersion: number | null;
}

export interface UseQEParameterMetadataResult {
  // Modules
  modules: QEModuleMeta[];
  modulesLoading: boolean;
  modulesError: string | null;
  loadModules: () => Promise<void>;
  
  // Sections
  sections: QESectionMeta[];
  sectionsLoading: boolean;
  sectionsError: string | null;
  loadSections: (module: string) => Promise<void>;
  
  // Parameters
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
  
  // Reload
  reloadMetadata: () => Promise<void>;
  isReloading: boolean;
}

/**
 * Hook for accessing QE parameter metadata.
 * 
 * This hook provides a consistent interface for accessing QE parameter metadata
 * across the application. It uses the same RPC as Resources view, ensuring
 * cache consistency.
 */
export function useQEParameterMetadata(): UseQEParameterMetadataResult {
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
  // Key format: `${module}::${section}`
  const loadedSectionsRef = useRef<Set<string>>(new Set());
  const inFlightRef = useRef<Map<string, Promise<void>>>(new Map());
  
  // Load modules
  const loadModules = useCallback(async () => {
    setModulesLoading(true);
    setModulesError(null);
    
    try {
      const response = await qv.listQeParameterMetadata('list_modules');
      
      if (!response.ok) {
        setModulesError(response.error?.message ?? 'Failed to load modules');
        setModules([]);
        return;
      }
      
      if (response.data?.modules) {
        setModules(response.data.modules);
      } else {
        setModules([]);
      }
      
      // Update metadata info
      if (response.data) {
        setMetadataInfo({
          pathAbs: response.data.metadata_path_abs ?? null,
          schemaVersion: response.data.schema_version ?? null,
        });
      }
    } catch (err) {
      setModulesError(err instanceof Error ? err.message : 'Unknown error');
      setModules([]);
    } finally {
      setModulesLoading(false);
    }
  }, [qv]);
  
  // Load sections for a module
  const loadSections = useCallback(async (module: string) => {
    setSectionsLoading(true);
    setSectionsError(null);
    
    try {
      const response = await qv.listQeParameterMetadata('list_sections', { module });
      
      if (!response.ok) {
        setSectionsError(response.error?.message ?? 'Failed to load sections');
        setSections([]);
        return;
      }
      
      if (response.data?.sections) {
        setSections(response.data.sections);
      } else {
        setSections([]);
      }
      
      // Update metadata info
      if (response.data) {
        setMetadataInfo({
          pathAbs: response.data.metadata_path_abs ?? null,
          schemaVersion: response.data.schema_version ?? null,
        });
      }
    } catch (err) {
      setSectionsError(err instanceof Error ? err.message : 'Unknown error');
      setSections([]);
    } finally {
      setSectionsLoading(false);
    }
  }, [qv]);
  
  // Load parameters for a module and section
  // CRITICAL: This must ACCUMULATE parameters, not replace them, because multiple sections
  // are loaded (e.g., &CONTROL, &SYSTEM, &ELECTRONS). Each call should add to the existing array.
  // IDEMPOTENT: Uses loadedSectionsRef and inFlightRef to prevent duplicate RPC calls.
  const loadParameters = useCallback(async (module: string, section: string) => {
    const key = `${module}::${section}`;
    
    // Early return if already loaded
    if (loadedSectionsRef.current.has(key)) {
      console.log('[useQEParameterMetadata] loadParameters early-return (already loaded)', { module, section, key });
      return;
    }
    
    // Return existing promise if already in flight
    const existingPromise = inFlightRef.current.get(key);
    if (existingPromise) {
      console.log('[useQEParameterMetadata] loadParameters early-return (in-flight)', { module, section, key });
      return existingPromise;
    }
    
    // Create new load promise
    console.log('[useQEParameterMetadata] loadParameters calling RPC', { module, section, key });
    setParametersLoading(true);
    setParametersError(null);
    
    const loadPromise = (async () => {
      try {
        const response = await qv.listQeParameterMetadata('list_parameters', { module, section });
        
        if (!response.ok) {
          setParametersError(response.error?.message ?? 'Failed to load parameters');
          // Don't mark as loaded on error - allow retry
          return;
        }
        
        if (response.data?.parameters) {
          // ACCUMULATE: Add new parameters to existing array, avoiding duplicates
          setParameters(prev => {
            // Create a map of existing parameters by key to avoid duplicates
            const existingMap = new Map<string, QEParameterMeta>();
            prev.forEach(p => {
              const paramKey = `${p.module}::${p.section}::${p.name}`;
              existingMap.set(paramKey, p);
            });
            
            const prevSize = existingMap.size;
            
            // Add new parameters
            response.data!.parameters!.forEach(p => {
              const paramKey = `${p.module}::${p.section}::${p.name}`;
              existingMap.set(paramKey, p);
            });
            
            // Only update state if something actually changed
            if (existingMap.size === prevSize) {
              // No new parameters added, return prev to avoid re-render
              return prev;
            }
            
            return Array.from(existingMap.values());
          });
          
          // Mark as loaded only on success
          loadedSectionsRef.current.add(key);
        } else {
          // Empty response - still mark as loaded to avoid retrying
          loadedSectionsRef.current.add(key);
        }
        
        // Update metadata info
        if (response.data) {
          setMetadataInfo({
            pathAbs: response.data.metadata_path_abs ?? null,
            schemaVersion: response.data.schema_version ?? null,
          });
        }
      } catch (err) {
        setParametersError(err instanceof Error ? err.message : 'Unknown error');
        // Don't mark as loaded on error - allow retry
      } finally {
        setParametersLoading(false);
        // Remove from in-flight map
        inFlightRef.current.delete(key);
      }
    })();
    
    // Store in-flight promise
    inFlightRef.current.set(key, loadPromise);
    
    return loadPromise;
  }, [qv]);
  
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
      const response = await qv.listQeParameterMetadata('search', { query });
      
      if (!response.ok) {
        setSearchError(response.error?.message ?? 'Search failed');
        setSearchResults([]);
        return;
      }
      
      if (response.data?.results) {
        setSearchResults(response.data.results);
      } else {
        setSearchResults([]);
      }
      
      // Update metadata info
      if (response.data) {
        setMetadataInfo({
          pathAbs: response.data.metadata_path_abs ?? null,
          schemaVersion: response.data.schema_version ?? null,
        });
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Unknown error');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [qv]);
  
  // Reload metadata
  const reloadMetadata = useCallback(async () => {
    setIsReloading(true);
    
    try {
      const response = await qv.call('reload_qe_parameter_metadata', {});
      
      if (!response.ok) {
        throw new Error(response.error?.message ?? 'Failed to reload metadata');
      }
      
      // Clear loaded sections cache to allow fresh loads
      loadedSectionsRef.current.clear();
      inFlightRef.current.clear();
      
      // Update metadata info
      if (response.data) {
        setMetadataInfo({
          pathAbs: response.data.metadata_path_abs ?? null,
          schemaVersion: response.data.schema_version ?? null,
        });
      }
      
      // Reload modules
      await loadModules();
    } catch (err) {
      console.error('[useQEParameterMetadata] Failed to reload metadata', err);
      throw err;
    } finally {
      setIsReloading(false);
    }
  }, [qv, loadModules]);
  
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
  };
}

