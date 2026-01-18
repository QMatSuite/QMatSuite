/**
 * ScanValuesEditor - Editor for parameter scan values list.
 * 
 * Supports explicit enumeration only (scalar or simple list values).
 */

import React, { useState, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react';
import './ScanValuesEditor.css';

interface ScanValuesEditorProps {
  values: unknown[];
  onChange: (values: unknown[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export interface ScanValuesEditorHandle {
  flush: () => { ok: boolean; values?: unknown[]; error?: string };
}

export const ScanValuesEditor = forwardRef<ScanValuesEditorHandle, ScanValuesEditorProps>(({
  values,
  onChange,
  disabled = false,
  placeholder = 'Enter values (JSON array, e.g., [30, 40, 50])',
}, ref) => {
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  
  // Initialize input from values, but only if not dirty or if values match current input
  useEffect(() => {
    // If user is typing (dirty), don't overwrite unless values match what user typed
    if (isDirty) {
      try {
        // Try to parse current input
        const currentParsed = JSON.parse(inputValue);
        // If parsed input matches canonical values, clear dirty flag and sync
        if (JSON.stringify(currentParsed) === JSON.stringify(values)) {
          setIsDirty(false);
          // Input already matches, no need to update
          return;
        }
        // Otherwise, keep user input (don't overwrite while typing)
        return;
      } catch (e) {
        // Invalid JSON - keep user input
        return;
      }
    }
    
    // Not dirty: sync from canonical values
    try {
      const jsonStr = JSON.stringify(values);
      setInputValue(jsonStr);
      setError(null);
    } catch (e) {
      setInputValue('');
      setError('Invalid values');
    }
  }, [values, isDirty, inputValue]);
  
  const handleChange = useCallback((newInput: string) => {
    setInputValue(newInput);
    setError(null);
    setIsDirty(true); // Mark as dirty when user types
    
    if (!newInput.trim()) {
      onChange([]);
      setIsDirty(false); // Clear dirty after successful onChange
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
          setIsDirty(false); // Clear dirty after successful onChange
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
        
        // CRITICAL: Immediately commit parsed value to parent state on every valid keystroke
        // This ensures Apply will have the latest values, not empty/old state
        onChange(parsed);
        setIsDirty(false); // Clear dirty after successful onChange
      }
    } catch (e) {
      // Parse error - keep old values, show error (stay dirty)
      setError('Invalid JSON');
    }
  }, [onChange]);
  
  // Expose flush method for parent to call before Apply
  // This ensures any pending input is committed even if user didn't blur
  const flush = useCallback((): { ok: boolean; values?: unknown[]; error?: string } => {
    const currentInput = inputValue.trim();
    
    // If empty string: allow empty array (validator can hard-error if needed)
    if (!currentInput) {
      onChange([]);
      setIsDirty(false);
      return { ok: true, values: [] };
    }
    
    try {
      const parsed = JSON.parse(currentInput);
      
      // Handle scalar values: wrap in array
      if (!Array.isArray(parsed)) {
        if (parsed === null || typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean') {
          const wrapped = [parsed];
          onChange(wrapped);
          setIsDirty(false);
          return { ok: true, values: wrapped };
        } else {
          return { ok: false, error: 'Must be an array or single value' };
        }
      }
      
      // Array: use as-is (no type checking in flush, just parse)
      onChange(parsed);
      setIsDirty(false);
      return { ok: true, values: parsed };
    } catch (e) {
      return { ok: false, error: 'Invalid JSON' };
    }
  }, [inputValue, onChange]);
  
  // Expose flush via ref (parent can call it)
  useImperativeHandle(ref, () => ({ flush }), [flush]);
  
  return (
    <div className="scan-values-editor">
      <textarea
        className={`scan-values-editor__input ${error ? 'scan-values-editor__input--error' : ''}`}
        value={inputValue}
        onChange={(e) => handleChange(e.target.value)}
        onBlur={() => {
          // On blur, sync if dirty and input is valid
          if (isDirty && !error) {
            try {
              const parsed = JSON.parse(inputValue);
              // If parsed matches current values, clear dirty flag
              if (JSON.stringify(parsed) === JSON.stringify(values)) {
                setIsDirty(false);
              }
            } catch (e) {
              // Invalid - keep dirty
            }
          }
        }}
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
});

