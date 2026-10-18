export interface MathExpression {
  source: string | null;
  latex: string;
}

export interface Predicate {
  left: MathExpression;
  relation: 'eq' | 'ne' | 'lt' | 'le' | 'gt' | 'ge';
  right: MathExpression;
}

export interface TemplateSummary {
  id: string;
  title: string;
  tags: string[];
  difficulty: string;
}

export interface DomainSpec { number_system: 'real' | 'complex' | 'integer'; constraints: Predicate[] }
export interface DomainBinding { kind: 'domain'; variable: string; current: DomainSpec }
export interface DomainChoice { id: string; label: string; domain: DomainSpec }

export interface PublicTemplate extends TemplateSummary {
  original_problem: {
    statement: string;
    expression: MathExpression;
    goal: string;
    variables: Record<string, 'real' | 'complex' | 'integer'>;
    parameters: { name: string; value: MathExpression; domain: string }[];
    conditions: { id: string; description: string; predicate: Predicate | null; domain_binding?: DomainBinding | null }[];
    domain_constraints: Predicate[];
    well_formedness: 'WellFormed' | 'NoSolution' | 'Divergent' | 'Undefined' | 'ContradictoryConditions' | null;
  };
  allowed_perturbations: {
    id: string;
    condition_id: string;
    type: string;
    description: string;
    allowed_values: MathExpression[];
    domain_choices?: DomainChoice[];
  }[];
}

export type Problem = PublicTemplate['original_problem'];
export type PerturbationRule = PublicTemplate['allowed_perturbations'][number];
export interface Perturbation {
  template_id: string; rule_id: string; condition_id: string; type: string;
  new_value: MathExpression | null;
  choice_id?: string | null;
}
export function initialRuleValue(rule?: PerturbationRule) {
  return rule?.type === 'domain' ? rule.domain_choices?.[0]?.id ?? '' : rule?.allowed_values[0]?.source ?? '';
}
export type ValidityLabel = 'Valid' | 'Needs Checking' | 'Inconvenient' | 'Invalid Step' | 'Changed Conclusion' | 'Unknown';
export interface Evidence { rule_id: string; summary: string; origin: 'computed' | 'author_reviewed'; outcome: string | null }
export interface DimensionResult {
  labels: ValidityLabel[]; evidence: Evidence[];
  affected_refs: { kind: 'step' | 'assumption' | 'condition'; id: string }[];
  reason_if_unknown: string | null; remediation: string | null;
}
export interface Assumption {
  id: string; kind: string; description: string; condition_ids: string[]; predicate: Predicate | null;
  state: 'assumed_true' | 'perturbed_removed' | 'perturbed_false' | 'unchecked';
}
export interface Method { id: string; name: string; description: string; assumption_ids: string[] }
export interface Step {
  id: string; number: number; input: MathExpression; output: MathExpression; method_id: string;
  assumption_ids: string[]; transformation_kind: 'Equivalent' | 'OneWayImplication' | 'CaseSplit';
  domain_constraints: Predicate[]; verification: DimensionResult | null; explanation: string;
}
export interface ConclusionResult {
  status: 'numeric_value' | 'solution_set' | 'divergent' | 'undefined' | 'unknown' | 'classification';
  classification?: 'local_minimum' | 'local_maximum' | 'stationary_non_extremum' | null;
  value: MathExpression | null; completeness: 'complete' | 'partial' | 'conditional' | null;
  reason_if_unknown: string | null;
}
export interface ValidityReport {
  problem_well_formedness: Problem['well_formedness'];
  step: Record<string, DimensionResult>; method: DimensionResult; conclusion: DimensionResult;
  comparison: { basis: 'numeric_value' | 'symbolic_formula' | 'classification'; original: MathExpression;
    perturbed: MathExpression | null; changed: boolean | null } | null;
  first_invalid_step_id: string | null; first_unresolved_step_id: string | null;
  assumptions: Record<string, { status: 'satisfied' | 'violated' | 'needs_checking' | 'unknown'; evidence: Evidence; reason: string | null }>;
  original_outcome: ConclusionResult | null; perturbed_outcome: ConclusionResult | null;
}
export interface AnalysisResponse {
  template_id: string; original_problem: Problem;
  perturbed: { template_id: string; perturbation: Perturbation | null; problem: Problem; assumptions: Assumption[] };
  replayed_steps: Step[]; methods: Method[]; report: ValidityReport; explanations: string[];
  execution: { status: 'success' | 'timeout' | 'failed' | 'result_limit' | 'cancelled'; error: string | null;
    worker_pid: number | null; exit_code: number | null; elapsed_seconds: number } | null;
}

