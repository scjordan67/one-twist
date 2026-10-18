import { createContext, useCallback, useContext, useEffect, useReducer, useRef, type ReactNode } from 'react';
import { api, initialRuleValue, type AnalysisResponse, type PublicTemplate, type TemplateSummary } from '../api';

type Status = 'idle' | 'loading' | 'ready' | 'error';
type View = 'original' | 'perturbed';
interface State {
  started: boolean; templates: TemplateSummary[]; listStatus: Status; listError: string; listAttempt: number;
  selectedId: string; template: PublicTemplate | null; baseline: AnalysisResponse | null;
  loadStatus: Status; loadError: string; loadAttempt: number;
  ruleId: string; valueSource: string; current: AnalysisResponse | null; currentStatus: Status; currentError: string;
  view: View; selectedStep: string;
}
const initial: State = {
  started: false, templates: [], listStatus: 'idle', listError: '', listAttempt: 0,
  selectedId: '', template: null, baseline: null, loadStatus: 'idle', loadError: '', loadAttempt: 0,
  ruleId: '', valueSource: '', current: null, currentStatus: 'idle', currentError: '', view: 'original', selectedStep: '',
};
type Action =
  | { type: 'start' | 'listLoading' | 'retryList' | 'retryLoad' | 'loadStart' | 'submit' }
  | { type: 'listLoaded'; items: TemplateSummary[] }
  | { type: 'listError' | 'loadError' | 'analysisError'; message: string }
  | { type: 'select'; id: string }
  | { type: 'templateLoaded'; template: PublicTemplate }
  | { type: 'baselineLoaded' | 'analyzed'; analysis: AnalysisResponse }
  | { type: 'draft'; ruleId: string; valueSource: string }
  | { type: 'view'; view: View }
  | { type: 'step'; id: string };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'start': return state.started ? state : { ...state, started: true };
    case 'listLoading': return { ...state, listStatus: 'loading', listError: '' };
    case 'listLoaded': return { ...state, listStatus: 'ready', templates: action.items, selectedId: action.items[0]?.id ?? '' };
    case 'listError': return { ...state, listStatus: 'error', listError: action.message };
    case 'retryList': return { ...state, listAttempt: state.listAttempt + 1 };
    case 'select': return { ...state, selectedId: action.id, template: null, baseline: null, current: null,
      loadStatus: 'loading', loadError: '', currentStatus: 'idle', currentError: '', ruleId: '', valueSource: '', selectedStep: '', view: 'original' };
    case 'retryLoad': return { ...state, loadAttempt: state.loadAttempt + 1 };
    case 'loadStart': return { ...state, template: null, baseline: null, current: null, loadStatus: 'loading', loadError: '',
      currentStatus: 'idle', currentError: '', selectedStep: '', view: 'original' };
    case 'templateLoaded': return action.template.id !== state.selectedId ? state : { ...state, template: action.template,
      ruleId: action.template.allowed_perturbations[0]?.id ?? '', valueSource: initialRuleValue(action.template.allowed_perturbations[0]) };
    case 'baselineLoaded': return action.analysis.template_id !== state.selectedId ? state : { ...state,
      baseline: action.analysis, loadStatus: 'ready', selectedStep: action.analysis.replayed_steps[0]?.id ?? '' };
    case 'loadError': return { ...state, loadStatus: 'error', loadError: action.message };
    case 'draft': return { ...state, ruleId: action.ruleId, valueSource: action.valueSource, current: null,
      currentStatus: 'idle', currentError: '', selectedStep: '' };
    case 'submit': return { ...state, current: null, currentStatus: 'loading', currentError: '', view: 'perturbed', selectedStep: '' };
    case 'analyzed': return action.analysis.template_id !== state.selectedId ? state : { ...state,
      current: action.analysis, currentStatus: 'ready', view: 'perturbed', selectedStep: action.analysis.report.first_invalid_step_id
        ?? action.analysis.report.first_unresolved_step_id ?? action.analysis.replayed_steps[0]?.id ?? '' };
    case 'analysisError': return { ...state, currentStatus: 'error', currentError: action.message };
    case 'view': return { ...state, view: action.view, selectedStep: '' };
    case 'step': return { ...state, selectedStep: action.id };
  }
}
interface Explorer {
  state: State; start: () => void; selectTemplate: (id: string) => void;
  edit: (ruleId: string, valueSource: string) => void; submit: () => Promise<void>;
  retryList: () => void; retryLoad: () => void; setView: (view: View) => void; selectStep: (id: string) => void;
}
const Context = createContext<Explorer | null>(null);
const message = (error: unknown) => error instanceof Error ? error.message : 'The request could not be completed.';

