/**
 * PresetSection - Displays and allows editing of calculation presets.
 * 
 * Per Constitution Chapter 10:
 * - §10.4.1: Detector B is the sole legitimate state source (UI shows detected state)
 * - §10.3.3: Applying a preset BROADCASTS to applicable steps (overwrite, not merge)
 * - Presets are runtime-only interpretations
 * 
 * Per UI requirements:
 * - UI must not hardcode dimensions, options, or labels
 * - All rendering is driven by preset catalog from backend
 * - Scope information comes from variant applies_to_step_types
 */

import { useCallback, useState, useMemo } from 'react';
import { usePresets, ApplyResult } from '../../hooks/usePresets';
import { usePresetCatalog, PresetCatalogDimension } from '../../hooks/usePresetCatalog';
import type { WorkflowType } from '../../types/qms';
import './PresetSection.css';

interface PresetSectionProps {
  projectRoot: string;
  calculationSlug: string;
  /** Called when presets change (to refresh calculation detail) */
  onPresetsChanged?: () => void;
}

interface PresetDimensionRowProps {
  dimension: PresetCatalogDimension;
  value: string | 'Custom' | undefined;
  isCustom: boolean;
  isApplying: boolean;
  onChange: (value: string) => void;
  customTooltip?: string;
}

/**
 * Individual preset dimension row with dropdown
 */
