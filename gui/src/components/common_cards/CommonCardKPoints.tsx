/**
 * CommonCardKPoints - K_POINTS card editor (unified)
 * 
 * STATE MODEL (CANONICAL SOURCE OF TRUTH):
 * =========================================
 * 
 * Canonical source: rawBodyText (string)
 * - This is the SINGLE source of truth for the K_POINTS body data
 * - All structured state (localAutomatic, localPoints) is DERIVED from rawBodyText
 * - When user edits structured fields, rawBodyText is UPDATED (one-way: structured -> rawBodyText)
 * - When user edits raw text, rawBodyText is UPDATED directly
 * - On Apply, rawBodyText is ALWAYS saved (never structured state directly)
 * 
 * Flow:
 * 1. Initialize: viewModel -> derive rawBodyText -> derive structured state (for display)
 * 2. Structured edit: update structured state -> update rawBodyText (one-way sync)
 * 3. Raw edit: update rawBodyText directly (no sync to structured)
 * 4. Apply: save rawBodyText (with mode header) -> backend re-parses on next load
 * 
 * NO TWO-WAY SYNC:
 * - rawBodyText never syncs FROM structured state after raw edit
 * - Structured state only syncs FROM rawBodyText when toggling raw->structured (parse)
 * - This prevents loops and preserves user raw edits
 * 
 * Architecture:
 * - Single source of truth: rawBodyText (string)
 * - Raw text is derived from view model, not the other way around
 * - Mode/header is ALWAYS controlled by dropdown (never raw text)
 * 
 * Edit modes:
 * - Structured (default): Edit via dropdown and inputs
 * - Raw: Edit raw text body ONLY (mode still locked to dropdown)
 * - When toggling back from raw to structured, parses best effort and warns if data lost
 * 
 * Apply behavior:
 * - Apply ALWAYS saves current state (structured OR raw) without requiring mode toggle
 * - Raw edits are persisted immediately on Apply
 * - No silent data loss
 */

import { useState, useEffect, useCallback, useMemo, useImperativeHandle, forwardRef, useRef } from 'react';
import './CommonCardKPoints.css';

interface KPointsViewModel {
  raw: string;
  mode: string;
  automatic?: {
    nk1: number;
    nk2: number;
    nk3: number;
    sk1: number;
    sk2: number;
    sk3: number;
  };
  points?: Array<{
    x: number;
    y: number;
    z: number;
    w: number;
  }>;
  parse_ok?: boolean;
  canonical_raw?: string;
  warnings?: string[];
  errors?: string[];
  summary?: string;
}

// Raw card data format from step detail (when view model unavailable)
interface RawCardData {
  option?: string;
  data?: string[] | string[][];
}

interface CommonCardKPointsProps {
  viewModel: KPointsViewModel | null;
  rawCardData?: RawCardData;
  isEditing: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onApplyingChange?: (applying: boolean) => void;
  onUpdate: (viewModel: KPointsViewModel) => Promise<void>;
}

export interface CommonCardKPointsRef {
  apply: () => Promise<void>;
  isDirty: boolean;
  isApplying: boolean;
}

const K_POINTS_MODES = [
  { value: 'gamma', label: 'Gamma' },
  { value: 'automatic', label: 'Automatic' },
  { value: 'tpiba', label: 'tpiba' },
  { value: 'crystal', label: 'crystal' },
  { value: 'tpiba_b', label: 'tpiba_b (band path)' },
  { value: 'crystal_b', label: 'crystal_b (band path)' },
  { value: 'tpiba_c', label: 'tpiba_c (band path)' },
  { value: 'crystal_c', label: 'crystal_c (band path)' },
];

/**
 * Convert raw card data to raw text string for fallback display
 */
