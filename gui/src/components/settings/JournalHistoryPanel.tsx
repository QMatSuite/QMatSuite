/**
 * JournalHistoryPanel - Debug view for change history
 * 
 * Features:
 * - Scrollable list of recent journal entries
 * - Columns: timestamp, target ULID, doc type, summary
 * - Click to view raw JSON diff (before vs after)
 * 
 * This is a debug-only view for visibility into YAML changes.
 */

import { useState, useEffect, useCallback } from 'react';
import type { JournalEntry, ListJournalEntriesResult } from '../../types/qv';
import './JournalHistoryPanel.css';

interface JournalHistoryPanelProps {
  /** Whether to fetch entries on mount */
  autoLoad?: boolean;
}

export function JournalHistoryPanel({ autoLoad = true }: JournalHistoryPanelProps) {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  const fetchEntries = useCallback(async () => {
    if (!window.qv) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<ListJournalEntriesResult>('list_journal_entries', {
        limit: 50,
      });
      
      if (response.ok && response.data) {
        setEntries(response.data.entries);
      } else {
        setError(response.error?.message || 'Failed to fetch journal entries');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch journal entries');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoLoad) {
      fetchEntries();
    }
  }, [autoLoad, fetchEntries]);

  const handleEntryClick = useCallback(async (entry: JournalEntry) => {
    setSelectedEntry(entry);
    setShowDiff(true);
  }, []);

  const formatTimestamp = (iso: string): string => {
    try {
      const date = new Date(iso);
      return date.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  const formatUlid = (ulid: string): string => {
    // Show last 8 chars for readability
    return ulid.length > 8 ? `...${ulid.slice(-8)}` : ulid;
  };

  return (
    <div className="journal-history-panel">
      <div className="journal-history-panel__header">
        <h4 className="journal-history-panel__title">Journal History</h4>
        <button
          className="settings-btn settings-btn--sm"
          onClick={fetchEntries}
          disabled={isLoading}
        >
          {isLoading ? '...' : '🔄 Refresh'}
        </button>
      </div>

      {error && (
        <div className="journal-history-panel__error">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      <div className="journal-history-panel__list">
        {entries.length === 0 ? (
          <div className="journal-history-panel__empty">
            {isLoading ? 'Loading...' : 'No journal entries yet'}
          </div>
        ) : (
          <table className="journal-history-panel__table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Target</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className="journal-history-panel__row"
                  onClick={() => handleEntryClick(entry)}
                >
                  <td className="journal-col-time">{formatTimestamp(entry.timestamp)}</td>
                  <td className="journal-col-type">
                    <span className={`journal-type-badge journal-type-badge--${entry.doc_type}`}>
                      {entry.doc_type}
                    </span>
                  </td>
                  <td className="journal-col-ulid" title={entry.target_ulid}>
                    {formatUlid(entry.target_ulid)}
                  </td>
                  <td className="journal-col-summary">{entry.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Diff Modal */}
      {showDiff && selectedEntry && (
        <div className="journal-diff-modal-overlay" onClick={() => setShowDiff(false)}>
          <div className="journal-diff-modal" onClick={(e) => e.stopPropagation()}>
            <div className="journal-diff-modal__header">
              <h3>Change Details</h3>
              <button
                className="journal-diff-modal__close"
                onClick={() => setShowDiff(false)}
              >
                ×
              </button>
            </div>
            
            <div className="journal-diff-modal__meta">
              <div><strong>ID:</strong> {selectedEntry.id}</div>
              <div><strong>Target:</strong> {selectedEntry.target_ulid}</div>
              <div><strong>Type:</strong> {selectedEntry.doc_type}</div>
              <div><strong>Time:</strong> {formatTimestamp(selectedEntry.timestamp)}</div>
              {selectedEntry.path && (
                <div><strong>Path:</strong> <code>{selectedEntry.path}</code></div>
              )}
            </div>

            <div className="journal-diff-modal__content">
              <div className="journal-diff-pane">
                <div className="journal-diff-pane__header">Before</div>
                <pre className="journal-diff-pane__json">
                  {JSON.stringify(selectedEntry.before, null, 2)}
                </pre>
              </div>
              <div className="journal-diff-pane">
                <div className="journal-diff-pane__header">After</div>
                <pre className="journal-diff-pane__json">
                  {JSON.stringify(selectedEntry.after, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