function PresetDimensionRow({
  dimension,
  value,
  isCustom,
  isApplying,
  onChange,
  customTooltip,
}: PresetDimensionRowProps) {
  const handleChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange(e.target.value);
  }, [onChange]);
  
  // Render scope information - compact summary with detailed tooltip
  const { scopeText, scopeTooltip } = useMemo(() => {
    if (dimension.scope.type === 'variant_step_types') {
      const stepTypes = dimension.scope.step_types || [];
      if (stepTypes.length === 0) {
        return { scopeText: 'No applicable steps', scopeTooltip: 'No applicable steps' };
      }
      // Compact summary: show count
      const count = stepTypes.length;
      return {
        scopeText: `${count} step type${count !== 1 ? 's' : ''}`,
        scopeTooltip: `Applies to: ${stepTypes.join(', ')}`,
      };
    } else if (dimension.scope.type === 'variants') {
      const variants = dimension.scope.variants || [];
      if (variants.length === 0) {
        return { scopeText: 'No applicable steps', scopeTooltip: 'No applicable steps' };
      }
      // For precision, show variant count + details in tooltip
      const stepTypesSet = new Set<string>();
      variants.forEach(v => v.step_types.forEach(st => stepTypesSet.add(st)));
      const stepTypes = Array.from(stepTypesSet).sort();
      const count = stepTypes.length;
      return {
        scopeText: `${count} step type${count !== 1 ? 's' : ''}`,
        scopeTooltip: `Applies to: ${stepTypes.join(', ')}`,
      };
    }
    return { scopeText: 'Applicable steps', scopeTooltip: 'Applies to applicable steps' };
  }, [dimension.scope]);
  
  return (
    <div className="preset-dimension-row" title={dimension.description}>
      <span className="preset-dimension-row__label">{dimension.label}</span>
      <div className="preset-dimension-row__value-container">
        {isCustom ? (
          <>
            <span 
              className="preset-dimension-row__custom-badge"
              title={customTooltip || "Steps have different values for this preset. Check step rows for details."}
            >
              Custom
            </span>
            <select
              className="preset-dimension-row__select preset-dimension-row__select--custom"
              value=""
              onChange={handleChange}
              disabled={isApplying}
              title="Apply preset to applicable steps"
            >
              <option value="" disabled>Apply...</option>
              {dimension.options.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </>
        ) : (
          <select
            className="preset-dimension-row__select"
            value={value || ''}
            onChange={handleChange}
            disabled={isApplying}
          >
            {dimension.options.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
            <option value="Custom" disabled>Custom</option>
          </select>
        )}
      </div>
      <div className="preset-dimension-row__scope" title={scopeTooltip}>
        <small>{scopeText}</small>
      </div>
    </div>
  );
}

/** Toast component for apply feedback (Phase 8B) */
interface ApplyToastProps {
  result: ApplyResult
  onClose: () => void;
  onShowDetails: () => void;
}

function ApplyToast({ result, onClose, onShowDetails }: ApplyToastProps) {
  const isSuccess = result.success;
  
  return (
    <div className={`apply-toast ${isSuccess ? 'apply-toast--success' : 'apply-toast--error'}`}>
      <div className="apply-toast__content">
        {isSuccess ? (
          <>
            <span className="apply-toast__icon">✓</span>
            <span className="apply-toast__message">
              Applied {result.dimension}={result.value}: {result.stepsUpdated} updated, {result.stepsSkipped} skipped
            </span>
          </>
        ) : (
          <>
            <span className="apply-toast__icon">✗</span>
            <span className="apply-toast__message">
              Failed to apply {result.dimension}: {result.error}
            </span>
          </>
        )}
      </div>
      <div className="apply-toast__actions">
        {isSuccess && result.stepResults.length > 0 && (
          <button
            className="apply-toast__details-btn"
            onClick={onShowDetails}
            title="Show detailed results per step"
          >
            Details
          </button>
        )}
        <button className="apply-toast__close-btn" onClick={onClose}>×</button>
      </div>
    </div>
  );
}

/** Modal for detailed apply results (Phase 8B) */
interface ApplyDetailsModalProps {
  result: ApplyResult;
  onClose: () => void;
}

function ApplyDetailsModal({ result, onClose }: ApplyDetailsModalProps) {
  return (
    <div className="apply-details-modal-overlay" onClick={onClose}>
      <div className="apply-details-modal" onClick={e => e.stopPropagation()}>
        <div className="apply-details-modal__header">
          <h3>Apply Results: {result.dimension}={result.value}</h3>
          <button className="apply-details-modal__close" onClick={onClose}>×</button>
        </div>
        <div className="apply-details-modal__summary">
          <span className="apply-details-modal__stat apply-details-modal__stat--updated">
            {result.stepsUpdated} updated
          </span>
          <span className="apply-details-modal__stat apply-details-modal__stat--skipped">
            {result.stepsSkipped} skipped
          </span>
        </div>
        <div className="apply-details-modal__list">
          {result.stepResults.map((step, idx) => (
            <div 
              key={idx}
              className={`apply-details-modal__step apply-details-modal__step--${step.status}`}
            >
              <span className="apply-details-modal__step-file">{step.step_file}</span>
              <span className="apply-details-modal__step-type">{step.step_type}</span>
              <span className={`apply-details-modal__step-status apply-details-modal__step-status--${step.status}`}>
                {step.status}
              </span>
              {step.applied_presets && step.applied_presets.length > 0 && (
                <span className="apply-details-modal__step-presets">
                  {step.applied_presets.join(', ')}
                </span>
              )}
              {step.updated_fields && step.updated_fields.length > 0 && (
                <span className="apply-details-modal__step-fields apply-details-modal__step-fields--updated">
                  Updated: {step.updated_fields.join(', ')}
                </span>
              )}
              {step.skipped_fields && step.skipped_fields.length > 0 && (
                <span className="apply-details-modal__step-fields apply-details-modal__step-fields--skipped">
                  Skipped: {step.skipped_fields.join('; ')}
                </span>
              )}
              {step.reason && (
                <span className="apply-details-modal__step-reason">{step.reason}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Workflow badge component
 */
function WorkflowBadge({ workflow }: { workflow: WorkflowType | null }) {
  if (!workflow || workflow === 'Unknown') return null;
  
  const workflowColors: Record<string, string> = {
    SCF: 'var(--color-success)',
    DOS: 'var(--color-info)',
    BandStructure: 'var(--color-primary)',
    Relaxation: 'var(--color-warning)',
    Phonon: 'var(--color-accent)',
    MD: 'var(--color-danger)',
    NSCF: 'var(--color-secondary)',
  };
  
  return (
    <span
      className="preset-section__workflow-badge"
      style={{ backgroundColor: workflowColors[workflow] || 'var(--bg-tertiary)' }}
      title="Detected workflow type (informational only)"
    >
      {workflow}
    </span>
  );
}

/**
 * Main PresetSection component
 */
export function PresetSection({
  projectRoot,
  calculationSlug,
  onPresetsChanged,
}: PresetSectionProps) {
  // Fetch catalog (UI's single source of truth)
  const { catalog, isLoading: catalogLoading, error: catalogError } = usePresetCatalog();
  
  const {
    presets,
    workflow,
    isLoading: presetsLoading,
    isApplying,
    error: presetsError,
    applyPreset,
    clearApplyResult,
  } = usePresets(projectRoot, calculationSlug);
  
  // State for toast and modal (Phase 8B)
  const [showToast, setShowToast] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [currentApplyResult, setCurrentApplyResult] = useState<ApplyResult | null>(null);
  
  // State for confirmation modal (Bug 2: Custom → preset safety)
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingApply, setPendingApply] = useState<{ dimension: string; value: string } | null>(null);
  
  const handleApplyComplete = useCallback((result: ApplyResult) => {
    setCurrentApplyResult(result);
    setShowToast(true);
    if (result.success && onPresetsChanged) {
      onPresetsChanged();
    }
    // Auto-dismiss toast after 5 seconds
    setTimeout(() => {
      setShowToast(false);
    }, 5000);
  }, [onPresetsChanged]);
  
  // Generic handler for dimension changes
  const handleDimensionChange = useCallback(async (dimension: string, value: string) => {
    // Safety check: if current state is Custom, show confirmation modal
    const currentValue = presets?.[dimension];
    if (currentValue === 'Custom') {
      setPendingApply({ dimension, value });
      setShowConfirmModal(true);
      return;
    }
    const result = await applyPreset(dimension, value);
    handleApplyComplete(result);
  }, [applyPreset, handleApplyComplete, presets]);
  
  const handleConfirmApply = useCallback(async () => {
    if (!pendingApply) return;
    
    setShowConfirmModal(false);
    const result = await applyPreset(pendingApply.dimension, pendingApply.value);
    setPendingApply(null);
    handleApplyComplete(result);
  }, [pendingApply, applyPreset, handleApplyComplete]);
  
  const handleCancelApply = useCallback(() => {
    setShowConfirmModal(false);
    setPendingApply(null);
  }, []);
  
  const handleCloseToast = useCallback(() => {
    setShowToast(false);
    clearApplyResult();
  }, [clearApplyResult]);
  
  const handleShowDetails = useCallback(() => {
    setShowDetailsModal(true);
  }, []);
  
  const handleCloseDetails = useCallback(() => {
    setShowDetailsModal(false);
  }, []);
  
  // Loading state
  if (catalogLoading || presetsLoading) {
    return (
      <div className="preset-section preset-section--loading">
        <div className="preset-section__header">
          <h3>Presets</h3>
        </div>
        <div className="preset-section__loading">
          Loading preset state...
        </div>
      </div>
    );
  }
  
  // Error state - catalog unavailable
  if (catalogError) {
    return (
      <div className="preset-section preset-section--error">
        <div className="preset-section__header">
          <h3>Presets</h3>
        </div>
        <div className="preset-section__error">
          {catalogError}
        </div>
      </div>
    );
  }
  
  // Error state - presets unavailable
  if (presetsError) {
    return (
      <div className="preset-section preset-section--error">
        <div className="preset-section__header">
          <h3>Presets</h3>
        </div>
        <div className="preset-section__error">
          {presetsError}
        </div>
      </div>
    );
  }
  
  // No catalog or presets
  if (!catalog || !presets) {
    return null;
  }
  
  // Custom badge tooltip (Phase 8F)
  const customTooltip = "Steps disagree on this dimension. Check step rows for details.";
  
  return (
    <div className="preset-section" data-testid="qms-preset-section">
      <div className="preset-section__header">
        <h3>
          Presets
          <WorkflowBadge workflow={workflow} />
        </h3>
        <div className="preset-section__info" title="Presets are detected from step parameters and applied to applicable steps when changed">
          ℹ️
        </div>
      </div>
      
      {isApplying && (
        <div className="preset-section__applying">
          Applying preset to applicable steps...
        </div>
      )}
      
      <div className="preset-section__dimensions">
        {catalog.dimensions.map(dimension => {
          const currentValue = presets[dimension.dimension];
          const isCustom = currentValue === 'Custom' || currentValue === undefined;
          
          return (
            <PresetDimensionRow
              key={dimension.dimension}
              dimension={dimension}
              value={isCustom ? undefined : currentValue}
              isCustom={isCustom}
              isApplying={isApplying}
              onChange={(value) => handleDimensionChange(dimension.dimension, value)}
              customTooltip={customTooltip}
            />
          );
        })}
      </div>
      
      <div className="preset-section__footer">
        <small>
          Values detected from step YAML • Hover step counts for details
        </small>
      </div>
      
      {/* Confirmation modal for Custom → preset (Bug 2: Safety) */}
      {showConfirmModal && pendingApply && (
        <div className="preset-confirm-modal-overlay" onClick={handleCancelApply}>
          <div className="preset-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="preset-confirm-modal__header">
              <h4>Confirm Preset Application</h4>
            </div>
            <div className="preset-confirm-modal__body">
              <p>
                This will overwrite step parameters for all applicable steps.
              </p>
              <p className="preset-confirm-modal__detail">
                Applying <strong>{pendingApply.value}</strong> to <strong>{pendingApply.dimension}</strong> dimension.
              </p>
            </div>
            <div className="preset-confirm-modal__actions">
              <button
                className="preset-confirm-modal__btn preset-confirm-modal__btn--cancel"
                onClick={handleCancelApply}
              >
                Cancel
              </button>
              <button
                className="preset-confirm-modal__btn preset-confirm-modal__btn--apply"
                onClick={handleConfirmApply}
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Toast for apply feedback (Phase 8B) */}
      {showToast && currentApplyResult && (
        <ApplyToast
          result={currentApplyResult}
          onClose={handleCloseToast}
          onShowDetails={handleShowDetails}
        />
      )}
      
      {/* Modal for detailed apply results (Phase 8B) */}
      {showDetailsModal && currentApplyResult && (
        <ApplyDetailsModal
          result={currentApplyResult}
          onClose={handleCloseDetails}
        />
      )}
    </div>
  );
}
