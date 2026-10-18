# One-Twist

Change one condition. Break one assumption. Discover why.

One-Twist explores the conditions behind mathematical methods. This repository
implements **Phase 1: Foundation**, **Phase 2: Mathematical Engine** and
**Phase 3: Interactive Explorer** and **Phase 4: Challenge Modes** from
[PRD.md](PRD.md), plus the first ten reviewed templates of Phase 5. It contains
eleven JSON templates (ten reviewed, one awaiting its scheduled review), an isolated FastAPI mathematical
engine, a restricted mathematical constructor and a Vite/React/TypeScript
interface with KaTeX. Three explorer pages call the real engine; Challenge
Interface supports Find the Flaw, Break the Method and Judge the AI.

Claude Code independently approved the five fixed derivation samples and ten
challenge configurations on 2026-10-17. They are published with named review
records. A/B grading uses isolated engine evidence; C uses the reviewed sample
rubric and explicitly identifies that source. See [Phase 4 notes](docs/phase4-report.md)
and the [historical sample review packet](docs/phase4-draft-review.md).

## Requirements and dependency versions

- Python **3.12–3.14**; Windows validation currently uses Python 3.12.
- Node.js **22.12+**; Node 24 is recommended and used for Windows validation.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the locked
  Python environment, and npm supplied with Node.

Python constraints are in `pyproject.toml`: FastAPI `>=0.115,<1`, Pydantic
`>=2.10,<3`, SymPy `==1.14.0`, Uvicorn `>=0.34,<1`, Pytest `>=8.3,<10` and
HTTPX `>=0.28,<1`. `uv.lock` pins the actual resolved dependency graph.
The frontend pins React 19.3.1, Vite 8.3.4, TypeScript ~5.9.3, KaTeX 0.19.0
and React Router 7.18.4; `frontend/package-lock.json` locks transitive versions.
Browser acceptance tests use Playwright `^1.64.1` with the installed Microsoft
Edge browser; the lockfile records the exact version.

## Windows: install and run

Run these PowerShell commands from the repository root:

```powershell
uv sync --frozen
uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second PowerShell window, from the repository root:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open <http://127.0.0.1:5173>. The five navigation destinations are Home,
Problem Explorer, Method Inspector, Boundary Explorer and Challenge Interface.
Problem Explorer, Method Inspector and Boundary Explorer are independent pages
sharing one exploration session. Challenge Interface has its own practice session.

Choose an example, then select a declared condition change and value. Click
**Analyze change** to run it. Problem Explorer compares the problems; Method
Inspector switches between original and changed derivations and explains each
step; Boundary Explorer traces the condition through premises, steps, repair
suggestions and outcomes. Changing a draft clears its old result. Navigation
keeps the session; reloading the page resets it.

Domain changes use named, template-declared choices. The updated domain appears
in the condition comparison and is enforced by the same isolated computation.
The log-product example also shows an invalid derivation with an unchanged,
independently correct answer; method and conclusion labels remain separate.

In **Challenge Interface**, choose a mode and practice item. Find the Flaw asks
for a complete step/premise/reason selection. Break the Method states its target:
invalidate the original derivation or change the conclusion. Judge the AI asks
about derivation soundness and conclusion correctness independently; sound
samples require no invented flaw. Click **Check answer** to submit. Feedback is
Correct, Incorrect or Indeterminate, with supporting evidence and possible
repairs. Unknown verification and request errors are distinct from Incorrect.
The optional explanation is echoed only; it is not saved or semantically graded.

Use `npm.cmd` in PowerShell to avoid execution-policy restrictions on `npm.ps1`.
The Vite dev proxy forwards `/api` to port 8000; no cross-origin setup is needed.
Open <http://127.0.0.1:8000/docs> for API documentation. Both services bind to
loopback by default.

## Validation

From the repository root:

```powershell
uv run --frozen pytest -q
```

From `frontend`:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Backend tests cover model invariants, template IDs and references, supported
grammar, invalid Python syntax, complexity limits, attempted input execution,
public-response filtering, isolated analysis and explicit Unknown/HTTP error
responses. Frontend tests cover KaTeX HTML/MathML rendering, independent page
routes, API-driven analysis, multi-label reports, remedies, unresolved results,
request errors and stale-response rejection after edits or example switches.
Independent SymPy tests check approved template values and private mathematical
drafts, including exact root sets, domain boundaries and one-sided limits. These are content
checks in addition to the finite runtime verification engine.
Isolation tests additionally exercise actual Windows spawn workers, deadline
termination, Pipe size boundaries, capacity rejection and application shutdown.
Build output goes to `frontend/dist/`. `npm run preview` alone does not provide
the backend proxy; use `npm run dev` for the complete local workflow.

With both development servers running, execute these from `frontend`:

```powershell
npm.cmd run test:integration
npm.cmd run test:browser
```

The first runs the actual React interface in jsdom, using native HTTP fetch
through the Vite proxy to real FastAPI/spawn computations. The second uses
headless installed Edge, testing 1440px desktop and 390px mobile viewports,
navigation, condition changes, formula rendering and layout overflow. Screenshots
are written under `frontend/test-results/` (ignored by Git). These checks require
free ports 5173/8000 and the two servers described above. The browser configuration
targets local Windows Edge; it does not download a browser during `npm ci`.

Unit-test contract fixtures are exported through actual API/spawn calls and are
never imported by application code. To refresh them after a response change:

```powershell
uv run --frozen python -m scripts.export_explorer_fixtures
uv run --frozen python -m scripts.export_challenge_fixtures
```

## API scope

| Endpoint | Current behavior |
| --- | --- |
| `GET /api/templates` | Real summaries of both JSON templates |
| `GET /api/templates/{id}` | Public problem and declared condition changes; 404 for missing IDs |
| `POST /api/perturbations` | Validate one declared change and recompute an analysis in a disposable child |
| `POST /api/analyze` | Analyze the baseline or a single declared change using the same computation path |
| `GET /api/challenges` | Reviewed challenge summaries only |
| `GET /api/challenges/{id}` | Public statement, proposed steps and offered choices; no keys or private annotations |
| `POST /api/challenges/check` | Mode-specific structured grading; Correct / Incorrect / Indeterminate and evidence |

The public template DTO deliberately omits correct solution steps, conclusions,
assumptions, expected failure mechanisms, verification rules and explanations.
The explorer's analysis response includes replayed steps and method metadata;
challenge GET responses withhold answer keys. The JSON files are bundled
source content, so this is response filtering, not DRM or a secure exam system.

`POST /api/analyze` accepts this baseline request:

```json
{"template_id": "linear-degeneration"}
```

To change one condition, use `POST /api/perturbations` with:

```json
{
  "template_id": "linear-degeneration",
  "rule_id": "change-a",
  "condition_id": "parameter-a",
  "type": "parameter_value",
  "new_value": {"source": "2", "latex": "2"}
}
```

The same object may be supplied as `perturbation` beside `template_id` in an
analysis request. Values must match a declared `source` string exactly; the
server uses its own canonical LaTeX and never accepts a client verdict, proof,
computational spec or deadline. Equivalent unlisted strings such as `2.0` are
not accepted in this finite content model.

Responses contain the original problem, reconstructed problem, recomputed
steps, method names/descriptions, independent step/method/conclusion dimensions, assumption evidence,
original/new conclusion outcomes, comparison and deterministic explanations.
Generated formulas may omit `source`; their LaTeX comes from SymPy output.
`execution` records worker status, PID, exit code and elapsed time. A timed out,
failed or oversized computation returns HTTP 200 with mathematical **Unknown**
and a specific reason. Capacity, shutdown or uncertain cleanup returns **503**;
invalid changes return **422**, and absent templates return **404**.

`conclusion.labels` describes the independently established new outcome.
For `a=2`, the method is Valid and the conclusion has both Valid and Changed
Conclusion. An empty solution set or a divergent integral is an established
outcome, distinct from an undefined expression or an unknown calculation.
`comparison.changed = null` means the comparison is unresolved. Partial and
conditional solution sets never establish an unchanged conclusion.

## Models and content

- `app/models/domain.py`: independent step/method/conclusion results, evidence,
  retained domain restrictions, assumption states and conclusion comparisons.
  A null verification or well-formedness means unassessed. A null comparison
  `changed` means unknown, not unchanged.
- Display labels are sets. A single step cannot be both Valid and Invalid Step.
  Unknown needs a reason; Inconvenient needs author-reviewed evidence.
- `Problem.well_formedness` follows the agreed Phase 1 enum. Its NoSolution and
  Divergent values classify the problem's outcome; they do not imply the problem
  statement is syntactically malformed. One field is not a full mathematical
  ontology and may need refinement for future templates with combined cases.
- `app/templates/loader.py`: startup schema, unique ID, reference, step-order and
  supported expression checks. No template contains executable validation code.
- `Problem.computation` contains a finite equation, definite-integral, closed-scalar,
  point-derivative, stationary-point or finite-point-limit spec;
  step rules contain typed parameters for equation transformation, affine
  substitution, antiderivative checking, scalar identity/evaluation, candidate
  solving, candidate acceptance, principal-sine coverage and the reviewed
  calculus operations. There is no
  natural-language, LaTeX or general proof-rule interpreter.
- `app/engine/`: canonical perturbation construction, ordinary function
  registries for assumption/step checks, real-domain and solution-set checks,
  classification and deterministic explanations. An explanation fragment
  matches explicit `(rule_id, outcome)` combinations. Authored
  `expected_failure_mechanisms` is excluded from worker content and used only
  in content regression expectations.
- The linear example starts at `a = 1` in `ax = 1`; the zero case must be checked
  in the original equation. The integration example starts at `b = 1/2` in
  the integral of `1/(1-x)` from zero to `b`. At `b = 1`, an improper-integral
  limit is required; substitution can be repaired and the integral diverges.
- The first five reviewed templates cover linear degeneration, cancellation after a
  domain expansion, squaring with a candidate-sign constraint, inverse-square
  branches and real-logarithm definedness. `linear-degeneration` was formally
  re-reviewed with this batch. `integral-endpoint` remains draft until its
  planned batch 11-15 re-review. Detailed records accompany each template.
- The second reviewed batch adds missing sine branches, cosine quadrant signs,
  a cusp derivative, stationary-point classification and L'Hopital's limiting
  form. Point derivatives use original one-sided difference quotients; a known
  missing derivative is separate from the function's well-formedness. Stationary
  classifications are typed outcomes; conclusion changes do not compare LaTeX.

## Restricted mathematical syntax

`parse_math(source, symbols={...})` validates an AST and constructs SymPy objects
node by node. It never evaluates the input as Python. Allowed syntax:

- Integer and decimal literals, declared ASCII symbol names, `pi`, `E`, `I`.
- `+`, `-`, `*`, `/`, parentheses and literal integer powers `**`.
- Unary `sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `abs`.

