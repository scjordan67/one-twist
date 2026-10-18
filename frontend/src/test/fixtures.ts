import raw from './engine-fixtures.json';
import type { AnalysisResponse, PublicTemplate, TemplateSummary } from '../api';

export const fixtures = raw as unknown as {
  summaries: TemplateSummary[];
  examples: Record<string, { template: PublicTemplate; baseline: AnalysisResponse; changes: Record<string, AnalysisResponse> }>;
};
export const linear = fixtures.examples['linear-degeneration'];
export const integral = fixtures.examples['integral-endpoint'];

export function unknownAnalysis(status: 'timeout' | 'success' = 'timeout'): AnalysisResponse {
  const analysis = structuredClone(linear.changes['set-a-zero:0']);
  const unknown = { labels: ['Unknown' as const], evidence: [], affected_refs: [],
    reason_if_unknown: status === 'timeout' ? 'deadline_exceeded' : 'Unsupported verification rule', remediation: null };
  analysis.report = { ...analysis.report, method: unknown, conclusion: unknown,
    step: Object.fromEntries(analysis.replayed_steps.map((step) => [step.id, unknown])),
    first_invalid_step_id: null, first_unresolved_step_id: analysis.replayed_steps[0].id,
    comparison: null, problem_well_formedness: null, assumptions: {},
    original_outcome: { status: 'unknown', value: null, completeness: null, reason_if_unknown: unknown.reason_if_unknown },
    perturbed_outcome: { status: 'unknown', value: null, completeness: null, reason_if_unknown: unknown.reason_if_unknown },
  };
  analysis.replayed_steps.forEach((step) => { step.output = { source: null, latex: '\\text{Not verified}' }; step.verification = unknown; });
  analysis.execution = { status, error: status === 'timeout' ? 'deadline_exceeded' : null, worker_pid: null, exit_code: null, elapsed_seconds: 3 };
  analysis.explanations = [unknown.reason_if_unknown];
  return analysis;
}
