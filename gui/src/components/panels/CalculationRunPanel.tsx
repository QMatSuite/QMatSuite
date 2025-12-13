/**
 * CalculationRunPanel - Shows jobs and logs for a specific calculation
 * 
 * Reuses logic from JobsPanel but filters jobs by calculation.
 */

import { useState, useMemo, useRef, useEffect } from 'react';
import { useJobs, useJobDetail } from '../../hooks/useJobs';
import type { CalculationInfo, CalculationDetailResult } from '../../types/qv';
import './CalculationRunPanel.css';

// Reuse StatusBadge from JobsPanel
interface StatusBadgeProps {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  size?: 'small' | 'medium';
}

function StatusBadge({ status, size = 'medium' }: StatusBadgeProps) {
  const icon = {
    pending: '⏳',
    running: '⚡',
    completed: '✓',
    failed: '✗',
    cancelled: '⊘',
  }[status];
  
  return (
    <span 
      className={`status-badge status-badge--${status} status-badge--${size}`}
      data-testid="qv-job-status"
    >
      <span className="status-badge__icon">{icon}</span>
      <span className="status-badge__label">{status}</span>
    </span>
  );
}

interface CalculationRunPanelProps {
  projectRoot: string;
  calculation: CalculationInfo | CalculationDetailResult | null;
}

