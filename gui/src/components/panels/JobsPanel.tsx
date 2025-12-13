/**
 * JobsPanel - Job list and detail view for QE runs
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { useJobs, useJobDetail } from '../../hooks/useJobs';
import type { JobSummary, JobInfo, JobStatus, JobStepInfo } from '../../types/qv';
import './JobsPanel.css';

// =============================================================================
// Job Status Badge
// =============================================================================

interface StatusBadgeProps {
  status: JobStatus;
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

// =============================================================================
// Job List Item
// =============================================================================

interface JobListItemProps {
  job: JobSummary;
  isSelected: boolean;
  onSelect: (job: JobSummary) => void;
}

// B) Step progress visualization component
interface StepStepperProps {
  steps: JobStepInfo[];
  currentStepIndex?: number;
}

function StepStepper({ steps, currentStepIndex }: StepStepperProps) {
  if (steps.length === 0) return null;
  
  return (
    <div className="job-step-stepper">
      <div className="job-step-stepper__track">
        {steps.map((step, idx) => {
          const isCompleted = step.status === 'completed';
          const isRunning = step.status === 'running';
          const isFailed = step.status === 'failed';
          const isPending = step.status === 'pending';
          
          return (
            <div key={idx} className="job-step-stepper__step">
              <div
                className={`job-step-stepper__dot ${
                  isRunning ? 'job-step-stepper__dot--running' :
                  isCompleted ? 'job-step-stepper__dot--completed' :
                  isFailed ? 'job-step-stepper__dot--failed' :
                  isPending ? 'job-step-stepper__dot--pending' :
                  'job-step-stepper__dot--pending'
                }`}
                title={`${step.step_type}: ${step.status}`}
              />
              {idx < steps.length - 1 && (
                <div
                  className={`job-step-stepper__connector ${
                    isCompleted ? 'job-step-stepper__connector--completed' :
                    isRunning ? 'job-step-stepper__connector--active' :
                    'job-step-stepper__connector--pending'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="job-step-stepper__labels">
        {steps.map((step, idx) => (
          <div key={idx} className="job-step-stepper__label" title={step.step_type}>
            {step.step_type}
          </div>
        ))}
      </div>
      {/* Compact summary */}
      {currentStepIndex !== undefined && (
        <div className="job-step-stepper__summary">
          {(() => {
            const runningCount = steps.filter(s => s.status === 'running').length;
            const completedCount = steps.filter(s => s.status === 'completed').length;
            const total = steps.length;
            const currentStep = steps[currentStepIndex];
            
            if (runningCount > 0) {
              return `${completedCount + runningCount}/${total} running: ${currentStep?.step_type || '...'}`;
            } else if (completedCount === total) {
              return `${total}/${total} completed`;
            } else {
              return `${completedCount}/${total} completed`;
            }
          })()}
        </div>
      )}
    </div>
  );
}

function JobListItem({ job, isSelected, onSelect }: JobListItemProps) {
  const shortId = job.id.slice(0, 8);
  const createdDate = new Date(job.created_at);
  const timeStr = createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  
  // Extract steps from job (may be in job.steps or job.result.steps)
  const steps: JobStepInfo[] = useMemo(() => {
    // First try job.steps (if backend includes it in list_jobs response or merged from detail)
    if (job.steps && Array.isArray(job.steps) && job.steps.length > 0) {
      return job.steps;
    }
    // Fallback: try to extract from result.steps (for completed/running jobs)
    // This works for both list_jobs (if backend includes result.steps in summary) 
    // and get_job_status (full detail)
    const result = (job as any).result;
    if (result && result.steps && Array.isArray(result.steps) && result.steps.length > 0) {
      return result.steps;
    }
    return [];
  }, [job]);
  
  // Find current step: first running, else last completed
  const currentStepIndex = useMemo(() => {
    if (steps.length === 0) return undefined;
    const runningIdx = steps.findIndex(s => s.status === 'running');
    if (runningIdx >= 0) return runningIdx;
    const lastCompletedIdx = steps.map((s, i) => s.status === 'completed' ? i : -1).filter(i => i >= 0).pop();
    return lastCompletedIdx;
  }, [steps]);
  
  return (
    <button
      className={`job-list-item ${isSelected ? 'job-list-item--selected' : ''}`}
      onClick={() => onSelect(job)}
      data-testid="qv-job-row"
      data-job-id={job.id}
    >
      <div className="job-list-item__header">
        <code className="job-list-item__id">#{shortId}</code>
        <StatusBadge status={job.status} size="small" />
      </div>
      <div className="job-list-item__main">
        <span className="job-list-item__type">{job.job_type.replace('_', ' ')}</span>
        {job.target_name && (
          <span className="job-list-item__target">{job.target_name}</span>
        )}
      </div>
      {/* B) Step progress stepper */}
      {steps.length > 0 && (
        <div className="job-list-item__stepper">
          <StepStepper steps={steps} currentStepIndex={currentStepIndex} />
        </div>
      )}
      <div className="job-list-item__footer">
        <span className="job-list-item__time">{timeStr}</span>
        {job.last_log_line && (
          <span className="job-list-item__log-preview" title={job.last_log_line}>
            {job.last_log_line.slice(0, 50)}...
          </span>
        )}
      </div>
    </button>
  );
}

