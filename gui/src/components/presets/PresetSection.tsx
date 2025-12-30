/**
 * PresetSection - Displays and allows editing of calculation presets.
 * 
 * Per Constitution Chapter 10:
 * - §10.4.1: Detector B is the sole legitimate state source (UI shows detected state)
 * - §10.3.3: Applying a preset BROADCASTS to all steps (overwrite, not merge)
 * - Presets are runtime-only interpretations
 * 
 * Phase 8B: Toast feedback with expandable audit detail
 * Phase 8F: Custom badge tooltip explaining disagreement
 */

import { useCallback, useState } from 'react';
import { usePresets, ApplyResult } from '../../hooks/usePresets';
import type { WorkflowType } from '../../types/qv';
import {
  SPIN_OPTIONS,
  SOC_OPTIONS,
  MATERIAL_OPTIONS,
  PRESET_LABELS,
} from '../../types/qv';
import './PresetSection.css';

interface PresetSectionProps {
  projectRoot: string;
  calculationSlug: string;
  /** Called when presets change (to refresh calculation detail) */
  onPresetsChanged?: () => void;
}

interface PresetDimensionRowProps {
  label: string;
  value: string;
  options: readonly string[];
  isCustom: boolean;
  isApplying: boolean;
  onChange: (value: string) => void;
  tooltip?: string;
  /** Tooltip for Custom badge specifically (Phase 8F) */
  customTooltip?: string;
}

/**
 * Individual preset dimension row with dropdown
 */
function PresetDimensionRow({
  label,
  value,
  options,
  isCustom,
  isApplying,
  onChange,
  tooltip,
  customTooltip,
}: PresetDimensionRowProps) {
  const handleChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange(e.target.value);
  }, [onChange]);
  
  return (
    <div className="preset-dimension-row" title={tooltip}>
      <span className="preset-dimension-row__label">{label}</span>
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
              title="Apply preset to all steps"
            >
              <option value="" disabled>Apply...</option>
              {options.map(opt => (
                <option key={opt} value={opt}>
                  {PRESET_LABELS[opt] || opt}
                </option>
              ))}
            </select>
          </>
        ) : (
          <select
            className="preset-dimension-row__select"
            value={value}
            onChange={handleChange}
            disabled={isApplying}
          >
            {options.map(opt => (
              <option key={opt} value={opt}>
                {PRESET_LABELS[opt] || opt}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

/** Toast component for apply feedback (Phase 8B) */
interface ApplyToastProps {
  result: ApplyResult;
  onClose: () => void;
  onShowDetails: () => void;
}

function ApplyToast({ result, onClose, onShowDetails }: ApplyToastProps) {
  const isSuccess = result.success;
  const dimensionLabel = PRESET_LABELS[result.value] || result.value;
  
  return (
    <div className={`apply-toast ${isSuccess ? 'apply-toast--success' : 'apply-toast--error'}`}>
      <div className="apply-toast__content">
        {isSuccess ? (
          <>
            <span className="apply-toast__icon">✓</span>
            <span className="apply-toast__message">
              Applied {result.dimension}={dimensionLabel}: {result.stepsUpdated} updated, {result.stepsSkipped} skipped
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
  const dimensionLabel = PRESET_LABELS[result.value] || result.value;
  
  return (
    <div className="apply-details-modal-overlay" onClick={onClose}>
      <div className="apply-details-modal" onClick={e => e.stopPropagation()}>
        <div className="apply-details-modal__header">
          <h3>Apply Results: {result.dimension}={dimensionLabel}</h3>
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
  const {
    presets,
    workflow,
    isLoading,
    isApplying,
    error,
    applyPreset,
    clearApplyResult,
  } = usePresets(projectRoot, calculationSlug);
  
  // State for toast and modal (Phase 8B)
  const [showToast, setShowToast] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [currentApplyResult, setCurrentApplyResult] = useState<ApplyResult | null>(null);
  
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
  
  const handleSpinChange = useCallback(async (value: string) => {
    const result = await applyPreset('spin', value);
    handleApplyComplete(result);
  }, [applyPreset, handleApplyComplete]);
  
  const handleSocChange = useCallback(async (value: string) => {
    const result = await applyPreset('soc', value);
    handleApplyComplete(result);
  }, [applyPreset, handleApplyComplete]);
  
  const handleMaterialChange = useCallback(async (value: string) => {
    const result = await applyPreset('material', value);
    handleApplyComplete(result);
  }, [applyPreset, handleApplyComplete]);
  
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
  
  if (isLoading) {
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
  
  if (error) {
    return (
      <div className="preset-section preset-section--error">
        <div className="preset-section__header">
          <h3>Presets</h3>
        </div>
        <div className="preset-section__error">
          {error}
        </div>
      </div>
    );
  }
  
  if (!presets) {
    return null;
  }
  
  // Custom badge tooltip (Phase 8F)
  const customTooltip = "Steps disagree on this dimension. Check step rows for details.";
  
  return (
    <div className="preset-section" data-testid="qv-preset-section">
      <div className="preset-section__header">
        <h3>
          Presets
          <WorkflowBadge workflow={workflow} />
        </h3>
        <div className="preset-section__info" title="Presets are detected from step parameters and broadcast to all steps when changed">
          ℹ️
        </div>
      </div>
      
      {isApplying && (
        <div className="preset-section__applying">
          Applying preset to all steps...
        </div>
      )}
      
      <div className="preset-section__dimensions">
        <PresetDimensionRow
          label="Spin"
          value={presets.spin}
          options={SPIN_OPTIONS}
          isCustom={presets.spin === 'Custom'}
          isApplying={isApplying}
          onChange={handleSpinChange}
          tooltip="Spin treatment: non-polarized, collinear, or non-collinear"
          customTooltip={customTooltip}
        />
        
        <PresetDimensionRow
          label="SOC"
          value={presets.soc}
          options={SOC_OPTIONS}
          isCustom={presets.soc === 'Custom'}
          isApplying={isApplying}
          onChange={handleSocChange}
          tooltip="Spin-orbit coupling (requires non-collinear spin and FR pseudopotentials)"
          customTooltip={customTooltip}
        />
        
        <PresetDimensionRow
          label="Material"
          value={presets.material}
          options={MATERIAL_OPTIONS}
          isCustom={presets.material === 'Custom'}
          isApplying={isApplying}
          onChange={handleMaterialChange}
          tooltip="Material type: insulator (fixed occupations) or metal (smearing)"
          customTooltip={customTooltip}
        />
      </div>
      
      <div className="preset-section__footer">
        <small>
          Changes apply to all steps • Detected from step.yml
        </small>
      </div>
      
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

