---
title: Modern Quant — A Research Synthesis for Allocators and Quant Engineering Leadership
date: 2026-04-21
audience: LP allocators evaluating hedge-fund managers; quant and engineering leadership at hedge funds evaluating build-vs-buy of productionalization platforms
status: research synthesis, not a position paper; cite-by-name where claims are load-bearing
---

# Modern Quant — A Research Synthesis for Allocators and Quant Engineering Leadership

## How to read this document

This is a research synthesis. It speaks to two audiences in parallel:

- **An LP allocator** — a CIO at a pension fund, an endowment director, a family-office head of investments. Someone deciding which quantitative hedge funds deserve their next allocation, and increasingly being asked whether the manager's *technology* is a real edge or a marketing veneer.
- **The quant or engineering leadership at a hedge fund** — a CIO of a systematic shop, a head of quant research, a head of quant technology. Someone deciding what to build internally and what to buy from a productionalization platform vendor.

Both audiences face the same underlying question from different sides: *what does a credible 2026 quantitative investment process look like end-to-end, and which parts are now commoditised platform work versus genuine edge?*

The document is divided into seven parts plus an appendix. Parts 2 and 3 — cross-sectional equity alpha and time-series forecasting with foundation models — are the deep ones. Parts 4 and 5 — multi-asset/macro and execution/portfolio — are surveys. Part 6 maps the research onto a productionalization stack. Part 7 is the LP allocator's evaluation lens. The appendix is a glossary and a "what to read next" list.

A reader short on time should read Part 1, skim Parts 2 and 3 for the bolded summaries, read Part 6 in full, and read Part 7. That route takes thirty minutes.

A note on style and certainty: where a claim is empirical and load-bearing, it is sourced inline by author/repo/paper. Where I am extrapolating from first principles or from practitioner consensus, the language softens to "the practitioner consensus is..." or "the literature suggests...". Marketing claims from vendors and from any single research paper are treated with appropriate skepticism; benchmarks have known leakage problems (see §3.6 for why), and the difference between "wins on a benchmark" and "wins in production" is large.

---

# Part 1 — Setting the stage

## 1.1 What "quant" means in 2026

Quantitative investment management in 2026 is a coexistence of four modelling paradigms, not a succession:

1. **Classical statistics and econometrics.** ARIMA, ETS, Kalman filters, GARCH, cointegration, factor models in the Fama-French / Carhart / Fung-Hsieh tradition. Forty years of accumulated craft. Still the *baseline* every newer technique is measured against.
2. **Tabular machine learning.** Gradient-boosted decision trees (LightGBM, XGBoost, CatBoost), random forests, regularised linear models. The workhorse of cross-sectional alpha at most systematic equity managers between roughly 2014 and 2022, and still the workhorse for many.
3. **Deep learning.** Sequence models (LSTM, GRU, TCN), Transformers and their many time-series adaptations, graph neural networks, autoencoders. The dominant theme of 2018-2024 academic work; uneven in production deployment, with skew toward the largest and most engineering-heavy shops.
4. **Foundation models for time series and language.** Pre-trained models that generalise across series — Chronos (Amazon), Moirai (Salesforce), TimesFM (Google), TimeGPT (Nixtla), Lag-Llama (ServiceNow) on the time-series side; GPT-class LLMs and their finance-specialised derivatives on the language side. The 2024-2026 frontier.

A useful working definition for this document: **modern quant is the process of producing investment decisions by combining all four paradigms in an architecture that lets you change components without rewriting the system around them.** The tension across paradigms is not which one wins; it is which one is appropriate to which problem, and how the seams between them are managed.

The four paradigms differ in their data requirements (foundation models pretrain on enormous corpora; classical models live on a single series), their interpretability (linear regression is fully transparent; an LLM-derived signal is not), and their failure modes (a GBDT degrades gracefully; a Transformer can fall off a cliff when its input distribution shifts). A platform that pretends one paradigm subsumes the others is making a marketing claim, not an engineering one.

## 1.2 Why 2026 looks different from 2018 or 2022

Three structural shifts have happened over the past four years that an allocator or a head of quant tech needs to internalise:

**The modelling toolkit is no longer the bottleneck.** Open-source libraries (Qlib, Nixtla, Darts, scikit-learn, PyTorch, JAX, MLflow, Optuna) cover more of the modelling lifecycle, with better defaults, than was true even in 2022. The marginal model improvement from picking a smarter library has shrunk substantially. The marginal improvement from cleaner data, better point-in-time discipline, and faster research-to-production iteration has not.

**The productionalization layer is now where edge lives.** A 2018 systematic equity team's edge often came from access to alternative data nobody else had, or from a model architecture nobody else was using. In 2026, the alternative data is widely available (often through vendors who sell to multiple managers simultaneously), and the model architectures are open-sourced within months of publication. What is *not* equally distributed is the engineering substrate: whether a research idea reaches production in two weeks or six months, whether a backtest can be reproduced bit-for-bit on a date five years hence, whether walk-forward validation is enforced by tooling or by team discipline. This is where the edge has migrated.

**LLMs and agentic systems have started producing live-trading signals.** Man Group's quant arm Man Numeric publicly disclosed in 2025 that its internal AlphaGPT system — an agentic LLM tool that mines historical data, formulates rule-based trading signals, writes their code, and backtests them — had produced "several dozen investment signals approved for live trading." [Hedgeweek, 2025] Whatever one thinks of the long-term defensibility of LLM-generated alpha, it is now a documented production pattern at one of the world's largest systematic shops. An allocator who hasn't asked their managers about this is missing a question.

## 1.3 The two audiences, in one frame

The LP allocator and the head of quant tech ask two halves of the same question.

**The LP allocator asks**: *"Does this manager have a real, defensible technical edge, or are they running 2018-vintage models on AWS and calling it AI?"* The instruments for answering this are model-governance evidence, point-in-time-correctness evidence, walk-forward-validation evidence, code-parity evidence between research and production, and a credible answer to the question "what would happen if your CTO left tomorrow?"

**The head of quant tech asks**: *"For each piece of the stack — data ingestion, feature engineering, model training, validation, registry, serving, audit — should we build it ourselves, contract it to a platform vendor, or use open source?"* The instruments are an honest accounting of what the team's current stack is, what it costs to maintain, what it costs in slowed iteration, and what the build-vs-buy break-even looks like as the business scales (more strategies, more data sources, more regulatory burden, more SMA mandates).

Both audiences benefit from the same underlying analysis. Hence one document.

## 1.4 Why this document, why now

Three forces converged to make the productionalization gap the central conversation of 2026:

- **Allocators have become technically literate.** A typical 2026 ODD (operational due diligence) questionnaire from a sophisticated LP includes specific questions about model registry, experiment tracking, audit trail immutability, and whether "the same code that runs in research runs in production." Five years ago these questions were rare; in 2026 they are routine.
- **The customer-mandated separately-managed-account (SMA) structure** has pushed managers toward deployment patterns that look, from an engineering standpoint, like a multi-tenant SaaS — except each tenant is a hedge-fund mandate. A manager whose tech stack cannot stamp out a per-mandate instance with isolated data, identity, and compute cannot serve this segment economically. Industry capital-introduction surveys consistently report SMAs as one of the fastest-growing allocation vehicles for institutional investors.
- **The build-vs-buy economics have shifted decisively.** Cloud-native primitives (Cloud Run, Cloud SQL, Vertex AI, Postgres extensions, MLflow, Polars, uv) have improved enough that a small platform vendor can credibly offer an end-to-end environment that an in-house build at a single mid-sized fund cannot match without years of engineering investment. The presence of credible vendor offerings forces every fund to re-evaluate what it builds in-house.

This document addresses all three. The next two parts go deep on the modelling content the platforms must support; Part 6 maps that content to the platform; Part 7 is the LP's evaluation lens.

---

# Part 2 — Cross-sectional equity alpha (deep dive)

## 2.1 The Qlib reference frame

Microsoft's open-source Qlib platform [microsoft/qlib on GitHub] has become the de-facto reference for cross-sectional equity research outside the largest proprietary shops. Two of Qlib's choices have shaped how the field talks about itself:

- **Alpha158 and Alpha360 datasets.** Alpha158 is a tabular feature set of 158 hand-engineered technical indicators (rolling returns, volatility, volume measures, simple cross-sectional rank features). Alpha360 is the raw OHLCV history reshaped into a 360-dimensional vector per stock-day (60 days × 6 channels). Alpha158 is what tree-based models like; Alpha360 is what sequence and convolutional models like. The two datasets are not competitors so much as different test conditions: Alpha158 measures whether your model can extract signal from already-engineered features; Alpha360 measures whether it can engineer its own features from raw data.
- **The Information Coefficient (IC) as the primary metric.** IC is the cross-sectional Spearman (or Pearson) rank correlation between predicted returns and realised returns at a given date, averaged over time. Practitioner consensus, reflected in the Qlib documentation and in the academic literature, treats **IC > 0.05** as marginally interesting and **IC > 0.1** as practically significant in liquid equity universes. Information Ratio of IC over time (ICIR) is a related measure of how stable the predictive power is. A model with high mean IC but low ICIR is not a tradable model; the signal is too noisy across time.

These two anchors — the Alpha158/Alpha360 datasets and the IC family of metrics — let researchers compare apples to apples across architectures. A claim that a new architecture "beats LightGBM on Alpha158" is meaningful in a way that a claim about returns on a private universe is not.

## 2.2 The GBDT regime and why it lasted

