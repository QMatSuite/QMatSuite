/**
 * Path helpers for E2E tests
 * 
 * All E2E-generated projects live under temp/e2e_projects/
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
 * Get and ensure the E2E projects root directory exists
 * Creates <repo_root>/temp/e2e_projects if it doesn't exist
 */
export function ensureE2EProjectsRoot(): string {
  const e2eRoot = path.join(getRepoRoot(), 'temp', 'e2e_projects');
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
 * Removes all contents of temp/e2e_projects/
 */
export function clearE2EProjectsRoot(): void {
  const e2eRoot = path.join(getRepoRoot(), 'temp', 'e2e_projects');
  if (fs.existsSync(e2eRoot)) {
    fs.rmSync(e2eRoot, { recursive: true, force: true });
  }
  // Recreate the directory
  fs.mkdirSync(e2eRoot, { recursive: true });
}

