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
import { useQVClient, useQVLogs } from '../../hooks/useQVClient';
import { usePseudoConfig } from '../../hooks/usePseudoConfig';
import { LibrariesPanel } from './LibrariesPanel';
import { PseudoArchivesPanel } from '../settings/PseudoArchivesPanel';
import type { QEDetectionResult, EnvironmentInfo } from '../../types/qv';
import { getVisibleLogLines, getVisibleLogText } from '../../utils/logFilter';
import './SettingsPanel.css';

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
  const qv = useQVClient();
  const [envInfo, setEnvInfo] = useState<EnvironmentInfo | null>(null);
  const [qeInfo, setQeInfo] = useState<QEDetectionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Debug/Diagnostics state
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [isPinging, setIsPinging] = useState(false);
  const [daemonLogVerbosity, setDaemonLogVerbosity] = useState<'INFO' | 'DEBUG'>('INFO');
  const [logVerbosityError, setLogVerbosityError] = useState<string | null>(null);
  const [showPollingLogs, setShowPollingLogs] = useState(false);
  const [copyButtonLabel, setCopyButtonLabel] = useState('Copy');
  const logs = useQVLogs(200);
  const logsScrollRef = useRef<HTMLDivElement>(null);
  
  // QE metadata debug info
  const [qeMetadataDebugInfo, setQeMetadataDebugInfo] = useState<{
    loaded_via: 'cache' | 'disk' | 'not_loaded';
    loaded_at: string | null;
    schema_version: number | null;
    path_abs: string | null;
  } | null>(null);
  
  // Fetch QE metadata debug info
  const fetchQEMetadataDebugInfo = useCallback(async () => {
    if (!qv) return;
    
    try {
      const response = await qv.call('get_qe_parameter_metadata_debug_info', {});
      if (response.ok && response.data) {
        setQeMetadataDebugInfo(response.data);
      }
    } catch (e) {
      // Silently fail - debug info is optional
      console.debug('[Settings] Failed to fetch QE metadata debug info', e);
    }
  }, [qv]);
  
  // Fetch environment info on mount
  useEffect(() => {
    const fetchEnvInfo = async () => {
      if (!window.qv) return;
      
      setIsLoading(true);
      setError(null);
      
      try {
        // Fetch environment info
        const envResponse = await window.qv.request<EnvironmentInfo>('get_env_info', {});
        if (envResponse.ok && envResponse.data) {
          setEnvInfo(envResponse.data);
        }
        
        // Fetch QE detection without forcing re-detect
        const qeResponse = await window.qv.request<QEDetectionResult>('detect_qe', {});
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
  
  // Fetch QE metadata debug info when diagnostics section is shown
  useEffect(() => {
    if (showDiagnostics) {
      fetchQEMetadataDebugInfo();
    }
  }, [showDiagnostics, fetchQEMetadataDebugInfo]);
  
  const handleRedetectQE = useCallback(async () => {
    if (!window.qv) return;
    
    setIsDetecting(true);
    setError(null);
    
    try {
      const response = await window.qv.request<QEDetectionResult>('detect_qe', {});
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
    
    const response = await qv.ping();
    
    if (response.ok && response.data) {
      setPingResult(`✓ Daemon v${response.data.version} (connected)`);
    } else {
      setPingResult(`✗ ${response.error?.message || 'Connection failed'}`);
    }
    setIsPinging(false);
  }, [qv]);
  
  const handleLogVerbosityChange = useCallback(async (level: 'INFO' | 'DEBUG') => {
    if (!qv) return;
    
    const previousLevel = daemonLogVerbosity;
    setDaemonLogVerbosity(level);
    setLogVerbosityError(null);
    
    try {
      const response = await qv.call('set_log_level', { level });
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
  }, [qv, daemonLogVerbosity]);
  
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
        {/* QE Detection Section */}
        <div className="settings-section">
          <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">⚛️</span>
            Quantum ESPRESSO
          </h3>
          <button 
            className="settings-btn settings-btn--sm"
            onClick={handleRedetectQE}
            disabled={isDetecting}
          >
            {isDetecting ? '🔄 Detecting...' : '🔍 Re-detect'}
            </button>
          </div>
          
          <div className="settings-section__content">
          {qeInfo ? (
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
          )}
          </div>
        </div>
        
        {/* Libraries Section */}
        <LibrariesPanel onRevealPath={(path) => {
          if (window.qv?.revealPath) {
            window.qv.revealPath(path);
          }
        }} />
        
        {/* Pseudopotential Archives Section */}
        <PseudoArchivesPanel />
        
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
                <span className="detail-label">QV Version</span>
                <span className="detail-value">{envInfo.qv_version}</span>
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
                  placeholder="~/Documents/QuantumVITAS-projects"
                />
                <button
                  className="settings-path-input__browse"
                  onClick={async () => {
                    if (window.qv?.openDirectory) {
                      const path = await window.qv.openDirectory();
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
              
              {/* Daemon Status */}
              <div className="diagnostics-subsection">
                <h4 className="diagnostics-subsection__title">Daemon Status</h4>
                <div className="diagnostics-subsection__content">
                  <div className="diagnostics-info">
                    <div className="diagnostics-info-item">
                      <span className="diagnostics-info-label">Connected:</span>
                      <span className={`diagnostics-info-value ${qv.state.isConnected ? 'diagnostics-info-value--success' : 'diagnostics-info-value--error'}`}>
                        {qv.state.isConnected ? 'Yes' : 'No'}
                      </span>
                    </div>
                    {qv.state.daemonStatus?.pythonPath && (
                      <div className="diagnostics-info-item">
                        <span className="diagnostics-info-label">Python:</span>
                        <code className="diagnostics-info-value">{qv.state.daemonStatus.pythonPath}</code>
                      </div>
                    )}
                    {qv.state.daemonStatus?.projectRoot && (
                      <div className="diagnostics-info-item">
                        <span className="diagnostics-info-label">CWD:</span>
                        <code className="diagnostics-info-value">{qv.state.daemonStatus.projectRoot}</code>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* QE Metadata Load Status */}
              <div className="diagnostics-subsection">
                <div className="diagnostics-subsection__header">
                  <h4 className="diagnostics-subsection__title">QE Metadata Load Status</h4>
                  <button
                    className="settings-btn settings-btn--sm"
                    onClick={fetchQEMetadataDebugInfo}
                    title="Refresh metadata load status"
                  >
                    🔄
                  </button>
                </div>
                <div className="diagnostics-subsection__content">
                  {qeMetadataDebugInfo ? (
                    <div className="diagnostics-info">
                      <div className="diagnostics-info-item">
                        <span className="diagnostics-info-label">Loaded via:</span>
                        <span className="diagnostics-info-value">
                          {(() => {
                            const loadedVia = qeMetadataDebugInfo.loaded_via;
                            const loadedAt = qeMetadataDebugInfo.loaded_at;
                            
                            if (loadedVia === 'not_loaded') {
                              return 'not loaded yet';
                            }
                            
                            let timeStr = '—';
                            if (loadedAt) {
                              try {
                                const date = new Date(loadedAt);
                                const hours = date.getHours().toString().padStart(2, '0');
                                const minutes = date.getMinutes().toString().padStart(2, '0');
                                const seconds = date.getSeconds().toString().padStart(2, '0');
                                timeStr = `${hours}:${minutes}:${seconds}`;
                              } catch {
                                timeStr = '—';
                              }
                            }
                            return `${loadedVia} (${timeStr})`;
                          })()}
                        </span>
                      </div>
                      {qeMetadataDebugInfo.schema_version !== null && (
                        <div className="diagnostics-info-item">
                          <span className="diagnostics-info-label">Schema:</span>
                          <span className="diagnostics-info-value">
                            v{qeMetadataDebugInfo.schema_version}
                          </span>
                        </div>
                      )}
                      {qeMetadataDebugInfo.path_abs && (
                        <div className="diagnostics-info-item">
                          <span className="diagnostics-info-label">Path:</span>
                          <code 
                            className="diagnostics-info-value" 
                            title={qeMetadataDebugInfo.path_abs}
                            style={{
                              maxWidth: '400px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              display: 'inline-block',
                            }}
                          >
                            {qeMetadataDebugInfo.path_abs}
                          </code>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="diagnostics-info">
                      <span className="diagnostics-info-value">Loading...</span>
                    </div>
                  )}
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
                      data-testid="qv-settings-daemon-logs-copy"
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


/**
 * PseudopotentialsSection - Simplified SSSP library management
 * 
 * Normal view: Status summary, Download & Install buttons, progress, installed list
 * Advanced (collapsed): Seed cache, network toggle, validate
 */
function PseudopotentialsSection() {
  const {
    config,
    isLoading,
    isDownloading,
    downloadStage,
    error,
    validationResult,
    isValidating,
    installedLibraries,
    seedArchives,
    updateConfig,
    validate,
    installFromSeed,
    listInstalledLibraries,
    listSeedArchives,
    downloadLibrary,
    downloadAll,
    importSeedArchives,
  } = usePseudoConfig();
  
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [localStoreDir, setLocalStoreDir] = useState('');
  
  // Sync local state with config
  useEffect(() => {
    if (config) {
      setLocalStoreDir(config.store_dir);
    }
  }, [config]);
  
  // Load installed libraries and seed archives on mount
  useEffect(() => {
    listInstalledLibraries();
    listSeedArchives();
  }, [listInstalledLibraries, listSeedArchives]);
  
  // Refresh seed archives after download/install
  useEffect(() => {
    if (!isDownloading && !isLoading) {
      listSeedArchives();
    }
  }, [isDownloading, isLoading, listSeedArchives]);
  
  const handleStoreDirChange = useCallback((value: string) => {
    setLocalStoreDir(value);
  }, []);
  
  const handleApplyStoreDir = useCallback(async () => {
    await updateConfig({ store_dir: localStoreDir });
    setActionResult({ type: 'success', message: 'Store directory updated' });
    setTimeout(() => setActionResult(null), 3000);
  }, [localStoreDir, updateConfig]);
  
  const handleRevealPath = useCallback((path: string) => {
    if (window.qv?.revealPath) {
      window.qv.revealPath(path);
    }
  }, []);
  
  // One-click download: enables network access if needed, then downloads
  const handleDownloadClick = useCallback(async (flavor: 'efficiency' | 'precision' | 'all') => {
    setActionResult(null);
    
    const needsEnable = config ? !config.allow_download : false;
    
    try {
      let result;
      if (flavor === 'all') {
        result = await downloadAll(needsEnable);
      } else {
        result = await downloadLibrary(flavor, needsEnable);
      }
      
      if (result.success) {
        const successMsg = result.messages && result.messages.length > 0 
          ? result.messages.join('; ')
          : `Successfully ${needsEnable ? 'enabled downloads and ' : ''}downloaded ${flavor === 'all' ? 'all SSSP libraries' : `SSSP ${flavor} library`}`;
        setActionResult({ type: 'success', message: successMsg });
        await listInstalledLibraries();
        await listSeedArchives();
      } else {
        const errorMsg = result.errors && result.errors.length > 0
          ? result.errors.join('; ')
          : `Download failed for ${flavor === 'all' ? 'SSSP libraries' : `SSSP ${flavor}`}`;
        setActionResult({ type: 'error', message: errorMsg });
      }
      setTimeout(() => setActionResult(null), 8000);
    } catch (e) {
      setActionResult({ 
        type: 'error', 
        message: `Download error: ${e instanceof Error ? e.message : 'Unknown error'}` 
      });
      setTimeout(() => setActionResult(null), 8000);
    }
  }, [config, downloadLibrary, downloadAll, listInstalledLibraries, listSeedArchives]);
  
  const handleInstallFromSeed = useCallback(async () => {
    setActionResult(null);
    const result = await installFromSeed();
    if (result.success) {
      setActionResult({ type: 'success', message: result.messages.join(', ') || 'Installation complete' });
      await listInstalledLibraries();
      await listSeedArchives();
    } else {
      setActionResult({ type: 'error', message: result.messages.join(', ') || 'Installation failed' });
    }
    setTimeout(() => setActionResult(null), 5000);
  }, [installFromSeed, listInstalledLibraries, listSeedArchives]);
  
  const handleAllowDownloadChange = useCallback(async (checked: boolean) => {
    await updateConfig({ allow_download: checked });
  }, [updateConfig]);
  
  const handleValidate = useCallback(async () => {
    setActionResult(null);
    const result = await validate();
    if (result) {
      if (result.ok) {
        setActionResult({ type: 'success', message: 'Configuration valid' });
      } else {
        setActionResult({ type: 'error', message: result.errors[0] || 'Validation failed' });
      }
      setTimeout(() => setActionResult(null), 5000);
    }
  }, [validate]);
  
  const handleImportSeedArchives = useCallback(async () => {
    if (!window.qv?.openFiles) {
      setActionResult({ type: 'error', message: 'File picker not available' });
      setTimeout(() => setActionResult(null), 5000);
      return;
    }
    
    setActionResult(null);
    
    try {
      const filePaths = await window.qv.openFiles({
        filters: [
          { name: 'Archive Files', extensions: ['tar.gz', 'tgz', 'zip'] },
          { name: 'All Files', extensions: ['*'] },
        ],
        properties: ['multiSelections'],
      });
      
      if (!filePaths || filePaths.length === 0) {
        return; // User cancelled
      }
      
      const result = await importSeedArchives(filePaths);
      
      if (result.errors.length > 0) {
        setActionResult({ 
          type: 'error', 
          message: `Import completed with errors: ${result.errors.join('; ')}` 
        });
      } else if (result.imported.length > 0) {
        setActionResult({ 
          type: 'success', 
          message: `Imported ${result.imported.length} archive(s). ${result.skipped.length > 0 ? `${result.skipped.length} skipped (duplicates).` : ''}` 
        });
      } else if (result.skipped.length > 0) {
        setActionResult({ 
          type: 'success', 
          message: `All archives already exist (${result.skipped.length} skipped)` 
        });
      } else {
        setActionResult({ type: 'success', message: 'Import completed' });
      }
      
      setTimeout(() => setActionResult(null), 8000);
    } catch (e) {
      setActionResult({ 
        type: 'error', 
        message: `Import failed: ${e instanceof Error ? e.message : 'Unknown error'}` 
      });
      setTimeout(() => setActionResult(null), 8000);
    }
  }, [importSeedArchives]);
  
  // Get status summary
  const hasPrecision = installedLibraries.some(lib => lib.installed && lib.flavor === 'precision');
  const hasEfficiency = installedLibraries.some(lib => lib.installed && lib.flavor === 'efficiency');
  const statusSummary = hasPrecision && hasEfficiency 
    ? 'Both Precision and Efficiency installed'
    : hasPrecision 
      ? 'Precision installed'
      : hasEfficiency
        ? 'Efficiency installed'
        : 'No libraries installed';
  
  // Get download stage label
  const getDownloadStageLabel = useCallback(() => {
    switch (downloadStage) {
      case 'downloading':
        return 'Downloading...';
      case 'verifying':
        return 'Verifying...';
      case 'extracting':
        return 'Extracting...';
      case 'installed':
        return 'Installed ✓';
      case 'error':
        return 'Error';
      default:
        return '';
    }
  }, [downloadStage]);
  
  const hasStoreDirChanges = config && localStoreDir !== config.store_dir;
  
  return (
    <div className="settings-section">
      <div className="settings-section__header">
        <h3 className="settings-section__title">
          <span className="settings-icon">⚗️</span>
          SSSP Libraries
        </h3>
      </div>
      
      <div className="settings-section__content">
        {error && (
          <div className="settings-error">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}
        
        {actionResult && (
          <div className={`settings-action-result settings-action-result--${actionResult.type}`}>
            <span>{actionResult.type === 'success' ? '✓' : '⚠️'}</span>
            <span>{actionResult.message}</span>
          </div>
        )}
        
        {!config ? (
          <p className="settings-empty">
            {isLoading ? 'Loading configuration...' : 'Configuration not available'}
          </p>
        ) : (
          <>
            {/* NORMAL VIEW - Status Summary */}
            <div className="pseudo-status-summary">
              <div className="pseudo-status-summary__label">Status:</div>
              <div className="pseudo-status-summary__value">
                {hasPrecision && hasEfficiency ? '✓ ' : hasPrecision || hasEfficiency ? '○ ' : '○ '}
                {statusSummary}
              </div>
            </div>
            
            {/* NORMAL VIEW - Download & Install Buttons */}
            <div className="pseudo-download-section">
              <div className="pseudo-download-section__buttons">
                <button
                  className="settings-btn settings-btn--primary settings-btn--download"
                  onClick={() => handleDownloadClick('precision')}
                  disabled={isLoading || isDownloading}
                  title={config.allow_download 
                    ? "Download & Install SSSP Precision library (higher accuracy)"
                    : "Click to enable network downloads and install Precision"}
                >
                  {isDownloading && downloadStage !== 'idle' ? (
                    <span>{getDownloadStageLabel()}</span>
                  ) : (
                    <span>⬇️ Download & Install Precision{!config.allow_download ? ' (Enable Network)' : ''}</span>
                  )}
                </button>
                <button
                  className="settings-btn settings-btn--primary settings-btn--download"
                  onClick={() => handleDownloadClick('efficiency')}
                  disabled={isLoading || isDownloading}
                  title={config.allow_download 
                    ? "Download & Install SSSP Efficiency library (smaller, faster)"
                    : "Click to enable network downloads and install Efficiency"}
                >
                  {isDownloading && downloadStage !== 'idle' ? (
                    <span>{getDownloadStageLabel()}</span>
                  ) : (
                    <span>⬇️ Download & Install Efficiency{!config.allow_download ? ' (Enable Network)' : ''}</span>
                  )}
                </button>
                <button
                  className="settings-btn settings-btn--primary settings-btn--download"
                  onClick={() => handleDownloadClick('all')}
                  disabled={isLoading || isDownloading}
                  title={config.allow_download 
                    ? "Download & Install both Precision and Efficiency libraries"
                    : "Click to enable network downloads and install all libraries"}
                >
                  {isDownloading && downloadStage !== 'idle' ? (
                    <span>{getDownloadStageLabel()}</span>
                  ) : (
                    <span>⬇️ Download & Install All{!config.allow_download ? ' (Enable Network)' : ''}</span>
                  )}
                </button>
              </div>
            </div>
            
            {/* NORMAL VIEW - Progress Indicator */}
            {isDownloading && downloadStage !== 'idle' && (
              <div className="pseudo-download-progress">
                <div className="pseudo-download-progress__stages">
                  <div className={`pseudo-download-progress__stage ${['downloading', 'verifying', 'extracting', 'installed'].includes(downloadStage) ? 'pseudo-download-progress__stage--active' : ''} ${downloadStage === 'installed' ? 'pseudo-download-progress__stage--completed' : ''}`}>
                    <span className="pseudo-download-progress__dot">1</span>
                    <span>Download</span>
                  </div>
                  <div className={`pseudo-download-progress__stage ${['verifying', 'extracting', 'installed'].includes(downloadStage) ? 'pseudo-download-progress__stage--active' : ''} ${downloadStage === 'installed' ? 'pseudo-download-progress__stage--completed' : ''}`}>
                    <span className="pseudo-download-progress__dot">2</span>
                    <span>Verify</span>
                  </div>
                  <div className={`pseudo-download-progress__stage ${['extracting', 'installed'].includes(downloadStage) ? 'pseudo-download-progress__stage--active' : ''} ${downloadStage === 'installed' ? 'pseudo-download-progress__stage--completed' : ''}`}>
                    <span className="pseudo-download-progress__dot">3</span>
                    <span>Extract</span>
                  </div>
                  <div className={`pseudo-download-progress__stage ${downloadStage === 'installed' ? 'pseudo-download-progress__stage--active pseudo-download-progress__stage--completed' : ''}`}>
                    <span className="pseudo-download-progress__dot">✓</span>
                    <span>Installed</span>
                  </div>
                </div>
              </div>
            )}
            
            {/* NORMAL VIEW - Installed Libraries List */}
            {installedLibraries.some(lib => lib.installed) && (
              <div className="pseudo-libraries">
                <div className="pseudo-libraries__header">Installed Libraries</div>
                <div className="pseudo-libraries__list">
                  {installedLibraries.filter(lib => lib.installed).map(lib => (
                    <div key={`${lib.version}-${lib.flavor}`} className="pseudo-library">
                      <span className="pseudo-library__name">
                        ✓ SSSP {lib.version} ({lib.flavor})
                      </span>
                      <span className="pseudo-library__info">
                        {lib.file_count} files{lib.has_cutoffs && ' • cutoffs'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* NORMAL VIEW - Store Directory (simplified) */}
            <div className="pseudo-store-dir">
              <div className="pseudo-store-dir__label">Store Directory</div>
              <div className="pseudo-store-dir__control">
                <input
                  type="text"
                  className="settings-input settings-input--path"
                  value={localStoreDir}
                  onChange={(e) => handleStoreDirChange(e.target.value)}
                  placeholder={config.default_store_dir}
                  style={{ flex: 1, marginRight: '0.5rem' }}
                />
                {localStoreDir && (
                  <button
                    className="settings-btn settings-btn--sm"
                    onClick={() => handleRevealPath(localStoreDir)}
                    title={`Open: ${localStoreDir}`}
                  >
                    📂 Open
                  </button>
                )}
                {hasStoreDirChanges && (
                  <button
                    className="settings-btn settings-btn--sm settings-btn--primary"
                    onClick={handleApplyStoreDir}
                    disabled={isLoading}
                  >
                    Apply
                  </button>
                )}
              </div>
            </div>
            
            {/* ADVANCED SECTION - Collapsed by default */}
            <div className="pseudo-advanced-section">
              <button
                className="pseudo-advanced-section__header"
                onClick={() => setAdvancedExpanded(!advancedExpanded)}
                aria-expanded={advancedExpanded}
              >
                <span className="pseudo-advanced-section__title">Advanced</span>
                <span className="pseudo-advanced-section__icon">{advancedExpanded ? '▼' : '▶'}</span>
              </button>
              
              {advancedExpanded && (
                <div className="pseudo-advanced-section__content">
                  {/* Seed Cache */}
                  <div className="pseudo-advanced-subsection">
                    <div className="pseudo-advanced-subsection__header">
                      <span className="pseudo-advanced-subsection__title">Seed Cache (Disaster Recovery)</span>
                    </div>
                    <div className="pseudo-advanced-subsection__description">
                      Archives are kept here so you can reinstall if the store is corrupted.
                    </div>
                    
                    {config.seed_dir && (
                      <div className="pseudo-advanced-subsection__field">
                        <div className="pseudo-advanced-subsection__label">Seed Directory (Advanced Cache)</div>
                        <div className="pseudo-advanced-subsection__control">
                          <code className="pseudo-advanced-subsection__path">{config.seed_dir}</code>
                          <button
                            className="settings-btn settings-btn--sm"
                            onClick={() => handleRevealPath(config.seed_dir)}
                            title={`Open: ${config.seed_dir}`}
                          >
                            📂 Open
                          </button>
                        </div>
                      </div>
                    )}
                    
                    {seedArchives.length > 0 && (
                      <div className="pseudo-advanced-subsection__archives">
                        <div className="pseudo-advanced-subsection__archives-header">Cached Archives</div>
                        <div className="pseudo-advanced-subsection__archives-list">
                          {seedArchives.map((arch, idx) => (
                            <div key={idx} className="pseudo-archive-item">
                              <span className="pseudo-archive-item__name">{arch.filename}</span>
                              <span className="pseudo-archive-item__size">
                                {(arch.size_bytes / 1024 / 1024).toFixed(1)} MB
                                {arch.sha256 && ` • SHA256: ${arch.sha256.substring(0, 16)}...`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div className="pseudo-advanced-subsection__actions">
                      <button
                        className="settings-btn settings-btn--secondary"
                        onClick={handleImportSeedArchives}
                        disabled={isLoading || isDownloading}
                        title="Import tar.gz/zip archives into seed cache"
                      >
                        Import Seed Archives…
                      </button>
                      <button
                        className="settings-btn settings-btn--primary"
                        onClick={handleInstallFromSeed}
                        disabled={isLoading || isDownloading || seedArchives.length === 0}
                        title="Re-extract cached archives into store directory"
                      >
                        Install from Seed
                      </button>
                    </div>
                  </div>
                  
                  {/* Network Behavior */}
                  <div className="pseudo-advanced-subsection">
                    <div className="pseudo-advanced-subsection__header">
                      <span className="pseudo-advanced-subsection__title">Network Behavior</span>
                    </div>
                    <div className="pseudo-advanced-subsection__field">
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={config.allow_download}
                          onChange={(e) => handleAllowDownloadChange(e.target.checked)}
                          disabled={isLoading}
                        />
                        <span className="toggle-slider"></span>
                        <span className="pseudo-advanced-subsection__toggle-label">Allow network downloads</span>
                      </label>
                    </div>
                  </div>
                  
                  {/* Validate / Diagnostics */}
                  <div className="pseudo-advanced-subsection">
                    <div className="pseudo-advanced-subsection__header">
                      <span className="pseudo-advanced-subsection__title">Diagnostics</span>
                    </div>
                    <div className="pseudo-advanced-subsection__actions">
                      <button
                        className="settings-btn"
                        onClick={handleValidate}
                        disabled={isLoading || isValidating}
                      >
                        {isValidating ? 'Validating...' : 'Validate Configuration'}
                      </button>
                    </div>
                    
                    {validationResult && (
                      <div className="pseudo-validation">
                        <div className="pseudo-validation__header">
                          <span className={`pseudo-validation__status pseudo-validation__status--${validationResult.ok ? 'ok' : 'error'}`}>
                            {validationResult.ok ? '✓ Valid' : '⚠️ Issues Found'}
                          </span>
                        </div>
                        <div className="pseudo-validation__details">
                          <div className="pseudo-validation__row">
                            <span>Repo Pseudos:</span>
                            <span className={validationResult.repo_pseudo_exists ? 'pseudo-validation--ok' : 'pseudo-validation--warn'}>
                              {validationResult.repo_pseudo_exists ? '✓ Found' : '⚠️ Missing'}
                            </span>
                          </div>
                          <div className="pseudo-validation__row">
                            <span>Store Dir:</span>
                            <span className={validationResult.store_dir_exists ? 'pseudo-validation--ok' : 'pseudo-validation--warn'}>
                              {validationResult.store_dir_exists ? '✓ Exists' : '○ Not created'}
                            </span>
                          </div>
                          <div className="pseudo-validation__row">
                            <span>Store Writable:</span>
                            <span className={validationResult.store_dir_writable ? 'pseudo-validation--ok' : 'pseudo-validation--error'}>
                              {validationResult.store_dir_writable ? '✓ Yes' : '✗ No'}
                            </span>
                          </div>
                          <div className="pseudo-validation__row">
                            <span>Seed Dir:</span>
                            <span className={validationResult.seed_dir_exists ? 'pseudo-validation--ok' : 'pseudo-validation--warn'}>
                              {validationResult.seed_dir_exists ? '✓ Exists' : '○ Not found'}
                            </span>
                          </div>
                          {validationResult.seed_dir_exists && (
                            <div className="pseudo-validation__row">
                              <span>Seed SSSP:</span>
                              <span className={validationResult.seed_has_sssp ? 'pseudo-validation--ok' : 'pseudo-validation--warn'}>
                                {validationResult.seed_has_sssp ? '✓ Found' : '○ No SSSP data'}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Repo Pseudo Info (read-only) */}
                  {config.repo_pseudo_dir && (
                    <div className="pseudo-advanced-subsection">
                      <div className="pseudo-advanced-subsection__header">
                        <span className="pseudo-advanced-subsection__title">Repo Pseudos</span>
                      </div>
                      <div className="pseudo-advanced-subsection__field">
                        <code className="pseudo-advanced-subsection__path pseudo-advanced-subsection__path--readonly">
                          {config.repo_pseudo_dir}
                        </code>
                        <span className="pseudo-advanced-subsection__note">(committed, for demos/tests)</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