Limits: 1,024 input characters, 24 parenthesis/tree levels, 128 AST nodes,
32 digits per numeric literal, absolute exponent at most 16, at most 32 declared
symbols. Decimals use exact rational values. Scientific notation, implicit
multiplication, arbitrary calls, attributes, indexing, Python containers,
comments, keyword arguments and symbolic exponents are rejected.

All checks precede symbolic construction. Construction suppresses evaluation,
so `x/x` retains its denominator. The worker can also supply trusted Symbol
objects with real/integer assumptions without rebuilding the parsed tree.
This parser does **not** prove definedness,
equivalence, convergence or the cost of later symbolic operations. Explicit
model domain restrictions survive engine transformations. Equation comparisons
also preserve the original expression's denominator exclusions; a new output
restriction cannot retroactively discard an input solution.

`MathExpression.source = null` explicitly denotes display-only notation outside
the Phase 1 grammar, including integral and equation notation. KaTeX renders
`latex`; the loader does not assert equivalence between authored LaTeX and
optional arithmetic source. This remains a content-review responsibility.

## Known limitations and next phases

- **Phase 2 uses disposable computation workers.**
  An application-owned `ComputationExecutor` uses disposable spawn children,
  a single-use JSON Pipe, a 3-second deadline (including startup), at most two
  concurrent jobs and terminate/join/kill cleanup. Only internal `ping` and
  template `analyze` operations exist; there is no public probe route or
  arbitrary operation endpoint. Fault injection lives in
  tests. See [ADR 001](docs/adr/001-symbolic-computation-isolation.md).
- The 64 KiB message limit and concurrency/deadline controls do not provide a
  hard RAM quota or an OS security sandbox. Windows Pipe transfer uses a small
  CPython spawn adapter to avoid stranding a writer handle when a child is
  killed before unpickling. It is tested on CPython 3.12.10; the internal API
  compatibility on Python 3.13/3.14 and Termux is not yet verified.
