/**
 * Test ID validation helpers for E2E tests
 * 
 * Ensures that data-testid attributes are unique across the rendered DOM
 * to prevent test selector ambiguity.
 */

import type { Page } from '@playwright/test';

/**
 * Assert that there are no duplicate data-testid values in the current page.
 * 
 * Throws an error if duplicates are found, listing all duplicate IDs and their counts.
 * 
 * @param page - Playwright page object
 * @throws Error if duplicate test IDs are found
 */
export async function assertNoDuplicateTestIds(page: Page): Promise<void> {
  // Get all elements with data-testid attributes
  const testIds = await page.$$eval('[data-testid]', (nodes) =>
    nodes
      .map((n) => n.getAttribute('data-testid'))
      .filter((id): id is string => !!id)
  );

  // Count occurrences of each test ID
  const idCounts = new Map<string, number>();
  for (const id of testIds) {
    idCounts.set(id, (idCounts.get(id) || 0) + 1);
  }

  // Find duplicates (IDs that appear more than once)
  const duplicates = Array.from(idCounts.entries())
    .filter(([_, count]) => count > 1)
    .map(([id, count]) => ({ id, count }));

  if (duplicates.length > 0) {
    const duplicateList = duplicates
      .map(({ id, count }) => `  - "${id}" (appears ${count} times)`)
      .join('\n');
    
    throw new Error(
      `Duplicate data-testid values detected:\n${duplicateList}\n\n` +
      `Each data-testid must be unique. Use namespaced IDs like:\n` +
      `  - "home-btn-open-project" (for Home view)\n` +
      `  - "sidebar-btn-open-project" (for Sidebar)\n` +
      `  - "demo-card-si-bands-demo" (for Demo Gallery)`
    );
  }
}

