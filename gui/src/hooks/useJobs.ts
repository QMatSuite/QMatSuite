/**
 * useJobs - Hook for managing job polling and state
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { JobSummary, JobInfo, JobLogs, JobCounts, JobStatus } from '../types/qv';
import { normalizeProjectRoot } from '../utils/pathUtils';

interface UseJobsOptions {
  /** Polling interval in ms (default: 3000) */
  pollInterval?: number;
  /** Auto-start polling (default: true) */
  autoStart?: boolean;
  /** Filter by project root */
  projectRoot?: string;
  /** Filter by status */
  status?: JobStatus;
  /** Max jobs to fetch */
  limit?: number;
}

interface UseJobsResult {
  /** List of jobs */
  jobs: JobSummary[];
  /** Job counts by status */
  counts: JobCounts | null;
  /** Whether currently loading */
  isLoading: boolean;
  /** Last error message */
  error: string | null;
  /** Manually refresh jobs list */
  refresh: () => Promise<void>;
  /** Start polling */
  startPolling: () => void;
  /** Stop polling */
  stopPolling: () => void;
  /** Whether polling is active */
  isPolling: boolean;
}

/**
 * Hook for polling and managing jobs list
 */
export function useJobs(options: UseJobsOptions = {}): UseJobsResult {
  const {
    pollInterval = 3000,
    autoStart = true,
    projectRoot,
    status,
    limit = 50,
  } = options;
  
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [counts, setCounts] = useState<JobCounts | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(autoStart);
  
  // Refs for stable polling without dependencies on jobs state
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const jobsRef = useRef<JobSummary[]>([]);
  const inFlightRef = useRef(false);
  const isPollingRef = useRef(autoStart);
  const isInitialLoadRef = useRef(true);
  
  // Keep refs in sync with state
  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);
  
  useEffect(() => {
    isPollingRef.current = isPolling;
  }, [isPolling]);
  
  const fetchJobs = useCallback(async (isPollingCall = false) => {
    if (!window.qv) return;
    
    // Prevent re-entrant calls
    if (inFlightRef.current) {
      if (process.env.NODE_ENV === 'development') {
        console.log('[useJobs] poll skipped; inFlight=true');
      }
      return;
    }
    
    inFlightRef.current = true;
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[useJobs] poll start');
    }
    
    // Only set loading state on initial load, not on polling updates
    if (isInitialLoadRef.current || !isPollingCall) {
      setIsLoading(true);
    }
    setError(null);
    
    try {
      // Normalize project_root to absolute path (backend expects normalized paths for matching)
      // NOTE: Backend expects project_root as normalized absolute path, see tests/daemon/test_gui_job_and_step_flows.py
      const normalizedProjectRoot = normalizeProjectRoot(projectRoot);
      
      // Fetch jobs list
      // Backend contract: { project_root?: string (normalized absolute), limit?: int }
      const listResponse = await window.qv.request<{ jobs: JobSummary[]; count: number }>(
        'list_jobs',
        { 
          project_root: normalizedProjectRoot, // Only include if defined (backend handles None/undefined)
          status, 
          limit 
        }
      );
      
      if (listResponse.ok && listResponse.data) {
        setJobs(listResponse.data.jobs || []);
      } else if (listResponse.error) {
        setError(listResponse.error.message || 'Failed to fetch jobs');
      } else {
        // Empty response - no jobs (not an error)
        setJobs([]);
      }
      
      // Fetch counts
      const countsResponse = await window.qv.request<JobCounts>('job_counts', {});
      if (countsResponse.ok && countsResponse.data) {
        setCounts(countsResponse.data);
      }
      
      isInitialLoadRef.current = false;
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Failed to fetch jobs';
      setError(errorMsg);
      setJobs([]); // Clear jobs on error
      isInitialLoadRef.current = false;
    } finally {
      setIsLoading(false);
      inFlightRef.current = false;
    }
  }, [projectRoot, status, limit]);
  
  const startPolling = useCallback(() => {
    setIsPolling(true);
  }, []);
  
  const stopPolling = useCallback(() => {
    setIsPolling(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);
  
  // Store latest pollInterval in ref to avoid recreating scheduleNextPoll
  const pollIntervalRef = useRef(pollInterval);
  useEffect(() => {
    pollIntervalRef.current = pollInterval;
  }, [pollInterval]);
  
  // Store fetchJobs in ref so scheduleNextPoll can call it without dependency
  const fetchJobsRef = useRef(fetchJobs);
  useEffect(() => {
    fetchJobsRef.current = fetchJobs;
  }, [fetchJobs]);
  
  // Polling scheduler using chained setTimeout (not setInterval)
  // This ensures the next poll is scheduled only after the current one completes
  const scheduleNextPoll = useCallback(() => {
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    
    // Don't schedule if polling is disabled
    if (!isPollingRef.current) {
      return;
    }
    
    // Determine effective interval based on current jobs state (read from ref, not state)
    const hasRunningJobs = jobsRef.current.some(j => j.status === 'running' || j.status === 'pending');
    const currentPollInterval = pollIntervalRef.current;
    const effectivePollInterval = hasRunningJobs ? Math.min(currentPollInterval, 2000) : currentPollInterval;
    
    // Ensure interval is valid (not 0, NaN, or negative)
    const delay = Math.max(effectivePollInterval, 100);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`[useJobs] poll end; next in ${delay}ms; hasRunning=${hasRunningJobs}; inFlight=${inFlightRef.current}`);
    }
    
    // Schedule next poll
    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      if (isPollingRef.current) {
        fetchJobsRef.current(true).then(() => {
          scheduleNextPoll();
        }).catch(() => {
          // On error, still schedule next poll
          scheduleNextPoll();
        });
      }
    }, delay);
  }, []); // No dependencies - uses refs for all values
  
  // Initial fetch and polling setup
  useEffect(() => {
    // Reset initial load flag when projectRoot changes
    isInitialLoadRef.current = true;
    
    // Clear any existing polling
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    
    // Initial fetch
    fetchJobs(false).then(() => {
      // Start polling after initial fetch completes
      if (isPolling) {
        scheduleNextPoll();
      }
    });
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [isPolling, projectRoot, status, limit, fetchJobs, scheduleNextPoll]);
  
  // Handle polling state changes (when isPolling toggles)
  useEffect(() => {
    if (isPolling && !timeoutRef.current) {
      // Polling was just enabled, start scheduling
      scheduleNextPoll();
    } else if (!isPolling && timeoutRef.current) {
      // Polling was just disabled, stop scheduling
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, [isPolling, scheduleNextPoll]);
  
  return {
    jobs,
    counts,
    isLoading,
    error,
    refresh: () => fetchJobs(false), // Manual refresh is not polling
    startPolling,
    stopPolling,
    isPolling,
  };
}

// =============================================================================
// useJobDetail - Hook for a single job with logs
// =============================================================================

interface UseJobDetailOptions {
  jobId: string | null;
  pollInterval?: number;
  autoStart?: boolean;
}

interface UseJobDetailResult {
  job: JobInfo | null;
  logs: JobLogs | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  refreshLogs: () => Promise<void>;
  cancelJob: () => Promise<boolean>;
}

export function useJobDetail(options: UseJobDetailOptions): UseJobDetailResult {
  const { jobId, pollInterval = 2000, autoStart = true } = options;
  
  const [job, setJob] = useState<JobInfo | null>(null);
  const [logs, setLogs] = useState<JobLogs | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  
  const fetchJob = useCallback(async () => {
    if (!window.qv || !jobId) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await window.qv.request<JobInfo>('get_job_status', { job_id: jobId });
      
      if (response.ok && response.data) {
        setJob(response.data);
      } else if (response.error) {
        setError(response.error.message);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch job');
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);
  
  const fetchLogs = useCallback(async () => {
    if (!window.qv || !jobId) return;
    
    try {
      const response = await window.qv.request<JobLogs>('get_job_logs', {
        job_id: jobId,
        tail_lines: 200,
      });
      
      if (response.ok && response.data) {
        setLogs(response.data);
      }
    } catch (e) {
      // Ignore log fetch errors
    }
  }, [jobId]);
  
  const cancelJob = useCallback(async (): Promise<boolean> => {
    if (!window.qv || !jobId) return false;
    
    try {
      const response = await window.qv.request<{ cancelled: boolean }>('cancel_job', { job_id: jobId });
      if (response.ok && response.data?.cancelled) {
        await fetchJob();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [jobId, fetchJob]);
  
  // Initial fetch and polling
  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setLogs(null);
      return;
    }
    
    // Initial fetch
    fetchJob();
    fetchLogs();
    
    // Setup polling if job is not terminal
    const shouldPoll = autoStart && job && (job.status === 'pending' || job.status === 'running');
    
    if (shouldPoll) {
      intervalRef.current = setInterval(() => {
        fetchJob();
        fetchLogs();
      }, pollInterval);
    }
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, autoStart, pollInterval, fetchJob, fetchLogs, job?.status]);
  
  return {
    job,
    logs,
    isLoading,
    error,
    refresh: fetchJob,
    refreshLogs: fetchLogs,
    cancelJob,
  };
}

