/**
 * ParameterValueEditor - Type-aware editor for QE parameter values
 * 
 * STRING-ONLY RULE: All values are stored as strings in YAML.
 * 
 * Supports:
 * - LOGICAL: select (.true./.false.) with raw string fallback
 * - INTEGER: text input (string, numeric hints only)
 * - REAL: text input (string, numeric hints only)
 * - CHARACTER: text input
 * - Enum: select dropdown with raw string fallback
 */

import { useCallback, useState, useMemo, useEffect } from 'react';
import type { QEParameterMeta } from '../../hooks/useQEParameterMetadata';
import './ParameterValueEditor.css';

interface ParameterValueEditorProps {
  parameter: QEParameterMeta;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ParameterValueEditor({
  parameter,
  value,
  onChange,
  disabled = false,
  placeholder,
}: ParameterValueEditorProps) {
  // Always work with string values
  const stringValue = value === null || value === undefined ? '' : String(value);
  
  const paramType = parameter.type?.toUpperCase() || 'CHARACTER';
  const hasEnum = parameter.enum && parameter.enum.length > 0;
  
  // Check if value matches enum (case-insensitive for LOGICAL)
  const enumValues = hasEnum ? parameter.enum!.map(v => String(v).toLowerCase()) : [];
  const valueMatchesEnum = useMemo(() => {
    if (!hasEnum || !stringValue) return false;
    return enumValues.includes(stringValue.toLowerCase());
  }, [hasEnum, stringValue, enumValues]);
  
  // Check if LOGICAL value matches .true./.false. (case-insensitive)
  const logicalValues = ['.true.', '.false.'];
  const valueMatchesLogical = useMemo(() => {
    if (paramType !== 'LOGICAL' || !stringValue) return false;
    return logicalValues.some(v => v.toLowerCase() === stringValue.toLowerCase());
  }, [paramType, stringValue]);
  
  // Auto-fallback to raw mode if value doesn't match expected values
  const [useRawMode, setUseRawMode] = useState(() => {
    if (hasEnum && !valueMatchesEnum) return true;
    if (paramType === 'LOGICAL' && !valueMatchesLogical) return true;
    return false;
  });
  
  // Sync raw mode state when value changes externally
  useEffect(() => {
    if (hasEnum && !valueMatchesEnum) {
      setUseRawMode(true);
    } else if (paramType === 'LOGICAL' && !valueMatchesLogical) {
      setUseRawMode(true);
    } else if (hasEnum || paramType === 'LOGICAL') {
      // If value now matches, allow switching back to dropdown (but don't force it)
      // User can manually switch back if they want
    }
  }, [hasEnum, valueMatchesEnum, paramType, valueMatchesLogical]);
  
  const handleChange = useCallback((newValue: string) => {
    // Always store as string (empty string means unset)
    onChange(newValue === '' ? undefined : newValue);
  }, [onChange]);
  
  // If enum is provided and value matches, show select with raw toggle
  if (hasEnum && !useRawMode) {
    return (
      <div className="parameter-value-editor-wrapper">
        <select
          className="parameter-value-editor parameter-value-editor--select"
          value={stringValue}
          onChange={(e) => {
            const val = e.target.value;
            handleChange(val);
          }}
          disabled={disabled}
        >
          <option value="">-- Not set --</option>
          {parameter.enum!.map(opt => (
            <option key={String(opt)} value={String(opt)}>{String(opt)}</option>
          ))}
        </select>
        <button
          className="parameter-value-editor__raw-toggle"
          onClick={() => setUseRawMode(true)}
          title="Edit raw value"
          disabled={disabled}
          type="button"
        >
          ✏️
        </button>
      </div>
    );
  }
  
  // LOGICAL type: .true./.false. select with raw toggle
  if (paramType === 'LOGICAL' && !useRawMode) {
    return (
      <div className="parameter-value-editor-wrapper">
        <select
          className="parameter-value-editor parameter-value-editor--logical"
          value={stringValue}
          onChange={(e) => {
            const val = e.target.value;
            handleChange(val);
          }}
          disabled={disabled}
        >
          <option value="">-- Not set --</option>
          <option value=".true.">.true.</option>
          <option value=".false.">.false.</option>
        </select>
        <button
          className="parameter-value-editor__raw-toggle"
          onClick={() => setUseRawMode(true)}
          title="Edit raw value"
          disabled={disabled}
          type="button"
        >
          ✏️
        </button>
      </div>
    );
  }
  
  // Raw mode or types without enum: text input (always string)
  const inputType = paramType === 'INTEGER' || paramType === 'REAL' ? 'text' : 'text';
  const inputPlaceholder = paramType === 'INTEGER' 
    ? (placeholder || 'Enter integer (as string)')
    : paramType === 'REAL'
    ? (placeholder || 'Enter number (as string)')
    : (placeholder || 'Enter text');
  
  return (
    <div className="parameter-value-editor-wrapper">
      <input
        type={inputType}
        className={`parameter-value-editor parameter-value-editor--${paramType.toLowerCase()} ${useRawMode ? 'parameter-value-editor--raw' : ''}`}
        value={stringValue}
        onChange={(e) => {
          handleChange(e.target.value);
        }}
        placeholder={inputPlaceholder}
        disabled={disabled}
      />
      {(hasEnum || paramType === 'LOGICAL') && useRawMode && (
        <button
          className="parameter-value-editor__raw-toggle"
          onClick={() => {
            setUseRawMode(false);
            // If value now matches enum/logical, keep it; otherwise it will auto-fallback
          }}
          title="Use dropdown"
          disabled={disabled}
          type="button"
        >
          📋
        </button>
      )}
    </div>
  );
}

