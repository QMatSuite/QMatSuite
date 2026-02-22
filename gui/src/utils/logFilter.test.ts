/**
 * Unit tests for logFilter utility functions.
 * 
 * Simple unit tests that can be verified manually or with a test runner.
 * Tests the core filtering logic to ensure copy matches visible content.
 */

import { getVisibleLogLines, getVisibleLogText } from './logFilter';

// Simple assertion helpers
function assertEqual<T>(actual: T, expected: T, message?: string) {
  if (actual !== expected) {
    throw new Error(message || `Expected ${expected}, but got ${actual}`);
  }
}

function assertDeepEqual<T>(actual: T, expected: T, message?: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      message || `Expected ${JSON.stringify(expected)}, but got ${JSON.stringify(actual)}`
    );
  }
}

// Test: should return all lines when showPolling is true
export function test_showPollingTrue() {
  const logs = [
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
    '[qms-daemon] [DEBUG] [RPC] [polling] job_counts took 0.5ms',
    '[qms-daemon] [DEBUG] [RPC] [polling] list_jobs took 0.8ms',
    '[qms-daemon] [INFO] [RPC] get_env_info took 2.1ms',
  ];
  
  const result = getVisibleLogLines(logs, true);
  assertEqual(result.length, 4);
  assertDeepEqual(result, logs);
}

// Test: should filter out polling logs when showPolling is false
export function test_showPollingFalse() {
  const logs = [
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
    '[qms-daemon] [DEBUG] [RPC] [polling] job_counts took 0.5ms',
    '[qms-daemon] [DEBUG] [RPC] [polling] list_jobs took 0.8ms',
    '[qms-daemon] [INFO] [RPC] get_env_info took 2.1ms',
  ];
  
  const result = getVisibleLogLines(logs, false);
  assertEqual(result.length, 2);
  assertEqual(result[0], logs[0]);
  assertEqual(result[1], logs[3]);
}

// Test: should handle empty log array
export function test_emptyLogs() {
  const result = getVisibleLogLines([], false);
  assertEqual(result.length, 0);
}

// Test: should filter [polling] tag (case-insensitive)
export function test_filterPollingTag() {
  const logs = [
    '[qms-daemon] [DEBUG] [RPC] [polling] job_counts took 0.5ms',
    '[qms-daemon] [INFO] [RPC] [POLLING] list_jobs took 0.8ms',
    '[qms-daemon] [DEBUG] [RPC] [Polling] job_counts (req_id=123) took 0.6ms',
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
  ];
  
  const result = getVisibleLogLines(logs, false);
  assertEqual(result.length, 1);
  assertEqual(result[0], logs[3]);
}

// Test: should filter job_counts and list_jobs (backward compatibility)
export function test_filterJobCountsAndListJobs() {
  const logs = [
    '[qms-daemon] [DEBUG] [RPC] job_counts took 0.5ms',
    '[qms-daemon] [INFO] [RPC] job_counts (req_id=123) took 0.5ms',
    '[qms-daemon] [DEBUG] [RPC] list_jobs took 0.8ms',
    '[qms-daemon] [INFO] [RPC] list_jobs (req_id=456, project: test) took 0.9ms',
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
  ];
  
  const result = getVisibleLogLines(logs, false);
  assertEqual(result.length, 1);
  assertEqual(result[0], logs[4]);
}

// Test: should not filter non-polling RPCs that contain similar text
export function test_noFalsePositives() {
  const logs = [
    '[qms-daemon] [INFO] [RPC] get_job_counts_summary took 1.5ms',
    '[qms-daemon] [INFO] [RPC] list_jobs_history took 2.0ms',
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
    '[qms-daemon] [INFO] [RPC] get_job_counts took 1.8ms',  // Different endpoint
  ];
  
  const result = getVisibleLogLines(logs, false);
  assertEqual(result.length, 4);
  assertDeepEqual(result, logs);
}

// Test: should filter lines with [polling] tag even if job_counts/list_jobs not present
export function test_filterPollingTagAlone() {
  const logs = [
    '[qms-daemon] [DEBUG] [RPC] [polling] some_other_endpoint took 0.5ms',
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
  ];
  
  const result = getVisibleLogLines(logs, false);
  assertEqual(result.length, 1);
  assertEqual(result[0], logs[1]);
}

// Test: getVisibleLogText should filter and join correctly
export function test_getVisibleLogText() {
  const logs = [
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
    '[qms-daemon] [DEBUG] [RPC] [polling] job_counts took 0.5ms',
    '[qms-daemon] [INFO] [RPC] get_env_info took 2.1ms',
  ];
  
  const result = getVisibleLogText(logs, false);
  const expected = [
    '[qms-daemon] [INFO] [RPC] ping took 1.2ms',
    '[qms-daemon] [INFO] [RPC] get_env_info took 2.1ms',
  ].join('\n');
  
  assertEqual(result, expected);
}

// Run all tests if executed directly
if (typeof window === 'undefined' && typeof process !== 'undefined') {
  const tests = [
    { name: 'showPollingTrue', fn: test_showPollingTrue },
    { name: 'showPollingFalse', fn: test_showPollingFalse },
    { name: 'emptyLogs', fn: test_emptyLogs },
    { name: 'filterPollingTag', fn: test_filterPollingTag },
    { name: 'filterJobCountsAndListJobs', fn: test_filterJobCountsAndListJobs },
    { name: 'noFalsePositives', fn: test_noFalsePositives },
    { name: 'filterPollingTagAlone', fn: test_filterPollingTagAlone },
    { name: 'getVisibleLogText', fn: test_getVisibleLogText },
  ];
  
  let passed = 0;
  let failed = 0;
  
  console.log('Running logFilter tests...\n');
  
  for (const test of tests) {
    try {
      test.fn();
      console.log(`✓ ${test.name}`);
      passed++;
    } catch (e) {
      console.error(`✗ ${test.name}`);
      console.error(`  ${e instanceof Error ? e.message : String(e)}`);
      failed++;
    }
  }
  
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}