For roughly the decade from 2013 to 2022, the dominant production tool for cross-sectional equity alpha was a gradient-boosted decision tree ensemble. LightGBM (Microsoft, 2016), XGBoost (Chen-Guestrin, 2016), CatBoost (Yandex, 2017). At many systematic equity managers it remains the dominant tool in 2026.

The reasons GBDTs held the throne for so long are:

1. **Tabular data, mostly noise, modest signal.** Equity cross-sectional features have low signal-to-noise. GBDTs are robust to noisy features, handle missing values without imputation, do not require careful normalisation, and degrade gracefully under distribution shift. They are also fast to train and easy to debug.
2. **Feature engineering does the heavy lifting.** The Alpha158 design — and the equivalent feature libraries inside every quant shop — is a hundred-plus features carefully chosen by humans. A GBDT exploits feature interactions cheaply; a neural network has to relearn what the human knew.
3. **Interpretability and risk-management hygiene.** SHAP values, feature-importance rankings, and partial-dependence plots are standard tooling around GBDTs. A risk officer can ask "what happened when this strategy drew down 80 bps last Tuesday?" and get a defensible answer. With a Transformer the same question is much harder.
4. **Production friendliness.** A LightGBM model is a few megabytes, runs in microseconds on a CPU, and serialises cleanly. There is no GPU dependency in the serving path. The total cost of operating a GBDT-based strategy is low.

The places GBDTs are weak are well known: they cannot natively model temporal dependencies (each row is independent), they cannot natively model cross-sectional dependencies between assets, and they extract no signal from raw price-volume sequences without explicit feature engineering. These weaknesses are exactly what the deep-learning generation set out to fix.

## 2.3 Sequence models — LSTM, GRU, TCN

The first wave of "go beyond GBDT" models was the recurrent-network family: LSTM (Hochreiter-Schmidhuber 1997, popularised in finance circa 2017), GRU, and the convolutional alternative TCN (Bai-Kolter-Koltun, 2018). These models accept Alpha360-style raw OHLCV input and learn temporal feature extraction end-to-end.

The picture from a decade of cross-sectional equity benchmarking, including Qlib's own [examples/benchmarks at microsoft/qlib]:

**Where they help.** When the input is genuinely raw and the human feature engineering is poor or absent, LSTMs and GRUs improve substantially over a tree on raw features. When the prediction target depends on multi-day momentum, mean-reversion patterns that span variable windows, or volatility regime context, sequence models can extract signal a tree on summary features misses.

**Where they don't.** When Alpha158-style hand-engineered features are available, the gain over a well-tuned GBDT is usually modest and often statistically indistinguishable. The cost is a substantially harder training process, a substantially heavier serving footprint, and substantially worse interpretability.

**Where they fail.** Sequence models are sensitive to distribution shift. A GBDT that worked in 2019 typically still produces a positive (smaller, but positive) IC in 2024. An LSTM trained on 2017-2019 data and deployed in 2024 can produce IC that is *negative* — actively wrong. This is one of the unspoken reasons GBDTs continue to dominate production: the failure mode is forgivable, the failure mode of the deep network is not.

## 2.4 Transformers for cross-sectional equity

The Transformer architecture (Vaswani et al., 2017) was adapted to time series starting around 2019. By 2025 there are at least a dozen finance-relevant Transformer variants in active research use, and adoption in production at the larger shops is growing. The variants worth knowing by name:

- **Vanilla Transformer** — plain self-attention over a univariate series. Often used as a baseline in finance papers; rarely competitive with the variants below.
- **Informer** (Zhou et al., 2021) — sparse attention to handle long input sequences efficiently. Important methodological contribution; less directly used in production today.
- **Autoformer** (Wu et al., 2021) — series decomposition + auto-correlation as a replacement for self-attention. Strong on long-horizon forecasting.
- **PatchTST** (Nie et al., 2023) — patches the input series (like ViT for vision) and applies channel-independent attention. Strong empirical results across many TS benchmarks; cleaner inductive bias than vanilla Transformer.
- **TimesNet** (Wu et al., 2023) — represents 1D series as 2D tensors keyed on inferred period, then applies vision-style backbones. Conceptually elegant; benchmarks well.
- **iTransformer** (Liu et al., 2024) — inverts the role of channels and tokens; treats each variate as a token and applies attention across variates. Particularly relevant to cross-sectional equity because it natively models cross-asset dependencies.
- **MASTER** (Li et al., 2024) — purpose-built for cross-sectional stock prediction; combines momentary and cross-sectional attention. Often cited in 2024-2026 benchmarks.
- **CrossFormer** — explicit cross-time and cross-dimension attention; used in equity ranking benchmarks.

The picture from comparative studies in 2025-2026 [see "Comparing Transformer Models for Stock Selection in Quantitative Trading", SpringerLink 2025; arXiv research surveys]: **iTransformer and MASTER consistently outperform vanilla Transformers on cross-sectional equity ranking, but the margin over a well-tuned LightGBM on the same features is modest in many published settings.** The honest summary is that Transformers have closed the gap with GBDTs and now slightly exceed them on raw-data regimes, but the gain is not the order-of-magnitude shift the marketing language sometimes implies.

A 2025 study from ScienceDirect specifically titled "Machine learning for stock return prediction: Transformers or simple neural networks" reaches a conclusion the field is increasingly hearing: that simple architectures with careful regularisation often match Transformer performance on equity prediction, and the Transformer's advantage is more pronounced when the input regime is genuinely high-dimensional and richly cross-sectional.

## 2.5 Wavelet and frequency-domain Transformers (a 2025-2026 trend)

A specific 2025-2026 thread worth flagging is the marriage of frequency-domain decomposition with Transformer attention. The "learnable wavelet Transformer" line of work [arXiv:2601.13435] decomposes the input series into multi-scale wavelet components and applies attention within and across scales. The intuition: equity signals operate on multiple time scales (intraday momentum, multi-day reversal, monthly factor exposure), and a representation that explicitly separates them gives the model a head start.

A related thread is *frequency-aware* models that embed FFT representations alongside the time-domain input [Nature Scientific Reports 2025 article on integrating frequency-domain and time-series features]. The empirical results in published 2025 work suggest material improvements over time-domain-only architectures on long-short equity backtests.

These are research-grade results, not yet production-standard. The practitioner's takeaway is to track the literature but not to bet a strategy on the latest paper.

## 2.6 Graph neural networks for cross-sectional alpha

The most under-exploited modelling lever in cross-sectional equity is *relational data*: the explicit graph structure between firms (industry membership, supply-chain links, ownership networks, analyst-coverage graphs). A 2024 systematic review [ACM Computing Surveys, doi 10.1145/3696411] surveyed 124 stock-prediction papers and found **only 4.2% used relational data**. The remaining 95.8% treated stocks as independent series — a strong assumption and one a graph neural network can directly relax.

Recent (2025) hybrid architectures combining temporal models with GNNs have produced consistent improvements:

- **Hybrid LSTM-GNN** [arXiv:2502.15813] — LSTM extracts temporal features per stock, GNN aggregates information across the cross-sectional graph. Reports material directional-accuracy gains over LSTM alone.
- **TFT-GNN** [Preprints 2510.2481, MDPI 2673-9909] — Temporal Fusion Transformer + GNN for stock-market prediction. Published improvements over T-GCN baseline of around 4.3% on directional accuracy in 2012-2024 benchmarks.
- **CNN-LSTM-GNN (CLGNN)** [MDPI 1099-4300] — three-component hybrid; CNN for local patterns, LSTM for temporal, GNN for cross-asset relationships.

The graph itself can be constructed several ways: from explicit industry classifications (GICS), from co-movement (Pearson or DCC correlation), from supply-chain databases, from analyst-coverage co-mentions, from ownership-network databases (institutional 13F overlap), or learned end-to-end. Different graph constructions encode different priors. The practitioner consensus is that *no single graph dominates*, and the most defensible architectures combine multiple graph views (a heterogeneous-graph approach).

For an LP allocator, the question to ask a manager is: "Do you use any graph structure between names in your model? If not, why not?" A "we tried it and it didn't help" answer is defensible. A confused look is a finding.

## 2.7 Multi-source information fusion

A 2025 ScienceDirect paper, "Transforming machine learning strategies in quantitative stock investment: A multisource information fusion and online ensemble modeling approach" (MSIF-OEM), is representative of where production-leaning research is moving in 2026:

- Parallel network architecture with multiple feature streams (price-volume, fundamentals, alternative data, sentiment).
- Each stream uses an architecture appropriate to its data type (Transformer for sequences, MLP for tabular, LLM-derived embeddings for text).
- Online ensembling that re-weights the streams based on recent performance, addressing concept drift.

This is a specific instance of a broader pattern: **the 2026 production architecture is not "one big model" but "an ensemble of specialists with an adaptive router."** The router is the place where regime detection (see Part 4) interacts with the modelling stack.

## 2.8 LLM-generated and LLM-assisted alpha

A 2025-2026 development sufficiently new that it deserves its own subsection: large language models are now generating live-trading signals at scale at named hedge funds.

- **AlphaGPT (Wang et al., 2023; further developed 2024-2025)** — an agentic LLM system that mines historical data, *formulates* rule-based trading signals (i.e., produces the signal specification, not just an executive summary), writes the code that implements them, and backtests them in a closed loop. A 2025 hybrid-method paper [Frontiers of Computer Science 11704-025-41061-5] reports an average IC of 0.0515 — a 75% improvement over the prior RL-based baseline — and cumulative excess returns more than double the prior baseline.
- **Man Numeric's AlphaGPT (Man Group, 2025)** — public disclosure (via Hedgeweek) that several dozen LLM-generated investment signals had been approved for live trading as of late 2025.
- **A wider survey** — "From Deep Learning to LLMs: A survey of AI in Quantitative Investment" [arXiv:2503.21422] is the most cited 2025 overview.

