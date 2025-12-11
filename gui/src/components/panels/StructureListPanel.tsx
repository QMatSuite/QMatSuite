/**
 * StructureListPanel - Displays a list of structures in a project
 */

import { useState, useCallback } from 'react';
import type { StructureInfo } from '../../types/qv';
import './StructureListPanel.css';

interface StructureListPanelProps {
  structures: StructureInfo[] | null;
  isLoading?: boolean;
  selectedId?: string | null;
  onSelect?: (structure: StructureInfo) => void;
  onRename?: (structure: StructureInfo) => void;
  onDelete?: (structure: StructureInfo) => void;
  onRefreshProjectRegistry?: () => void;
}

export function StructureListPanel({ 
  structures, 
  isLoading, 
  selectedId,
  onSelect,
  onRename,
  onDelete,
  onRefreshProjectRegistry,
}: StructureListPanelProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const handleRefresh = useCallback(async () => {
    if (!onRefreshProjectRegistry) return;
    setIsRefreshing(true);
    try {
      await onRefreshProjectRegistry();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefreshProjectRegistry]);
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
    <div className="structure-list-panel">
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
          <span className="panel-count">{structures.length} total</span>
        </div>
      </div>
      
      <div className="structure-list">
        {structures.map((structure) => (
          <div
            key={structure.id}
            className={`structure-item ${selectedId === structure.id ? 'structure-item--selected' : ''}`}
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
                <div className="structure-item__stat">
                  <span className="stat-value">{structure.n_species}</span>
                  <span className="stat-label">species</span>
                </div>
              </div>
              
              <div className="structure-item__lattice">
                <span className="lattice-param">a={structure.lattice_params.a.toFixed(2)}</span>
                <span className="lattice-param">b={structure.lattice_params.b.toFixed(2)}</span>
                <span className="lattice-param">c={structure.lattice_params.c.toFixed(2)}</span>
              </div>
              
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
}

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
              <span className="detail-label">Species</span>
              <span className="detail-value">{structure.n_species}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">ID</span>
              <code className="detail-value">{structure.id}</code>
            </div>
          </div>
        </div>
        
        <div className="detail-section">
          <h3>Lattice Parameters</h3>
          <div className="detail-grid detail-grid--lattice">
            <div className="detail-item">
              <span className="detail-label">a</span>
              <span className="detail-value">{structure.lattice_params.a.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">b</span>
              <span className="detail-value">{structure.lattice_params.b.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">c</span>
              <span className="detail-value">{structure.lattice_params.c.toFixed(4)} Å</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">α</span>
              <span className="detail-value">{structure.lattice_params.alpha.toFixed(2)}°</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">β</span>
              <span className="detail-value">{structure.lattice_params.beta.toFixed(2)}°</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">γ</span>
              <span className="detail-value">{structure.lattice_params.gamma.toFixed(2)}°</span>
            </div>
            {structure.lattice_params.volume && (
              <div className="detail-item detail-item--full">
                <span className="detail-label">Volume</span>
                <span className="detail-value">{structure.lattice_params.volume.toFixed(2)} Å³</span>
              </div>
            )}
          </div>
        </div>
        
        <div className="detail-section">
          <h3>File Location</h3>
          <div className="file-location">
            <code className="file-location__path" title={structure.absolute_path}>
              {structure.absolute_path}
            </code>
            <button 
              className="file-location__reveal-btn"
              onClick={() => window.qv?.revealPath?.(structure.absolute_path)}
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

