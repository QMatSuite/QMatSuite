/**
 * CalculationListPanel - Displays a list of calculations in a project
 */

import { useState, useCallback, useMemo, useEffect, type RefObject } from 'react';
import type { CalculationInfo } from '../../types/qv';
import './CalculationListPanel.css';

interface CalculationListPanelProps {
  calculations: CalculationInfo[] | null;
  isLoading?: boolean;
  selectedId?: string | null;
  onSelect?: (calculation: CalculationInfo) => void;
  onRename?: (calculation: CalculationInfo) => void;
  onDelete?: (calculation: CalculationInfo) => void;
  onRefreshProjectRegistry?: () => void;
  onToggleCollapse?: () => void;
  isCollapsed?: boolean;
  paneRef?: RefObject<{ toggle: () => void; collapse: () => void; expand: () => void }>;
}

export function CalculationListPanel({ 
  calculations, 
  isLoading, 
  selectedId,
  onSelect,
  onRename,
  onDelete,
  onRefreshProjectRegistry,
  onToggleCollapse,
  isCollapsed: externalIsCollapsed,
  paneRef,
}: CalculationListPanelProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Internal collapsed state (persisted in localStorage, can be overridden by prop)
  const [internalIsCollapsed, setInternalIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem('qv-calculations-panel-collapsed') === 'true';
    } catch {
      return false;
    }
  });
  
  const isCollapsed = externalIsCollapsed !== undefined ? externalIsCollapsed : internalIsCollapsed;
  
  // Persist collapsed state
  useEffect(() => {
    if (externalIsCollapsed === undefined) {
      localStorage.setItem('qv-calculations-panel-collapsed', String(internalIsCollapsed));
    }
  }, [internalIsCollapsed, externalIsCollapsed]);
  
  const handleToggleCollapse = useCallback(() => {
    // Sync with ResizablePane if ref is provided
    if (paneRef?.current) {
      paneRef.current.toggle();
    }
    // Also call external handler if provided
    if (onToggleCollapse) {
      onToggleCollapse();
    }
    // Update internal state if no external control
    if (externalIsCollapsed === undefined) {
      setInternalIsCollapsed(prev => !prev);
    }
  }, [onToggleCollapse, paneRef, externalIsCollapsed]);
  
  // Sync collapsed state with ResizablePane width
  useEffect(() => {
    if (paneRef?.current && externalIsCollapsed !== undefined) {
      if (externalIsCollapsed) {
        paneRef.current.collapse();
      } else {
        paneRef.current.expand();
      }
    }
  }, [externalIsCollapsed, paneRef]);
  
  const handleRefresh = useCallback(async () => {
    if (!onRefreshProjectRegistry) return;
    setIsRefreshing(true);
    try {
      await onRefreshProjectRegistry();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefreshProjectRegistry]);
  
  // Get selected calculation for rail view
  const selectedCalculation = useMemo(() => {
    if (!selectedId || !calculations) return null;
    return calculations.find(calc => calc.id === selectedId) || null;
  }, [selectedId, calculations]);
  
  // Generate monogram from calculation name or structure
  const getMonogram = useCallback((calc: CalculationInfo | null): string => {
    if (!calc) return '??';
    // Prefer "Si" for Silicon
    if (calc.structure && calc.structure.toLowerCase().includes('si')) {
      return 'Si';
    }
    // Use first 2 characters of calculation name
    if (calc.name && calc.name.length >= 2) {
      return calc.name.substring(0, 2).toUpperCase();
    }
    // Fallback to structure name
    if (calc.structure && calc.structure.length >= 2) {
      return calc.structure.substring(0, 2).toUpperCase();
    }
    return '??';
  }, []);
  
  // Generate tooltip text for selected calculation
  const getTooltipText = useCallback((calc: CalculationInfo | null): string => {
    if (!calc) return 'No calculation selected';
    const parts = [calc.name];
    if (calc.structure) parts.push(`Structure: ${calc.structure}`);
    if (calc.n_steps) parts.push(`${calc.n_steps} step${calc.n_steps !== 1 ? 's' : ''}`);
    if (calc.mode) parts.push(`Mode: ${calc.mode}`);
    return parts.join(' • ');
  }, []);
  if (isLoading) {
    return (
      <div className="calculation-list-panel calculation-list-panel--loading">
        <div className="loading-spinner" />
        <p>Loading calculations...</p>
      </div>
    );
  }
  
  if (!calculations) {
    return (
      <div className="calculation-list-panel calculation-list-panel--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Calculations Loaded</h3>
          <p>Click "List Calculations" to view calculations in this project.</p>
        </div>
      </div>
    );
  }
  
  if (calculations.length === 0) {
    return (
      <div className="calculation-list-panel calculation-list-panel--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Calculations Found</h3>
          <p>This project doesn't have any calculations yet.</p>
        </div>
      </div>
    );
  }
  
  // Collapsed rail view
  if (isCollapsed) {
    return (
      <div className={`calculation-list-panel calculation-list-panel--collapsed`} data-testid="qv-calculations-view">
        {/* Icon at top */}
        <div className="calculation-list-panel__rail-icon">
          <span className="panel-icon">📊</span>
        </div>
        
        {/* Count badge */}
        {calculations && calculations.length > 0 && (
          <div className="calculation-list-panel__rail-count">
            {calculations.length}
          </div>
        )}
        
        {/* Selected item indicator */}
        {selectedCalculation && (
          <div 
            className="calculation-list-panel__rail-selected"
            title={getTooltipText(selectedCalculation)}
          >
            {getMonogram(selectedCalculation)}
          </div>
        )}
        
        {/* Spacer */}
        <div className="calculation-list-panel__rail-spacer" />
        
        {/* Footer with collapse toggle */}
        <div className="calculation-list-panel__footer">
          <button
            className="calculation-list-panel__collapse-btn"
            onClick={handleToggleCollapse}
            title="Expand calculations"
            aria-label="Expand calculations"
          >
            »
          </button>
        </div>
      </div>
    );
  }
  
  // Expanded view
  return (
    <div className="calculation-list-panel" data-testid="qv-calculations-view">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📊</span>
          All Calculations
        </h2>
        <div className="panel-header__actions">
          {onRefreshProjectRegistry && (
            <button
              className="qv-icon-button qv-icon-button--ghost"
              onClick={handleRefresh}
              disabled={isRefreshing}
              aria-label="Refresh"
              title="Refresh"
            >
              {isRefreshing ? '⟳' : '🔄'}
            </button>
          )}
          <span className="panel-count">{calculations.length} total</span>
        </div>
      </div>
      
      <div className="calculation-list" data-testid="qv-calculations-list">
        {calculations.map((calculation) => (
          <div
            key={calculation.id}
            className={`calculation-item ${selectedId === calculation.id ? 'calculation-item--selected' : ''}`}
            data-testid="qv-calculation-row"
            data-calculation-slug={calculation.slug}
          >
            <button
              className="calculation-item__content"
              onClick={() => onSelect?.(calculation)}
            >
              {/* Header row with title and actions */}
              <div className="calculation-item__header">
                <div className="calculation-item__name">{calculation.name}</div>
                {(onRename || onDelete) && (
                  <div className="calculation-item__actions">
                    {onRename && (
                      <button
                        className="calculation-item__action-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRename(calculation);
                        }}
                        title="Rename calculation"
                      >
                        ✏️
                      </button>
                    )}
                    {onDelete && (
                      <button
                        className="calculation-item__action-btn calculation-item__action-btn--danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(calculation);
                        }}
                        title="Delete calculation"
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                )}
              </div>
              
              <div className="calculation-item__structure">
                Structure: <code>{calculation.structure || 'none'}</code>
              </div>
              
              <div className="calculation-item__details">
                <div className="calculation-item__stat">
                  <span className="stat-value">{calculation.n_steps}</span>
                  <span className="stat-label">steps</span>
                </div>
                <div className="calculation-item__mode">
                  <span className={`mode-badge mode-badge--${calculation.mode}`}>
                    {calculation.mode}
                  </span>
                </div>
              </div>
              
              <div className="calculation-item__steps">
                {calculation.steps.map((step, idx) => (
                  <span key={step.id} className="step-chip">
                    {idx > 0 && <span className="step-arrow">→</span>}
                    <span className="step-type">{step.type}</span>
                  </span>
                ))}
              </div>
              
              <div className="calculation-item__path">
                <code>{calculation.path}</code>
              </div>
            </button>
          </div>
        ))}
      </div>
      
      {/* Footer spacer */}
      <div className="calculation-list-panel__spacer" />
      
      {/* Footer with collapse toggle */}
      <div className="calculation-list-panel__footer">
        <button
          className="calculation-list-panel__collapse-btn"
          onClick={handleToggleCollapse}
          title="Collapse calculations"
          aria-label="Collapse calculations"
        >
          «
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// Calculation Detail View
// =============================================================================