Three points an LP or a head of quant tech needs to internalise:

- **The signals are auditable.** Unlike a deep-learning prediction (black box), an LLM-generated signal is typically a rule like "long stocks where 20-day momentum > X and analyst-revision count > Y, with weight inversely proportional to volatility." The rule itself can be reviewed by a human; its derivation is the part the LLM accelerates.
- **The deployment risk is concentrated in the LLM's *idea generation*, not its *execution*.** The LLM proposes; a backtest disposes. A robust backtest harness with PBO/DSR (Part 5) is the load-bearing piece, not the LLM itself.
- **The defensibility question is open.** An LLM that generates signals can be run by anyone. The defensibility comes from the *mining infrastructure* — the data the LLM mines, the backtest harness it submits to, the experimental discipline the team imposes on what passes — not from the LLM weights. This is reassuring for the platform-builder argument and uncomfortable for managers whose pitch was "we have a unique LLM."

## 2.9 What's actually working in 2026 — a synthesis

Pulling the strands together, here is the empirical picture for cross-sectional equity alpha at the end of 2025 / start of 2026:

1. **GBDTs on hand-engineered features remain the most common production architecture** at small-to-mid systematic equity shops. They are not "old" — they are still close to the frontier when feature engineering is good.
2. **Transformer-based sequence models** (PatchTST, iTransformer, MASTER) outperform GBDTs on raw-data regimes (Alpha360-style) but the margin on hand-engineered regimes (Alpha158-style) is small.
3. **Hybrid GNN-temporal models** are a 2025-2026 frontier with material published gains; production deployment is concentrated at the larger shops with engineering depth.
4. **Frequency-domain / wavelet-augmented Transformers** are research-grade in 2026, with promising published results but limited production exposure.
5. **LLM-generated alpha** is a new and expanding production category; the defensibility argument has shifted from "do you have a unique LLM" to "do you have a unique mining-and-validation infrastructure."
6. **Multi-source / multi-stream / online-ensembling** architectures are the practitioner consensus for combining the above into a production system.

The competent 2026 quant team is not married to any one of the above. It is married to an *architecture* — research notebook → packaged feature extractor → trainable model → walk-forward validator → registry → serving — that lets it swap any of the above in or out without rewriting the surrounding system. That architecture is the subject of Parts 6 and 7.

## 2.10 Reality check: alpha half-life and capacity

A model that produces IC = 0.08 in backtest is not a model that produces 8 bps of daily return after costs at $1B AUM. The honest production picture has three further filters:

- **Capacity.** The same signal that works at $50M scales sub-linearly to $5B. A signal that buys small-cap names with thin liquidity is a small-AUM signal. The capacity calculation involves participation rates, transaction-cost models (Almgren-Chriss style; see Part 5), and impact decay assumptions.
- **Decay / half-life.** A new signal typically has its sharpest performance in its first few months and decays as it gets crowded. The literature on alpha half-life in equity markets suggests typical decays measured in months, not years. The team that found the signal first eats most of the meal.
- **Drawdown tolerance.** Live trading exposes a strategy to drawdown patterns that the backtest's smoothed metrics flatter. A strategy with backtest Sharpe 1.5 typically lives at live Sharpe 0.8-1.2 after costs and after the LP-relevant 1-2 years of out-of-sample reality.

The architecture-level implication: **the platform must make it cheap to test, deploy, and *retire* a strategy.** A platform where shipping a model takes six months is a platform that ships dead alpha.

---

# Part 3 — Time-series forecasting and foundation models (deep dive)

## 3.1 Why TS forecasting is a distinct problem from cross-sectional alpha

Cross-sectional alpha (Part 2) is *which name will outperform which other name* — a ranking problem across hundreds or thousands of assets at a single point in time. Time-series forecasting is *what will this single series do next* — a univariate or multivariate prediction problem on one (or a small number of) targets.

Both matter to a hedge fund, and they do not share the same toolkit:

- **Cross-sectional alpha** is the workhorse of long-short equity, statistical arbitrage, and quantitative factor strategies.
- **Time-series forecasting** is the workhorse of macro funds, options pricing inputs (volatility forecasting in particular), risk-system inputs (VaR, scenario inputs), demand/inventory forecasting in commodity strategies, and signal inputs to multi-asset systematic strategies.

The 2024-2026 period has seen the most disruption on the time-series side — specifically, the arrival of *foundation models* trained on enormous heterogeneous corpora of time series and capable of zero-shot or few-shot forecasting on series they have never seen. This is a categorical change in how the practitioner thinks about the toolbox.

## 3.2 The Nixtla suite as a mature ecosystem

The Nixtla project [nixtla.io, github.com/Nixtla] has become the de-facto open-source ecosystem for time-series forecasting in Python in 2026. It comprises a family of libraries with a consistent API and clear separation of concerns:

- **StatsForecast** — Numba-accelerated implementations of the classical statistical and econometric models: ARIMA, ETS (state-space exponential smoothing), Theta, TBATS, MSTL, ADIDA. Fast enough to fit thousands of series in seconds.
- **MLForecast** — gradient-boosted-tree forecasting at scale, with automatic feature generation (lags, rolling statistics, calendar features) and consistent train/predict semantics with the rest of the suite.
- **NeuralForecast** — implementations of 30+ deep-learning architectures (NHITS, NBEATS, TFT, PatchTST, TimesNet, iTransformer, DLinear, NLinear, etc.) with a common training and prediction API.
- **HierarchicalForecast** — a separate library for cross-sectional and temporal *reconciliation* of forecasts produced by any of the above (see §3.3).
- **TimeGPT** — Nixtla's own foundation model for time series, accessed as a hosted API (commercial offering).

The architectural value of the Nixtla suite is that it lets a single team move between paradigms — classical ARIMA, gradient-boosted tree, deep-learning Transformer, foundation model — without changing the surrounding scaffolding. This is exactly the kind of "swap a component without rewriting the system" pattern Part 1 argued is the modern edge.

For a productionalization platform like the one the rest of this conversation has been about, the Nixtla suite is a strong default for the time-series modelling layer. The team building forecasts no longer has to choose a paradigm at architecture time; they choose it at experiment time.

## 3.3 Hierarchical forecasting and reconciliation

A fact about forecasting that sits underneath most production systems and is rarely explained well: forecasts at different levels of aggregation are usually *not coherent* with each other. The forecast for "total energy demand" is not the sum of the forecasts for each region. The forecast for "total US equity volatility" is not derivable from the forecasts for individual sectors. Stakeholders need coherent forecasts because they make decisions at multiple levels.

The mathematics of forcing coherence — making bottom-level forecasts and top-level forecasts agree by construction — is *reconciliation*. The HierarchicalForecast library implements the standard methods:

- **BottomUp (BU)** — forecast each leaf, sum to get higher levels. Simplest. Ignores potentially-useful aggregate-level signal.
- **TopDown (TD)** — forecast the top, distribute to leaves by historical proportions. Simple, but loses leaf-level signal.
- **MiddleOut (MO)** — forecast at a chosen middle level, combine BU above and TD below. Practical compromise.
- **MinTrace** — a least-squares reconciliation that chooses a coherent forecast minimising trace of the error covariance. Statistically grounded; the de-facto modern default for many use cases.
- **ERM (empirical-risk-minimisation reconciliation)** — learns the reconciliation weights from data rather than assuming the error structure.

For finance specifically, hierarchical reconciliation matters wherever a portfolio is decomposed (sector / sub-sector / name-level forecasts), wherever a macro forecast is decomposed (country / region / global), and wherever a derivative pricing input requires consistent term-structure or surface forecasts. A 2026 production system without explicit reconciliation logic is producing forecasts that quietly contradict each other — a real but easy-to-overlook source of P&L noise.

## 3.4 Classical workhorses still relevant

The presence of foundation models has not retired classical statistical methods. In particular:

- **ARIMA / SARIMA** — still strong baselines for many financial series. Auto-ARIMA in StatsForecast removes the parameter-tuning friction.
- **ETS (state-space exponential smoothing)** — captures trend and seasonality with minimal data. Strong for short series.
- **Theta** — extremely simple, surprisingly hard to beat on short horizons.
- **GARCH and its extensions (EGARCH, GJR-GARCH)** — still the workhorse for volatility forecasting in production at most quant shops, despite many neural-network alternatives. Fast, interpretable, and well-understood.
- **Kalman filtering and state-space models** — central to multi-factor risk models, dynamic factor models for macro nowcasting, and signal extraction from noisy macro releases.

Production rule of thumb that survives in 2026: **a classical model that beats your fancy model is not a problem with the classical model; it is a problem with your fancy model.** The Nixtla suite makes running a classical baseline costless, which means there is no excuse for skipping it.

## 3.5 Deep TS architectures (non-foundation)

Sitting between classical methods and foundation models is the deep-learning architecture family for time series. The most relevant in 2026:

- **NHITS** (Challu et al., 2023) — neural hierarchical interpolation; specifically designed for long-horizon forecasting. Strong on macro and commodity series.
- **NBEATS / NBEATSx** — fully connected residual blocks with interpretable seasonality and trend components.
- **TFT (Temporal Fusion Transformer)** — Lim et al., 2021; combines LSTM with attention and produces interpretable variable importances. Widely used in finance.
- **PatchTST** — Nie et al., 2023; the Vision-Transformer-style patching approach mentioned in Part 2.
- **TimesNet** — period-aware 2D representation.
- **DLinear / NLinear** — Zeng et al., 2023; dramatically simple linear baselines that, on many TS benchmarks, beat earlier Transformer architectures. The "Are Transformers Effective for Time Series Forecasting?" paper is one of the most-cited methodological challenges of the era and forced the field to be more careful about benchmarks.

