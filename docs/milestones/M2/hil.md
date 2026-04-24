# Milestone M2 — HIL Checkpoint

## Scope of this review

What landed:
- `packages/sdk/src/quantplatform/validation/` module with PBO, DSR, CPCV, walk-forward, and gates (ported from MVP-A archive; LESSONS.md §worth-keeping).
- Unit tests: 4 PBO + 4 DSR + 4 CPCV + 5 walk-forward + 9 gates + 5 Hypothesis property tests + 8 edge-case tests = 39 tests.
- 100% line-coverage gate on the validation module (201/201 stmts).

What did NOT land (deliberately):
- No wiring of the gate into runs / MLflow alias flips (M4).
- No UI chart of walk-forward folds (M5).
- No integration with strategy code (M3).
- Thresholds are spec defaults (pbo_max=0.7, dsr_probability_min=0.95, walk_forward_min_folds=8). Production tuning is a separate conversation.

## Prerequisites

- Repo on `main` at the M2 merge SHA
- Python 3.12+, `uv` installed
- No Docker needed for this HIL — the math is pure-function

```bash
cd packages/sdk
uv sync --all-packages
uv run pytest tests/validation/ -v
```

Automated tests all green, coverage at 100%.

## Script (target 30 min)

1. **Run the full validation test suite and read the output**
   ```bash
   cd packages/sdk
   uv run pytest tests/validation/ -v
   ```
   Expected: 39 tests PASS, coverage report shows 100% on every file under
   `quantplatform/validation/`.

2. **Walk one reference test in full**
   Open `packages/sdk/tests/validation/test_pbo.py`, read `test_pbo_returns_low_for_genuinely_uncorrelated_winner` end-to-end with me. Confirm:
   - You understand what the test is asserting.
   - The assertion matches your intuition about what "low PBO" should mean.
   - The ported source (`packages/sdk/src/quantplatform/validation/pbo.py`) behaves the way the docstring says.

3. **Read the default-thresholds block together**
   Open `packages/sdk/src/quantplatform/validation/gates.py`. The dataclass
   `GateThresholds(pbo_max=0.7, dsr_probability_min=0.95, walk_forward_min_folds=8)`
   is what gates every promotion in M4+. Discuss:
   - Is 0.7 PBO a reasonable ceiling? (López de Prado's "red zone" is >0.5; the 0.7 ceiling is generous to avoid rejecting reasonable strategies on tiny backtests. Look at the PBO values your M5 demo run produces to see where real strategies land.)
   - Is 0.95 DSR probability a reasonable floor? (Bailey's 2014 DSR paper suggests 0.95 as "one-sided 95% confidence the true Sharpe exceeds zero". Same review once we have demo data.)
   - Is 8 folds a reasonable minimum? (For weekly step + 1m test window on 10y of SPY, a typical M5 run produces ~100 folds, so 8 is safe. If you run quarterly-step strategies, 8 might be right at the edge — revisit in M5 HIL.)

4. **Run the Hypothesis property file and inspect its output**
   ```bash
   uv run pytest tests/validation/test_properties.py -v --hypothesis-seed=0
   ```
   Walk one example per invariant to make sure the random-generation isn't hiding a real bug (e.g., `assume(...)` conditions filtering too aggressively).

## Decision points (HIL judgement)

- **Are the default thresholds acceptable as spec defaults?** If yes, leave them. If no, open a spec PR now to change §6.1.1 (`Strategy.thresholds` doc) and re-record in this HIL's sign-off notes.
- **Are the tests readable enough that a quant can trust them?** The audience for these tests is not just CI — it's the quant reviewing whether the platform's gates are honest. Flag any test whose assertion is inscrutable.
- **Is the module's public surface right?** Currently: `PBOScore`, `pbo`, `DSRScore`, `deflated_sharpe`, `CPCVConfig`, `CPCVSplit`, `cpcv_splits`, `WalkForwardConfig`, `Fold`, `fold_dates`, `GateThresholds`, `GateResults`, `evaluate_gates`. Are any of these names wrong or missing for how M4 will call them?
- **Is the edge-case suite doing the right work?** `test_edge_cases.py` exists solely to hit the validation branches the archive tests didn't reach. The 100% gate forces those paths to be exercised. If any edge test feels contrived (especially `test_pbo_skips_combinations_with_all_nan_is_sharpe`, which constructs a degenerate returns matrix on purpose), flag — we can always demote the gate from 100% to e.g. 95% if the last few lines are genuine dead-defensive code.

## Sign-off

- [ ] Automated tests green (39/39 PASS; coverage 100%)
- [ ] One reference test walked end-to-end and accepted
- [ ] Default thresholds discussed and accepted (or a spec update logged)
- [ ] Public API names accepted (or rename tickets logged)
- [ ] User approves proceeding to M3 (SDK + local runs)

## Defects found

(Add below; classify each as MUST-FIX-BEFORE-M3 / DEFER-TO-V2 / SPEC-UPDATE)

## Spec / plan updates triggered

(If a threshold or public name changes, record it here and open a spec PR.)
