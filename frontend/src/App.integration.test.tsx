/** Real UI -> Vite proxy -> FastAPI -> spawn worker. Start both servers first. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import type { AnalysisResponse } from './api';

const origin = 'http://127.0.0.1:5173';
const nativeFetch = globalThis.fetch;
let analyses: AnalysisResponse[];
beforeEach(() => {
  analyses = [];
  // Resolve relative browser URLs using native HTTP fetch; no responses are mocked.
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    const response = await nativeFetch(new URL(input, origin), init);
    if (input === '/api/analyze' || input === '/api/perturbations') {
      expect(response.status).toBe(200);
      const data = await response.clone().json() as AnalysisResponse;
      expect(data.execution?.status).toBe('success');
      expect(data.execution?.worker_pid).toBeGreaterThan(0);
      analyses.push(data);
    }
    return response;
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function ready() {
  await waitFor(() => expect((screen.getByRole('button', { name: 'Analyze change' }) as HTMLButtonElement).disabled).toBe(false), { timeout: 10_000 });
}
function navigate(name: string) { fireEvent.click(within(screen.getByRole('navigation')).getByRole('link', { name })); }

it('loads the Vite application and computes a real zero-parameter boundary across all explorer pages', async () => {
  const html = await nativeFetch(origin).then((response) => response.text());
  expect(html).toContain('/src/main.tsx');
  render(<MemoryRouter initialEntries={['/problems']}><App /></MemoryRouter>);
  await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: 'linear-degeneration' } }); await ready();
  fireEvent.change(screen.getByLabelText('Declared change'), { target: { value: 'set-a-zero' } });
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  const report = await screen.findByRole('article', { name: 'Changed validity report' }, { timeout: 10_000 });
  expect(report.textContent).toContain('No solution');
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  const latest = analyses.at(-1)!;
  expect(latest.perturbed.problem.parameters[0].value.source).toBe('0');
  expect(latest.report.perturbed_outcome?.value?.latex).toBe('\\emptyset');
  const requests = analyses.length;
  navigate('Method Inspector'); expect(screen.getByRole('article', { name: 'Step 1 details' }).textContent).toContain('Algebraic rearrangement');
  navigate('Boundary Explorer'); expect(screen.getByText(/First established invalid step/).textContent).toContain('Step 1');
  expect(analyses).toHaveLength(requests);
  expect(new Set(analyses.map((analysis) => analysis.execution!.worker_pid)).size).toBe(analyses.length);
});

it('computes regular and singular integral endpoints through actual workers and renders the returned repair', async () => {
  const { container } = render(<MemoryRouter initialEntries={['/boundaries']}><App /></MemoryRouter>);
  await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: 'integral-endpoint' } }); await ready();
  fireEvent.change(screen.getByLabelText('New value'), { target: { value: '3/4' } });
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  await screen.findByRole('heading', { name: 'One condition changed' }, { timeout: 10_000 });
  expect(analyses.at(-1)!.report.perturbed_outcome?.value?.latex).toBe('\\log{\\left(4 \\right)}');
  expect(screen.getByRole('region', { name: 'Method applicability' }).textContent).toContain('Valid');
  fireEvent.change(screen.getByLabelText('New value'), { target: { value: '1' } });
  expect(screen.queryByRole('heading', { name: 'One condition changed' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  await screen.findByRole('heading', { name: 'One condition changed' }, { timeout: 10_000 });
  const method = screen.getByRole('region', { name: 'Method applicability' });
  expect(method.textContent).toContain('Needs Checking'); expect(method.textContent).toContain('one-sided');
  expect(screen.getByRole('region', { name: 'Changed outcome' }).textContent).toContain('Divergent');
  expect(analyses.at(-1)!.report.perturbed_outcome?.value?.latex).toBe('\\infty');
  expect(container.querySelector('.outcome .katex')).not.toBeNull();
  expect(new Set(analyses.filter((analysis) => analysis.template_id === 'integral-endpoint').map((analysis) => analysis.execution!.worker_pid)).size).toBe(3);
});

it('widens an actual domain and preserves the locally valid intermediate step', async () => {
  render(<MemoryRouter initialEntries={['/problems']}><App /></MemoryRouter>);
  await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: 'cancelled-factor-domain' } }); await ready();
  expect(screen.getByLabelText('New domain')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  const report = await screen.findByRole('article', { name: 'Changed validity report' }, { timeout: 10_000 });
  const data = analyses.at(-1)!;
  expect(data.perturbed.perturbation?.type).toBe('domain');
  expect(data.perturbed.perturbation?.choice_id).toBeTruthy();
  expect(data.perturbed.problem.conditions.find((item) => item.domain_binding)?.domain_binding?.current.constraints).toEqual([]);
  expect(Object.values(data.report.step).map((item) => item.labels)).toEqual([['Invalid Step'], ['Valid'], ['Invalid Step']]);
  expect(data.report.comparison?.changed).toBe(true);
  expect(within(report).getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  expect(within(report).getByRole('region', { name: 'Conclusion validity' }).textContent).toContain('Changed Conclusion');
});

it('renders an unchanged real conclusion independently from an invalid logarithm split', async () => {
  render(<MemoryRouter initialEntries={['/boundaries']}><App /></MemoryRouter>);
  await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: 'real-log-product' } }); await ready();
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  await screen.findByRole('heading', { name: 'One condition changed' }, { timeout: 10_000 });
  const data = analyses.at(-1)!;
  expect(data.report.perturbed_outcome?.value?.latex).toBe('0');
  expect(data.report.comparison?.changed).toBe(false);
  expect(screen.getByRole('region', { name: 'Method applicability' }).textContent).toContain('Invalid Step');
  const conclusion = screen.getByRole('region', { name: 'Conclusion validity' });
  expect(conclusion.textContent).toContain('Valid');
  expect(conclusion.textContent).not.toContain('Changed Conclusion');
});

it.each([
  ['derivative-cusp', 'undefined', 'Derivative does not exist'],
  ['stationary-second-derivative', 'classification', 'stationary non extremum'],
])('computes and renders the new %s family through real workers', async (id, status, text) => {
  render(<MemoryRouter initialEntries={['/boundaries']}><App /></MemoryRouter>);
  await ready();
  fireEvent.change(screen.getByLabelText('Choose an example'), { target: { value: id } }); await ready();
  fireEvent.click(screen.getByRole('button', { name: 'Analyze change' }));
  await screen.findByRole('heading', { name: 'One condition changed' }, { timeout: 10_000 });
  const data = analyses.at(-1)!;
  expect(data.report.perturbed_outcome?.status).toBe(status);
  expect(data.report.problem_well_formedness).toBe('WellFormed');
  expect(data.report.comparison?.changed).toBe(true);
  expect(screen.getByRole('region', { name: 'Changed outcome' }).textContent).toContain(text);
  if (status === 'classification') {
    expect(data.report.perturbed_outcome?.classification).toBe('stationary_non_extremum');
    expect(data.report.comparison?.basis).toBe('classification');
    expect(screen.getByText('Comparison basis: classification.')).toBeTruthy();
  }
});
