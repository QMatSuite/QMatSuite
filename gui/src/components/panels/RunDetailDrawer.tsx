/**
 * RunDetailDrawer - Slide-out drawer showing run revision details.
 *
 * Uses get_run_revision RPC (same endpoint as CLI `qv history show`).
 */

import { useState, useEffect } from 'react';
import type { QVResult } from '../../types/qv';
import './RunDetailDrawer.css';

type RunRevision = NonNullable<QVResult<'get_run_revision'>['revision']>;

interface RunDetailDrawerProps {
  projectRoot: string;
  runUlid: string;
  onClose: () => void;
}

export function RunDetailDrawer({ projectRoot, runUlid, onClose }: RunDetailDrawerProps) {
  const [revision, setRevision] = useState<RunRevision | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSnapshot, setShowSnapshot] = useState(false);

  useEffect(() => {
    if (!projectRoot || !runUlid || !window.qv) return;

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await window.qv.request<QVResult<'get_run_revision'>>(
          'get_run_revision',
          { project_root: projectRoot, run_ulid: runUlid },
        );

        if (cancelled) return;

        if (response.ok && response.data?.revision) {
          setRevision(response.data.revision);
        } else {
          setError(response.data?.error || response.error?.message || 'Failed to load run details');
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load run details');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [projectRoot, runUlid]);

  const shortUlid = (ulid: string) => ulid.length > 10 ? ulid.slice(0, 10) + '...' : ulid;

  const formatTimestamp = (ts?: string) => {
    if (!ts) return '-';
    try {
      return new Date(ts).toLocaleString(undefined, {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return ts; }
  };

  const statusClass = revision?.status === 'success' ? 'run-drawer__badge--success' : 'run-drawer__badge--failed';

  return (
    <div className="run-drawer-overlay" onClick={onClose}>
      <div className="run-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="run-drawer__header">
          <h3 className="run-drawer__title">
            Run {shortUlid(runUlid)}
          </h3>
          <button className="run-drawer__close" onClick={onClose} title="Close">
            &times;
          </button>
        </div>

        {loading ? (
          <div className="run-drawer__loading">Loading run details...</div>
        ) : error ? (
          <div className="run-drawer__error">{error}</div>
        ) : revision ? (
          <div className="run-drawer__body">
            <div className="run-drawer__meta">
              <div className="run-drawer__meta-row">
                <span className="run-drawer__label">Status</span>
                <span className={`run-drawer__badge ${statusClass}`}>
                  {revision.status || 'unknown'}
                </span>
              </div>
              {revision.engine && (
                <div className="run-drawer__meta-row">
                  <span className="run-drawer__label">Engine</span>
                  <span>{revision.engine}</span>
                </div>
              )}
              <div className="run-drawer__meta-row">
                <span className="run-drawer__label">Started</span>
                <span>{formatTimestamp(revision.started_at)}</span>
              </div>
              <div className="run-drawer__meta-row">
                <span className="run-drawer__label">Finished</span>
                <span>{formatTimestamp(revision.finished_at)}</span>
              </div>
              <div className="run-drawer__meta-row">
                <span className="run-drawer__label">ULID</span>
                <span className="run-drawer__mono">{revision.ulid}</span>
              </div>
              <div className="run-drawer__meta-row">
                <span className="run-drawer__label">Calc</span>
                <span className="run-drawer__mono">{shortUlid(revision.calc_ulid)}</span>
              </div>
              {revision.snapshot_sha && (
                <div className="run-drawer__meta-row">
                  <span className="run-drawer__label">Snapshot</span>
                  <span className="run-drawer__mono">{revision.snapshot_sha.slice(0, 12)}...</span>
                </div>
              )}
            </div>

            {revision.step_ulids && revision.step_ulids.length > 0 && (
              <div className="run-drawer__section">
                <h4>Steps ({revision.step_ulids.length})</h4>
                <table className="run-drawer__steps-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Step ULID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {revision.step_ulids.map((stepUlid, idx) => (
                      <tr key={stepUlid}>
                        <td>{idx + 1}</td>
                        <td className="run-drawer__mono">{shortUlid(stepUlid)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {revision.snapshot && (
              <div className="run-drawer__section">
                <button
                  className="run-drawer__toggle"
                  onClick={() => setShowSnapshot(!showSnapshot)}
                >
                  {showSnapshot ? '▼' : '▶'} Snapshot Data
                </button>
                {showSnapshot && (
                  <pre className="run-drawer__snapshot">
                    {JSON.stringify(revision.snapshot, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
