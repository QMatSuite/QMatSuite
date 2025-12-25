/**
 * AddParameterPalette - Search and add QE parameters
 * 
 * Provides a search interface to find and add QE parameters from metadata.
 * Shows parameter name, section/namelist, type, default, and description.
 * On click "Add", inserts the parameter into the step under the correct namelist.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { QESearchResult } from '../../hooks/useQEParameterMetadata';
import { useQEParameterMetadata } from '../../hooks/useQEParameterMetadata';
import './AddParameterPalette.css';

interface AddParameterPaletteProps {
  module: string | null;
  stepParameters: Record<string, Record<string, unknown>>; // Current step parameters
  onAddParameter: (section: string, paramName: string) => void;
  onScrollToParameter?: (section: string, paramName: string) => void;
}

export function AddParameterPalette({
  module,
  stepParameters,
  onAddParameter,
  onScrollToParameter,
}: AddParameterPaletteProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  
  const {
    searchResults,
    searchLoading,
    searchError,
    search,
    metadataInfo,
  } = useQEParameterMetadata();
  
  // Filter search results to only show parameters for the current module
  const filteredResults = module
    ? searchResults.filter(r => r.module === module)
    : searchResults;
  
  // Check if a parameter is already set in the step
  const isParameterSet = useCallback((result: QESearchResult): boolean => {
    const section = result.section.startsWith('&') 
      ? result.section.substring(1).toUpperCase()
      : result.section.toUpperCase();
    
    return stepParameters[section]?.[result.name] !== undefined;
  }, [stepParameters]);
  
  // Handle search
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      search(query);
    }
  }, [search]);
  
  // Handle add parameter
  const handleAddParameter = useCallback((result: QESearchResult) => {
    const section = result.section.startsWith('&')
      ? result.section.substring(1).toUpperCase()
      : result.section.toUpperCase();
    
    onAddParameter(section, result.name);
    setIsOpen(false);
    setSearchQuery('');
  }, [onAddParameter]);
  
  // Handle scroll to existing parameter
  const handleScrollToParameter = useCallback((result: QESearchResult) => {
    const section = result.section.startsWith('&')
      ? result.section.substring(1).toUpperCase()
      : result.section.toUpperCase();
    
    if (onScrollToParameter) {
      onScrollToParameter(section, result.name);
    }
    setIsOpen(false);
    setSearchQuery('');
  }, [onScrollToParameter]);
  
  // Focus search input when opened
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);
  
  // Close on Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen]);
  
  return (
    <div className="add-parameter-palette">
      <button
        className="add-parameter-palette__trigger"
        onClick={() => setIsOpen(!isOpen)}
        title="Add QE parameter"
      >
        ➕ Add Parameter
      </button>
      
      {isOpen && (
        <div className="add-parameter-palette__overlay" onClick={() => setIsOpen(false)}>
          <div className="add-parameter-palette__popup" onClick={(e) => e.stopPropagation()}>
            <div className="add-parameter-palette__header">
              <h3 className="add-parameter-palette__title">Add QE Parameter</h3>
              <button
                className="add-parameter-palette__close"
                onClick={() => setIsOpen(false)}
                title="Close"
              >
                ×
              </button>
            </div>
            
            <div className="add-parameter-palette__search">
              <input
                ref={searchInputRef}
                type="text"
                className="add-parameter-palette__search-input"
                placeholder="Search by parameter name, description, section..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && filteredResults.length > 0) {
                    const firstResult = filteredResults[0];
                    if (isParameterSet(firstResult)) {
                      handleScrollToParameter(firstResult);
                    } else {
                      handleAddParameter(firstResult);
                    }
                  }
                }}
              />
              {metadataInfo.schemaVersion !== null && (
                <span className="add-parameter-palette__version" title={metadataInfo.pathAbs || undefined}>
                  v{metadataInfo.schemaVersion}
                </span>
              )}
            </div>
            
            {searchLoading && (
              <div className="add-parameter-palette__loading">
                Searching...
              </div>
            )}
            
            {searchError && (
              <div className="add-parameter-palette__error">
                {searchError}
              </div>
            )}
            
            {!searchLoading && !searchError && searchQuery.trim() && (
              <div className="add-parameter-palette__results">
                {filteredResults.length === 0 ? (
                  <div className="add-parameter-palette__empty">
                    No parameters found for "{searchQuery}"
                  </div>
                ) : (
                  <div className="add-parameter-palette__results-list">
                    {filteredResults.slice(0, 20).map((result) => {
                      const isSet = isParameterSet(result);
                      
                      return (
                        <div
                          key={result.key}
                          className={`add-parameter-palette__result-item ${
                            isSet ? 'add-parameter-palette__result-item--set' : ''
                          }`}
                          onClick={() => {
                            if (isSet) {
                              handleScrollToParameter(result);
                            } else {
                              handleAddParameter(result);
                            }
                          }}
                        >
                          <div className="add-parameter-palette__result-header">
                            <span className="add-parameter-palette__result-name">
                              {result.name}
                            </span>
                            <span className="add-parameter-palette__result-section">
                              {result.section}
                            </span>
                            {isSet && (
                              <span className="add-parameter-palette__result-badge">
                                Already set
                              </span>
                            )}
                          </div>
                          
                          <div className="add-parameter-palette__result-meta">
                            <span className="add-parameter-palette__result-type">
                              {result.type || 'UNKNOWN'}
                            </span>
                            {result.default !== null && result.default !== undefined && (
                              <span className="add-parameter-palette__result-default">
                                Default: {String(result.default)}
                              </span>
                            )}
                          </div>
                          
                          {result.description && (
                            <div className="add-parameter-palette__result-description">
                              {result.description}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {filteredResults.length > 20 && (
                      <div className="add-parameter-palette__results-more">
                        Showing first 20 of {filteredResults.length} results
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            
            {!searchQuery.trim() && (
              <div className="add-parameter-palette__hint">
                Start typing to search for QE parameters...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