- Runtime support is deliberately limited to eleven real-variable/scalar
  templates and their declared parameter values or domain choices. Mutable
  domain restrictions have one condition owner; retained step restrictions are
  separate. Finite candidate predicates quantify over actual candidate roots.
  Scalar real definedness is checked on every unevaluated intermediate before
  simplification. Complex-domain equations, general case
  splits, nonlinear substitutions, interior integral singularities and
  zero-length integral conventions are unsupported and remain Unknown.
  Integrals use separately computed one-sided endpoint limits, never a Cauchy
  principal value. This is not a general proof system; authored display/spec
  correspondence and relevance of each finite rule still need content review.
- A failed premise alone does not establish an invalid step, unusable method or
  wrong conclusion. Missing facts produce Needs Checking; unsupported checks
  produce Unknown. At `b=1`, the proper-integral steps are invalid and the
  method is Needs Checking with an explicit improper-integral repair. A later
  invalid step is not advertised as the first if an earlier step is unresolved.
- Inconvenient is not inferred by the engine.
- The UI preserves every returned validity label and presents Needs Checking
  separately from Unknown. Problem outcome status is independent of validity.
  A request failure (422/404/503/network) produces a retryable request error;
  mathematical Unknown retains its report and reason. There are no automatic
  retry loops. Editing or switching examples aborts waiting and discards stale
  responses; this does not cancel a server computation or immediately free its
  capacity. First-invalid/unresolved positions come exclusively from the server.
- Challenge answers distinguish A/B/C and reject cross-mode fields and forged
  verdicts. Ten reviewed challenges and five fixed, reviewed AI derivation samples
  are available. A needs a computed first-invalid step and all required evidence;
  B uses its declared goal. C compares complete judgements to a private reviewed
  rubric; it does not run the canonical engine on an external derivation or
  claim live symbolic verification. Draft challenges are withheld. GET responses
  contain no answer keys or private annotations; post-submission feedback may
  disclose the review findings. Existing explorer analysis endpoints remain
  available; these are learning exercises, not a secure examination system.
- There are ten reviewed templates and one draft example, not the final 20
  reviewed templates. Only
  template-declared changes and values are editable; there is no free-form
  mathematical editor, exploration history or cross-reload persistence.
- No database, login, persistence, paid LLM service or remote deployment is used.
- Browser checks cover Windows Edge at two viewport sizes, not a physical mobile
  device or every browser. The in-app browser tool could not connect in this
  session; standalone Edge acceptance tests and screenshot inspection succeeded.
- Vite reports a roughly 558 kB minified application chunk including KaTeX
  (about 170 kB gzip). Builds pass; no additional loading or caching architecture
  has been introduced for this finite template set.
- The new calculus checkers are finite: sqrt(x*x+q) at zero with known q>=0;
  real quadratic/cubic stationary points; real rational finite-point limits;
  and affine numerator/denominator checks for the reviewed zero-over-zero
  L'Hopital rule. Required punctured domains are checked separately from value
  definedness at the approach point. Unsupported functions, incomplete proofs
  or missing neighborhoods return Unknown. Inconclusive second derivatives are
  never treated alone as proof of a non-extremum.

## Termux (best effort, unverified)

Install Python, Node and Git using Termux packages. If uv is unavailable, a
conventional Python virtual environment can install this project's dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade "pip>=25.1"
python -m pip install -e . --group dev
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use `npm ci` and `npm run dev` from `frontend` in a second session. The pip
fallback is constrained by `pyproject.toml` but does not consume `uv.lock`.
Pydantic-core and the Vite toolchain may require Android-compatible native
builds or additional tooling. No Termux device has been used for validation;
Windows is the supported development target.

See [Phase 2 implementation and acceptance notes](docs/phase2-report.md) for
the mathematical matrix, actual test results and API details.
See [Phase 3 implementation and verification notes](docs/phase3-report.md) for
page behavior, state boundaries and frontend acceptance results.
See [Phase 4 implementation and verification notes](docs/phase4-report.md) for
review records, challenge endpoints, grading boundaries and acceptance results.
See [Phase 5 batch 01 implementation](docs/phase5/batch-01-implementation.md)
and [batch 02 mathematical drafts](docs/phase5/batch-02-review.md) for current
progress and the next independent review gate. Phase 5 is still in progress;
Termux and Python 3.13/3.14 have not been tested.
The [batch 02 implementation report](docs/phase5/batch-02-implementation.md)
records the actual typed-calculus scope and current acceptance results.
