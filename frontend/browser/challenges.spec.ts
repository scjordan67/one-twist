import { expect, test, type Page } from '@playwright/test';

async function ready(page: Page, number: string) {
  await expect(page.getByRole('heading', { level: 2, name: new RegExp(`^Practice ${number} ·`) })).toBeVisible();
}
async function grade(page: Page, expected: string) {
  const pending = page.waitForResponse((response) => response.url().endsWith('/api/challenges/check') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Check answer', exact: true }).click();
  const response = await pending; expect(response.status()).toBe(200);
  const result = await response.json(); expect(result.grade).toBe(expected);
  await expect(page.getByRole('article', { name: 'Challenge feedback', exact: true })).toContainText(`Grade: ${expected}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  return result;
}

test('Find the Flaw uses actual evidence and displays an integral repair', async ({ page }, testInfo) => {
  const calls: string[] = [];
  page.on('request', (request) => { if (request.url().includes('/api/')) calls.push(request.url()); });
  await page.goto('/challenges'); await ready(page, '01');
  await page.getByLabel('Choose a challenge').selectOption('practice-002'); await ready(page, '02');
  expect(calls.every((url) => !/check|analyze|perturbations/.test(url))).toBe(true);
  await expect(page.locator('.presented-steps .katex')).toHaveCount(6);
  await page.getByLabel('Reason category').selectOption('improper_endpoint');
  await page.getByLabel('First flawed step').selectOption('change-variable');
  await page.getByLabel('Related premise').selectOption('regular-upper-bound');
  const result = await grade(page, 'Correct'); expect(result.analysis.execution.status).toBe('success');
  const method = page.getByRole('region', { name: 'Method applicability' });
  await expect(method).toContainText('Needs Checking'); await expect(method).toContainText('one-sided');
  await page.getByRole('form', { name: 'Challenge answer' }).screenshot({ path: testInfo.outputPath('find-flaw-form.png') });
  await method.screenshot({ path: testInfo.outputPath('find-flaw-repair.png') });
  await page.getByLabel('Related premise').selectOption('positive-u');
  await expect(page.getByRole('article', { name: 'Challenge feedback', exact: true })).toHaveCount(0);
});

test('Break the Method differentiates changing an answer from invalidating a derivation', async ({ page }, testInfo) => {
  await page.goto('/challenges'); await ready(page, '01');
  await page.getByRole('button', { name: 'Break the Method', exact: true }).click(); await ready(page, '03');
  await page.getByLabel('Declared change').selectOption('change-a'); await page.getByLabel('New value').selectOption('2');
  await grade(page, 'Incorrect');
  await expect(page.getByRole('region', { name: 'Method applicability' })).toContainText('Valid');
  await page.getByLabel('Choose a challenge').selectOption('practice-005'); await ready(page, '05');
  await expect(page.getByRole('form', { name: 'Challenge answer' })).toContainText('Challenge goal: Change the conclusion');
  await page.getByLabel('Declared change').selectOption('change-a'); await page.getByLabel('New value').selectOption('2');
  await grade(page, 'Correct');
  await page.getByRole('article', { name: 'Challenge feedback', exact: true }).screenshot({ path: testInfo.outputPath('break-method-feedback.png') });
});

test('Judge the AI permits correct samples and separates proof soundness from the answer', async ({ page }, testInfo) => {
  const errors: string[] = []; page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/challenges'); await ready(page, '01');
  await page.getByRole('button', { name: 'Judge the AI', exact: true }).click(); await ready(page, '06');
  await page.getByLabel('Derivation judgement').selectOption('sound'); await page.getByLabel('Conclusion judgement').selectOption('correct');
  let result = await grade(page, 'Correct'); expect(result.analysis).toBeNull();
  await page.getByLabel('Choose a challenge').selectOption('practice-009'); await ready(page, '09');
  await page.getByLabel('Derivation judgement').selectOption('not_sound'); await page.getByLabel('Conclusion judgement').selectOption('correct');
  await page.getByLabel('Reason category').selectOption('irreversible_squaring');
  await page.getByLabel('First flawed step').selectOption('step-002'); await page.getByLabel('Related premise').selectOption('premise-001');
  await page.getByRole('form', { name: 'Challenge answer' }).screenshot({ path: testInfo.outputPath('judge-ai-form.png') });
  result = await grade(page, 'Correct'); expect(result.analysis).toBeNull();
  const reviewed = page.getByRole('region', { name: 'Reviewed sample judgement' });
  await expect(reviewed).toContainText('Derivation: Not sound'); await expect(reviewed).toContainText('Conclusion: Correct');
  await reviewed.screenshot({ path: testInfo.outputPath('judge-ai-reviewed-feedback.png') });
  expect(errors).toEqual([]);
});
