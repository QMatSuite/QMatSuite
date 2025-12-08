/**
 * Electron CDP launch helper for E2E tests
 * 
 * Workaround for Playwright's _electron.launch() issue on macOS where
 * --remote-debugging-port=0 is rejected by Electron.
 * 
 * This helper manually spawns Electron with a real debugging port and
 * connects via CDP (Chrome DevTools Protocol).
 */

import { chromium, Browser, Page } from '@playwright/test';
import * as path from 'path';
import * as os from 'os';
import { spawn, ChildProcess } from 'child_process';
import { getGuiDir, getRepoRoot } from './paths';
import * as http from 'http';

export interface ElectronCDPResult {
  browser: Browser;
  page: Page;
  electronProcess: ChildProcess;
  close: () => Promise<void>;
}

/**
 * Get the path to the Electron executable binary
 * Computes platform-specific path to the Electron binary in node_modules
 */
function getElectronExecutablePath(): string {
  const repoRoot = getRepoRoot();
  const electronDistDir = path.join(repoRoot, 'gui', 'node_modules', 'electron', 'dist');
  
  if (os.platform() === 'darwin') {
    // macOS: Electron.app/Contents/MacOS/Electron
    return path.join(
      electronDistDir,
      'Electron.app',
      'Contents',
      'MacOS',
      'Electron'
    );
  } else if (os.platform() === 'win32') {
    // Windows: electron.exe
    return path.join(electronDistDir, 'electron.exe');
  } else {
    // Linux: electron
    return path.join(electronDistDir, 'electron');
  }
}

/**
 * Wait for Electron's debugging port to be ready
 * Polls the /json/version endpoint until it responds
 * Also tries /json/list as an alternative endpoint
 */
async function waitForDebuggingPort(port: number, timeout: number = 10000): Promise<string> {
  const startTime = Date.now();
  const maxWait = timeout;
  let lastError: Error | null = null;
  let attempts = 0;
  
  while (Date.now() - startTime < maxWait) {
    attempts++;
    try {
      // Try /json/version first (gives us the WebSocket URL directly)
      const response = await new Promise<{ webSocketDebuggerUrl?: string }>((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${port}/json/version`, (res) => {
          if (res.statusCode !== 200) {
            reject(new Error(`HTTP ${res.statusCode}`));
            return;
          }
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              reject(e);
            }
          });
        });
        req.on('error', (err) => {
          lastError = err;
          reject(err);
        });
        req.setTimeout(2000, () => {
          req.destroy();
          reject(new Error('Request timeout'));
        });
      });
      
      if (response.webSocketDebuggerUrl) {
        return response.webSocketDebuggerUrl;
      }
      
      // If no WebSocket URL, try /json/list to get targets
      const listResponse = await new Promise<any[]>((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${port}/json/list`, (res) => {
          if (res.statusCode !== 200) {
            reject(new Error(`HTTP ${res.statusCode}`));
            return;
          }
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              reject(e);
            }
          });
        });
        req.on('error', reject);
        req.setTimeout(2000, () => {
          req.destroy();
          reject(new Error('Request timeout'));
        });
      });
      
      // If we got a list, use the first target's WebSocket URL
      if (listResponse && listResponse.length > 0 && listResponse[0].webSocketDebuggerUrl) {
        return listResponse[0].webSocketDebuggerUrl;
      }
      
    } catch (error) {
      // Port not ready yet, wait and retry
      if (attempts % 10 === 0) {
        // Log progress every 10 attempts (every ~2 seconds)
        console.log(`[CDP] Waiting for Electron debugging port ${port}... (attempt ${attempts})`);
      }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }
  
  const errorMsg = lastError 
    ? `Electron debugging port ${port} did not become ready within ${timeout}ms after ${attempts} attempts. Last error: ${lastError.message}`
    : `Electron debugging port ${port} did not become ready within ${timeout}ms after ${attempts} attempts`;
  throw new Error(errorMsg);
}

/**
 * Launch Electron via CDP (Chrome DevTools Protocol)
 * 
 * Manually spawns Electron with --remote-debugging-port and connects via CDP.
 * This works around Playwright's _electron.launch() issue on macOS.
 * 
 * @param options - Optional launch options
 * @returns Browser, page, process, and close function
 */
