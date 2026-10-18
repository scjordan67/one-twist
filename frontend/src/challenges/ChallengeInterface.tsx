import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, initialRuleValue, type ChallengeAnswer, type ChallengeFeedback, type ChallengeMode, type ChallengeSummary,
  type ConclusionJudgement, type DerivationJudgement, type PublicChallenge, type ReasonCategory } from '../api';
import { Math } from '../components/Math';
import { DomainSummary, ProblemCard, Report } from '../explorer/Report';

const modes: Record<ChallengeMode, string> = { A: 'Find the Flaw', B: 'Break the Method', C: 'Judge the AI' };
const derivations = { sound: 'Sound', not_sound: 'Not sound' };
const conclusions = { correct: 'Correct', incorrect: 'Incorrect', not_established: 'Not established' };
const errorText = (error: unknown) => error instanceof Error ? error.message : 'The request could not finish. Please retry.';

export function ChallengeInterface() {
  const [mode, setMode] = useState<ChallengeMode>('A');
  const [list, setList] = useState<ChallengeSummary[] | null>(null);
  const [id, setId] = useState('');
  const [detail, setDetail] = useState<PublicChallenge | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    api.challenges(controller.signal).then((items) => { if (current) setList(items); })
      .catch((err: unknown) => { if (current) setError(errorText(err)); });
    return () => { current = false; controller.abort(); };
  }, [retry]);
  const choices = list?.filter((item) => item.mode === mode) ?? [];
  const selected = choices.some((item) => item.id === id) ? id : choices[0]?.id ?? '';
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let current = true;
    setDetail(null); setError(null);
    api.challenge(selected, controller.signal).then((item) => { if (current) setDetail(item); })
      .catch((err: unknown) => { if (current) setError(errorText(err)); });
    return () => { current = false; controller.abort(); };
  }, [selected, retry]);
  function choose(nextMode: ChallengeMode, nextId = '') { setMode(nextMode); setId(nextId); setDetail(null); setError(null); }
  return <section><p className="eyebrow">PRACTICE THE BOUNDARIES</p><h1>Challenge Interface</h1>
    <p className="lead">Make a judgement, then check its evidence. A correct answer and a sound derivation are separate questions.</p>
    <div className="view-selector" role="group" aria-label="Challenge mode">{(Object.keys(modes) as ChallengeMode[]).map((key) =>
      <button key={key} aria-pressed={mode === key} onClick={() => { if (mode !== key) choose(key); }}>{modes[key]}</button>)}</div>
    {list === null && !error && <p role="status">Loading challenges…</p>}
    {list && choices.length === 0 && <p>No reviewed challenges are available in this mode.</p>}
    {choices.length > 0 && <label className="template-select">Choose a challenge<select value={selected} onChange={(event) => choose(mode, event.target.value)}>
      {choices.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>}
    {error && <div className="request-error" role="alert"><p>{error}</p><button onClick={() => { setError(null); setRetry((value) => value + 1); }}>Retry loading</button></div>}
    {selected && !detail && !error && <p role="status">Loading challenge…</p>}
    {detail && detail.id === selected && <ChallengeSession key={detail.id} challenge={detail} />}
  </section>;
}

