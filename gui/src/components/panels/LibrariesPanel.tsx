/**
 * LibrariesPanel - Generic library manager UI
 * 
 * Provides package-manager-like interface for managing pseudopotential libraries
 * (SSSP, PseudoDojo, etc.)
 */

import { useState, useCallback } from 'react';
import { useLibraryManager, type LibraryStatus, type InstallSource } from '../../hooks/useLibraryManager';
import './SettingsPanel.css';

interface LibrariesPanelProps {
  onRevealPath?: (path: string) => void;
}

export function LibrariesPanel({ onRevealPath }: LibrariesPanelProps) {
  const manager = useLibraryManager();
  const {
    libraries = [],
    libraryStatuses = new Map(),
    storeSize,
    isLoading,
    isInstalling,
    installStage,
    storeDir,
    seedDir,
    allowDownload,
    installLibrary,
    removeLibrary,
    repairLibrary,
    loadLibraryStatus,
  } = manager;
  
  const [selectedLibrary, setSelectedLibrary] = useState<string | null>(null);
  const [showInstallModal, setShowInstallModal] = useState(false);
  const [showRemoveModal, setShowRemoveModal] = useState(false);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string; details?: string } | null>(null);
  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [filterTab, setFilterTab] = useState<'all' | 'installed' | 'available'>('all');
  
  const handleRevealPath = useCallback((path: string) => {
    if (onRevealPath) {
      onRevealPath(path);
    } else if (window.qv?.revealPath) {
      window.qv.revealPath(path);
    }
  }, [onRevealPath]);
  
  const handleInstall = useCallback((libraryId: string) => {
    setSelectedLibrary(libraryId);
    setShowInstallModal(true);
  }, []);
  
  const handleRemove = useCallback((libraryId: string) => {
    setSelectedLibrary(libraryId);
    setShowRemoveModal(true);
  }, []);
  
  const handleRepair = useCallback(async (libraryId: string) => {
    const status = libraryStatuses.get(libraryId);
    if (!status) return;
    
    setActionResult(null);
    const result = await repairLibrary(libraryId, status.installed_variants);
    
    if (result.success) {
      setActionResult({ type: 'success', message: result.messages.join('; ') || 'Repair completed' });
    } else {
      setActionResult({ type: 'error', message: result.errors.join('; ') || 'Repair failed' });
    }
    
    setTimeout(() => setActionResult(null), 5000);
  }, [libraryStatuses, repairLibrary]);
  
  // Compute installed count and filter libraries
  const installedCount = libraryStatuses ? Array.from(libraryStatuses.values()).filter(
    s => s && (s.status === 'installed' || s.status === 'partial')
  ).length : 0;
  
  // Filter libraries based on selected tab
  const filteredLibraries = libraries.filter(lib => {
    if (filterTab === 'all') return true;
    const status = libraryStatuses.get(lib.id);
    if (!status) return filterTab === 'available';
    if (filterTab === 'installed') {
      return status.status === 'installed' || status.status === 'partial';
    }
    if (filterTab === 'available') {
      return status.status === 'not_installed';
    }
    return true;
  });
  
  // Format store size
  const formatSize = (bytes: number | null): string => {
    if (bytes === null) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };
  
  const getStatusBadge = (status: LibraryStatus['status']) => {
    switch (status) {
      case 'installed':
        return <span className="library-status-badge library-status-badge--installed">✓ Installed</span>;
      case 'partial':
        return <span className="library-status-badge library-status-badge--partial">○ Partial</span>;
      case 'not_installed':
        return <span className="library-status-badge library-status-badge--not-installed">○ Not Installed</span>;
    }
  };
  
  return (
    <div className="settings-section">
      <div className="settings-section__header">
        <h3 className="settings-section__title">
          <span className="settings-icon">📚</span>
          Libraries
        </h3>
      </div>
      
      <div className="settings-section__content">
        {actionResult && (
          <div className={`settings-action-result settings-action-result--${actionResult.type}`}>
            <span>{actionResult.type === 'success' ? '✓' : '⚠️'}</span>
            <span>{actionResult.message}</span>
            {actionResult.details && <span className="settings-action-result__details">{actionResult.details}</span>}
          </div>
        )}
        
        {/* Overview Header */}
        <div className="libraries-overview">
          <div className="libraries-overview__stats">
            <div className="libraries-overview__stat">
              <span className="libraries-overview__stat-label">Installed:</span>
              <span className="libraries-overview__stat-value">{installedCount} libraries</span>
            </div>
            {storeSize !== null && (
              <div className="libraries-overview__stat">
                <span className="libraries-overview__stat-label">Disk usage:</span>
                <span className="libraries-overview__stat-value">{formatSize(storeSize)}</span>
              </div>
            )}
          </div>
          
          {storeDir && (
            <div className="libraries-overview__path">
              <span className="libraries-overview__path-label">Store directory:</span>
              <code className="libraries-overview__path-value">{storeDir}</code>
              <button
                className="settings-btn settings-btn--sm"
                onClick={() => handleRevealPath(storeDir)}
                title={`Open: ${storeDir}`}
              >
                📂 Open
              </button>
            </div>
          )}
        </div>
        
        {/* Filter Tabs */}
        <div className="libraries-filter-tabs">
          <button
            className={`libraries-filter-tab ${filterTab === 'all' ? 'active' : ''}`}
            onClick={() => setFilterTab('all')}
          >
            All
          </button>
          <button
            className={`libraries-filter-tab ${filterTab === 'installed' ? 'active' : ''}`}
            onClick={() => setFilterTab('installed')}
          >
            Installed ({installedCount})
          </button>
          <button
            className={`libraries-filter-tab ${filterTab === 'available' ? 'active' : ''}`}
            onClick={() => setFilterTab('available')}
          >
            Available
          </button>
        </div>
        
        {/* Library List */}
        <div className="libraries-list">
          {filteredLibraries && filteredLibraries.length > 0 ? filteredLibraries.map(lib => {
            const status = libraryStatuses.get(lib.id);
            if (!status) {
              // Loading state
              return (
                <div key={lib.id} className="library-card library-card--loading">
                  <div className="library-card__header">
                    <span className="library-card__name">{lib.name}</span>
                    <span className="library-card__loading">Loading...</span>
                  </div>
                </div>
              );
            }
            
            const isInstalled = status.status === 'installed' || status.status === 'partial';
            const isAvailable = status.status === 'not_installed';
            
            return (
              <div key={lib.id} className={`library-card ${isInstalled ? 'library-card--installed' : ''} ${isAvailable ? 'library-card--available' : ''}`}>
                <div className="library-card__header">
                  <div className="library-card__info">
                    <span className="library-card__name">{lib.name}</span>
                    <span className="library-card__description">{lib.description}</span>
                  </div>
                  {getStatusBadge(status.status)}
                </div>
                
                <div className="library-card__variants">
                  <span className="library-card__variants-label">Variants:</span>
                  <div className="library-card__variants-chips">
                    {(status.variant_statuses || []).map(vs => (
                      <span
                        key={vs.variant}
                        className={`library-variant-chip ${vs.installed ? 'library-variant-chip--installed' : ''}`}
                        title={vs.installed 
                          ? `Installed: ${vs.file_count} files${vs.size_bytes ? ` (${formatSize(vs.size_bytes)})` : ''}`
                          : 'Not installed'}
                      >
                        {vs.variant}
                        {vs.installed && ' ✓'}
                      </span>
                    ))}
                  </div>
                </div>
                
                <div className="library-card__actions">
                  <button
                    className="settings-btn settings-btn--primary"
                    onClick={() => handleInstall(lib.id)}
                    disabled={isInstalling || isLoading}
                  >
                    Install…
                  </button>
                  {status.installed_variants && status.installed_variants.length > 0 && (
                    <>
                      <button
                        className="settings-btn"
                        onClick={() => handleRemove(lib.id)}
                        disabled={isInstalling || isLoading}
                      >
                        Remove…
                      </button>
                      {seedDir && (
                        <button
                          className="settings-btn settings-btn--secondary"
                          onClick={() => handleRepair(lib.id)}
                          disabled={isInstalling || isLoading}
                          title="Re-extract from seed cache"
                        >
                          Repair
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          }) : (
            <div className="library-card library-card--loading">
              <div className="library-card__header">
                <span className="library-card__loading">
                  {libraries.length === 0 ? 'Loading libraries...' : `No ${filterTab === 'all' ? '' : filterTab} libraries found`}
                </span>
              </div>
            </div>
          )}
        </div>
        
        {/* Advanced Section */}
        <div className="libraries-advanced">
          <button
            className="libraries-advanced__header"
            onClick={() => setAdvancedExpanded(!advancedExpanded)}
            aria-expanded={advancedExpanded}
          >
            <span className="libraries-advanced__title">Advanced</span>
            <span className="libraries-advanced__icon">{advancedExpanded ? '▼' : '▶'}</span>
          </button>
          
          {advancedExpanded && (
            <div className="libraries-advanced__content">
              {seedDir && (
                <div className="libraries-advanced__field">
                  <span className="libraries-advanced__label">Seed cache:</span>
                  <code className="libraries-advanced__path">{seedDir}</code>
                  <button
                    className="settings-btn settings-btn--sm"
                    onClick={() => handleRevealPath(seedDir)}
                    title={`Open: ${seedDir}`}
                  >
                    📂 Open
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Modals */}
      {showInstallModal && selectedLibrary && (() => {
        const lib = libraries.find(l => l.id === selectedLibrary);
        if (!lib) {
          setShowInstallModal(false);
          return null;
        }
        return (
          <InstallLibraryModal
            key={`install-${selectedLibrary}`}
            libraryId={selectedLibrary}
            library={lib}
            status={libraryStatuses.get(selectedLibrary)}
            allowDownload={allowDownload}
            onInstall={async (variants, source, localPaths, force) => {
              setShowInstallModal(false);
              setActionResult(null);
              const result = await installLibrary(selectedLibrary, variants, source, localPaths, force);
              if (result.success) {
                const messages = result.messages || [];
                const warnings = result.warnings || [];
                const details = warnings.length > 0 ? warnings.join('; ') : undefined;
                setActionResult({ 
                  type: 'success', 
                  message: messages.join('; ') || 'Installation completed',
                  details
                });
              } else {
                setActionResult({ 
                  type: 'error', 
                  message: result.errors.join('; ') || 'Installation failed' 
                });
              }
              setTimeout(() => setActionResult(null), 10000);
            }}
            onClose={() => setShowInstallModal(false)}
            installStage={installStage}
            isInstalling={isInstalling}
          />
        );
      })()}
      
      {showRemoveModal && selectedLibrary && (() => {
        const lib = libraries.find(l => l.id === selectedLibrary);
        if (!lib) {
          setShowRemoveModal(false);
          return null;
        }
        return (
          <RemoveLibraryModal
            key={`remove-${selectedLibrary}`}
            libraryId={selectedLibrary}
            library={lib}
            status={libraryStatuses.get(selectedLibrary)}
            onRemove={async (variants) => {
              setShowRemoveModal(false);
              setActionResult(null);
              const result = await removeLibrary(selectedLibrary, variants);
              if (result.success) {
                setActionResult({ type: 'success', message: result.messages.join('; ') || 'Removal completed' });
              } else {
                setActionResult({ type: 'error', message: result.errors.join('; ') || 'Removal failed' });
              }
              setTimeout(() => setActionResult(null), 5000);
            }}
            onClose={() => setShowRemoveModal(false)}
          />
        );
      })()}
    </div>
  );
}

interface InstallLibraryModalProps {
  libraryId: string;
  library: { id: string; name: string; supported_variants: string[]; default_variants: string[] };
  status: LibraryStatus | undefined;
  allowDownload: boolean;
  onInstall: (variants: string[], source: InstallSource, localPaths?: string[], force?: boolean) => Promise<void>;
  onClose: () => void;
  installStage: string;
  isInstalling: boolean;
}

function InstallLibraryModal({
  library,
  status,
  allowDownload,
  onInstall,
  onClose,
  installStage,
  isInstalling,
}: InstallLibraryModalProps) {
  const [selectedVariants, setSelectedVariants] = useState<string[]>(library.default_variants);
  const [source, setSource] = useState<InstallSource>('github_release');
  const [localPaths, setLocalPaths] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const handleVariantToggle = (variant: string) => {
    setSelectedVariants(prev =>
      prev.includes(variant)
        ? prev.filter(v => v !== variant)
        : [...prev, variant]
    );
  };
  
  const handleSourceChange = (newSource: InstallSource) => {
    setSource(newSource);
    if (newSource === 'local_archive') {
      setShowAdvanced(true);
    }
  };
  
  const handleSelectFiles = async () => {
    if (!window.qv?.openFiles) return;
    
    const paths = await window.qv.openFiles({
      filters: [
        { name: 'Archive Files', extensions: ['tar.gz', 'tgz', 'zip'] },
        { name: 'All Files', extensions: ['*'] },
      ],
      properties: ['multiSelections'],
    });
    
    if (paths && paths.length > 0) {
      setLocalPaths(paths);
    }
  };
  
  const handleInstall = async () => {
    if (selectedVariants.length === 0) return;
    if (source === 'local_archive' && localPaths.length === 0) {
      alert('Please select archive files');
      return;
    }
    
    // If network is disabled and source is github_release, enable it automatically
    const force = !allowDownload && source === 'github_release';
    await onInstall(selectedVariants, source, localPaths.length > 0 ? localPaths : undefined, force);
  };
  
  const getStageLabel = () => {
    switch (installStage) {
      case 'downloading': return 'Downloading...';
      case 'verifying': return 'Verifying...';
      case 'extracting': return 'Extracting...';
      case 'installed': return 'Installed ✓';
      case 'error': return 'Error';
      default: return '';
    }
  };
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Install {library.name}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          {/* Variants */}
          <div className="modal-field">
            <label className="modal-label">Variants:</label>
            <div className="modal-checkboxes">
              {(library.supported_variants || []).map(variant => (
                <label key={variant} className="modal-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedVariants.includes(variant)}
                    onChange={() => handleVariantToggle(variant)}
                    disabled={isInstalling}
                  />
                  <span>
                    {variant}
                    {library.default_variants.includes(variant) && ' (recommended)'}
                  </span>
                </label>
              ))}
            </div>
          </div>
          
          {/* Source */}
          <div className="modal-field">
            <label className="modal-label">Source:</label>
            <div className="modal-radio-group">
              <label className="modal-radio">
                <input
                  type="radio"
                  name="source"
                  value="github_release"
                  checked={source === 'github_release'}
                  onChange={() => handleSourceChange('github_release')}
                  disabled={isInstalling}
                />
                <span>GitHub Online{!allowDownload && ' (Enable Network)'}</span>
              </label>
              <label className="modal-radio">
                <input
                  type="radio"
                  name="source"
                  value="seed"
                  checked={source === 'seed'}
                  onChange={() => handleSourceChange('seed')}
                  disabled={isInstalling}
                />
                <span>Seed Cache</span>
              </label>
              <label className="modal-radio">
                <input
                  type="radio"
                  name="source"
                  value="local_archive"
                  checked={source === 'local_archive'}
                  onChange={() => handleSourceChange('local_archive')}
                  disabled={isInstalling}
                />
                <span>Local Archive</span>
              </label>
            </div>
          </div>
          
          {/* Local Archive File Selection */}
          {source === 'local_archive' && (
            <div className="modal-field">
              <label className="modal-label">Archive Files:</label>
              <button
                className="settings-btn"
                onClick={handleSelectFiles}
                disabled={isInstalling}
              >
                Select Files…
              </button>
              {localPaths.length > 0 && (
                <div className="modal-file-list">
                  {(localPaths || []).map((path, i) => (
                    <div key={i} className="modal-file-item">{path}</div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {/* Progress */}
          {isInstalling && installStage !== 'idle' && (
            <div className="modal-progress">
              <div className="modal-progress-stages">
                <div className={`modal-progress-stage ${['downloading', 'verifying', 'extracting', 'installed'].includes(installStage) ? 'active' : ''} ${installStage === 'installed' ? 'completed' : ''}`}>
                  <span>1</span> Download
                </div>
                <div className={`modal-progress-stage ${['verifying', 'extracting', 'installed'].includes(installStage) ? 'active' : ''} ${installStage === 'installed' ? 'completed' : ''}`}>
                  <span>2</span> Verify
                </div>
                <div className={`modal-progress-stage ${['extracting', 'installed'].includes(installStage) ? 'active' : ''} ${installStage === 'installed' ? 'completed' : ''}`}>
                  <span>3</span> Extract
                </div>
                <div className={`modal-progress-stage ${installStage === 'installed' ? 'active completed' : ''}`}>
                  <span>✓</span> Installed
                </div>
              </div>
              {getStageLabel() && (
                <div className="modal-progress-label">{getStageLabel()}</div>
              )}
            </div>
          )}
        </div>
        
        <div className="modal-footer">
          <button
            className="settings-btn"
            onClick={onClose}
            disabled={isInstalling}
          >
            Cancel
          </button>
          <button
            className="settings-btn settings-btn--primary"
            onClick={handleInstall}
            disabled={isInstalling || selectedVariants.length === 0 || (source === 'local_archive' && localPaths.length === 0)}
          >
            {isInstalling ? getStageLabel() || 'Installing...' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface RemoveLibraryModalProps {
  libraryId: string;
  library: { id: string; name: string };
  status: LibraryStatus | undefined;
  onRemove: (variants: string[]) => Promise<void>;
  onClose: () => void;
}

function RemoveLibraryModal({
  library,
  status,
  onRemove,
  onClose,
}: RemoveLibraryModalProps) {
  const [selectedVariants, setSelectedVariants] = useState<string[]>(
    status?.installed_variants || []
  );
  const [isRemoving, setIsRemoving] = useState(false);
  
  const handleVariantToggle = (variant: string) => {
    setSelectedVariants(prev =>
      prev.includes(variant)
        ? prev.filter(v => v !== variant)
        : [...prev, variant]
    );
  };
  
  const handleRemove = async () => {
    if (selectedVariants.length === 0) return;
    
    setIsRemoving(true);
    await onRemove(selectedVariants);
    setIsRemoving(false);
  };
  
  if (!status || status.installed_variants.length === 0) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3 className="modal-title">Remove {library.name}</h3>
            <button className="modal-close" onClick={onClose}>×</button>
          </div>
          <div className="modal-body">
            <p>No variants installed.</p>
          </div>
          <div className="modal-footer">
            <button className="settings-btn" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    );
  }
  
  // Compute estimated freed space
  const estimatedFreed = status.variant_statuses
    .filter(vs => selectedVariants.includes(vs.variant) && vs.installed)
    .reduce((sum, vs) => sum + (vs.size_bytes || 0), 0);
  
  const formatSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Remove {library.name}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          <div className="modal-field">
            <label className="modal-label">Select variants to remove:</label>
            <div className="modal-checkboxes">
              {(status.variant_statuses || [])
                .filter(vs => vs && vs.installed)
                .map(vs => (
                  <label key={vs.variant} className="modal-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedVariants.includes(vs.variant)}
                      onChange={() => handleVariantToggle(vs.variant)}
                      disabled={isRemoving}
                    />
                    <span>
                      {vs.variant} ({vs.file_count} files{vs.size_bytes ? `, ${formatSize(vs.size_bytes)}` : ''})
                    </span>
                  </label>
                ))}
            </div>
          </div>
          
          {estimatedFreed > 0 && (
            <div className="modal-info">
              Estimated freed space: <strong>{formatSize(estimatedFreed)}</strong>
            </div>
          )}
        </div>
        
        <div className="modal-footer">
          <button
            className="settings-btn"
            onClick={onClose}
            disabled={isRemoving}
          >
            Cancel
          </button>
          <button
            className="settings-btn settings-btn--danger"
            onClick={handleRemove}
            disabled={isRemoving || selectedVariants.length === 0}
          >
            {isRemoving ? 'Removing...' : 'Remove'}
          </button>
        </div>
      </div>
    </div>
  );
}