// =============================================================================
// Job Detail Panel
// =============================================================================

interface JobDetailPanelProps {
  jobId: string;
  onClose: () => void;
  onViewAnalysis?: (calculationSlug: string) => void;
  onJobUpdate?: (job: JobInfo) => void;
}

function JobDetailPanel({ jobId, onClose, onViewAnalysis, onJobUpdate }: JobDetailPanelProps) {
  const { job, logs, isLoading, error, cancelJob, refresh, refreshLogs } = useJobDetail({
    jobId,
    pollInterval: 2000,
    autoStart: true,
  });
  
  // C) Notify parent when job updates so it can merge steps into list
  useEffect(() => {
    if (job && onJobUpdate) {
      // Always update, even if steps are empty (to clear stale data)
      onJobUpdate(job);
    }
  }, [job, onJobUpdate]);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  
  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);
  
  if (isLoading && !job) {
    return (
      <div className="job-detail-panel job-detail-panel--loading">
        <div className="loading-spinner" />
        <p>Loading job details...</p>
      </div>
    );
  }
  
  if (error || !job) {
    return (
      <div className="job-detail-panel job-detail-panel--error">
        <p>Failed to load job: {error || 'Not found'}</p>
        <button onClick={onClose}>Close</button>
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
    <div className="job-detail-panel" data-testid="qv-job-detail">
      <div className="job-detail-panel__header">
        <div className="job-detail-panel__title">
          <code>#{shortId}</code>
          <StatusBadge status={job.status} />
        </div>
        <button className="job-detail-panel__close" onClick={onClose}>×</button>
      </div>
      
      <div className="job-detail-panel__content">
        {/* Info Section */}
        <div className="job-detail-section">
          <h3>Job Info</h3>
          <div className="job-detail-grid">
            <div className="job-detail-item">
              <span className="job-detail-label">Type</span>
              <span className="job-detail-value">{job.job_type.replace('_', ' ')}</span>
            </div>
            <div className="job-detail-item">
              <span className="job-detail-label">Target</span>
              <span className="job-detail-value">{job.target_name || '—'}</span>
            </div>
            <div className="job-detail-item">
              <span className="job-detail-label">Created</span>
              <span className="job-detail-value">{formatTime(job.created_at)}</span>
            </div>
            <div className="job-detail-item">
              <span className="job-detail-label">Started</span>
              <span className="job-detail-value">{formatTime(job.started_at)}</span>
            </div>
            <div className="job-detail-item">
              <span className="job-detail-label">Completed</span>
              <span className="job-detail-value">{formatTime(job.completed_at)}</span>
            </div>
            <div className="job-detail-item">
              <span className="job-detail-label">Duration</span>
              <span className="job-detail-value">{getDuration()}</span>
            </div>
          </div>
        </div>
        
        {/* C) QE I/O Locations Section */}
        {job.io_dir && (
          <div className="job-detail-section">
            <h3>I/O Directory</h3>
            <div className="job-detail-paths">
              <div className="job-detail-path-row">
                <div className="job-detail-path-value">
                  <code 
                    className="job-detail-path-text" 
                    title={job.io_dir}
                  >
                    {job.io_dir}
                  </code>
                  <button
                    className="job-detail-path-reveal"
                    onClick={() => window.qv?.revealPath?.(job.io_dir!)}
                    title={`Reveal in Finder: ${job.io_dir}`}
                  >
                    📂 Reveal
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Error Section */}
        {job.error && (
          <div className="job-detail-section job-detail-section--error">
            <h3>Error</h3>
            <pre className="job-detail-error">{job.error}</pre>
          </div>
        )}
        
        {/* Result Section */}
        {job.result && job.status === 'completed' && (
          <div className="job-detail-section">
            <h3>Result</h3>
            <pre className="job-detail-result">
              {JSON.stringify(job.result, null, 2)}
            </pre>
          </div>
        )}
        
        {/* Logs Section */}
        <div className="job-detail-section job-detail-section--logs">
          <div className="job-detail-logs-header">
            <h3>Output Logs</h3>
            <div className="job-detail-logs-actions">
              <label className="auto-scroll-toggle">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                Auto-scroll
              </label>
              <button 
                className="refresh-logs-btn"
                onClick={refreshLogs}
                title="Refresh logs"
              >
                🔄
              </button>
            </div>
          </div>
          <div className="job-detail-logs">
            {logs?.output_file && (
              <div className="job-detail-logs-file">
                <code>{logs.output_file}</code>
              </div>
            )}
            {logs && logs.logs.length > 0 ? (
              <>
                {logs.has_more && (
                  <div className="job-detail-logs-truncated">
                    ... {logs.total_lines - logs.logs.length} earlier lines ...
                  </div>
                )}
                {logs.logs.map((line, idx) => (
                  <div key={idx} className="job-detail-log-line">
                    {line}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </>
            ) : (
              <div className="job-detail-logs-empty">
                {isActive ? 'Waiting for output...' : 'No output logs available'}
              </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="job-detail-actions">
          {isActive && (
            <button
              className="job-action-btn job-action-btn--cancel"
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
          {/* View Analysis button for completed calculation jobs */}
          {job.status === 'completed' && 
           job.job_type === 'run_calculation' && 
           job.target_name && 
           onViewAnalysis && (
            <button
              className="job-action-btn job-action-btn--primary"
              onClick={() => onViewAnalysis(job.target_name!)}
            >
              📊 View Analysis
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Jobs Panel
// =============================================================================

interface JobsPanelProps {
  projectRoot?: string;
  onViewAnalysis?: (calculationSlug: string) => void;
}

export function JobsPanel({ projectRoot, onViewAnalysis }: JobsPanelProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJobDetail, setSelectedJobDetail] = useState<JobInfo | null>(null);
  const didAutoSelectRef = useRef(false);
  const { jobs, counts, isLoading, error, refresh, isPolling, startPolling, stopPolling } = useJobs({
    projectRoot,
    pollInterval: 3000, // Base interval; hook will use 2s when jobs are running
    autoStart: true,
    limit: 50,
  });
  
  // A) Auto-select most recent job on panel entry
  // D) Loop prevention: This effect ONLY sets selectedJobId state.
  // It does NOT trigger list refresh or cause re-renders that would trigger more updates.
  useEffect(() => {
    // Reset auto-select flag when projectRoot changes (new panel mount)
    if (projectRoot) {
      didAutoSelectRef.current = false;
    }
  }, [projectRoot]);
  
  // D) Loop prevention: This effect is carefully guarded to prevent infinite loops:
  // - Only runs when jobs or selectedJobId changes (not on every render)
  // - Only sets selectedJobId (doesn't trigger list refresh)
  // - Uses ref to track auto-select state (doesn't cause re-renders)
  // - Manual selection sets the ref flag to prevent override
  useEffect(() => {
    // Only auto-select if:
    // 1. Jobs list is non-empty
    // 2. No job is currently selected
    // 3. We haven't auto-selected yet (one-time per mount)
    if (jobs.length > 0 && selectedJobId === null && !didAutoSelectRef.current) {
      // Find most recent job: sort by started_at if present, else created_at (descending)
      const mostRecent = [...jobs].sort((a, b) => {
        const aTime = a.started_at ? new Date(a.started_at).getTime() : new Date(a.created_at).getTime();
        const bTime = b.started_at ? new Date(b.started_at).getTime() : new Date(b.created_at).getTime();
        return bTime - aTime; // Descending (most recent first)
      })[0];
      
      if (mostRecent) {
        setSelectedJobId(mostRecent.id);
        didAutoSelectRef.current = true;
      }
    }
    
    // If selected job disappeared from list, fall back to most recent
    // D) Loop prevention: This only runs when selectedJobId exists but job is missing from list
    if (selectedJobId && !jobs.find(j => j.id === selectedJobId)) {
      if (jobs.length > 0) {
        const mostRecent = [...jobs].sort((a, b) => {
          const aTime = a.started_at ? new Date(a.started_at).getTime() : new Date(a.created_at).getTime();
          const bTime = b.started_at ? new Date(b.started_at).getTime() : new Date(b.created_at).getTime();
          return bTime - aTime;
        })[0];
        if (mostRecent) {
          setSelectedJobId(mostRecent.id);
        }
      } else {
        setSelectedJobId(null);
      }
    }
  }, [jobs, selectedJobId]);
  
  const handleSelectJob = (job: JobSummary) => {
    setSelectedJobId(job.id);
    // Mark that user has manually selected (prevent auto-select override)
    didAutoSelectRef.current = true;
  };
  
  const handleCloseDetail = () => {
    setSelectedJobId(null);
    // Reset auto-select flag when user closes detail (allow re-auto-select on next entry)
    didAutoSelectRef.current = false;
  };
  
  return (
    <div className="jobs-panel" data-testid="qv-jobs-view">
      {/* Header */}
      <div className="jobs-panel__header">
        <div className="jobs-panel__title">
          <h2>Jobs</h2>
          {counts && (
            <div className="jobs-panel__counts">
              {counts.running > 0 && (
                <span className="count-badge count-badge--running">
                  {counts.running} running
                </span>
              )}
              {counts.pending > 0 && (
                <span className="count-badge count-badge--pending">
                  {counts.pending} pending
                </span>
              )}
            </div>
          )}
        </div>
        <div className="jobs-panel__actions">
          <button 
            className="jobs-panel__refresh"
            onClick={refresh}
            disabled={isLoading}
          >
            🔄 Refresh
          </button>
          <button
            className={`jobs-panel__polling ${isPolling ? 'active' : ''}`}
            onClick={isPolling ? stopPolling : startPolling}
          >
            {isPolling ? '⏸ Pause' : '▶ Auto'}
          </button>
        </div>
      </div>
      
      {/* Error Banner */}
      {error && (
        <div className="jobs-panel__error">
          {error}
        </div>
      )}
      
      {/* Content */}
      <div className="jobs-panel__content">
        {/* Job List */}
        <div className="jobs-panel__list" data-testid="qv-jobs-list">
          {isLoading && jobs.length === 0 ? (
            <div className="jobs-panel__loading" data-testid="qv-jobs-loading">
              <div className="loading-spinner" />
              <p>Loading jobs...</p>
            </div>
          ) : error && jobs.length === 0 ? (
            <div className="jobs-panel__empty" data-testid="qv-jobs-error">
              <span className="jobs-panel__empty-icon">⚠️</span>
              <h3>Error Loading Jobs</h3>
              <p>{error}</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="jobs-panel__empty" data-testid="qv-jobs-empty">
              <span className="jobs-panel__empty-icon">📋</span>
              <h3>No Jobs</h3>
              <p>Run a calculation to create jobs.</p>
              {!projectRoot && (
                <p className="jobs-panel__empty-hint">Open a project to see jobs</p>
              )}
            </div>
          ) : (
            jobs.map((job) => {
              // C) Merge detail steps into list job for selected job to show live updates
              let jobWithSteps = job;
              if (selectedJobId === job.id && selectedJobDetail) {
                // Extract steps from detail (may be in steps or result.steps)
                const detailSteps = selectedJobDetail.steps && selectedJobDetail.steps.length > 0
                  ? selectedJobDetail.steps
                  : (selectedJobDetail.result as any)?.steps;
                
                if (detailSteps && Array.isArray(detailSteps) && detailSteps.length > 0) {
                  // Merge detail steps to show live progress
                  jobWithSteps = { ...job, steps: detailSteps };
                }
              }
              return (
                <JobListItem
                  key={job.id}
                  job={jobWithSteps}
                  isSelected={selectedJobId === job.id}
                  onSelect={handleSelectJob}
                />
              );
            })
          )}
        </div>
        
        {/* Job Detail */}
        {selectedJobId && (
          <div className="jobs-panel__detail">
            <JobDetailPanel
              jobId={selectedJobId}
              onClose={handleCloseDetail}
              onViewAnalysis={onViewAnalysis}
              onJobUpdate={setSelectedJobDetail}
            />
          </div>
        )}
      </div>
    </div>
  );
}

