/**
 * E2E Test 1: Welcome Screen
 * 
 * Tests that the welcome screen displays correctly when no project is loaded.
 * 
 * **This spec does NOT run any workflows.** It only tests UI state and navigation.
 * 
 * Each test file runs in its own Playwright process, ensuring complete isolation.
 * The unified Electron fixture automatically chooses the appropriate launch strategy
 * based on platform (Linux: _electron.launch, macOS: CDP).
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/welcome.spec.ts --project=electron
 */

import { electronTest as test, expect } from './fixtures/electronTest';
import { clearE2EProjectsRoot } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E Test 1: Welcome Screen', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  // Clear E2E projects directory before each test
  // Leave it after tests for inspection
  test.beforeEach(() => {
    clearE2EProjectsRoot();
  });
  
  test('displays welcome screen with all action buttons', async ({ appPage }) => {
    // Wait for the welcome screen to be visible
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
    const welcomeContainer = appPage.getByTestId('qv-welcome');
    await expect(welcomeContainer).toBeVisible();
    
    // Verify all action buttons are present within the welcome screen
    // Use namespaced test IDs (welcome-* instead of generic qv-btn-*)
    await expect(welcomeContainer.getByTestId('qv-welcome-btn-open-project')).toBeVisible();
    await expect(welcomeContainer.getByTestId('qv-welcome-btn-create-new-project')).toBeVisible();
    // Updated: "Create Demo Project" button is now "Browse Demo Gallery"
    await expect(welcomeContainer.getByTestId('qv-welcome-btn-demo-gallery')).toBeVisible();
    
    // Verify the welcome title text
    const title = appPage.getByTestId('qv-welcome-title');
    await expect(title).toContainText('Welcome to QuantumVITAS');
  });
});

