/**
 * PseudoArchivesPanel - Generic pseudopotential archives management
 * 
 * Displays all archives from MANIFEST_PSEUDO_SEED.json in a grouped table,
 * with install status and actions (Install/Reinstall/Verify).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { ArchiveStatus } from '../../types/qv';
import './PseudoArchivesPanel.css';

interface GroupedArchives {
  [key: string]: ArchiveStatus[];
}

export function PseudoArchivesPanel() {
  const qv = useQVClient();
  const [archives, setArchives] = useState<ArchiveStatus[]>([]);
  const [groupedArchives, setGroupedArchives] = useState<GroupedArchives>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installing, setInstalling] = useState<Set<string>>(new Set());
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Load archives on mount
  useEffect(() => {
    loadArchives();
  }, []);

  const loadArchives = useCallback(async () => {
    if (!qv) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await qv.listPseudoArchivesStatus();
      if (response.ok && response.data) {
        const archivesList = response.data.archives || [];
        setArchives(archivesList);
        
        // Group by library_name + library_version
        const grouped: GroupedArchives = {};
        for (const archive of archivesList) {
          const key = `${archive.library_name} ${archive.library_version}`;
          if (!grouped[key]) {
            grouped[key] = [];
          }
          grouped[key].push(archive);
        }
        setGroupedArchives(grouped);
      } else {
        setError(response.error || 'Failed to load archives');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [qv]);

  const handleInstall = useCallback(async (assetName: string) => {
    if (!qv || installing.has(assetName)) return;
    
    setInstalling(prev => new Set(prev).add(assetName));
    setActionResult(null);
    
    try {
      const response = await qv.installPseudoArchive(assetName);
      if (response.ok && response.data) {
        const result = response.data;
        if (result.success) {
          setActionResult({
            type: 'success',
            message: result.messages?.join('; ') || `Successfully installed ${assetName}`,
          });
          // Reload archives to refresh status
          await loadArchives();
          // Emit global event to refresh pseudo options in other components
          window.dispatchEvent(new CustomEvent('pseudo-archives-changed', {
            detail: { asset_name: assetName, action: 'installed' }
          }));
        } else {
          setActionResult({
            type: 'error',
            message: result.errors?.join('; ') || `Failed to install ${assetName}`,
          });
        }
      } else {
        setActionResult({
          type: 'error',
          message: response.error || `Failed to install ${assetName}`,
        });
      }
    } catch (e) {
      setActionResult({
        type: 'error',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    } finally {
      setInstalling(prev => {
        const next = new Set(prev);
        next.delete(assetName);
        return next;
      });
      setTimeout(() => setActionResult(null), 5000);
    }
  }, [qv, installing, loadArchives]);

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusBadge = (archive: ArchiveStatus) => {
    if (archive.installed && !archive.corrupt) {
      return <span className="archive-status archive-status--installed">✓ Installed</span>;
    }
    if (archive.corrupt) {
      return <span className="archive-status archive-status--corrupt">⚠ Corrupt</span>;
    }
    return <span className="archive-status archive-status--not-installed">⬜ Not installed</span>;
  };

  const getActionButton = (archive: ArchiveStatus) => {
    const isInstalling = installing.has(archive.asset_name);
    
    if (archive.corrupt) {
      return (
        <button
          className="archive-action archive-action--reinstall"
          onClick={() => handleInstall(archive.asset_name)}
          disabled={isInstalling}
        >
          {isInstalling ? '⏳ Installing...' : '🔄 Reinstall'}
        </button>
      );
    }
    
    if (archive.installed) {
      return (
        <button
          className="archive-action archive-action--verify"
          onClick={() => handleInstall(archive.asset_name)}
          disabled={isInstalling}
          title="Re-verify and reinstall if needed"
        >
          {isInstalling ? '⏳ Verifying...' : '✓ Verify'}
        </button>
      );
    }
    
    return (
      <button
        className="archive-action archive-action--install"
        onClick={() => handleInstall(archive.asset_name)}
        disabled={isInstalling}
      >
        {isInstalling ? '⏳ Installing...' : '⬇ Install'}
      </button>
    );
  };

  if (isLoading) {
    return (
      <div className="settings-section">
        <div className="settings-section__header">
          <h3 className="settings-section__title">
            <span className="settings-icon">📦</span>
            Pseudopotential Archives
          </h3>
        </div>
        <div className="settings-section__content">
          <p>Loading archives...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-section">
      <div className="settings-section__header">
        <h3 className="settings-section__title">
          <span className="settings-icon">📦</span>
          Pseudopotential Archives
        </h3>
        <button
          className="settings-btn settings-btn--sm"
          onClick={loadArchives}
          disabled={isLoading}
        >
          🔄 Refresh
        </button>
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
        
        {Object.keys(groupedArchives).length === 0 ? (
          <p className="settings-empty">No archives found in manifest.</p>
        ) : (
          <div className="pseudo-archives-table">
            {Object.entries(groupedArchives).map(([groupKey, groupArchives]) => (
              <div key={groupKey} className="archive-group">
                <div className="archive-group__header">
                  <h4 className="archive-group__title">{groupKey}</h4>
                  <span className="archive-group__count">
                    {groupArchives.filter(a => a.installed && !a.corrupt).length} / {groupArchives.length} installed
                  </span>
                </div>
                
                <table className="archive-table">
                  <thead>
                    <tr>
                      <th>Archive</th>
                      <th>Tags</th>
                      <th>Size</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupArchives.map((archive) => (
                      <tr key={archive.asset_name} className={archive.corrupt ? 'archive-row--corrupt' : ''}>
                        <td className="archive-name">{archive.asset_name}</td>
                        <td className="archive-tags">
                          {archive.xc && <span className="archive-tag">{archive.xc}</span>}
                          {archive.quality && <span className="archive-tag">{archive.quality}</span>}
                          {archive.type && <span className="archive-tag">{archive.type}</span>}
                          {archive.relativistic && <span className="archive-tag">{archive.relativistic}</span>}
                          {archive.category && <span className="archive-tag">{archive.category}</span>}
                        </td>
                        <td className="archive-size">{formatSize(archive.size_bytes)}</td>
                        <td className="archive-status-cell">
                          {getStatusBadge(archive)}
                          {archive.warning && (
                            <span className="archive-warning" title={archive.warning}>⚠️</span>
                          )}
                        </td>
                        <td className="archive-action-cell">
                          {getActionButton(archive)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