The DLinear / NLinear story is worth unpacking because it changed how the field talks about evaluation. Zeng et al. showed that earlier Transformer-for-TS papers had benchmark setups that flattered the Transformer; carefully controlled comparisons against a simple linear baseline showed the Transformer's advantage was much smaller, sometimes nonexistent. The 2023-2025 generation of TS Transformers (PatchTST, iTransformer, TimesNet) was developed in part to answer this challenge. They generally beat DLinear; the gain over a well-tuned classical baseline remains modest in many use cases.

## 3.6 Foundation models for time series — the 2024-2026 frontier

The arrival of foundation models for time series is the single most significant development in the field since the introduction of LSTM. The key 2024-2026 models:

- **TimeGPT** (Nixtla, 2024) — proprietary, accessed via API; trained on a large heterogeneous corpus; positioned for zero-shot and few-shot forecasting.
- **Chronos** (Amazon, 2024) — open-weights; built on T5-style language-model architecture; converts numeric series to discrete tokens. Two main families: **Chronos-Bolt** (faster, smaller) and **Chronos** (larger, slower, more accurate).
- **Moirai** (Salesforce, 2024) and **Moirai 2.0** (2025) — open; multivariate-aware; uses a "any-variate" attention pattern. Moirai 2.0 follows a "less is more" thesis [arXiv:2511.11698] — paradoxically smaller and more accurate than its predecessor.
- **Moirai-MoE** (Salesforce, 2025) — sparse mixture-of-experts variant; reportedly delivers up to **17% improvements over Moirai at the same model size and outperforms Chronos and TimesFM with up to 65× fewer activated parameters** [Salesforce blog, OpenReview].
- **TimesFM** (Google, 2024) — open-weights; decoder-only architecture; trained on a 100B-time-point corpus.
- **Lag-Llama** (ServiceNow, 2024) — Llama-style architecture adapted to time series; open-weights.
- **Timer-XL** (THUML, 2024) — open; competitive on academic benchmarks.

Comparative findings, drawing on 2025-2026 benchmark studies [MDPI 2813-0324/11/1/32; arXiv:2510.13654; MachineLearningMastery 2026 toolkit overview]:

- **Chronos-Bolt and Chronos-Large lead** the open-weights field on average across diverse benchmarks.
- **TimesFM is a strong all-rounder** with consistent performance across data types.
- **Moirai-MoE wins on parameter efficiency** — large gains per activated parameter.
- **No model dominates everywhere.** The best model varies by series characteristics (length, frequency, seasonality strength, noise level). A practitioner who picks one and stops is leaving performance on the table.

A critical caveat from a 2026 benchmarking-methodology review [arXiv:2510.13654] which has provoked discussion in the field: **train-test data separation across the 22 leading TSFMs is ambiguous in many cases, with one model's training set sometimes serving as another's test set.** This does not mean the benchmarks are useless, but it does mean a published "X beats Y by Z%" claim should be treated with caution — the comparison may not be apples-to-apples in the leakage sense.

## 3.7 Zero-shot vs fine-tuned for finance

The marketing pitch for foundation models is "zero-shot" — point them at a new series and they forecast without fine-tuning. The empirical reality for financial series:

**Zero-shot foundation models are often beaten by carefully fitted classical models on financial series specifically.** Financial series have features (heavy tails, volatility clustering, regime shifts, microstructure noise) that are under-represented in the heterogeneous TSFM training corpora. A practitioner using TSFMs in finance should think of them less as "the new state of the art" and more as "an additional tool whose absolute accuracy on financial series is decent but whose value lies elsewhere."

**Where TSFMs genuinely shine in finance:**

- **Cold start.** A new asset, a new strategy, a new alternative-data feed with twelve months of history. Classical methods need data the TSFM does not, because the TSFM can transfer from related series.
- **Cross-firm transfer.** Forecasting a ratio for a small-cap stock with sparse fundamental history, where the TSFM has seen thousands of similar small caps in training.
- **Probabilistic forecasting.** Many TSFMs natively produce calibrated quantile forecasts; this is what risk systems and option-pricing inputs actually want.
- **Multi-series scaling.** Forecasting ten thousand series in parallel without per-series model maintenance.

**Where they don't:**

- Single highly-instrumented liquid series (S&P 500 daily returns, US 10y yield) where decades of data and decades of econometric craft beat them.
- Volatility forecasting on liquid equities, where GARCH-family models with appropriate refinements remain competitive or superior.
- Ultra-short-horizon forecasting at the microsecond/millisecond scale; TSFMs' strengths are at minute-to-day horizons.

The practitioner heuristic: **TSFM as one component of an ensemble, classical as the baseline, fine-tuned per-series classical when the data supports it.**

## 3.8 Practical guidance — when to reach for what

Compressed into a decision rule for a 2026 forecasting problem:

| Situation | First reach for |
| :--- | :--- |
| Single liquid series, decades of history, smooth dynamics | Classical (ARIMA/ETS/Theta) baseline; then GBDT with calendar/lag features |
| Volatility series | GARCH family + structural breaks; consider neural GARCH variants |
| Cross-sectional ranking across many assets | Cross-sectional models (Part 2), not univariate TSFMs |
| Many series (1k-10k+), short individual histories | TSFM + global feature engineering + selective fine-tuning |
| Cold start (new series, < 6 months of data) | TSFM zero-shot; supplement with hierarchical reconciliation if a parent series exists |
| Macro nowcasting | DFM / MIDAS / mixed-frequency state-space; ensemble with foundation model on relevant series |
| Hierarchical aggregation needed (sector → sub-sector → name) | NeuralForecast or MLForecast at leaf, HierarchicalForecast for reconciliation |
| Anything where calibrated quantiles matter | TSFM (most natively probabilistic); or classical with bootstrap; avoid point-forecast-only deep learning |

For the productionalization platform: **a generic forecasting service that lets the user choose the model class at experiment time, with the same API surface and the same audit trail, is the right architecture.** The Nixtla suite plus a TSFM client is a pragmatic concrete realisation.

---

# Part 4 — Multi-asset, factor, and macro (survey)

## 4.1 The factor zoo, its cleanup, and what survives

The "factor zoo" is the term coined by Cochrane (2011) for the proliferation of equity factors published in the academic literature — by 2014, several hundred had been claimed as significant predictors of returns. Most do not survive replication.

Two cleanups are foundational reading:

- **Hou, Mo, Xue, and Zhang (2020)** — "An Augmented q-Factor Model with Expected Growth" — argue that a parsimonious five-factor model (market, size, investment, ROE, expected growth) explains most of the cross-section that the larger zoos claim to explain. The implication: most published factors are redundant or spurious.
- **Harvey, Liu, and Zhu (2016)** and **Harvey and Liu (2020)** — "...And the Cross-Section of Expected Returns" — show that after multiple-testing corrections, the threshold t-statistic for "significance" in factor research is closer to 3.0 than the conventional 2.0, and many published factors fail this bar.

The 2026 practitioner consensus is that the small set of factors that survive are *necessary* baselines for any equity strategy. A new "alpha" that a strategy claims is not really alpha if it is mechanically explained by exposure to known factors. This is the source of the universally-applied "alpha after factor decomposition" reporting in modern fund letters.

For an LP allocator: the question is not "what's your alpha?" but "what's your alpha *after factor decomposition*, on what factor model, and how stable is it across the factor model you choose?" A manager whose alpha disappears under a different factor decomposition is selling factor exposure as alpha.

## 4.2 Regime-switching models

Financial markets are not single-regime systems. The same model that works in 2017 fails in 2020 (COVID); the same model that works in 2020 fails in 2022 (rates regime change). A modelling framework that does not explicitly account for regime structure is implicitly betting that the next regime resembles the average of the past.

The dominant tooling:

- **Hidden Markov Models (HMMs).** The classical approach: define a small number of latent regimes, fit transition probabilities and within-regime distributions, decode the regime sequence. Strong with macro variables; less powerful with high-dimensional features.
- **Markov-Switching Regression (Hamilton 1989).** Allows model parameters to switch with regime. The standard tool in academic macro work.
- **Neural regime detection.** Recent (2023-2025) work uses LSTM autoencoders, contrastive learning, and clustering on learned representations to detect regimes without specifying their number a priori. Active research; not yet a standard production tool.
- **Change-point detection (CPD) and online change-point detection.** Tools like ruptures (Python) and Bayesian online change-point detection (Adams-MacKay 2007) for detecting regime changes in real time.

The production pattern at sophisticated 2026 quant shops is not to use a regime-switching *model* per se but to use a regime-switching *router* — a fast classifier on macro and market state that selects which strategy or which model is given more weight at any time. This is consistent with the "ensemble of specialists with adaptive router" pattern from §2.7.

## 4.3 Macro nowcasting

Macro forecasting is hard because the data arrives slowly, irregularly, and at different frequencies. Quarterly GDP releases lag months. Monthly indicators arrive on different calendars. Daily and weekly indicators are often less directly tied to the macro variable of interest.

The toolkit:

