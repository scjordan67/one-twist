import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { initialRuleValue, type AnalysisResponse } from '../api';
import { Math } from '../components/Math';
import { useExplorer } from './ExplorerContext';
import { Comparison, Dimension, DomainSummary, ExecutionNotice, Labels, Outcome, PredicateMath, ProblemCard, Report } from './Report';

function RequestError({ message, retry }: { message: string; retry: () => void }) {
  return <div className="request-error" role="alert"><p>{message}</p><p>This request error is separate from a mathematical Unknown judgement.</p><button onClick={retry}>Retry request</button></div>;
}
export function ExplorerPage({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const { state, start, selectTemplate, retryList, retryLoad, submit } = useExplorer();
  useEffect(start, [start]);
  return <section><p className="eyebrow">ONE CONDITION AT A TIME</p><h1>{title}</h1><p className="lead">{description}</p>
    {state.templates.length > 0 && <label className="template-select">Choose an example
      <select value={state.selectedId} onChange={(event) => selectTemplate(event.target.value)}>{state.templates.map((item) =>
        <option key={item.id} value={item.id}>{item.title}</option>,
      )}</select></label>}
    {(state.listStatus === 'loading' || state.loadStatus === 'loading') && <p role="status">Loading example and checking the original derivation…</p>}
    {state.listStatus === 'error' && <RequestError message={state.listError} retry={retryList} />}
    {state.loadStatus === 'error' && <RequestError message={state.loadError} retry={retryLoad} />}
    {state.listStatus === 'ready' && state.templates.length === 0 && <p>No examples are available.</p>}
    {state.template && <><h2>{state.template.title}</h2>
      <ConditionEditor />
      {state.currentError && <RequestError message={state.currentError} retry={() => { void submit(); }} />}
      {children}</>}
  </section>;

}

function ConditionEditor() {
  const { state, edit, submit, retryLoad } = useExplorer();
  const rule = state.template?.allowed_perturbations.find((item) => item.id === state.ruleId);
  const value = rule?.allowed_values.find((item) => item.source === state.valueSource);
  const domainChoice = rule?.domain_choices?.find((item) => item.id === state.valueSource);
  return <form className="condition-editor" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <h2>Change one condition</h2><div className="editor-fields">
      <label>Declared change<select value={state.ruleId} onChange={(event) => {
        const next = state.template?.allowed_perturbations.find((item) => item.id === event.target.value);
        edit(event.target.value, initialRuleValue(next));
      }}>{state.template?.allowed_perturbations.map((item) => <option key={item.id} value={item.id}>{item.description}</option>)}</select></label>
      {rule && rule.allowed_values.length > 0 && <label>New value<select value={state.valueSource} onChange={(event) => edit(state.ruleId, event.target.value)}>
        {rule.allowed_values.map((item) => <option key={item.source} value={item.source ?? ''}>{item.source ?? item.latex}</option>)}
      </select></label>}
      {rule?.type === 'domain' && <label>New domain<select value={state.valueSource} onChange={(event) => edit(state.ruleId, event.target.value)}>
        {rule.domain_choices?.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>}
    </div>
    {value && <p className="value-preview">Selected value: <Math latex={value.latex} /></p>}
    {domainChoice && <div className="value-preview">Selected domain: <DomainSummary domain={domainChoice.domain} /></div>}
    <button className="button" type="submit" disabled={!state.baseline || !rule || state.currentStatus === 'loading'}>{state.currentStatus === 'loading' ? 'Analyzing change…' : 'Analyze change'}</button>
    {state.baseline?.execution && state.baseline.execution.status !== 'success' && <button type="button" onClick={retryLoad}>Retry original analysis</button>}
    <p className="hint">Only declared changes are available. Editing clears the previous changed result; analysis starts when you click.</p>
    {state.currentStatus === 'loading' && <p role="status">Checking this change…</p>}
    <p className="phase-note">Switching examples or editing a pending change stops waiting for its response. The server computation may continue until its own deadline.</p>
  </form>;
}

export function ProblemExplorer() {
  const { state } = useExplorer();
  return <ExplorerPage title="Problem Explorer" description="Compare an original problem with one declared condition change.">
    {state.template && <div className="comparison-grid">
      <ProblemCard title="Original problem" problem={state.template.original_problem} />
      {state.current ? <ProblemCard title="Changed problem" problem={state.current.perturbed.problem} changedCondition={state.current.perturbed.perturbation?.condition_id} />
        : <article className="empty-card"><h2>Changed problem</h2><p>Analyze the selected change to see its problem and verification report.</p></article>}
    </div>}
    {state.baseline && <details className="baseline-report" open={!state.current}><summary>Original analysis</summary><Report title="Original validity report" analysis={state.baseline} /></details>}
    {state.current && <Report title="Changed validity report" analysis={state.current} />}
    <div className="page-links"><Link to="/methods">Inspect each transformation →</Link><Link to="/boundaries">Explore the method boundary →</Link></div>
  </ExplorerPage>;
}
function ViewSelector() {
  const { state, setView } = useExplorer();
  return <div className="view-selector" role="group" aria-label="Derivation to inspect">
    <button aria-pressed={state.view === 'original'} onClick={() => setView('original')}>Original derivation</button>
    <button aria-pressed={state.view === 'perturbed'} onClick={() => setView('perturbed')}>After condition change</button>
  </div>;
}
function Assumptions({ analysis, ids }: { analysis: AnalysisResponse; ids: string[] }) {
  return <ul className="assumptions">{ids.map((id) => {
    const assumption = analysis.perturbed.assumptions.find((item) => item.id === id);
    const check = analysis.report.assumptions[id];
    return <li key={id}><strong>{assumption?.description ?? id}</strong>
      {assumption?.predicate && <div><PredicateMath predicate={assumption.predicate} /></div>}
      <p>Premise state: {assumption?.state.replaceAll('_', ' ') ?? 'not supplied'}. Check: {check?.status.replaceAll('_', ' ') ?? 'not checked'}.</p>
      {check?.status === 'needs_checking' && <p>This premise still needs verification; it has not been established false.</p>}
      {check && <p>{check.evidence.summary}</p>}{check?.reason && <p>{check.reason}</p>}
    </li>;
  })}</ul>;
}
function StepInspector({ analysis }: { analysis: AnalysisResponse }) {
  const { state, selectStep } = useExplorer();
  const step = analysis.replayed_steps.find((item) => item.id === state.selectedStep) ?? analysis.replayed_steps[0];
  const method = analysis.methods.find((item) => item.id === step?.method_id);
  const names = { Equivalent: 'Equivalent transformation', OneWayImplication: 'One-way implication', CaseSplit: 'Case split' };
  return <><ExecutionNotice analysis={analysis} />
    <p>First established invalid step: <strong>{stepName(analysis, analysis.report.first_invalid_step_id)}</strong>.</p>
    <p>First unresolved step: <strong>{stepName(analysis, analysis.report.first_unresolved_step_id)}</strong>. An earlier unresolved check can prevent establishing the first invalid step.</p>
    <div className="inspector-grid"><ol className="step-list" aria-label="Derivation steps">{analysis.replayed_steps.map((item) => <li key={item.id}>
      <button aria-pressed={step?.id === item.id} onClick={() => selectStep(item.id)}>Step {item.number}<Math latex={item.output.latex} display />
        {analysis.report.step[item.id] && <Labels labels={analysis.report.step[item.id].labels} />}</button>
    </li>)}</ol>
      {step && <article className="step-detail" aria-label={`Step ${step.number} details`}><h2>Step {step.number}</h2>
        <p>{names[step.transformation_kind]}</p><h3>Before</h3><Math latex={step.input.latex} display /><h3>After</h3><Math latex={step.output.latex} display />
        <details><summary>Step explanation</summary><p>{step.explanation}</p></details>
        {method && <><h3>Method: {method.name}</h3><p>{method.description}</p></>}
        <h3>Retained domain constraints</h3>{step.domain_constraints.length ? <ul>{step.domain_constraints.map((predicate, index) => <li key={index}><PredicateMath predicate={predicate} /></li>)}</ul> : <p>No additional constraints declared for this step.</p>}
        <h3>Assumptions used by this step</h3>{step.assumption_ids.length ? <Assumptions analysis={analysis} ids={step.assumption_ids} /> : <p>No assumptions referenced.</p>}
        {analysis.report.step[step.id] && <Dimension title={`Step ${step.number} validity`} result={analysis.report.step[step.id]} analysis={analysis} />}
      </article>}
    </div>
    <div className="comparison-grid"><Dimension title="Method applicability" result={analysis.report.method} analysis={analysis} /><Dimension title="Conclusion validity" result={analysis.report.conclusion} analysis={analysis} /></div>
  </>;
}
function stepName(analysis: AnalysisResponse, id: string | null) {
  if (!id) return 'not established';
  const step = analysis.replayed_steps.find((item) => item.id === id);
  return step ? `Step ${step.number}` : id;
}
export function MethodInspector() {
  const { state } = useExplorer();
  const analysis = state.view === 'original' ? state.baseline : state.current;
  return <ExplorerPage title="Method Inspector" description="Inspect each transformation, its assumptions and its justification.">
    <ViewSelector />{analysis ? <StepInspector analysis={analysis} /> : <p>Analyze the selected change to inspect its derivation.</p>}
  </ExplorerPage>;
}
export function BoundaryExplorer() {
  const { state, setView } = useExplorer();
  const analysis = state.current;
  const conditionId = analysis?.perturbed.perturbation?.condition_id;
  const originalCondition = analysis?.original_problem.conditions.find((item) => item.id === conditionId);
  const changedCondition = analysis?.perturbed.problem.conditions.find((item) => item.id === conditionId);
  const affected = analysis?.perturbed.assumptions.filter((item) => item.condition_ids.includes(conditionId ?? '')).map((item) => item.id) ?? [];
  return <ExplorerPage title="Boundary Explorer" description="Trace a changed condition through assumptions, steps, method applicability and the conclusion.">
    {!analysis ? <p>Analyze a condition change to explore its boundary. The original result alone does not establish a boundary.</p> : <>
      <ExecutionNotice analysis={analysis} /><article className="report-card"><h2>One condition changed</h2>
        <div className="comparison-grid"><section><h3>Original condition</h3><p>{originalCondition?.description ?? 'Not supplied'}</p>{originalCondition?.predicate && <PredicateMath predicate={originalCondition.predicate} />}
          {originalCondition?.domain_binding && <DomainSummary domain={originalCondition.domain_binding.current} />}</section>
          <section><h3>Changed condition</h3><p>{changedCondition?.description ?? 'Condition removed'}</p>{changedCondition?.predicate && <PredicateMath predicate={changedCondition.predicate} />}
            {changedCondition?.domain_binding && <DomainSummary domain={changedCondition.domain_binding.current} />}</section></div>
        <h3>Assumptions linked to this condition</h3>{affected.length ? <Assumptions analysis={analysis} ids={affected} /> : <p>No directly linked assumptions were returned.</p>}
        <p className="hint">A failed premise alone does not establish that every use of the method fails or that the conclusion is wrong.</p>
        <h3>Step boundary</h3><p>First established invalid step: <strong>{stepName(analysis, analysis.report.first_invalid_step_id)}</strong>.</p>
        <p>First unresolved step: <strong>{stepName(analysis, analysis.report.first_unresolved_step_id)}</strong>.</p>
        <p className="hint">These positions come from the verifier. Unresolved earlier checks can prevent a first-invalid finding.</p>
        <ol>{analysis.replayed_steps.map((step) => <li key={step.id}>Step {step.number}: {analysis.report.step[step.id] && <Labels labels={analysis.report.step[step.id].labels} />}</li>)}</ol>
        <Link to="/methods" onClick={() => setView('perturbed')}>Inspect the changed derivation →</Link>
        <div className="comparison-grid"><Dimension title="Method applicability" result={analysis.report.method} analysis={analysis} /><Dimension title="Conclusion validity" result={analysis.report.conclusion} analysis={analysis} /></div>
        <div className="comparison-grid"><Outcome title="Original outcome" result={analysis.report.original_outcome} /><Outcome title="Changed outcome" result={analysis.report.perturbed_outcome} /></div>
        <Comparison analysis={analysis} />
        {analysis.explanations.map((text, index) => <p key={index}>{text}</p>)}
      </article>
    </>}
  </ExplorerPage>;
}
