/**
 * useLibraryManager - Hook for managing pseudopotential libraries
 * 
 * Provides generic library management interface for SSSP, PseudoDojo, etc.
 */

import { useState, useCallback, useEffect, useRef } from 'react';

export interface LibraryMetadata {
  id: string;
  name: string;
  description: string;
  supported_variants: string[];
  default_variants: string[];
}

export interface LibraryVariantStatus {
  variant: string;
  installed: boolean;
  path?: string;
  file_count: number;
  size_bytes?: number;
  version?: string;
}

export interface LibraryStatus {
  library_id: string;
  name: string;
  installed_variants: string[];
  variant_statuses: LibraryVariantStatus[];
  status: 'installed' | 'not_installed' | 'partial';
}

export interface InstallResult {
  success: boolean;
  messages: string[];
  errors: string[];
  warnings: string[];
}

export interface RemoveResult {
  success: boolean;
  messages: string[];
  errors: string[];
}

export type InstallSource = 'github_release' | 'local_archive' | 'seed';
export type InstallStage = 'idle' | 'downloading' | 'verifying' | 'extracting' | 'installed' | 'error';

export interface UseLibraryManagerResult {
  // State
  libraries: LibraryMetadata[];
  libraryStatuses: Map<string, LibraryStatus>;
  storeSize: number | null;
  isLoading: boolean;
  isInstalling: boolean;
  installStage: InstallStage;
  error: string | null;
  
  // Config
  storeDir: string | null;
  seedDir: string | null;
  allowDownload: boolean;
  
  // Actions
  loadLibraries: () => Promise<void>;
  loadLibraryStatus: (libraryId: string) => Promise<void>;
  loadAllStatuses: () => Promise<void>;
  loadStoreSize: () => Promise<void>;
  installLibrary: (
    libraryId: string,
    variants: string[],
    source: InstallSource,
    localArchivePaths?: string[],
    force?: boolean
  ) => Promise<InstallResult>;
  removeLibrary: (libraryId: string, variants: string[]) => Promise<RemoveResult>;
  repairLibrary: (libraryId: string, variants: string[]) => Promise<InstallResult>;
}

