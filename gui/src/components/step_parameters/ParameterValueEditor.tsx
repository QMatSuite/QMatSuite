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
 * 
 * Quote-aware: Recognizes both quoted and unquoted enum values (e.g., 'scf' and scf).
 * For CHARACTER enums, writes quoted values by default.
 */

import { useCallback, useState, useMemo, useEffect } from 'react';
import type { QEParameterMeta } from '../../hooks/useEngineParameterMetadata';
import { normalizeQeScalar, quoteSingle } from '../../utils/qeStringUtils';
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
  const isCharacter = paramType === 'CHARACTER';
  const isLogical = paramType === 'LOGICAL';
  
  // Normalize current value for comparison (strips quotes, trims)
  const normalizedValue = useMemo(() => {
    return stringValue ? normalizeQeScalar(stringValue) : '';
  }, [stringValue]);
  
  // Normalize enum values for comparison
  const normalizedEnumValues = useMemo(() => {
    if (!hasEnum) return [];
    return parameter.enum!.map(v => normalizeQeScalar(String(v)).toLowerCase());
  }, [hasEnum, parameter.enum]);
  
  // Check if normalized value matches any enum value (case-insensitive)
  const valueMatchesEnum = useMemo(() => {
    if (!hasEnum || !normalizedValue) return false;
    return normalizedEnumValues.includes(normalizedValue.toLowerCase());
  }, [hasEnum, normalizedValue, normalizedEnumValues]);
  
  // Find the matching enum value (for display in dropdown)
  const matchedEnumValue = useMemo(() => {
    if (!hasEnum || !normalizedValue) return null;
    const lower = normalizedValue.toLowerCase();
    return parameter.enum!.find(v => normalizeQeScalar(String(v)).toLowerCase() === lower) || null;
  }, [hasEnum, normalizedValue, parameter.enum]);
  
  // Check if LOGICAL value matches recognized logical tokens
  // Recognizes: .true., true, t, 1 (for true) and .false., false, f, 0 (for false)
  const logicalTrueTokens = ['.true.', 'true', 't', '1'];
  const logicalFalseTokens = ['.false.', 'false', 'f', '0'];
  const valueMatchesLogical = useMemo(() => {
    if (!isLogical || !normalizedValue) return false;
    const lower = normalizedValue.toLowerCase();
    return logicalTrueTokens.includes(lower) || logicalFalseTokens.includes(lower);
  }, [isLogical, normalizedValue]);
  
  // Determine canonical logical value (preserve original if it's .true./.false., otherwise canonicalize)
  const canonicalLogicalValue = useMemo(() => {
    if (!isLogical || !normalizedValue) return null;
    const lower = normalizedValue.toLowerCase();
    if (logicalTrueTokens.includes(lower)) {
      // Preserve original if it's already .true., otherwise canonicalize
      return stringValue.toLowerCase() === '.true.' ? stringValue : '.true.';
    }
    if (logicalFalseTokens.includes(lower)) {
      return stringValue.toLowerCase() === '.false.' ? stringValue : '.false.';
    }
    return null;
  }, [isLogical, normalizedValue, stringValue]);
  
  // Track if user manually forced raw mode (to preserve their preference during edit session)
  const [userForcedRaw, setUserForcedRaw] = useState(false);
  
  // Compute default mode based on value and metadata (fully reactive, derived every render)
  // This ensures mode is correct when:
  // - Edit mode is enabled (disabled becomes false)
  // - Metadata arrives async
  // - Value changes
  const shouldUseRawMode = useMemo(() => {
    // If value is empty, default to dropdown/toggle if metadata indicates it
    if (!stringValue) {
      return false; // Default to metadata-first controls
    }
    // If value is non-empty, check if it matches expected values
    if (hasEnum && !valueMatchesEnum) return true;
    if (isLogical && !valueMatchesLogical) return true;
    return false;
  }, [stringValue, hasEnum, valueMatchesEnum, isLogical, valueMatchesLogical]);
  
  // Derived mode: use raw mode if user forced it OR if shouldUseRawMode is true
  // This is computed every render, so it's always correct regardless of when metadata arrives
  const useRawMode = userForcedRaw || shouldUseRawMode;
  
  // Reset user preference when edit mode is disabled (to start fresh next time)
  useEffect(() => {
    if (disabled) {
      setUserForcedRaw(false);
    }
  }, [disabled]);
  
  const handleChange = useCallback((newValue: string) => {
    // Always store as string (empty string means unset)
    onChange(newValue === '' ? undefined : newValue);
  }, [onChange]);
  
  // Handle enum dropdown change
  const handleEnumChange = useCallback((selectedValue: string) => {
    if (selectedValue === '') {
      handleChange('');
      return;
    }
    
    // For CHARACTER type enums, write quoted value by default
    // For other types, write unquoted
    if (isCharacter) {
      handleChange(quoteSingle(selectedValue));
    } else {
      handleChange(selectedValue);
    }
  }, [handleChange, isCharacter]);
  
  // Handle logical dropdown change
  const handleLogicalChange = useCallback((selectedValue: string) => {
    if (selectedValue === '') {
      handleChange('');
      return;
    }
    // Write canonical .true./.false. format
    handleChange(selectedValue);
  }, [handleChange]);
  
  // If enum is provided, show select with raw toggle (default mode for enum)
  if (hasEnum && !useRawMode) {
    // For select value: use matched enum value (from metadata, unquoted) if value matches after normalization
    // This ensures the dropdown shows the correct selection even if YAML value is quoted
    // If value doesn't match any enum option, the select will show empty (which is fine, user can select)
    // The matchedEnumValue is the original enum value from metadata (e.g., "scf"), which matches the option value
    const selectValue = matchedEnumValue ? String(matchedEnumValue) : (stringValue || '');
    
    return (
      <div className="parameter-value-editor-wrapper">
        <select
          className="parameter-value-editor parameter-value-editor--select"
          value={selectValue}
          onChange={(e) => {
            handleEnumChange(e.target.value);
          }}
          disabled={disabled}
        >
          <option value="">-- Not set --</option>
          {parameter.enum!.map(opt => {
            const optStr = String(opt);
            // Normalize display label (strip quotes) but keep original value for storage
            // This ensures users see "scf" not "'scf'" in the dropdown
            const displayLabel = normalizeQeScalar(optStr);
            return (
              <option key={optStr} value={optStr}>{displayLabel}</option>
            );
          })}
        </select>
        <button
          className="parameter-value-editor__raw-toggle"
          onClick={() => {
            setUserForcedRaw(true);
          }}
          title="Edit raw value"
          disabled={disabled}
          type="button"
        >
          ✏️
        </button>
      </div>
    );
  }
  
  // LOGICAL type: .true./.false. select with raw toggle (default mode for logical)
  if (isLogical && !useRawMode) {
    // Use canonical value if available, otherwise use current string value
    const selectValue = canonicalLogicalValue || stringValue;
    
    return (
      <div className="parameter-value-editor-wrapper">
        <select
          className="parameter-value-editor parameter-value-editor--logical"
          value={selectValue}
          onChange={(e) => {
            handleLogicalChange(e.target.value);
          }}
          disabled={disabled}
        >
          <option value="">-- Not set --</option>
          <option value=".true.">.true.</option>
          <option value=".false.">.false.</option>
        </select>
        <button
          className="parameter-value-editor__raw-toggle"
          onClick={() => {
            setUserForcedRaw(true);
          }}
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
            setUserForcedRaw(false);
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

