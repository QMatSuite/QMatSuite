/**
 * StructureDetailPanel - Rich details panel for structures (project and online)
 * 
 * Shows prioritized overview fields and collapsible advanced sections.
 * Supports both project structures and online candidates with provenance metadata.
 */

import { useState, useMemo } from 'react';
import type { StructureModel, Provenance } from '../../types/qv';
import './StructureDetailPanel.css';

interface StructureDetailPanelProps {
  model: StructureModel | null;
  onClose?: () => void;
}

// Helper: Get first available value from a list of keys
function getFirstAvailable(obj: any, keys: string[]): any {
  if (!obj) return null;
  for (const key of keys) {
    const value = getNestedValue(obj, key);
    if (value !== null && value !== undefined && value !== '') {
      return value;
    }
  }
  return null;
}

// Helper: Get nested value by dot-separated path
function getNestedValue(obj: any, path: string): any {
  const parts = path.split('.');
  let current = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') {
      return null;
    }
    current = current[part];
  }
  return current;
}

// Helper: Format space group display
function formatSpaceGroup(provenance: Provenance | null | undefined): string | null {
  if (!provenance) return null;
  
  const symbol = getFirstAvailable(provenance, [
    'extras.spacegroup_international',
    'attributes.space_group_symbol',
    'attributes.spacegroup_international',
  ]);
  
  const number = getFirstAvailable(provenance, [
    'extras.spacegroup_number',
    'attributes.space_group_number',
  ]);
  
  if (symbol) {
    return number ? `${symbol} (No. ${number})` : symbol;
  }
  return null;
}

// Helper: Format dimensionality
function formatDimensionality(provenance: Provenance | null | undefined): string | null {
  if (!provenance) return null;
  
  const dim = getFirstAvailable(provenance, [
    'attributes.dimensionality',
    'extras.dimensionality',
  ]);
  
  if (dim != null) {
    return `${dim}D`;
  }
  return null;
}

// Helper: Check for partial occupancies
function hasPartialOccupancies(provenance: Provenance | null | undefined): boolean {
  if (!provenance) return false;
  
  const partialOcc = getFirstAvailable(provenance, [
    'extras.partial_occupancies',
  ]);
  
  if (partialOcc === true || partialOcc === 'true' || partialOcc === 'yes') {
    return true;
  }
  
  const features = getFirstAvailable(provenance, ['attributes.structure_features']);
  if (Array.isArray(features)) {
    return features.some((f: any) => 
      typeof f === 'string' && f.toLowerCase().includes('disorder')
    );
  }
  
  return false;
}

// Helper: Compute lattice lengths from 3x3 matrix
function computeLatticeLengths(matrix: number[][]): { a: number; b: number; c: number } {
  const a = Math.sqrt(matrix[0][0]**2 + matrix[0][1]**2 + matrix[0][2]**2);
  const b = Math.sqrt(matrix[1][0]**2 + matrix[1][1]**2 + matrix[1][2]**2);
  const c = Math.sqrt(matrix[2][0]**2 + matrix[2][1]**2 + matrix[2][2]**2);
  return { a, b, c };
}

// Helper: Compute cell volume from 3x3 matrix
function computeCellVolume(matrix: number[][]): number {
  // Volume = |det(matrix)|
  const det = 
    matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
    matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
    matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]);
  return Math.abs(det);
}

interface AccordionSectionProps {
  title: string;
  defaultExpanded?: boolean;
  children: React.ReactNode;
}

function AccordionSection({ title, defaultExpanded = false, children }: AccordionSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  
  return (
    <div className="detail-accordion-section">
      <button
        className="detail-accordion-header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="detail-accordion-title">{title}</span>
        <span className="detail-accordion-icon">{expanded ? '▼' : '▶'}</span>
      </button>
      {expanded && (
        <div className="detail-accordion-content">
          {children}
        </div>
      )}
    </div>
  );
}