import type { StructureInfo, CalculationDetailResult, StepPresetFootprint } from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import { useQVClient } from '../../hooks/useQVClient';
import { CommonCardPseudo } from '../common_cards/CommonCardPseudo';
import { PresetSection } from '../presets/PresetSection';
import { usePresets } from '../../hooks/usePresets';

/**
 * FootprintChips - Displays preset-related params as chips (Phase 8C)
 * 
 * Shows at most maxChips chips, with "+k more" expander if more exist.
 * Click on "+k more" expands to show all chips.
 */
interface FootprintChipsProps {
  footprint: StepPresetFootprint;
  maxChips?: number;
}

/**
 * Format a footprint parameter for display.
 * Makes chips more readable (e.g., "K 6×6×6" instead of "kmesh=6×6×6").
 */
function formatFootprintChip(key: string, value: unknown): string {
  const strValue = String(value);
  
  // Special formatting for common parameters
  if (key === 'kmesh' || key === 'K_POINTS') {
    // kmesh is already formatted as "6×6×6"
    return `K ${strValue}`;
  }
  
  if (key === 'ecutwfc' || key === 'ecutrho') {
    // Round to integer for display
    const num = typeof value === 'number' ? value : parseFloat(strValue);
    if (!isNaN(num)) {
      return `${key.replace('ecut', '')} ${Math.round(num)}`;
    }
  }
  
  if (key === 'conv_thr') {
    // Format scientific notation more compactly
    const num = typeof value === 'number' ? value : parseFloat(strValue);
    if (!isNaN(num) && num < 1) {
      const exp = Math.floor(Math.log10(num));
      return `conv 1e${exp}`;
    }
  }
  
  if (key === 'nspin') {
    return `nspin ${strValue}`;
  }
  
  if (key === 'occupations') {
    return `occ ${strValue}`;
  }
  
  // Default: key=value
  return `${key}=${strValue}`;
}

