/**
 * StructureListPanel - Displays a list of structures in a project
 * Supports two-panel layout: Project Structures + Online Import
 */

import { useState, useCallback, memo } from 'react';
import type { StructureInfo } from '../../types/qms';
import { OnlineImportPanel, type OnlineCandidate } from './OnlineImportPanel';
import './StructureListPanel.css';

interface StructureListPanelProps {
  structures: StructureInfo[] | null;
  isLoading?: boolean;
  selectedId?: string | null;
  onSelect?: (structure: StructureInfo) => void;
  onRename?: (structure: StructureInfo) => void;
  onDelete?: (structure: StructureInfo) => void;
  onRefreshProjectRegistry?: () => void;
  projectRoot?: string;
  // Import mode props
  leftMode?: 'project' | 'import';
  onEnterImportMode?: () => void;
  onExitImportMode?: () => void;
  onSelectOnlineCandidate?: (sessionId: string, candidateId: string) => void;
  selectedOnlineCandidateId?: string | null;
  onlineSessionId?: string | null;
  onlineCandidates?: OnlineCandidate[];
}

export const StructureListPanel = memo(function StructureListPanel({
  structures,
  isLoading,
  selectedId,
  onSelect,
  onRename,
  onDelete,
  onRefreshProjectRegistry,
  projectRoot,
  leftMode = 'project',
  onEnterImportMode,
  onExitImportMode,
  onSelectOnlineCandidate,
  selectedOnlineCandidateId,
  // These are passed but handled by OnlineImportPanel internally now
  onlineSessionId: __onlineSessionId,
  onlineCandidates: __onlineCandidates,
}: StructureListPanelProps) {
  // Suppress unused variable warnings - these props are kept for API compatibility
  void __onlineSessionId;
  void __onlineCandidates;
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Sync internal expanded state with leftMode prop
  // OnlineImportPanel needs isExpanded state, which should match leftMode === 'import'
  const isOnlinePanelExpanded = leftMode === 'import';
  
  const handleRefresh = useCallback(async () => {
    if (!onRefreshProjectRegistry) return;
    setIsRefreshing(true);
    try {
      await onRefreshProjectRegistry();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefreshProjectRegistry]);
  
  const handleEnterImportMode = useCallback(() => {
    onEnterImportMode?.();
  }, [onEnterImportMode]);
  
  const handleExitImportMode = useCallback(() => {
    onExitImportMode?.();
  }, [onExitImportMode]);
  
  const isImportMode = leftMode === 'import';
  // Project Structures Panel (Panel A)
  const renderProjectPanel = () => {
    if (isImportMode) {
      // Collapsed header-only in import mode (no body, height:0)
      const count = structures?.length || 0;
      return (
        <div className="structure-list-panel structure-list-panel--collapsed" style={{ height: 'auto', minHeight: '40px' }}>
          <button
            className="structure-list-panel__header-btn"
            onClick={handleExitImportMode}
            title="Click to return to project structures"
          >
            <span className="structure-list-panel__header-icon">←</span>
            Project Structures ({count}) — click to return
          </button>
          {/* No body content in import mode */}
        </div>
      );
    }
    
    // Expanded project panel
    if (isLoading) {
      return (
        <div className="structure-list-panel structure-list-panel--loading">
          <div className="loading-spinner" />
          <p>Loading structures...</p>
        </div>
      );
    }
    
    if (!structures) {
      return (
        <div className="structure-list-panel structure-list-panel--empty">
          <div className="panel-placeholder">
            <span className="panel-icon">🔬</span>
            <h3>No Structures Loaded</h3>
            <p>Click "List Structures" to view structures in this project.</p>
          </div>
        </div>
      );
    }
    
    if (structures.length === 0) {
      return (
        <div className="structure-list-panel structure-list-panel--empty">
          <div className="panel-placeholder">
            <span className="panel-icon">🔬</span>
            <h3>No Structures Found</h3>
            <p>This project doesn't have any structures yet.</p>
          </div>
        </div>
      );
    }
    
    return (
      <div className="structure-list-panel" data-testid="qms-structures-view">
        <div className="panel-header">
          <h2 className="panel-title">
            <span className="panel-icon">🔬</span>
            Structures
          </h2>
          <div className="panel-header__actions">
            {onRefreshProjectRegistry && (
              <button
                className="panel-refresh-btn"
                onClick={handleRefresh}
                disabled={isRefreshing}
                title="Refresh project registry"
              >
                {isRefreshing ? '⟳' : '🔄'} Refresh
              </button>
            )}
            <span className="panel-count" data-testid="qms-structures-count">{structures.length} total</span>
          </div>
        </div>

        <div className="structure-list">
          {structures.map((structure) => (
            <div
              key={structure.ulid}
              className={`structure-item ${selectedId === structure.ulid ? 'structure-item--selected' : ''}`}
              data-testid="qms-structure-row"
            >
              <button
                className="structure-item__content"
                onClick={() => onSelect?.(structure)}
              >
                <div className="structure-item__main">
                  <div className="structure-item__name">{structure.name}</div>
                  <div className="structure-item__formula">{structure.formula}</div>
                </div>
                
                <div className="structure-item__details">
                  <div className="structure-item__stat">
                    <span className="stat-value">{structure.n_atoms}</span>
                    <span className="stat-label">atoms</span>
                  </div>
                </div>

                {structure.lattice_abc && (
                <div className="structure-item__lattice">
                  <span className="lattice-param">a={structure.lattice_abc[0]?.toFixed(2)}</span>
                  <span className="lattice-param">b={structure.lattice_abc[1]?.toFixed(2)}</span>
                  <span className="lattice-param">c={structure.lattice_abc[2]?.toFixed(2)}</span>
                </div>
                )}
                
                <div className="structure-item__path">
                  <code>{structure.path}</code>
                </div>
              </button>
              
              {(onRename || onDelete) && (
                <div className="structure-item__actions">
                  {onRename && (
                    <button
                      className="item-action-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRename(structure);
                      }}
                      title="Rename structure"
                    >
                      ✏️
                    </button>
                  )}
                  {onDelete && (
                    <button
                      className="item-action-btn item-action-btn--danger"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(structure);
                      }}
                      title="Delete structure"
                    >
                      🗑️
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  // Two-panel layout
  return (
    <div className="structure-list-panels-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2, 8px)', height: '100%' }}>
      {renderProjectPanel()}
      {projectRoot && (
        <OnlineImportPanel
          projectRoot={projectRoot}
          isExpanded={isOnlinePanelExpanded}
          onExpand={handleEnterImportMode}
          onCollapse={handleExitImportMode}
          onSelectCandidate={onSelectOnlineCandidate || (() => {})}
          selectedCandidateId={selectedOnlineCandidateId || null}
        />
      )}
    </div>
  );
});

// =============================================================================
// Structure Detail View
// =============================================================================

interface StructureDetailPanelProps {
  structure: StructureInfo | null;
  onClose?: () => void;
}

export function StructureDetailPanel({ structure, onClose }: StructureDetailPanelProps) {
  if (!structure) {
    return null;
  }
  
  return (
    <div className="structure-detail-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📐</span>
          {structure.name}
        </h2>
        {onClose && (
          <button className="panel-close" onClick={onClose}>×</button>
        )}
      </div>
      
      <div className="panel-content">
        <div className="detail-section">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Formula</span>
              <span className="detail-value">{structure.formula}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Atoms</span>
              <span className="detail-value">{structure.n_atoms}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">ULID</span>
              <code className="detail-value">{structure.ulid}</code>
            </div>
          </div>
        </div>

        {structure.lattice_abc && structure.lattice_angles && (
        <div className="detail-section">
          <h3>Lattice Parameters</h3>
          <div className="detail-grid detail-grid--lattice">
            <div className="detail-item">
              <span className="detail-label">a</span>
              <span className="detail-value">{structure.lattice_abc[0]?.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">b</span>
              <span className="detail-value">{structure.lattice_abc[1]?.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">c</span>
              <span className="detail-value">{structure.lattice_abc[2]?.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">α</span>
              <span className="detail-value">{structure.lattice_angles[0]?.toFixed(2)}°</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">β</span>
              <span className="detail-value">{structure.lattice_angles[1]?.toFixed(2)}°</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">γ</span>
              <span className="detail-value">{structure.lattice_angles[2]?.toFixed(2)}°</span>
            </div>
            {structure.cell_volume_ang3 && (
              <div className="detail-item detail-item--full">
                <span className="detail-label">Volume</span>
                <span className="detail-value">{structure.cell_volume_ang3.toFixed(2)} Å³</span>
              </div>
            )}
          </div>
        </div>
        )}

        <div className="detail-section">
          <h3>File Location</h3>
          <div className="file-location">
            <code className="file-location__path" title={structure.path}>
              {structure.path}
            </code>
            <button
              className="file-location__reveal-btn"
              onClick={() => window.qms?.revealPath?.(structure.path)}
              title="Reveal in Finder"
            >
              📂 Reveal
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

