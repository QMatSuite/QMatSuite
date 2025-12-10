/**
 * Path utilities for normalizing project paths
 * 
 * Ensures project_root paths are normalized to absolute paths
 * before sending to the daemon, matching the backend expectation.
 * 
 * Backend RPC contract (from tests/daemon/test_gui_job_and_step_flows.py):
 * - project_root must be normalized absolute path string
 * - JobManager.list_jobs() normalizes project_root before comparing with stored jobs
 * - Daemon handlers normalize project_root using Path.resolve()
 */

/**
 * Normalize a project root path to an absolute path string.
 * 
 * Backend expects normalized absolute paths for project_root matching.
 * This ensures consistent path comparison in JobManager and daemon handlers.
 * 
 * @param projectRoot - Project root path (can be relative, absolute, or undefined)
 * @returns Normalized absolute path string, or undefined if input is invalid
 * 
 * @example
 * normalizeProjectRoot('/path/to/project') // '/path/to/project'
 * normalizeProjectRoot('./project') // '/absolute/path/to/project'
 * normalizeProjectRoot(undefined) // undefined
 */
export function normalizeProjectRoot(projectRoot: string | undefined | null): string | undefined {
  if (!projectRoot || projectRoot.trim() === '') {
    return undefined;
  }
  
  try {
    // Use Node.js path module if available (Electron environment)
    // This is the preferred method as it properly resolves relative paths
    if (typeof window !== 'undefined' && (window as any).require) {
      const path = (window as any).require('path');
      const resolved = path.resolve(projectRoot);
      // Remove trailing slashes for consistency
      return resolved.replace(/[/\\]+$/, '') || resolved;
    }
    
    // Fallback: basic normalization (remove trailing slashes)
    // Note: In pure browser context, we can't truly resolve relative paths,
    // but in Electron this should not happen as require('path') is available
    const normalized = projectRoot.replace(/[/\\]+$/, ''); // Remove trailing slashes
    return normalized || undefined;
  } catch (e) {
    console.warn('[normalizeProjectRoot] Failed to normalize path:', projectRoot, e);
    // Return as-is if normalization fails (backend will handle it)
    return projectRoot;
  }
}
