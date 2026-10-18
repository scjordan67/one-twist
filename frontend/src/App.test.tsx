import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { fixtures, integral, linear, unknownAnalysis } from './test/fixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;
function mockService(handler?: Handler) {
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    if (handler) return handler(input, init);
    return service(input, init);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function service(url: string, init?: RequestInit): Response {
  if (url === '/api/challenges') return response([]);
  if (url === '/api/templates') return response(fixtures.summaries.filter((item) => ['linear-degeneration', 'integral-endpoint'].includes(item.id)).reverse());
  if (url.startsWith('/api/templates/')) return response(fixtures.examples[url.split('/').at(-1)!].template);
  const body = JSON.parse(String(init?.body));
  const example = fixtures.examples[body.template_id];
  return response(url === '/api/analyze' ? example.baseline : example.changes[`${body.rule_id}:${body.choice_id ?? body.new_value?.source}`]);
}
function open(path = '/problems', strict = false) {
  const app = <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>;
  return render(strict ? <StrictMode>{app}</StrictMode> : app);
}
async function ready() { await waitFor(() => expect((screen.getByRole('button', { name: 'Analyze change' }) as HTMLButtonElement).disabled).toBe(false)); }
function analyze() { fireEvent.click(screen.getByRole('button', { name: 'Analyze change' })); }
async function changedReport() { return screen.findByRole('article', { name: 'Changed validity report' }); }
function chooseRule(value: string) { fireEvent.change(screen.getByLabelText('Declared change'), { target: { value } }); }
function chooseValue(value: string) { fireEvent.change(screen.getByLabelText('New value'), { target: { value } }); }
function navigate(name: string) { fireEvent.click(within(screen.getByRole('navigation')).getByRole('link', { name })); }

it.each(['cancelled-factor-domain', 'inverse-square-domain'])('submits a declared domain choice and displays retained step restrictions for %s', async (id) => {
  const fetchMock = mockService((url, init) => url === '/api/templates' ? response(fixtures.summaries.filter((item) => item.id === id)) : service(url, init));
  const { container } = open(); await ready();
  expect((screen.getByLabelText('New domain') as HTMLSelectElement).value).toBe('all-real');
  analyze(); const report = await changedReport();
  const body = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === '/api/perturbations')![1]?.body));
  expect(body).toEqual({ template_id: id, rule_id: id === 'cancelled-factor-domain' ? 'allow-all-real' : 'allow-negative-preimages',
    condition_id: 'admissible-domain', type: 'domain', new_value: null, choice_id: 'all-real' });
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  expect(container.querySelector('.condition-changed .domain-summary .katex')).not.toBeNull();
  navigate('Method Inspector');
  expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).toContain('Retained domain constraints');
});

it('shows a defined unchanged logarithm value independently of the invalid real split', async () => {
  const id = 'real-log-product';
  mockService((url, init) => url === '/api/templates' ? response(fixtures.summaries.filter((item) => item.id === id)) : service(url, init));
  open(); await ready(); analyze(); const report = await changedReport();
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  const conclusion = within(report).getByRole('region', { name: 'Conclusion validity' });
  expect(conclusion.textContent).toContain('Valid'); expect(conclusion.textContent).not.toContain('Changed Conclusion');
  expect(within(report).getByText('The conclusion is unchanged.')).toBeTruthy();
  expect(report.textContent).toContain('Well formed');
});

it('renders typed stationary classifications and compares them independently of the method', async () => {
  const id = 'stationary-second-derivative';
  mockService((url, init) => url === '/api/templates' ? response(fixtures.summaries.filter((item) => item.id === id)) : service(url, init));
  open(); await ready(); analyze(); let report = await changedReport();
  expect(within(report).getByRole('region', { name: 'Current outcome' }).textContent).toContain('Classification');
  expect(within(report).getByText('Comparison basis: classification.')).toBeTruthy();
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  chooseRule('positive-control'); analyze(); report = await changedReport();
  expect(within(report).getByText('The conclusion is unchanged.')).toBeTruthy();
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).not.toContain('Invalid Step');
});