- **Dynamic Factor Models (DFM).** Stock and Watson's 2002 framework remains a workhorse. Extracts a small number of latent factors from a wide panel of monthly indicators.
- **MIDAS (Mixed Data Sampling, Ghysels et al.).** Specifically designed to combine high-frequency and low-frequency data without aggregating both to the lower frequency.
- **Mixed-frequency state-space models.** Generalisation of the above.
- **Neural-network nowcasters.** Use the high-frequency stream as direct input. Compete with DFM/MIDAS on some series; less reliable across regime changes.
- **LLM-based macro nowcasting.** A 2024-2026 thread that ingests news articles, central-bank speeches, and earnings transcripts via LLM embeddings as additional macro signals. Active research with mixed published results.

For a hedge fund's macro book or for a multi-strategy fund's macro overlay, the production pattern combines all of the above: a DFM/MIDAS baseline for the main factor extraction, plus neural and LLM-derived signals as additional inputs to a meta-model that combines them.

## 4.4 Alternative data

The alternative-data category exploded between 2014 and 2020 and has matured into a normal part of the quant data budget at most large managers. Categories worth knowing:

- **Geolocation and foot-traffic.** Aggregated mobile-device location data from data brokers (e.g., SafeGraph, Advan) used to nowcast retail revenue, restaurant traffic, etc.
- **Satellite imagery.** Parking-lot car counts, oil-tank fill levels, agricultural yield estimation, factory activity. Vendors include Orbital Insight, RS Metrics, Descartes Labs.
- **Transactional / credit-card panels.** Aggregated consumer spending data (Yodlee, Earnest, Second Measure). Direct nowcast of company revenue.
- **Web-scraped pricing.** E-commerce price scraping for inflation nowcasting and competitive intelligence.
- **News and sentiment.** RavenPack, Bloomberg's NLP feeds, increasingly LLM-derived sentiment from raw news text.
- **Patents, hiring (LinkedIn-derived), shipping data, ESG.** Many vendor-specific niches.
- **App-store and digital-product data.** Sensor Tower, App Annie, etc. — directly maps to digital-economy company revenue.

The 2026 challenges with alternative data:

- **Crowding.** Many funds buy from the same vendors. The signal in any single dataset decays as more managers act on it.
- **Point-in-time integrity.** Most alternative datasets have *correction* processes — vendors restate prior periods as their methodology improves. A fund that does not maintain bi-temporal records of when it received what data is producing backtests that benefit from corrections it could not have known about. (This is why the platform-architecture chapter in the underlying blueprint argues so strongly for a `_knowable_at` column on every silver row, distinct from the business-event timestamp.)
- **Vendor dependence.** A unique vendor is a unique single point of failure.

For an LP allocator: ask the manager which alternative datasets they use and how they handle vendor restatements. A confident, specific answer about bi-temporal storage is a positive signal. A vague answer ("we have point-in-time discipline") is a yellow flag.

## 4.5 Cross-asset transfer learning

A specific 2024-2025 thread in multi-asset quant is the use of transfer learning across asset classes — pre-training a model on data-rich asset classes (US large-cap equities, US treasuries) and fine-tuning to data-sparse classes (emerging-market bonds, crypto, commodities). The intuition is the same that makes TSFMs work in §3: useful representations transfer.

Active but not yet standard production. The architectures that show the most promise are:

- Self-supervised pre-training on raw price-volume sequences, akin to BERT-for-equities.
- Multi-task training on prediction targets across assets (returns, volatility, correlation).
- Meta-learning approaches where the model learns to adapt quickly to a new asset.

For a productionalization platform, the architectural implication is the standard one: the model registry must be agnostic to asset class, and the data platform must allow joint training across asset classes. Both are easier said than done if the platform was originally designed as one-asset-at-a-time.

## 4.6 The factor-crowding problem

A specific feature of 2026 systematic equity that an allocator should understand: many funds run substantially similar models, on substantially overlapping data, with substantially overlapping factor exposures. When the factor runs, they all win together. When it reverses, they all suffer the same drawdown — and they all rebalance the same direction at the same time, amplifying the drawdown.

The "quant melt-up" of 2007 (the August 6-9 GFC-era event) is the canonical example. The flash crashes of 2010 and 2015 are related cases. The Q4 2018 momentum reversal is a more recent one. Every such event shows quant equity strategies that look uncorrelated in calm regimes are correlated in stressed ones, because they share factor exposures.

The detection tooling:

- **Factor-crowding indices** published by some prime brokers (Goldman's hedge-fund crowding, Morgan Stanley's QIS).
- **Hedge-fund 13F replication** — proxying the average hedge-fund book from public filings.
- **Internal monitoring** — tracking the strategy's loadings on each factor through time and watching whether the loadings are getting concentrated.

For an allocator: ask the manager how they monitor for crowding *in their own positioning* and what action they take when they detect it. A reduction in position size or a deliberate factor-neutralisation is a credible answer.

---

# Part 5 — Execution and portfolio construction (survey)

## 5.1 Optimal execution

The problem: given a target trade size that is large relative to typical liquidity, how do you split it across time to minimise market impact?

The classical foundation is **Almgren and Chriss (2000)** — "Optimal Execution of Portfolio Transactions." Models price impact as a sum of permanent (linear in trade size) and temporary (square-root in participation rate) components. Solves a continuous-time problem and produces an optimal trade trajectory. Practitioners refer to this framework as "AC" or "Almgren-Chriss" and it remains the production baseline at most institutional brokers and at most quant funds for their own execution.

Refinements that matter in 2026:

- **Stochastic AC** — adds volatility risk to the trader's preference. The trader balances impact against the risk of price moving away during execution.
- **Hamilton-Jacobi-Bellman (HJB) approaches** — solve the dynamic-programming problem more carefully when the trader has a more nuanced utility function.
- **Reinforcement learning for execution.** A 2018-2024 academic line of work. The framing is natural: the agent observes the state (remaining inventory, market state, time remaining) and chooses an action (slice size). DDPG, D4PG, PPO have all been tried.

The 2026 reality: **adoption of pure-RL execution at hedge funds has receded slightly.** A 2025 review surveying RL applications in finance reported that hybrid approaches (RL as a refinement on top of an AC-style baseline) grew from 15% of deployments in 2020 to 42% in 2025, while pure-RL approaches fell from 85% to 58% [Medium, "How Hedge Funds Use Reinforcement Learning for Algorithmic Trading," Nov 2025]. The reasons are pragmatic: pure-RL fails ungracefully under regime change, AC degrades gracefully, and the hybrid captures most of the RL upside without the regime-change risk.

For an LP: a manager who claims sophisticated execution should be able to explain whether they use AC, hybrid AC+RL, or something else, and why. "We outsource execution to our prime broker and use their algos" is also a defensible answer for many fund sizes.

## 5.2 Mean-variance, Black-Litterman, robust optimisation

Portfolio construction — translating a vector of expected returns and a covariance matrix into a weight vector — is a sixty-year-old problem that is still done badly more often than not.

The lineage:

- **Markowitz (1952)** — Mean-variance optimisation. The intellectual foundation. Famously sensitive to estimation error in the inputs; small changes to expected returns produce large changes to weights.
- **Black-Litterman (1991)** — Bayesian shrinkage of expected returns toward a market-implied prior, with explicit "views" the investor can layer on. Reduces estimation-error sensitivity dramatically.
- **Robust optimisation** — formulate the optimisation to be robust against worst-case parameter realisations within an uncertainty set. Loses some efficiency in the average case; gains stability.
- **Hierarchical Risk Parity (HRP)** — López de Prado (2016). Builds a hierarchical clustering of assets from the correlation matrix and allocates risk down the hierarchy. **Avoids covariance-matrix inversion entirely**, which is the source of most mean-variance instability.

The 2026 practitioner consensus:

- **HRP has become a widely-used production default** at small-to-mid quant shops, especially for portfolios where the covariance matrix is poorly conditioned (long histories, many assets, regime changes within the history).
- **Black-Litterman remains the workhorse** at larger shops with view-generation processes that benefit from explicit Bayesian incorporation.
- **Robust optimisation** is a tool to reach for when the strategy has known sensitivity to parameter shifts.
- **Pure mean-variance optimisation** is rarely used as the only step. It is typically wrapped in some combination of shrinkage, regularisation, transaction-cost adjustment, and constraint handling.

## 5.3 Transaction-cost-aware allocation

A signal that says "buy these ten names, sell those ten names" is not a strategy. A strategy is "buy these ten names, sell those ten names, in these proportions, executed over this time horizon, accounting for these transaction costs." The optimisation that produces the trade list must include the transaction costs in its objective; otherwise it produces an unimplementable solution.

The cleanest framework: Markowitz objective + AC-style impact penalty + turnover penalty + position constraints. Solved as a quadratic program (or, with non-quadratic costs, as a more general convex program).

The production pattern is to *integrate* the optimiser with the execution algorithm — the optimiser knows the AC parameters the execution algorithm will use, and the execution algorithm knows the optimiser's intended urgency. Funds that separate the two and "throw the trade list over the wall" lose efficiency; the better-engineered shops have a single optimiser-execution loop.

## 5.4 Risk targeting and dynamic leverage

A separate-from-allocation concern: how much leverage does the portfolio carry, and is that leverage stable across regimes?

The dominant pattern at 2026 systematic shops is **volatility targeting.** Estimate the realised or forecast portfolio volatility; lever up or down to maintain a target. Simple, defensible, and historically associated with smoother return paths. The downside: in fast volatility spikes (March 2020), volatility-targeting funds delever into a falling market and lock in losses.

Refinements:

