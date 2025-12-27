/**
 * CommonCardPseudo - Pseudopotential mapping editor
 * 
 * Manages pseudopotential file mappings for each species in the structure.
 * 
 * Key design decisions (per constitution):
 * - pseudo_dir is NOT editable (runtime always uses ../pseudo)
 * - Per-element mapping is the canonical source of truth (species_overrides)
 * - Library preference (accuracy/efficiency) affects auto-fill defaults only
 * - Import button copies files to project/pseudo for self-containment
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import './CommonCardPseudo.css';

type LibraryPreference = 'precision' | 'efficiency';

interface PseudoMapping {
  species: string[];
  mapping: Record<string, string>;
  pseudo_dir: string;
  available_pseudos: string[];
  warnings: string[];
  library_preference?: LibraryPreference;
  sssp_defaults?: Record<string, { precision: string; efficiency: string }>;
  sssp_installed?: { precision: boolean; efficiency: boolean };
}

interface CommonCardPseudoProps {
  mapping: PseudoMapping | null;
  isEditing: boolean;
  onUpdate: (mapping: Record<string, string>, libraryPreference?: LibraryPreference) => Promise<void>;
  onImportFiles?: (files: FileList) => Promise<void>;
  onRefresh?: () => Promise<void>;
}

export function CommonCardPseudo({
  mapping,
  isEditing,
  onUpdate,
  onImportFiles,
  onRefresh,
}: CommonCardPseudoProps) {
  const [localMapping, setLocalMapping] = useState<Record<string, string>>({});
  const [libraryPreference, setLibraryPreference] = useState<LibraryPreference>('precision');
  const [isImporting, setIsImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Sync local state when mapping changes
  useEffect(() => {
    if (mapping) {
      setLocalMapping({ ...mapping.mapping });
      setLibraryPreference(mapping.library_preference || 'precision');
    }
  }, [mapping]);
  
  const handlePseudoChange = useCallback((species: string, pseudo: string) => {
    setLocalMapping(prev => ({
      ...prev,
      [species]: pseudo,
    }));
  }, []);
  
  const handleLibraryPreferenceChange = useCallback((preference: LibraryPreference) => {
    setLibraryPreference(preference);
    
    // Auto-fill unset mappings from the selected library
    if (mapping?.sssp_defaults) {
      setLocalMapping(prev => {
        const updated = { ...prev };
        for (const species of mapping.species) {
          // Only auto-fill if currently unset
          if (!updated[species] || updated[species] === '') {
            const defaults = mapping.sssp_defaults?.[species];
            if (defaults) {
              updated[species] = defaults[preference] || '';
            }
          }
        }
        return updated;
      });
    }
  }, [mapping]);
  
  const handleApply = useCallback(async () => {
    await onUpdate(localMapping, libraryPreference);
  }, [localMapping, libraryPreference, onUpdate]);
  
  const handleImportClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);
  
  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !onImportFiles) return;
    
    setIsImporting(true);
    try {
      await onImportFiles(files);
      // Refresh to show newly imported files
      if (onRefresh) {
        await onRefresh();
      }
    } finally {
      setIsImporting(false);
      // Clear the file input for next selection
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [onImportFiles, onRefresh]);
  
  const handleAutoFill = useCallback(() => {
    if (!mapping?.sssp_defaults) return;
    
    setLocalMapping(prev => {
      const updated = { ...prev };
      for (const species of mapping.species) {
        // Only auto-fill if currently unset
        if (!updated[species] || updated[species] === '') {
          const defaults = mapping.sssp_defaults?.[species];
          if (defaults) {
            updated[species] = defaults[libraryPreference] || '';
          }
        }
      }
      return updated;
    });
  }, [mapping, libraryPreference]);
  
  if (!mapping) {
    return (
      <div className="common-card-pseudo">
        <div className="common-card-pseudo__empty">
          <p>No structure found. Pseudopotentials require a structure.</p>
        </div>
      </div>
    );
  }
  
  // Group available pseudos by element for cleaner dropdowns
  const pseudosByElement: Record<string, string[]> = {};
  for (const pseudo of mapping.available_pseudos) {
    // Simple heuristic: first part before '.' or '_' is element symbol
    const match = pseudo.match(/^([A-Z][a-z]?)/i);
    const elem = match ? match[1] : 'other';
    if (!pseudosByElement[elem]) {
      pseudosByElement[elem] = [];
    }
    pseudosByElement[elem].push(pseudo);
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
        {/* Library preference selector */}
        {isEditing && (
          <div className="common-card-pseudo__library">
            <label>SSSP Library:</label>
            <select
              value={libraryPreference}
              onChange={(e) => handleLibraryPreferenceChange(e.target.value as LibraryPreference)}
              className="common-card-pseudo__library-select"
            >
              <option 
                value="precision" 
                disabled={mapping.sssp_installed && !mapping.sssp_installed.precision}
              >
                SSSP Precision (recommended){mapping.sssp_installed && !mapping.sssp_installed.precision ? ' — not installed' : ''}
              </option>
              <option 
                value="efficiency"
                disabled={mapping.sssp_installed && !mapping.sssp_installed.efficiency}
              >
                SSSP Efficiency{mapping.sssp_installed && !mapping.sssp_installed.efficiency ? ' — not installed' : ''}
              </option>
            </select>
            <button
              type="button"
              onClick={handleAutoFill}
              className="common-card-pseudo__autofill-btn"
              disabled={!mapping.sssp_installed?.precision && !mapping.sssp_installed?.efficiency}
              title="Auto-fill unset entries from selected library"
            >
              Auto-fill
            </button>
          </div>
        )}
        
        {/* Species mapping table */}
        {mapping.species.length > 0 ? (
          <div className="common-card-pseudo__mapping">
            <table className="common-card-pseudo__table">
              <thead>
                <tr>
                  <th>Element</th>
                  <th>Pseudopotential File</th>
                </tr>
              </thead>
              <tbody>
                {mapping.species.map((species) => {
                  const currentPseudo = localMapping[species] || '';
                  const matchingPseudos = pseudosByElement[species] || [];
                  const otherPseudos = mapping.available_pseudos.filter(
                    p => !matchingPseudos.includes(p)
                  );
                  
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
                              className={`common-card-pseudo__select ${
                                !currentPseudo ? 'common-card-pseudo__select--unset' : ''
                              }`}
                            >
                              <option value="">— Select —</option>
                              {matchingPseudos.length > 0 && (
                                <optgroup label={`${species} pseudopotentials`}>
                                  {matchingPseudos.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                  ))}
                                </optgroup>
                              )}
                              {otherPseudos.length > 0 && (
                                <optgroup label="Other available">
                                  {otherPseudos.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                  ))}
                                </optgroup>
                              )}
                            </select>
                            {currentPseudo && !mapping.available_pseudos.includes(currentPseudo) && (
                              <span className="common-card-pseudo__not-found">
                                ⚠️ Not in project
                              </span>
                            )}
                          </div>
                        ) : (
                          <code className="common-card-pseudo__pseudo-display">
                            {currentPseudo || '—'}
                          </code>
                        )}
                      </td>
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
        
        {/* Info: pseudo_dir is managed automatically */}
        <div className="common-card-pseudo__info">
          <small>
            📁 Pseudopotentials are stored in <code>project/pseudo/</code> and referenced via <code>../pseudo</code> at runtime.
          </small>
        </div>
        
        {/* Actions */}
        {isEditing && (
          <div className="common-card-pseudo__actions">
            {onImportFiles && (
              <>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".upf,.UPF"
                  multiple
                  style={{ display: 'none' }}
                />
                <button
                  type="button"
                  onClick={handleImportClick}
                  className="common-card-pseudo__import-btn"
                  disabled={isImporting}
                >
                  {isImporting ? 'Importing...' : 'Import Pseudopotentials'}
                </button>
              </>
            )}
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