function ChallengeSession({ challenge }: { challenge: PublicChallenge }) {
  const [step, setStep] = useState('');
  const [premise, setPremise] = useState('');
  const [reason, setReason] = useState<ReasonCategory | ''>('');
  const [derivation, setDerivation] = useState<DerivationJudgement | ''>('');
  const [conclusion, setConclusion] = useState<ConclusionJudgement | ''>('');
  const [ruleId, setRuleId] = useState(challenge.mode === 'B' ? challenge.allowed_perturbations[0]?.id ?? '' : '');
  const rule = challenge.mode === 'B' ? challenge.allowed_perturbations.find((item) => item.id === ruleId) : undefined;
  const [value, setValue] = useState(initialRuleValue(rule));
  const domainChoice = rule?.domain_choices?.find((item) => item.id === value);
  const [text, setText] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<ChallengeFeedback | null>(null);
  const job = useRef<AbortController | null>(null);
  useEffect(() => () => { job.current?.abort(); job.current = null; }, []);
  function edit() {
    job.current?.abort(); job.current = null;
    setPending(false); setError(null); setFeedback(null);
  }
  const needsFlaw = reason !== '' && reason !== 'no_flaw';
  const valid = challenge.mode === 'B' ? !!rule && (rule.type === 'domain' ? !!domainChoice : rule.allowed_values.length === 0 || rule.allowed_values.some((item) => item.source === value))
    : !!reason && (!needsFlaw || !!step) && (challenge.mode === 'A' || !!derivation && !!conclusion);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || job.current) return;
    const controller = new AbortController(); job.current = controller;
    setPending(true); setError(null); setFeedback(null);
    const common = { challenge_id: challenge.id, free_text: text || null };
    let body: ChallengeAnswer;
    if (challenge.mode === 'B' && rule) {
      body = { ...common, mode: 'B', perturbation: { template_id: challenge.template_id, rule_id: rule.id,
        condition_id: rule.condition_id, type: rule.type, new_value: rule.allowed_values.find((item) => item.source === value) ?? null,
        ...(rule.type === 'domain' ? { choice_id: domainChoice!.id } : {}) } };
    } else {
      const selection = { step_id: needsFlaw ? step : null, assumption_id: needsFlaw ? premise || null : null, reason_category: reason as ReasonCategory };
      body = challenge.mode === 'A' ? { ...common, mode: 'A', ...selection }
        : { ...common, mode: 'C', ...selection, derivation: derivation as DerivationJudgement, conclusion: conclusion as ConclusionJudgement };
    }
    try {
      const result = await api.check(body, controller.signal);
      if (job.current === controller && result.challenge_id === challenge.id && result.mode === challenge.mode) setFeedback(result);
    } catch (err) { if (job.current === controller) setError(errorText(err)); }
    finally { if (job.current === controller) { job.current = null; setPending(false); } }
  }
  return <><h2>{challenge.title} · {modes[challenge.mode]}</h2><p>{challenge.prompt}</p>
    {challenge.mode === 'A' ? <div className="comparison-grid">
      <ProblemCard title="Original problem" problem={challenge.problem} />
      <ProblemCard title="Changed problem" problem={challenge.changed_problem} changedCondition={challenge.perturbation.condition_id} />
    </div> : <ProblemCard title="Problem" problem={challenge.problem} />}
    <article className="report-card" aria-label="Presented derivation"><h2>Presented derivation</h2>
      <p className="hint">These are the proposed steps to inspect. Transformation types are claims made by the derivation.</p>
      <ol className="presented-steps">{challenge.steps.map((item) => <li key={item.id}><h3>Step {item.number}</h3>
        <p>{challenge.methods.find((method) => method.id === item.method_id)?.name} · Claimed: {item.transformation_kind}</p>
        <Math latex={item.input.latex} display /><span>to</span><Math latex={item.output.latex} display /></li>)}</ol>
      {challenge.mode === 'C' && <><h3>Claimed conclusion</h3><Math latex={challenge.claimed_conclusion.latex} display /></>}
    </article>
    <form className="condition-editor challenge-form" onSubmit={(event) => { void submit(event); }} aria-label="Challenge answer">
      <h2>Your judgement</h2>
      {challenge.mode === 'B' ? <>
        <p><strong>Challenge goal:</strong> {challenge.goal === 'change_conclusion' ? 'Change the conclusion' : 'Invalidate the original derivation as written'}</p>
        <label>Declared change<select value={ruleId} onChange={(event) => {
          edit(); setRuleId(event.target.value);
          setValue(initialRuleValue(challenge.allowed_perturbations.find((item) => item.id === event.target.value)));
        }}>{challenge.allowed_perturbations.map((item) => <option key={item.id} value={item.id}>{item.description}</option>)}</select></label>
        {rule && rule.allowed_values.length > 0 && <label>New value<select value={value} onChange={(event) => { edit(); setValue(event.target.value); }}>
          {rule.allowed_values.map((item) => <option key={item.source} value={item.source ?? ''}>{item.source}</option>)}</select></label>}
        {rule?.type === 'domain' && <label>New domain<select value={value} onChange={(event) => { edit(); setValue(event.target.value); }}>
          {rule.domain_choices?.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
        {domainChoice && <DomainSummary domain={domainChoice.domain} />}
        {rule?.allowed_values.find((item) => item.source === value) && <p>Selected value: <Math latex={rule.allowed_values.find((item) => item.source === value)!.latex} /></p>}
      </> : <>
        {challenge.mode === 'C' && <div className="editor-fields"><label>Derivation judgement<select value={derivation} onChange={(event) => {
          edit(); const next = event.target.value as DerivationJudgement | ''; setDerivation(next);
          setReason(next === 'sound' ? 'no_flaw' : ''); setStep(''); setPremise('');
        }}><option value="">Choose a judgement</option>{Object.entries(derivations).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label>Conclusion judgement<select value={conclusion} onChange={(event) => { edit(); setConclusion(event.target.value as ConclusionJudgement | ''); }}>
            <option value="">Choose a judgement</option>{Object.entries(conclusions).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div>}
        <label>Reason category<select value={reason} disabled={challenge.mode === 'C' && derivation !== 'not_sound'} onChange={(event) => {
          edit(); setReason(event.target.value as ReasonCategory | ''); if (event.target.value === 'no_flaw') { setStep(''); setPremise(''); }
        }}><option value="">Choose a reason</option>{challenge.reason_options.filter((item) => challenge.mode === 'A' || derivation === 'sound' || item.id !== 'no_flaw').map((item) =>
          <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        {reason && <p className="hint">Selected reason: {challenge.reason_options.find((item) => item.id === reason)?.label}</p>}
        {needsFlaw && <div className="editor-fields"><label>First flawed step<select value={step} onChange={(event) => { edit(); setStep(event.target.value); }}>
          <option value="">Choose a step</option>{challenge.steps.map((item) => <option key={item.id} value={item.id}>Step {item.number}</option>)}</select></label>
          <label>Related premise<select value={premise} onChange={(event) => { edit(); setPremise(event.target.value); }}>
            <option value="">No premise selected</option>{challenge.assumption_options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>}
        {needsFlaw && premise && <p className="hint">Selected premise: {challenge.assumption_options.find((item) => item.id === premise)?.label}</p>}
      </>}
      <label>Optional explanation<textarea value={text} maxLength={4000} rows={3} onChange={(event) => { edit(); setText(event.target.value); }} /></label>
      <p className="hint">Your explanation is returned with this attempt; it is not saved or automatically graded.</p>
      <button className="button" disabled={!valid || pending} type="submit">{pending ? 'Checking answer…' : 'Check answer'}</button>
      {pending && <p role="status">Checking this attempt…</p>}
      <p className="hint">Editing or switching challenges clears feedback. Cancelling a browser request does not cancel computation already running on the server.</p>
      {error && <div className="request-error" role="alert"><p>{error}</p><p>No grade was returned. Check your selection and retry.</p></div>}
    </form>
    {feedback && <Feedback feedback={feedback} challenge={challenge} />}
  </>;
}

function Feedback({ feedback, challenge }: { feedback: ChallengeFeedback; challenge: PublicChallenge }) {
  const reviewed = feedback.sample_feedback;
  const stepName = (id: string | null) => id ? `Step ${challenge.steps.find((item) => item.id === id)?.number ?? id}` : 'None established';
  return <article className="report-card" aria-label="Challenge feedback" aria-live="polite">
    <h2>Grade: {feedback.grade}</h2><p>{feedback.explanation}</p>
    {feedback.grade === 'Indeterminate' && <p className="notice">This attempt cannot be graded from the available evidence. It is not an incorrect answer.</p>}
    {reviewed && <section aria-label="Reviewed sample judgement"><h3>Human-reviewed findings</h3>
      <p>Derivation: <strong>{reviewed.derivation ? derivations[reviewed.derivation] : 'Not established'}</strong></p>
      <p>Conclusion: <strong>{reviewed.conclusion ? conclusions[reviewed.conclusion] : 'Not established'}</strong></p>
      <p>First flaw: {stepName(reviewed.first_flaw_step_id)}</p>
      {reviewed.reason_if_unknown && <p className="unknown-reason">{reviewed.reason_if_unknown}</p>}
      {reviewed.actual_conclusion && <><h3>Reviewed mathematical result</h3><Math latex={reviewed.actual_conclusion.latex} display /></>}
      <ol>{reviewed.annotations.map((item) => <li key={item.step_id}><strong>{stepName(item.step_id)} · {item.finding.replace('_', ' ')}</strong><p>{item.basis}</p></li>)}</ol>
    </section>}
    {feedback.remediation && <p className="remediation"><strong>Possible repair:</strong> {feedback.remediation}</p>}
    {feedback.analysis && <><p>First established invalid step: {stepName(feedback.analysis.report.first_invalid_step_id)}</p>
      <p>First unresolved step: {stepName(feedback.analysis.report.first_unresolved_step_id)}</p></>}
    <details><summary>Grading evidence ({feedback.evidence.length})</summary><ul>{feedback.evidence.map((item, index) =>
      <li key={index}>{item.summary} <small>({item.origin === 'computed' ? 'computed' : 'author reviewed'})</small></li>)}</ul></details>
    {feedback.free_text && <section><h3>Your ungraded explanation</h3><p className="attempt-text">{feedback.free_text}</p></section>}
    {feedback.analysis && <Report analysis={feedback.analysis} title="Challenge mathematical report" />}
  </article>;
}
