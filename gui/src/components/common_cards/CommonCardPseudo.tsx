/**
 * CommonCardPseudo - Pseudopotential mapping editor
 * 
 * Manages pseudopotential file mappings for each species in the structure.
 */

import { useState, useEffect, useCallback } from 'react';
import './CommonCardPseudo.css';

interface PseudoMapping {
  species: string[];
  mapping: Record<string, string>;
  pseudo_dir: string;
  available_pseudos: string[];
  warnings: string[];
}

interface CommonCardPseudoProps {
  mapping: PseudoMapping | null;
  isEditing: boolean;
  onUpdate: (mapping: Record<string, string>, pseudoDir?: string) => Promise<void>;
}

export function CommonCardPseudo({
  mapping,
  isEditing,
  onUpdate,
}: CommonCardPseudoProps) {
  const [localMapping, setLocalMapping] = useState<Record<string, string>>({});
  const [localPseudoDir, setLocalPseudoDir] = useState('');
  
  // Sync local state when mapping changes
  useEffect(() => {
    if (mapping) {
      setLocalMapping({ ...mapping.mapping });
      setLocalPseudoDir(mapping.pseudo_dir || '');
    }
  }, [mapping]);
  
  const handlePseudoChange = useCallback((species: string, pseudo: string) => {
    setLocalMapping(prev => ({
      ...prev,
      [species]: pseudo,
    }));
  }, []);
  
  const handlePseudoDirChange = useCallback((dir: string) => {
    setLocalPseudoDir(dir);
  }, []);
  
  const handleApply = useCallback(async () => {
    await onUpdate(localMapping, localPseudoDir || undefined);
  }, [localMapping, localPseudoDir, onUpdate]);
  
  if (!mapping) {
    return (
      <div className="common-card-pseudo">
        <div className="common-card-pseudo__empty">
          <p>No structure found. Pseudopotentials require a structure.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="common-card-pseudo">
      <div className="common-card-pseudo__header">
        <h4>Pseudopotentials</h4>
        {mapping.warnings && mapping.warnings.length > 0 && (
          <div className="common-card-pseudo__warnings">
            {mapping.warnings.map((w, i) => (
              <div key={i} className="common-card-pseudo__warning">
                ⚠️ {w}
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="common-card-pseudo__content">
        {/* Pseudo directory */}
        <div className="common-card-pseudo__dir">
          <label>Pseudo Directory:</label>
          <input
            type="text"
            value={localPseudoDir}
            onChange={(e) => handlePseudoDirChange(e.target.value)}
            disabled={!isEditing}
            placeholder="e.g., ./pseudo"
            className="common-card-pseudo__dir-input"
          />
        </div>
        
        {/* Species mapping table */}
        {mapping.species.length > 0 ? (
          <div className="common-card-pseudo__mapping">
            <table className="common-card-pseudo__table">
              <thead>
                <tr>
                  <th>Species</th>
                  <th>Pseudopotential File</th>
                  {isEditing && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {mapping.species.map((species) => {
                  const currentPseudo = localMapping[species] || '';
                  return (
                    <tr key={species}>
                      <td>
                        <strong>{species}</strong>
                      </td>
                      <td>
                        {isEditing ? (
                          <div className="common-card-pseudo__pseudo-select">
                            <select
                              value={currentPseudo}
                              onChange={(e) => handlePseudoChange(species, e.target.value)}
                              className="common-card-pseudo__select"
                            >
                              <option value="">-- Not set --</option>
                              {mapping.available_pseudos
                                .filter(p => p.toLowerCase().startsWith(species.toLowerCase()))
                                .map(p => (
                                  <option key={p} value={p}>{p}</option>
                                ))}
                              {mapping.available_pseudos.length > 0 && (
                                <option disabled>---</option>
                              )}
                              {mapping.available_pseudos.map(p => (
                                <option key={p} value={p}>{p}</option>
                              ))}
                            </select>
                            {currentPseudo && !mapping.available_pseudos.includes(currentPseudo) && (
                              <span className="common-card-pseudo__not-found">
                                ⚠️ File not found
                              </span>
                            )}
                          </div>
                        ) : (
                          <code className="common-card-pseudo__pseudo-display">
                            {currentPseudo || '—'}
                          </code>
                        )}
                      </td>
                      {isEditing && (
                        <td>
                          <button
                            type="button"
                            onClick={() => handlePseudoChange(species, '')}
                            className="common-card-pseudo__clear-btn"
                            title="Clear pseudopotential"
                          >
                            Clear
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="common-card-pseudo__no-species">
            <p>No species found in structure.</p>
          </div>
        )}
        
        {/* Available pseudos info */}
        {mapping.available_pseudos.length > 0 && (
          <div className="common-card-pseudo__available">
            <details>
              <summary>Available Pseudopotentials ({mapping.available_pseudos.length})</summary>
              <ul className="common-card-pseudo__pseudo-list">
                {mapping.available_pseudos.map(p => (
                  <li key={p} className="common-card-pseudo__pseudo-item">
                    <code>{p}</code>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}
        
        {/* Apply button (only in edit mode) */}
        {isEditing && (
          <div className="common-card-pseudo__actions">
            <button
              type="button"
              onClick={handleApply}
              className="common-card-pseudo__apply-btn"
            >
              Apply
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

