# Batch 01 radical comparison: root cause and repair

2026-10-18. Claude Code reproduced the published radical template's missing
Changed Conclusion label during full regression. Batch 02 implementation was
paused to resolve it. This note supersedes the original delivery's unresolved
diagnostic observation; the reviewer was right that successful reruns alone
did not resolve the defect.

## What failed

For the baseline sqrt(x)=x (c=0), original_outcome was **unknown**, not an
incorrect complete root set. The perturbed c=-1/4 result was the correct
complete set {1/4}. As designed, comparison.changed was null because the
baseline was unestablished; the conclusion displayed Valid without Changed
Conclusion. Neither finite-set comparison nor label merging caused the loss.

The baseline failure reason was SymPy InconsistentAssumptions: the same
knowledge base held integer=true, odd=false, even=false, zero=false and then
attempted to deduce even=true. It occurred in a successful worker, not at a
deadline or capacity boundary.

The captured original exception stack reaches:

```
evaluate_problem -> solve_equation -> context.expr(spec.right)
  -> simplify(raw_expression) -> expr.is_zero
  -> SymPy assumptions._ask -> Add's hermitian query
  -> facts.deduce_all_facts -> InconsistentAssumptions
```

The restricted parser/parameter substitution deliberately retains syntax.
Thus x-c at c=0 becomes Add(x, Mul(-1, 0, evaluate=False), evaluate=False),
rather than canonical x. SymPy's arithmetic assumption handlers assume
canonical forms; for example the locked version's Mul._eval_is_even returns
false for this noncanonical zero product while its zero handler returns true.
Randomized prerequisite-query order can expose the inconsistency. SymPy's
assumption RNG is independent of Python's hash seed; changing only
PYTHONHASHSEED did not control it. Fresh workers do not eliminate this defect,
and a passing focused run does not establish absence in a full run.

## Deterministic evidence

`tests/isolation_workers.py::order_assumption_facts` replaces only the test
query ordering: prioritize zero, even, odd, integer, hermitian, then sort the
remaining facts alphabetically. It does not fabricate a truth value, solve
result or verdict. This produces a stable failure independently of the random
seed. The actual mathematical operations remain SymPy operations.

Before changing production code, running
`uv run --frozen pytest tests/test_canonical_arithmetic.py -q --tb=short`
gave **6 failed, 1 passed (4.27s)**. The baseline, c=-1/4 and c=6 analyses all
lost their baseline evaluation. All three actual Windows spawn/API cases also
failed with execution=success and original_outcome=unknown. The seventh test
characterized the upstream raw-tree failure directly. This is a red/green
reproducer, not additional probabilistic observation.

## Repair

`Context.expr` now computes simplify(raw(expression).doit()). The bounded
parser's arithmetic/function nodes are evaluated bottom-up in a computation
copy before generic simplification can query their assumptions. Parameter
construction uses the same evaluate-before-simplify order on its parsed copy.
This is two changed computation lines plus an explanatory comment; there is
no retry, RNG seeding in production, exception swallowing, hardcoded answer,
forced changed flag or broader rule engine.

`Context.raw`, the restricted parser, domain extraction and scalar intermediate
definedness remain unchanged. They retain the source structure needed to
recognize excluded denominators and invalid real intermediates. Tests verify
that computing x/x=1 and x*x/x=x still excludes zero; log(x)-log(x)=0 retains
x>0; sqrt(x)*sqrt(x)=x retains x>=0; and normalizing the computation does not
mutate the retained tree. Existing complex-intermediate and 0**0 tests remain
in the full suite.

The controlled worker exists only in tests; it delegates to the actual
production _worker_main/analyze operation. The production operation registry,
default three-second deadline, spawn context, concurrency and JSON caps have
not changed.

The repaired direct and real-spawn cases establish these actual complete sets:

| Scenario | Original set | Perturbed set | changed |
| --- | --- | --- | --- |
| c=0 baseline | {0,1} | {0,1} | false |
| c=-1/4 control | {0,1} | {1/4} | true |
| c=6 extraneous candidate | {0,1} | {9} | true |

## Validation

The initial repaired scoped run of the seven new tests plus all 61 batch-01
runtime tests passed **68 tests (31.51s)**. After adding seven preservation/zero
parameter cases, the deterministic regression file passed **14 tests (3.71s)**.
The final `uv run --frozen pytest -q --tb=short` run passed **440 tests in
64.69s**, including all original eight fixed-hash fresh-worker comparisons and
the fourteen deterministic regression cases. The only warning is the existing
Starlette/HTTPX deprecation. No frontend code changed in this repair; frontend
checks were not rerun for this backend-only computation change.

The first delivery's single unexplained observation is therefore resolved by
a specific failing operation, an adverse-order reproducer that fails the old
code, and a computation-boundary repair. Batch 02's mathematical approval is
recorded; this fix does not introduce any batch-02 spec/checker or publication.

Independent acceptance: Claude Code reverted the expr() repair and reproduced
all six adverse-order direct/spawn failures, restored it and passed all fourteen
cases, then independently obtained four consecutive 440-test full-suite passes.
Batch 01, including this repair, was formally accepted before batch 02 resumed.