function rawCardDataToText(rawData: RawCardData | undefined): string {
  if (!rawData) return '';
  
  const lines: string[] = [];
  
  // Header line
  if (rawData.option) {
    lines.push(`K_POINTS ${rawData.option}`);
  } else {
    lines.push('K_POINTS');
  }
  
  // Data lines
  if (rawData.data) {
    for (const line of rawData.data) {
      if (Array.isArray(line)) {
        lines.push(line.join(' '));
      } else {
        lines.push(String(line));
      }
    }
  }
  
  return lines.join('\n');
}

/**
 * Generate the body portion of K_POINTS (everything after the header line)
 */
function generateBodyFromViewModel(vm: KPointsViewModel): string {
  if (vm.mode === 'gamma') {
    return ''; // No body for gamma
  }
  
  if (vm.mode === 'automatic' && vm.automatic) {
    const { nk1, nk2, nk3, sk1, sk2, sk3 } = vm.automatic;
    return `${nk1} ${nk2} ${nk3} ${sk1} ${sk2} ${sk3}`;
  }
  
  if (vm.points && vm.points.length > 0) {
    const lines = [String(vm.points.length)];
    for (const pt of vm.points) {
      lines.push(`${pt.x} ${pt.y} ${pt.z} ${pt.w}`);
    }
    return lines.join('\n');
  }
  
  // Fallback: extract body from raw (with defensive check)
  if (vm.raw) {
    const rawLines = vm.raw.split('\n');
    if (rawLines.length > 1) {
      return rawLines.slice(1).join('\n');
    }
  }

  return '';
}

/**
 * Parse body text back into view model fields based on mode
 */
function parseBodyToViewModel(mode: string, bodyText: string): Partial<KPointsViewModel> {
  const lines = bodyText.trim().split('\n').filter(l => l.trim());
  
  if (mode === 'gamma') {
    return { automatic: undefined, points: undefined };
  }
  
  if (mode === 'automatic') {
    if (lines.length > 0) {
      const parts = lines[0].split(/\s+/).map(Number);
      if (parts.length >= 6 && parts.every(n => !isNaN(n))) {
        return {
          automatic: {
            nk1: parts[0],
            nk2: parts[1],
            nk3: parts[2],
            sk1: parts[3],
            sk2: parts[4],
            sk3: parts[5],
          },
          points: undefined,
        };
      }
    }
    // Fallback: keep defaults
    return {
      automatic: { nk1: 8, nk2: 8, nk3: 8, sk1: 0, sk2: 0, sk3: 0 },
      points: undefined,
    };
  }
  
  // List modes (tpiba, crystal, etc.)
  if (lines.length > 0) {
    const nPts = parseInt(lines[0]);
    if (!isNaN(nPts)) {
      const points: Array<{ x: number; y: number; z: number; w: number }> = [];
      for (let i = 1; i <= nPts && i < lines.length; i++) {
        const parts = lines[i].split(/\s+/).map(Number);
        if (parts.length >= 3) {
          points.push({
            x: parts[0] || 0,
            y: parts[1] || 0,
            z: parts[2] || 0,
            w: parts[3] ?? 1,
          });
        }
      }
      return { automatic: undefined, points };
    }
  }
  
  return { automatic: undefined, points: [] };
}

