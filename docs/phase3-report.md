# Phase 3: Interactive Explorer

Implemented on Windows on 2026-10-17. This is the implementation report for
independent review, not a claim that Phase 3 has already been accepted.

## Scope and pages

| Page | Delivered behavior |
| --- | --- |
| Home | Project idea, entry point, three future practice modes and current exploration instructions |
| Problem Explorer | Real template selection, original baseline analysis, one declared condition/value editor, explicit submission, original/changed problem comparison and validity reports |
| Method Inspector | Independent `/methods` route; original/changed derivation selection; clickable steps; before/after KaTeX; method names; retained constraints; premise states and checks; expandable explanations and evidence |
| Boundary Explorer | Independent `/boundaries` route; condition comparison, linked assumptions, backend-reported first invalid/unresolved steps, actual checker repair suggestions and independent conclusion outcomes |
| Challenge Interface | Original Phase 1 placeholder; no challenge or grading requests |

Only the two existing draft templates are used. No mathematical rule, template
or challenge mode has been added. The sole backend contract addition is
`AnalysisResponse.methods`, populated from the template in both normal and
unverified responses. The public GET DTO still excludes solution steps, answers,
assumptions, verification rules and expected failure mechanisms.

## State and request behavior

`ExplorerContext.tsx` owns one in-memory Context/useReducer session. Baseline
and changed responses are separate. All three explorer pages can initialize
directly and share the same selection/results without re-running calculations
when navigating. Home and Challenge Interface do not initiate calculations.
There is no new state library, database, history, persistent storage or cache.

Template loading fetches the public detail before requesting `/api/analyze` for
the original problem. Only an explicit click calls `/api/perturbations` for the
selected change. Inputs come from the template's declared rules and exact
values, and the server remains authoritative. Editing clears the changed
response; a disabled pending button plus a synchronous pending-job reference
prevents duplicate submission.

Template requests have AbortControllers; changed requests also use job identity
checks. Aborted or superseded results are ignored even when fetch still resolves.
Navigation retains a session, while reload resets it. Aborting a browser wait
does not claim to cancel the server's worker or immediately recover capacity.

## Mathematical presentation

- Step, method and conclusion results render independently; every returned
  label is shown. A changed conclusion can coexist with Valid. No client-side
  validity classification is performed.
- Problem status is separate: no solution and divergence are established
  outcomes, distinct from undefined mathematics and unknown verification.
- Needs Checking is presented as a conditional judgement. Unknown displays the
  verifier's reason. A timeout has an execution notice and an Unknown report,
  without inventing a wrong-answer judgement.
- Remediation text, evidence and affected references come from the actual
  response. Inconvenient is never inferred by the UI. Expandable evidence shows
  computed versus author-reviewed origin.
- First-invalid and first-unresolved positions use only the backend fields.
  A later invalid step is not promoted when the first-invalid field is null.
- Comparison `changed: null` is unresolved, not unchanged; partial/conditional
  solution sets are explicitly identified as incomplete conclusions.
- All expression/predicate/outcome fields use the existing trusted-off KaTeX
  wrapper. Explanatory prose remains text. A selector shows the allowed source
  value for input, with a KaTeX preview alongside it.
- HTTP 422/404/503 and network failures have retryable request-error UI, separate
  from mathematical Unknown. Retries are explicit, with no background loops.

## Verification

Run from the repository root for Python, or `frontend` for npm commands.

| Command | Actual result |
| --- | --- |
| `uv run --frozen pytest -q` | **202 passed**, 1 existing Starlette/HTTPX deprecation warning, 23.04s |
| `npm.cmd test` | **24 passed**: component/session tests plus KaTeX tests |
| `npm.cmd run test:integration` | **2 passed**, real React DOM → native HTTP → Vite proxy → FastAPI → spawn computations |
| `npm.cmd run test:browser` | **4 passed**, actual headless Edge, desktop 1440×1000 and mobile viewport 390×844 |
| `npm.cmd run typecheck` | Passed, including application code and browser tests/configuration |
| `npm.cmd run build` | Passed; Vite emits a chunk-size advisory for the KaTeX-containing application bundle |

The live commands require the backend on 8000 and Vite on 5173. They never
replace API responses with fixtures. They check worker execution status and
values, including `a=0` (empty solution set), `b=3/4` (log 4), and `b=1` (+∞),
with the last case retaining Invalid Step, a Needs Checking method and the
verifier's one-sided-limit repair. Browser checks also exercise `a=2` and `a=-1`,
cross-page navigation, formulas, preserved constraints and absence of whole-page
horizontal overflow. No browser page errors were observed.

Unit tests intentionally use API-shaped fixtures to exercise failures and races:
late baseline response after a template switch; late mutation after editing
despite abort being ignored; explicit submission; duplicate prevention; shared
page state; original/changed view switching; step selection; null first-invalid
with earlier unresolved checks; conditional solution sets; timeout and successful
execution with mathematical Unknown; 422/404/503/network errors and manual retry;
empty content; list and baseline recovery; StrictMode initialization.

`scripts/export_explorer_fixtures.py` refreshes the fixture JSON through actual
API/spawn calls. Execution timing/PIDs are omitted and label sets sorted for
stable snapshots. Fixtures are imported only by tests, not by the application.
Backend tests continue to check the mathematics independently of these snapshots.

## Browser review and limits

The in-app browser connection failed before bootstrap with an environment
metadata error (`sandboxPolicy` missing). The browser skill's prescribed
connection was attempted first; standalone Playwright with the installed Edge
browser was then used successfully. Screenshots of the desktop/mobile problem
comparison, mobile step inspector and integral repair were visually inspected.
Generated PNGs are under `frontend/test-results/`; these artifacts are ignored
by Git and can be regenerated with `npm.cmd run test:browser`.

The following remain outside this phase:

- Final content review, 20-template expansion and Mode C samples remain in
  later phases; both template review fields remain draft.
- Only declared values can be edited. There is no free-form algebra editor,
  proof assistant, saved exploration or challenge grading.
- Browser validation covers Windows Edge at two viewport sizes. It does not
  establish coverage on physical phones, other browsers or Termux.
- The application chunk is about 546 kB minified / 167 kB gzip, including KaTeX;
  the build succeeds with Vite's size advisory. No speculative loading framework
  was added for the current two examples.
- Isolation retains the documented Phase 2 limitations: bounded time/concurrency
  and JSON results, without a hard OS memory quota. Browser aborts do not cancel
  an active worker.
