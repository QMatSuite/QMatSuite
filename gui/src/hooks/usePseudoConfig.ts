/**
 * usePseudoConfig - Hook for managing pseudopotential configuration
 * 
 * Provides:
 * - Configuration state (store_dir, seed_dir, allow_download)
 * - Actions for validation, initialization, and installation
 * - Loading state for async operations
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { QVResult } from '../types/qv';

export interface PseudoConfig {
  store_dir: string;
  seed_dir: string;
  allow_download: boolean;
  repo_pseudo_dir: string;
  default_store_dir: string;
  default_seed_dir: string;
}

export interface PseudoValidationResult {
  ok: boolean;
  repo_pseudo_exists: boolean;
  store_dir_exists: boolean;
  store_dir_writable: boolean;
  seed_dir_exists: boolean;
  seed_has_sssp: boolean;
  messages: string[];
  warnings: string[];
  errors: string[];
}

export interface SSSPLibraryInfo {
  version: string;
  flavor: string;
  installed: boolean;
  path: string | null;
  file_count: number;
  has_cutoffs: boolean;
  has_manifest: boolean;
}

export interface DownloadResult {
  success: boolean;
  messages: string[];
  errors: string[];
  warnings: string[];
}

export interface UsePseudoConfigResult {
  // State
  config: PseudoConfig | null;
  isLoading: boolean;
  isDownloading: boolean;
  error: string | null;
  
  // Validation
  validationResult: PseudoValidationResult | null;
  isValidating: boolean;
  
  // Installed libraries
  installedLibraries: SSSPLibraryInfo[];
  
  // Actions
  loadConfig: () => Promise<void>;
  updateConfig: (updates: Partial<Pick<PseudoConfig, 'store_dir' | 'seed_dir' | 'allow_download'>>) => Promise<void>;
  resetToDefaults: () => Promise<void>;
  validate: () => Promise<PseudoValidationResult | null>;
  initDirs: () => Promise<{ success: boolean; messages: string[]; errors: string[] }>;
  installFromSeed: (version?: string, flavor?: string) => Promise<{ success: boolean; messages: string[] }>;
  listInstalledLibraries: () => Promise<void>;
  
  // Download actions
  downloadLibrary: (flavor: 'efficiency' | 'precision', force?: boolean) => Promise<DownloadResult>;
  downloadAll: (force?: boolean) => Promise<DownloadResult>;
}

export function usePseudoConfig(): UsePseudoConfigResult {
  const [config, setConfig] = useState<PseudoConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<PseudoValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [installedLibraries, setInstalledLibraries] = useState<SSSPLibraryInfo[]>([]);
  
  // Track if we've loaded initially
  const hasLoadedRef = useRef(false);
  
  // Concurrency lock for downloads (prevent multiple simultaneous downloads)
  const downloadInFlightRef = useRef(false);
  
  const loadConfig = useCallback(async () => {
    if (!window.qv) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<QVResult<'get_pseudo_config'>>('get_pseudo_config', {});
      if (response.ok && response.data) {
        setConfig(response.data);
      } else {
        setError(response.error?.message || 'Failed to load pseudo config');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pseudo config');
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const updateConfig = useCallback(async (
    updates: Partial<Pick<PseudoConfig, 'store_dir' | 'seed_dir' | 'allow_download'>>
  ) => {
    if (!window.qv) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<QVResult<'set_pseudo_config'>>('set_pseudo_config', updates);
      if (response.ok && response.data) {
        setConfig(response.data);
      } else {
        setError(response.error?.message || 'Failed to update pseudo config');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update pseudo config');
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const resetToDefaults = useCallback(async () => {
    if (!config) return;
    
    await updateConfig({
      store_dir: config.default_store_dir,
      seed_dir: config.default_seed_dir,
      allow_download: false,
    });
  }, [config, updateConfig]);
  
  const validate = useCallback(async (): Promise<PseudoValidationResult | null> => {
    if (!window.qv) return null;
    
    setIsValidating(true);
    
    try {
      const response = await window.qv.request<QVResult<'validate_pseudo_config'>>('validate_pseudo_config', {});
      if (response.ok && response.data) {
        setValidationResult(response.data);
        return response.data;
      } else {
        setError(response.error?.message || 'Failed to validate pseudo config');
        return null;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to validate pseudo config');
      return null;
    } finally {
      setIsValidating(false);
    }
  }, []);
  
  const initDirs = useCallback(async (): Promise<{ success: boolean; messages: string[]; errors: string[] }> => {
    if (!window.qv) return { success: false, messages: [], errors: ['No connection'] };
    
    setIsLoading(true);
    
    try {
      const response = await window.qv.request<QVResult<'init_pseudo_dirs'>>('init_pseudo_dirs', {});
      if (response.ok && response.data) {
        const result = {
          success: response.data.store_dir_created || response.data.seed_dir_created,
          messages: response.data.messages,
          errors: response.data.errors,
        };
        // Refresh validation after init
        await validate();
        return result;
      } else {
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Failed to init dirs'],
        };
      }
    } catch (e) {
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Failed to init dirs'],
      };
    } finally {
      setIsLoading(false);
    }
  }, [validate]);
  
  const installFromSeed = useCallback(async (
    version?: string,
    flavor?: string
  ): Promise<{ success: boolean; messages: string[] }> => {
    if (!window.qv) return { success: false, messages: ['No connection'] };
    
    setIsLoading(true);
    
    try {
      const response = await window.qv.request<QVResult<'install_seed_to_store'>>(
        'install_seed_to_store',
        { version, flavor }
      );
      if (response.ok && response.data) {
        // Refresh installed libraries after install
        await listInstalledLibraries();
        return {
          success: response.data.success,
          messages: response.data.messages,
        };
      } else {
        return {
          success: false,
          messages: [response.error?.message || 'Failed to install from seed'],
        };
      }
    } catch (e) {
      return {
        success: false,
        messages: [e instanceof Error ? e.message : 'Failed to install from seed'],
      };
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const listInstalledLibraries = useCallback(async () => {
    if (!window.qv) return;
    
    try {
      const response = await window.qv.request<QVResult<'list_installed_sssp'>>('list_installed_sssp', {});
      if (response.ok && response.data) {
        setInstalledLibraries(response.data.libraries);
      }
    } catch (e) {
      console.error('Failed to list installed SSSP:', e);
    }
  }, []);
  
  const downloadLibrary = useCallback(async (
    flavor: 'efficiency' | 'precision',
    force: boolean = false
  ): Promise<DownloadResult> => {
    if (!window.qv) return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    
    // Concurrency guard: prevent multiple simultaneous downloads
    if (downloadInFlightRef.current) {
      return {
        success: false,
        messages: [],
        errors: ['Another download is already in progress'],
        warnings: [],
      };
    }
    
    downloadInFlightRef.current = true;
    setIsDownloading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<QVResult<'download_sssp_library'>>(
        'download_sssp_library',
        { flavor, force }
      );
      if (response.ok && response.data) {
        // Update installed libraries from response
        if (response.data.installed_libraries) {
          setInstalledLibraries(response.data.installed_libraries);
        }
        return {
          success: response.data.success,
          messages: response.data.messages,
          errors: response.data.errors,
          warnings: response.data.warnings,
        };
      } else {
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Download failed'],
          warnings: [],
        };
      }
    } catch (e) {
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Download failed'],
        warnings: [],
      };
    } finally {
      downloadInFlightRef.current = false;
      setIsDownloading(false);
    }
  }, []);
  
  const downloadAll = useCallback(async (
    force: boolean = false
  ): Promise<DownloadResult> => {
    if (!window.qv) return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    
    // Concurrency guard: prevent multiple simultaneous downloads
    if (downloadInFlightRef.current) {
      return {
        success: false,
        messages: [],
        errors: ['Another download is already in progress'],
        warnings: [],
      };
    }
    
    downloadInFlightRef.current = true;
    setIsDownloading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<QVResult<'download_all_sssp'>>(
        'download_all_sssp',
        { force }
      );
      if (response.ok && response.data) {
        // Update installed libraries from response
        if (response.data.installed_libraries) {
          setInstalledLibraries(response.data.installed_libraries);
        }
        return {
          success: response.data.success,
          messages: response.data.messages,
          errors: [],
          warnings: [],
        };
      } else {
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Download failed'],
          warnings: [],
        };
      }
    } catch (e) {
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Download failed'],
        warnings: [],
      };
    } finally {
      downloadInFlightRef.current = false;
      setIsDownloading(false);
    }
  }, []);
  
  // Load config on mount
  useEffect(() => {
    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true;
      loadConfig();
    }
  }, [loadConfig]);
  
  return {
    config,
    isLoading,
    isDownloading,
    error,
    validationResult,
    isValidating,
    installedLibraries,
    loadConfig,
    updateConfig,
    resetToDefaults,
    validate,
    initDirs,
    installFromSeed,
    listInstalledLibraries,
    downloadLibrary,
    downloadAll,
  };
}

