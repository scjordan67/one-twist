# Phase 4: Challenge Modes

Implemented on Windows on 2026-10-17, following Claude Code's independent
mathematical and contract approval of Phase 4.1–4.2. This implementation is
submitted for independent review; it does not claim Phase 4 acceptance.
Final verification and report completed on 2026-10-18 after resuming the session.

## Content and review records

All five samples and ten challenge configurations now record `reviewed` and
reviewer `Claude Code`. The basis records the actual independent approval,
hand calculations, source/contract audit and the independently rerun 268 tests.
The two canonical templates remain draft for Phase 5 content review.

The fixed samples remain 2 correct / 1 missing_condition /
1 wrong_derivation_right_answer / 1 flawed. No mathematical content, accepted
tuple or offered choice was changed after approval. The original review packet
is preserved with a subsequent-approval note in
[phase4-draft-review.md](phase4-draft-review.md).

## Backend

| Endpoint | Behavior |
| --- | --- |
| `GET /api/challenges` | Ten reviewed summaries, no answers or category metadata |
| `GET /api/challenges/{id}` | Explicit public DTOs: stated problems, proposed steps, claimed transformation kinds, methods and offered choices |
| `POST /api/challenges/check` | Mode-discriminated answer; Correct / Incorrect / Indeterminate; evidence and optional mathematical/review feedback |

The application loads the challenge bank before creating its executor. Existing
template endpoints and analysis behavior remain available. Missing/draft items
return 404; mismatched modes, nonexistent choices, cross-mode fields, forged
verdicts and undeclared perturbations return 422. A/B computation admission uses
the same two-slot executor as explorer analysis, with immediate 503 at capacity.
Routes run in FastAPI's threadpool. GET presentation and C grading start no
workers and remain responsive while both slots are occupied.

The grader is a finite set of functions in `app/challenges/grading.py`, with no
rule language, class hierarchy, new symbolic checker or inference from authored
expected-failure text.

- **A — Find the Flaw:** recompute the fixed perturbation in a disposable worker.
  Require the backend's established first-invalid step and every computed
  evidence match for a complete accepted step/premise/reason tuple. A proven
  matching tuple earns Correct even if another acceptable tuple is unverified.
  An unmatched submission earns Incorrect only when the relevant standard is
  fully established; otherwise it remains Indeterminate. Components from
  different accepted tuples cannot be combined into an invented correct answer.
- **B — Break the Method:** recompute the submitted declared change. For
  `invalidate_original_derivation`, any established invalid step meets the
  target; all steps established Valid fail it; unresolved cases are
  Indeterminate. A known later invalid step can establish that some step fails
  without claiming it is the first. For `change_conclusion`, use only the
  independently computed comparison's true/false/null state. Premise failure,
  method repairability and conclusion correctness are distinct facts.
- **C — Judge the AI:** compare the complete structured judgement to the named,
  reviewed private rubric. No call to canonical template analysis is made.
  Separate `sample_feedback` carries reviewed proof/conclusion judgements,
  first-flaw reference, annotations and actual result. Every grading evidence
  item has `origin=author_reviewed`; `analysis` is null. Unknown rubric standards
  yield Indeterminate with null judgements and no asserted step annotations.
  Category/provenance are not grading evidence.

No worker failure or deadline produces an Incorrect grade. A/B return the
existing Unknown analysis and execution reason with Indeterminate. HTTP request
errors are not grades. Free text is echoed only, without persistence or semantic
grading. Before submission, public DTO allowlists still exclude annotations,
rubrics, actual answers, verification rules, category and review metadata;
post-submission feedback intentionally explains the findings.

## Interface

The existing `/challenges` route now supports all three modes. It has local
React state and reuses KaTeX, ProblemCard and the independent step/method/
conclusion report. No state library, new application page or dependency was
introduced. The explorer's shared session remains intact.

Mode A compares the original and changed problem and requests the full flaw
selection. Mode B displays the declared target and accepts only offered rules
and values. Mode C judges proof soundness and final conclusion independently;
sound answers need no invented flawed step. The proposed derivation explicitly
labels transformation types as claims, not verified findings. Long selected
reason/premise labels also appear as wrapping prose for narrow screens.