export async function launchElectronViaCDP(options?: {
  timeout?: number;
  debugPort?: number;
}): Promise<ElectronCDPResult> {
  const guiDir = getGuiDir();
  const timeout = options?.timeout ?? 30000;
  // Use a random port to avoid conflicts if previous Electron instance didn't close properly
  // Generate a random port between 9222-9299
  const debugPort = options?.debugPort ?? (9222 + Math.floor(Math.random() * 78));
  
  // Path to the compiled main entry point
  const mainPath = path.join(guiDir, 'dist-electron', 'main.js');
  
  // Explicit path to Electron binary (platform-specific)
  const electronExecutablePath = getElectronExecutablePath();
  
  // Spawn Electron with remote debugging enabled via environment variable
  // The main.ts file will read ELECTRON_REMOTE_DEBUG_PORT and enable debugging
  // IMPORTANT: Use 'ignore' for stdout/stderr to prevent EPIPE errors when streams are closed
  // We only need stderr initially to extract the WebSocket URL, then we can ignore it
  const electronProcess = spawn(electronExecutablePath, [
    mainPath,
  ], {
    cwd: guiDir,
    env: {
      ...process.env,
      // Enable remote debugging on the specified port
      ELECTRON_REMOTE_DEBUG_PORT: debugPort.toString(),
      // Enable E2E test mode
      E2E_TEST_MODE: 'true',
      // Ensure QE_HOME is passed through if set
      QE_HOME: process.env.QE_HOME || '',
      // Disable security warnings
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
    stdio: ['ignore', 'ignore', 'pipe'], // Only capture stderr initially for WebSocket URL, then ignore
  });
  
  // Track if process exited unexpectedly
  let processExited = false;
  let exitCode: number | null = null;
  let exitSignal: string | null = null;
  
  electronProcess.on('exit', (code, signal) => {
    processExited = true;
    exitCode = code;
    exitSignal = signal;
  });
  
  // Log Electron output and extract WebSocket URL from stderr
  // Note: stdout is set to 'ignore' to prevent EPIPE errors
  const outputLines: string[] = [];
  let wsUrlFromOutput: string | null = null;
  
  // Handle stderr - we only need this temporarily to extract the WebSocket URL
  // After that, we'll stop reading to prevent EPIPE errors
  electronProcess.stderr?.on('data', (data) => {
    const text = data.toString();
    outputLines.push(text);
    
    // Extract WebSocket URL from "DevTools listening on ws://..." message
    const wsMatch = text.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (wsMatch && wsMatch[1]) {
      wsUrlFromOutput = wsMatch[1];
    }
    
    if (process.env.DEBUG_ELECTRON) {
      console.error('[Electron stderr]', text);
    }
  });
  
  // Handle stderr errors gracefully - ignore EPIPE
  electronProcess.stderr?.on('error', (error: NodeJS.ErrnoException) => {
    // Ignore EPIPE errors - these happen when we stop reading
    if (error.code !== 'EPIPE') {
      console.error('[Electron stderr error]', error);
    }
  });
  
  // Handle process errors
  electronProcess.on('error', (error) => {
    throw new Error(`Failed to spawn Electron: ${error.message}`);
  });
  
  // Wait a moment for Electron to start and output the WebSocket URL
  // Give more time for Electron to fully initialize
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Check if process exited immediately (indicates a startup error)
  if (processExited) {
    const output = outputLines.join('\n');
    throw new Error(
      `Electron process exited immediately with code ${exitCode}, signal ${exitSignal}. ` +
      `This usually indicates a startup error. Output: ${output.slice(0, 500)}`
    );
  }
  
  // Try to get WebSocket URL - prefer from output, fallback to HTTP endpoint
  let wsUrl: string;
  if (wsUrlFromOutput) {
    wsUrl = wsUrlFromOutput;
  } else {
    // Fallback: query the HTTP endpoint (give more time for Electron to start)
    wsUrl = await waitForDebuggingPort(debugPort, 15000);
  }
  
  // After we have the WebSocket URL, keep reading stderr but discard data
  // This prevents EPIPE errors - we must keep reading from the pipe or it will close
  // and cause EPIPE when Electron tries to write to it
  if (electronProcess.stderr) {
    // Replace the data handler to just discard data (prevent EPIPE)
    electronProcess.stderr.removeAllListeners('data');
    electronProcess.stderr.on('data', () => {
      // Discard data - we don't need it after getting the WebSocket URL
      // But we must keep reading to prevent EPIPE errors
    });
  }
  
  // Connect to Electron via CDP
  const browser = await chromium.connectOverCDP(wsUrl);
  
  // Get the first context (Electron's main window)
  const contexts = browser.contexts();
  if (contexts.length === 0) {
    throw new Error('No browser contexts found after connecting to Electron');
  }
  
  const context = contexts[0];
  
  // Get the first page or wait for one
  let page: Page;
  const pages = context.pages();
  if (pages.length > 0) {
    page = pages[0];
  } else {
    // Wait for a page to be created
    page = await context.waitForEvent('page', { timeout });
  }
  
  // Wait for the app to be ready
  await page.waitForLoadState('domcontentloaded');
  
  // Return browser, page, process, and close function
  return {
    browser,
    page,
    electronProcess,
    close: async () => {
      // Close browser connection first
      try {
        await browser.close();
      } catch (e) {
        // Ignore errors during close
      }
      
      // Don't close stdout/stderr streams - let them close naturally when process exits
      // Closing them prematurely causes EPIPE errors when Electron tries to write
      // Instead, we'll just kill the process and let the OS clean up the streams
      
      // Then kill the Electron process
      try {
        if (!processExited && electronProcess.pid) {
          // Try graceful shutdown first
          electronProcess.kill('SIGTERM');
          
          // Wait a bit for graceful shutdown
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          // Force kill if still running
          if (!processExited && electronProcess.pid) {
            electronProcess.kill('SIGKILL');
          }
        }
      } catch (e) {
        // Ignore errors during kill
      }
      
      // Wait for process to actually exit
      if (!processExited && electronProcess.pid) {
        await new Promise<void>((resolve) => {
          if (processExited) {
            resolve();
            return;
          }
          electronProcess.once('exit', () => resolve());
          // Timeout after 2 seconds
          setTimeout(() => resolve(), 2000);
        });
      }
    },
  };
}