- **Drawdown-aware vol targeting** — reduce target vol during drawdowns to allow recovery.
- **Regime-conditional vol targeting** — different target vols in different macro regimes.
- **Tail-risk-aware sizing** — explicit attention to CVaR or expected shortfall, not just standard deviation.

For an LP: ask the manager what their leverage policy is, whether they target volatility, and what they did in March 2020 / February 2018 / Q4 2018. The candor of the answer is informative.

## 5.5 RL for portfolio management

Beyond execution, a 2022-2025 research thread applied RL directly to portfolio construction. Recent published work:

- "Risk-Sensitive Deep Reinforcement Learning for Portfolio Optimization" [MDPI 1911-8074/18/7/347] — uses risk-aware reward formulations.
- "Smart Tangency Portfolio: Deep Reinforcement Learning for Dynamic Rebalancing" [MDPI 2227-7072/13/4/227].
- Multi-agent RL approaches [MDPI 2673-4591/120/1/11].

Production deployment is concentrated at the largest shops with the engineering depth to operate them safely. For most funds, the practitioner consensus is that a Markowitz / Black-Litterman / HRP construction with a good signal feed is more productive than an RL portfolio agent — the gain from a better allocator is small, the gain from a better signal is large.

## 5.6 Hedging and derivatives

A specific 2025-2026 application of RL that has seen genuine production traction is in **derivatives hedging**, particularly gamma and vega hedging of options books. The published approach uses **Distributional RL (D4PG with quantile regression)** to learn hedging policies that target a chosen risk percentile (CVaR, VaR) rather than the mean. This explicit distributional modelling matches what risk officers actually want — bounds on tail outcomes, not just expected outcomes.

For options-heavy strategies (volatility funds, derivative-overlay programs, dispersion strategies), the platform implication is: the modelling stack must support distributional outputs, not just point predictions. Many of the foundation TS models (§3.6) and the RL frameworks support this natively; many of the simpler regression-style frameworks do not.

---

# Part 6 — The platform map: how the research lands on a productionalization stack

## 6.1 The stack the research implies

Pulling together Parts 2-5, the 2026 quant productionalization stack must support the following capabilities, organised by layer:

**Data layer:**

- **Bi-temporal storage of every data point** — both the business-event time and the system-knowable time (the `_knowable_at` discipline from the underlying blueprint). Required by §4.4 alternative-data restatement, §2.10 walk-forward correctness, §3 TSFM cold-start cross-firm transfer.
- **Multi-frequency data ingestion** — daily, intraday, monthly, irregular. Required by §4.3 macro nowcasting (mixed-frequency models), §3 hierarchical reconciliation, §4.4 alternative data.
- **File-first ingestion patterns** — reflecting the reality that hedge-fund data integrations are file-based (vendor SFTP, GCS drops). The blueprint's four-pattern enumeration (scheduled pull / push to GCS / push via SFTP / customer-operated drop) directly serves this.
- **Quarantine and reconciliation** — a row that fails validation is not silently dropped, and a row that fails an outbound contract is not silently truncated.

**Feature / pipeline layer:**

- **Polars + Pandera as the default DataFrame stack** — for the silver-to-gold transformation pipelines. Polars' lazy execution and predicate pushdown make it materially faster than pandas at the workloads typical of feature pipelines.
- **Dagster as the asset orchestrator wrapping the Polars transformations** — every gold-layer table is a Dagster software-defined asset; the bronze-to-silver-to-gold dependency graph is what Dagster materialises and what its UI exposes as the lineage view.
- **A feature library** — Alpha158-style hand-engineered features as a starting point, with custom features added by the team. These are *callable functions*, not config files, because the research-to-serving parity story (§6.3 of the blueprint) requires that the same Python function compute a feature in research and in production.
- **Lineage from every gold-layer row to its bronze sources** — required for audit and for debugging "why did this feature have a strange value yesterday?"

**Modelling layer:**

- **Multi-paradigm support** — classical statistical (StatsForecast, statsmodels), tabular ML (LightGBM/XGBoost/CatBoost), deep learning (PyTorch + NeuralForecast wrappers), foundation models (TimeGPT API, Chronos / Moirai / TimesFM via Transformers Hub).
- **Hyperparameter search** — Optuna is the 2026 default; MLflow-integrated; supports multi-objective.
- **MLflow as the experiment-tracking and registry backbone** — cross-paradigm; open-source; full local stack.
- **Distributional model outputs supported** — required for §3.7 probabilistic forecasting, §5.6 derivatives hedging.
- **Pyfunc-style packaging** — model + preprocessing in one artefact, callable identically at training and at serving.

**Validation and governance layer:**

- **Walk-forward validation as a first-class platform operation** — gating model promotion. A model whose walk-forward performance fails the configured threshold cannot transition from staging to production, regardless of researcher preference. The blueprint already states this.
- **Probability of Backtest Overfitting (PBO) and Deflated Sharpe Ratio (DSR) computed automatically** for every backtest. López de Prado's measures should not be a researcher's choice but a platform default. This is a *gap* in the underlying blueprint — see §6.4.
- **Combinatorial Purged Cross-Validation (CPCV)** as the validation cross-validation method, not standard k-fold. Standard k-fold leaks information across folds in financial settings.
- **Audit trail with cryptographic chaining** — every model promotion, every training-data extraction, every inference, queryable by an LP / regulator / internal compliance officer.

**Serving layer:**

- **Synchronous, batch, and scheduled inference** — three modes, not one. Most strategies are batch + scheduled; some signals (intraday rebalancing) are synchronous.
- **Inference logging at the same fidelity as training logging** — the inference log is the audit evidence.
- **Model version pinning and shadow-model evaluation** — the new model serves alongside the old; production traffic feeds both; only when shadow performance matches expectations does the new model get traffic.

**Application and API layer:**

- **CQRS-style separation of writes and reads** — writes (training-run submission, model promotion, configuration changes) go through events; reads (dashboards, reports) come from purpose-built projections. Audit comes for free because the event log is the system of record.
- **Customer identity federation** — the customer's existing OIDC provider (Google Workspace, Microsoft Entra) is the authority. The platform issues short-lived session JWTs.

## 6.2 Walking the blueprint chapters with quant content overlaid

Reading the underlying platform blueprint with the quant content from Parts 2-5 in mind, the chapter-by-chapter mapping is:

- **Chapter 5 (System Architecture).** The "single image, multiple roles" pattern serves the quant workload directly. Training jobs, inference workers, and batch-processing roles all stamp from the same image. The Polars / Pandera / MLflow / Optuna stack is the right default for the research above.
- **Chapter 7 (Application Architecture).** The CQRS event log is the audit trail required by every conversation in §6.1. The worker role table covers projector workers (read-model serving), pipeline workers (data transformation), training workers, and batch inference — exactly the operational shape this content needs.
- **Chapter 8 (Data Platform).** The medallion architecture and the bi-temporal `_valid_from`/`_valid_to`/`_knowable_at` schema serves §4.4 alternative-data restatement and §3 TSFM cross-firm transfer. The four file-ingestion patterns serve the hedge-fund integration reality. Bronze, silver, and gold tables are Dagster software-defined assets; their materialisation, lineage, and asset-check validation are managed by Dagster rather than by bespoke worker scaffolding.
- **Chapter 9 (ML Platform).** Cleanly separates training and serving. MLflow is the registry. The `pyfunc` discipline is the research-to-production parity discipline. Walk-forward validation is enforced as a platform property. Aligns directly with §6.1 above. `training_run` and `model_version` are themselves Dagster assets, with asset-check validation gates (walk-forward fold count, PBO/DSR thresholds) acting as the promotion guardrails.
- **Chapter 10 (Infrastructure).** The Cloud-Run-per-role pattern with queue-depth autoscaling is the right shape for a quant workload — training runs are bursty, projectors are queue-driven, the API is request-driven.
- **Chapter 14 (Security).** The audit trail with cryptographic chaining is what an LP / regulator audit will ask for.

The blueprint as written is a strong foundation for the modelling content of Parts 2-5. **What's missing is the topic of §6.3-6.5.**

## 6.3 Gaps in the current blueprint, derived from the research

A careful reading of Parts 2-5 against the blueprint surfaces the following gaps. None are deal-breakers; all are addressable.

A note on framing: the gap analysis below was completed *before* Dagster was un-deferred from the v1 stack (Ch.15 had previously held it back). The gaps remain valid as written, but their architectural anchor is now Dagster rather than the bespoke worker scaffolding the original analysis assumed — Gap 1's backtest-as-a-service, in particular, is a Dagster software-defined asset materialised on a schedule (APScheduler triggers the run; PGMQ carries the resulting events), not a freestanding worker the platform team builds from scratch.

**Gap 1 — LLM-based signal generation infrastructure.** The blueprint stack mentions FastAPI, Pydantic, MLflow, Polars — no LLM service in the application image. Yet §2.8 documents the production deployment of LLM-generated alpha at named hedge funds. A platform that does not provide an LLM-mining-and-validation infrastructure ships its customers to build that themselves. The minimal addition: a `worker-llm-research` role that hosts an LLM (local or API-backed), with a feedback loop into the backtest harness.

**Gap 2 — Backtest infrastructure as a first-class component.** vectorbt and QSTrader are mentioned in the tech-stack table; the full backtest harness is not described in the depth that §2.9 (research-to-production), §2.10 (capacity, half-life), and §5.3 (transaction-cost-aware allocation) require. The minimal addition: a backtest service that takes (model_id, dataset_snapshot_id, transaction_cost_model_id, capacity_assumption) and returns a structured backtest report with PBO and DSR computed by default.

