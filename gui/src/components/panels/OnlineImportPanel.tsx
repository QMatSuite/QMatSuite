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
  structure_type: "crystal" | "molecule";
  formula: string;
  nsites: number;
  spacegroup?: string | null;
  providers: string[];
  flags: string[];
  score: number;
  metadata?: Record<string, unknown>;
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
  const [mode, setMode] = useState<"crystal" | "molecule" | "auto">("auto");
  const [isSearching, setIsSearching] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<OnlineCandidate[]>([]);
  const [providersQueried, setProvidersQueried] = useState<string[]>([]);
  const [partial, setPartial] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    setError(null);
    
    try {
      const response = await qv.call('structure_search_online', {
        query: query.trim(),
        mode: mode,
        limit: 50,
      });
      
      if (response.ok && response.data) {
        setSessionId(response.data.session_id);
        setCandidates(response.data.candidates || []);
        setProvidersQueried(response.data.providers_queried || []);
        setPartial(response.data.partial || false);
        // Auto-select first candidate if available
        if (response.data.candidates && response.data.candidates.length > 0) {
          onSelectCandidate(response.data.session_id, response.data.candidates[0].candidate_id);
        }
      } else {
        setError(response.error?.message || 'Search failed');
        setCandidates([]);
        setSessionId(null);
        setProvidersQueried([]);
        setPartial(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      setCandidates([]);
      setSessionId(null);
      setProvidersQueried([]);
      setPartial(false);
    } finally {
      setIsSearching(false);
    }
  }, [query, mode, qv, onSelectCandidate]);

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
        {/* Mode Selection Tabs */}
        <div className="online-import-panel__mode-tabs">
          <button
            className={`online-import-panel__mode-tab ${mode === "crystal" ? "online-import-panel__mode-tab--active" : ""}`}
            onClick={() => setMode("crystal")}
            disabled={isSearching}
            title="Search only crystal structures"
          >
            🔷 Crystals
          </button>
          <button
            className={`online-import-panel__mode-tab ${mode === "molecule" ? "online-import-panel__mode-tab--active" : ""}`}
            onClick={() => setMode("molecule")}
            disabled={isSearching}
            title="Search only molecules"
          >
            ⚛️ Molecules
          </button>
          <button
            className={`online-import-panel__mode-tab ${mode === "auto" ? "online-import-panel__mode-tab--active" : ""}`}
            onClick={() => setMode("auto")}
            disabled={isSearching}
            title="Search both crystals and molecules"
          >
            🔍 All
          </button>
        </div>
        
        <div className="online-import-panel__search">
          <input
            type="text"
            className="online-import-panel__search-input"
            placeholder="Enter formula or name (e.g., MoS2, caffeine)"
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
        
        {/* Providers queried indicator */}
        {providersQueried.length > 0 && (
          <div className="online-import-panel__providers-info">
            <span className="online-import-panel__providers-label">Providers:</span>
            <div className="online-import-panel__providers-badges">
              {providersQueried.map((provider) => (
                <span key={provider} className="online-import-panel__provider-badge">
                  {provider}
                </span>
              ))}
            </div>
            {partial && (
              <span className="online-import-panel__partial-indicator" title="Some providers timed out">
                ⚠️ Partial results
              </span>
            )}
          </div>
        )}
        
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
              {candidates.map((candidate) => (
                <div
                  key={candidate.candidate_id}
                  className={`online-import-panel__candidate ${
                    selectedCandidateId === candidate.candidate_id
                      ? 'online-import-panel__candidate--selected'
                      : ''
                  }`}
                  onClick={() => handleCandidateClick(candidate.candidate_id)}
                >
                  <div className="online-import-panel__candidate-header">
                    <div className="online-import-panel__candidate-label">
                      {candidate.structure_type === "crystal" ? "🔷" : "⚛️"} {candidate.label}
                    </div>
                    <div className="online-import-panel__candidate-type-badge">
                      {candidate.structure_type === "crystal" ? "Crystal" : "Molecule"}
                    </div>
                  </div>
                  <div className="online-import-panel__candidate-meta">
                    <div className="online-import-panel__candidate-providers">
                      {candidate.providers && candidate.providers.length > 0 ? (
                        candidate.providers.map((provider) => (
                          <span key={provider} className="online-import-panel__candidate-provider-badge">
                            {provider}
                          </span>
                        ))
                      ) : (
                        <span className="online-import-panel__candidate-source">
                          {candidate.source}
                        </span>
                      )}
                    </div>
                    <span className="online-import-panel__candidate-sites">
                      {candidate.nsites} sites
                    </span>
                    {candidate.spacegroup && (
                      <span className="online-import-panel__candidate-spacegroup">
                        {candidate.spacegroup}
                      </span>
                    )}
                    {candidate.flags.length > 0 && (
                      <span className="online-import-panel__candidate-flags">
                        {candidate.flags.join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
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
