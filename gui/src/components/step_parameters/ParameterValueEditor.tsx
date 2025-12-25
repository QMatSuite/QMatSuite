/**
 * ParameterValueEditor - Type-aware editor for QE parameter values
 * 
 * Supports:
 * - LOGICAL: boolean toggle or select (.true./.false.)
 * - INTEGER: number input
 * - REAL: number input (float)
 * - CHARACTER: text input
 * - Enum: select dropdown (if enum values provided)
 */

import { useCallback } from 'react';
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
  const handleChange = useCallback((newValue: unknown) => {
    onChange(newValue);
  }, [onChange]);
  
  const paramType = parameter.type?.toUpperCase() || 'CHARACTER';
  const hasEnum = parameter.enum && parameter.enum.length > 0;
  
  // If enum is provided, use select regardless of type
  if (hasEnum) {
    return (
      <select
        className="parameter-value-editor parameter-value-editor--select"
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => {
          const val = e.target.value;
          if (val === '') {
            handleChange(undefined);
          } else if (paramType === 'LOGICAL' || paramType === 'INTEGER') {
            // For LOGICAL/INTEGER with enum, keep as string (e.g., '.true.', '1')
            handleChange(val);
          } else if (paramType === 'REAL') {
            const num = parseFloat(val);
            handleChange(isNaN(num) ? undefined : num);
          } else {
            handleChange(val);
          }
        }}
        disabled={disabled}
      >
        <option value="">-- Not set --</option>
        {parameter.enum!.map(opt => (
          <option key={String(opt)} value={String(opt)}>{String(opt)}</option>
        ))}
      </select>
    );
  }
  
  // LOGICAL type: boolean toggle or .true./.false. select
  if (paramType === 'LOGICAL') {
    return (
      <select
        className="parameter-value-editor parameter-value-editor--logical"
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => {
          const val = e.target.value;
          handleChange(val === '' ? undefined : val);
        }}
        disabled={disabled}
      >
        <option value="">-- Not set --</option>
        <option value=".true.">.true.</option>
        <option value=".false.">.false.</option>
      </select>
    );
  }
  
  // INTEGER type: number input
  if (paramType === 'INTEGER') {
    return (
      <input
        type="text"
        className="parameter-value-editor parameter-value-editor--integer"
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => {
          const val = e.target.value.trim();
          if (val === '') {
            handleChange(undefined);
          } else {
            const num = parseInt(val, 10);
            handleChange(isNaN(num) ? val : num); // Allow typing, but prefer integer
          }
        }}
        onBlur={(e) => {
          // On blur, ensure it's a valid integer
          const val = e.target.value.trim();
          if (val === '') {
            handleChange(undefined);
          } else {
            const num = parseInt(val, 10);
            if (!isNaN(num)) {
              handleChange(num);
            }
          }
        }}
        placeholder={placeholder || 'Enter integer'}
        disabled={disabled}
      />
    );
  }
  
  // REAL type: number input (float)
  if (paramType === 'REAL') {
    return (
      <input
        type="text"
        className="parameter-value-editor parameter-value-editor--real"
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => {
          const val = e.target.value.trim();
          if (val === '') {
            handleChange(undefined);
          } else {
            const num = parseFloat(val);
            handleChange(isNaN(num) ? val : num); // Allow typing, but prefer float
          }
        }}
        onBlur={(e) => {
          // On blur, ensure it's a valid float
          const val = e.target.value.trim();
          if (val === '') {
            handleChange(undefined);
          } else {
            const num = parseFloat(val);
            if (!isNaN(num)) {
              handleChange(num);
            }
          }
        }}
        placeholder={placeholder || 'Enter number'}
        disabled={disabled}
      />
    );
  }
  
  // CHARACTER type (default): text input
  return (
    <input
      type="text"
      className="parameter-value-editor parameter-value-editor--character"
      value={value === null || value === undefined ? '' : String(value)}
      onChange={(e) => {
        const val = e.target.value;
        handleChange(val === '' ? undefined : val);
      }}
      placeholder={placeholder || 'Enter text'}
      disabled={disabled}
    />
  );
}