function FootprintChips({ footprint, maxChips = 3 }: FootprintChipsProps) {
  const [expanded, setExpanded] = useState(false);
  
  const entries = Object.entries(footprint.params);
  const totalCount = entries.length;
  
  if (totalCount === 0) return null;
  
  const visibleEntries = expanded ? entries : entries.slice(0, maxChips);
  const hiddenCount = totalCount - maxChips;
  const showMore = !expanded && hiddenCount > 0;
  
  return (
    <div className="step-footprint">
      {visibleEntries.map(([key, value]) => {
        const displayText = formatFootprintChip(key, value);
        const fullText = `${key}=${String(value)}`;
        return (
          <span 
            key={key} 
            className="step-footprint__chip" 
            title={fullText}
          >
            {displayText}
          </span>
        );
      })}
      {showMore && (
        <button
          className="step-footprint__more"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(true);
          }}
          title={`Show ${hiddenCount} more parameter${hiddenCount > 1 ? 's' : ''}`}
        >
          +{hiddenCount}
        </button>
      )}
      {expanded && hiddenCount > 0 && (
        <button
          className="step-footprint__collapse"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(false);
          }}
          title="Show fewer"
        >
          ◂
        </button>
      )}
    </div>
  );
}

interface CalculationDetailPanelProps {
  calculationSummary: CalculationInfo | null;  // Summary from list_calculations (for high-level fields)
  calculationDetail: CalculationDetailResult | null;  // Detail from get_calculation_detail (canonical steps array)
  projectRoot: string;
  structures?: StructureInfo[];
  onClose?: () => void;
  onRunCalculation?: (calculation: CalculationInfo) => void;
  onSelectStep?: (stepId: string) => void;
  onDeleteStep?: (stepId: string) => void;  // Callback when step is deleted
  onGoToJobs?: () => void;
  onCalculationUpdated?: () => void;
  onCalculationDetailUpdated?: (detail: CalculationDetailResult) => void;  // Callback to update calculationDetail directly
  isFocusMode?: boolean;  // If true, hide large buttons (they're shown in compact step list instead)
}