export function useLibraryManager(): UseLibraryManagerResult {
  const [libraries, setLibraries] = useState<LibraryMetadata[]>([]);
  const [libraryStatuses, setLibraryStatuses] = useState<Map<string, LibraryStatus>>(new Map());
  const [storeSize, setStoreSize] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);
  const [installStage, setInstallStage] = useState<InstallStage>('idle');
  const [error, setError] = useState<string | null>(null);
  
  const [storeDir, setStoreDir] = useState<string | null>(null);
  const [seedDir, setSeedDir] = useState<string | null>(null);
  const [allowDownload, setAllowDownload] = useState(false);
  
  const installInFlightRef = useRef(false);
  
  const loadLibraries = useCallback(async () => {
    if (!window.qv) return;
    
    try {
      const response = await window.qv.request<{ libraries: LibraryMetadata[] }>('list_libraries', {});
      if (response.ok && response.data) {
        setLibraries(response.data.libraries || []);
      } else {
        // If response failed, ensure we have an empty array
        setLibraries([]);
      }
    } catch (e) {
      console.error('Failed to load libraries:', e);
      setLibraries([]);
    }
  }, []);
  
  const loadLibraryStatus = useCallback(async (libraryId: string) => {
    if (!window.qv) return;
    
    try {
      const response = await window.qv.request<{ ok: boolean; data?: LibraryStatus; error?: any }>(
        'get_library_status',
        { library_id: libraryId }
      );
      if (response.ok && response.data) {
        setLibraryStatuses(prev => {
          const next = new Map(prev);
          next.set(libraryId, response.data as unknown as LibraryStatus);
          return next;
        });
      }
    } catch (e) {
      console.error(`Failed to load library status for ${libraryId}:`, e);
    }
  }, []);
  
  const loadAllStatuses = useCallback(async () => {
    if (!window.qv) return;
    
    // Load config first to get store_dir
    try {
      const configResponse = await window.qv.request<{ ok: boolean; data?: { store_dir?: string; seed_dir?: string; allow_download?: boolean }; error?: any }>('get_pseudo_config', {});
      if (configResponse.ok && configResponse.data) {
        const data = configResponse.data as { store_dir?: string; seed_dir?: string; allow_download?: boolean };
        setStoreDir(data.store_dir || null);
        setSeedDir(data.seed_dir || null);
        setAllowDownload(data.allow_download || false);
      }
    } catch (e) {
      console.error('Failed to load config:', e);
    }
    
    // Load all library statuses
    for (const lib of libraries) {
      await loadLibraryStatus(lib.id);
    }
  }, [libraries, loadLibraryStatus]);
  
  const loadStoreSize = useCallback(async () => {
    if (!window.qv) return;
    
    try {
      const response = await window.qv.request<{ ok: boolean; data?: { size_bytes?: number | null }; error?: any }>('compute_store_size', {});
      if (response.ok && response.data) {
        const data = response.data as { size_bytes?: number | null };
        setStoreSize(data.size_bytes ?? null);
      }
    } catch (e) {
      console.error('Failed to load store size:', e);
    }
  }, []);
  
  const installLibrary = useCallback(async (
    libraryId: string,
    variants: string[],
    source: InstallSource,
    localArchivePaths?: string[],
    force: boolean = false
  ): Promise<InstallResult> => {
    if (!window.qv) {
      return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    }
    
    // Concurrency guard
    if (installInFlightRef.current) {
      return {
        success: false,
        messages: [],
        errors: ['Another installation is already in progress'],
        warnings: [],
      };
    }
    
    installInFlightRef.current = true;
    setIsInstalling(true);
    setInstallStage('downloading');
    setError(null);
    
    try {
      const response = await window.qv.request<{ ok: boolean; data?: InstallResult; error?: any }>(
        'install_library',
        {
          library_id: libraryId,
          variants,
          source,
          local_archive_paths: localArchivePaths,
          force,
        }
      );
      
      if (response.ok && response.data) {
        const result = response.data as unknown as InstallResult;
        const messages = result.messages || [];
        const allMessages = messages.join(' ').toLowerCase();
        
        // Track progress stages
        if (allMessages.includes('extract') || allMessages.includes('extracted')) {
          setInstallStage('extracting');
        } else if (allMessages.includes('verif') || allMessages.includes('verified') || allMessages.includes('sha256')) {
          setInstallStage('verifying');
        } else if (allMessages.includes('download')) {
          setInstallStage('downloading');
        }
        
        if (result.success) {
          setInstallStage('installed');
          // Force refresh status - wait a bit for filesystem to settle
          await new Promise(resolve => setTimeout(resolve, 500));
          await loadLibraryStatus(libraryId);
          await loadStoreSize();
          // Also refresh all statuses to ensure consistency
          await loadAllStatuses();
        } else if (result.errors && result.errors.length > 0) {
          setInstallStage('error');
        }
        
        return result;
      } else {
        setInstallStage('error');
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Installation failed'],
          warnings: [],
        };
      }
    } catch (e) {
      setInstallStage('error');
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Installation failed'],
        warnings: [],
      };
    } finally {
      installInFlightRef.current = false;
      setIsInstalling(false);
      // Reset stage after delay
      setTimeout(() => {
        setInstallStage(prev => prev === 'installed' ? 'idle' : prev);
      }, 2000);
    }
  }, [loadLibraryStatus, loadStoreSize]);
  
  const removeLibrary = useCallback(async (
    libraryId: string,
    variants: string[]
  ): Promise<RemoveResult> => {
    if (!window.qv) {
      return { success: false, messages: [], errors: ['No connection'] };
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<{ ok: boolean; data?: RemoveResult; error?: any }>(
        'remove_library',
        { library_id: libraryId, variants }
      );
      
      if (response.ok && response.data) {
        const result = response.data as unknown as RemoveResult;
        // Force refresh status - wait a bit for filesystem to settle
        await new Promise(resolve => setTimeout(resolve, 500));
        await loadLibraryStatus(libraryId);
        await loadStoreSize();
        // Also refresh all statuses to ensure consistency
        await loadAllStatuses();
        return result;
      } else {
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Removal failed'],
        };
      }
    } catch (e) {
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Removal failed'],
      };
    } finally {
      setIsLoading(false);
    }
  }, [loadLibraryStatus, loadStoreSize]);
  
  const repairLibrary = useCallback(async (
    libraryId: string,
    variants: string[]
  ): Promise<InstallResult> => {
    if (!window.qv) {
      return { success: false, messages: [], errors: ['No connection'], warnings: [] };
    }
    
    setIsInstalling(true);
    setInstallStage('extracting');
    setError(null);
    
    try {
      const response = await window.qv.request<{ ok: boolean; data?: InstallResult; error?: any }>(
        'repair_library',
        { library_id: libraryId, variants }
      );
      
      if (response.ok && response.data) {
        const result = response.data as unknown as InstallResult;
        if (result.success) {
          setInstallStage('installed');
          // Force refresh status - wait a bit for filesystem to settle
          await new Promise(resolve => setTimeout(resolve, 500));
          await loadLibraryStatus(libraryId);
          await loadStoreSize();
          // Also refresh all statuses to ensure consistency
          await loadAllStatuses();
        } else {
          setInstallStage('error');
        }
        return result;
      } else {
        setInstallStage('error');
        return {
          success: false,
          messages: [],
          errors: [response.error?.message || 'Repair failed'],
          warnings: [],
        };
      }
    } catch (e) {
      setInstallStage('error');
      return {
        success: false,
        messages: [],
        errors: [e instanceof Error ? e.message : 'Repair failed'],
        warnings: [],
      };
    } finally {
      setIsInstalling(false);
      setTimeout(() => {
        setInstallStage(prev => prev === 'installed' ? 'idle' : prev);
      }, 2000);
    }
  }, [loadLibraryStatus, loadStoreSize]);
  
  // Load libraries on mount
  useEffect(() => {
    loadLibraries();
  }, [loadLibraries]);
  
  // Load all statuses when libraries are loaded
  useEffect(() => {
    if (libraries.length > 0) {
      loadAllStatuses();
      loadStoreSize();
    }
  }, [libraries, loadAllStatuses, loadStoreSize]);
  
  return {
    libraries,
    libraryStatuses,
    storeSize,
    isLoading,
    isInstalling,
    installStage,
    error,
    storeDir,
    seedDir,
    allowDownload,
    loadLibraries,
    loadLibraryStatus,
    loadAllStatuses,
    loadStoreSize,
    installLibrary,
    removeLibrary,
    repairLibrary,
  };
}

