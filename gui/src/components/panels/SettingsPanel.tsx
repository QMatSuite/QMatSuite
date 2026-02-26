/**
 * SettingsPanel - Displays environment info, QE detection status, and app settings
 * 
 * Includes:
 * - QE detection and configuration
 * - Python/daemon environment info
 * - Appearance settings (theme)
 * - Analysis settings
 * - Default projects directory
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQMSClient, useQMSLogs } from '../../hooks/useQMSClient';
import { LibrariesPanel } from './LibrariesPanel';
import { PseudoArchivesPanel } from '../settings/PseudoArchivesPanel';
import { JournalHistoryPanel } from '../settings/JournalHistoryPanel';
import type {
  QEDetectionResult,
  EnvironmentInfo,
  EngineFamilyInfo,
  EngineStatusEntry,
  EngineInstallation,
  InstallableEngineEntry,
  PendingEngineEntry,
} from '../../types/qms';
import { getVisibleLogLines, getVisibleLogText } from '../../utils/logFilter';
import './SettingsPanel.css';

// Online Structures Settings Section Component
interface OnlineStructuresSettingsSectionProps {
  qms: ReturnType<typeof useQMSClient>;
}

function OnlineStructuresSettingsSection({ qms }: OnlineStructuresSettingsSectionProps) {
  const [providers, setProviders] = useState<Array<{
    provider_key: string;
    name: string;
    enabled: boolean;
    base_url?: string | null;
    structure_count?: number | null;
    requires_api_key: boolean;
  }>>([]);
  const [pubchemEnabled, setPubchemEnabled] = useState(true);
  const [materialsProjectEnabled, setMaterialsProjectEnabled] = useState(false);
  const [materialsProjectHasKey, setMaterialsProjectHasKey] = useState(false);
  const [mpApiKey, setMpApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Load providers on mount
  useEffect(() => {
    const loadProviders = async () => {
      if (!qms) return;
      setIsLoading(true);
      setError(null);
      try {
        const response = await qms.call('structure_list_providers', {});
        if (response.ok && response.data) {
          setProviders(response.data.optimade_providers || []);
          setPubchemEnabled(response.data.pubchem_enabled ?? true);
          setMaterialsProjectEnabled(response.data.materials_project_enabled ?? false);
          setMaterialsProjectHasKey(response.data.materials_project_has_key ?? false);
        } else {
          setError(response.error?.message || 'Failed to load providers');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load providers');
      } finally {
        setIsLoading(false);
      }
    };
    loadProviders();
  }, [qms]);
  
  const handleToggleProvider = useCallback(async (providerId: string, enabled: boolean) => {
    if (!qms || isSaving) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const currentProviders = providers.map(p => ({ provider_key: p.provider_key, enabled: p.enabled }));
      const updatedProviders = currentProviders.map(p => 
        p.provider_key === providerId ? { ...p, enabled } : p
      );
      
      const response = await qms.call('structure_update_online_sources', {
        patch: {
          optimade_providers: updatedProviders,
        },
      });
      
      if (response.ok && response.data) {
        setProviders(response.data.settings.optimade_providers || []);
        setPubchemEnabled(response.data.settings.pubchem_enabled);
        setMaterialsProjectEnabled(response.data.settings.materials_project.enabled);
        setMaterialsProjectHasKey(response.data.settings.materials_project.has_key);
      } else {
        setError(response.error?.message || 'Failed to update provider');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update provider');
    } finally {
      setIsSaving(false);
    }
  }, [qms, providers, isSaving]);
  
  const handleTogglePubChem = useCallback(async (enabled: boolean) => {
    if (!qms || isSaving) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await qms.call('structure_update_online_sources', {
        patch: {
          pubchem_enabled: enabled,
        },
      });
      
      if (response.ok && response.data) {
        setPubchemEnabled(response.data.settings.pubchem_enabled);
      } else {
        setError(response.error?.message || 'Failed to update PubChem setting');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update PubChem setting');
    } finally {
      setIsSaving(false);
    }
  }, [qms, isSaving]);
  
  const handleToggleMaterialsProject = useCallback(async (enabled: boolean) => {
    if (!qms || isSaving) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await qms.call('structure_update_online_sources', {
        patch: {
          materials_project: {
            enabled: enabled,
          },
        },
      });
      
      if (response.ok && response.data) {
        setMaterialsProjectEnabled(response.data.settings.materials_project.enabled);
        setMaterialsProjectHasKey(response.data.settings.materials_project.has_key);
      } else {
        setError(response.error?.message || 'Failed to update Materials Project setting');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update Materials Project setting');
    } finally {
      setIsSaving(false);
    }
  }, [qms, isSaving]);
  
  const handleSaveMpApiKey = useCallback(async () => {
    if (!qms || isSaving || !mpApiKey.trim()) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await qms.call('structure_update_online_sources', {
        patch: {
          materials_project: {
            enabled: materialsProjectEnabled,
            api_key: mpApiKey.trim(),
          },
        },
      });
      
      if (response.ok && response.data) {
        setMaterialsProjectEnabled(response.data.settings.materials_project.enabled);
        setMaterialsProjectHasKey(response.data.settings.materials_project.has_key);
        setMpApiKey(''); // Clear input after successful save
      } else {
        setError(response.error?.message || 'Failed to save API key');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save API key');
    } finally {
      setIsSaving(false);
    }
  }, [qms, mpApiKey, materialsProjectEnabled, isSaving]);
  
  return (
    <div className="settings-section">
      <div className="settings-section__header">
        <h3 className="settings-section__title">
          <span className="settings-icon">🌐</span>
          Online Structure Sources
        </h3>
      </div>
      
      <div className="settings-section__content">
        {error && (
          <div className="settings-error" style={{ marginBottom: '1rem' }}>
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}
        
        {isLoading ? (
          <p className="settings-empty">Loading providers...</p>
        ) : (
          <>
            {/* OPTIMADE Providers */}
            <div className="settings-field">
              <label className="settings-field__label">OPTIMADE Providers</label>
              <div className="online-sources-providers-list">
                {providers.map((provider) => (
                  <div key={provider.provider_key} className="settings-option">
                    <div className="settings-option__info">
                      <span className="settings-option__label">{provider.name || provider.provider_key}</span>
                      {provider.base_url && (
                        <span className="settings-option__description" style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                          {provider.base_url}
                        </span>
                      )}
                      {provider.structure_count !== null && provider.structure_count !== undefined && (
                        <span className="settings-option__description" style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                          {provider.structure_count.toLocaleString()} structures
                        </span>
                      )}
                    </div>
                    <div className="settings-option__control">
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={provider.enabled}
                          onChange={(e) => handleToggleProvider(provider.provider_key, e.target.checked)}
                          disabled={isSaving}
                        />
                        <span className="toggle-slider" />
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* PubChem */}
            <div className="settings-field" style={{ marginTop: '1.5rem' }}>
              <div className="settings-option">
                <div className="settings-option__info">
                  <span className="settings-option__label">PubChem</span>
                  <span className="settings-option__description">
                    Search for molecular structures by name or formula
                  </span>
                </div>
                <div className="settings-option__control">
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={pubchemEnabled}
                      onChange={(e) => handleTogglePubChem(e.target.checked)}
                      disabled={isSaving}
                    />
                    <span className="toggle-slider" />
                  </label>
                </div>
              </div>
            </div>
            
            {/* Materials Project Native API */}
            <div className="settings-field" style={{ marginTop: '1.5rem' }}>
              <div className="settings-option">
                <div className="settings-option__info">
                  <span className="settings-option__label">Materials Project Native API</span>
                  <span className="settings-option__description">
                    Access Materials Project via native API (requires API key). Provides richer metadata than OPTIMADE.
                  </span>
                  {materialsProjectHasKey && (
                    <span className="settings-option__description" style={{ fontSize: '0.75rem', color: '#4caf50' }}>
                      ✓ API key configured
                    </span>
                  )}
                </div>
                <div className="settings-option__control">
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={materialsProjectEnabled}
                      onChange={(e) => handleToggleMaterialsProject(e.target.checked)}
                      disabled={isSaving || !materialsProjectHasKey}
                    />
                    <span className="toggle-slider" />
                  </label>
                </div>
              </div>
              
              {/* API Key Input */}
              <div className="settings-path-input" style={{ marginTop: '0.75rem' }}>
                <input
                  type="password"
                  className="settings-path-input__field"
                  value={mpApiKey}
                  onChange={(e) => setMpApiKey(e.target.value)}
                  placeholder="Enter Materials Project API key"
                  disabled={isSaving}
                />
                <button
                  className="settings-path-input__browse"
                  onClick={handleSaveMpApiKey}
                  disabled={isSaving || !mpApiKey.trim()}
                  title="Save API key"
                >
                  💾
                </button>
                {mpApiKey && (
                  <button
                    className="settings-path-input__clear"
                    onClick={() => setMpApiKey('')}
                    title="Clear"
                  >
                    ×
                  </button>
                )}
              </div>
              <p className="settings-option__description" style={{ fontSize: '0.75rem', marginTop: '0.5rem', opacity: 0.7 }}>
                Get your API key from <a href="https://next-gen.materialsproject.org/api" target="_blank" rel="noopener noreferrer">Materials Project</a>
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface EngineManagementSectionProps {
  qms: ReturnType<typeof useQMSClient>;
  engineDisplayNames: Record<string, string>;
}

function formatEngineSourceLabel(source: string | null | undefined): string {
  switch ((source || '').toLowerCase()) {
    case 'bundled':
      return 'bundled';
    case 'micromamba':
      return 'conda-forge';
    case 'github_release':
      return 'github release';
    case 'system_path':
      return 'system PATH';
    case 'user_path':
      return 'user path';
    case 'user_venv':
      return 'user venv';
    case 'fallback':
      return 'fallback';
    default:
      return source || 'unknown';
  }
}

function isInstallationUninstallable(installation: EngineInstallation | null | undefined): boolean {
  const source = (installation?.source || '').toLowerCase();
  return source === 'micromamba' || source === 'github_release';
}

function EngineNotice({ engine, notice }: { engine: string; notice: { tone: 'ok' | 'error'; text: string } }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = notice.text.length > 150;

  return (
    <div
      className={`engine-manager-row__notice engine-manager-row__notice--${notice.tone}`}
      data-testid={`qms-engine-notice-${engine}`}
    >
      {isLong && !expanded ? (
        <>
          {notice.text.slice(0, 150)}...{' '}
          <button
            className="engine-notice-toggle"
            onClick={() => setExpanded(true)}
          >
            Show more
          </button>
        </>
      ) : isLong && expanded ? (
        <>
          {notice.text}{' '}
          <button
            className="engine-notice-toggle"
            onClick={() => setExpanded(false)}
          >
            Show less
          </button>
        </>
      ) : (
        notice.text
      )}
    </div>
  );
}

function formatBytes(bytes: number | null): string {
  if (bytes == null || bytes < 0) return '';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const val = bytes / Math.pow(1024, i);
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`;
}

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return '';
  const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  if (elapsed < 0) return '';
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function EngineManagementSection({ qms, engineDisplayNames }: EngineManagementSectionProps) {
  const [engineRows, setEngineRows] = useState<EngineStatusEntry[]>([]);
  const [installableRows, setInstallableRows] = useState<InstallableEngineEntry[]>([]);
  const [pendingEngines, setPendingEngines] = useState<PendingEngineEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingJobs, setPendingJobs] = useState<
    Record<string, {
      jobId: string;
      action: 'install' | 'uninstall';
      message: string;
      progressPct: number | null;
      progressBytes: number | null;
      progressTotal: number | null;
      progressStage: string | null;
      startedAt: string | null;
    }>
  >({});
  const [rowNotices, setRowNotices] = useState<Record<string, { tone: 'ok' | 'error'; text: string }>>({});
  const [_tick, setTick] = useState(0);

  // Tick every second while jobs are active so elapsed time updates
  useEffect(() => {
    if (Object.keys(pendingJobs).length === 0) return;
    const timer = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(timer);
  }, [Object.keys(pendingJobs).length > 0]);

  const refreshEngineData = useCallback(async (discover: boolean = false) => {
    if (!qms?.state.isConnected) return;

    setIsLoading(true);
    setError(null);
    try {
      const [listResp, installableResp] = await Promise.all([
        qms.listEngines(false, discover),
        qms.listInstallableEngines(),
      ]);

      if (!listResp.ok) {
        throw new Error(listResp.error?.message || 'Failed to list engines');
      }
      if (!installableResp.ok) {
        throw new Error(installableResp.error?.message || 'Failed to list installable engines');
      }

      setEngineRows(listResp.data?.engines || []);
      setInstallableRows(installableResp.data?.engines || []);
      setPendingEngines(listResp.data?.pending_engines || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh engine manager');
    } finally {
      setIsLoading(false);
    }
  }, [qms]);

  useEffect(() => {
    if (!qms?.state.isConnected) return;
    refreshEngineData();
  }, [qms, qms?.state.isConnected, refreshEngineData]);

  // Auto-refresh every 5s while bundled engines are still being staged.
  useEffect(() => {
    if (pendingEngines.length === 0) return;
    const timer = setInterval(() => { void refreshEngineData(); }, 5000);
    return () => clearInterval(timer);
  }, [pendingEngines.length, refreshEngineData]);

  useEffect(() => {
    if (!qms?.state.isConnected || Object.keys(pendingJobs).length === 0) return;

    let cancelled = false;

    const pollJobs = async () => {
      const entries = Object.entries(pendingJobs);
      if (entries.length === 0) return;

      const nextJobs: typeof pendingJobs = {
        ...pendingJobs,
      };
      let needsRefresh = false;
      const notices: Record<string, { tone: 'ok' | 'error'; text: string }> = {};

      for (const [engine, jobMeta] of entries) {
        if (jobMeta.jobId === '__pending__') {
          continue;
        }
        const statusResp = await qms.call('get_job_status', { job_id: jobMeta.jobId });
        if (!statusResp.ok || !statusResp.data) {
          notices[engine] = {
            tone: 'error',
            text: `Failed to poll ${jobMeta.action} status`,
          };
          delete nextJobs[engine];
          continue;
        }

        const status = statusResp.data.status;
        const line = statusResp.data.last_log_line || statusResp.data.error || '';
        if (status === 'pending') {
          nextJobs[engine] = {
            ...jobMeta,
            message: 'Waiting for current task to complete...',
            progressPct: null,
            progressBytes: null,
            progressTotal: null,
            progressStage: null,
            startedAt: jobMeta.startedAt,
          };
          continue;
        }
        if (status === 'running') {
          nextJobs[engine] = {
            ...jobMeta,
            message: line || `${jobMeta.action} in progress...`,
            progressPct: statusResp.data.progress_pct ?? null,
            progressBytes: statusResp.data.progress_bytes ?? null,
            progressTotal: statusResp.data.progress_total ?? null,
            progressStage: statusResp.data.progress_stage ?? null,
            startedAt: statusResp.data.started_at ?? jobMeta.startedAt,
          };
          continue;
        }

        delete nextJobs[engine];
        needsRefresh = true;
        notices[engine] = status === 'completed'
          ? { tone: 'ok', text: `${jobMeta.action} completed` }
          : { tone: 'error', text: line || `${jobMeta.action} failed` };
      }

      if (cancelled) return;
      setPendingJobs(nextJobs);
      setRowNotices((prev) => ({ ...prev, ...notices }));
      if (needsRefresh) {
        await refreshEngineData(true);
      }
    };

    const timer = setInterval(() => {
      void pollJobs();
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [pendingJobs, qms, refreshEngineData]);

  const installableMap = new Map(installableRows.map((row) => [row.engine, row]));
  const rowMap = new Map(engineRows.map((row) => [row.engine, row]));
  const allEngines = Array.from(new Set([...rowMap.keys(), ...installableMap.keys()])).sort();

  const handleInstall = useCallback(async (engine: string) => {
    setPendingJobs((prev) => ({
      ...prev,
      [engine]: { jobId: '__pending__', action: 'install', message: 'Starting install...', progressPct: null, progressBytes: null, progressTotal: null, progressStage: null, startedAt: null },
    }));
    setRowNotices((prev) => ({ ...prev, [engine]: { tone: 'ok', text: 'Starting install...' } }));
    const response = await qms.installEngine(engine, { async: true, source: 'auto' });
    if (!response.ok) {
      setPendingJobs((prev) => {
        const next = { ...prev };
        delete next[engine];
        return next;
      });
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || 'Install failed to start' },
      }));
      return;
    }

    const jobId = response.data?.job_id;
    if (jobId) {
      setPendingJobs((prev) => ({
        ...prev,
        [engine]: { jobId, action: 'install', message: 'Install queued...', progressPct: null, progressBytes: null, progressTotal: null, progressStage: null, startedAt: null },
      }));
      return;
    }

    setPendingJobs((prev) => {
      const next = { ...prev };
      delete next[engine];
      return next;
    });
    setRowNotices((prev) => ({ ...prev, [engine]: { tone: 'ok', text: 'Install completed' } }));
    await refreshEngineData(true);
  }, [qms, refreshEngineData]);

  const handleUninstall = useCallback(async (engine: string, installationId: string) => {
    if (!window.confirm(`Uninstall ${engine} (${installationId})?`)) return;
    setRowNotices((prev) => ({ ...prev, [engine]: { tone: 'ok', text: 'Starting uninstall...' } }));
    const response = await qms.uninstallEngine(engine, { installationId, async: true });
    if (!response.ok) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || 'Uninstall failed to start' },
      }));
      return;
    }

    const jobId = response.data?.job_id;
    if (jobId) {
      setPendingJobs((prev) => ({
        ...prev,
        [engine]: { jobId, action: 'uninstall', message: 'Uninstall queued...', progressPct: null, progressBytes: null, progressTotal: null, progressStage: null, startedAt: null },
      }));
      return;
    }

    setRowNotices((prev) => ({ ...prev, [engine]: { tone: 'ok', text: 'Uninstall completed' } }));
    await refreshEngineData(true);
  }, [qms, refreshEngineData]);

  const handleVerify = useCallback(async (engine: string) => {
    const response = await qms.verifyEngine(engine);
    if (!response.ok) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || 'Verification failed' },
      }));
      return;
    }
    setRowNotices((prev) => ({
      ...prev,
      [engine]: {
        tone: response.data?.ok ? 'ok' : 'error',
        text: response.data?.message || (response.data?.ok ? 'OK' : 'Verification failed'),
      },
    }));
  }, [qms]);

  const handleFixPermissions = useCallback(async (engine: string, engineDir: string) => {
    setRowNotices((prev) => ({
      ...prev,
      [engine]: { tone: 'ok', text: 'Fixing permissions...' },
    }));
    const response = await qms.fixEnginePermissions(engineDir);
    if (!response.ok) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || 'Failed to fix permissions' },
      }));
      return;
    }
    const fixes = response.data?.fixes_applied || [];
    setRowNotices((prev) => ({
      ...prev,
      [engine]: {
        tone: response.data?.success ? 'ok' : 'error',
        text: response.data?.success
          ? `Permissions fixed (${fixes.length} change${fixes.length !== 1 ? 's' : ''}). Re-verifying...`
          : (response.data?.error || 'Fix failed'),
      },
    }));
    if (response.data?.success) {
      await handleVerify(engine);
    }
  }, [qms, handleVerify]);

  const handleSetActive = useCallback(async (engine: string, installationId: string) => {
    const response = await qms.setActiveEngineInstallation(engine, installationId);
    if (!response.ok || !response.data?.active) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || response.data?.message || 'Failed to set active installation' },
      }));
      return;
    }
    setRowNotices((prev) => ({
      ...prev,
      [engine]: { tone: 'ok', text: `Active installation set to ${installationId}` },
    }));
    await refreshEngineData(true);
  }, [qms, refreshEngineData]);

  const handleConfigurePath = useCallback(async (engine: string) => {
    if (!window.qms?.openDirectory) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: 'Path picker is unavailable in this environment' },
      }));
      return;
    }

    const selectedPath = await window.qms.openDirectory();
    if (!selectedPath) return;

    const response = await qms.registerEnginePath(engine, selectedPath, { source: 'user_path' });
    if (!response.ok) {
      setRowNotices((prev) => ({
        ...prev,
        [engine]: { tone: 'error', text: response.error?.message || 'Failed to register path' },
      }));
      return;
    }
    setRowNotices((prev) => ({
      ...prev,
      [engine]: { tone: 'ok', text: `Registered path: ${selectedPath}` },
    }));
    await refreshEngineData(true);
  }, [qms, refreshEngineData]);

  return (
    <div className="settings-section" data-testid="qms-engine-manager-section">
      <div className="settings-section__header">
        <h3 className="settings-section__title">
          <span className="settings-icon">🧩</span>
          Engine Management
        </h3>
        <button
          className="settings-btn settings-btn--sm"
          onClick={() => void refreshEngineData(true)}
          disabled={isLoading}
          data-testid="qms-engine-manager-refresh"
        >
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="settings-section__content">
        {error && (
          <div className="settings-error" style={{ marginBottom: '1rem' }}>
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}

        {allEngines.length === 0 ? (
          <p className="settings-empty">No engines discovered yet.</p>
        ) : (
          <div className="engine-manager-list">
            {allEngines.map((engine) => {
              const row = rowMap.get(engine);
              const installable = installableMap.get(engine);
              const displayName = engineDisplayNames[engine] || installable?.display_name || engine.toUpperCase();
              const active = row?.active || null;
              const isInstalled = !!row?.installed;
              const statusText = isInstalled
                ? `Installed${active?.version ? ` (v${active.version})` : ''}`
                : 'Not installed';
              const sourceText = row?.active_source ? formatEngineSourceLabel(row.active_source) : '—';
              const pending = pendingJobs[engine];
              const pendingStaging = pendingEngines.find(pe => pe.engine === engine);
              const notice = rowNotices[engine];
              const hasInstallMethod = !!(installable && installable.install_methods.length > 0);
              const manualOnly = !!installable?.manual_only;
              const activeInstallId = row?.active_installation_id || '';
              const installations = row?.installations || [];
              const canUninstall = isInstallationUninstallable(active);

              return (
                <div
                  key={engine}
                  className="engine-manager-row"
                  data-testid={`qms-engine-row-${engine}`}
                >
                  <div className="engine-manager-row__main">
                    <div className="engine-manager-row__title">{displayName}</div>
                    <div className="engine-manager-row__meta">
                      <span>{statusText}</span>
                      <span>Source: {sourceText}</span>
                      {manualOnly && <span>Manual path engine</span>}
                    </div>
                    {pending && (
                      <div className="engine-manager-row__progress" data-testid={`qms-engine-progress-${engine}`}>
                        <div className="engine-progress-bar">
                          <div
                            className={`engine-progress-bar__fill${pending.progressPct == null ? ' engine-progress-bar__fill--indeterminate' : ''}`}
                            style={pending.progressPct != null ? { width: `${pending.progressPct}%` } : undefined}
                          />
                        </div>
                        <div className="engine-progress-info">
                          <span className="engine-progress-info__stage">
                            {pending.progressStage || pending.message}
                          </span>
                          <span className="engine-progress-info__stats">
                            {pending.progressPct != null && `${Math.round(pending.progressPct)}%`}
                            {pending.progressBytes != null && pending.progressTotal != null &&
                              ` · ${formatBytes(pending.progressBytes)} / ${formatBytes(pending.progressTotal)}`}
                            {pending.startedAt && ` · ${formatElapsed(pending.startedAt)}`}
                          </span>
                        </div>
                        {pending.message && pending.progressStage &&
                          pending.message !== pending.progressStage && (
                          <div className="engine-progress-log">{pending.message}</div>
                        )}
                      </div>
                    )}
                    {!pending && pendingStaging && (
                      <div className="engine-manager-row__progress" data-testid={`qms-engine-staging-${engine}`}>
                        <div className="engine-progress-bar">
                          <div className="engine-progress-bar__fill engine-progress-bar__fill--indeterminate" />
                        </div>
                        <div className="engine-progress-info">
                          <span className="engine-progress-info__stage">{pendingStaging.message}</span>
                        </div>
                      </div>
                    )}
                    {notice && (
                      <EngineNotice engine={engine} notice={notice} />
                    )}
                    {notice && notice.tone === 'error' && active?.path &&
                      /lacks execute permission|chmod|permission denied/i.test(notice.text) && (
                      <button
                        className="settings-btn settings-btn--sm"
                        onClick={() => void handleFixPermissions(engine, active.path!)}
                        disabled={!!pending}
                        data-testid={`qms-engine-fix-permissions-${engine}`}
                      >
                        Fix Permissions
                      </button>
                    )}
                  </div>

                  <div className="engine-manager-row__actions">
                    {installations.length > 1 && (
                      <select
                        className="settings-select"
                        value={activeInstallId}
                        onChange={(e) => void handleSetActive(engine, e.target.value)}
                        disabled={!!pending}
                        data-testid={`qms-engine-active-select-${engine}`}
                      >
                        {installations.map((inst) => (
                          <option key={inst.id} value={inst.id}>
                            {inst.id}{inst.version ? ` (v${inst.version})` : ''}{inst.stale ? ' [stale]' : ''}
                          </option>
                        ))}
                      </select>
                    )}

                    {!isInstalled && hasInstallMethod && (
                      <button
                        className="settings-btn"
                        onClick={() => void handleInstall(engine)}
                        disabled={!!pending}
                        data-testid={`qms-engine-install-${engine}`}
                      >
                        {pending?.action === 'install' ? 'Installing...' : 'Install'}
                      </button>
                    )}

                    <button
                      className="settings-btn"
                      onClick={() => void handleConfigurePath(engine)}
                      disabled={!!pending}
                      data-testid={`qms-engine-configure-path-${engine}`}
                    >
                      Configure Path
                    </button>

                    {isInstalled && (
                      <button
                        className="settings-btn settings-btn--sm"
                        onClick={() => void handleVerify(engine)}
                        disabled={!!pending}
                        data-testid={`qms-engine-verify-${engine}`}
                      >
                        Verify
                      </button>
                    )}

                    {isInstalled && canUninstall && active?.id && (
                      <button
                        className="settings-btn settings-btn--danger"
                        onClick={() => void handleUninstall(engine, active.id)}
                        disabled={!!pending}
                        data-testid={`qms-engine-uninstall-${engine}`}
                      >
                        {pending?.action === 'uninstall' ? 'Uninstalling...' : 'Uninstall'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export interface AppSettings {
  theme: 'dark' | 'light';
  autoAnalysis: boolean;
  defaultProjectsDir: string;
}

interface SettingsPanelProps {
  settings: AppSettings;
  onSettingsChange: (settings: AppSettings) => void;
}

export function SettingsPanel({ settings, onSettingsChange }: SettingsPanelProps) {
  const qms = useQMSClient();
  const [envInfo, setEnvInfo] = useState<EnvironmentInfo | null>(null);
  const [qeInfo, setQeInfo] = useState<QEDetectionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Engine families state
  const [engineFamilies, setEngineFamilies] = useState<EngineFamilyInfo[]>([]);
  
  // QE Engine selection state (two-state model)
  const [qeEngineInfo, setQeEngineInfo] = useState<{
    current_mode: 'internal' | 'external';
    current_bin_dir: string | null;
    internal_engines: Array<{ bin_dir: string; engine_path: string; pw_path: string }>;
  } | null>(null);
  const [isSettingQE, setIsSettingQE] = useState(false);
  const [qeError, setQeError] = useState<string | null>(null);
  
  // Debug/Diagnostics state
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [isPinging, setIsPinging] = useState(false);
  const [daemonLogVerbosity, setDaemonLogVerbosity] = useState<'INFO' | 'DEBUG'>('INFO');
  const [logVerbosityError, setLogVerbosityError] = useState<string | null>(null);
  const [debugResolution, setDebugResolution] = useState<boolean>(false);
  const [debugResolutionError, setDebugResolutionError] = useState<string | null>(null);
  const [showPollingLogs, setShowPollingLogs] = useState(false);
  const [copyButtonLabel, setCopyButtonLabel] = useState('Copy');
  const logs = useQMSLogs(200);
  const logsScrollRef = useRef<HTMLDivElement>(null);
  
  // Fetch debug resolution flag on mount
  useEffect(() => {
    const fetchDebugResolution = async () => {
      try {
        const response = await qms.call('get_debug_resolution', {});
        if (response.ok && response.data) {
          setDebugResolution(response.data.enabled);
        }
      } catch (e) {
        // Ignore errors on initial load
      }
    };
    if (qms && qms.state.isConnected) {
      fetchDebugResolution();
    }
  }, [qms, qms?.state.isConnected]);
  
  // Fetch QE engine info on mount
  const fetchQEEngineInfo = useCallback(async () => {
    if (!qms) return;
    try {
      const response = await qms.call('list_qe_engines', {});
      if (response.ok && response.data) {
        setQeEngineInfo({
          current_mode: response.data.current_mode || 'internal',
          current_bin_dir: response.data.current_bin_dir || null,
          internal_engines: response.data.internal_engines || [],
        });
        setQeError(null);
      }
    } catch (e) {
      console.error('[Settings] Failed to fetch QE engine info', e);
      setQeError(e instanceof Error ? e.message : 'Failed to fetch QE engine info');
    }
  }, [qms]);
  
  // Fetch engine families on mount
  useEffect(() => {
    const fetchEngineFamilies = async () => {
      if (!qms) return;
      try {
        const response = await qms.listEngineFamilies();
        if (response.ok && response.data) {
          setEngineFamilies(response.data.engines.filter(e => e.engine_role === 'base'));
        }
      } catch (e) {
        console.error('[Settings] Failed to fetch engine families', e);
      }
    };
    fetchEngineFamilies();
  }, [qms]);
  
  // Fetch environment info on mount
  useEffect(() => {
    fetchQEEngineInfo();
  }, [fetchQEEngineInfo]);
  
  useEffect(() => {
    const fetchEnvInfo = async () => {
      if (!window.qms) return;
      
      setIsLoading(true);
      setError(null);
      
      try {
        // Fetch environment info
        const envResponse = await window.qms.request<EnvironmentInfo>('get_env_info', {});
        if (envResponse.ok && envResponse.data) {
          setEnvInfo(envResponse.data);
        }
        
        // Fetch QE detection without forcing re-detect
        const qeResponse = await window.qms.request<QEDetectionResult>('detect_qe', {});
        if (qeResponse.ok && qeResponse.data) {
          setQeInfo(qeResponse.data);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to fetch environment info');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchEnvInfo();
  }, []);
  
  const handleRedetectQE = useCallback(async () => {
    if (!window.qms) return;
    
    setIsDetecting(true);
    setError(null);
    
    try {
      const response = await window.qms.request<QEDetectionResult>('detect_qe', {});
      if (response.ok && response.data) {
        setQeInfo(response.data);
      } else {
        setError(response.error?.message || 'Failed to detect QE');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to detect QE');
    } finally {
      setIsDetecting(false);
    }
  }, []);
  
  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsScrollRef.current && showDiagnostics) {
      logsScrollRef.current.scrollTop = logsScrollRef.current.scrollHeight;
    }
  }, [logs, showDiagnostics]);
  
  const handlePing = useCallback(async () => {
    setIsPinging(true);
    setPingResult(null);
    
    const response = await qms.ping();
    
    if (response.ok && response.data) {
      setPingResult(`✓ Daemon v${response.data.version} (connected)`);
    } else {
      setPingResult(`✗ ${response.error?.message || 'Connection failed'}`);
    }
    setIsPinging(false);
  }, [qms]);
  
  const handleLogVerbosityChange = useCallback(async (level: 'INFO' | 'DEBUG') => {
    if (!qms) return;
    
    const previousLevel = daemonLogVerbosity;
    setDaemonLogVerbosity(level);
    setLogVerbosityError(null);
    
    try {
      const response = await qms.call('set_log_level', { level });
      if (!response.ok) {
        // Revert on failure
        setDaemonLogVerbosity(previousLevel);
        setLogVerbosityError(response.error?.message || 'Failed to set log level');
      }
    } catch (e) {
      // Revert on error
      setDaemonLogVerbosity(previousLevel);
      setLogVerbosityError(e instanceof Error ? e.message : 'Failed to set log level');
    }
  }, [qms, daemonLogVerbosity]);
  
  const handleDebugResolutionChange = useCallback(async (enabled: boolean) => {
    if (!qms) return;
    
    const previousEnabled = debugResolution;
    setDebugResolution(enabled);
    setDebugResolutionError(null);
    
    try {
      const response = await qms.call('set_debug_resolution', { enabled });
      if (!response.ok) {
        // Revert on failure
        setDebugResolution(previousEnabled);
        setDebugResolutionError(response.error?.message || 'Failed to set debug resolution flag');
      }
    } catch (e) {
      // Revert on error
      setDebugResolution(previousEnabled);
      setDebugResolutionError(e instanceof Error ? e.message : 'Failed to set debug resolution flag');
    }
  }, [qms, debugResolution]);
  
  const handleCopyLogs = useCallback(async () => {
    const textToCopy = getVisibleLogText(logs, showPollingLogs);
    
    if (!textToCopy) {
      return;
    }
    
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        // Fallback for older browsers/contexts
        const textarea = document.createElement('textarea');
        textarea.value = textToCopy;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.left = '-999999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      
      // Show feedback
      setCopyButtonLabel('Copied!');
      setTimeout(() => {
        setCopyButtonLabel('Copy');
      }, 2000);
    } catch (e) {
      console.error('Failed to copy logs:', e);
      // Could show error toast here if needed
    }
  }, [logs, showPollingLogs, getVisibleLogText]);
  
  // Compute visible logs for rendering
  const visibleLogs = getVisibleLogLines(logs, showPollingLogs);
  const engineDisplayNames = Object.fromEntries(
    engineFamilies.map((engine) => [engine.engine_family, engine.display_name])
  );
  
  if (isLoading) {
    return (
      <div className="settings-panel settings-panel--loading">
        <div className="loading-spinner" />
        <p>Loading environment info...</p>
      </div>
    );
  }
  
  return (
    <div className="settings-panel">
      <div className="settings-scroll-container">
        <EngineManagementSection qms={qms} engineDisplayNames={engineDisplayNames} />

        {/* Engine Detection Sections */}
        {engineFamilies.map((engine) => (
          <div key={engine.engine_family} className="settings-section">
            <div className="settings-section__header">
              <h3 className="settings-section__title">
                <span className="settings-icon">⚛️</span>
                {engine.display_name}
              </h3>
              {/* For QE, keep the existing re-detect button */}
              {engine.engine_family === 'qe' && (
                <button
                  className="settings-btn settings-btn--sm"
                  onClick={handleRedetectQE}
                  disabled={isDetecting}
                >
                  {isDetecting ? '🔄 Detecting...' : '🔍 Re-detect'}
                </button>
              )}
            </div>
            <div className="settings-section__content">
              {engine.engine_family === 'qe' ? (
                /* Keep existing QE detection display */
                qeInfo ? (
                  <div className={`qe-status qe-status--${qeInfo.found ? 'found' : 'missing'}`}>
                    <div className="qe-status__indicator">
                      {qeInfo.found ? (
                        <>
                          <span className="status-dot status-dot--success" />
                          <span className="status-text">QE Installation Found</span>
                        </>
                      ) : (
                        <>
                          <span className="status-dot status-dot--error" />
                          <span className="status-text">QE Not Found</span>
                        </>
                      )}
                    </div>
                    
                    {qeInfo.found && qeInfo.qe_home && (
                      <div className="qe-details">
                        <div className="detail-row">
                          <span className="detail-label">QE Home</span>
                          <code className="detail-value detail-value--path">{qeInfo.qe_home}</code>
                        </div>
                        
                        {qeInfo.version && (
                          <div className="detail-row">
                            <span className="detail-label">Version</span>
                            <span className="detail-value">{qeInfo.version}</span>
                          </div>
                        )}
                        
                        {qeInfo.executables && qeInfo.executables.length > 0 && (
                          <div className="detail-row">
                            <span className="detail-label">Executables</span>
                            <div className="detail-tags">
                              {qeInfo.executables.map(exe => (
                                <span key={exe} className="exe-tag">{exe}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {!qeInfo.found && (
                      <div className="qe-not-found">
                        <p className="qe-not-found__message">
                          Quantum ESPRESSO was not detected on your system.
                        </p>
                        <div className="qe-not-found__help">
                          <p><strong>To fix this:</strong></p>
                          <ol>
                            <li>Install QE from <a href="https://www.quantum-espresso.org/" target="_blank" rel="noopener noreferrer">quantum-espresso.org</a></li>
                            <li>Set the <code>QE_HOME</code> environment variable to your QE installation directory</li>
                            <li>Or add QE&apos;s <code>bin/</code> directory to your <code>PATH</code></li>
                            <li>Click &quot;Re-detect&quot; after installation</li>
                          </ol>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="settings-empty">Click &quot;Re-detect&quot; to check for QE installation</p>
                )
              ) : (
                /* Generic engine status */
                <div className="engine-status">
                  <p>Supported gen steps: {engine.supported_gen_steps.join(', ')}</p>
                  {engine.companion_engines.length > 0 && (
                    <p>Companion engines: {engine.companion_engines.join(', ')}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {/* QE Engine Selection Section (Two-State Model) */}
        <div className="settings-section">
          <div className="settings-section__header">
            <h3 className="settings-section__title">
              <span className="settings-icon">⚙️</span>
              QE Engine Selection
            </h3>
          </div>
          
          <div className="settings-section__content">
            {/* Current Mode Display */}
            {qeEngineInfo && (
              <div className="settings-field">
                <label className="settings-field__label">Current Mode</label>
                <div className="qe-mode-display">
                  {qeEngineInfo.current_mode === 'internal' ? (
                    <div>
                      <span className="status-text">Using internal QE</span>
                      {qeEngineInfo.current_bin_dir && (
                        <code className="detail-value detail-value--path" style={{ display: 'block', marginTop: '0.5rem' }}>
                          {qeEngineInfo.current_bin_dir}
                        </code>
                      )}
                    </div>
                  ) : (
                    <div>
                      <span className="status-text">Using external QE</span>
                      {qeEngineInfo.current_bin_dir && (
                        <code className="detail-value detail-value--path" style={{ display: 'block', marginTop: '0.5rem' }}>
                          {qeEngineInfo.current_bin_dir}
                        </code>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Error Display */}
            {qeError && (
              <div className="settings-error" style={{ marginBottom: '1rem' }}>
                <span className="error-icon">⚠️</span>
                <span className="error-text">{qeError}</span>
              </div>
            )}
            
            {/* Action Buttons */}
            <div className="settings-field">
              <button
                className="settings-btn"
                onClick={async () => {
                  if (!qms) return;
                  setIsSettingQE(true);
                  setQeError(null);
                  try {
                    const response = await qms.call('set_qe_engine', { bin_dir: null });
                    if (response.ok) {
                      await fetchQEEngineInfo();
                      // Also refresh QE detection
                      const qeResponse = await window.qms?.request<QEDetectionResult>('detect_qe', {});
                      if (qeResponse?.ok && qeResponse.data) {
                        setQeInfo(qeResponse.data);
                      }
                    } else {
                      setQeError(response.error?.message || 'Failed to set internal QE');
                    }
                  } catch (e) {
                    setQeError(e instanceof Error ? e.message : 'Failed to set internal QE');
                  } finally {
                    setIsSettingQE(false);
                  }
                }}
                disabled={isSettingQE || (qeEngineInfo?.current_mode === 'internal')}
              >
                {isSettingQE ? 'Setting...' : 'Use Internal QE'}
              </button>
            </div>
            
            <div className="settings-field">
              <button
                className="settings-btn"
                onClick={async () => {
                  if (!window.qms?.openDirectory) {
                    setQeError('File picker not available');
                    return;
                  }
                  
                  setIsSettingQE(true);
                  setQeError(null);
                  try {
                    const selectedDir = await window.qms.openDirectory();
                    if (!selectedDir) {
                      setIsSettingQE(false);
                      return;
                    }
                    
                    // Note: We can't directly check file existence from frontend,
                    // so we rely on backend validation
                    const response = await qms.call('set_qe_engine', { bin_dir: selectedDir });
                    if (response.ok) {
                      await fetchQEEngineInfo();
                      // Also refresh QE detection
                      const qeResponse = await window.qms?.request<QEDetectionResult>('detect_qe', {});
                      if (qeResponse?.ok && qeResponse.data) {
                        setQeInfo(qeResponse.data);
                      }
                    } else {
                      setQeError(response.error?.message || 'Invalid QE bin directory. Must contain pw.x or pw.x.exe');
                    }
                  } catch (e) {
                    setQeError(e instanceof Error ? e.message : 'Failed to set external QE');
                  } finally {
                    setIsSettingQE(false);
                  }
                }}
                disabled={isSettingQE}
              >
                {isSettingQE ? 'Setting...' : 'Set External QE Bin Dir...'}
              </button>
            </div>
            
            {/* Internal Engines List (Info Only) */}
            {qeEngineInfo && qeEngineInfo.internal_engines.length > 0 && (
              <div className="settings-field">
                <label className="settings-field__label">Available Internal Engines</label>
                <div className="internal-engines-list">
                  {qeEngineInfo.internal_engines.map((eng, idx) => (
                    <div key={idx} className="internal-engine-item">
                      <code className="detail-value detail-value--path">{eng.bin_dir}</code>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        
        {/* Libraries Section */}
        <LibrariesPanel onRevealPath={(path) => {
          if (window.qms?.revealPath) {
            window.qms.revealPath(path);
          }
        }} />
        
        {/* Pseudopotential Archives Section */}
        <PseudoArchivesPanel />
        
        {/* Online Structure Sources Section */}
        <OnlineStructuresSettingsSection qms={qms} />
        
        {/* Python/Daemon Section */}
        <div className="settings-section">
        <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">🐍</span>
            Python Environment
          </h3>
        </div>
        
        <div className="settings-section__content">
          {envInfo ? (
            <div className="env-details">
              <div className="detail-row">
                <span className="detail-label">Python Version</span>
                <span className="detail-value">{envInfo.python_version}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Python Path</span>
                <code className="detail-value detail-value--path">{envInfo.python_executable}</code>
              </div>
              <div className="detail-row">
                <span className="detail-label">QMS Version</span>
                <span className="detail-value">{envInfo.qms_version}</span>
              </div>
            </div>
          ) : (
            <p className="settings-empty">Environment info not available</p>
          )}
        </div>
      </div>
      
        {/* Error Display */}
        {error && (
          <div className="settings-error">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}
      
        {/* Appearance Section */}
        <div className="settings-section">
        <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">🎨</span>
            Appearance
          </h3>
        </div>
        
        <div className="settings-section__content">
          <div className="settings-option">
            <div className="settings-option__info">
              <span className="settings-option__label">Theme</span>
              <span className="settings-option__description">
                Choose between dark and light appearance
              </span>
            </div>
            <div className="settings-option__control">
              <button
                className={`theme-btn ${settings.theme === 'dark' ? 'theme-btn--active' : ''}`}
                onClick={() => onSettingsChange({ ...settings, theme: 'dark' })}
              >
                🌙 Dark
              </button>
              <button
                className={`theme-btn ${settings.theme === 'light' ? 'theme-btn--active' : ''}`}
                onClick={() => onSettingsChange({ ...settings, theme: 'light' })}
              >
                ☀️ Light
              </button>
            </div>
          </div>
        </div>
      </div>
      
        {/* Analysis Section */}
        <div className="settings-section">
        <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">📊</span>
            Analysis
          </h3>
        </div>
        
        <div className="settings-section__content">
          <div className="settings-option">
            <div className="settings-option__info">
              <span className="settings-option__label">Automatic Analysis</span>
              <span className="settings-option__description">
                Automatically load analysis when selecting a calculation
              </span>
            </div>
            <div className="settings-option__control">
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={settings.autoAnalysis}
                  onChange={(e) => onSettingsChange({ ...settings, autoAnalysis: e.target.checked })}
                />
                <span className="toggle-slider" />
              </label>
            </div>
          </div>
        </div>
      </div>
      
        {/* Default Projects Directory Section */}
        <div className="settings-section">
        <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">📁</span>
            Default Projects Directory
          </h3>
        </div>
        
        <div className="settings-section__content">
          <div className="settings-option settings-option--vertical">
            <div className="settings-option__info">
              <span className="settings-option__label">Projects Directory</span>
              <span className="settings-option__description">
                Default location for creating new projects. Used as the initial directory in project creation dialogs.
              </span>
            </div>
            <div className="settings-option__control settings-option__control--full">
              <div className="settings-path-input">
                <input
                  type="text"
                  className="settings-path-input__field"
                  value={settings.defaultProjectsDir || ''}
                  onChange={(e) => onSettingsChange({ ...settings, defaultProjectsDir: e.target.value })}
                  placeholder="~/Documents/QMatSuite-projects"
                />
                <button
                  className="settings-path-input__browse"
                  onClick={async () => {
                    if (window.qms?.openDirectory) {
                      const path = await window.qms.openDirectory();
                      if (path) {
                        onSettingsChange({ ...settings, defaultProjectsDir: path });
                      }
                    }
                  }}
                  title="Browse for directory"
                >
                  📂
                </button>
                {settings.defaultProjectsDir && (
                  <button
                    className="settings-path-input__clear"
                    onClick={() => onSettingsChange({ ...settings, defaultProjectsDir: '' })}
                    title="Clear"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      
        {/* Diagnostics / Debug Section */}
        <div className="settings-section">
          <div className="settings-section__header">
            <h3 className="settings-section__title">
              <span className="settings-icon">🔧</span>
              Diagnostics / Debug
            </h3>
            <button
              className="settings-btn settings-btn--sm"
              onClick={() => setShowDiagnostics(!showDiagnostics)}
            >
              {showDiagnostics ? '▼ Hide' : '▶ Show'}
            </button>
          </div>
          
          {showDiagnostics && (
            <div className="settings-section__content">
              {/* Connection Test */}
              <div className="diagnostics-subsection">
                <h4 className="diagnostics-subsection__title">Connection Test</h4>
                <div className="diagnostics-subsection__content">
                  <button
                    className="settings-btn"
                    onClick={handlePing}
                    disabled={isPinging}
                  >
                    {isPinging ? '⏳ Pinging...' : '🏓 Ping Daemon'}
                  </button>
                  {pingResult && (
                    <span className={`diagnostics-result ${pingResult.startsWith('✓') ? 'diagnostics-result--success' : 'diagnostics-result--error'}`}>
                      {pingResult}
                    </span>
                  )}
                </div>
              </div>
              
              {/* Daemon Log Verbosity */}
              <div className="diagnostics-subsection">
                <h4 className="diagnostics-subsection__title">Daemon Log Verbosity</h4>
                <div className="diagnostics-subsection__content">
                  <div className="settings-option">
                    <div className="settings-option__info">
                      <span className="settings-option__label">Log Level</span>
                      <span className="settings-option__description">
                        Control daemon log verbosity. Debug shows polling RPC logs (job_counts, list_jobs).
                      </span>
                    </div>
                    <div className="settings-option__control">
                      <select
                        className="settings-select"
                        value={daemonLogVerbosity}
                        onChange={(e) => handleLogVerbosityChange(e.target.value as 'INFO' | 'DEBUG')}
                      >
                        <option value="INFO">Info</option>
                        <option value="DEBUG">Debug</option>
                      </select>
                    </div>
                  </div>
                  {logVerbosityError && (
                    <div className="settings-error" style={{ marginTop: '8px' }}>
                      <span className="error-icon">⚠️</span>
                      <span className="error-text">{logVerbosityError}</span>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Resolution/Addressing Debug Logs */}
              <div className="diagnostics-subsection">
                <h4 className="diagnostics-subsection__title">Resolution/Addressing Debug Logs</h4>
                <div className="diagnostics-subsection__content">
                  <div className="settings-option">
                    <div className="settings-option__info">
                      <span className="settings-option__label">Enable resolution/addressing debug logs</span>
                      <span className="settings-option__description">
                        When enabled, emits detailed trace logs for resource resolution (ULID vs slug, expected_kind filtering),
                        step detail loading (calculation.steps entries), workflow detection (per-step tracing), and RPC boundary logging.
                        Default: OFF. Useful for debugging slug collisions and resolution issues.
                      </span>
                    </div>
                    <div className="settings-option__control">
                      <label className="settings-toggle">
                        <input
                          type="checkbox"
                          checked={debugResolution}
                          onChange={(e) => handleDebugResolutionChange(e.target.checked)}
                        />
                        <span className="settings-toggle__slider"></span>
                      </label>
                    </div>
                  </div>
                  {debugResolutionError && (
                    <div className="settings-error" style={{ marginTop: '8px' }}>
                      <span className="error-icon">⚠️</span>
                      <span className="error-text">{debugResolutionError}</span>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Daemon Status */}
              <div className="diagnostics-subsection">
                <h4 className="diagnostics-subsection__title">Daemon Status</h4>
                <div className="diagnostics-subsection__content">
                  <div className="diagnostics-info">
                    <div className="diagnostics-info-item">
                      <span className="diagnostics-info-label">Connected:</span>
                      <span className={`diagnostics-info-value ${qms.state.isConnected ? 'diagnostics-info-value--success' : 'diagnostics-info-value--error'}`}>
                        {qms.state.isConnected ? 'Yes' : 'No'}
                      </span>
                    </div>
                    {qms.state.daemonStatus?.pythonPath && (
                      <div className="diagnostics-info-item">
                        <span className="diagnostics-info-label">Python:</span>
                        <code className="diagnostics-info-value">{qms.state.daemonStatus.pythonPath}</code>
                      </div>
                    )}
                    {qms.state.daemonStatus?.projectRoot && (
                      <div className="diagnostics-info-item">
                        <span className="diagnostics-info-label">CWD:</span>
                        <code className="diagnostics-info-value">{qms.state.daemonStatus.projectRoot}</code>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Daemon Logs */}
              <div className="diagnostics-subsection">
                <div className="diagnostics-subsection__header">
                  <h4 className="diagnostics-subsection__title">Daemon Logs</h4>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <button
                      className="settings-btn settings-btn--sm"
                      onClick={handleCopyLogs}
                      disabled={visibleLogs.length === 0}
                      title="Copy visible logs to clipboard"
                      data-testid="qms-settings-daemon-logs-copy"
                    >
                      {copyButtonLabel}
                    </button>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={showPollingLogs}
                        onChange={(e) => setShowPollingLogs(e.target.checked)}
                        style={{ cursor: 'pointer' }}
                      />
                      <span>Show polling logs</span>
                    </label>
                    <span className="diagnostics-logs-count">{visibleLogs.length} lines</span>
                  </div>
                </div>
                <div className="diagnostics-logs-content" ref={logsScrollRef}>
                  {visibleLogs.length === 0 ? (
                    <div className="diagnostics-logs-empty">
                      {logs.length === 0 ? 'No daemon output yet...' : 'No logs match current filter'}
                    </div>
                  ) : (
                    visibleLogs.map((log, i) => (
                      <div key={i} className="diagnostics-log-line">
                        {log}
                      </div>
                    ))
                  )}
                </div>
              </div>
              
              {/* Journal History (Debug View) */}
              <div className="diagnostics-subsection">
                <div className="diagnostics-subsection__header">
                  <h4 className="diagnostics-subsection__title">Journal History</h4>
                </div>
                <div className="diagnostics-subsection__content">
                  <JournalHistoryPanel autoLoad={showDiagnostics} />
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Info Section */}
        <div className="settings-section settings-section--info">
          <div className="settings-info">
            <span className="info-icon">💡</span>
            <p>
              The GUI communicates with a Python daemon process that handles QE execution.
              All calculations are performed through Quantum ESPRESSO executables.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
