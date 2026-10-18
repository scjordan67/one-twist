import { expect, test, type Page } from '@playwright/test';

async function ready(page: Page) { await expect(page.getByRole('button', { name: 'Analyze change', exact: true })).toBeEnabled(); }
async function analyze(page: Page) {
  const response = page.waitForResponse((response) => response.url().endsWith('/api/perturbations') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analyze change', exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  expect((await result.json()).execution.status).toBe('success');
}
async function fitsViewport(page: Page) {
  // Read-only layout measurement; internal formula scrollers may be wider.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test('algebra comparison, preserved step constraints and boundary navigation', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/problems'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('linear-degeneration'); await ready(page);
  await page.getByLabel('Declared change').selectOption('change-a');
  await page.getByLabel('New value').selectOption('2'); await analyze(page);
  const report = page.getByRole('article', { name: 'Changed validity report' });
  await expect(report.getByRole('region', { name: 'Method applicability' })).toContainText('Valid');
  await expect(report.getByRole('region', { name: 'Conclusion validity' })).toContainText('Changed Conclusion');
  await expect(page.locator('.condition-changed')).toHaveCount(1);
  await expect(page.locator('.condition-changed .katex')).toHaveCount(1);
  await page.locator('.comparison-grid').first().screenshot({ path: testInfo.outputPath('problem-comparison.png') });
  await fitsViewport(page);
  await page.getByLabel('New value').selectOption('-1');
  await expect(report).toHaveCount(0); await analyze(page);
  await expect(report.getByText('The conclusion changed.', { exact: true })).toBeVisible();
  await page.getByLabel('Declared change').selectOption('set-a-zero'); await analyze(page);
  await expect(report).toContainText('No solution');
  await page.getByRole('navigation').getByRole('link', { name: 'Method Inspector', exact: true }).click();
  const step = page.getByRole('article', { name: 'Step 1 details' });
  await expect(step).toContainText('Invalid Step'); await expect(step).toContainText('Algebraic rearrangement');
  await expect(step.getByRole('heading', { name: 'Retained domain constraints' })).toBeVisible();
  await step.screenshot({ path: testInfo.outputPath('method-step.png') }); await fitsViewport(page);
  await page.getByRole('navigation').getByRole('link', { name: 'Boundary Explorer', exact: true }).click();
  await expect(page.getByText('First established invalid step:', { exact: false })).toContainText('Step 1');
  await expect(page.getByRole('region', { name: 'Changed outcome' })).toContainText('Solution set');
  await fitsViewport(page); expect(errors).toEqual([]);
});

test('domain widening displays the new domain, extra root and local validity', async ({ page }, testInfo) => {
  await page.goto('/problems'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('cancelled-factor-domain'); await ready(page);
  await expect(page.getByLabel('New domain')).toBeVisible();
  await analyze(page);
  const report = page.getByRole('article', { name: 'Changed validity report' });
  await expect(report.getByRole('region', { name: 'Method applicability' })).toContainText('Invalid Step');
  await expect(report.getByRole('region', { name: 'Conclusion validity' })).toContainText('Changed Conclusion');
  await expect(page.locator('.condition-changed')).toHaveCount(1);
  await page.locator('.comparison-grid').first().screenshot({ path: testInfo.outputPath('domain-comparison.png') });
  await fitsViewport(page);
  await page.getByRole('navigation').getByRole('link', { name: 'Method Inspector', exact: true }).click();
  await page.getByRole('button', { name: /^Step 2/ }).click();
  const step = page.getByRole('article', { name: 'Step 2 details' });
  await expect(step.getByRole('region', { name: 'Step 2 validity' })).toContainText('Valid');
  await fitsViewport(page);
});

test('invalid real logarithm split retains the independently unchanged answer', async ({ page }, testInfo) => {
  await page.goto('/boundaries'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('real-log-product'); await ready(page);
  await analyze(page);
  await expect(page.getByRole('region', { name: 'Method applicability' })).toContainText('Invalid Step');
  const conclusion = page.getByRole('region', { name: 'Conclusion validity' });
  await expect(conclusion).toContainText('Valid');
  await expect(conclusion).not.toContainText('Changed Conclusion');
  await expect(page.getByText('The conclusion is unchanged.', { exact: true })).toBeVisible();
  await page.getByRole('heading', { name: 'One condition changed' }).locator('..').screenshot({ path: testInfo.outputPath('log-boundary.png') });
  await fitsViewport(page);
});

test('improper integral repair and independent validity dimensions', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/boundaries'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('integral-endpoint'); await ready(page);
  await page.getByLabel('New value').selectOption('1'); await analyze(page);
  const method = page.getByRole('region', { name: 'Method applicability' });
  await expect(method).toContainText('Needs Checking'); await expect(method).toContainText('one-sided');
  await expect(page.getByRole('region', { name: 'Conclusion validity' })).toContainText('Changed Conclusion');
  await expect(page.getByRole('region', { name: 'Changed outcome' })).toContainText('Divergent');
  await method.screenshot({ path: testInfo.outputPath('integral-remediation.png') });
  await page.getByRole('region', { name: 'Changed outcome' }).screenshot({ path: testInfo.outputPath('divergent-outcome.png') });
  await fitsViewport(page); expect(errors).toEqual([]);
});

test('a cusp has a known missing point derivative and a valid punctured identity', async ({ page }, testInfo) => {
  await page.goto('/boundaries'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('derivative-cusp'); await ready(page);
  await analyze(page);
  await expect(page.getByRole('region', { name: 'Changed outcome' })).toContainText('Derivative does not exist');
  await expect(page.getByRole('region', { name: 'Conclusion validity' })).toContainText('Changed Conclusion');
  await page.getByRole('heading', { name: 'One condition changed' }).locator('..').screenshot({ path: testInfo.outputPath('cusp-boundary.png') });
  await fitsViewport(page);
  await page.getByRole('link', { name: 'Inspect the changed derivation', exact: false }).click();
  await page.getByRole('button', { name: /^Step 1/ }).click();
  await expect(page.getByRole('region', { name: 'Step 1 validity' })).toContainText('Valid');
  await page.getByRole('button', { name: /^Step 2/ }).click();
  await expect(page.getByRole('region', { name: 'Step 2 validity' })).toContainText('Invalid Step');
  await fitsViewport(page);
});

test('stationary classification changes while the positive control stays valid', async ({ page }, testInfo) => {
  await page.goto('/boundaries'); await ready(page);
  await page.getByLabel('Choose an example').selectOption('stationary-second-derivative'); await ready(page);
  await analyze(page);
  await expect(page.getByRole('region', { name: 'Changed outcome' })).toContainText('Classification');
  await expect(page.getByRole('region', { name: 'Changed outcome' })).toContainText('stationary non extremum');
  await expect(page.getByText('Comparison basis: classification.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Method applicability' })).toContainText('Invalid Step');
  await page.getByRole('heading', { name: 'One condition changed' }).locator('..').screenshot({ path: testInfo.outputPath('stationary-boundary.png') });
  await fitsViewport(page);
  await page.getByLabel('Declared change').selectOption('positive-control'); await analyze(page);
  await expect(page.getByText('The conclusion is unchanged.', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Method applicability' })).not.toContainText('Invalid Step');
});
