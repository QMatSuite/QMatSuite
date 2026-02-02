/**
 * HistoryPanel - Notebook-style timeline view of project history
 * 
 * Displays:
 * - Run cards with status, duration, step digests
 * - Edit events with semantic summaries
 * - Pinned analysis previews
 * - Filters and search (v1: basic grouping)
 * 
 * This is a READ-ONLY view - history is immutable.
 * Users can filter by limit and delete history with confirmation.
 */

import { useState, useEffect, useCallback } from 'react';
import type { HistoryTimelineEntry } from '../../types/qv';
import './HistoryPanel.css';

// Limit options for history display
type LimitOption = 'all' | '50' | '200';

interface HistoryPanelProps {
  projectRoot: string;
}

export function HistoryPanel({ projectRoot }: HistoryPanelProps) {
  const [timeline, setTimeline] = useState<HistoryTimelineEntry[]>([]);
  const [latestRunUlid, setLatestRunUlid] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState<LimitOption>('all');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (!projectRoot || !window.qv) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const limitValue = limit === 'all' ? undefined : parseInt(limit, 10);
      const response = await window.qv.request<{
        timeline: HistoryTimelineEntry[];
        latest_run_ulid: string | null;
        total: number;
      }>('get_project_history', {
        project_root: projectRoot,
        limit: limitValue,
      });

      if (response.ok && response.data) {
        setTimeline(response.data.timeline || []);
        setLatestRunUlid(response.data.latest_run_ulid);
      } else {
        setError(response.error?.message || 'Failed to load history');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  }, [projectRoot, limit]);
  
  // Handle delete history
  const handleDeleteHistory = useCallback(async () => {
    if (!projectRoot || !window.qv) return;
    
    setIsDeleting(true);
    
    try {
      const response = await window.qv.request<{
        success: boolean;
        error?: string;
        deleted_path?: string;
      }>('delete_project_history', {
        project_root: projectRoot,
        confirm: true,
      });
      
      if (response.ok && response.data?.success) {
        // Clear timeline immediately
        setTimeline([]);
        setLatestRunUlid(null);
        setShowDeleteModal(false);
      } else {
        const errorMsg = response.data?.error || response.error?.message || 'Failed to delete history';
        setError(errorMsg);
        setShowDeleteModal(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete history');
      setShowDeleteModal(false);
    } finally {
      setIsDeleting(false);
    }
  }, [projectRoot]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const toggleRunExpanded = useCallback((runId: string) => {
    setExpandedRuns(prev => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  }, []);

  const formatDuration = (seconds: number | undefined): string => {
    if (!seconds) return '';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const formatTimestamp = (ts: string): string => {
    try {
      const date = new Date(ts);
      return date.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  const renderTimelineEntry = (entry: HistoryTimelineEntry) => {
    switch (entry.event_type) {
      case 'run_finished':
        return renderRunCard(entry);
      case 'run_started':
        return renderRunStarted(entry);
      case 'edit':
        return renderEditEvent(entry);
      case 'pin_created':
        return renderPinEvent(entry);
      case 'baseline':
        return renderBaselineEvent(entry);
      default:
        return renderGenericEvent(entry);
    }
  };

  const renderRunCard = (entry: HistoryTimelineEntry) => {
    const isExpanded = entry.run_ulid ? expandedRuns.has(entry.run_ulid) : false;
    const isSuccess = entry.status === 'success';
    const isLatest = entry.run_ulid === latestRunUlid;

    return (
      <div
        key={entry.ulid}
        className={`history-entry history-entry--run ${isSuccess ? 'history-entry--success' : 'history-entry--failed'} ${isLatest ? 'history-entry--latest' : ''}`}
      >
        <div
          className="history-entry__header"
          onClick={() => entry.run_ulid && toggleRunExpanded(entry.run_ulid)}
        >
          <div className="history-entry__icon">
            {isSuccess ? '✓' : '✗'}
          </div>
          <div className="history-entry__title">
            <span className="history-entry__label">
              Run {isLatest && <span className="history-entry__badge">Latest</span>}
            </span>
            {entry.calc_name && (
              <span className="history-entry__calc-name">{entry.calc_name}</span>
            )}
          </div>
          <div className="history-entry__meta">
            <span className="history-entry__time">{formatTimestamp(entry.timestamp)}</span>
            {entry.duration_seconds && (
              <span className="history-entry__duration">
                {formatDuration(entry.duration_seconds)}
              </span>
            )}
          </div>
          <div className="history-entry__expand">
            {isExpanded ? '▼' : '▶'}
          </div>
        </div>
        
        {/* Summary chips */}
        <div className="history-entry__chips">
          <span className={`history-chip ${isSuccess ? 'history-chip--success' : 'history-chip--error'}`}>
            {entry.success_count}/{entry.step_count} steps
          </span>
          {entry.run_digest?.total_energy_ry && (
            <span className="history-chip history-chip--energy">
              E = {entry.run_digest.total_energy_ry.toFixed(4)} Ry
            </span>
          )}
          {entry.run_digest?.fermi_energy_ev && (
            <span className="history-chip history-chip--fermi">
              Ef = {entry.run_digest.fermi_energy_ev.toFixed(2)} eV
            </span>
          )}
        </div>
        
        {entry.error_summary && (
          <div className="history-entry__error">
            {entry.error_summary}
          </div>
        )}
        
        {/* Expanded details */}
        {isExpanded && entry.step_digests && (
          <div className="history-entry__details">
            <h4 className="history-entry__details-title">Step Digests</h4>
            <div className="history-entry__steps">
              {entry.step_digests.map((step, idx) => (
                <div
                  key={step.step_ulid || idx}
                  className={`history-step ${step.status === 'success' ? 'history-step--success' : 'history-step--failed'}`}
                >
                  <span className="history-step__type">{step.step_type_gen}</span>
                  <span className="history-step__status">
                    {step.status === 'success' ? '✓' : step.status === 'skipped' ? '⊘' : '✗'}
                  </span>
                  {step.total_energy?.value && (
                    <span className="history-step__metric">
                      {step.total_energy.value.toFixed(4)} Ry
                    </span>
                  )}
                  {step.fermi_energy?.value && (
                    <span className="history-step__metric">
                      Ef: {step.fermi_energy.value.toFixed(2)} eV
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderRunStarted = (entry: HistoryTimelineEntry) => {
    // Usually followed by run_finished, so render compact
    return (
      <div key={entry.ulid} className="history-entry history-entry--run-started history-entry--compact">
        <div className="history-entry__icon">▶</div>
        <div className="history-entry__content">
          <span className="history-entry__label">Run started</span>
          {entry.step_type_gens && entry.step_type_gens.length > 0 && (
            <span className="history-entry__step-types">
              {entry.step_type_gens.join(' → ')}
            </span>
          )}
        </div>
        <div className="history-entry__time">{formatTimestamp(entry.timestamp)}</div>
      </div>
    );
  };

  const renderEditEvent = (entry: HistoryTimelineEntry) => {
    return (
      <div key={entry.ulid} className="history-entry history-entry--edit history-entry--compact">
        <div className="history-entry__icon">✎</div>
        <div className="history-entry__content">
          <span className="history-entry__label">{entry.summary || 'Edit'}</span>
          {entry.doc_path && (
            <span className="history-entry__path">{entry.doc_path}</span>
          )}
        </div>
        <div className="history-entry__meta">
          {entry.actor && <span className="history-entry__actor">{entry.actor}</span>}
          <span className="history-entry__time">{formatTimestamp(entry.timestamp)}</span>
        </div>
      </div>
    );
  };

  const renderPinEvent = (entry: HistoryTimelineEntry) => {
    return (
      <div key={entry.ulid} className="history-entry history-entry--pin history-entry--compact">
        <div className="history-entry__icon">📌</div>
        <div className="history-entry__content">
          <span className="history-entry__label">
            Pinned {entry.analysis_kind}
          </span>
        </div>
        <div className="history-entry__time">{formatTimestamp(entry.timestamp)}</div>
      </div>
    );
  };

  const renderBaselineEvent = (entry: HistoryTimelineEntry) => {
    return (
      <div key={entry.ulid} className="history-entry history-entry--baseline">
        <div className="history-entry__icon">🚩</div>
        <div className="history-entry__content">
          <span className="history-entry__label">Project History Initialized</span>
          {entry.calculation_ids && entry.calculation_ids.length > 0 && (
            <span className="history-entry__counts">
              {entry.calculation_ids.length} calculation(s)
            </span>
          )}
        </div>
        <div className="history-entry__time">{formatTimestamp(entry.timestamp)}</div>
      </div>
    );
  };

  const renderGenericEvent = (entry: HistoryTimelineEntry) => {
    return (
      <div key={entry.ulid} className="history-entry history-entry--generic history-entry--compact">
        <div className="history-entry__icon">•</div>
        <div className="history-entry__content">
          <span className="history-entry__label">{entry.event_type}</span>
        </div>
        <div className="history-entry__time">{formatTimestamp(entry.timestamp)}</div>
      </div>
    );
  };

  if (!projectRoot) {
    return (
      <div className="history-panel history-panel--empty">
        <div className="history-panel__placeholder">
          <span className="history-panel__placeholder-icon">📜</span>
          <h2>Project History</h2>
          <p>Load a project to view its history timeline.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="history-panel">
      <div className="history-panel__header">
        <h2 className="history-panel__title">
          <span className="history-panel__icon">📜</span>
          Project History
        </h2>
        <div className="history-panel__controls">
          {/* Limit selector */}
          <select
            className="history-panel__limit-select"
            value={limit}
            onChange={(e) => setLimit(e.target.value as LimitOption)}
            disabled={loading}
            title="Limit number of entries"
          >
            <option value="all">All</option>
            <option value="50">Last 50</option>
            <option value="200">Last 200</option>
          </select>
          
          <button 
            className="history-panel__refresh"
            onClick={fetchHistory}
            disabled={loading}
            title="Refresh history"
          >
            {loading ? '⟳' : '↻'}
          </button>
          
          {timeline.length > 0 && (
            <button
              className="history-panel__delete-btn"
              onClick={() => setShowDeleteModal(true)}
              disabled={loading || isDeleting}
              title="Delete all history"
            >
              🗑️
            </button>
          )}
        </div>
      </div>
      
      {error && (
        <div className="history-panel__error">
          {error}
          <button 
            className="history-panel__error-dismiss"
            onClick={() => setError(null)}
          >
            ×
          </button>
        </div>
      )}
      
      {loading && timeline.length === 0 ? (
        <div className="history-panel__loading">
          Loading history...
        </div>
      ) : timeline.length === 0 ? (
        <div className="history-panel__empty-state">
          <span className="history-panel__empty-icon">📭</span>
          <h3>No History Yet</h3>
          <p>Run a calculation to start recording history.</p>
        </div>
      ) : (
        <div className="history-panel__timeline">
          {timeline.map(entry => renderTimelineEntry(entry))}
        </div>
      )}
      
      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div className="history-modal-overlay" onClick={() => !isDeleting && setShowDeleteModal(false)}>
          <div className="history-modal" onClick={(e) => e.stopPropagation()}>
            <div className="history-modal__header">
              <h3>Delete Project History?</h3>
            </div>
            <div className="history-modal__body">
              <p>
                This will permanently delete the <code>.history</code> directory 
                and all recorded runs, edits, and pins.
              </p>
              <p className="history-modal__note">
                ✓ Your project files (structures, calculations, steps) will NOT be affected.
              </p>
            </div>
            <div className="history-modal__footer">
              <button
                className="history-modal__btn history-modal__btn--cancel"
                onClick={() => setShowDeleteModal(false)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                className="history-modal__btn history-modal__btn--danger"
                onClick={handleDeleteHistory}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete History'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

