/**
 * AppShellContext — UI chrome state
 *
 * Owns: view navigation, theme/settings, recent projects, updater,
 * notifications, and dialog visibility flags.
 *
 * Dependency: none (root context).
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  type ReactNode,
} from 'react';
import type { ViewType } from '../components/layout/Sidebar';
import type { UpdaterState } from '../types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type HomeMode = 'welcome' | 'demo-gallery';

export interface AppSettings {
  theme: 'dark' | 'light';
  autoAnalysis: boolean;
  defaultProjectsDir: string;
}

export interface AppShellContextValue {
  // View
  currentView: ViewType;
  setCurrentView: (v: ViewType) => void;
  homeMode: HomeMode;
  setHomeMode: (m: HomeMode) => void;

  // Debug
  showDebugFooter: boolean;
  setShowDebugFooter: (v: boolean) => void;

  // Settings
  appSettings: AppSettings;
  setAppSettings: React.Dispatch<React.SetStateAction<AppSettings>>;

  // Updater
  updaterState: UpdaterState | null;
  updaterDismissed: boolean;
  setUpdaterDismissed: (v: boolean) => void;
  handleCheckForUpdates: () => Promise<void>;
  handleDownloadUpdate: () => Promise<void>;
  handleInstallDownloadedUpdate: () => Promise<void>;

  // Notifications
  jobNotification: { message: string; type: 'success' | 'error' } | null;
  setJobNotification: (v: { message: string; type: 'success' | 'error' } | null) => void;
  showNotification: (message: string, type?: 'success' | 'error') => void;

  // Recent projects
  recentProjects: string[];
  addToRecentProjects: (path: string) => void;
  removeFromRecentProjects: (path: string) => void;

  // Dialog flags
  showCreateProject: boolean;
  setShowCreateProject: (v: boolean) => void;
  showCreateDemoProject: boolean;
  setShowCreateDemoProject: (v: boolean) => void;
  showImportStructure: boolean;
  setShowImportStructure: (v: boolean) => void;
  showCreateCalculation: boolean;
  setShowCreateCalculation: (v: boolean) => void;

  // Navigation helpers
  handleOpenDemoGallery: () => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AppShellContext = createContext<AppShellContextValue | null>(null);

export function useAppShell(): AppShellContextValue {
  const ctx = useContext(AppShellContext);
  if (!ctx) throw new Error('useAppShell must be used within <AppShellProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AppShellProvider({ children }: { children: ReactNode }) {
  // --- View -----------------------------------------------------------------
  const [currentView, setCurrentView] = useState<ViewType>('home');
  const [homeMode, setHomeMode] = useState<HomeMode>('welcome');
  const [showDebugFooter, setShowDebugFooter] = useState(true);

  // --- Settings (persisted) -------------------------------------------------
  const [appSettings, setAppSettings] = useState<AppSettings>(() => {
    try {
      const saved = localStorage.getItem('qms-app-settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          theme: parsed.theme || 'dark',
          autoAnalysis: parsed.autoAnalysis ?? true,
          defaultProjectsDir: parsed.defaultProjectsDir || '',
        };
      }
    } catch {
      // ignore
    }
    return { theme: 'dark', autoAnalysis: true, defaultProjectsDir: '' };
  });

  // Effect 1: Apply theme to document + persist
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', appSettings.theme);
    localStorage.setItem('qms-app-settings', JSON.stringify(appSettings));
  }, [appSettings]);

  // --- Updater --------------------------------------------------------------
  const [updaterState, setUpdaterState] = useState<UpdaterState | null>(null);
  const [updaterDismissed, setUpdaterDismissed] = useState(false);

  // Effect 2: Subscribe to updater state
  useEffect(() => {
    if (!window.qms) return;
    let cancelled = false;

    void window.qms.getUpdaterState().then((status) => {
      if (!cancelled) setUpdaterState(status);
    }).catch(() => {
      // Updater state channel is best-effort.
    });

    const unsubUpdater = window.qms.onUpdaterState((status) => {
      if (!cancelled) setUpdaterState(status);
    });

    return () => {
      cancelled = true;
      unsubUpdater();
    };
  }, []);

  // Effect 3: Reset dismiss on new updater event
  useEffect(() => {
    if (!updaterState) return;
    if (updaterState.state === 'available' || updaterState.state === 'downloading' || updaterState.state === 'downloaded') {
      setUpdaterDismissed(false);
    }
  }, [updaterState?.state, updaterState?.version]);

  // --- Notifications --------------------------------------------------------
  const [jobNotification, setJobNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const notificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showNotification = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    if (notificationTimeoutRef.current) {
      clearTimeout(notificationTimeoutRef.current);
    }
    setJobNotification({ message, type });
    notificationTimeoutRef.current = setTimeout(() => {
      setJobNotification(null);
    }, 5000);
  }, []);

  // Effect 4: Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (notificationTimeoutRef.current) {
        clearTimeout(notificationTimeoutRef.current);
      }
    };
  }, []);

  // --- Updater actions ------------------------------------------------------
  const handleCheckForUpdates = useCallback(async () => {
    if (!window.qms?.checkForUpdates) return;
    const response = await window.qms.checkForUpdates();
    if (!response.ok && response.message) {
      showNotification(response.message, 'error');
    }
  }, [showNotification]);

  const handleDownloadUpdate = useCallback(async () => {
    if (!window.qms?.downloadUpdate) return;
    const response = await window.qms.downloadUpdate();
    if (!response.ok) {
      showNotification(response.message || 'Failed to start update download', 'error');
    }
  }, [showNotification]);

  const handleInstallDownloadedUpdate = useCallback(async () => {
    if (!window.qms?.quitAndInstallUpdate) return;
    const response = await window.qms.quitAndInstallUpdate();
    if (!response.ok) {
      showNotification(response.message || 'Failed to install update', 'error');
    }
  }, [showNotification]);

  // --- Recent projects (persisted) ------------------------------------------
  const [recentProjects, setRecentProjects] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('qms-recent-projects') || '[]');
    } catch {
      return [];
    }
  });

  const addToRecentProjects = useCallback((path: string) => {
    setRecentProjects(prev => {
      const filtered = prev.filter(p => p !== path);
      const updated = [path, ...filtered].slice(0, 5);
      localStorage.setItem('qms-recent-projects', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const removeFromRecentProjects = useCallback((path: string) => {
    setRecentProjects(prev => {
      const filtered = prev.filter(p => p !== path);
      localStorage.setItem('qms-recent-projects', JSON.stringify(filtered));
      return filtered;
    });
  }, []);

  // --- Dialog flags ---------------------------------------------------------
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [showCreateDemoProject, setShowCreateDemoProject] = useState(false);
  const [showImportStructure, setShowImportStructure] = useState(false);
  const [showCreateCalculation, setShowCreateCalculation] = useState(false);

  // --- Navigation helpers ---------------------------------------------------
  const handleOpenDemoGallery = useCallback(() => {
    setHomeMode('demo-gallery');
    setCurrentView('home');
  }, []);

  // --- Memoised context value -----------------------------------------------
  const value = useMemo<AppShellContextValue>(() => ({
    currentView,
    setCurrentView,
    homeMode,
    setHomeMode,
    showDebugFooter,
    setShowDebugFooter,
    appSettings,
    setAppSettings,
    updaterState,
    updaterDismissed,
    setUpdaterDismissed,
    handleCheckForUpdates,
    handleDownloadUpdate,
    handleInstallDownloadedUpdate,
    jobNotification,
    setJobNotification,
    showNotification,
    recentProjects,
    addToRecentProjects,
    removeFromRecentProjects,
    showCreateProject,
    setShowCreateProject,
    showCreateDemoProject,
    setShowCreateDemoProject,
    showImportStructure,
    setShowImportStructure,
    showCreateCalculation,
    setShowCreateCalculation,
    handleOpenDemoGallery,
  }), [
    currentView,
    homeMode,
    showDebugFooter,
    appSettings,
    updaterState,
    updaterDismissed,
    handleCheckForUpdates,
    handleDownloadUpdate,
    handleInstallDownloadedUpdate,
    jobNotification,
    showNotification,
    recentProjects,
    addToRecentProjects,
    removeFromRecentProjects,
    showCreateProject,
    showCreateDemoProject,
    showImportStructure,
    showCreateCalculation,
    handleOpenDemoGallery,
  ]);

  return (
    <AppShellContext.Provider value={value}>
      {children}
    </AppShellContext.Provider>
  );
}
