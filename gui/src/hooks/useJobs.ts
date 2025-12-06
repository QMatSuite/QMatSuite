/**
 * useJobs - Hook for managing job polling and state
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { JobSummary, JobInfo, JobLogs, JobCounts, JobStatus } from '../types/qv';

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
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  
  const fetchJobs = useCallback(async () => {
    if (!window.qv) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Fetch jobs list
      const listResponse = await window.qv.request<{ jobs: JobSummary[]; count: number }>(
        'list_jobs',
        { project_root: projectRoot, status, limit }
      );
      
      if (listResponse.ok && listResponse.data) {
        setJobs(listResponse.data.jobs);
      } else if (listResponse.error) {
        setError(listResponse.error.message);
      }
      
      // Fetch counts
      const countsResponse = await window.qv.request<JobCounts>('job_counts', {});
      if (countsResponse.ok && countsResponse.data) {
        setCounts(countsResponse.data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch jobs');
    } finally {
      setIsLoading(false);
    }
  }, [projectRoot, status, limit]);
  
  const startPolling = useCallback(() => {
    setIsPolling(true);
  }, []);
  
  const stopPolling = useCallback(() => {
    setIsPolling(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);
  
  // Initial fetch and polling setup
  useEffect(() => {
    // Initial fetch
    fetchJobs();
    
    // Setup polling if enabled
    if (isPolling) {
      intervalRef.current = setInterval(fetchJobs, pollInterval);
    }
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isPolling, pollInterval, fetchJobs]);
  
  return {
    jobs,
    counts,
    isLoading,
    error,
    refresh: fetchJobs,
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