Only GETs load a practice item. Check answer explicitly submits the structured
choice. A synchronous task identity prevents duplicate submission; editing
clears feedback, aborts the client wait and rejects late responses. Keyed
sessions and load cleanup prevent old detail or grading responses from
contaminating a different item/mode, including fetch implementations that ignore
abort. Cancelling the wait does not claim to cancel server computation.

Feedback preserves Correct / Incorrect / Indeterminate separately from math
labels and HTTP/network errors. A/B reuse the actual mathematical report and
first-invalid/unresolved server fields. C displays human-reviewed proof and
conclusion findings with repairs and actual mathematical result, without a
fabricated computation report. Retries are explicit.

## Verification

Commands run from the repository root for Python, and `frontend` for npm.
The table records actual runs from this delivery. The full backend, component,
build and browser results were obtained before the interruption; the real HTTP
integration suite was rerun on 2026-10-18 against freshly started services and
the final application code.

| Command | Actual result |
| --- | --- |
| `uv run --frozen pytest -q` | 313 passed, 1 existing Starlette/HTTPX deprecation warning, 36.85s |
| `uv run --frozen pytest tests/test_challenge_grading.py -q` | 45 passed, 12.85s |
| `npm.cmd test` | 43 passed; 24 existing and 19 new challenge component cases |
| `npm.cmd run typecheck` | Passed; also run by build |
| `npm.cmd run build` | Passed; 557.02 kB JS / 169.36 kB gzip, existing chunk-size advisory |
| `npm.cmd run test:integration` | 5 passed on 2026-10-18, 28.59s; real React DOM → native HTTP → Vite proxy → FastAPI, A/B real spawn and C reviewed rubric |
| `npm.cmd run test:browser` | 10 passed; installed headless Edge at 1440×1000 and 390×844, 42.5s |

An earlier run overlapped backend tests, fixture export and frontend tests. It
returned Indeterminate for the regular `b=3/4` B case where the acceptance test
expected Incorrect. Resource contention was confirmed rather than a grading
defect. After stopping the development services and running verification
sequentially, the 45 grading tests and the full 313-test suite passed. The
successful-computation assertion now reports execution metadata on failure.
The production deadline and grading semantics were not relaxed to make it pass.

The backend grading tests include both A examples and both integral accepted
premises; B's eight-value/goal matrix; all five C samples and alternative
accepted reasons; wrong steps/premises/conclusions; independent proof/answer
judgements; incomplete evidence and first-invalid uncertainty; real deadline
termination; shared-capacity 503 with responsive GET/C; HTTP validation and
draft withholding. C tests forbid engine/worker calls. Category and free-text
poisoning leave grading unchanged. Content math remains independently tested
by SymPy.

Frontend tests cover explicit requests, canonical payloads, no answer prefetch,
sound C samples, wrong proof/right answer, Incorrect and Indeterminate, timeout
versus successful Unknown, 422/404/503/network errors, retry, duplicate prevention,
and stale detail/grading responses after edits, mode switches and newer attempts.
API-shaped fixtures are exported through actual handlers and spawn workers by
`python -m scripts.export_challenge_fixtures`; production code never imports them.

Browser checks cover all modes plus the four existing explorer scenarios,
mathematical typesetting, repairs and whole-page width at both viewports.
Screenshots in `frontend/test-results/` were visually inspected. The in-app
browser connection failed before execution with missing `sandboxPolicy`;
standalone Playwright/installed Edge provided the actual browser validation.
The first browser run had a test-only exact-text selector mismatch for the
labelled B goal; using the full labelled paragraph fixed it. Development
services started for these checks have been stopped.

## Limits

Only the two canonical templates, ten reviewed challenges and five fixed samples
are included. Phase 5's twenty-template library and further content coverage are
not implemented. C is reviewed fixed content, not live LLM output or a generic
external-proof verifier. There is no login, grade history, database, free-text
grading or secure-exam claim. GET filtering does not hide bundled source files
or remove the existing explorer analysis endpoints.

The unchanged three-second deadline includes Windows spawn startup; sufficiently
loaded machines can return Unknown / Indeterminate even for supported examples.
The executor still provides no hard RAM quota or OS security sandbox. Browser
coverage is two Edge viewports, not physical mobile hardware. The KaTeX-containing
bundle-size advisory and existing Starlette/HTTPX deprecation warning remain.