it('shows known nonexistence of a point derivative while keeping the function well formed', async () => {
  const id = 'derivative-cusp';
  mockService((url, init) => url === '/api/templates' ? response(fixtures.summaries.filter((item) => item.id === id)) : service(url, init));
  open(); await ready(); analyze(); const report = await changedReport();
  expect(report.textContent).toContain('Well formed');
  expect(within(report).getByRole('region', { name: 'Current outcome' }).textContent).toContain('Derivative does not exist');
  expect(within(report).getByRole('region', { name: 'Current outcome' }).textContent).not.toContain('Unknown');
  navigate('Method Inspector');
  fireEvent.click(screen.getByRole('button', { name: /^Step 1/ }));
  expect(screen.getByRole('region', { name: 'Step 1 validity' }).textContent).toContain('Valid');
});

it('keeps principal-root evaluation locally valid after a sine branch is lost', async () => {
  const id = 'sine-principal-branch';
  mockService((url, init) => url === '/api/templates' ? response(fixtures.summaries.filter((item) => item.id === id)) : service(url, init));
  open('/methods'); await ready(); analyze();
  await waitFor(() => expect(screen.getByRole('region', { name: 'Step 1 validity' }).textContent).toContain('Invalid Step'));
  fireEvent.click(screen.getByRole('button', { name: /^Step 2/ }));
  expect(screen.getByRole('region', { name: 'Step 2 validity' }).textContent).toContain('Valid');
});

it.each([
  ['/', 'Change one condition.'], ['/problems', 'Problem Explorer'], ['/methods', 'Method Inspector'],
  ['/boundaries', 'Boundary Explorer'], ['/challenges', 'Challenge Interface'],
])('opens the independent %s route', async (path, heading) => {
  const fetchMock = mockService(); open(path);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toContain(heading);
  expect(screen.getByRole('navigation').querySelectorAll('a')).toHaveLength(5);
  if (['/problems', '/methods', '/boundaries'].includes(path)) await ready();
  else if (path === '/challenges') await screen.findByText('No reviewed challenges are available in this mode.');
  else expect(fetchMock).not.toHaveBeenCalled();
});

it('loads real-shaped public content then explicitly requests baseline verification, including StrictMode', async () => {
  const fetchMock = mockService(); const { container } = open('/problems', true); await ready();
  expect(screen.getByRole('heading', { name: linear.template.title })).toBeTruthy();
  expect(container.querySelector('.problem-card .katex')).not.toBeNull();
  expect(fetchMock.mock.calls.filter(([url]) => url === '/api/analyze')).toHaveLength(1);
  const baseline = screen.getByRole('article', { name: 'Original validity report' });
  expect(within(baseline).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Valid');
  expect(within(baseline).getByText('The conclusion is unchanged.')).toBeTruthy();
});

it('only submits declared canonical selections on click and renders the three verdict dimensions independently', async () => {
  const fetchMock = mockService(); const { container } = open(); await ready();
  chooseRule('change-a'); chooseValue('2');
  expect(fetchMock.mock.calls.filter(([url]) => url === '/api/perturbations')).toHaveLength(0);
  analyze(); const report = await changedReport();
  const body = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === '/api/perturbations')![1]?.body));
  expect(body).toEqual({ template_id: linear.template.id, rule_id: 'change-a', condition_id: 'parameter-a', type: 'parameter_value', new_value: { source: '2', latex: '2' } });
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Valid');
  const conclusion = within(report).getByRole('region', { name: 'Conclusion validity' });
  expect(conclusion.textContent).toContain('Valid'); expect(conclusion.textContent).toContain('Changed Conclusion');
  expect(within(report).getByRole('region', { name: 'Step validity' }).textContent).toContain('Valid');
  expect(container.querySelectorAll('.condition-changed')).toHaveLength(1);
  expect(container.querySelector('.condition-changed .katex')).not.toBeNull();
  chooseValue('-1');
  expect(screen.queryByRole('article', { name: 'Changed validity report' })).toBeNull();
  expect(screen.getByRole('article', { name: 'Original validity report' })).toBeTruthy();
  expect(fetchMock.mock.calls.filter(([url]) => url === '/api/perturbations')).toHaveLength(1);
});