**Gap 3 — PBO and DSR as platform defaults.** The blueprint mentions "walk-forward validation as a first-class operation" but does not name PBO/DSR. These are the López de Prado measures from §5.0/§2.10 that the research community has converged on as the right honesty checks for backtest results. Computing them automatically on every backtest, and surfacing them in the model registry, would be a meaningful platform discipline. The minimal addition: a few hundred lines of computation in the backtest worker; a column in the registry.

**Gap 4 — A feature store, deferred but worth re-examining.** The blueprint notes Feast is deferred; the practitioner consensus in §2.7 (multi-source / multi-stream architectures) is that as the strategy count grows, a feature store becomes valuable. The current "deferred until a customer asks" framing is right; the trigger for un-deferring should be "we have three strategies sharing meaningful feature code" rather than "we feel like adding it."

**Gap 5 — Regime detection as a cross-cutting service.** §4.2 argues that regime structure should be explicit in production architectures. The blueprint does not discuss this. The minimal addition: a `regime` aggregate in the domain model, with a regime-detection worker that publishes regime-change events; subscribers (signal weighting, leverage adjustment, alerting) react.

**Gap 6 — Distributional model outputs.** §5.6 argues for distributional model outputs (CVaR, quantile predictions) as a first-class capability for derivatives-heavy use cases. The blueprint's serving model implicitly assumes point predictions. The minimal addition: extend the serving API contract to support quantile responses; the storage and audit changes are minor.

**Gap 7 — Alternative-data ingestion patterns.** §4.4 emphasises that alt-data has restatement / correction patterns that the bi-temporal schema is meant to handle, but the blueprint's data chapter focuses on traditional pull/push patterns. Specific alt-data vendor integration patterns (RavenPack-style streaming sentiment, geolocation-vendor monthly drops with correction history) deserve their own pattern documentation.

## 6.4 The opinionated stack the research actually points to

If the research above is the brief, the productionalization platform's modelling-and-validation stack should look like:

| Concern | Component | Justification (Part) |
| :--- | :--- | :--- |
| Tabular ML | LightGBM / XGBoost / CatBoost | §2.2 |
| Sequence models | PyTorch + NeuralForecast wrappers | §2.3 §3.5 |
| Cross-sectional Transformers | iTransformer, MASTER, PatchTST via PyTorch | §2.4 |
| Graph neural networks | PyTorch Geometric or DGL | §2.6 |
| Time-series classical | StatsForecast | §3.4 |
| Time-series ML | MLForecast | §3 |
| Time-series deep | NeuralForecast | §3.5 |
| Time-series foundation | Chronos (open) + TimeGPT (API) + TimesFM | §3.6 |
| Hierarchical reconciliation | HierarchicalForecast | §3.3 |
| Volatility | arch (Python GARCH library) + neural-GARCH variants | §3.4 §5.6 |
| Backtest framework | vectorbt or QSTrader; in-house wrapper for PBO/DSR | §2.10 §5.3 |
| Portfolio optimiser | cvxpy + custom HRP implementation; PyPortfolioOpt as reference | §5.2 |
| Execution | Almgren-Chriss baseline; optional RL refinement | §5.1 |
| Hyperparameter search | Optuna | §6.1 |
| Experiment tracking and registry | MLflow 2.16+ (Aliases) | §6.1 |
| Pipeline orchestration | **Dagster** (open-source, software-defined assets) | §6.1 (data layer); LP-visible asset graph and lineage |
| LLM (signal mining) | local Llama-class model + Anthropic API for the heaviest workloads | §2.8 |
| LLM (sentiment / text) | sentence-transformers; FinBERT family; LLM-embeddings | §4.3 §4.4 |
| Regime detection | hmmlearn + ruptures + custom neural detector | §4.2 |
| Quant numerics | NumPy, SciPy, QuantLib | (general) |

This stack is what the research argues for. The blueprint's current stack is consistent with most of it. The places it diverges are concentrated in the gaps listed in §6.3.

## 6.5 A note on compute

Most of the modelling content above runs on CPU. The exceptions:

- Foundation TS models for inference at scale — GPU helps but is not strictly required (Chronos-Bolt runs on CPU).
- Transformer / GNN training on Alpha360-scale data — GPU strongly preferred.
- LLM workloads (§2.8, §4.3) — GPU required for local hosting; API-served alternatives exist.

The blueprint's Cloud-Run-Jobs-for-CPU + Vertex-AI-for-GPU pattern is a clean fit for this profile. A hedge-fund customer with a serious LLM strategy may also want a dedicated GPU pool for local LLM hosting — a Phase-2 or Phase-3 platform addition rather than a Phase-1 one.

---

# Part 7 — What an LP allocator should look for

## 7.1 The premise

The premise of this section: an LP allocator in 2026 cannot rely on returns alone to evaluate a quantitative manager. Returns are noisy on the multi-year evaluation horizon LPs typically use, and the funds with the best three-year track records are not, on average, the funds with the best forward-looking edge. **Operational and technical due diligence has to do work that returns analysis cannot.**

The five questions below are the questions an LP can ask any quant manager that produce diagnostic answers. The five red flags are the patterns that should slow down (or stop) an allocation.

## 7.2 Five questions to ask any quant manager

**Question 1: "How do you guard against backtest overfitting?"**

What you want to hear: explicit mention of walk-forward validation as a discipline (not just a metric), Combinatorial Purged Cross-Validation (CPCV) as the cross-validation method, and the Probability of Backtest Overfitting (PBO) and Deflated Sharpe Ratio (DSR) as standard reporting. A manager whose answer is "we hold out a test set" is using 2010-vintage rigor and will not be reliable on the LP's 5-year horizon.

What you do not want to hear: "we only test things we believe in," "our researchers have a strict process," or any answer that places the discipline in the human rather than the platform. The literature is clear (López de Prado 2018, Bailey-López de Prado 2014) that the discipline must be enforced by tooling because human pattern-matching is too prone to backtest overfitting.

**Question 2: "What's your research-to-production parity story?"**

What you want to hear: the same Python function that computes a feature in research is the function that computes it in production; the model is packaged with its preprocessing in one artefact (MLflow `pyfunc` or equivalent); a feature change in research immediately changes the production behaviour after re-training, with no parallel re-implementation step.

What you do not want to hear: "we have a formal hand-off process between research and engineering," "the production code is a re-implementation of the research code," or any answer that implies a translation step. Translation is where the train-serve skew failure mode lives, and it is one of the two largest sources of "the model worked in backtest and stopped working in production" (the other being look-ahead bias).

**Question 3: "How do you handle alternative data and point-in-time correctness?"**

What you want to hear: explicit mention of bi-temporal storage, with both a `valid_from`/`valid_to` business-time interval *and* a separate timestamp recording when the data point became visible to the platform. Vendor restatement is recorded as a new row, not an update to an old row. Training extraction filters by the latter timestamp (system-knowable time) and never by an aggregate of business-event timestamps.

What you do not want to hear: "we make sure to use the data correctly," "our researchers know to use point-in-time," "we just use the file timestamp as the point-in-time field." Each of these answers leaves the discipline at the human layer where it cannot be reliably enforced.

**Question 4: "What's your model governance and audit trail?"**

What you want to hear: every model has a registry entry; every promotion is an event with a timestamp, an actor, and a reason; every inference is logged with model id, model version, input feature hash, output, and latency; the audit log is immutable (cryptographic chaining or append-only ledger), exportable on demand, and queryable by the manager's own compliance team without engineering involvement.

What you do not want to hear: "we have logs," "our quants keep notebooks," any answer that requires an engineer to investigate "what did model X return on date Y for input Z?"

**Question 5: "What would happen if your CTO left tomorrow?"**

What you want to hear: the platform is documented; the deployment is reproducible from version control; the operational runbooks are written and tested; the team can deploy without the CTO. The honest version of this answer often includes "it would be a hard six months" — that's defensible. The harder answer to live with is implicit single-points-of-failure across the modelling team.

What you do not want to hear: a defensive non-answer; an answer that reveals the CTO is the only person who understands the production deployment.

## 7.3 Five red flags

**Red flag 1: "We built it ourselves on AWS."** Five years ago this was a credible answer. In 2026, with Cloud Run / Cloud SQL / Vertex AI / MLflow / Polars / uv, building from raw cloud primitives is no longer a moat — it is overhead that distracts from research. A fund whose technology pitch is "we built it ourselves" without specifying *what* part is the moat is selling commodity engineering as edge.

**Red flag 2: "Our backtest Sharpe is X."** Sharpe is a single number. PBO and DSR are the modern honest reporting. A manager who reports Sharpe without reporting PBO is either ignorant of the methodology or hiding the result.

**Red flag 3: "We use foundation models for everything now."** §3.7 is clear that foundation models are one tool, with specific strengths and specific weaknesses on financial series. A manager who has migrated away from classical baselines is taking a specific bet whose downside is real.

**Red flag 4: "Our alpha is unique and proprietary; we can't share details."** Detail-sharing is not the question. Methodological discipline is. A manager who refuses to discuss their walk-forward methodology, their cross-validation protocol, or their model-promotion process — citing IP — is either uncomfortable with the answer or has not thought it through.

**Red flag 5: A small engineering team relative to the modelling team.** A 2026 quant fund running serious systematic strategies needs engineering depth. The ratio of quants to engineers at the leading shops is closer to 1:1 than to 5:1. A fund where the modelling headcount is many times the engineering headcount is a fund whose engineering will be the bottleneck on every research idea.

## 7.4 Why "we built it ourselves" is no longer a moat — and what is

The argument compressed:

