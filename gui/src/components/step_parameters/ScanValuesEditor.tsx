/**
 * ScanValuesEditor - Editor for parameter scan values list.
 * 
 * Supports explicit enumeration only (scalar or simple list values).
 */

import { useState, useCallback, useEffect } from 'react';
import './ScanValuesEditor.css';

interface ScanValuesEditorProps {
  values: unknown[];
  onChange: (values: unknown[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ScanValuesEditor({
  values,
  onChange,
  disabled = false,
  placeholder = 'Enter values (JSON array, e.g., [30, 40, 50])',
}: ScanValuesEditorProps) {
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  // Initialize input from values
  useEffect(() => {
    try {
      const jsonStr = JSON.stringify(values);
      setInputValue(jsonStr);
      setError(null);
    } catch (e) {
      setInputValue('');
      setError('Invalid values');
    }
  }, [values]);
  
  const handleChange = useCallback((newInput: string) => {
    setInputValue(newInput);
    setError(null);
    
    if (!newInput.trim()) {
      onChange([]);
      return;
    }
    
    try {
      // Try to parse as JSON
      const parsed = JSON.parse(newInput);
      
      // Ensure it's an array
      if (!Array.isArray(parsed)) {
        // If it's a single value, wrap it in an array
        if (parsed === null || typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean') {
          onChange([parsed]);
        } else {
          setError('Must be an array or single value');
          return;
        }
      } else {
        // Validate array items are leaf values
        const isValid = parsed.every(item => 
          item === null || 
          typeof item === 'string' || 
          typeof item === 'number' || 
          typeof item === 'boolean' ||
          (Array.isArray(item) && item.every(subItem => 
            subItem === null || 
            typeof subItem === 'string' || 
            typeof subItem === 'number' || 
            typeof subItem === 'boolean'
          ))
        );
        
        if (!isValid) {
          setError('Array items must be scalars or simple lists');
          return;
        }
        
        onChange(parsed);
      }
    } catch (e) {
      // Parse error - keep old values, show error
      setError('Invalid JSON');
    }
  }, [onChange]);
  
  return (
    <div className="scan-values-editor">
      <textarea
        className={`scan-values-editor__input ${error ? 'scan-values-editor__input--error' : ''}`}
        value={inputValue}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        rows={3}
      />
      {error && (
        <div className="scan-values-editor__error">{error}</div>
      )}
      <div className="scan-values-editor__hint">
        Enter JSON array (e.g., [30, 40, 50]) or single value (e.g., 30)
      </div>
    </div>
  );
}

