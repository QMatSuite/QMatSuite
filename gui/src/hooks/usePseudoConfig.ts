/**
 * usePseudoConfig - Hook for managing pseudopotential configuration
 * 
 * Provides:
 * - Configuration state (store_dir, seed_dir, allow_download)
 * - Actions for validation, initialization, and installation
 * - Loading state for async operations
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { QMSResult } from '../types/qms';

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

export interface SeedArchiveInfo {
  filename: string;
  path: string;
  size_bytes: number;
  sha256: string | null;
  version: string | null;
  flavor: string | null;
}

export interface DownloadResult {
  success: boolean;
  messages: string[];
  errors: string[];
  warnings: string[];
}

export type DownloadStage = 'idle' | 'downloading' | 'verifying' | 'extracting' | 'installed' | 'error';

export interface UsePseudoConfigResult {
  // State
  config: PseudoConfig | null;
  isLoading: boolean;
  isDownloading: boolean;
  downloadStage: DownloadStage;
  error: string | null;
  
  // Validation
  validationResult: PseudoValidationResult | null;
  isValidating: boolean;
  
  // Installed libraries
  installedLibraries: SSSPLibraryInfo[];
  
  // Seed archives
  seedArchives: SeedArchiveInfo[];
  
  // Actions
  loadConfig: () => Promise<void>;
  updateConfig: (updates: Partial<Pick<PseudoConfig, 'store_dir' | 'seed_dir' | 'allow_download'>>) => Promise<void>;
  resetToDefaults: () => Promise<void>;
  validate: () => Promise<PseudoValidationResult | null>;
  initDirs: () => Promise<{ success: boolean; messages: string[]; errors: string[] }>;
  installFromSeed: (version?: string, flavor?: string) => Promise<{ success: boolean; messages: string[] }>;
  listInstalledLibraries: () => Promise<void>;
  listSeedArchives: () => Promise<void>;
  
  // Download actions
  downloadLibrary: (flavor: 'efficiency' | 'precision', enableIfDisabled?: boolean) => Promise<DownloadResult>;
  downloadAll: (enableIfDisabled?: boolean) => Promise<DownloadResult>;
  
  // Seed import
  importSeedArchives: (filePaths: string[]) => Promise<{ imported: any[]; skipped: string[]; errors: string[] }>;
}

export function usePseudoConfig(): UsePseudoConfigResult {
  const [config, setConfig] = useState<PseudoConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadStage, setDownloadStage] = useState<DownloadStage>('idle');
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<PseudoValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [installedLibraries, setInstalledLibraries] = useState<SSSPLibraryInfo[]>([]);
  const [seedArchives, setSeedArchives] = useState<SeedArchiveInfo[]>([]);
  
  // Track if we've loaded initially
  const hasLoadedRef = useRef(false);
  
  // Concurrency lock for downloads (prevent multiple simultaneous downloads)
  const downloadInFlightRef = useRef(false);
  
  const loadConfig = useCallback(async () => {
    if (!window.qms) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qms.request<QMSResult<'get_pseudo_config'>>('get_pseudo_config', {});
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
    if (!window.qms) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qms.request<QMSResult<'set_pseudo_config'>>('set_pseudo_config', updates);
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
    if (!window.qms) return null;
    
    setIsValidating(true);
    
    try {
      const response = await window.qms.request<QMSResult<'validate_pseudo_config'>>('validate_pseudo_config', {});
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
    if (!window.qms) return { success: false, messages: [], errors: ['No connection'] };
    
    setIsLoading(true);
    
    try {
      const response = await window.qms.request<QMSResult<'init_pseudo_dirs'>>('init_pseudo_dirs', {});
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
    if (!window.qms) return { success: false, messages: ['No connection'] };
    
    setIsLoading(true);
    
    try {
      const response = await window.qms.request<QMSResult<'install_seed_to_store'>>(
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
    if (!window.qms) return;
    
    try {
      const response = await window.qms.request<QMSResult<'list_installed_sssp'>>('list_installed_sssp', {});
      if (response.ok && response.data) {
        setInstalledLibraries(response.data.libraries);
      }
    } catch (e) {
      console.error('Failed to list installed SSSP:', e);
    }
  }, []);
  
  const listSeedArchives = useCallback(async () => {
    if (!window.qms) return;
    
    try {
      const response = await window.qms.request<QMSResult<'list_seed_archives'>>('list_seed_archives', {});
      if (response.ok && response.data) {
        setSeedArchives(response.data.archives || []);
      }
    } catch (e) {
      console.error('Failed to list seed archives:', e);
    }
  }, []);
  
  const downloadLibrary = useCallback(async (
    flavor: 'efficiency' | 'precision',
    enableIfDisabled: boolean = false
  ): Promise<DownloadResult> => {
    if (!window.qms) return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    
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
    setDownloadStage('downloading');
    setError(null);
    
    try {
      // If enableIfDisabled is true and downloads are disabled, enable them first
      if (enableIfDisabled && config && !config.allow_download) {
        await updateConfig({ allow_download: true });
      }
      
      const response = await window.qms.request<QMSResult<'download_sssp_library'>>(
        'download_sssp_library',
        { flavor, force: enableIfDisabled }
      );
      
      // Track progress stages from messages
      if (response.ok && response.data) {
        const messages = response.data.messages || [];
        const allMessages = messages.join(' ').toLowerCase();
        
        // Check for extraction stage
        if (allMessages.includes('extract') || allMessages.includes('extracted')) {
          setDownloadStage('extracting');
        }
        // Check for verification stage (after download, before extract)
        else if (allMessages.includes('verif') || allMessages.includes('verified') || allMessages.includes('sha256')) {
          setDownloadStage('verifying');
        }
        // Check for download stage
        else if (allMessages.includes('download')) {
          setDownloadStage('downloading');
        }
        
        if (response.data.success) {
          setDownloadStage('installed');
          // Update installed libraries from response
          if (response.data.installed_libraries) {
            setInstalledLibraries(response.data.installed_libraries);
          }
        } else if (response.data.errors && response.data.errors.length > 0) {
          setDownloadStage('error');
        }
        
        return {
          success: response.data.success,
          messages: response.data.messages,
          errors: response.data.errors,
          warnings: response.data.warnings,
        };
      } else {
        setDownloadStage('error');
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Download failed'],
          warnings: [],
        };
      }
    } catch (e) {
      setDownloadStage('error');
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Download failed'],
        warnings: [],
      };
    } finally {
      downloadInFlightRef.current = false;
      setIsDownloading(false);
      // Reset stage after a delay to show final state
      setTimeout(() => {
        setDownloadStage((current) => {
          if (current === 'installed') {
            return 'idle';
          }
          return current;
        });
      }, 2000);
    }
  }, [config, updateConfig]);
  
  const downloadAll = useCallback(async (
    enableIfDisabled: boolean = false
  ): Promise<DownloadResult> => {
    if (!window.qms) return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    
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
    setDownloadStage('downloading');
    setError(null);
    
    try {
      // If enableIfDisabled is true and downloads are disabled, enable them first
      if (enableIfDisabled && config && !config.allow_download) {
        await updateConfig({ allow_download: true });
      }
      
      const response = await window.qms.request<QMSResult<'download_all_sssp'>>(
        'download_all_sssp',
        { force: enableIfDisabled }
      );
      
      // Track progress stages from messages
      if (response.ok && response.data) {
        const messages = response.data.messages || [];
        const allMessages = messages.join(' ').toLowerCase();
        
        // Check for extraction stage
        if (allMessages.includes('extract') || allMessages.includes('extracted')) {
          setDownloadStage('extracting');
        }
        // Check for verification stage (after download, before extract)
        else if (allMessages.includes('verif') || allMessages.includes('verified') || allMessages.includes('sha256')) {
          setDownloadStage('verifying');
        }
        // Check for download stage
        else if (allMessages.includes('download')) {
          setDownloadStage('downloading');
        }
        
        if (response.data.success) {
          setDownloadStage('installed');
          // Update installed libraries from response
          if (response.data.installed_libraries) {
            setInstalledLibraries(response.data.installed_libraries);
          }
        } else if (response.data.failed && response.data.failed.length > 0) {
          setDownloadStage('error');
        }
        
        return {
          success: response.data.success,
          messages: response.data.messages,
          errors: [],
          warnings: [],
        };
      } else {
        setDownloadStage('error');
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Download failed'],
          warnings: [],
        };
      }
    } catch (e) {
      setDownloadStage('error');
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Download failed'],
        warnings: [],
      };
    } finally {
      downloadInFlightRef.current = false;
      setIsDownloading(false);
      // Reset stage after a delay to show final state
      setTimeout(() => {
        setDownloadStage((current) => {
          if (current === 'installed') {
            return 'idle';
          }
          return current;
        });
      }, 2000);
    }
  }, [config, updateConfig]);
  
  const importSeedArchives = useCallback(async (
    filePaths: string[]
  ): Promise<{ imported: any[]; skipped: string[]; errors: string[] }> => {
    if (!window.qms) return { imported: [], skipped: [], errors: ['No connection'] };
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qms.request<QMSResult<'import_seed_archives'>>(
        'import_seed_archives',
        { file_paths: filePaths }
      );
      if (response.ok && response.data) {
        // Refresh seed archives after import
        await listSeedArchives();
        return {
          imported: response.data.imported || [],
          skipped: response.data.skipped || [],
          errors: response.data.errors || [],
        };
      } else {
        return {
          imported: [],
          skipped: [],
          errors: [response.error?.message || 'Failed to import seed archives'],
        };
      }
    } catch (e) {
      return {
        imported: [],
        skipped: [],
        errors: [e instanceof Error ? e.message : 'Failed to import seed archives'],
      };
    } finally {
      setIsLoading(false);
    }
  }, [listSeedArchives]);
  
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
    downloadStage,
    error,
    validationResult,
    isValidating,
    installedLibraries,
    seedArchives,
    loadConfig,
    updateConfig,
    resetToDefaults,
    validate,
    initDirs,
    installFromSeed,
    listInstalledLibraries,
    listSeedArchives,
    downloadLibrary,
    downloadAll,
    importSeedArchives,
  };
}