export function CalculationRunPanel({ projectRoot, calculation }: CalculationRunPanelProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  
  // Fetch all jobs for the project
  const { jobs, isLoading, error, refresh } = useJobs({
    projectRoot,
    pollInterval: 3000,
    autoStart: true,
    limit: 50,
  });
  
  // Filter jobs for this calculation
  const calculationJobs = useMemo(() => {
    if (!calculation) return [];
    
    const calculationSlug = calculation.slug || calculation.name;
    const calculationId = calculation.id;
    
    return jobs.filter(job => {
      // Match by target_name (slug) or target_calculation_id
      if (job.target_name === calculationSlug || job.target_name === calculation.name) {
        return true;
      }
      // Also check if job has target_calculation_id field
      const jobAny = job as any;
      if (jobAny.target_calculation_id === calculationId || jobAny.target_calculation === calculationId) {
        return true;
      }
      return false;
    }).sort((a, b) => {
      // Sort by most recent first
      const aTime = a.started_at ? new Date(a.started_at).getTime() : new Date(a.created_at).getTime();
      const bTime = b.started_at ? new Date(b.started_at).getTime() : new Date(b.created_at).getTime();
      return bTime - aTime;
    });
  }, [jobs, calculation]);
  
  // Auto-select most recent job
  useEffect(() => {
    if (calculationJobs.length > 0 && !selectedJobId) {
      setSelectedJobId(calculationJobs[0].id);
    }
  }, [calculationJobs, selectedJobId]);
  
  if (!calculation) {
    return (
      <div className="calculation-run-panel calculation-run-panel--empty">
        <p>No calculation selected</p>
      </div>
    );
  }
  
  if (isLoading && calculationJobs.length === 0) {
    return (
      <div className="calculation-run-panel calculation-run-panel--loading">
        <div className="loading-spinner" />
        <p>Loading jobs...</p>
      </div>
    );
  }
  
  return (
    <div className="calculation-run-panel">
      <div className="calculation-run-panel__header">
        <h3>Jobs for {calculation.name}</h3>
        <button className="refresh-btn" onClick={refresh} title="Refresh jobs">
          🔄
        </button>
      </div>
      
      {error && (
        <div className="calculation-run-panel__error">
          <span>⚠️ {error}</span>
        </div>
      )}
      
      <div className="calculation-run-panel__content">
        {/* Job List */}
        <div className="calculation-run-panel__job-list">
          {calculationJobs.length === 0 ? (
            <div className="calculation-run-panel__empty">
              <p>No jobs found for this calculation</p>
              <p className="calculation-run-panel__hint">Run the calculation to see jobs here</p>
            </div>
          ) : (
            calculationJobs.map(job => (
              <div
                key={job.id}
                className={`calculation-run-panel__job-item ${
                  selectedJobId === job.id ? 'calculation-run-panel__job-item--selected' : ''
                }`}
                onClick={() => setSelectedJobId(job.id)}
              >
                <div className="calculation-run-panel__job-header">
                  <code className="calculation-run-panel__job-id">#{job.id.slice(0, 8)}</code>
                  <StatusBadge status={job.status} size="small" />
                </div>
                <div className="calculation-run-panel__job-meta">
                  <span className="calculation-run-panel__job-type">{job.job_type.replace('_', ' ')}</span>
                  <span className="calculation-run-panel__job-time">
                    {new Date(job.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
        
        {/* Job Detail */}
        {selectedJobId && (
          <CalculationJobDetail
            jobId={selectedJobId}
            onClose={() => setSelectedJobId(null)}
          />
        )}
      </div>
    </div>
  );
}

// Job Detail Component (reusing logic from JobsPanel)
interface CalculationJobDetailProps {
  jobId: string;
  onClose?: () => void;
}

function CalculationJobDetail({ jobId, onClose }: CalculationJobDetailProps) {
  const { job, logs, isLoading, error, refresh, refreshLogs, cancelJob } = useJobDetail({
    jobId,
    pollInterval: 2000,
    autoStart: true,
  });
  
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  
  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);
  
  if (isLoading && !job) {
    return (
      <div className="calculation-job-detail calculation-job-detail--loading">
        <div className="loading-spinner" />
        <p>Loading job details...</p>
      </div>
    );
  }
  
  if (error || !job) {
    return (
      <div className="calculation-job-detail calculation-job-detail--error">
        <p>Failed to load job: {error || 'Not found'}</p>
        {onClose && <button onClick={onClose}>Close</button>}
      </div>
    );
  }
  
  const shortId = job.id.slice(0, 8);
  const isActive = job.status === 'pending' || job.status === 'running';
  
  const formatTime = (isoStr: string | null) => {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleString();
  };
  
  return (
    <div className="calculation-job-detail">
      <div className="calculation-job-detail__header">
        <div className="calculation-job-detail__title">
          <code>#{shortId}</code>
          <StatusBadge status={job.status} />
        </div>
        {onClose && (
          <button className="calculation-job-detail__close" onClick={onClose}>×</button>
        )}
      </div>
      
      <div className="calculation-job-detail__content">
        {/* Job Info */}
        <div className="calculation-job-detail__section">
          <h4>Job Info</h4>
          <div className="calculation-job-detail__grid">
            <div className="calculation-job-detail__item">
              <span className="calculation-job-detail__label">Type</span>
              <span className="calculation-job-detail__value">{job.job_type.replace('_', ' ')}</span>
            </div>
            <div className="calculation-job-detail__item">
              <span className="calculation-job-detail__label">Target</span>
              <span className="calculation-job-detail__value">{job.target_name || '—'}</span>
            </div>
            <div className="calculation-job-detail__item">
              <span className="calculation-job-detail__label">Created</span>
              <span className="calculation-job-detail__value">{formatTime(job.created_at)}</span>
            </div>
            <div className="calculation-job-detail__item">
              <span className="calculation-job-detail__label">Started</span>
              <span className="calculation-job-detail__value">{formatTime(job.started_at)}</span>
            </div>
            <div className="calculation-job-detail__item">
              <span className="calculation-job-detail__label">Completed</span>
              <span className="calculation-job-detail__value">{formatTime(job.completed_at)}</span>
            </div>
          </div>
        </div>
        
        {/* I/O Directory */}
        {job.io_dir && (
          <div className="calculation-job-detail__section">
            <h4>I/O Directory</h4>
            <div className="calculation-job-detail__path">
              <code title={job.io_dir}>{job.io_dir}</code>
              <button
                className="calculation-job-detail__reveal"
                onClick={() => window.qv?.revealPath?.(job.io_dir!)}
                title={`Reveal: ${job.io_dir}`}
              >
                📂 Reveal
              </button>
            </div>
          </div>
        )}
        
        {/* Error */}
        {job.error && (
          <div className="calculation-job-detail__section calculation-job-detail__section--error">
            <h4>Error</h4>
            <pre className="calculation-job-detail__error">{job.error}</pre>
          </div>
        )}
        
        {/* Logs */}
        <div className="calculation-job-detail__section calculation-job-detail__section--logs">
          <div className="calculation-job-detail__logs-header">
            <h4>Output Logs</h4>
            <div className="calculation-job-detail__logs-actions">
              <label className="calculation-job-detail__auto-scroll">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                Auto-scroll
              </label>
              <button 
                className="calculation-job-detail__refresh-logs"
                onClick={refreshLogs}
                title="Refresh logs"
              >
                🔄
              </button>
            </div>
          </div>
          <div className="calculation-job-detail__logs">
            {logs?.output_file && (
              <div className="calculation-job-detail__logs-file">
                <code>{logs.output_file}</code>
              </div>
            )}
            {logs && logs.logs.length > 0 ? (
              <>
                {logs.has_more && (
                  <div className="calculation-job-detail__logs-truncated">
                    ... {logs.total_lines - logs.logs.length} earlier lines ...
                  </div>
                )}
                {logs.logs.map((line, idx) => (
                  <div key={idx} className="calculation-job-detail__log-line">
                    {line}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </>
            ) : (
              <div className="calculation-job-detail__logs-empty">
                {isActive ? 'Waiting for output...' : 'No output logs available'}
              </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="calculation-job-detail__actions">
          {isActive && (
            <button
              className="calculation-job-detail__cancel"
              onClick={async () => {
                const cancelled = await cancelJob();
                if (cancelled) {
                  refresh();
                }
              }}
            >
              Cancel Job
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

