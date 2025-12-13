/**
 * CalculationRunTab - Run & Logs tab content
 * 
 * Shows only the latest job for the selected calculation.
 * Focuses on runtime state, not job history.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { useJobs, useJobDetail } from '../../hooks/useJobs';
import type { CalculationInfo, CalculationDetailResult, JobSummary } from '../../types/qv';
import './CalculationRunTab.css';

interface CalculationRunTabProps {
  projectRoot: string;
  calculation: CalculationInfo | CalculationDetailResult | null;
}

// Reuse StatusBadge from JobsPanel pattern
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

export function CalculationRunTab({ projectRoot, calculation }: CalculationRunTabProps) {
  const { jobs, isLoading, refresh } = useJobs({
    projectRoot,
    pollInterval: 3000,
    autoStart: true,
    limit: 50,
  });
  
  // Find latest job for this calculation
  const latestJob = useMemo<JobSummary | null>(() => {
    if (!calculation || !jobs.length) return null;
    
    const calculationSlug = calculation.slug || calculation.name;
    const calculationId = calculation.id;
    
    // Filter jobs for this calculation
    const calculationJobs = jobs.filter(job => {
      if (job.target_name === calculationSlug || job.target_name === calculation.name) {
        return true;
      }
      const jobAny = job as any;
      if (jobAny.target_calculation_id === calculationId || jobAny.target_calculation === calculationId) {
        return true;
      }
      return false;
    });
    
    if (calculationJobs.length === 0) return null;
    
    // Sort by most recent (started_at or created_at)
    return calculationJobs.sort((a, b) => {
      const aTime = a.started_at ? new Date(a.started_at).getTime() : new Date(a.created_at).getTime();
      const bTime = b.started_at ? new Date(b.started_at).getTime() : new Date(b.created_at).getTime();
      return bTime - aTime; // Descending
    })[0];
  }, [jobs, calculation]);
  
  // Use useJobDetail for the latest job
  const { job, logs, isLoading: isLoadingDetail, refresh: refreshJob, refreshLogs, cancelJob } = useJobDetail({
    jobId: latestJob?.id || null,
    pollInterval: 2000,
    autoStart: true,
  });
  
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  
  // Extract steps from job if available
  // NOTE: This useMemo must be called unconditionally (before any early returns)
  // to satisfy React hooks rules
  const jobSteps = useMemo(() => {
    if (!job) return [];
    if (job.steps && Array.isArray(job.steps) && job.steps.length > 0) {
      return job.steps;
    }
    const result = (job as any).result;
    if (result && result.steps && Array.isArray(result.steps) && result.steps.length > 0) {
      return result.steps;
    }
    return [];
  }, [job]);
  
  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);
  
  // Early returns AFTER all hooks have been called
  if (!calculation) {
    return (
      <div className="calculation-run-tab calculation-run-tab--empty">
        <p>No calculation selected</p>
      </div>
    );
  }
  
  if (isLoading && !latestJob) {
    return (
      <div className="calculation-run-tab calculation-run-tab--loading">
        <div className="loading-spinner" />
        <p>Loading jobs...</p>
      </div>
    );
  }
  
  if (!latestJob) {
    return (
      <div className="calculation-run-tab calculation-run-tab--empty">
        <div className="calculation-run-tab__empty-content">
          <span className="calculation-run-tab__empty-icon">⚡</span>
          <h3>No Run History</h3>
          <p>This calculation has never been run.</p>
          <p className="calculation-run-tab__hint">
            Use the "Run Calculation" button in the Overview & Steps tab to start a run.
          </p>
        </div>
      </div>
    );
  }
  
  if (isLoadingDetail && !job) {
    return (
      <div className="calculation-run-tab calculation-run-tab--loading">
        <div className="loading-spinner" />
        <p>Loading job details...</p>
      </div>
    );
  }
  
  if (!job) {
    return (
      <div className="calculation-run-tab calculation-run-tab--error">
        <p>Failed to load job details</p>
        <button onClick={refresh}>Retry</button>
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
  
  const getDuration = () => {
    if (!job.started_at) return '—';
    const start = new Date(job.started_at).getTime();
    const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
    const seconds = Math.floor((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSec = seconds % 60;
    return `${minutes}m ${remainingSec}s`;
  };
  
  return (
    <div className="calculation-run-tab" data-testid="qv-calc-run-logs-panel">
      <div className="calculation-run-tab__header">
        <div className="calculation-run-tab__title">
          <h3>Latest Run: {calculation.name}</h3>
          <code className="calculation-run-tab__job-id">#{shortId}</code>
          <StatusBadge status={job.status} />
        </div>
        <button className="calculation-run-tab__refresh" onClick={refresh} title="Refresh">
          🔄
        </button>
      </div>
      
      <div className="calculation-run-tab__content">
        {/* Job Info */}
        <div className="calculation-run-tab__section" data-testid="qv-calc-job-summary">
          <h4>Job Info</h4>
          <div className="calculation-run-tab__grid">
            <div className="calculation-run-tab__item">
              <span className="calculation-run-tab__label">Type</span>
              <span className="calculation-run-tab__value">{job.job_type.replace('_', ' ')}</span>
            </div>
            <div className="calculation-run-tab__item">
              <span className="calculation-run-tab__label">Created</span>
              <span className="calculation-run-tab__value">{formatTime(job.created_at)}</span>
            </div>
            <div className="calculation-run-tab__item">
              <span className="calculation-run-tab__label">Started</span>
              <span className="calculation-run-tab__value">{formatTime(job.started_at)}</span>
            </div>
            <div className="calculation-run-tab__item">
              <span className="calculation-run-tab__label">Completed</span>
              <span className="calculation-run-tab__value">{formatTime(job.completed_at)}</span>
            </div>
            <div className="calculation-run-tab__item">
              <span className="calculation-run-tab__label">Duration</span>
              <span className="calculation-run-tab__value">{getDuration()}</span>
            </div>
          </div>
        </div>
        
        {/* Step Progress (if available) */}
        {jobSteps.length > 0 && (
          <div className="calculation-run-tab__section">
            <h4>Step Progress</h4>
            <div className="calculation-run-tab__steps">
              {jobSteps.map((step: any, idx: number) => {
                const isCompleted = step.status === 'completed';
                const isRunning = step.status === 'running';
                const isFailed = step.status === 'failed';
                
                return (
                  <div key={idx} className={`calculation-run-tab__step ${
                    isRunning ? 'calculation-run-tab__step--running' :
                    isCompleted ? 'calculation-run-tab__step--completed' :
                    isFailed ? 'calculation-run-tab__step--failed' :
                    'calculation-run-tab__step--pending'
                  }`}>
                    <span className="calculation-run-tab__step-icon">
                      {isRunning ? '⚡' : isCompleted ? '✓' : isFailed ? '✗' : '⏳'}
                    </span>
                    <span className="calculation-run-tab__step-type">{step.step_type || step.type || 'Unknown'}</span>
                    <span className="calculation-run-tab__step-status">{step.status}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        
        {/* I/O Directory */}
        {job.io_dir && (
          <div className="calculation-run-tab__section">
            <h4>I/O Directory</h4>
            <div className="calculation-run-tab__path">
              <code title={job.io_dir}>{job.io_dir}</code>
              <button
                className="calculation-run-tab__reveal"
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
          <div className="calculation-run-tab__section calculation-run-tab__section--error">
            <h4>Error</h4>
            <pre className="calculation-run-tab__error">{job.error}</pre>
          </div>
        )}
        
        {/* Logs */}
        <div className="calculation-run-tab__section calculation-run-tab__section--logs">
          <div className="calculation-run-tab__logs-header">
            <h4>Output Logs</h4>
            <div className="calculation-run-tab__logs-actions">
              <label className="calculation-run-tab__auto-scroll">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                Auto-scroll
              </label>
              <button 
                className="calculation-run-tab__refresh-logs"
                onClick={refreshLogs}
                title="Refresh logs"
              >
                🔄
              </button>
            </div>
          </div>
          <div className="calculation-run-tab__logs" data-testid="qv-calc-job-logs">
            {logs?.output_file && (
              <div className="calculation-run-tab__logs-file">
                <code>{logs.output_file}</code>
              </div>
            )}
            {logs && logs.logs.length > 0 ? (
              <>
                {logs.has_more && (
                  <div className="calculation-run-tab__logs-truncated">
                    ... {logs.total_lines - logs.logs.length} earlier lines ...
                  </div>
                )}
                {logs.logs.map((line, idx) => (
                  <div key={idx} className="calculation-run-tab__log-line">
                    {line}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </>
            ) : (
              <div className="calculation-run-tab__logs-empty">
                {isActive ? 'Waiting for output...' : 'No output logs available'}
              </div>
            )}
          </div>
        </div>
        
        {/* Hint when completed */}
        {job.status === 'completed' && (
          <div className="calculation-run-tab__hint">
            <span>💡</span>
            <span>When the run is finished, switch to the Analysis tab to view results.</span>
          </div>
        )}
        
        {/* Actions */}
        <div className="calculation-run-tab__actions">
          {isActive && (
            <button
              className="calculation-run-tab__cancel"
              onClick={async () => {
                const cancelled = await cancelJob();
                if (cancelled) {
                  refreshJob();
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

