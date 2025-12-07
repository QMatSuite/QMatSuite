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

import { useState, useCallback, useEffect } from 'react';
import type { QEDetectionResult, EnvironmentInfo } from '../../types/qv';
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
  const [envInfo, setEnvInfo] = useState<EnvironmentInfo | null>(null);
  const [qeInfo, setQeInfo] = useState<QEDetectionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
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
                Automatically load analysis when selecting a workflow
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
  );
}

