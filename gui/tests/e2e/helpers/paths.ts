/**
 * Path helpers for E2E tests
 * 
 * All E2E-generated projects live under .tmp/e2e_projects/
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Get the repository root path
 * Resolves from gui/tests/e2e/helpers/ up to repo root
 */
export function getRepoRoot(): string {
  // Start from current file location and go up to find repo root
  let current = __dirname;
  
  // Go up until we find the repo root (contains src/ and gui/)
  for (let i = 0; i < 10; i++) {
    const parent = path.dirname(current);
    const srcExists = fs.existsSync(path.join(parent, 'src'));
    const guiExists = fs.existsSync(path.join(parent, 'gui'));
    
    if (srcExists && guiExists) {
      return parent;
    }
    current = parent;
  }
  
  // Fallback: assume we're in gui/tests/e2e/helpers
  return path.resolve(__dirname, '..', '..', '..', '..');
}

/**
 * Get the gui directory path
 */
export function getGuiDir(): string {
  return path.join(getRepoRoot(), 'gui');
}

/**
 * Resolve the root folder for ephemeral E2E projects.
 * Defaults to repo-local .tmp/e2e_projects for inspectable artifacts.
 *
 * Override with QMS_E2E_PROJECTS_ROOT when needed.
 */
export function getE2EProjectsRoot(): string {
  const override = process.env.QMS_E2E_PROJECTS_ROOT?.trim();
  if (override) {
    return path.resolve(override);
  }
  return path.join(getRepoRoot(), '.tmp', 'e2e_projects');
}

/**
 * Get and ensure the E2E projects root directory exists
 * Creates the configured E2E projects root if it doesn't exist.
 */
export function ensureE2EProjectsRoot(): string {
  const e2eRoot = getE2EProjectsRoot();
  fs.mkdirSync(e2eRoot, { recursive: true });
  return e2eRoot;
}

/**
 * Create a unique project directory for E2E tests
 * 
 * @param prefix - Prefix for the directory name
 * @returns Path to the new unique directory
 */
export function createUniqueProjectDir(prefix: string): string {
  const e2eRoot = ensureE2EProjectsRoot();
  let attempts = 0;
  while (attempts < 10) {
    const uniqueName = `${prefix}-${Date.now()}-${process.pid}-${Math.random().toString(36).slice(2, 8)}`;
    const uniqueDir = path.join(e2eRoot, uniqueName);
    if (!fs.existsSync(uniqueDir)) {
      fs.mkdirSync(uniqueDir, { recursive: false });
      return uniqueDir;
    }
    attempts += 1;
  }
  throw new Error(`Failed to create unique E2E project directory for prefix: ${prefix}`);
}

/**
 * Clean up a project directory
 */
export function cleanupProjectDir(dirPath: string): void {
  if (fs.existsSync(dirPath)) {
    fs.rmSync(dirPath, { recursive: true, force: true });
  }
}

/**
 * Clear all E2E test projects directory
 * Legacy compatibility helper: ensure root exists without deleting artifacts.
 */
export function clearE2EProjectsRoot(): void {
  ensureE2EProjectsRoot();
}