export function ExplorerProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const mutation = useRef<{ controller: AbortController; pending: boolean } | null>(null);
  const start = useCallback(() => dispatch({ type: 'start' }), []);
  useEffect(() => {
    if (!state.started) return;
    const controller = new AbortController();
    dispatch({ type: 'listLoading' });
    api.templates(controller.signal).then((items) => {
      if (!controller.signal.aborted) dispatch({ type: 'listLoaded', items });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) dispatch({ type: 'listError', message: message(error) });
    });
    return () => controller.abort();
  }, [state.started, state.listAttempt]);
  useEffect(() => {
    if (!state.selectedId) return;
    const controller = new AbortController();
    dispatch({ type: 'loadStart' });
    void (async () => {
      try {
        const template = await api.template(state.selectedId, controller.signal);
        if (controller.signal.aborted) return;
        dispatch({ type: 'templateLoaded', template });
        const analysis = await api.analyze(template.id, controller.signal);
        if (!controller.signal.aborted) dispatch({ type: 'baselineLoaded', analysis });
      } catch (error) {
        if (!controller.signal.aborted) dispatch({ type: 'loadError', message: message(error) });
      }
    })();
    return () => controller.abort();
  }, [state.selectedId, state.loadAttempt]);
  useEffect(() => () => mutation.current?.controller.abort(), []);
  function cancelWaiting() { mutation.current?.controller.abort(); mutation.current = null; }
  function selectTemplate(id: string) {
    if (id === state.selectedId) return;
    cancelWaiting(); dispatch({ type: 'select', id });
  }
  function edit(ruleId: string, valueSource: string) {
    cancelWaiting(); dispatch({ type: 'draft', ruleId, valueSource });
  }
  async function submit() {
    const rule = state.template?.allowed_perturbations.find((item) => item.id === state.ruleId);
    const value = rule?.allowed_values.find((item) => item.source === state.valueSource);
    const domainChoice = rule?.domain_choices?.find((item) => item.id === state.valueSource);
    if (!state.template || !state.baseline || !rule || (rule.allowed_values.length > 0 && !value) || mutation.current?.pending) return;
    if (rule.type === 'domain' && !domainChoice) return;
    const job = { controller: new AbortController(), pending: true };
    mutation.current = job;
    dispatch({ type: 'submit' });
    try {
      const analysis = await api.perturb({ template_id: state.template.id, rule_id: rule.id,
        condition_id: rule.condition_id, type: rule.type, new_value: value ?? null,
        ...(rule.type === 'domain' ? { choice_id: domainChoice!.id } : {}) }, job.controller.signal);
      if (mutation.current === job && !job.controller.signal.aborted) dispatch({ type: 'analyzed', analysis });
    } catch (error) {
      if (mutation.current === job && !job.controller.signal.aborted) dispatch({ type: 'analysisError', message: message(error) });
    } finally { if (mutation.current === job) job.pending = false; }
  }
  return <Context.Provider value={{ state, start, selectTemplate, edit, submit,
    retryList: () => dispatch({ type: 'retryList' }),
    retryLoad: () => { cancelWaiting(); dispatch({ type: 'retryLoad' }); },
    setView: (view) => dispatch({ type: 'view', view }), selectStep: (id) => dispatch({ type: 'step', id }),
  }}>{children}</Context.Provider>;
}

export function useExplorer() {
  const value = useContext(Context);
  if (!value) throw new Error('ExplorerProvider is required');
  return value;
}
