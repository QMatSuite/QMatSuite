/**
 * Path helpers for E2E tests
 * 
 * All E2E-generated projects live under .tmp/e2e_projects/
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
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
 * Defaults to OS temp dir to avoid nesting test projects inside the repo.
 *
 * Override with QV_E2E_PROJECTS_ROOT when needed.
 */
export function getE2EProjectsRoot(): string {
  const override = process.env.QV_E2E_PROJECTS_ROOT?.trim();
  if (override) {
    return path.resolve(override);
  }
  return path.join(os.tmpdir(), 'qv_e2e_projects');
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
  const timestamp = Date.now();
  const uniqueDir = path.join(e2eRoot, `${prefix}-${timestamp}`);
  fs.mkdirSync(uniqueDir, { recursive: true });
  return uniqueDir;
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
 * Removes all contents of the configured E2E projects root.
 */
export function clearE2EProjectsRoot(): void {
  const e2eRoot = getE2EProjectsRoot();
  if (fs.existsSync(e2eRoot)) {
    fs.rmSync(e2eRoot, { recursive: true, force: true });
  }
  // Recreate the directory
  fs.mkdirSync(e2eRoot, { recursive: true });
}