export function StructureDetailPanel({ model, onClose }: StructureDetailPanelProps) {
  if (!model) {
    return null;
  }
  
  const provenance = model.provenance;
  const isOnline = provenance != null;
  
  // Extract prioritized fields
  const formula = model.formula || getFirstAvailable(provenance, [
    'extras.formula_hill',
    'extras.formula_hill_compact',
    'attributes.chemical_formula_reduced',
    'attributes.chemical_formula_descriptive',
  ]) || 'Unknown';
  
  const nsites = model.nsites || getFirstAvailable(provenance, [
    'extras.number_of_sites',
    'attributes.nsites',
  ]) || 0;
  
  // Step 3: Fix Details panel "Species" - use primary atoms (non-boundary)
  // Species should be derived from primary atoms, never from boundary atoms
  const species = useMemo(() => {
    if (model.species.length > 0) {
      return model.species.join(', ');
    }
    // Extract primary atoms (non-boundary) from model.atoms
    // Fallback: if no is_boundary flag, use all atoms (legacy payload)
    const primaryAtoms = model.atoms.filter(a => !(a as any).is_boundary);
    const sourceAtoms = primaryAtoms.length > 0 ? primaryAtoms : model.atoms;
    const uniqueElements = Array.from(new Set(sourceAtoms.map(a => a.element))).sort();
    return uniqueElements.join(', ');
  }, [model.species, model.atoms]);
  
  // Step 3: Boundary count (optional display)
  const boundaryCount = useMemo(() => {
    return model.atoms.filter(a => (a as any).is_boundary === true).length;
  }, [model.atoms]);
  
  const spaceGroup = formatSpaceGroup(provenance);
  const bravaisLattice = getFirstAvailable(provenance, [
    'extras.bravais_lattice_extended',
    'extras.bravais_lattice',
  ]);
  const dimensionality = formatDimensionality(provenance);
  const partialOcc = hasPartialOccupancies(provenance);
  
  // Compute lattice lengths and volume
  const latticeLengths = useMemo(() => {
    if (model.lattice && model.lattice.length === 3) {
      return computeLatticeLengths(model.lattice);
    }
    return null;
  }, [model.lattice]);
  
  const cellVolume = useMemo(() => {
    if (model.lattice && model.lattice.length === 3) {
      return computeCellVolume(model.lattice);
    }
    return null;
  }, [model.lattice]);
  
  return (
    <div className="structure-detail-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📐</span>
          {model.name}
        </h2>
        {onClose && (
          <button className="panel-close" onClick={onClose}>×</button>
        )}
      </div>
      
      <div className="panel-content structure-detail-panel__content">
        {/* Overview Section (always expanded) */}
        <div className="detail-section detail-section--overview">
          <h3>Overview</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Formula</span>
              <span className="detail-value">{formula}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Number of Sites</span>
              <span className="detail-value">{nsites}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Species</span>
              <span className="detail-value">{species}</span>
            </div>
            {spaceGroup && (
              <div className="detail-item">
                <span className="detail-label">Space Group</span>
                <span className="detail-value">{spaceGroup}</span>
              </div>
            )}
            {bravaisLattice && (
              <div className="detail-item">
                <span className="detail-label">Bravais Lattice</span>
                <span className="detail-value">{bravaisLattice}</span>
              </div>
            )}
            {dimensionality && (
              <div className="detail-item">
                <span className="detail-label">Dimensionality</span>
                <span className="detail-value">{dimensionality}</span>
              </div>
            )}
            <div className="detail-item">
              <span className="detail-label">Partial Occupancies</span>
              <span className="detail-value">{partialOcc ? 'Yes' : 'No'}</span>
            </div>
            {latticeLengths && (
              <>
                <div className="detail-item">
                  <span className="detail-label">a</span>
                  <span className="detail-value">{latticeLengths.a.toFixed(4)} Å</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">b</span>
                  <span className="detail-value">{latticeLengths.b.toFixed(4)} Å</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">c</span>
                  <span className="detail-value">{latticeLengths.c.toFixed(4)} Å</span>
                </div>
              </>
            )}
            {cellVolume && (
              <div className="detail-item detail-item--full">
                <span className="detail-label">Cell Volume</span>
                <span className="detail-value">{cellVolume.toFixed(2)} Å³</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Provenance Section (for online structures) - Collapsible */}
        {isOnline && provenance && (
          <AccordionSection title="Provenance" defaultExpanded={false}>
            <div className="detail-grid">
              {provenance.source_name && (
                <div className="detail-item">
                  <span className="detail-label">Source</span>
                  <span className="detail-value">{provenance.source_name}</span>
                </div>
              )}
              {provenance.provider && (
                <div className="detail-item">
                  <span className="detail-label">Provider</span>
                  <span className="detail-value">{provenance.provider}</span>
                </div>
              )}
              {provenance.database && (
                <div className="detail-item">
                  <span className="detail-label">Database</span>
                  <span className="detail-value">{provenance.database}</span>
                </div>
              )}
              {provenance.base_url && (
                <div className="detail-item detail-item--full">
                  <span className="detail-label">Base URL</span>
                  <code className="detail-value detail-value--monospace" style={{ fontSize: '0.85em' }}>
                    {provenance.base_url}
                  </code>
                </div>
              )}
              {provenance.optimade_id && (
                <div className="detail-item detail-item--full">
                  <span className="detail-label">OPTIMADE ID</span>
                  <code className="detail-value detail-value--monospace" title={provenance.optimade_id}>
                    {provenance.optimade_id}
                  </code>
                </div>
              )}
              {(provenance.aiida_uuid || getFirstAvailable(provenance, ['raw.uuid', 'attributes.uuid'])) && (
                <div className="detail-item detail-item--full">
                  <span className="detail-label">AiiDA UUID</span>
                  <code className="detail-value detail-value--monospace">
                    {provenance.aiida_uuid || getFirstAvailable(provenance, ['raw.uuid', 'attributes.uuid'])}
                  </code>
                </div>
              )}
            </div>
          </AccordionSection>
        )}
        
        {/* Identifiers Section (for online structures) - Deprecated, moved to Provenance */}
        
        {/* Timestamps Section (for online structures) */}
        {isOnline && provenance && (provenance.created || provenance.modified) && (
          <div className="detail-section">
            <h3>Timestamps</h3>
            <div className="detail-grid">
              {provenance.created && (
                <div className="detail-item">
                  <span className="detail-label">Created</span>
                  <span className="detail-value">{provenance.created}</span>
                </div>
              )}
              {provenance.modified && (
                <div className="detail-item">
                  <span className="detail-label">Modified</span>
                  <span className="detail-value">{provenance.modified}</span>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Collapsible Sections (for online structures with rich metadata) */}
        {isOnline && provenance && (
          <>
            {provenance.extras && Object.keys(provenance.extras).length > 0 && (
              <AccordionSection title="Extras">
                <div className="detail-key-value-table">
                  {Object.entries(provenance.extras)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, value]) => (
                      <div key={key} className="detail-kv-row">
                        <span className="detail-kv-key">{key}</span>
                        <span className="detail-kv-value">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </span>
                      </div>
                    ))}
                </div>
              </AccordionSection>
            )}
            
            {provenance.raw && Object.keys(provenance.raw).length > 0 && (
              <AccordionSection title="Full Metadata">
                <div className="detail-key-value-table">
                  {Object.entries(provenance.raw)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, value]) => (
                      <div key={key} className="detail-kv-row">
                        <span className="detail-kv-key">{key}</span>
                        <span className="detail-kv-value">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </span>
                      </div>
                    ))}
                </div>
              </AccordionSection>
            )}
            
            {provenance.attributes && Object.keys(provenance.attributes).length > 0 && (
              <AccordionSection title="Raw OPTIMADE Attributes">
                <pre className="detail-json-preview">
                  {JSON.stringify(provenance.attributes, null, 2)}
                </pre>
              </AccordionSection>
            )}
          </>
        )}
        
        {/* File Location (for project structures only) */}
        {!isOnline && model.id && !model.id.startsWith('online:') && (
          <div className="detail-section">
            <h3>File Location</h3>
            <div className="file-location">
              <code className="file-location__path" title={model.id}>
                {model.id}
              </code>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

