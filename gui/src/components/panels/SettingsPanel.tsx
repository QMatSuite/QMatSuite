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
import { LibrariesPanel } from './LibrariesPanel';
import { PseudoArchivesPanel } from '../settings/PseudoArchivesPanel';
import type { QEDetectionResult, EnvironmentInfo, QVResult } from '../../types/qv';
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
      const response = await window.qv.request('get_qe_parameter_metadata_debug_info', {});
      if (response.ok && response.data) {
        setQeMetadataDebugInfo(response.data);
      }
    } catch (e) {
      // Silently fail - debug info is optional
      console.debug('[Settings] Failed to fetch QE metadata debug info', e);
    }
  }, [qv]);
  
  // Fetch QE engine info on mount
  const fetchQEEngineInfo = useCallback(async () => {
    if (!qv) return;
    try {
      const response = await qv.call('list_qe_engines', {});
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
  }, [qv]);
  
  // Fetch environment info on mount
  useEffect(() => {
    fetchQEEngineInfo();
  }, [fetchQEEngineInfo]);
  
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
                  if (!qv) return;
                  setIsSettingQE(true);
                  setQeError(null);
                  try {
                    const response = await qv.call('set_qe_engine', { bin_dir: null });
                    if (response.ok) {
                      await fetchQEEngineInfo();
                      // Also refresh QE detection
                      const qeResponse = await window.qv?.request<QEDetectionResult>('detect_qe', {});
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
                  if (!window.qv?.openDirectory) {
                    setQeError('File picker not available');
                    return;
                  }
                  
                  setIsSettingQE(true);
                  setQeError(null);
                  try {
                    const selectedDir = await window.qv.openDirectory();
                    if (!selectedDir) {
                      setIsSettingQE(false);
                      return;
                    }
                    
                    // Validate: check for pw.x or pw.x.exe
                    const pwX = `${selectedDir}/pw.x`;
                    const pwExe = `${selectedDir}/pw.x.exe`;
                    
                    // Note: We can't directly check file existence from frontend,
                    // so we rely on backend validation
                    const response = await qv.call('set_qe_engine', { bin_dir: selectedDir });
                    if (response.ok) {
                      await fetchQEEngineInfo();
                      // Also refresh QE detection
                      const qeResponse = await window.qv?.request<QEDetectionResult>('detect_qe', {});
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
