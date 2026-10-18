import type { AnalysisResponse, ConclusionResult, DimensionResult, DomainSpec, Predicate, Problem, ValidityLabel } from '../api';
import { Math } from '../components/Math';

const relations = { eq: '=', ne: '\\ne', lt: '<', le: '\\le', gt: '>', ge: '\\ge' };
export function PredicateMath({ predicate }: { predicate: Predicate }) {
  return <Math latex={`${predicate.left.latex} ${relations[predicate.relation]} ${predicate.right.latex}`} />;
}
export function DomainSummary({ domain }: { domain: DomainSpec }) {
  const symbols = { real: '\\mathbb{R}', complex: '\\mathbb{C}', integer: '\\mathbb{Z}' };
  return <div className="domain-summary"><Math latex={symbols[domain.number_system]} />
    {domain.constraints.length > 0 && <ul>{domain.constraints.map((predicate, index) => <li key={index}><PredicateMath predicate={predicate} /></li>)}</ul>}
  </div>;
}
const labelClass: Record<ValidityLabel, string> = {
  Valid: 'valid', 'Needs Checking': 'checking', Inconvenient: 'inconvenient', 'Invalid Step': 'invalid',
  'Changed Conclusion': 'changed', Unknown: 'unknown',
};
export function Labels({ labels }: { labels: ValidityLabel[] }) {
  return <span className="labels">{labels.map((label) => <span key={label} className={`label label-${labelClass[label]}`}>{label}</span>)}</span>;
}
export function Dimension({ title, result, analysis }: { title: string; result: DimensionResult; analysis: AnalysisResponse }) {
  function refName(kind: string, id: string) {
    if (kind === 'step') {
      const step = analysis.replayed_steps.find((item) => item.id === id);
      return step ? `Step ${step.number}` : id;
    }
    if (kind === 'assumption') return analysis.perturbed.assumptions.find((item) => item.id === id)?.description ?? id;
    return analysis.perturbed.problem.conditions.find((item) => item.id === id)?.description ?? id;
  }
  return <section className="dimension" aria-label={title}>
    <h3>{title}</h3><Labels labels={result.labels} />
    {result.labels.includes('Needs Checking') && <p className="hint">A prerequisite or repair still needs checking. This is a conditional judgement.</p>}
    {result.reason_if_unknown && <p className="unknown-reason"><strong>Unable to verify:</strong> {result.reason_if_unknown}</p>}
    {result.remediation && <p className="remediation"><strong>Possible repair:</strong> {result.remediation}</p>}
    <details><summary>Evidence and affected references ({result.evidence.length})</summary>
      {result.evidence.length === 0 ? <p>No verification evidence was returned.</p> : <ul>{result.evidence.map((item, index) =>
        <li key={`${item.rule_id}-${index}`}>{item.summary} <small>({item.origin === 'computed' ? 'computed' : 'author reviewed'}{item.outcome ? `; ${item.outcome}` : ''})</small></li>,
      )}</ul>}
      {result.affected_refs.length > 0 && <ul>{result.affected_refs.map((ref) =>
        <li key={`${ref.kind}-${ref.id}`}>{ref.kind}: {refName(ref.kind, ref.id)}</li>,
      )}</ul>}
    </details>
  </section>;
}
const wellFormed = { WellFormed: 'Well formed', NoSolution: 'No solution', Divergent: 'Divergent', Undefined: 'Undefined', ContradictoryConditions: 'Contradictory conditions' };
export function ProblemCard({ title, problem, changedCondition }: { title: string; problem: Omit<Problem, 'well_formedness'>; changedCondition?: string }) {
  return <article className="problem-card">
    <h2>{title}</h2><p>{problem.statement}</p><Math latex={problem.expression.latex} display />
    <div className="parameters">{problem.parameters.map((parameter) => <Math key={parameter.name} latex={`${parameter.name}=${parameter.value.latex}`} />)}</div>
    <p><strong>Goal:</strong> {problem.goal}</p><h3>Conditions</h3>
    <ul className="conditions">{problem.conditions.map((condition) => <li key={condition.id} className={changedCondition === condition.id ? 'condition-changed' : ''}>
      {changedCondition === condition.id && <span className="change-marker">Changed condition</span>}
      {condition.description}{condition.predicate && <div><PredicateMath predicate={condition.predicate} /></div>}
      {condition.domain_binding && <DomainSummary domain={condition.domain_binding.current} />}
    </li>)}</ul>
    {problem.domain_constraints.length > 0 && <><h3>Domain constraints</h3><ul>{problem.domain_constraints.map((predicate, index) =>
      <li key={index}><PredicateMath predicate={predicate} /></li>,
    )}</ul></>}
  </article>;
}
export function Outcome({ title, result }: { title: string; result: ConclusionResult | null }) {
  const names = { numeric_value: 'Numeric value', solution_set: 'Solution set', divergent: 'Divergent', undefined: 'Undefined', unknown: 'Unknown', classification: 'Classification', symbolic_formula: 'Solution formula' };
  return <section className="outcome" aria-label={title}><h3>{title}</h3>
    {!result ? <p>Outcome not established.</p> : <>
      <p>{names[result.status]}{result.completeness ? ` · ${result.completeness}` : ''}</p>
      {result.value && <Math latex={result.value.latex} display />}
      {result.solution_scope && <p>{result.solution_scope === 'unique_solution'
        ? 'Unique solution on the declared time domain.'
        : result.solution_scope === 'verified_witness'
        ? 'One verified solution; uniqueness and a complete solution family are not claimed.'
        : 'Not unique: at least two distinct verified solutions exist. This does not claim they are the complete solution family.'}</p>}
      {result.time_domain && <p>Time domain: <Math latex={result.variable + '\\in'
        + (result.time_domain.left_closed ? '[' : '(') + (result.time_domain.lower?.latex ?? '-\\infty')
        + ',' + (result.time_domain.upper?.latex ?? '\\infty') + (result.time_domain.right_closed ? ']' : ')')} /></p>}
      {result.reason_if_unknown && <p>{result.reason_if_unknown}</p>}
      {result.completeness && result.completeness !== 'complete' && <p>This is not an established complete solution set.</p>}
    </>}
  </section>;
}
export function ExecutionNotice({ analysis }: { analysis: AnalysisResponse }) {
  const execution = analysis.execution;
  if (!execution || execution.status === 'success') return null;
  const names = { timeout: 'Computation timed out', failed: 'Computation could not finish', result_limit: 'Computation exceeded the result limit', cancelled: 'Computation was interrupted' };
  return <aside className="notice" role="status"><strong>{names[execution.status]}.</strong> {execution.error}
    <p>The checks below remain Unknown where verification could not finish. This does not establish an invalid derivation. You can retry the analysis.</p>
  </aside>;
}
export function Comparison({ analysis }: { analysis: AnalysisResponse }) {
  const comparison = analysis.report.comparison;
  return <section aria-label="Conclusion comparison"><h3>Conclusion comparison</h3>
    {!comparison ? <p>Comparison not established.</p> : <>
      <p>{comparison.changed === null ? 'Whether the conclusion changed is not established.' : comparison.changed ? 'The conclusion changed.' : 'The conclusion is unchanged.'}</p>
      <p>Comparison basis: {comparison.basis === 'numeric_value' ? 'numeric value' : comparison.basis === 'classification' ? 'classification' : 'symbolic formula'}.</p>
      <div className="comparison-values"><div><span>Original</span><Math latex={comparison.original.latex} display /></div>
        <div><span>After change</span>{comparison.perturbed ? <Math latex={comparison.perturbed.latex} display /> : <p>Not established</p>}</div></div>
    </>}
  </section>;
}
export function Report({ analysis, title }: { analysis: AnalysisResponse; title: string }) {
  const report = analysis.report;
  return <article className="report-card" aria-label={title}><h2>{title}</h2><ExecutionNotice analysis={analysis} />
    <p><strong>Problem status:</strong> {report.problem_well_formedness ? wellFormed[report.problem_well_formedness] : 'Not established'}</p>
    <p className="hint">Problem status, step validity, method applicability and conclusion changes are separate judgements.</p>
    <section aria-label="Step validity"><h3>Step validity</h3><ol className="step-verdicts">{analysis.replayed_steps.map((step) =>
      <li key={step.id}>Step {step.number}: {report.step[step.id] ? <Labels labels={report.step[step.id].labels} /> : 'Not checked'}</li>,
    )}</ol></section>
    <div className="comparison-grid"><Dimension title="Method applicability" result={report.method} analysis={analysis} />
      <Dimension title="Conclusion validity" result={report.conclusion} analysis={analysis} /></div>
    <div className="comparison-grid"><Outcome title="Original outcome" result={report.original_outcome} /><Outcome title="Current outcome" result={report.perturbed_outcome} /></div>
    <Comparison analysis={analysis} />
    {analysis.explanations.length > 0 && <details><summary>Explanation</summary>{analysis.explanations.map((text, index) => <p key={index}>{text}</p>)}</details>}
  </article>;
}