export const CommonCardKPoints = forwardRef<CommonCardKPointsRef, CommonCardKPointsProps>(({
  viewModel,
  rawCardData,
  isEditing,
  onDirtyChange,
  onApplyingChange,
  onUpdate,
}, ref) => {
  // CANONICAL SOURCE OF TRUTH: rawBodyText (string)
  const [rawBodyText, setRawBodyText] = useState('');
  
  // Derived state (for display/editing - always synced FROM rawBodyText when needed)
  const [localMode, setLocalMode] = useState<string>('automatic');
  const [localAutomatic, setLocalAutomatic] = useState({
    nk1: 8, nk2: 8, nk3: 8, sk1: 0, sk2: 0, sk3: 0
  });
  const [localPoints, setLocalPoints] = useState<Array<{ x: number; y: number; z: number; w: number }>>([]);
  
  // Edit mode: structured vs raw
  const [useRawEdit, setUseRawEdit] = useState(false);
  const [parseWarning, setParseWarning] = useState<string | null>(null);
  
  // UI state
  const [isExpanded, setIsExpanded] = useState(true); // Always expanded by default
  const [showDebugInfo, setShowDebugInfo] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  
  // In-flight guard to prevent double-submit
  const isApplyingRef = useRef(false);
  
  // Derive structured state from rawBodyText (one-way: rawBodyText -> structured)
  // This is called when toggling raw->structured or when initializing
  const syncStructuredFromRaw = useCallback((bodyText: string, mode: string) => {
    const parsed = parseBodyToViewModel(mode, bodyText);
    if (parsed.automatic) {
      setLocalAutomatic(parsed.automatic);
    }
    if (parsed.points) {
      setLocalPoints(parsed.points);
    }
  }, []);
  
  // Initialize from viewModel (one-time, when viewModel changes)
  useEffect(() => {
    if (viewModel) {
      setLocalMode(viewModel.mode || 'automatic');
      const bodyText = generateBodyFromViewModel(viewModel);
      setRawBodyText(bodyText); // Set canonical source
      syncStructuredFromRaw(bodyText, viewModel.mode || 'automatic'); // Derive structured
      setIsDirty(false);
      setParseWarning(null);
    } else if (rawCardData) {
      // Fallback: extract mode from option
      const mode = rawCardData.option?.toLowerCase() || 'automatic';
      setLocalMode(mode);
      const fullText = rawCardDataToText(rawCardData);
      const bodyText = fullText.split('\n').slice(1).join('\n');
      setRawBodyText(bodyText); // Set canonical source
      syncStructuredFromRaw(bodyText, mode); // Derive structured
      setIsDirty(false);
    }
  }, [viewModel, rawCardData, syncStructuredFromRaw]);
  
  // Reset raw edit mode when exiting edit mode
  useEffect(() => {
    if (!isEditing) {
      setUseRawEdit(false);
      setParseWarning(null);
    }
  }, [isEditing]);
  
  // Build full raw text for display and saving
  const fullRawText = useMemo(() => {
    const header = localMode === 'gamma' ? 'K_POINTS gamma' : `K_POINTS ${localMode}`;
    if (!rawBodyText.trim()) return header;
    return `${header}\n${rawBodyText}`;
  }, [localMode, rawBodyText]);
  
  // Handle apply - CRITICAL: Always saves rawBodyText (canonical source)
  const handleApply = useCallback(async () => {
    // Prevent double-submit
    if (isApplyingRef.current) {
      return;
    }
    
    isApplyingRef.current = true;
    onApplyingChange?.(true);
    
    try {
      // Build view model from canonical source (rawBodyText)
      const newViewModel: KPointsViewModel = {
        raw: fullRawText,
        mode: localMode,
        canonical_raw: fullRawText,
      };
      
      // If in raw mode, we save the raw text as-is
      // Backend will re-parse on next load
      if (useRawEdit) {
        // Raw mode: save exactly what user typed
        newViewModel.parse_ok = false; // Mark as unparsed since we're saving raw
      } else {
        // Structured mode: include structured fields for backend validation
        if (localMode === 'automatic') {
          newViewModel.automatic = { ...localAutomatic };
        } else if (localMode !== 'gamma') {
          newViewModel.points = [...localPoints];
        }
        newViewModel.parse_ok = true;
      }
      
      await onUpdate(newViewModel);
      setIsDirty(false);
      setParseWarning(null);
    } finally {
      isApplyingRef.current = false;
      onApplyingChange?.(false);
    }
  }, [fullRawText, localMode, localAutomatic, localPoints, useRawEdit, onUpdate, onApplyingChange]);
  
  // Expose apply, isDirty, and isApplying to parent via ref
  useImperativeHandle(ref, () => ({
    apply: handleApply,
    isDirty,
    isApplying: isApplyingRef.current,
  }), [isDirty, handleApply]);
  
  // Notify parent of dirty state changes
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);
  
  // Handle mode change - updates rawBodyText (canonical source)
  const handleModeChange = useCallback((newMode: string) => {
    setLocalMode(newMode);
    setIsDirty(true);
    
    // Update canonical source (rawBodyText) based on new mode
    if (newMode === 'gamma') {
      setRawBodyText('');
      setLocalAutomatic({ nk1: 8, nk2: 8, nk3: 8, sk1: 0, sk2: 0, sk3: 0 });
      setLocalPoints([]);
    } else if (newMode === 'automatic') {
      const bodyText = `${localAutomatic.nk1} ${localAutomatic.nk2} ${localAutomatic.nk3} ${localAutomatic.sk1} ${localAutomatic.sk2} ${localAutomatic.sk3}`;
      setRawBodyText(bodyText);
    } else {
      // List modes
      if (localPoints.length > 0) {
        const lines = [String(localPoints.length)];
        for (const pt of localPoints) {
          lines.push(`${pt.x} ${pt.y} ${pt.z} ${pt.w}`);
        }
        setRawBodyText(lines.join('\n'));
      } else {
        const defaultBody = '1\n0.0 0.0 0.0 1.0';
        setRawBodyText(defaultBody);
        setLocalPoints([{ x: 0, y: 0, z: 0, w: 1 }]);
      }
    }
  }, [localAutomatic, localPoints]);
  
  // Handle automatic field change - updates rawBodyText (canonical source)
  const handleAutomaticChange = useCallback((field: string, value: number) => {
    setLocalAutomatic(prev => {
      const updated = { ...prev, [field]: value };
      // Update canonical source (rawBodyText) - ONE-WAY: structured -> rawBodyText
      const bodyText = `${updated.nk1} ${updated.nk2} ${updated.nk3} ${updated.sk1} ${updated.sk2} ${updated.sk3}`;
      setRawBodyText(bodyText);
      return updated;
    });
    setIsDirty(true);
  }, []);
  
  // Handle point change - updates rawBodyText (canonical source)
  const handlePointChange = useCallback((index: number, field: 'x' | 'y' | 'z' | 'w', value: number) => {
    setLocalPoints(prev => {
      const newPoints = [...prev];
      newPoints[index] = { ...newPoints[index], [field]: value };
      // Update canonical source (rawBodyText) - ONE-WAY: structured -> rawBodyText
      const lines = [String(newPoints.length)];
      for (const pt of newPoints) {
        lines.push(`${pt.x} ${pt.y} ${pt.z} ${pt.w}`);
      }
      setRawBodyText(lines.join('\n'));
      return newPoints;
    });
    setIsDirty(true);
  }, []);
  
  // Handle add point - updates rawBodyText (canonical source)
  const handleAddPoint = useCallback(() => {
    setLocalPoints(prev => {
      const newPoints = [...prev, { x: 0, y: 0, z: 0, w: 1 }];
      // Update canonical source (rawBodyText) - ONE-WAY: structured -> rawBodyText
      const lines = [String(newPoints.length)];
      for (const pt of newPoints) {
        lines.push(`${pt.x} ${pt.y} ${pt.z} ${pt.w}`);
      }
      setRawBodyText(lines.join('\n'));
      return newPoints;
    });
    setIsDirty(true);
  }, []);
  
  // Handle remove point - updates rawBodyText (canonical source)
  const handleRemovePoint = useCallback((index: number) => {
    setLocalPoints(prev => {
      const newPoints = prev.filter((_, i) => i !== index);
      if (newPoints.length > 0) {
        // Update canonical source (rawBodyText) - ONE-WAY: structured -> rawBodyText
        const lines = [String(newPoints.length)];
        for (const pt of newPoints) {
          lines.push(`${pt.x} ${pt.y} ${pt.z} ${pt.w}`);
        }
        setRawBodyText(lines.join('\n'));
      } else {
        setRawBodyText('');
      }
      return newPoints;
    });
    setIsDirty(true);
  }, []);
  
  // Toggle raw edit mode
  const handleToggleRawEdit = useCallback(() => {
    if (useRawEdit) {
      // Switching from raw to structured: parse rawBodyText (canonical source) -> structured
      syncStructuredFromRaw(rawBodyText, localMode);
      // Check if parse was lossy
      const originalLines = rawBodyText.trim().split('\n').filter(l => l.trim()).length;
      const parsedCount = localMode === 'automatic' ? 1 : (localPoints.length || 0) + 1;
      if (originalLines !== parsedCount && originalLines > 0) {
        setParseWarning(`Some data may have been lost during parsing (${originalLines} lines → ${parsedCount} parsed)`);
      } else {
        setParseWarning(null);
      }
    }
    setUseRawEdit(!useRawEdit);
  }, [useRawEdit, localMode, rawBodyText, localPoints, syncStructuredFromRaw]);
  
  // Handle raw body text change - updates canonical source directly
  const handleRawBodyChange = useCallback((text: string) => {
    setRawBodyText(text); // Direct update to canonical source
    setIsDirty(true);
    // NO sync to structured state - preserves user raw edits
  }, []);
  
  // No card data at all
  if (!viewModel && !rawCardData) {
    return (
      <div className="kpoints-card">
        <div className="kpoints-card__header">
          <span className="kpoints-card__title">K_POINTS</span>
        </div>
        <div className="kpoints-card__empty">
          <p>No K_POINTS card found</p>
        </div>
      </div>
    );
  }
  
  const isListMode = !['gamma', 'automatic'].includes(localMode);
  
  // Generate summary text
  const getSummaryText = () => {
    if (viewModel?.summary && !isDirty) return viewModel.summary;
    
    if (localMode === 'gamma') return 'Gamma point only';
    if (localMode === 'automatic') {
      const { nk1, nk2, nk3, sk1, sk2, sk3 } = localAutomatic;
      return `Automatic ${nk1}×${nk2}×${nk3} shift ${sk1} ${sk2} ${sk3}`;
    }
    if (isListMode) {
      return `${localMode} (${localPoints.length} points)`;
    }
    return 'Custom';
  };
  
  // Non-edit mode: clean summary view (always expanded)
  if (!isEditing) {
    return (
      <div className="kpoints-card">
        <div className="kpoints-card__header">
          <span className="kpoints-card__title">K_POINTS</span>
          <span className="kpoints-card__summary">{getSummaryText()}</span>
          <div className="kpoints-card__header-actions">
            <button
              type="button"
              className={`kpoints-card__toggle-btn ${!isExpanded ? 'kpoints-card__toggle-btn--active' : ''}`}
              onClick={() => setIsExpanded(!isExpanded)}
              title={isExpanded ? "Collapse" : "Expand"}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
            <button
              type="button"
              className={`kpoints-card__toggle-btn ${showDebugInfo ? 'kpoints-card__toggle-btn--active' : ''}`}
              onClick={() => setShowDebugInfo(!showDebugInfo)}
              title="Show debug info"
            >
              🔍
            </button>
          </div>
        </div>
        
        {isExpanded && (
          <>
            {/* Warnings */}
            {viewModel?.warnings && viewModel.warnings.length > 0 && (
              <div className="kpoints-card__warnings">
                {viewModel.warnings.map((w, i) => (
                  <div key={i} className="kpoints-card__warning">⚠️ {w}</div>
                ))}
              </div>
            )}
            
            {/* Raw Text Pane (always visible when expanded) */}
            <div className="kpoints-card__raw-pane">
              <div className="kpoints-card__raw-pane-label">Raw QE Text:</div>
              <pre className="kpoints-card__raw-pane-content">{viewModel?.canonical_raw || fullRawText}</pre>
              <div className="kpoints-card__raw-pane-actions">
                <button
                  type="button"
                  className="kpoints-card__copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(viewModel?.canonical_raw || fullRawText);
                  }}
                  title="Copy raw text to clipboard"
                >
                  📋 Copy
                </button>
              </div>
            </div>
            
            {/* Debug Info (non-intrusive) */}
            {showDebugInfo && (
              <div className="kpoints-card__debug-pane">
                <div className="kpoints-card__debug-label">Debug Info (Parsed JSON):</div>
                <pre className="kpoints-card__debug-content">
                  {JSON.stringify({
                    mode: viewModel?.mode || localMode,
                    parse_ok: viewModel?.parse_ok,
                    automatic: viewModel?.automatic || localAutomatic,
                    points: viewModel?.points || localPoints,
                    warnings: viewModel?.warnings,
                    errors: viewModel?.errors,
                    raw: viewModel?.raw || fullRawText,
                  }, null, 2)}
                </pre>
                <div className="kpoints-card__debug-actions">
                  <button
                    type="button"
                    className="kpoints-card__copy-btn"
                    onClick={() => {
                      const debugJson = JSON.stringify({
                        mode: viewModel?.mode || localMode,
                        parse_ok: viewModel?.parse_ok,
                        automatic: viewModel?.automatic || localAutomatic,
                        points: viewModel?.points || localPoints,
                        warnings: viewModel?.warnings,
                        errors: viewModel?.errors,
                        raw: viewModel?.raw || fullRawText,
                      }, null, 2);
                      navigator.clipboard.writeText(debugJson);
                    }}
                    title="Copy debug JSON to clipboard"
                  >
                    📋 Copy JSON
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  }
  
  // Edit mode
  return (
    <div className="kpoints-card kpoints-card--editing">
      <div className="kpoints-card__header">
        <span className="kpoints-card__title">K_POINTS</span>
        <div className="kpoints-card__edit-toggle">
          <button
            type="button"
            className={`kpoints-card__mode-btn ${!useRawEdit ? 'kpoints-card__mode-btn--active' : ''}`}
            onClick={() => useRawEdit && handleToggleRawEdit()}
            title="Structured editor"
          >
            📊 Structured
          </button>
          <button
            type="button"
            className={`kpoints-card__mode-btn ${useRawEdit ? 'kpoints-card__mode-btn--active' : ''}`}
            onClick={() => !useRawEdit && handleToggleRawEdit()}
            title="Raw text editor"
          >
            📝 Raw
          </button>
        </div>
        {isDirty && <span className="kpoints-card__dirty-indicator">• Modified</span>}
        {isDirty && (
          <button
            type="button"
            onClick={handleApply}
            className="kpoints-card__apply-btn-header"
            disabled={isApplyingRef.current}
            title="Apply K_POINTS changes"
          >
            {isApplyingRef.current ? 'Applying...' : 'Apply'}
          </button>
        )}
      </div>
      
      {/* Parse warning */}
      {parseWarning && (
        <div className="kpoints-card__parse-warning">
          ⚠️ {parseWarning}
        </div>
      )}
      
      <div className="kpoints-card__content">
        {/* Mode selector - always available */}
        <div className="kpoints-card__field">
          <label>Mode:</label>
          <select
            value={localMode}
            onChange={(e) => handleModeChange(e.target.value)}
            disabled={useRawEdit}
          >
            {K_POINTS_MODES.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          {useRawEdit && (
            <span className="kpoints-card__field-hint">Switch to Structured to change mode</span>
          )}
        </div>
        
        {/* Structured editor (grayed out when in raw mode) */}
        <div className={`kpoints-card__structured ${useRawEdit ? 'kpoints-card__structured--disabled' : ''}`}>
          {localMode === 'gamma' && (
            <div className="kpoints-card__gamma">
              <p>Gamma point only — no additional parameters needed</p>
            </div>
          )}
          
          {localMode === 'automatic' && (
            <div className="kpoints-card__automatic">
              <div className="kpoints-card__grid-row">
                <div className="kpoints-card__grid-label">Grid:</div>
                <div className="kpoints-card__grid-inputs">
                  {['nk1', 'nk2', 'nk3'].map(field => (
                    <div key={field} className="kpoints-card__input-group">
                      <label>{field}</label>
                      <input
                        type="number"
                        value={localAutomatic[field as keyof typeof localAutomatic]}
                        onChange={(e) => handleAutomaticChange(field, parseInt(e.target.value) || 0)}
                        min={1}
                        disabled={useRawEdit}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="kpoints-card__grid-row">
                <div className="kpoints-card__grid-label">Shift:</div>
                <div className="kpoints-card__grid-inputs">
                  {['sk1', 'sk2', 'sk3'].map(field => (
                    <div key={field} className="kpoints-card__input-group">
                      <label>{field}</label>
                      <input
                        type="number"
                        value={localAutomatic[field as keyof typeof localAutomatic]}
                        onChange={(e) => handleAutomaticChange(field, parseInt(e.target.value) || 0)}
                        min={0}
                        max={1}
                        disabled={useRawEdit}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          
          {isListMode && (
            <div className="kpoints-card__points">
              <div className="kpoints-card__points-header">
                <span>K-points ({localPoints.length}):</span>
                <button
                  type="button"
                  onClick={handleAddPoint}
                  className="kpoints-card__add-btn"
                  disabled={useRawEdit}
                >
                  + Add Point
                </button>
              </div>
              {localPoints.length > 0 && (
                <table className="kpoints-card__table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>x</th>
                      <th>y</th>
                      <th>z</th>
                      <th>w</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {localPoints.map((point, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        {(['x', 'y', 'z', 'w'] as const).map(field => (
                          <td key={field}>
                            <input
                              type="number"
                              step="any"
                              value={point[field]}
                              onChange={(e) => handlePointChange(i, field, parseFloat(e.target.value) || 0)}
                              disabled={useRawEdit}
                            />
                          </td>
                        ))}
                        <td>
                          <button
                            type="button"
                            onClick={() => handleRemovePoint(i)}
                            className="kpoints-card__remove-btn"
                            title="Remove point"
                            disabled={useRawEdit}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
        
        {/* Raw body editor (grayed out when in structured mode) */}
        <div className={`kpoints-card__raw-section ${!useRawEdit ? 'kpoints-card__raw-section--disabled' : ''}`}>
          <div className="kpoints-card__raw-header">
            <span>Raw Body Text:</span>
            <span className="kpoints-card__raw-hint">
              {useRawEdit ? 'Edit the body data below (mode controlled by dropdown above)' : 'Switch to Raw mode to edit'}
            </span>
          </div>
          <textarea
            value={rawBodyText}
            onChange={(e) => handleRawBodyChange(e.target.value)}
            className="kpoints-card__raw-textarea"
            rows={localMode === 'gamma' ? 1 : 4}
            placeholder={localMode === 'gamma' ? '(no body for gamma)' : '8 8 8 0 0 0'}
            disabled={!useRawEdit}
            readOnly={!useRawEdit}
          />
        </div>
        
        {/* Preview of full raw text */}
        <div className="kpoints-card__preview">
          <div className="kpoints-card__preview-label">Preview (full QE card):</div>
          <pre className="kpoints-card__preview-content">{fullRawText}</pre>
        </div>
        
        {/* Warnings */}
        {viewModel?.warnings && viewModel.warnings.length > 0 && (
          <div className="kpoints-card__warnings">
            {viewModel.warnings.map((w, i) => (
              <div key={i} className="kpoints-card__warning">⚠️ {w}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

CommonCardKPoints.displayName = 'CommonCardKPoints';
