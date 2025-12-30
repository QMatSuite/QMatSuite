/**
 * CommonCardPseudo - Pseudopotential mapping editor (sha256-keyed, filename-first, constitution-compliant)
 * 
 * Manages pseudopotential file mappings for each species in the structure.
 * 
 * **Selection Model:**
 * - Selection keyed by sha256 (strict bytes identity) - PRIMARY
 * - sha_family used only for warnings and collision detection
 * - Default selection priority: project filename → internal filename → lib
 * 
 * **Constitution Rules:**
 * - UI must NEVER mutate filesystem (no copy/rename/overwrite/mkdir)
 * - Only Step0 (prepare_project_pseudos_for_run) mutates project/pseudo
 * - Only 3 sources exist: lib, internal, project/pseudo
 * - sha256 is selection key; sha_family is for physical equivalence warnings
 * - Warnings come from backend analyzer (read-only)
 * 
 * **Key design decisions:**
 * - pseudo_dir is NOT editable (runtime always uses project/pseudo)
 * - Per-element mapping is the canonical source of truth (species_map)
 * - Selection stored as sha256 (primary) + basename + sha_family (triplet)
 * - Restore-by-sha256 first, then fallback-by-filename (does NOT write calc.yml)
 * - Write triplet together on user change (with debug log)
 * - Warnings displayed inline per element from analyzer
 * - Apply/Run gated by source availability (project/internal or installed+not-corrupt lib)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { PseudoVariant } from '../../types/qv';
import './CommonCardPseudo.css';

type LibraryPreference = 'internal' | 'precision' | 'efficiency';

interface PseudoMapping {
  species: string[];
  mapping: Record<string, string>;
  pseudo_dir: string;
  available_pseudos: string[];
  warnings: string[];
  library_preference?: LibraryPreference;
  sssp_defaults?: Record<string, { precision: string; efficiency: string }>;
  sssp_installed?: { precision: boolean; efficiency: boolean };
  installed_sources?: {
    internal: boolean;
    sssp_precision: boolean;
    sssp_efficiency: boolean;
  };
  candidates_by_element?: Record<string, Array<{
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project';
    path?: string | null;
  }>>;
  resolved_by_element?: Record<string, {
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project' | null;
    resolved: boolean;
    in_project?: boolean;
  }>;
  species_map?: Record<string, {
    pseudopot?: string;
    pseudo_sha256?: string;
    pseudo_sha_family?: string;
    pseudo_basename?: string;
    mass?: number;
  }>;
}

interface LegacyPseudoCandidate {
  filename: string;
  url: string;
  element: string;
  xc?: string | null;
}

// Legacy PseudoOption (sha256-based) - kept for backward compatibility
interface PseudoOption {
  sha256: string;
  sha_family: string;
  element: string;
  display_basename: string;
  all_basenames: string[];
  sources: Array<{
    kind: 'project' | 'internal' | 'library';
    label: string;
    installed: boolean;
    corrupt?: boolean;
    warning?: string;
    archive_asset?: string;
  }>;
  availability: { any_installed: boolean };
}

// PseudoVariant (sha256-keyed, filename-first, constitution-compliant)
// Imported from types/qv.ts - using PseudoVariant interface

interface CommonCardPseudoProps {
  mapping: PseudoMapping | null;
  isEditing: boolean;
  onUpdate: (
    mapping: Record<string, string>,
    libraryPreference?: LibraryPreference,
    sha256Map?: Record<string, string>,
    shaFamilyMap?: Record<string, string>
  ) => Promise<void>;
  onImportFiles?: (files: FileList) => Promise<void>;
  onRefresh?: () => Promise<void>;
  onSearchLegacy?: (element: string) => Promise<{ candidates: LegacyPseudoCandidate[]; errors: string[] }>;
  onDownloadByFilename?: (filename: string) => Promise<{ filename: string; renamed: boolean; skipped: boolean; errors: string[] }>;
  onDownloadCandidate?: (candidate: LegacyPseudoCandidate) => Promise<{ filename: string; renamed: boolean; skipped: boolean; errors: string[] }>;
  projectRoot?: string;
  calculation?: string; // Calculation slug/selector for new API
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
  calculation,
}: CommonCardPseudoProps) {
  const qv = useQVClient();
  // Store sha256 + basename for pinned selections
  const [localMapping, setLocalMapping] = useState<Record<string, string>>({});
  const [localMappingSha256, setLocalMappingSha256] = useState<Record<string, string>>({});
  const [localMappingShaFamily, setLocalMappingShaFamily] = useState<Record<string, string>>({});
  const [libraryPreference, setLibraryPreference] = useState<LibraryPreference>('internal');
  const [isImporting, setIsImporting] = useState(false);
  const [onlineMode, setOnlineMode] = useState<'filename' | 'element'>('filename');
  const [filenameInput, setFilenameInput] = useState('');
  const [selectedElement, setSelectedElement] = useState('');
  const [legacyCandidates, setLegacyCandidates] = useState<LegacyPseudoCandidate[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [pseudoOptions, setPseudoOptions] = useState<Record<string, PseudoOption[]>>({});
  const [pseudoVariants, setPseudoVariants] = useState<Record<string, PseudoVariant[]>>({}); // sha256-keyed variants
  const [selectedSha256ByElement, setSelectedSha256ByElement] = useState<Record<string, string>>({}); // Primary selection key
  const [warningsByElement, setWarningsByElement] = useState<Record<string, string[]>>({});
  const [errorsByElement, setErrorsByElement] = useState<Record<string, string[]>>({});
  const [isLoadingOptions, setIsLoadingOptions] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasRestoredRef = useRef(false); // Track if we've done initial restore (to avoid writing on restore)
  
  // Use new API if calculation is provided
  const useNewAPI = Boolean(projectRoot && calculation);
  
  // Restore selection from calc.yml (does NOT write calc.yml)
  // Rule: match by sha256 first, then fallback by filename (project > internal > lib)
  const restoreSelectionFromCalc = useCallback(() => {
    if (!mapping?.species_map || Object.keys(pseudoVariants).length === 0) {
      return;
    }
    
    const restored: Record<string, string> = {}; // sha256 by element
    
    for (const [element, entry] of Object.entries(mapping.species_map)) {
      if (typeof entry !== 'object' || !entry) continue;
      
      const variants = pseudoVariants[element] || [];
      if (variants.length === 0) continue;
      
      const calcSha256 = entry.pseudo_sha256;
      const calcFilename = entry.pseudo_basename || entry.pseudopot;
      
      let matchedVariant: PseudoVariant | null = null;
      
      // Primary: match by sha256
      if (calcSha256) {
        const matches = variants.filter(v => v.sha256 === calcSha256);
        if (matches.length === 0) {
          matchedVariant = null;
        } else if (matches.length === 1) {
          matchedVariant = matches[0];
        } else {
          // Multiple matches: apply tie-break rules (Constitution 7.5.1.1)
          let candidates = matches;
          
          // Step 1: If calc.yml has pseudo_filename, prefer filename match
          if (calcFilename) {
            const filenameMatches = candidates.filter(v => v.basename === calcFilename);
            if (filenameMatches.length > 0) {
              candidates = filenameMatches;
            }
          }
          
          // Step 2: Source priority (project > internal > lib)
          const projectCandidates = candidates.filter(v => v.sources.some(s => s.kind === 'project' && s.installed));
          const internalCandidates = candidates.filter(v => v.sources.some(s => s.kind === 'internal' && s.installed));
          const libCandidates = candidates.filter(v => v.sources.some(s => s.kind === 'lib' && s.installed && !s.corrupt));
          
          if (projectCandidates.length > 0) {
            candidates = projectCandidates;
          } else if (internalCandidates.length > 0) {
            candidates = internalCandidates;
          } else if (libCandidates.length > 0) {
            candidates = libCandidates;
          }
          
          // Step 3: If multiple libs, sort by library/asset name lexicographically
          if (candidates.length > 1 && candidates.some(v => v.sources.some(s => s.kind === 'lib'))) {
            candidates.sort((a, b) => {
              // Get all lib sources for each variant
              const aLibs = a.sources.filter(s => s.kind === 'lib' && s.installed && !s.corrupt);
              const bLibs = b.sources.filter(s => s.kind === 'lib' && s.installed && !s.corrupt);
              
              if (aLibs.length === 0 && bLibs.length === 0) return 0;
              if (aLibs.length === 0) return 1;
              if (bLibs.length === 0) return -1;
              
              // Compare first lib source (library_name + archive_asset)
              const aLib = aLibs[0];
              const bLib = bLibs[0];
              
              const aLabel = `${aLib.library_name || ''}_${aLib.archive_asset || ''}`.toLowerCase();
              const bLabel = `${bLib.library_name || ''}_${bLib.archive_asset || ''}`.toLowerCase();
              
              return aLabel.localeCompare(bLabel);
            });
          }
          
          // Step 4: If same lib (or non-lib), sort by basename lexicographically
          if (candidates.length > 1) {
            candidates.sort((a, b) => a.basename.localeCompare(b.basename));
          }
          
          // Select first candidate after all tie-breaks
          matchedVariant = candidates[0];
        }
      }
      
      // Fallback: match by filename (project > internal > lib)
      if (!matchedVariant && calcFilename) {
        // Filter to filesystem-real options only
        const realVariants = variants.filter(v => {
          const hasProject = v.sources.some(s => s.kind === 'project' && s.installed);
          const hasInternal = v.sources.some(s => s.kind === 'internal' && s.installed);
          const hasInstalledLib = v.sources.some(s => s.kind === 'lib' && s.installed && !s.corrupt);
          return hasProject || hasInternal || hasInstalledLib;
        });
        
        // Try project first
        matchedVariant = realVariants.find(v => 
          v.basename === calcFilename && v.sources.some(s => s.kind === 'project' && s.installed)
        ) || null;
        
        // Then internal
        if (!matchedVariant) {
          matchedVariant = realVariants.find(v => 
            v.basename === calcFilename && v.sources.some(s => s.kind === 'internal' && s.installed)
          ) || null;
        }
        
        // Then lib (any installed, non-corrupt)
        if (!matchedVariant) {
          matchedVariant = realVariants.find(v => 
            v.basename === calcFilename && v.sources.some(s => s.kind === 'lib' && s.installed && !s.corrupt)
          ) || null;
        }
      }
      
      if (matchedVariant) {
        restored[element] = matchedVariant.sha256;
        setLocalMappingSha256(prev => ({ ...prev, [element]: matchedVariant!.sha256 }));
        setLocalMappingShaFamily(prev => ({ ...prev, [element]: matchedVariant!.sha_family }));
        setLocalMapping(prev => ({ ...prev, [element]: matchedVariant!.basename }));
        setSelectedSha256ByElement(prev => ({ ...prev, [element]: matchedVariant!.sha256 }));
      }
    }
  }, [mapping, pseudoVariants]);
  
  // Fetch options from new API (sha256-keyed variants)
  const fetchPseudoOptions = useCallback(() => {
    if (!useNewAPI || !projectRoot || !calculation) {
      return;
    }
    
    setIsLoadingOptions(true);
    qv.getPseudoOptionsForCalculation(projectRoot, calculation)
      .then(response => {
        if (response.ok && response.data) {
          const optionsByElement = response.data.options_by_element || {};
          
          // Check if new sha256-keyed format (has sha256, basename, element)
          const isNewFormat = Object.values(optionsByElement).some((opts: any) => 
            Array.isArray(opts) && opts.length > 0 && opts[0].sha256 !== undefined && opts[0].basename !== undefined
          );
          
          if (isNewFormat) {
            // New sha256-keyed format (PseudoVariant[])
            // Transform API response to match PseudoVariant interface
            const transformed: Record<string, PseudoVariant[]> = {};
            for (const [element, variants] of Object.entries(optionsByElement)) {
              if (Array.isArray(variants)) {
                transformed[element] = variants.map((v: any) => ({
                  sha256: v.sha256,
                  sha_family: v.sha_family,
                  basename: v.display_basename || v.basename,
                  element: v.element,
                  sources: v.sources || [],
                  size_bytes: v.size_bytes,
                  upf_format: v.upf_format,
                  is_project_local_unknown: v.is_project_local_unknown,
                  family_match_warnings: v.family_match_warnings,
                  display_label: v.display_basename || v.basename,
                  availability: v.availability || { any_installed: false },
                })) as PseudoVariant[];
              }
            }
            setPseudoVariants(transformed);
            setPseudoOptions({}); // Clear legacy
          } else {
            // Legacy format
            setPseudoOptions(optionsByElement as Record<string, PseudoOption[]>);
            setPseudoVariants({}); // Clear new
          }
          
          // After loading options, restore selection from calc (if not already restored)
          if (!hasRestoredRef.current) {
            restoreSelectionFromCalc();
            hasRestoredRef.current = true;
          }
          
          // After loading options, analyze current selections for warnings
          if (projectRoot && Object.keys(selectedSha256ByElement).length > 0) {
            analyzeSelections();
          }
        }
      })
      .catch(err => {
        console.error('[CommonCardPseudo] Failed to load pseudo options', err);
      })
      .finally(() => {
        setIsLoadingOptions(false);
      });
  }, [useNewAPI, projectRoot, calculation, qv]);

  // Initial fetch
  useEffect(() => {
    fetchPseudoOptions();
  }, [fetchPseudoOptions]);
  
  // Restore selection when variants are loaded (if not already restored)
  useEffect(() => {
    if (Object.keys(pseudoVariants).length > 0 && !hasRestoredRef.current && mapping?.species_map) {
      restoreSelectionFromCalc();
      hasRestoredRef.current = true;
    }
  }, [pseudoVariants, mapping, restoreSelectionFromCalc]);

  // Listen for archive changes
  useEffect(() => {
    const handleArchiveChange = () => {
      // Refresh options when archives are installed/reinstalled
      fetchPseudoOptions();
    };
    
    window.addEventListener('pseudo-archives-changed', handleArchiveChange);
    return () => {
      window.removeEventListener('pseudo-archives-changed', handleArchiveChange);
    };
  }, [fetchPseudoOptions]);
  
  // Sync local state when mapping changes
  // Auto-preselect SSSP defaults ONLY for entries that are truly unset (None/empty in species_overrides)
  // AND not already set by user in localMapping (e.g., after download)
  useEffect(() => {
    if (mapping) {
      const initialMapping: Record<string, string> = {};
      
      // Start with existing mapping from species_map (backend truth)
      // If a pseudo is already set and resolved, preserve it
      const initialSha256: Record<string, string> = {};
      const initialShaFamily: Record<string, string> = {};
      
      for (const [species, pseudo] of Object.entries(mapping.mapping)) {
        if (pseudo) {
          // Check if this pseudo is resolved from any source
          const resolvedInfo = mapping.resolved_by_element?.[species];
          if (resolvedInfo?.resolved) {
            // Pseudo is resolved, use it
            initialMapping[species] = pseudo;
          } else {
            // Pseudo is set but not resolved - still use it (user may have typed it)
            initialMapping[species] = pseudo;
          }
        }
      }
      
      // Also load sha256/sha_family from species_map if available (new pinned format)
      // Note: mapping.mapping may contain the full species_map entry with pseudo_sha256
      // We need to check the actual species_map structure
      const initialSelectedShaFamily: Record<string, string> = {};
      
      if (mapping.species_map) {
        for (const [species, entry] of Object.entries(mapping.species_map)) {
          if (typeof entry === 'object' && entry !== null) {
            if (entry.pseudo_sha256) {
              initialSha256[species] = entry.pseudo_sha256;
            }
            if (entry.pseudo_sha_family) {
              initialShaFamily[species] = entry.pseudo_sha_family;
              initialSelectedShaFamily[species] = entry.pseudo_sha_family; // Primary selection key (constitution)
            } else if (entry.pseudo_sha256) {
              // Backward compatibility: if calc has sha256 but not sha_family, try to map it
              // This will be resolved when options load and we can match sha256 to sha_family
              initialSha256[species] = entry.pseudo_sha256;
            }
            // Use pseudo_basename if available, otherwise fall back to pseudopot
            if (entry.pseudo_basename) {
              initialMapping[species] = entry.pseudo_basename;
            } else if (entry.pseudopot && !initialMapping[species]) {
              initialMapping[species] = entry.pseudopot;
            }
          }
        }
      }
      
      setLocalMappingSha256(initialSha256);
      setLocalMappingShaFamily(initialShaFamily);
      
      // CRITICAL: Only auto-preselect if:
      // 1. species_overrides[element] is None/empty (not set in backend)
      // 2. localMapping[element] is also empty (user hasn't manually selected)
      // This prevents overwriting user selections after download
      for (const species of mapping.species) {
        // Check backend: only auto-preselect if species_overrides[species] is None/empty
        const backendValue = mapping.mapping[species];
        const isBackendUnset = !backendValue || backendValue === '';
        
        // Check local state: only auto-preselect if user hasn't set it
        const localValue = localMapping[species];
        const isLocalUnset = !localValue || localValue === '';
        
        // Only auto-preselect if BOTH backend and local are unset
        if (isBackendUnset && isLocalUnset) {
          // Try to find a candidate from the preferred library
          const candidates = mapping.candidates_by_element?.[species] || [];
          const preferredLibrary = mapping.library_preference || 'internal';
          
          // Find first candidate from preferred library
          let selectedCandidate = null;
          if (preferredLibrary === 'internal') {
            selectedCandidate = candidates.find(c => c.source === 'internal');
          } else if (preferredLibrary === 'precision') {
            selectedCandidate = candidates.find(c => c.source === 'sssp_precision');
            if (!selectedCandidate) {
              // Fallback to internal if SSSP precision not available
              selectedCandidate = candidates.find(c => c.source === 'internal');
            }
          } else if (preferredLibrary === 'efficiency') {
            selectedCandidate = candidates.find(c => c.source === 'sssp_efficiency');
            if (!selectedCandidate) {
              // Fallback to internal if SSSP efficiency not available
              selectedCandidate = candidates.find(c => c.source === 'internal');
            }
          }
          
          // Fallback to SSSP defaults if available
          if (!selectedCandidate && mapping.sssp_defaults?.[species]) {
            const defaults = mapping.sssp_defaults[species];
            if (preferredLibrary === 'precision' && defaults.precision) {
              initialMapping[species] = defaults.precision;
            } else if (preferredLibrary === 'efficiency' && defaults.efficiency) {
              initialMapping[species] = defaults.efficiency;
            } else if (defaults.precision) {
              initialMapping[species] = defaults.precision;
            } else if (defaults.efficiency) {
              initialMapping[species] = defaults.efficiency;
            }
          } else if (selectedCandidate) {
            initialMapping[species] = selectedCandidate.filename;
          }
        } else if (localValue) {
          // Preserve user's local selection (e.g., after download)
          initialMapping[species] = localValue;
        }
      }
      
      setLocalMapping(initialMapping);
      setLibraryPreference(mapping.library_preference || 'internal');
      
      // Set selected element for online search to first species if available
      if (mapping.species.length > 0 && !selectedElement) {
        setSelectedElement(mapping.species[0]);
      }
    }
  }, [mapping]); // Removed selectedElement from deps to avoid unnecessary re-runs
  
  // Analyze selections using backend analyzer (read-only)
  const analyzeSelections = useCallback(async () => {
    if (!projectRoot || !calculation) return;
    
    const allVariants = Object.values(pseudoVariants).flat();
    const selections = Object.entries(selectedSha256ByElement)
      .map(([element, sha256]) => {
        const variant = allVariants.find(v => v.element === element && v.sha256 === sha256);
        if (!variant) return null;
        
        // Determine source_kind: project > internal > lib (priority order)
        let source_kind: 'project' | 'internal' | 'lib' = 'internal';
        const projectSource = variant.sources.find(s => s.kind === 'project' && s.installed);
        const internalSource = variant.sources.find(s => s.kind === 'internal' && s.installed);
        const libSource = variant.sources.find(s => s.kind === 'lib' && s.installed && !s.corrupt);
        
        if (projectSource) source_kind = 'project';
        else if (internalSource) source_kind = 'internal';
        else if (libSource) source_kind = 'lib';
        
        return {
          element,
          requested_basename: variant.basename,
          requested_sha256: sha256,
          requested_sha_family: variant.sha_family,
          source_kind,
          source_path: undefined, // Will be resolved by backend
        };
      })
      .filter((s): s is NonNullable<typeof s> => s !== null);
    
    if (selections.length === 0) {
      setWarningsByElement({});
      setErrorsByElement({});
      return;
    }
    
    try {
      // Build species_map for analyzer
      const speciesMap: Record<string, any> = {};
      for (const sel of selections) {
        speciesMap[sel.element] = {
          pseudopot: sel.requested_basename,
          pseudo_sha256: sel.requested_sha256,
          pseudo_sha_family: sel.requested_sha_family,
          pseudo_basename: sel.requested_basename,
        };
      }
      
      const speciesMapArray = Object.entries(speciesMap).map(([element, entry]) => ({
        element,
        requested_basename: entry.pseudo_basename || entry.pseudopot || '',
        requested_sha256: entry.pseudo_sha256,
        requested_sha_family: entry.pseudo_sha_family,
        source_kind: entry.source_kind,
        source_path: entry.source_path,
      }));
      const response = await qv.analyzeProjectPseudoEffects(projectRoot, speciesMapArray);
      if (response.ok && response.data) {
        const warnings: Record<string, string[]> = {};
        const errors: Record<string, string[]> = {};
        
        // Group warnings/errors by element
        for (const action of response.data.actions || []) {
          if (!warnings[action.element]) warnings[action.element] = [];
          if (action.detail) {
            warnings[action.element].push(action.detail);
          }
        }
        
        for (const warning of response.data.warnings || []) {
          // Parse element from warning message (format: "Element: message")
          const match = warning.match(/^(\w+):\s*(.+)$/);
          if (match) {
            const [, element, msg] = match;
            if (!warnings[element]) warnings[element] = [];
            warnings[element].push(msg);
          }
        }
        
        for (const error of response.data.errors || []) {
          const match = error.match(/^(\w+):\s*(.+)$/);
          if (match) {
            const [, element, msg] = match;
            if (!errors[element]) errors[element] = [];
            errors[element].push(msg);
          }
        }
        
        // Add token-match warnings from variants
        for (const sel of selections) {
          const variant = allVariants.find(v => v.element === sel.element && v.sha256 === sel.requested_sha256);
          if (variant && variant.family_match_warnings && variant.family_match_warnings.length > 0) {
            if (!warnings[sel.element]) warnings[sel.element] = [];
            warnings[sel.element].push(...variant.family_match_warnings);
          }
        }
        
        setWarningsByElement(warnings);
        setErrorsByElement(errors);
      }
    } catch (err) {
      console.error('[CommonCardPseudo] Failed to analyze selections', err);
    }
  }, [projectRoot, calculation, qv, pseudoVariants, selectedSha256ByElement]);
  
  const handlePseudoChange = useCallback((species: string, variant: PseudoVariant) => {
    // Update local state
    setLocalMapping(prev => ({
      ...prev,
      [species]: variant.basename,
    }));
    setLocalMappingSha256(prev => ({
      ...prev,
      [species]: variant.sha256,
    }));
    setLocalMappingShaFamily(prev => ({
      ...prev,
      [species]: variant.sha_family,
    }));
    // Update primary selection key (sha256)
    setSelectedSha256ByElement(prev => ({
      ...prev,
      [species]: variant.sha256,
    }));
    
    // Determine source kind for debug log
    const projectSource = variant.sources.find(s => s.kind === 'project' && s.installed);
    const internalSource = variant.sources.find(s => s.kind === 'internal' && s.installed);
    const libSource = variant.sources.find(s => s.kind === 'lib' && s.installed && !s.corrupt);
    const sourceKind = projectSource ? 'project' : (internalSource ? 'internal' : (libSource ? 'lib' : 'unknown'));
    
    // Write triplet to calc.yml (user-initiated change)
    // IMPORTANT: This is the ONLY place we write calc.yml on user change
    onUpdate(
      { [species]: variant.basename },
      libraryPreference,
      { [species]: variant.sha256 },
      { [species]: variant.sha_family }
    ).then(() => {
      // Debug log: one line per user-initiated change
      console.log(`[CommonCardPseudo] User selection changed: element=${species}, filename=${variant.basename}, sha256=${variant.sha256.substring(0, 16)}..., sha_family=${variant.sha_family.substring(0, 16)}..., source=${sourceKind}`);
    }).catch(err => {
      console.error('[CommonCardPseudo] Failed to write selection to calc.yml', err);
    });
    
    // Trigger analysis after selection change
    setTimeout(() => analyzeSelections(), 100);
  }, [analyzeSelections, onUpdate, libraryPreference]);
  
  const handleLibraryPreferenceChange = useCallback((preference: LibraryPreference) => {
    setLibraryPreference(preference);
    
    // Update unset mappings from the selected library
    if (preference === 'internal') {
      // For INTERNAL, use first candidate from internal source for each element
      if (mapping?.candidates_by_element) {
        setLocalMapping(prev => {
          const updated = { ...prev };
          for (const species of mapping.species) {
            const current = updated[species] || '';
            if (!current) {
              const candidates = mapping.candidates_by_element?.[species] || [];
              const internalCandidate = candidates.find(c => c.source === 'internal');
              if (internalCandidate) {
                updated[species] = internalCandidate.filename;
              }
            }
          }
          return updated;
        });
      }
    } else if (mapping?.sssp_defaults) {
      // For SSSP, use defaults
      setLocalMapping(prev => {
        const updated = { ...prev };
        for (const species of mapping.species) {
          const current = updated[species] || '';
          const defaults = mapping.sssp_defaults?.[species];
          if (defaults) {
            const oldDefault = mapping.library_preference === 'precision' 
              ? defaults.precision 
              : mapping.library_preference === 'efficiency'
              ? defaults.efficiency
              : null;
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
  
  // Check if Apply/Run should be blocked (no viable source for any selection)
  const canApply = useCallback(() => {
    if (!useNewAPI) return true; // Legacy API: always allow
    
    const allVariants = Object.values(pseudoVariants).flat();
    for (const [element, sha256] of Object.entries(selectedSha256ByElement)) {
      const variant = allVariants.find(v => v.element === element && v.sha256 === sha256);
      if (variant) {
        const hasViableSource = variant.sources.some(s => 
          (s.kind === 'project' || s.kind === 'internal' || (s.kind === 'lib' && s.installed && !s.corrupt))
        );
        if (!hasViableSource) {
          return false;
        }
      } else {
        // Variant not found - cannot apply
        return false;
      }
    }
    return true;
  }, [useNewAPI, pseudoVariants, selectedSha256ByElement]);
  
  const handleApply = useCallback(async () => {
    // Re-analyze before applying
    await analyzeSelections();
    
    // Check gating
    if (!canApply()) {
      // Error already shown in warnings panel
      return;
    }
    
    // Apply writes triplet together (filename + sha256 + sha_family)
    // Note: handlePseudoChange already writes on user change, but Apply button
    // ensures all selections are written together
    await onUpdate(localMapping, libraryPreference, localMappingSha256, localMappingShaFamily);
  }, [localMapping, libraryPreference, localMappingSha256, localMappingShaFamily, onUpdate, analyzeSelections, canApply]);
  
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
          // Find variant by filename or create a minimal one
          const variants = pseudoVariants[candidate.element] || [];
          const variant = variants.find(v => v.basename === result.filename) || variants[0];
          if (variant) {
            handlePseudoChange(candidate.element, variant);
          }
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
  
  // Helper to get source label
  const getSourceLabel = (source: string): string => {
    switch (source) {
      case 'internal': return 'Internal';
      case 'sssp_precision': return 'SSSP Precision';
      case 'sssp_efficiency': return 'SSSP Efficiency';
      case 'project': return 'Project';
      default: return source;
    }
  };
  
  // Helper to get source badge class
  const getSourceBadgeClass = (source: string): string => {
    switch (source) {
      case 'internal': return 'pseudo-source-badge--internal';
      case 'sssp_precision': return 'pseudo-source-badge--sssp-precision';
      case 'sssp_efficiency': return 'pseudo-source-badge--sssp-efficiency';
      case 'project': return 'pseudo-source-badge--project';
      default: return '';
    }
  };
  
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
        {/* Library preference selector - only show for old API */}
        {isEditing && !useNewAPI && (
          <div className="common-card-pseudo__library">
            <label>Library:</label>
            <select
              value={libraryPreference}
              onChange={(e) => handleLibraryPreferenceChange(e.target.value as LibraryPreference)}
              className="common-card-pseudo__library-select"
            >
              <option value="internal">
                Internal{mapping.installed_sources?.internal ? '' : ' — not available'}
              </option>
              <option 
                value="precision" 
                disabled={mapping.installed_sources && !mapping.installed_sources.sssp_precision}
              >
                SSSP Precision{mapping.installed_sources && !mapping.installed_sources.sssp_precision ? ' — not installed' : ''}
              </option>
              <option 
                value="efficiency"
                disabled={mapping.installed_sources && !mapping.installed_sources.sssp_efficiency}
              >
                SSSP Efficiency{mapping.installed_sources && !mapping.installed_sources.sssp_efficiency ? ' — not installed' : ''}
              </option>
            </select>
            {mapping.installed_sources && !mapping.installed_sources.sssp_precision && !mapping.installed_sources.sssp_efficiency && (
              <div className="common-card-pseudo__library-note">
                SSSP libraries not installed. Install from Settings or use Internal library.
              </div>
            )}
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
                  const resolvedInfo = mapping.resolved_by_element?.[species];
                  
                  if (useNewAPI) {
                    // New API: use sha256-keyed variants (constitution-compliant)
                    const variants = pseudoVariants[species] || [];
                    const legacyOptions = pseudoOptions[species] || [];
                    
                    // Determine if using new format or legacy
                    const useVariants = variants.length > 0;
                    
                    // Filter to only filesystem-real options (project/internal or installed lib)
                    const realVariants = useVariants ? variants.filter(v => {
                      const hasProject = v.sources.some(s => s.kind === 'project' && s.installed);
                      const hasInternal = v.sources.some(s => s.kind === 'internal' && s.installed);
                      const hasInstalledLib = v.sources.some(s => s.kind === 'lib' && s.installed && !s.corrupt);
                      return hasProject || hasInternal || hasInstalledLib;
                    }) : [];
                    
                    // Find current selection (sha256-primary)
                    const currentSha256 = selectedSha256ByElement[species];
                    let currentVariant: PseudoVariant | null = null;
                    let currentOption: PseudoOption | null = null;
                    
                    if (useVariants && currentSha256) {
                      currentVariant = realVariants.find(v => v.sha256 === currentSha256) || null;
                    } else if (!useVariants) {
                      // Legacy: find by sha256 or basename
                      currentOption = legacyOptions.find(opt => 
                        opt.display_basename === currentPseudo || 
                        opt.all_basenames.includes(currentPseudo) ||
                        opt.sha256 === currentPseudo
                      ) || null;
                    }
                    
                    // Check if selection has viable source (for Apply/Run gating)
                    const hasViableSource = useVariants && currentVariant
                      ? currentVariant.sources.some(s => 
                          (s.kind === 'project' || s.kind === 'internal' || (s.kind === 'lib' && s.installed && !s.corrupt))
                        )
                      : currentOption
                      ? currentOption.sources.some(s => s.installed && !s.corrupt)
                      : false;
                    
                    // Get warnings/errors for this element
                    const elementWarnings = warningsByElement[species] || [];
                    const elementErrors = errorsByElement[species] || [];
                    
                    return (
                      <tr key={species}>
                        <td>
                          <strong>{species}</strong>
                        </td>
                        <td>
                          {isEditing ? (
                            <div className="common-card-pseudo__pseudo-select">
                              {isLoadingOptions ? (
                                <div className="common-card-pseudo__loading">Loading options...</div>
                              ) : (
                                <>
                                  <select
                                    value={useVariants && currentVariant ? currentVariant.sha256 : (currentOption ? currentOption.sha256 : '')}
                                    onChange={(e) => {
                                      const selectedValue = e.target.value;
                                      if (useVariants) {
                                        const selected = realVariants.find(v => v.sha256 === selectedValue);
                                        if (selected) {
                                          handlePseudoChange(species, selected);
                                        }
                                      } else {
                                        const selected = legacyOptions.find(opt => opt.sha256 === selectedValue);
                                        if (selected) {
                                          // Legacy: create a minimal variant-like object
                                          const legacyVariant: PseudoVariant = {
                                            sha256: selected.sha256,
                                            sha_family: selected.sha_family,
                                            basename: selected.display_basename,
                                            element: selected.element,
                                            sources: selected.sources.map(s => ({
                                              kind: s.kind === 'library' ? 'lib' : s.kind,
                                              label: s.label,
                                              installed: s.installed,
                                              corrupt: s.corrupt,
                                              warning: s.warning,
                                              archive_asset: s.archive_asset,
                                            })),
                                            display_label: selected.display_basename,
                                            availability: selected.availability,
                                          };
                                          handlePseudoChange(species, legacyVariant);
                                        }
                                      }
                                    }}
                                    className={`common-card-pseudo__select ${
                                      !currentPseudo ? 'common-card-pseudo__select--unset' : ''
                                    }`}
                                    style={{ width: 'max-content', maxWidth: '520px' }}
                                  >
                                    <option value="">— Select —</option>
                                    {useVariants ? (
                                      // New format: variants keyed by sha256
                                      realVariants.map((variant) => (
                                        <option key={variant.sha256} value={variant.sha256}>
                                          {variant.display_label}
                                        </option>
                                      ))
                                    ) : (
                                      // Legacy format: options keyed by sha256
                                      legacyOptions.map((opt, idx) => {
                                        const collisions = legacyOptions.filter(o => o.display_basename === opt.display_basename);
                                        const hasCollision = collisions.length > 1;
                                        const displayName = hasCollision 
                                          ? `${opt.display_basename} · ${opt.sha256.substring(0, 8)}`
                                          : opt.display_basename;
                                        
                                        return (
                                          <option key={`${opt.sha256}-${idx}`} value={opt.sha256}>
                                            {displayName}
                                          </option>
                                        );
                                      })
                                    )}
                                  </select>
                                  {/* Show source chips */}
                                  {useVariants && currentVariant && (
                                    <div className="common-card-pseudo__source-chips">
                                      {currentVariant.sources.map((source, idx) => (
                                        <span
                                          key={idx}
                                          className={`common-card-pseudo__source-chip ${
                                            (source.kind === 'project' || source.kind === 'internal' || (source.kind === 'lib' && source.installed && !source.corrupt))
                                              ? 'common-card-pseudo__source-chip--installed' 
                                              : 'common-card-pseudo__source-chip--available'
                                          }`}
                                          title={
                                            source.corrupt && source.warning
                                              ? source.warning
                                              : source.archive_asset || source.label
                                          }
                                        >
                                          {source.corrupt ? '⚠️ ' : ''}{source.label}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  {!useVariants && currentOption && (
                                    <div className="common-card-pseudo__source-chips">
                                      {currentOption.sources.map((source, idx) => (
                                        <span
                                          key={idx}
                                          className={`common-card-pseudo__source-chip ${
                                            source.installed && !source.corrupt
                                              ? 'common-card-pseudo__source-chip--installed' 
                                              : 'common-card-pseudo__source-chip--available'
                                          }`}
                                          title={
                                            source.corrupt && source.warning
                                              ? source.warning
                                              : source.archive_asset || source.label
                                          }
                                        >
                                          {source.corrupt ? '⚠️ ' : ''}{source.label}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  {/* Token-match warnings */}
                                  {useVariants && currentVariant && currentVariant.family_match_warnings && currentVariant.family_match_warnings.length > 0 && (
                                    <div className="common-card-pseudo__warnings-inline">
                                      {currentVariant.family_match_warnings.map((warn, idx) => (
                                        <div key={`family-warn-${idx}`} className="common-card-pseudo__warning-info">
                                          ⚠️ {warn}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {/* Warnings panel (right side, per element) */}
                                  {(elementWarnings.length > 0 || elementErrors.length > 0) && (
                                    <div className="common-card-pseudo__warnings-inline">
                                      {elementErrors.map((err, idx) => (
                                        <div key={`error-${idx}`} className="common-card-pseudo__warning-error">
                                          ⚠️ {err}
                                        </div>
                                      ))}
                                      {elementWarnings.map((warn, idx) => (
                                        <div key={`warn-${idx}`} className="common-card-pseudo__warning-info">
                                          ℹ️ {warn}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {/* Apply/Run gating warning */}
                                  {currentVariant && !hasViableSource && (
                                    <div className="common-card-pseudo__warning-error">
                                      ⚠️ Selected pseudo requires installing archive(s). Go to Settings → Pseudopotentials.
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          ) : (
                            <div className="common-card-pseudo__pseudo-display">
                              <code>{currentPseudo || '—'}</code>
                              {useVariants && currentVariant && (
                                <div className="common-card-pseudo__source-chips">
                                  {currentVariant.sources.map((source, idx) => (
                                    <span
                                      key={idx}
                                      className={`common-card-pseudo__source-chip ${
                                        (source.kind === 'project' || source.kind === 'internal' || (source.kind === 'lib' && source.installed && !source.corrupt))
                                          ? 'common-card-pseudo__source-chip--installed' 
                                          : 'common-card-pseudo__source-chip--available'
                                      }`}
                                      title={source.corrupt && source.warning ? source.warning : undefined}
                                    >
                                      {source.corrupt ? '⚠️ ' : ''}{source.label}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {!useVariants && currentOption && (
                                <div className="common-card-pseudo__source-chips">
                                  {currentOption.sources.map((source, idx) => (
                                    <span
                                      key={idx}
                                      className={`common-card-pseudo__source-chip ${
                                        source.installed && !source.corrupt
                                          ? 'common-card-pseudo__source-chip--installed' 
                                          : 'common-card-pseudo__source-chip--available'
                                      }`}
                                      title={source.corrupt && source.warning ? source.warning : undefined}
                                    >
                                      {source.corrupt ? '⚠️ ' : ''}{source.label}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  } else {
                    // Old API: use candidates_by_element
                  const candidates = mapping.candidates_by_element?.[species] || [];
                  
                  // Group candidates by source
                  const candidatesBySource: Record<string, typeof candidates> = {};
                  for (const cand of candidates) {
                    if (!candidatesBySource[cand.source]) {
                      candidatesBySource[cand.source] = [];
                    }
                    candidatesBySource[cand.source].push(cand);
                  }
                  
                  // Get current source
                  const currentSource = resolvedInfo?.source || null;
                  const isResolved = resolvedInfo?.resolved || false;
                  const inProject = resolvedInfo?.in_project || false;
                  
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
                              onChange={(e) => {
                                const selectedFilename = e.target.value;
                                // Find candidate by filename
                                const selectedCandidate = candidates.find(c => c.filename === selectedFilename);
                                if (selectedCandidate) {
                                  // Create minimal variant-like object for legacy API
                                  const legacyVariant: PseudoVariant = {
                                    sha256: '', // Not available in legacy API
                                    sha_family: '',
                                    basename: selectedCandidate.filename,
                                    element: species,
                                    sources: [{
                                      kind: selectedCandidate.source === 'sssp_precision' ? 'lib' : 
                                            selectedCandidate.source === 'sssp_efficiency' ? 'lib' :
                                            selectedCandidate.source === 'internal' ? 'internal' : 'project',
                                      label: selectedCandidate.source === 'sssp_precision' ? 'SSSP Precision' :
                                             selectedCandidate.source === 'sssp_efficiency' ? 'SSSP Efficiency' :
                                             selectedCandidate.source === 'internal' ? 'Internal' : 'Project',
                                      installed: true,
                                    }],
                                    display_label: selectedCandidate.filename,
                                    availability: { any_installed: true },
                                  };
                                  handlePseudoChange(species, legacyVariant);
                                }
                              }}
                              className={`common-card-pseudo__select ${
                                !currentPseudo ? 'common-card-pseudo__select--unset' : ''
                              }`}
                            >
                              <option value="">— Select —</option>
                              {/* Group by source */}
                              {candidatesBySource['internal'] && candidatesBySource['internal'].length > 0 && (
                                <optgroup label="Internal">
                                  {candidatesBySource['internal'].map(cand => (
                                    <option key={cand.filename} value={cand.filename}>
                                      {cand.filename}
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              {candidatesBySource['sssp_precision'] && candidatesBySource['sssp_precision'].length > 0 && (
                                <optgroup label="SSSP Precision">
                                  {candidatesBySource['sssp_precision'].map(cand => (
                                    <option key={cand.filename} value={cand.filename}>
                                      {cand.filename}
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              {candidatesBySource['sssp_efficiency'] && candidatesBySource['sssp_efficiency'].length > 0 && (
                                <optgroup label="SSSP Efficiency">
                                  {candidatesBySource['sssp_efficiency'].map(cand => (
                                    <option key={cand.filename} value={cand.filename}>
                                      {cand.filename}
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              {candidatesBySource['project'] && candidatesBySource['project'].length > 0 && (
                                <optgroup label="Project">
                                  {candidatesBySource['project'].map(cand => (
                                    <option key={cand.filename} value={cand.filename}>
                                      {cand.filename}
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                            </select>
                            {/* Show resolved status */}
                            {currentPseudo && isResolved && currentSource && (
                              <span className={`common-card-pseudo__source-badge ${getSourceBadgeClass(currentSource)}`}>
                                {getSourceLabel(currentSource)}
                                {!inProject && (
                                  <span className="common-card-pseudo__copy-note" title="Will be copied into project on run">
                                    (will copy)
                                  </span>
                                )}
                              </span>
                            )}
                            {/* Only show warning if truly unresolved */}
                            {currentPseudo && !isResolved && (
                              <span className="common-card-pseudo__not-found">
                                ⚠️ Not found
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="common-card-pseudo__pseudo-display">
                            <code>{currentPseudo || '—'}</code>
                            {currentSource && (
                              <span className={`common-card-pseudo__source-badge ${getSourceBadgeClass(currentSource)}`}>
                                {getSourceLabel(currentSource)}
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                  }
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="common-card-pseudo__no-species">
            <p>No species found in structure.</p>
          </div>
        )}
        
        {/* Info: minimal, clean */}
        {isEditing && (
          <div className="common-card-pseudo__info">
            <small>
              Pseudopotentials will be copied into <code>project/pseudo/</code> when the calculation runs.
            </small>
          </div>
        )}
        
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
              disabled={!canApply()}
              className="common-card-pseudo__apply-btn"
              title={!canApply() ? "Selected pseudo(s) require installing archive(s). Go to Settings → Pseudopotentials." : undefined}
            >
              Apply
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