export type ChallengeMode = 'A' | 'B' | 'C';
export type ReasonCategory = 'no_flaw' | 'zero_divisor' | 'improper_endpoint' | 'missing_sign_condition' | 'irreversible_squaring' | 'extraneous_root' | 'lost_root' | 'arithmetic_error';
export type DerivationJudgement = 'sound' | 'not_sound';
export type ConclusionJudgement = 'correct' | 'incorrect' | 'not_established';
export interface ChallengeSummary { id: string; title: string; mode: ChallengeMode }
interface ChallengeBase extends ChallengeSummary {
  prompt: string; problem: Omit<Problem, 'well_formedness'>;
  steps: Pick<Step, 'id' | 'number' | 'input' | 'output' | 'method_id' | 'transformation_kind'>[];
  methods: Pick<Method, 'id' | 'name'>[];
}
interface FlawOptions {
  assumption_options: { id: string; label: string }[];
  reason_options: { id: ReasonCategory; label: string }[];
}
export interface FindFlawChallenge extends ChallengeBase, FlawOptions {
  mode: 'A'; changed_problem: ChallengeBase['problem']; perturbation: Perturbation;
}
export interface BreakMethodChallenge extends ChallengeBase {
  mode: 'B'; template_id: string; goal: 'invalidate_original_derivation' | 'change_conclusion';
  allowed_perturbations: PerturbationRule[];
}
export interface JudgeAIChallenge extends ChallengeBase, FlawOptions {
  mode: 'C'; claimed_conclusion: MathExpression;
}
export type PublicChallenge = FindFlawChallenge | BreakMethodChallenge | JudgeAIChallenge;
interface Selection { step_id: string | null; assumption_id: string | null; reason_category: ReasonCategory }
interface AnswerBase { challenge_id: string; free_text: string | null }
export type ChallengeAnswer = AnswerBase & (
  | ({ mode: 'A' } & Selection)
  | { mode: 'B'; perturbation: Perturbation }
  | ({ mode: 'C'; derivation: DerivationJudgement; conclusion: ConclusionJudgement } & Selection)
);
export interface ChallengeFeedback {
  challenge_id: string; mode: ChallengeMode; grade: 'Correct' | 'Incorrect' | 'Indeterminate';
  explanation: string; evidence: Evidence[]; remediation: string | null;
  analysis: AnalysisResponse | null; free_text: string | null;
  sample_feedback: {
    derivation: DerivationJudgement | null; conclusion: ConclusionJudgement | null;
    first_flaw_step_id: string | null; actual_conclusion: MathExpression | null; reason_if_unknown: string | null;
    annotations: { step_id: string; finding: 'valid' | 'missing_condition' | 'invalid'; assumption_ids: string[]; basis: string }[];
  } | null;
}

export class ApiError extends Error {
  constructor(public status: number | null, message: string) { super(message); }
}

async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { signal, ...(body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }) });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(null, 'Unable to reach the service. Check that the backend is running and try again.');
  }
  if (!response.ok) {
    let detail = '';
    try {
      const data = await response.json() as { detail?: string | { msg: string }[] };
      detail = typeof data.detail === 'string' ? data.detail : data.detail?.map((item) => item.msg).join('; ') ?? '';
    } catch { /* The HTTP status remains useful when no JSON body is available. */ }
    const message = response.status === 503 ? 'The computation service is busy or unavailable. Please retry.'
      : response.status === 422 ? 'The submitted selection was rejected. Check the selection and retry.'
      : response.status === 404 ? 'The requested item is no longer available.' : 'The request failed. Please retry.';
    throw new ApiError(response.status, `${message} (HTTP ${response.status})${detail ? ` ${detail}` : ''}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  templates: (signal?: AbortSignal) => request<TemplateSummary[]>('/templates', signal),
  template: (id: string, signal?: AbortSignal) =>
    request<PublicTemplate>(`/templates/${encodeURIComponent(id)}`, signal),
  analyze: (id: string, signal?: AbortSignal) => request<AnalysisResponse>('/analyze', signal, { template_id: id }),
  perturb: (body: Perturbation, signal?: AbortSignal) => request<AnalysisResponse>('/perturbations', signal, body),
  challenges: (signal?: AbortSignal) => request<ChallengeSummary[]>('/challenges', signal),
  challenge: (id: string, signal?: AbortSignal) => request<PublicChallenge>(`/challenges/${encodeURIComponent(id)}`, signal),
  check: (body: ChallengeAnswer, signal?: AbortSignal) => request<ChallengeFeedback>('/challenges/check', signal, body),
};
