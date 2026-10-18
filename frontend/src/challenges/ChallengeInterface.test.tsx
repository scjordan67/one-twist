import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { App } from '../App';
import type { ChallengeAnswer, ChallengeFeedback } from '../api';
import { challenges } from '../test/challenge-fixtures';
import { unknownAnalysis } from '../test/fixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
type Handler = (url: string, init?: RequestInit) => Response | Promise<Response> | undefined;
function mockService(handler?: Handler) {
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    const result = handler?.(url, init);
    if (result) return Promise.resolve(result);
    if (url === '/api/challenges') return Promise.resolve(response(challenges.summaries));
    if (url === '/api/challenges/check') {
      const body = JSON.parse(String(init?.body)) as ChallengeAnswer;
      return Promise.resolve(response({ ...challenges.feedbacks[body.challenge_id], free_text: body.free_text }));
    }
    if (url.startsWith('/api/challenges/')) return Promise.resolve(response(challenges.details[url.split('/').at(-1)!]));
    throw new Error(`Unexpected request ${url}`);
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
function open(strict = false) {
  const app = <MemoryRouter initialEntries={['/challenges']}><App /></MemoryRouter>;
  return render(strict ? <StrictMode>{app}</StrictMode> : app);
}
function select(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
async function ready(id = 'practice-001') {
  await waitFor(() => expect(screen.getByRole('heading', { level: 2, name: new RegExp(`^${challenges.details[id].title} ·`) })).toBeTruthy());
}
async function choose(id: string) { select('Choose a challenge', id); await ready(id); }
async function mode(name: string, id: string) { fireEvent.click(screen.getByRole('button', { name })); await ready(id); }
function answerA() { select('Reason category', 'zero_divisor'); select('First flawed step', 'divide-by-a'); select('Related premise', 'a-nonzero'); }
function submit() { fireEvent.click(screen.getByRole('button', { name: 'Check answer' })); }
async function feedback() { return screen.findByRole('article', { name: 'Challenge feedback' }); }

it('loads only safe presentation GETs, including StrictMode; never prefetches a verdict', async () => {
  const fetch = mockService(); const { container } = open(true); await ready();
  expect(fetch.mock.calls.every(([url]) => !url.includes('check') && !url.includes('analyze') && !url.includes('perturbations'))).toBe(true);
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
  expect(container.querySelector('.presented-steps .katex')).not.toBeNull();
  expect(screen.getByRole('button', { name: 'Check answer' }).hasAttribute('disabled')).toBe(true);
});

it('submits the complete A tuple and ungraded text, renders real-shaped independent math dimensions, then clears on edit', async () => {
  const fetch = mockService(); open(); await ready(); answerA();
  select('Optional explanation', '<script>not executed or semantically graded</script>');
  submit(); const report = await feedback();
  expect(report.textContent).toContain('Grade: Correct');
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/check'))!;
  expect(JSON.parse(String(call[1]?.body))).toEqual({ ...challenges.answers['practice-001'], free_text: '<script>not executed or semantically graded</script>' });
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  expect(within(report).getByRole('region', { name: 'Conclusion validity' }).textContent).toContain('Valid');
  expect(report.querySelector('script')).toBeNull();
  select('Related premise', ''); expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
});

it('keeps declared B goals visible and sends only a template-declared canonical perturbation', async () => {
  const fetch = mockService(); open(); await ready(); await mode('Break the Method', 'practice-003');
  expect(screen.getByText('Invalidate the original derivation as written')).toBeTruthy();
  select('Declared change', 'change-a'); select('New value', '2');
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/check'))).toBe(false);
  submit(); await feedback();
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/check'))![1]?.body));
  expect(body).toEqual({ mode: 'B', challenge_id: 'practice-003', free_text: null, perturbation: {
    template_id: 'linear-degeneration', rule_id: 'change-a', condition_id: 'parameter-a', type: 'parameter_value', new_value: { source: '2', latex: '2' },
  } });
  await choose('practice-005'); expect(screen.getByText('Change the conclusion')).toBeTruthy();
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
});

it.each(['practice-006', 'practice-007'])('lets a correct C sample %s be judged without inventing a flaw', async (id) => {
  const fetch = mockService(); open(); await ready(); await mode('Judge the AI', 'practice-006');
  if (id !== 'practice-006') await choose(id);
  select('Derivation judgement', 'sound'); select('Conclusion judgement', 'correct'); submit();
  const result = await feedback();
  expect(result.textContent).toContain('Grade: Correct'); expect(result.textContent).toContain('human review');
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/check'))![1]?.body));
  expect(body).toEqual(challenges.answers[id]);
  expect(screen.queryByLabelText('First flawed step')).toBeNull();
  expect(within(result).queryByRole('article', { name: 'Challenge mathematical report' })).toBeNull();
});

it.each(['practice-008', 'practice-009', 'practice-010'])('renders reviewed C proof and conclusion independently for %s', async (id) => {
  mockService(); open(); await ready(); await mode('Judge the AI', 'practice-006'); await choose(id);
  const body = challenges.answers[id]; if (body.mode !== 'C') throw new Error('fixture mode');
  select('Derivation judgement', body.derivation); select('Conclusion judgement', body.conclusion);
  select('Reason category', body.reason_category); select('First flawed step', body.step_id!); select('Related premise', body.assumption_id!);
  submit(); const result = await feedback();
  const reviewed = within(result).getByRole('region', { name: 'Reviewed sample judgement' });
  expect(reviewed.textContent).toContain('Derivation: Not sound');
  expect(reviewed.textContent).toContain(`Conclusion: ${id === 'practice-009' ? 'Correct' : 'Incorrect'}`);
  expect(reviewed.textContent).toContain(`First flaw: Step ${id === 'practice-010' ? 3 : 2}`);
  expect(reviewed.querySelector('.katex')).not.toBeNull();
  expect(result.textContent).toContain('author reviewed'); expect(result.textContent).toContain('Possible repair:');
});

it('does not turn a real-shaped timeout Unknown into Incorrect, and supports retry', async () => {
  let timeout = true;
  mockService((url) => {
    if (url.endsWith('/check') && timeout) return response({ ...challenges.feedbacks['practice-001'], grade: 'Indeterminate', analysis: unknownAnalysis() });
  });
  open(); await ready(); answerA(); submit(); const report = await feedback();
  expect(report.textContent).toContain('Grade: Indeterminate'); expect(report.textContent).toContain('Computation timed out');
  expect(report.textContent).toContain('Unknown'); expect(report.textContent).not.toContain('Grade: Incorrect');
  timeout = false; submit(); expect((await feedback()).textContent).toContain('Grade: Correct');
});

it('shows mathematical Unknown with successful execution as Indeterminate separately from timeout', async () => {
  mockService((url) => url.endsWith('/check') ? response({ ...challenges.feedbacks['practice-001'], grade: 'Indeterminate', analysis: unknownAnalysis('success') }) : undefined);
  open(); await ready(); answerA(); submit(); const report = await feedback();
  expect(report.textContent).toContain('Unknown'); expect(report.textContent).not.toContain('Computation timed out');
});

it.each([422, 404, 503])('keeps HTTP %i out of grading and allows explicit retry', async (status) => {
  let fail = true;
  mockService((url) => url.endsWith('/check') && fail ? response({ detail: 'Rejected for this request' }, status) : undefined);
  open(); await ready(); answerA(); submit();
  expect((await screen.findByRole('alert')).textContent).toContain(`HTTP ${status}`);
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
  fail = false; submit(); expect((await feedback()).textContent).toContain('Correct');
});

it('shows a network failure without an incorrect grade', async () => {
  mockService((url) => url.endsWith('/check') ? Promise.reject(new TypeError('network down')) : undefined);
  open(); await ready(); answerA(); submit();
  expect((await screen.findByRole('alert')).textContent).toContain('Unable to reach the service');
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
});

it('ignores late grading after edits even when fetch ignores abort, and blocks duplicate submission', async () => {
  let resolve!: (response: Response) => void;
  let signal: AbortSignal | null | undefined;
  const fetch = mockService((url, init) => {
    if (url.endsWith('/check')) { signal = init?.signal; return new Promise((done) => { resolve = done; }); }
  });
  open(); await ready(); answerA(); submit();
  fireEvent.submit(screen.getByRole('form', { name: 'Challenge answer' }));
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/check'))).toHaveLength(1);
  select('Related premise', ''); expect(signal?.aborted).toBe(true);
  await act(async () => { resolve(response(challenges.feedbacks['practice-001'])); });
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
  expect(screen.getByRole('button', { name: 'Check answer' }).hasAttribute('disabled')).toBe(false);
});

it('ignores late detail and grading after switching challenges and modes', async () => {
  let resolveDetail!: (response: Response) => void;
  let resolveGrade!: (response: Response) => void;
  mockService((url) => {
    if (url === '/api/challenges/practice-002') return new Promise((done) => { resolveDetail = done; });
    if (url.endsWith('/check')) return new Promise((done) => { resolveGrade = done; });
  });
  open(); await ready(); answerA(); submit(); select('Choose a challenge', 'practice-002');
  await waitFor(() => expect(resolveDetail).toBeTypeOf('function'));
  await mode('Judge the AI', 'practice-006');
  await act(async () => { resolveDetail(response(challenges.details['practice-002'])); resolveGrade(response(challenges.feedbacks['practice-001'])); });
  expect(screen.getByRole('heading', { name: /^Practice 06 ·/ })).toBeTruthy();
  expect(screen.queryByRole('article', { name: 'Challenge feedback' })).toBeNull();
});

it('ignores an older attempt finishing after a newer attempt', async () => {
  const resolvers: ((response: Response) => void)[] = [];
  mockService((url) => url.endsWith('/check') ? new Promise((done) => { resolvers.push(done); }) : undefined);
  open(); await ready(); answerA(); submit(); select('Optional explanation', 'new attempt'); submit();
  await act(async () => { resolvers[1](response({ ...challenges.feedbacks['practice-001'], explanation: 'New attempt result' })); });
  expect((await feedback()).textContent).toContain('New attempt result');
  await act(async () => { resolvers[0](response({ ...challenges.feedbacks['practice-001'], explanation: 'Stale result' })); });
  expect((await feedback()).textContent).not.toContain('Stale result');
});

it('renders an explicit Incorrect grade returned by the backend without deriving it in the browser', async () => {
  mockService((url) => url.endsWith('/check') ? response({ ...challenges.feedbacks['practice-001'], grade: 'Incorrect' }) : undefined);
  open(); await ready(); answerA(); submit(); expect((await feedback()).textContent).toContain('Grade: Incorrect');
});

it('handles empty content and retries failed content loading', async () => {
  let fail = true;
  mockService((url) => url === '/api/challenges' ? response(fail ? { detail: 'not available' } : [], fail ? 503 : 200) : undefined);
  open(); expect((await screen.findByRole('alert')).textContent).toContain('HTTP 503');
  fail = false; fireEvent.click(screen.getByRole('button', { name: 'Retry loading' }));
  expect(await screen.findByText('No reviewed challenges are available in this mode.')).toBeTruthy();
});
