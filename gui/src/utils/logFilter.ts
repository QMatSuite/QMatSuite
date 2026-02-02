/**
 * Utility functions for filtering daemon logs.
 * 
 * These functions provide a single source of truth for log filtering logic,
 * ensuring that what is displayed matches what can be copied.
 */

/**
 * Check if a log line is a polling RPC log.
 * 
 * Polling logs are identified by:
 * 1. Lines containing [RPC] [polling] tag (case-insensitive)
 * 2. Lines containing [RPC] job_counts or [RPC] list_jobs (for backward compatibility)
 * 
 * @param line - Log line to check
 * @returns true if the line is a polling RPC log
 */
function isPollingRpcLog(line: string): boolean {
  // Match [RPC] [polling] tag (case-insensitive)
  if (/\[RPC\]\s+\[polling\]/i.test(line)) {
    return true;
  }
  // Match [RPC] job_counts or [RPC] list_jobs (backward compatibility)
  if (/\[RPC\]\s+(job_counts|list_jobs)\b/.test(line)) {
    return true;
  }
  return false;
}

/**
 * Filter log lines based on polling visibility.
 * 
 * @param allLines - All log lines from useQVLogs
 * @param showPolling - Whether to include polling RPC logs (job_counts, list_jobs)
 * @returns Filtered array of log lines
 */
export function getVisibleLogLines(allLines: string[], showPolling: boolean): string[] {
  // Defensive check: ensure allLines is an array
  if (!allLines || !Array.isArray(allLines)) {
    return [];
  }
  if (showPolling) {
    return allLines;
  }
  // Filter out polling RPC logs
  return allLines.filter(line => !isPollingRpcLog(line));
}

/**
 * Get the visible log text as a single string (for copying).
 * Uses the same filtering logic as rendering.
 * 
 * @param allLines - All log lines from useQVLogs
 * @param showPolling - Whether to include polling RPC logs
 * @returns Filtered log text joined with newlines
 */
export function getVisibleLogText(allLines: string[], showPolling: boolean): string {
  const visibleLines = getVisibleLogLines(allLines, showPolling);
  return visibleLines.join('\n');
}
