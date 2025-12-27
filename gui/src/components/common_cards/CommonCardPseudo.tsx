/**
 * CommonCardPseudo - Pseudopotential mapping editor
 * 
 * Manages pseudopotential file mappings for each species in the structure.
 * 
 * Key design decisions (per constitution):
 * - pseudo_dir is NOT editable (runtime always uses ../pseudo)
 * - Per-element mapping is the canonical source of truth (species_overrides)
 * - Auto-preselect SSSP defaults (precision preferred, efficiency fallback) but only commit on Apply
 * - Import/Download buttons copy files to project/pseudo for self-containment
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

interface LegacyPseudoCandidate {
  filename: string;
  url: string;
  element: string;
  xc?: string | null;
}

interface CommonCardPseudoProps {
  mapping: PseudoMapping | null;
  isEditing: boolean;
  onUpdate: (mapping: Record<string, string>, libraryPreference?: LibraryPreference) => Promise<void>;
  onImportFiles?: (files: FileList) => Promise<void>;
  onRefresh?: () => Promise<void>;
  onSearchLegacy?: (element: string) => Promise<{ candidates: LegacyPseudoCandidate[]; errors: string[] }>;
  onDownloadByFilename?: (filename: string) => Promise<{ filename: string; renamed: boolean; skipped: boolean; errors: string[] }>;
  onDownloadCandidate?: (candidate: LegacyPseudoCandidate) => Promise<{ filename: string; renamed: boolean; skipped: boolean; errors: string[] }>;
  projectRoot?: string;
}

export function CommonCardPseudo({
  mapping,
  isEditing,
  onUpdate,
  onImportFiles,
  onRefresh,
  onSearchLegacy,
  onDownloadByFilename,
  onDownloadCandidate,
  projectRoot,
}: CommonCardPseudoProps) {
  const [localMapping, setLocalMapping] = useState<Record<string, string>>({});
  const [libraryPreference, setLibraryPreference] = useState<LibraryPreference>('precision');
  const [isImporting, setIsImporting] = useState(false);
  const [onlineResolveExpanded, setOnlineResolveExpanded] = useState(false);
  const [onlineMode, setOnlineMode] = useState<'filename' | 'element'>('filename');
  const [filenameInput, setFilenameInput] = useState('');
  const [selectedElement, setSelectedElement] = useState('');
  const [legacyCandidates, setLegacyCandidates] = useState<LegacyPseudoCandidate[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Sync local state when mapping changes
  // Auto-preselect SSSP defaults ONLY for entries that are truly unset (None/empty in species_overrides)
  // AND not already set by user in localMapping (e.g., after download)
  useEffect(() => {
    if (mapping) {
      const initialMapping: Record<string, string> = {};
      
      // Start with existing mapping from species_overrides (backend truth)
      for (const [species, pseudo] of Object.entries(mapping.mapping)) {
        initialMapping[species] = pseudo;
      }
      
      // CRITICAL: Only auto-preselect if:
      // 1. species_overrides[element] is None/empty (not set in backend)
      // 2. localMapping[element] is also empty (user hasn't manually selected)
      // This prevents overwriting user selections after download
      if (mapping.sssp_defaults) {
        for (const species of mapping.species) {
          // Check backend: only auto-preselect if species_overrides[species] is None/empty
          const backendValue = mapping.mapping[species];
          const isBackendUnset = !backendValue || backendValue === '';
          
          // Check local state: only auto-preselect if user hasn't set it
          const localValue = localMapping[species];
          const isLocalUnset = !localValue || localValue === '';
          
          // Only auto-preselect if BOTH backend and local are unset
          if (isBackendUnset && isLocalUnset) {
            const defaults = mapping.sssp_defaults[species];
            if (defaults) {
              // Prefer precision, fallback to efficiency
              initialMapping[species] = defaults.precision || defaults.efficiency || '';
            }
          } else if (localValue) {
            // Preserve user's local selection (e.g., after download)
            initialMapping[species] = localValue;
          }
        }
      }
      
      setLocalMapping(initialMapping);
      setLibraryPreference(mapping.library_preference || 'precision');
      
      // Set selected element for online search to first species if available
      if (mapping.species.length > 0 && !selectedElement) {
        setSelectedElement(mapping.species[0]);
      }
    }
  }, [mapping]); // Removed selectedElement from deps to avoid unnecessary re-runs
  
  const handlePseudoChange = useCallback((species: string, pseudo: string) => {
    setLocalMapping(prev => ({
      ...prev,
      [species]: pseudo,
    }));
  }, []);
  
  const handleLibraryPreferenceChange = useCallback((preference: LibraryPreference) => {
    setLibraryPreference(preference);
    
    // Update unset mappings from the selected library
    if (mapping?.sssp_defaults) {
      setLocalMapping(prev => {
        const updated = { ...prev };
        for (const species of mapping.species) {
          // Only update if currently unset or matches old preference
          const current = updated[species] || '';
          const defaults = mapping.sssp_defaults?.[species];
          if (defaults) {
            const oldDefault = mapping.library_preference === 'precision' 
              ? defaults.precision 
              : defaults.efficiency;
            // If current value matches old default, update to new default
            if (current === oldDefault || !current) {
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
    setDownloadError(null);
    try {
      await onImportFiles(files);
      // Refresh to show newly imported files
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setIsImporting(false);
      // Clear the file input for next selection
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [onImportFiles, onRefresh]);
  
  const handleSearchLegacy = useCallback(async () => {
    if (!selectedElement || !onSearchLegacy) return;
    
    setIsSearching(true);
    setLegacyCandidates([]);
    setDownloadError(null);
    try {
      const result = await onSearchLegacy(selectedElement);
      setLegacyCandidates(result.candidates);
      if (result.errors.length > 0) {
        setDownloadError(result.errors.join('; '));
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsSearching(false);
    }
  }, [selectedElement, onSearchLegacy]);
  
  const handleDownloadByFilename = useCallback(async () => {
    if (!filenameInput.trim() || !onDownloadByFilename) return;
    
    setIsDownloading(true);
    setDownloadError(null);
    try {
      const result = await onDownloadByFilename(filenameInput.trim());
      if (result.errors.length > 0) {
        setDownloadError(result.errors.join('; '));
      } else {
        // Success - refresh to update available_pseudos list
        // Note: We don't auto-select here because we don't know which element
        // User should manually select from dropdown after download
        if (onRefresh) {
          await onRefresh();
        }
        // Clear input on success
        setFilenameInput('');
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  }, [filenameInput, onDownloadByFilename, onRefresh]);
  
  const handleDownloadCandidate = useCallback(async (candidate: LegacyPseudoCandidate) => {
    if (!onDownloadCandidate) return;
    
    setIsDownloading(true);
    setDownloadError(null);
    try {
      const result = await onDownloadCandidate(candidate);
      if (result.errors.length > 0) {
        setDownloadError(result.errors.join('; '));
      } else {
        // Auto-select FIRST (before refresh) to preserve user choice
        // This ensures useEffect won't overwrite it when mapping updates
        if (candidate.element && (!localMapping[candidate.element] || localMapping[candidate.element] === '')) {
          handlePseudoChange(candidate.element, result.filename);
        }
        // Then refresh to update available_pseudos list
        if (onRefresh) {
          await onRefresh();
        }
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  }, [onDownloadCandidate, onRefresh, localMapping, handlePseudoChange]);
  
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
                  
                  // Check if current value is from SSSP defaults (for visual indication)
                  const isSSSPDefault = mapping.sssp_defaults?.[species] && (
                    currentPseudo === mapping.sssp_defaults[species].precision ||
                    currentPseudo === mapping.sssp_defaults[species].efficiency
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
                              } ${isSSSPDefault ? 'common-card-pseudo__select--sssp-default' : ''}`}
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
                            {isSSSPDefault && (
                              <span className="common-card-pseudo__sssp-badge" title="SSSP default (will be saved on Apply)">
                                📚
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
            📁 Runtime uses <code>project/pseudo/</code> and QE inputs reference <code>../pseudo</code>.
            SSSP libraries are managed in Settings; online resolve downloads individual UPF files into this project.
          </small>
          <small style={{ display: 'block', marginTop: '0.5rem', color: 'var(--text-muted, #888)' }}>
            ⚠️ <strong>Note:</strong> Setting pseudopotentials is only one step. You still need to configure k-points, cutoffs, and other parameters before running.
          </small>
        </div>
        
        {/* Online Resolve section (Advanced) */}
        {isEditing && (onDownloadByFilename || onSearchLegacy) && (
          <details className="common-card-pseudo__online-resolve">
            <summary>Online Resolve (Advanced)</summary>
            <div className="common-card-pseudo__online-content">
              {/* Mode selector */}
              <div className="common-card-pseudo__online-mode">
                <label>
                  <input
                    type="radio"
                    name="online-mode"
                    value="filename"
                    checked={onlineMode === 'filename'}
                    onChange={(e) => setOnlineMode(e.target.value as 'filename' | 'element')}
                  />
                  Download by filename
                </label>
                <label>
                  <input
                    type="radio"
                    name="online-mode"
                    value="element"
                    checked={onlineMode === 'element'}
                    onChange={(e) => setOnlineMode(e.target.value as 'filename' | 'element')}
                  />
                  Search by element (legacy tables)
                </label>
              </div>
              
              {/* Mode 1: Download by filename */}
              {onlineMode === 'filename' && onDownloadByFilename && (
                <div className="common-card-pseudo__online-filename">
                  <label>UPF Filename:</label>
                  <div className="common-card-pseudo__online-input-group">
                    <input
                      type="text"
                      value={filenameInput}
                      onChange={(e) => setFilenameInput(e.target.value)}
                      placeholder="e.g., Si.pbe-n-rrkjus_psl.1.0.0.UPF"
                      className="common-card-pseudo__online-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && filenameInput.trim()) {
                          handleDownloadByFilename();
                        }
                      }}
                    />
                    <button
                      type="button"
                      onClick={handleDownloadByFilename}
                      disabled={!filenameInput.trim() || isDownloading}
                      className="common-card-pseudo__online-download-btn"
                    >
                      {isDownloading ? 'Downloading...' : 'Download'}
                    </button>
                  </div>
                </div>
              )}
              
              {/* Mode 2: Search by element */}
              {onlineMode === 'element' && onSearchLegacy && (
                <div className="common-card-pseudo__online-element">
                  <label>Element:</label>
                  <div className="common-card-pseudo__online-input-group">
                    <select
                      value={selectedElement}
                      onChange={(e) => setSelectedElement(e.target.value)}
                      className="common-card-pseudo__online-select"
                    >
                      {mapping.species.map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleSearchLegacy}
                      disabled={!selectedElement || isSearching}
                      className="common-card-pseudo__online-search-btn"
                    >
                      {isSearching ? 'Searching...' : 'Search'}
                    </button>
                  </div>
                  
                  {/* Candidates list */}
                  {legacyCandidates.length > 0 && (
                    <div className="common-card-pseudo__online-candidates">
                      <div className="common-card-pseudo__online-candidates-header">
                        Found {legacyCandidates.length} candidate{legacyCandidates.length !== 1 ? 's' : ''}:
                      </div>
                      <ul className="common-card-pseudo__online-candidates-list">
                        {legacyCandidates.map((candidate, idx) => (
                          <li key={idx} className="common-card-pseudo__online-candidate">
                            <div className="common-card-pseudo__online-candidate-info">
                              <code>{candidate.filename}</code>
                              {candidate.xc && (
                                <span className="common-card-pseudo__online-candidate-xc">
                                  {candidate.xc.toUpperCase()}
                                </span>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => handleDownloadCandidate(candidate)}
                              disabled={isDownloading}
                              className="common-card-pseudo__online-download-btn"
                            >
                              {isDownloading ? 'Downloading...' : 'Download'}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              
              {/* Error display */}
              {downloadError && (
                <div className="common-card-pseudo__online-error">
                  ⚠️ {downloadError}
                </div>
              )}
            </div>
          </details>
        )}
        
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
