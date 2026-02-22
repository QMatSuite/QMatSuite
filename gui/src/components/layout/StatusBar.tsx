/**
 * StatusBar - Bottom status bar showing project, QE status, and running jobs
 * 
 * Provides at-a-glance information about the current application state.
 */

import { useState, useEffect, useCallback } from 'react';
import type { EnvironmentInfo, JobCounts } from '../../types/qms';
import './StatusBar.css';

interface StatusBarProps {
  projectRoot: string | null;
  projectName: string | null;
  daemonConnected: boolean;
  onOpenSettings?: () => void;
  onOpenJobs?: () => void;
  onNavigateToHome?: () => void;
}

export function StatusBar({
  projectRoot,
  projectName,
  daemonConnected,
  onOpenSettings,
  onOpenJobs,
  onNavigateToHome,
}: StatusBarProps) {
  const [envInfo, setEnvInfo] = useState<EnvironmentInfo | null>(null);
  const [jobCounts, setJobCounts] = useState<JobCounts | null>(null);
  
  // Fetch environment info
  useEffect(() => {
    const fetchEnvInfo = async () => {
      if (!window.qms || !daemonConnected) return;
      
      try {
        const response = await window.qms.request<EnvironmentInfo>('get_environment_info', {});
        if (response.ok && response.data) {
          setEnvInfo(response.data);
        }
      } catch {
        // Silently fail
      }
    };
    
    fetchEnvInfo();
    const interval = setInterval(fetchEnvInfo, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [daemonConnected]);
  
  // Fetch job counts (polling at 5s interval to avoid conflicts with useJobs)
  // NOTE: This is for StatusBar display only. JobsPanel uses useJobs hook which also polls.
  useEffect(() => {
    const fetchJobCounts = async () => {
      if (!window.qms || !daemonConnected) return;
      
      try {
        const response = await window.qms.request<JobCounts>('job_counts', {});
        if (response.ok && response.data) {
          setJobCounts(response.data);
        }
      } catch {
        // Silently fail
      }
    };
    
    fetchJobCounts();
    const interval = setInterval(fetchJobCounts, 5000); // Refresh every 5s (throttled to avoid conflicts)
    return () => clearInterval(interval);
  }, [daemonConnected]);
  
  const getQEStatus = useCallback(() => {
    if (!envInfo) return { icon: '○', text: 'Unknown', className: 'status--muted' };
    if (envInfo.qe_found && envInfo.qe_home) {
      return { 
        icon: '●', 
        text: 'QE detected', 
        className: 'status--success' 
      };
    }
    return { icon: '○', text: 'QE not found', className: 'status--warning' };
  }, [envInfo]);
  
  const qeStatus = getQEStatus();
  const runningJobs = jobCounts?.running || 0;
  const pendingJobs = jobCounts?.pending || 0;
  const activeJobs = runningJobs + pendingJobs;
  
  return (
    <div className="status-bar">
      <div className="status-bar__left">
        {/* Daemon status */}
        <div className={`status-bar__item ${daemonConnected ? 'status--success' : 'status--error'}`}>
          <span className="status-bar__indicator" />
          <span className="status-bar__text">
            {daemonConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        
        {/* Divider */}
        <span className="status-bar__divider" />
        
        {/* Project */}
        {projectName ? (
          <button 
            className="status-bar__item status-bar__item--project status-bar__item--clickable"
            onClick={onNavigateToHome}
            title={`${projectRoot || projectName}\nClick to go to Home`}
          >
            <span className="status-bar__icon">📁</span>
            <span className="status-bar__text status-bar__project-name">
              {projectName}
            </span>
            {projectRoot && (
              <span className="status-bar__path status-bar__full-path" title={projectRoot}>
                {projectRoot}
              </span>
            )}
          </button>
        ) : (
          <div className="status-bar__item status--muted">
            <span className="status-bar__icon">📁</span>
            <span className="status-bar__text">No project</span>
          </div>
        )}
      </div>
      
      <div className="status-bar__right">
        {/* Jobs */}
        <button 
          className={`status-bar__item status-bar__item--clickable ${activeJobs > 0 ? 'status--active' : ''}`}
          onClick={onOpenJobs}
          title={`${runningJobs} running, ${pendingJobs} pending`}
        >
          {activeJobs > 0 ? (
            <>
              <span className="status-bar__pulse" />
              <span className="status-bar__icon">⚡</span>
              <span className="status-bar__text">{runningJobs} running</span>
              {pendingJobs > 0 && (
                <span className="status-bar__badge">{pendingJobs}</span>
              )}
            </>
          ) : (
            <>
              <span className="status-bar__icon">○</span>
              <span className="status-bar__text">No jobs</span>
            </>
          )}
        </button>
        
        {/* Divider */}
        <span className="status-bar__divider" />
        
        {/* QE status */}
        <button 
          className={`status-bar__item status-bar__item--clickable ${qeStatus.className}`}
          onClick={onOpenSettings}
          title={envInfo?.qe_home || 'Click to configure QE'}
        >
          <span className="status-bar__indicator" />
          <span className="status-bar__text">{qeStatus.text}</span>
        </button>
      </div>
    </div>
  );
}

