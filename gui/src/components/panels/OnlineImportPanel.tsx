/**
 * OnlineImportPanel - Search and import structures from online databases
 */

import { useState, useCallback } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import './OnlineImportPanel.css';

export interface OnlineCandidate {
  candidate_id: string;
  label: string;
  source: string;
  source_id: string;
  nsites: number;
  spacegroup?: string | null;
  flags: string[];
  score: number;
}

interface OnlineImportPanelProps {
  projectRoot: string;
  isExpanded: boolean;
  onExpand: () => void;
  onCollapse: () => void;
  onSelectCandidate: (sessionId: string, candidateId: string) => void;
  selectedCandidateId: string | null;
}

export function OnlineImportPanel({
  projectRoot,
  isExpanded,
  onExpand,
  onCollapse,
  selectedCandidateId,
  onSelectCandidate,
}: OnlineImportPanelProps) {
  const qv = useQVClient();
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<OnlineCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim() || !projectRoot) return;
    
    setIsSearching(true);
    setError(null);
    
    try {
      const response = await qv.call('structure_search_online', {
        project_root: projectRoot,
        query: query.trim(),
        max_results: 10,
      });
      
      if (response.ok && response.data) {
        setSessionId(response.data.session_id);
        setCandidates(response.data.candidates || []);
        // Auto-select first candidate if available
        if (response.data.candidates && response.data.candidates.length > 0) {
          onSelectCandidate(response.data.session_id, response.data.candidates[0].candidate_id);
        }
      } else {
        setError(response.error?.message || 'Search failed');
        setCandidates([]);
        setSessionId(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      setCandidates([]);
      setSessionId(null);
    } finally {
      setIsSearching(false);
    }
  }, [query, projectRoot, qv, onSelectCandidate]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isSearching) {
      handleSearch();
    }
  }, [handleSearch, isSearching]);

  const handleCandidateClick = useCallback((candidateId: string) => {
    if (sessionId) {
      onSelectCandidate(sessionId, candidateId);
    }
  }, [sessionId, onSelectCandidate]);

  if (!isExpanded) {
    return (
      <div className="online-import-panel online-import-panel--collapsed">
        <button
          className="online-import-panel__header-btn"
          onClick={onExpand}
          title="Search and import structures from online databases"
        >
          ➕ Online Import
        </button>
      </div>
    );
  }

  return (
    <div className="online-import-panel online-import-panel--expanded">
      <div className="online-import-panel__header">
        <h3 className="online-import-panel__title">Online Import</h3>
        <button
          className="online-import-panel__collapse-btn"
          onClick={onCollapse}
          title="Collapse"
        >
          ×
        </button>
      </div>
      
      <div className="online-import-panel__content">
        <div className="online-import-panel__search">
          <input
            type="text"
            className="online-import-panel__search-input"
            placeholder="Enter formula (e.g., MoS2)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isSearching}
          />
          <button
            className="online-import-panel__search-btn"
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>
        
        {error && (
          <div className="online-import-panel__error">
            ⚠️ {error}
          </div>
        )}
        
        {candidates.length > 0 && (
          <div className="online-import-panel__candidates">
            <div className="online-import-panel__candidates-header">
              Found {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
            </div>
            <div className="online-import-panel__candidates-list">
              {candidates.slice(0, 5).map((candidate) => (
                <div
                  key={candidate.candidate_id}
                  className={`online-import-panel__candidate ${
                    selectedCandidateId === candidate.candidate_id
                      ? 'online-import-panel__candidate--selected'
                      : ''
                  }`}
                  onClick={() => handleCandidateClick(candidate.candidate_id)}
                >
                  <div className="online-import-panel__candidate-label">
                    {candidate.label}
                  </div>
                  <div className="online-import-panel__candidate-meta">
                    <span className="online-import-panel__candidate-source">
                      {candidate.source}
                    </span>
                    {candidate.flags.length > 0 && (
                      <span className="online-import-panel__candidate-flags">
                        {candidate.flags.join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {candidates.length > 5 && (
                <div className="online-import-panel__candidates-more">
                  + {candidates.length - 5} more (scroll to see)
                </div>
              )}
            </div>
          </div>
        )}
        
        {!isSearching && candidates.length === 0 && query && (
          <div className="online-import-panel__empty">
            No results found. Try a different formula.
          </div>
        )}
      </div>
    </div>
  );
}
