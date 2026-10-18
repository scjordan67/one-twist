/** Real browser UI logic -> Vite proxy -> FastAPI; no response mocks. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from '../App';
import type { ChallengeFeedback } from '../api';

const nativeFetch = globalThis.fetch;
const origin = 'http://127.0.0.1:5173';
let results: ChallengeFeedback[];
let paths: string[];
beforeEach(() => {
  results = []; paths = [];
  vi.stubGlobal('fetch', async (path: string, init?: RequestInit) => {
    paths.push(path);
    const response = await nativeFetch(new URL(path, origin), init);
    expect(response.status).toBe(200);
    if (path.endsWith('/check')) results.push(await response.clone().json() as ChallengeFeedback);
    return response;
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function select(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
async function ready(title: string) { await screen.findByRole('heading', { level: 2, name: new RegExp(`^${title} ·`) }); }
async function open() { render(<MemoryRouter initialEntries={['/challenges']}><App /></MemoryRouter>); await ready('Practice 01'); }
async function submit() {
  const count = results.length;
  fireEvent.click(screen.getByRole('button', { name: 'Check answer' }));
  await waitFor(() => expect(results).toHaveLength(count + 1), { timeout: 10_000 });
  return screen.findByRole('article', { name: 'Challenge feedback' });
}

it('grades A using real isolated evidence and keeps a repairable method distinct from its invalid proper-integral steps', async () => {
  await open(); select('Choose a challenge', 'practice-002'); await ready('Practice 02');
  expect(paths.every((path) => !path.endsWith('/check') && !path.includes('/analyze'))).toBe(true);
  select('Reason category', 'improper_endpoint'); select('First flawed step', 'change-variable'); select('Related premise', 'regular-upper-bound');
  const feedback = await submit(); expect(feedback.textContent).toContain('Grade: Correct');
  expect(results[0].analysis!.execution!.status).toBe('success'); expect(results[0].analysis!.execution!.worker_pid).toBeGreaterThan(0);
  expect(within(feedback).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Needs Checking');
  expect(feedback.textContent).toContain('one-sided');
});

it('grades B by the declared goal: a=2 fails to break a derivation but succeeds in changing its conclusion', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: 'Break the Method' })); await ready('Practice 03');
  select('Declared change', 'change-a'); select('New value', '2');
  expect((await submit()).textContent).toContain('Grade: Incorrect');
  expect(results[0].analysis!.report.method.labels).toEqual(['Valid']);
  select('Choose a challenge', 'practice-005'); await ready('Practice 05');
  select('Declared change', 'change-a'); select('New value', '2');
  const feedback = await submit(); expect(feedback.textContent).toContain('Grade: Correct');
  expect(within(feedback).getByRole('region', { name: 'Conclusion validity' }).textContent).toContain('Changed Conclusion');
  expect(results[0].analysis!.execution!.worker_pid).not.toBe(results[1].analysis!.execution!.worker_pid);
});

it('grades C as reviewed content: a sound sample and a flawed proof with a correct answer require different judgements', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: 'Judge the AI' })); await ready('Practice 06');
  select('Derivation judgement', 'sound'); select('Conclusion judgement', 'correct');
  expect((await submit()).textContent).toContain('Grade: Correct');
  select('Choose a challenge', 'practice-009'); await ready('Practice 09');
  select('Derivation judgement', 'not_sound'); select('Conclusion judgement', 'correct');
  select('Reason category', 'irreversible_squaring'); select('First flawed step', 'step-002'); select('Related premise', 'premise-001');
  const feedback = await submit(); expect(feedback.textContent).toContain('Grade: Correct');
  const reviewed = within(feedback).getByRole('region', { name: 'Reviewed sample judgement' });
  expect(reviewed.textContent).toContain('Derivation: Not sound'); expect(reviewed.textContent).toContain('Conclusion: Correct');
  expect(results.every((result) => result.analysis === null && result.evidence.every((ev) => ev.origin === 'author_reviewed'))).toBe(true);
  expect(paths.some((path) => path.includes('/analyze') || path.includes('/perturbations'))).toBe(false);
});
