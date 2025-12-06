/**
 * JobsPanel - Job list and detail view for QE runs
 */

import { useState, useEffect, useRef } from 'react';
import { useJobs, useJobDetail } from '../../hooks/useJobs';
import type { JobSummary, JobStatus } from '../../types/qv';
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
    <span className={`status-badge status-badge--${status} status-badge--${size}`}>
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

function JobListItem({ job, isSelected, onSelect }: JobListItemProps) {
  const shortId = job.id.slice(0, 8);
  const createdDate = new Date(job.created_at);
  const timeStr = createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  
  return (
    <button
      className={`job-list-item ${isSelected ? 'job-list-item--selected' : ''}`}
      onClick={() => onSelect(job)}
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
  onViewAnalysis?: (workflowSlug: string) => void;
}

function JobDetailPanel({ jobId, onClose, onViewAnalysis }: JobDetailPanelProps) {
  const { job, logs, isLoading, error, cancelJob, refresh, refreshLogs } = useJobDetail({
    jobId,
    pollInterval: 2000,
    autoStart: true,
  });
  
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
    <div className="job-detail-panel">
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
          {/* View Analysis button for completed workflow jobs */}
          {job.status === 'completed' && 
           job.job_type === 'run_workflow' && 
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
  onViewAnalysis?: (workflowSlug: string) => void;
}

export function JobsPanel({ projectRoot, onViewAnalysis }: JobsPanelProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const { jobs, counts, isLoading, error, refresh, isPolling, startPolling, stopPolling } = useJobs({
    projectRoot,
    pollInterval: 3000,
    autoStart: true,
    limit: 50,
  });
  
  const handleSelectJob = (job: JobSummary) => {
    setSelectedJobId(job.id);
  };
  
  const handleCloseDetail = () => {
    setSelectedJobId(null);
  };
  
  return (
    <div className="jobs-panel">
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
        <div className="jobs-panel__list">
          {isLoading && jobs.length === 0 ? (
            <div className="jobs-panel__loading">
              <div className="loading-spinner" />
              <p>Loading jobs...</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="jobs-panel__empty">
              <span className="jobs-panel__empty-icon">📋</span>
              <h3>No Jobs</h3>
              <p>Run a workflow to create jobs.</p>
            </div>
          ) : (
            jobs.map((job) => (
              <JobListItem
                key={job.id}
                job={job}
                isSelected={selectedJobId === job.id}
                onSelect={handleSelectJob}
              />
            ))
          )}
        </div>
        
        {/* Job Detail */}
        {selectedJobId && (
          <div className="jobs-panel__detail">
            <JobDetailPanel
              jobId={selectedJobId}
              onClose={handleCloseDetail}
              onViewAnalysis={onViewAnalysis}
            />
          </div>
        )}
      </div>
    </div>
  );
}