- Cloud-native primitives have improved enough that a small specialised vendor can ship an end-to-end productionalization platform that an in-house build at a single mid-sized fund cannot match without years of engineering.
- The engineering bar — bi-temporal data discipline, MLflow-managed registry, walk-forward enforcement, audit chaining, blue/green Cloud Run deployment, Workload Identity Federation, the entire CI/CD pipeline — is high enough that doing it well takes a focused team's full attention, and that attention is a luxury most funds do not have.
- The economics tilt toward platform-based deployment as the SMA-driven pattern of "stamp out a per-mandate instance" becomes the standard hedge-fund product shape.
- The defensibility of a hedge fund therefore migrates **away from the engineering substrate and toward the research process and the data corpus.** A manager whose moat is "our own data" or "our own research process" is in a defensible position; a manager whose moat is "our own engineering" needs to be more specific about which engineering and why a vendor can't provide it.

For an allocator, this changes the diligence question. Instead of "do they have good engineering?" the question becomes "do they have a credible *research moat*, and is their engineering substrate a help or a hindrance to that research moat compounding?"

For a head of quant tech, it changes the build-vs-buy calculus. The default tilts toward buying the engineering substrate from a credible vendor, *if* such a vendor exists, *if* the vendor's substrate is genuinely portable (no vendor lock-in), and *if* the substrate's cost is materially less than the in-house build over the planning horizon.

The platform vendors that make this argument credible are the ones whose architecture matches the research above — silo-tenant by default (because hedge-fund mandates demand isolation), local-first development (because the research-to-production loop must be tight), Postgres-centric (because the operational data plane is auditable and transactional), and CQRS event-sourced (because audit and reproducibility require an event log). The blueprint underlying this conversation is one such platform.

---

# Appendix

## A.1 Glossary

- **AC** — Almgren-Chriss optimal execution model (2000).
- **AGE** — Apache AGE, the Postgres extension that provides Cypher graph queries.
- **Alpha158 / Alpha360** — Microsoft Qlib's two reference equity-feature datasets; tabular and raw respectively.
- **CPCV** — Combinatorial Purged Cross-Validation; López de Prado's preferred CV method for finance.
- **CQRS** — Command-Query Responsibility Segregation; an architectural pattern that separates write and read paths.
- **CVaR** — Conditional Value at Risk; expected loss conditional on being in the tail.
- **D4PG** — Distributional Distributed Distributional Deep Deterministic Policy Gradient; an RL algorithm that models the distribution of returns rather than just the mean.
- **DFM** — Dynamic Factor Model; Stock & Watson's framework for macro nowcasting.
- **DLinear / NLinear** — Zeng et al. (2023) linear baselines that exposed weaknesses in earlier TS Transformer benchmarking.
- **DSR** — Deflated Sharpe Ratio; López de Prado's correction to Sharpe accounting for multiple-testing inflation.
- **GARCH** — Generalised AutoRegressive Conditional Heteroskedasticity; the workhorse volatility model family.
- **GBDT** — Gradient-Boosted Decision Tree; the model class containing LightGBM, XGBoost, CatBoost.
- **GNN** — Graph Neural Network.
- **HJB** — Hamilton-Jacobi-Bellman; the equation governing dynamic-programming optimal control.
- **HRP** — Hierarchical Risk Parity; López de Prado's allocation method.
- **IC / ICIR** — Information Coefficient (cross-sectional rank correlation) and its ratio over time.
- **iTransformer** — Liu et al. (2024) Transformer variant that treats variates as tokens.
- **LLM** — Large Language Model.
- **MASTER** — Li et al. (2024) Transformer for cross-sectional stock prediction.
- **MIDAS** — Mixed Data Sampling; Ghysels et al.'s framework for mixed-frequency forecasting.
- **MinTrace** — minimum-trace hierarchical reconciliation.
- **NHITS** — Neural Hierarchical Interpolation; Challu et al. (2023).
- **PatchTST** — Nie et al. (2023) patching Transformer for time series.
- **PBO** — Probability of Backtest Overfitting; Bailey & López de Prado (2014).
- **PIT** — Point-in-time; the discipline of using only data that was knowable at the simulated decision time.
- **Qlib** — Microsoft's open-source quant research platform.
- **RL** — Reinforcement Learning.
- **TFT** — Temporal Fusion Transformer; Lim et al. (2021).
- **TimesFM** — Google's time-series foundation model (2024).
- **TimesNet** — Wu et al. (2023) period-aware TS architecture.
- **TSFM** — Time Series Foundation Model.
- **VaR** — Value at Risk; quantile-based risk measure.
- **WORM** — Write Once, Read Many; immutable storage pattern for audit.

## A.2 Key papers and repositories to know

**Foundational / methodological:**

- López de Prado, *Advances in Financial Machine Learning* (Wiley 2018) — the canonical 2018 reference; chapters on backtest pitfalls, CPCV, and HRP are required reading.
- Bailey & López de Prado, "The Probability of Backtest Overfitting" (Journal of Computational Finance, 2014).
- Hou, Mo, Xue & Zhang, "An Augmented q-Factor Model with Expected Growth" (Review of Finance, 2020).
- Harvey, Liu & Zhu, "...And the Cross-Section of Expected Returns" (Review of Financial Studies, 2016).
- Almgren & Chriss, "Optimal Execution of Portfolio Transactions" (Journal of Risk, 2000).

**Cross-sectional equity Transformers:**

- "Comparing Transformer Models for Stock Selection in Quantitative Trading" (Springer, 2025).
- "Machine learning for stock return prediction: Transformers or simple neural networks" (ScienceDirect, 2025).
- MASTER: Li et al. (2024).
- iTransformer: Liu et al. (2024).
- "Increase Alpha: Performance and Risk of an AI-Driven Trading Framework" (arXiv:2509.16707).

**Time-series foundation models:**

- Chronos: Ansari et al., "Chronos: Learning the Language of Time Series" (Amazon, 2024).
- Moirai 2.0: "When Less Is More for Time Series Forecasting" (arXiv:2511.11698).
- Moirai-MoE: "Empowering Time Series Foundation Models with Sparse Mixture of Experts" (Salesforce, 2025).
- TimesFM: Das et al. (Google, 2024).
- "Challenges and Requirements for Benchmarking Time Series Foundation Models" (arXiv:2510.13654).

**LLMs in quant:**

- "From Deep Learning to LLMs: A survey of AI in Quantitative Investment" (arXiv:2503.21422).
- "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading" (arXiv:2510.05533).
- "Automate Strategy Finding with LLM in Quant Investment" (EMNLP Findings 2025).
- "Large Language Model Agents for Investment Management" (ACM AI in Finance 2025).
- "A hybrid approach to formulaic alpha discovery with LLM assistance" (Frontiers of Computer Science, 2025).

**Graph neural networks for stocks:**

- "A Systematic Review on GNN-based Methods for Stock Market Forecasting" (ACM Computing Surveys, doi 10.1145/3696411).
- "A Novel Hybrid Temporal Fusion Transformer Graph Neural Network Model" (MDPI / Preprints, 2025).
- "Hybrid LSTM-GNN" (arXiv:2502.15813).

**Reinforcement learning in finance:**

- "Reinforcement Learning in Financial Decision Making: A Systematic Review" (arXiv:2512.10913).
- "Risk-Sensitive Deep Reinforcement Learning for Portfolio Optimization" (MDPI 1911-8074/18/7/347).
- "Smart Tangency Portfolio: Deep Reinforcement Learning for Dynamic Rebalancing" (MDPI 2227-7072/13/4/227).

**Open-source platforms:**

- Microsoft Qlib — github.com/microsoft/qlib
- Nixtla suite — github.com/Nixtla
- MLflow — mlflow.org
- vectorbt — github.com/polakowo/vectorbt
- QSTrader — github.com/quantstart/qstrader
- PyPortfolioOpt — github.com/robertmartin8/PyPortfolioOpt
- arch (GARCH library) — github.com/bashtage/arch
- ruptures (change-point detection) — github.com/deepcharles/ruptures

**Industry references:**

- Man Group / Man Numeric public disclosures on AlphaGPT (Hedgeweek, 2025).
- "The Rise of AI-First Hedge Funds: What Investors Should Watch in 2026" (HedgeThink).
- Salesforce Engineering blog: time-series foundation models.

## A.3 What this document deliberately does not cover

For honesty, the boundaries:

- **High-frequency trading and market-making microstructure.** These are different problems with different toolkits (Avellaneda-Stoikov, queue-position models, latency-optimised C++ infrastructure). Out of scope.
- **Crypto-specific quant.** Many of the same tools apply, but the specific data quality, custody, and regulatory considerations are different.
- **Tax-loss harvesting and tax-aware portfolio construction.** Important for a different segment (separately-managed-account wealth management); not the focus here.
- **ESG-specific quant.** A growing area; not given specific treatment here.
- **Specific implementation of any of the above.** This is a research synthesis. Code-level guidance belongs in the implementation phase that follows.

## A.4 How this document was assembled

- Synthesis from training data through January 2026 cut-off, with specific WebSearch refresh on TS foundation models, transformer-based cross-sectional alpha, RL for execution and portfolio, GNN for stocks, LLM applications in quant, and the López de Prado / hierarchical risk parity literature on 2026-04-21.
- Sources cited inline by author / paper / repo / publication where load-bearing.
- Where I could not verify a load-bearing claim, the language softens to indicate uncertainty.
- This document is research input, not a finished product position. The next phases — product feature requirements derived from this synthesis, UI direction, and the NotebookLM narrative directive — build on it.