export function CalculationDetailPanel({ 
  calculationSummary,
  calculationDetail,
  projectRoot,
  structures,
  onClose,
  onRunCalculation,
  onSelectStep,
  onDeleteStep,
  onGoToJobs: _onGoToJobs,
  onCalculationUpdated,
  onCalculationDetailUpdated,
  isFocusMode = false,
}: CalculationDetailPanelProps) {
  // IMPORTANT: When calculationDetail is available, we MUST use its steps array
  // as the canonical source of step order, since it is built from calculation.yaml.
  // Fall back to summary only if detail is still loading.
  const calculationForSteps = calculationDetail ?? calculationSummary;
  // Both CalculationInfo and CalculationDetailResult have compatible fields (id, name, slug, structure, mode, n_steps)
  const calculation = calculationForSteps as CalculationInfo | null;
  
  const [isReordering, setIsReordering] = useState(false);
  const [stepOrder, setStepOrder] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Add step state
  const [showAddStep, setShowAddStep] = useState(false);
  const [newStepType, setNewStepType] = useState('');
  const [newStepName, setNewStepName] = useState('');
  const [isAddingStep, setIsAddingStep] = useState(false);
  
  // Import step state
  const [isImportingStep, setIsImportingStep] = useState(false);
  
  // Delete step state
  const [isDeletingStep, setIsDeletingStep] = useState(false);
  
  // Pseudopotential mapping state (calculation-level)
  const qv = useQVClient();
  
  // Local structures state (fallback if not provided via props)
  const [localStructures, setLocalStructures] = useState<StructureInfo[] | null>(null);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  
  // Use provided structures or local state
  const effectiveStructures = structures ?? localStructures ?? [];
  
  // Fetch structures if not provided and project is loaded
  useEffect(() => {
    if (!structures && projectRoot && calculation) {
      setIsLoadingStructures(true);
      qv.listStructures(projectRoot)
        .then(response => {
          if (response.ok && response.data) {
            setLocalStructures(response.data.structures);
          }
        })
        .finally(() => setIsLoadingStructures(false));
    }
  }, [structures, projectRoot, calculation, qv]);
  
  const [pseudoMapping, setPseudoMapping] = useState<{
    species: string[];
    mapping: Record<string, string>;
    pseudo_dir: string;
    available_pseudos: string[];
    warnings: string[];
    sssp_defaults?: Record<string, { precision: string; efficiency: string }>;
    sssp_installed?: { precision: boolean; efficiency: boolean };
    installed_sources?: {
      internal: boolean;
      sssp_precision: boolean;
      sssp_efficiency: boolean;
    };
    resolved_by_element?: Record<string, {
      filename: string;
      source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project' | null;
      resolved: boolean;
      in_project?: boolean;
    }>;
  } | null>(null);
  const [_isLoadingPseudoMapping, setIsLoadingPseudoMapping] = useState(false);
  const [isEditingPseudos, setIsEditingPseudos] = useState(false);
  
  // Get preset footprints for step rows
  const { footprints: stepFootprints } = usePresets(
    !isFocusMode ? projectRoot : null,
    !isFocusMode && calculationForSteps ? calculationForSteps.slug : null
  );
  
  // Handle deleting a step
  const handleDeleteStep = useCallback(async (stepId: string, stepType: string) => {
    if (!window.qv || !calculationForSteps || isDeletingStep) return;
    
    // Show confirmation dialog
    const confirmed = window.confirm(
      `Delete step "${stepType}" (${stepId.substring(0, 8)}...) from calculation "${calculationForSteps.name}"?\n\n` +
      `This will move the step file to the project's trash folder. It cannot be undone from the GUI.`
    );
    
    if (!confirmed) return;
    
    setIsDeletingStep(true);
    setError(null);
    
    try {
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }
      
      const response = await window.qv.request('delete_step', {
        project_root: normalizedProjectRoot,
        calculation: calculationForSteps.slug,
        step: stepId, // ULID from calculation.yaml
      });
      
      if (response.ok) {
        // Step deleted successfully
        // Clear selection if the deleted step was selected
        if (onDeleteStep) {
          onDeleteStep(stepId);
        }
        // Refresh calculation detail to show updated steps list
        await onCalculationUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to delete step');
        // Still refresh calculation detail to avoid stale entries
        await onCalculationUpdated?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      // Still refresh calculation detail to avoid stale entries
      await onCalculationUpdated?.();
    } finally {
      setIsDeletingStep(false);
    }
  }, [calculationForSteps, projectRoot, isDeletingStep, onDeleteStep, onCalculationUpdated]);
  
  // Handle showing add step form
  const handleShowAddStep = useCallback(() => {
    setShowAddStep(true);
    setNewStepType('');
    setNewStepName('');
    setError(null);
  }, []);
  
  // Handle adding a new step
  const handleAddStep = useCallback(async () => {
    if (!window.qv || !calculationForSteps || !newStepType) return;
    
    setIsAddingStep(true);
    setError(null);
    
    try {
      const stepName = newStepName.trim() || newStepType;
      
      const response = await window.qv.request<CalculationDetailResult>('add_step_to_calculation', {
        project_root: projectRoot,
        calculation: calculationForSteps.slug,
        step_type: newStepType,
        step_name: stepName,
      });
      
      if (response.ok && response.data) {
        setShowAddStep(false);
        setNewStepType('');
        setNewStepName('');
        // CRITICAL: Wait for calculation detail to refresh before allowing step selection.
        // This ensures the new step is available in the calculation.steps list before
        // the user can click it, preventing "Step not found" errors from race conditions.
        // The onCalculationUpdated callback will trigger a refetch of calculation detail.
        // We also update the local calculation prop optimistically with the returned data
        // to ensure the new step appears immediately in the UI.
        await onCalculationUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to add step');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsAddingStep(false);
    }
  }, [calculation, projectRoot, newStepType, newStepName, onCalculationUpdated]);
  
  // Handle importing QE input as step
  const handleImportStep = useCallback(async () => {
    if (!window.qv || !calculationForSteps) return;
    
    // Use window.qv.openFile to pick file
    const inputFile = await window.qv.openFile({
      title: 'Import QE Input File',
      filters: [
        { name: 'QE Input Files', extensions: ['in'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    
    if (!inputFile) {
      return; // User cancelled
    }
    
    setIsImportingStep(true);
    setError(null);
    
    try {
      const response = await window.qv.request<CalculationDetailResult>('import_step_from_qe_input', {
        project_root: projectRoot,
        calculation: calculationForSteps.slug,
        input_file: inputFile,
      });
      
      if (response.ok) {
        onCalculationUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to import step');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsImportingStep(false);
    }
  }, [calculation, projectRoot, onCalculationUpdated]);
  
  // Drag-and-drop state
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  
  // Handle step reorder - move step up
  const handleMoveUp = useCallback((index: number) => {
    if (index === 0) return;
    setStepOrder(prev => {
      const newOrder = [...prev];
      [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
      return newOrder;
    });
  }, []);
  
  // Handle step reorder - move step down
  const handleMoveDown = useCallback((index: number, total: number) => {
    if (index >= total - 1) return;
    setStepOrder(prev => {
      const newOrder = [...prev];
      [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
      return newOrder;
    });
  }, []);
  
  // Drag-and-drop handlers
  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index.toString());
    // Make the dragged element semi-transparent
    const target = e.target as HTMLElement;
    target.style.opacity = '0.5';
  }, []);
  
  const handleDragEnd = useCallback((e: React.DragEvent) => {
    setDraggedIndex(null);
    setDragOverIndex(null);
    const target = e.target as HTMLElement;
    target.style.opacity = '1';
  }, []);
  
  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  }, []);
  
  const handleDragLeave = useCallback(() => {
    setDragOverIndex(null);
  }, []);
  
  const handleDrop = useCallback((e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    const dragIndex = draggedIndex;
    
    if (dragIndex === null || dragIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    
    setStepOrder(prev => {
      const newOrder = [...prev];
      const [removed] = newOrder.splice(dragIndex, 1);
      newOrder.splice(dropIndex, 0, removed);
      return newOrder;
    });
    
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, [draggedIndex]);
  
  // Start reorder mode
  const handleStartReorder = useCallback(() => {
    if (!calculation) return;
    setStepOrder(calculation.steps.map(s => s.id));
    setIsReordering(true);
    setError(null);
  }, [calculation]);
  
  // Cancel reorder
  const handleCancelReorder = useCallback(() => {
    setIsReordering(false);
    setStepOrder([]);
  }, []);
  
  // Save reorder
  const handleSaveReorder = useCallback(async () => {
    if (!window.qv || !calculationForSteps) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      // new_order must be array of step ULIDs (from step.id) in the desired order
      const response = await window.qv.request<CalculationDetailResult>('reorder_calculation_steps', {
        project_root: projectRoot,
        calculation: calculationForSteps.slug, // calculation selector: slug
        new_order: stepOrder, // array of step ULIDs (from step.id)
      });
      
      if (response.ok) {
        setIsReordering(false);
        setStepOrder([]);
        // CRITICAL: Use the returned calculation detail to update UI immediately
        // This ensures the UI reflects the new step order from calculation.yaml
        // The response.data contains the CalculationDetailResult with updated step order
        if (response.data && onCalculationDetailUpdated) {
          onCalculationDetailUpdated(response.data);
        }
        // Also call the general update callback for any other side effects
        onCalculationUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to reorder steps');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [calculation, projectRoot, stepOrder, onCalculationUpdated]);
  
  // Handle structure change
  const handleStructureChange = useCallback(async (newStructure: string) => {
    if (!window.qv || !calculationForSteps) return;
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response = await window.qv.request<CalculationDetailResult>('change_calculation_structure', {
        project_root: projectRoot,
        calculation: calculationForSteps.slug,
        new_structure: newStructure,
        update_steps: true,
      });
      
      if (response.ok) {
        onCalculationUpdated?.();
      } else {
        setError(response.error?.message || 'Failed to change structure');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsSaving(false);
    }
  }, [calculationForSteps, projectRoot, onCalculationUpdated]);
  
  // Fetch pseudopotential mapping when calculation changes
  useEffect(() => {
    if (!calculationForSteps || !projectRoot) {
      setPseudoMapping(null);
      return;
    }
    
    setIsLoadingPseudoMapping(true);
    qv.getCalculationPseudoMapping(projectRoot, calculationForSteps.slug)
      .then(response => {
        if (response.ok && response.data) {
          setPseudoMapping(response.data);
        } else {
          setPseudoMapping(null);
        }
      })
      .catch(err => {
        console.error('[CalculationDetailPanel] Failed to load pseudo mapping', err);
        setPseudoMapping(null);
      })
      .finally(() => {
        setIsLoadingPseudoMapping(false);
      });
  }, [calculationForSteps?.slug, projectRoot, qv]);
  
  // CRITICAL: Use calculationDetail.steps if available (canonical from calculation.yaml),
  // otherwise fall back to calculationSummary.steps (may have wrong order, but better than nothing)
  // The steps array from get_calculation_detail is the canonical source of step order and IDs.
  // Each step.id is a ULID (26 chars) that must be used as the step selector for RPC calls.
  const baseSteps = calculationDetail?.steps ?? calculationSummary?.steps ?? [];
  
  // When reordering, reorder baseSteps according to stepOrder
  // NOTE: This useMemo must be called unconditionally (before any early returns)
  // to satisfy React hooks rules
  const displaySteps = useMemo(() => {
    if (!isReordering || stepOrder.length === 0 || stepOrder.length !== baseSteps.length) {
      return baseSteps;
    }
    // Create a map of step ID to step object
    const stepMap = new Map(baseSteps.map(s => [s.id, s]));
    // Reorder according to stepOrder
    return stepOrder.map(id => stepMap.get(id)).filter((s): s is NonNullable<typeof s> => s !== undefined);
  }, [isReordering, stepOrder, baseSteps]);
  
  // Early returns AFTER all hooks have been called
  if (!calculationForSteps) {
    // Show loading state if we have summary but detail is still loading
    if (calculationSummary && !calculationDetail) {
      return (
        <div className="calculation-detail-panel" data-testid="qv-calculation-detail">
          <div className="panel-header">
            <h2 className="panel-title">Loading calculation details...</h2>
          </div>
        </div>
      );
    }
    return null;
  }
  
  // Early return if no calculation data
  if (!calculation) {
    return (
      <div className="calculation-detail-panel">
        <div className="panel-placeholder">
          <span className="panel-icon">📊</span>
          <h3>No Calculation Selected</h3>
          <p>Select a calculation to view its details.</p>
        </div>
      </div>
    );
  }
  
  // INSTRUMENTATION: Log steps to verify order matches calculation.yaml
  console.log('[CalculationDetailPanel] displaySteps', {
    calculationSlug: calculationForSteps.slug,
    hasDetail: !!calculationDetail,
    hasSummary: !!calculationSummary,
    stepCount: displaySteps.length,
    steps: displaySteps.map((s, i) => ({
      index: i,
      id: s.id,
      type: s.type,
      idLength: s.id?.length ?? 0,
    })),
  });

  return (
    <div className="calculation-detail-panel" data-testid="qv-calculation-detail">
      <div className="panel-header">
        <div className="qv-calc-header-title-group">
          {/* Breadcrumb: All Calculations → Selected Calculation */}
          <div className="qv-calc-breadcrumb" style={{ fontSize: '0.85em', color: '#888', marginBottom: '4px' }}>
            All Calculations → {calculation.name}
          </div>
          <h2 className="panel-title">
            <span className="panel-icon">📊</span>
            {calculation.name}
          </h2>
          <div className="qv-calc-header-subtitle">
            Calculation: <code style={{ fontSize: '0.85em', marginLeft: '0.25em' }}>{calculation.id}</code>
          </div>
        </div>
        <div className="panel-header-actions">
          {onRunCalculation && (
            <button 
              className="qv-button qv-button--primary qv-button--large"
              onClick={() => onRunCalculation(calculation)}
              disabled={isReordering || isSaving}
              title="Run all steps in this calculation"
              data-testid="qv-btn-run-calculation"
            >
              <span className="qv-button-icon-left">▶️</span>
              <span>Run Calculation</span>
            </button>
          )}
          {onClose && (
            <button className="panel-close" onClick={onClose}>×</button>
          )}
        </div>
      </div>
      
      <div className="panel-content">
        {/* Error banner */}
        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
            <button className="error-dismiss" onClick={() => setError(null)}>×</button>
          </div>
        )}
        
        <div className="detail-section">
          {/* MetaForm: 2×2 form layout with aligned value column */}
          <div className="meta-form">
            {/* Row 1: Structure */}
            <div className="meta-form__label">Structure:</div>
            <div className="meta-form__value meta-form__value--structure">
              {isLoadingStructures ? (
                <span className="detail-value">Loading...</span>
              ) : effectiveStructures.length > 0 ? (
                <select
                  className="structure-selector meta-form__structure-select"
                  value={
                    calculation.structure 
                      ? (effectiveStructures.find(s => s.name === calculation.structure)?.slug || '')
                      : ''
                  }
                  onChange={(e) => handleStructureChange(e.target.value)}
                  disabled={isSaving}
                >
                  <option value="">-- None --</option>
                  {effectiveStructures.map(s => (
                    <option key={s.id} value={s.slug}>{s.name} ({s.formula})</option>
                  ))}
                </select>
              ) : (
                <code className="detail-value">{calculation.structure || 'None'}</code>
              )}
            </div>
            {/* Row 2: Pseudopotentials */}
            <div className="meta-form__label">Pseudopotentials:</div>
            <div className="meta-form__value meta-form__value--pseudo">
              {_isLoadingPseudoMapping ? (
                <span className="detail-value">Loading...</span>
              ) : pseudoMapping && pseudoMapping.species.length > 0 ? (
                <div className="meta-form__pseudo-container">
                  <div className="pseudo-list">
                    {pseudoMapping.species.map((species) => {
                      const pseudo = pseudoMapping.mapping[species] || '—';
                      return (
                        <div key={species} className="pseudo-list__item">
                          {species}: {pseudo !== '—' ? pseudo : 'Missing'}
                        </div>
                      );
                    })}
                  </div>
                  {!isFocusMode && (
                    <button
                      className="meta-form__edit-btn"
                      onClick={() => setIsEditingPseudos(true)}
                      title="Edit pseudopotential mappings"
                    >
                      ✏️ Edit
                    </button>
                  )}
                </div>
              ) : (
                <span className="detail-value">No pseudopotentials mapping</span>
              )}
            </div>
          </div>
        </div>
        
        {/* Presets Section - Per Constitution §10.4.1: Detector B is sole state source */}
        {calculationForSteps && projectRoot && !isFocusMode && (
          <PresetSection
            projectRoot={projectRoot}
            calculationSlug={calculationForSteps.slug}
            onPresetsChanged={onCalculationUpdated}
          />
        )}
        
        <div className="detail-section">
          <div className="section-header-row">
            <h3>Calculation Steps</h3>
            {/* Hide large buttons in focus mode (they're shown in compact step list) */}
            {!isFocusMode && (
              <div className="section-actions">
                {!isReordering ? (
                  <>
                    <button 
                      className="section-action-btn section-action-btn--add"
                      onClick={handleShowAddStep}
                      title="Add a new step to this calculation"
                      data-testid="qv-add-step-btn"
                    >
                      ➕ Add Step
                    </button>
                    <button 
                      className="section-action-btn"
                      onClick={handleImportStep}
                      disabled={isImportingStep}
                      title="Import QE input file as step (preserves original parameters)"
                      data-testid="qv-import-step-btn"
                    >
                      {isImportingStep ? 'Importing...' : '📥 Import QE Input'}
                    </button>
                    <button 
                      className="section-action-btn"
                      onClick={handleStartReorder}
                      disabled={calculation.n_steps < 2}
                      title="Reorder steps"
                    >
                      ↕️ Reorder
                    </button>
                  </>
                ) : (
                  <>
                    <button 
                      className="section-action-btn section-action-btn--secondary"
                      onClick={handleCancelReorder}
                      disabled={isSaving}
                    >
                      Cancel
                    </button>
                    <button 
                      className="section-action-btn section-action-btn--primary"
                      onClick={handleSaveReorder}
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving...' : 'Save Order'}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
          
          {/* Add Step Form - positioned right after the Add Step button for better UX */}
          {showAddStep && (
            <div className="add-step-form" data-testid="qv-add-step-form">
              <div className="add-step-header">
                <h4>Add New Step</h4>
                <button 
                  className="add-step-close"
                  onClick={() => setShowAddStep(false)}
                  title="Cancel adding step"
                >×</button>
              </div>
              <div className="add-step-content">
                <div className="form-group">
                  <label htmlFor="step-type">Step Type</label>
                  <select
                    id="step-type"
                    value={newStepType}
                    onChange={(e) => setNewStepType(e.target.value)}
                    autoFocus
                  >
                    <option value="">-- Select Type --</option>
                    <option value="scf">SCF (pw.x)</option>
                    <option value="nscf">NSCF (pw.x)</option>
                    <option value="relax">Relax (pw.x)</option>
                    <option value="vc-relax">VC-Relax (pw.x)</option>
                    <option value="bands_pw">Bands PW (pw.x)</option>
                    <option value="bands">Bands PP (bands.x)</option>
                    <option value="dos">DOS (dos.x)</option>
                    <option value="projwfc">PDOS (projwfc.x)</option>
                    <option value="ph">Phonon (ph.x)</option>
                    <option value="pp">Post-Process (pp.x)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="step-name">Step Name (optional)</label>
                  <input
                    id="step-name"
                    type="text"
                    placeholder={newStepType || 'step name'}
                    value={newStepName}
                    onChange={(e) => setNewStepName(e.target.value)}
                  />
                </div>
                <div className="add-step-actions">
                  <button
                    className="add-step-btn add-step-btn--cancel"
                    onClick={() => setShowAddStep(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="add-step-btn add-step-btn--confirm"
                    onClick={handleAddStep}
                    disabled={!newStepType || isAddingStep}
                    data-testid="qv-confirm-add-step"
                  >
                    {isAddingStep ? 'Adding...' : 'Add Step'}
                  </button>
                </div>
              </div>
            </div>
          )}
          
          <div className="steps-list" data-testid="qv-steps-list">
            {displaySteps.map((step, idx) => (
              <div 
                key={step.id} 
                className={`step-item-container ${
                  isReordering ? 'step-item-container--reordering' : ''
                } ${
                  draggedIndex === idx ? 'step-item-container--dragging' : ''
                } ${
                  dragOverIndex === idx ? 'step-item-container--drag-over' : ''
                }`}
                draggable={isReordering && !isSaving}
                onDragStart={isReordering ? (e) => handleDragStart(e, idx) : undefined}
                onDragEnd={isReordering ? handleDragEnd : undefined}
                onDragOver={isReordering ? (e) => handleDragOver(e, idx) : undefined}
                onDragLeave={isReordering ? handleDragLeave : undefined}
                onDrop={isReordering ? (e) => handleDrop(e, idx) : undefined}
                data-testid={`qv-step-row-${step.id}`}
                data-step-id={step.id}
              >
                {isReordering && (
                  <div className="step-reorder-controls">
                    <span className="drag-handle" title="Drag to reorder">⋮⋮</span>
                    <button
                      className="reorder-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMoveUp(idx);
                      }}
                      disabled={idx === 0 || isSaving}
                      title="Move up"
                    >
                      ↑
                    </button>
                    <button
                      className="reorder-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMoveDown(idx, displaySteps.length);
                      }}
                      disabled={idx >= displaySteps.length - 1 || isSaving}
                      title="Move down"
                    >
                      ↓
                    </button>
                  </div>
                )}
                <button 
                  className="step-item"
                  onClick={() => {
                    if (!isReordering) {
                      // CRITICAL: step.id is ULID from backend (get_calculation_detail returns step.id from calculation.yaml)
                      // This is the ONLY correct selector for get_step_detail RPC
                      // We MUST use step.id directly, NOT derived from index or any other source
                      console.log('[CalculationDetailPanel] step clicked', {
                        calculationSlug: calculationForSteps.slug,
                        stepIndex: idx,
                        stepId: step.id,
                        stepType: step.type,
                      });
                      // CRITICAL: Pass step.id (ULID) directly to onSelectStep
                      // This will be stored as selectedStepId in App.tsx and passed to StepDetailPanel
                      onSelectStep?.(step.id);
                    }
                  }}
                  disabled={isReordering}
                  data-testid={`qv-step-button-${step.id}`}
                >
                  <span className="step-number">{idx + 1}</span>
                  <div className="step-info">
                    {/* step.id is ULID (26 chars) from backend - used as step selector */}
                    <span className="step-id">{step.id}</span>
                    <span className="step-type-badge">{step.type}</span>
                  </div>
                  {/* Preset footprint chips - WYSIWYG from step.yml (Phase 8C: limit to 3) */}
                  {stepFootprints && stepFootprints[step.step_file] && (
                    <FootprintChips footprint={stepFootprints[step.step_file]} maxChips={3} />
                  )}
                </button>
                {!isReordering && onDeleteStep && (
                  <button
                    className="step-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteStep(step.id, step.type);
                    }}
                    disabled={isDeletingStep}
                    title={`Delete step "${step.type}"`}
                    data-testid={`qv-delete-step-${step.id}`}
                  >
                    🗑️
                  </button>
                )}
              </div>
            ))}
          </div>
            </div>
            
            {/* Hide reveal button in focus mode (it's shown in StepDetailPanel footer) */}
            {!isFocusMode && (
              <div className="detail-section">
                <h3>File Location</h3>
                <div className="file-location">
                  <code className="file-location__path" title={calculation.absolute_path}>
                    {calculation.absolute_path}
                  </code>
                  <button 
                    className="file-location__reveal-btn"
                    onClick={() => window.qv?.revealPath?.(calculation.absolute_path)}
                    title="Reveal in Finder"
                  >
                    📂 Reveal
                  </button>
                </div>
              </div>
            )}
      </div>
      
      {/* Edit Pseudopotentials Modal */}
      {isEditingPseudos && pseudoMapping && (
        <div className="pseudo-edit-modal-overlay" onClick={() => setIsEditingPseudos(false)}>
          <div className="pseudo-edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pseudo-edit-modal-header">
              <h3>Edit Pseudopotentials</h3>
              <button
                className="pseudo-edit-modal-close"
                onClick={() => setIsEditingPseudos(false)}
                title="Close"
              >
                ×
              </button>
            </div>
            <div className="pseudo-edit-modal-content">
              <CommonCardPseudo
                mapping={pseudoMapping}
                isEditing={true}
                projectRoot={projectRoot}
                calculation={calculationForSteps?.slug}
                onUpdate={async (mapping, _libraryPreference, sha256Map, shaFamilyMap) => {
                  if (!calculationForSteps || !projectRoot) return;
                  
                  // Convert to species_map format with sha256 pinning
                  const speciesMap: Record<string, { 
                    pseudopot?: string; 
                    pseudo_sha256?: string;
                    pseudo_sha_family?: string;
                    pseudo_basename?: string;
                    mass?: number;
                  }> = {};
                  for (const [element, pseudo] of Object.entries(mapping)) {
                    const entry: any = { pseudopot: pseudo }; // Legacy field for backward compat
                    if (sha256Map?.[element]) {
                      entry.pseudo_sha256 = sha256Map[element];
                      entry.pseudo_basename = pseudo; // Use basename from mapping
                    }
                    if (shaFamilyMap?.[element]) {
                      entry.pseudo_sha_family = shaFamilyMap[element];
                    }
                    speciesMap[element] = entry;
                  }
                  
                  const response = await qv.updateCalculationSpeciesMap(
                    projectRoot,
                    calculationForSteps.slug,
                    speciesMap
                  );
                  
                  if (response.ok && response.data) {
                    // Refresh pseudo mapping
                    const mappingResponse = await qv.getCalculationPseudoMapping(
                      projectRoot,
                      calculationForSteps.slug
                    );
                    if (mappingResponse.ok && mappingResponse.data) {
                      setPseudoMapping(mappingResponse.data);
                    }
                    onCalculationUpdated?.();
                    setIsEditingPseudos(false);
                  } else {
                    setError(response.error?.message || 'Failed to update pseudopotential mapping');
                  }
                }}
                onImportFiles={async (files) => {
                  if (!projectRoot) return;
                  
                  const filePaths: string[] = [];
                  for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    const filePath = (file as unknown as { path: string }).path;
                    if (filePath) {
                      filePaths.push(filePath);
                    }
                  }
                  
                  if (filePaths.length === 0) {
                    setError('No valid file paths found');
                    return;
                  }
                  
                  const response = await qv.importPseudoFiles(projectRoot, filePaths);
                  if (response.ok && response.data) {
                    if (response.data.errors && response.data.errors.length > 0) {
                      setError(response.data.errors.join(', '));
                    }
                  } else {
                    setError(response.error?.message || 'Failed to import pseudopotential files');
                  }
                }}
                onRefresh={async () => {
                  if (!projectRoot || !calculationForSteps) return;
                  const mappingResponse = await qv.getCalculationPseudoMapping(
                    projectRoot,
                    calculationForSteps.slug
                  );
                  if (mappingResponse.ok && mappingResponse.data) {
                    setPseudoMapping(mappingResponse.data);
                  }
                }}
                onSearchLegacy={async (element: string) => {
                  if (!projectRoot) {
                    return { candidates: [], errors: ['No project root'] };
                  }
                  const response = await qv.searchLegacyPseudos(element, projectRoot);
                  if (response.ok && response.data) {
                    return response.data;
                  }
                  return { candidates: [], errors: [response.error?.message || 'Search failed'] };
                }}
                onDownloadByFilename={async (filename: string) => {
                  if (!projectRoot) {
                    return { filename: '', renamed: false, skipped: false, errors: ['No project root'] };
                  }
                  const response = await qv.downloadPseudoByFilename(projectRoot, filename);
                  if (response.ok && response.data) {
                    return response.data;
                  }
                  return { filename: '', renamed: false, skipped: false, errors: [response.error?.message || 'Download failed'] };
                }}
                onDownloadCandidate={async (candidate) => {
                  if (!projectRoot) {
                    return { filename: '', renamed: false, skipped: false, errors: ['No project root'] };
                  }
                  const response = await qv.downloadPseudoCandidate(projectRoot, candidate);
                  if (response.ok && response.data) {
                    return response.data;
                  }
                  return { filename: '', renamed: false, skipped: false, errors: [response.error?.message || 'Download failed'] };
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

