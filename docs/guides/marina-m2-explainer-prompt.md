# Prompt — explain M2 validation math to Marina

> Paste this into a fresh Claude Code session launched from the repo root.
> Designed to cold-start; does not depend on any prior session context.
> Audience: Marina (engineer's daughter, stats + data-science background).
> The generated output is a prose explainer — research + writing only.
> No source/tests/HIL files are modified.

---

# Explain the M2 validation math to Marina (engineer's daughter, stats + data-science background)

## Who this is for
My daughter Marina has a solid stats + data-science background. You can assume
comfort with: Sharpe ratio, null-hypothesis testing, t-statistic, p-value,
skewness, Pearson vs Fisher kurtosis conventions, k-fold cross-validation,
combinatorial bounds, hypothesis / property-based testing, Monte Carlo.
DO gloss finance-specific jargon on first use (e.g. "backtest", "strategy",
"alpha", "promotion gate", "out-of-sample", "walk-forward"). Her father is
an engineer, not a quant — so the document also doubles as a reference
he can read with her.

## What to produce
Write ONE self-contained markdown document to
`docs/guides/marina-m2-validation-math.md` (create the directory). Target
length: roughly 2000–3000 words. Use the section structure below. Prose,
not bullets-only. Include math where it clarifies, but keep it readable
(LaTeX inline, not whole derivations).

### Required sections

1. **Why model testing in finance is different.** What is a "strategy", what
   is a "backtest", why do standard ML CV techniques (k-fold, random split)
   leak information in time series, and why does the finance world's love
   of "highest Sharpe wins" tend to reward overfitting. Ground this in
   concrete scenarios (e.g., testing 1000 strategies and picking the best
   one). Establish what problem each of the four techniques below solves.

2. **Walk-forward cross-validation.** The simplest fix for temporal leakage:
   train on [t0, t1], test on [t1, t2], advance. Show the fold-dates function
   in `packages/sdk/src/quantplatform/validation/walk_forward.py`. Explain
   why `min_folds` matters, why "leave-one-out" doesn't make sense for
   time series. Reference: López de Prado's "Advances in Financial Machine
   Learning" (AFML), Wiley 2018, Ch. 11–12.

3. **CPCV (Combinatorial Purged Cross-Validation).** López de Prado's
   refinement of k-fold for time series: instead of N folds, generate
   C(N, k) combinations of test-slice choices; purge/embargo periods
   adjacent to test windows to prevent serial-correlation leakage. Show
   `cpcv.py`. Explain the embargo parameter concretely (why 5 periods,
   not 0). Reference: AFML Ch. 12.

4. **DSR (Deflated Sharpe Ratio) — Bailey & López de Prado 2014.** The
   paper people actually cite. Walk the audience through: why the sample
   Sharpe ratio is a biased and noisy estimator, how Lo (2002) derived
   Var(SR_hat) accounting for non-normality, how Bailey-LdP extended it
   to correct for multiple-testing selection bias via the expected maximum
   Sharpe term. Show `dsr.py`. Show Equation 7 from the paper. Call out
   the kurtosis convention explicitly (the coefficient is `(γ̂_4 − 1)/4`,
   where γ̂_4 is Pearson kurtosis — normal = 3, NOT Fisher excess where
   normal = 0). This leads naturally into section 7.

5. **PBO (Probability of Backtest Overfitting) — Bailey/Borwein/LdP/Zhu
   2014.** The "Combinatorially Symmetric Cross-Validation" algorithm.
   Intuition: if you pick the in-sample winner among many strategies and
   it consistently ranks below the median out-of-sample, your selection
   process is overfit. Show `pbo.py`. Explain the logit-rank mechanic.
   Explain why PBO ≈ 0.5 for pure noise, PBO = 0 for a truly dominant
   strategy, PBO = 1 for perfectly anti-correlated IS/OS winners.

6. **Gates.** How the three numbers above combine into a single
   pass/fail decision for promotion (`gates.py`). Default thresholds:
   `pbo_max=0.7, dsr_probability_min=0.95, walk_forward_min_folds=8`.
   Discuss why those specific numbers (hint: 0.5 is the red line in the
   PBO paper; 0.95 is the standard one-sided confidence level; 8 folds
   is a minimum for statistical meaningfulness). Marina should be able
   to defend or challenge these defaults after reading this section.

7. **The bug we found and fixed (the teaching moment).** During HIL
   review, the engineer spotted that the original implementation used
   `scipy.stats.kurtosis(fisher=True)` — Fisher excess kurtosis — plugged
   into Bailey's `(γ̂_4 − 1)/4` coefficient. For normal returns that gave
   `−0.25 · SR²` instead of `+0.5 · SR²` (sign-flipped!). This had shipped
   unnoticed in a prior codebase for weeks because the existing tests
   only checked *direction* (`deflated_single > deflated_many`), never
   *value* (`does it match the published formula on known inputs?`).
   The fix is one line: `fisher=False`. The lesson: directional tests
   are not enough for scientific code. Look at commit
   `fix(M2-13): DSR uses Pearson kurtosis (not Fisher) per Bailey 2014`
   (run `git log --all --grep='M2-13'` to find its SHA) for the full
   story. Reference LESSONS.md #12: "TDD rigorous but at the wrong level."

8. **How our tests exercise each concept.** Walk through one test from
   each file in `packages/sdk/tests/validation/`:
   - `test_walk_forward.py` → specific calendar-date assertions
   - `test_cpcv.py` → `C(6,2) = 15` combinatorial value
   - `test_pbo.py` (archive) → directional; note these are the weak tests
   - `test_dsr.py` (archive) → directional, same caveat
   - `test_gates.py` → state-table / boolean logic
   - `test_properties.py` → Hypothesis property tests (monotonicity, bounds,
     no-leakage invariants)
   - `test_edge_cases.py` → validation-error branches (coverage-driven)
   - `test_reference_values.py` → the crown jewels: PBO = 0 exactly under
     total domination, PBO = 1 exactly under anti-correlation, and DSR
     probability cross-checked against scipy-reimplemented Bailey Eq. 7
     at abs_tol=1e-10.

   Explain for each: what property is being verified, and why
   directional tests alone would have missed the DSR bug.

9. **Further reading.** Annotated bibliography with URLs. At minimum:
   - Bailey & López de Prado (2014), "The Deflated Sharpe Ratio":
     https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
     (SSRN landing; PDF at https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
   - López de Prado (2014), "Deflating the Sharpe Ratio" (plainer English
     companion): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2465675
   - Bailey/Borwein/López de Prado/Zhu (2014), "The Probability of
     Backtest Overfitting": search SSRN 2326253 (fetch the exact URL)
   - Lo (2002), "The Statistics of Sharpe Ratios": Financial Analysts
     Journal — fetch a canonical URL
   - López de Prado, *Advances in Financial Machine Learning*, Wiley
     2018 (book; Chapters 11 "The Dangers of Backtesting" and 12 "Cross-
     Validation in Finance" are the relevant ones)
   - Mertens (2002) on Sharpe ratio variance — find and link
   - Wikipedia DSR summary: https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio

   Include a one- or two-sentence description of what each link adds
   over the others.

## What to do, in order

1. **Read the code.** Open `packages/sdk/src/quantplatform/validation/`
   (five files: `pbo.py`, `dsr.py`, `cpcv.py`, `walk_forward.py`,
   `gates.py`) and `packages/sdk/tests/validation/` (every file).
   Read `docs/milestones/M2/hil.md` for the decision-point framing.
   Skim `docs/archive/LESSONS.md` for the "TDD at the wrong level" context.

2. **Fetch the papers** via WebFetch. Prioritize in order:
   a. The davidhbailey.com DSR PDF (primary source for Eq. 7).
   b. The Wikipedia DSR article (good sanity check on notation).
   c. The PBO paper on SSRN (search for "probability of backtest overfitting Bailey").
   d. Lo (2002) on Sharpe variance — find a stable URL.
   e. Any mlfinlab / hudson-thames reference implementation you can
      reach — useful for cross-checking the PBO construction if you
      want to be extra sure.

   If any PDF fetch fails due to binary encoding, fall back to the
   paper's abstract on SSRN plus Wikipedia / secondary sources. Flag
   any quantitative claim you can't ground in a primary source.

3. **Verify the kurtosis-convention claim in section 4/7.** The fix
   commit message asserts Lo (2002) gives `Var(SR) ≈ (1 + SR²/2)/T` for
   normal returns, and that Bailey's coefficient `(γ̂_4 − 1)/4 = 1/2`
   only holds if γ̂_4 = 3 (Pearson). Confirm or correct this from the
   primary sources before writing section 7. If you find the claim
   wrong, flag it loudly — this affects real code.

4. **Write the document.** Prose for Marina; an engineer can follow a
   data-scientist's explanation. Include code snippets (short) where
   they illuminate; link to full files rather than pasting them.

5. **Do NOT modify any source code, tests, or the HIL doc.** This is a
   research + writing task only. Commit the guide as:
   `docs(guide): M2 validation math explained for stats+DS audience`
   (with the standard `Co-Authored-By: Claude <...>` trailer if your
   session's convention includes one).

## Success criteria

Marina reads it in 30–45 minutes and can:
- Name each of the four techniques and what they correct for.
- Articulate why directional tests are insufficient and how the DSR
  kurtosis bug got missed.
- Open any of the referenced papers and recognize the equations the
  code implements.
- Critique the default gate thresholds (0.7 / 0.95 / 8) with a
  defensible opinion.

Her father reads it and can answer "what is the platform's promotion
gate and how do we know the math is right?" without stumbling.
