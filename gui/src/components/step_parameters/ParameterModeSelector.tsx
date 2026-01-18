/**
 * ParameterModeSelector - Mode selector for parameter value (Value vs Scan).
 * 
 * Replaces the "Value" button" with a segmented control/dropdown that allows
 * switching between Value and Scan modes.
 */

import './ParameterModeSelector.css';

interface ParameterModeSelectorProps {
  mode: 'value' | 'scan';
  onChange: (mode: 'value' | 'scan') => void;
  disabled?: boolean;
  showScanBadge?: boolean;
}

export function ParameterModeSelector({
  mode,
  onChange,
  disabled = false,
  showScanBadge = false,
}: ParameterModeSelectorProps) {
  return (
    <div className="parameter-mode-selector">
      <div className="parameter-mode-selector__segmented">
        <button
          className={`parameter-mode-selector__option ${mode === 'value' ? 'parameter-mode-selector__option--active' : ''}`}
          onClick={() => !disabled && onChange('value')}
          disabled={disabled}
          type="button"
          title="Edit as single value"
        >
          Value
        </button>
        <button
          className={`parameter-mode-selector__option ${mode === 'scan' ? 'parameter-mode-selector__option--active' : ''}`}
          onClick={() => !disabled && onChange('scan')}
          disabled={disabled}
          type="button"
          title="Edit as parameter scan"
        >
          Scan
        </button>
      </div>
      {showScanBadge && mode === 'scan' && (
        <span className="parameter-mode-selector__badge" title="Parameter scan enabled">
          📊
        </span>
      )}
    </div>
  );
}

