/**
 * E2E Test: Welcome Screen
 * 
 * Tests that the welcome screen displays correctly when no project is loaded.
 * 
 * NOTE: These tests may have compatibility issues on macOS due to how Playwright
 * launches Electron with debugging flags. They work best on Linux.
 * Set SKIP_ELECTRON_E2E=true to skip these tests.
 */

import { test, expect } from '@playwright/test';
import { launchApp, closeApp } from './helpers';
import * as os from 'os';

// Skip tests on macOS due to Playwright/Electron compatibility issues
// Also skip if explicitly requested via environment variable
const IS_MACOS = os.platform() === 'darwin';
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true' || IS_MACOS;

test.describe('Welcome Screen', () => {
  test.skip(SKIP_E2E, 'Skipped on macOS or when SKIP_ELECTRON_E2E=true');
  
  test('displays welcome screen with all action buttons', async () => {
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // Wait for the welcome screen to be visible
      await expect(page.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
      
      // Verify all action buttons are present
      await expect(page.getByTestId('qv-btn-open-project')).toBeVisible();
      await expect(page.getByTestId('qv-btn-create-new-project')).toBeVisible();
      await expect(page.getByTestId('qv-btn-create-demo-project')).toBeVisible();
      
      // Verify the welcome title text
      const title = page.getByTestId('qv-welcome-title');
      await expect(title).toContainText('Welcome to QuantumVITAS');
      
    } finally {
      await closeApp(app);
    }
  });
  
  test('navigation tabs are visible in sidebar', async () => {
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // Wait for navigation tabs to be visible
      await expect(page.getByTestId('qv-nav-home')).toBeVisible({ timeout: 30000 });
      await expect(page.getByTestId('qv-nav-structures')).toBeVisible();
      await expect(page.getByTestId('qv-nav-workflows')).toBeVisible();
      await expect(page.getByTestId('qv-nav-jobs')).toBeVisible();
      await expect(page.getByTestId('qv-nav-analysis')).toBeVisible();
      await expect(page.getByTestId('qv-nav-settings')).toBeVisible();
      
    } finally {
      await closeApp(app);
    }
  });
});