it('keeps the same result across pages and displays retained constraints, premise evidence and the backend first-invalid finding', async () => {
  const fetchMock = mockService(); const { container } = open(); await ready(); analyze(); await changedReport();
  const calls = fetchMock.mock.calls.length;
  navigate('Method Inspector');
  expect(screen.getByRole('heading', { name: 'Method Inspector' })).toBeTruthy();
  const detail = screen.getByRole('article', { name: 'Step 1 details' });
  expect(detail.textContent).toContain('Algebraic rearrangement');
  expect(detail.textContent).toContain('violated');
  expect(within(detail).getByRole('heading', { name: 'Retained domain constraints' })).toBeTruthy();
  expect(container.querySelector('.step-detail .katex')).not.toBeNull();
  fireEvent.click(within(screen.getByRole('list', { name: 'Derivation steps' })).getByRole('button', { name: /^Step 2/ }));
  expect(screen.getByRole('article', { name: 'Step 2 details' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Original derivation' }));
  expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).not.toContain('Invalid Step');
  navigate('Boundary Explorer');
  expect(screen.getByText(/First established invalid step/).textContent).toContain('Step 1');
  expect(screen.getByRole('region', { name: 'Changed outcome' }).textContent).toContain('Solution set');
  fireEvent.click(screen.getByRole('link', { name: 'Inspect the changed derivation →' }));
  expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).toContain('Invalid Step');
  expect(fetchMock.mock.calls).toHaveLength(calls);
});

it('shows a repairable integral method as Needs Checking while its proper steps are invalid and its divergent conclusion is established', async () => {
  mockService(); open('/boundaries'); await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: integral.template.id } }); await ready();
  chooseValue('1'); analyze();
  await screen.findByRole('heading', { name: 'One condition changed' });
  const method = screen.getByRole('region', { name: 'Method applicability' });
  expect(method.textContent).toContain('Needs Checking'); expect(method.textContent).toContain('one-sided');
  expect(screen.getByRole('region', { name: 'Conclusion validity' }).textContent).toContain('Changed Conclusion');
  expect(screen.getByRole('region', { name: 'Changed outcome' }).textContent).toContain('Divergent');
  expect(screen.getByText(/First established invalid step/).textContent).toContain('Step 1');
});

it.each([503, 422, 404, null])('keeps request failure %s separate from mathematical results and supports a manual retry', async (status) => {
  let attempts = 0;
  mockService((url, init) => {
    if (url === '/api/perturbations' && attempts++ === 0) {
      if (status === null) throw new TypeError('offline');
      return response({ detail: status === 422 ? [{ msg: 'Rejected condition' }] : 'Service unavailable' }, status);
    }
    return service(url, init);
  });
  open(); await ready(); analyze(); const alert = await screen.findByRole('alert');
  expect(alert.textContent).toContain(status === null ? 'Unable to reach' : `HTTP ${status}`);
  expect(screen.queryByRole('article', { name: 'Changed validity report' })).toBeNull();
  fireEvent.click(within(alert).getByRole('button', { name: 'Retry request' })); await changedReport();
  expect(attempts).toBe(2);
});

