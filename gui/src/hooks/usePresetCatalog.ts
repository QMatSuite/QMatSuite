/**
 * React hook for preset catalog (UI's single source of truth).
 * 
 * Per requirements:
 * - UI must not hardcode dimensions, options, or labels
 * - Catalog is fetched from backend (get_preset_catalog RPC)
 * - If catalog unavailable, show error (no fallback to hardcoded values)
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQMSClient } from './useQMSClient';

export interface PresetCatalogDimension {
  dimension: string;
  label: string;
  description: string;
  order: number;
  options: Array<{ value: string; label: string }>;
  default: string;
  scope: {
    type: 'variant_step_types' | 'variants';
    step_types?: string[];
    variants?: Array<{
      name: string;
      step_types: string[];
      notes: string;
    }>;
  };
}

export interface PresetCatalog {
  dimensions: PresetCatalogDimension[];
  schema_version: number;
}

export interface PresetCatalogHook {
  catalog: PresetCatalog | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching preset catalog from backend.
 * 
 * @example
 * function PresetsPanel() {
 *   const { catalog, isLoading, error } = usePresetCatalog();
 *   
 *   if (isLoading) return <div>Loading catalog...</div>;
 *   if (error) return <div>Error: {error}</div>;
 *   if (!catalog) return null;
 *   
 *   return (
 *     <div>
 *       {catalog.dimensions.map(dim => (
 *         <div key={dim.dimension}>
 *           <label>{dim.label}</label>
 *           <select>
 *             {dim.options.map(opt => (
 *               <option key={opt.value} value={opt.value}>{opt.label}</option>
 *             ))}
 *           </select>
 *         </div>
 *       ))}
 *     </div>
 *   );
 * }
 */
export function usePresetCatalog(): PresetCatalogHook {
  const qms = useQMSClient();
  
  const [catalog, setCatalog] = useState<PresetCatalog | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Track mounted state
  const mountedRef = useRef(true);
  
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // Fetch catalog
  const refresh = useCallback(async () => {
    if (mountedRef.current) {
      setIsLoading(true);
      setError(null);
    }
    
    try {
      const response = await qms.call('get_preset_catalog', {});
      
      if (!mountedRef.current) return;
      
      if (response.ok && response.data) {
        setCatalog(response.data as PresetCatalog);
        setIsLoading(false);
        setError(null);
      } else {
        // Check if RPC doesn't exist (old daemon)
        if (response.error?.code === 'METHOD_NOT_FOUND' || response.error?.code === 'UNKNOWN_COMMAND') {
          setError('Daemon is outdated: preset catalog not available. Please update the daemon.');
        } else {
          setError(response.error?.message || 'Failed to load preset catalog');
        }
        setIsLoading(false);
        setCatalog(null);
      }
    } catch (e) {
      if (mountedRef.current) {
        const errorMsg = e instanceof Error ? e.message : 'Unknown error';
        setError(errorMsg);
        setIsLoading(false);
        setCatalog(null);
      }
    }
  }, [qms]);
  
  // Auto-fetch on mount
  useEffect(() => {
    refresh();
  }, [refresh]);
  
  return {
    catalog,
    isLoading,
    error,
    refresh,
  };
}