it.each(['timeout', 'success'] as const)('presents mathematical Unknown with execution %s and no request-error alert', async (status) => {
  mockService((url, init) => url === '/api/perturbations' ? response(unknownAnalysis(status)) : service(url, init));
  open(); await ready(); analyze(); const report = await changedReport();
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Unable to verify:');
  expect(report.textContent).toContain('Unknown');
  expect(within(report).getByText('Comparison not established.')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
  expect(within(report).queryByText(/Computation timed out/)!==null).toBe(status === 'timeout');
});

it('does not infer the first invalid step when the backend reports an earlier unresolved step', async () => {
  const data = structuredClone(linear.changes['set-a-zero:0']);
  data.report.first_invalid_step_id = null; data.report.first_unresolved_step_id = data.replayed_steps[0].id;
  data.report.step[data.replayed_steps[0].id] = unknownAnalysis().report.method;
  mockService((url, init) => url === '/api/perturbations' ? response(data) : service(url, init));
  open('/methods'); await ready(); analyze();
  await waitFor(() => expect(screen.getByText(/First unresolved step/).textContent).toContain('Step 1'));
  expect(screen.getByText(/First established invalid step/).textContent).toContain('not established');
});

it('distinguishes unknown comparison and conditional solution sets from an unchanged complete conclusion', async () => {
  const data = structuredClone(linear.changes['change-a:2']);
  data.report.comparison!.changed = null;
  data.report.perturbed_outcome!.completeness = 'conditional';
  data.report.conclusion = unknownAnalysis('success').report.conclusion;
  mockService((url, init) => url === '/api/perturbations' ? response(data) : service(url, init));
  open(); await ready(); analyze(); const report = await changedReport();
  expect(within(report).getByText('Whether the conclusion changed is not established.')).toBeTruthy();
  expect(within(report).getByText('This is not an established complete solution set.')).toBeTruthy();
});

it('discards a late mutation response after editing even when fetch ignores abort, and prevents duplicate submission', async () => {
  let complete!: (value: Response) => void;
  const fetchMock = mockService((url, init) => url === '/api/perturbations' ? new Promise((resolve) => { complete = resolve; }) : service(url, init));
  open(); await ready(); analyze();
  const pending = screen.getByRole('button', { name: 'Analyzing change…' }) as HTMLButtonElement;
  expect(pending.disabled).toBe(true); fireEvent.click(pending);
  const request = fetchMock.mock.calls.find(([url]) => url === '/api/perturbations')!;
  chooseRule('change-a'); chooseValue('2');
  expect(request[1]?.signal?.aborted).toBe(true);
  await act(async () => complete(response(linear.changes['set-a-zero:0'])));
  expect(screen.queryByRole('article', { name: 'Changed validity report' })).toBeNull();
  expect(fetchMock.mock.calls.filter(([url]) => url === '/api/perturbations')).toHaveLength(1);
});

it('discards a late baseline response after switching templates', async () => {
  let complete!: (value: Response) => void;
  mockService((url, init) => url === '/api/analyze' && JSON.parse(String(init?.body)).template_id === linear.template.id
    ? new Promise((resolve) => { complete = resolve; }) : service(url, init));
  open('/methods'); await screen.findByRole('heading', { name: linear.template.title });
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: integral.template.id } }); await ready();
  await act(async () => complete(response(linear.baseline)));
  expect(screen.getByRole('heading', { name: integral.template.title })).toBeTruthy();
  expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).not.toContain('Algebraic rearrangement');
});

it('recovers from a baseline request error and an empty template list', async () => {
  let attempts = 0;
  mockService((url, init) => url === '/api/analyze' && attempts++ === 0 ? response({}, 503) : service(url, init));
  open('/methods'); const alert = await screen.findByRole('alert');
  expect((screen.getByRole('button', { name: 'Analyze change' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(within(alert).getByRole('button')); await ready();
  cleanup(); mockService(() => response([])); open('/problems');
  await screen.findByText('No examples are available.');
});

it('clears a changed derivation on draft edit across page navigation', async () => {
  mockService(); open('/methods'); await ready(); analyze();
  await waitFor(() => expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).toContain('Invalid Step'));
  chooseRule('change-a'); chooseValue('2');
  expect(screen.queryByRole('article', { name: 'Step 1 details' })).toBeNull();
  navigate('Boundary Explorer'); expect(screen.queryByRole('heading', { name: 'One condition changed' })).toBeNull();
  navigate('Method Inspector'); fireEvent.click(screen.getByRole('button', { name: 'Original derivation' }));
  expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).toContain('Valid');
});

it('retries a failed template-list request only when asked', async () => {
  let attempts = 0;
  mockService((url, init) => {
    if (url === '/api/templates' && attempts++ === 0) throw new TypeError('offline');
    return service(url, init);
  });
  open(); const alert = await screen.findByRole('alert');
  expect(attempts).toBe(1); expect(alert.textContent).toContain('Unable to reach the service');
  fireEvent.click(within(alert).getByRole('button', { name: 'Retry request' })); await ready();
  expect(attempts).toBe(2);
});
