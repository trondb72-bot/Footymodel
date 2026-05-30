# footymodel — a reusable football prediction engine

A clean, format-agnostic engine for forecasting football. Works for leagues,
knockout cups, and group+knockout tournaments (World Cup, Champions League).
Built as the generalization of the World Cup 2026 model.

## The five layers

| Layer | File / class | Job |
|-------|-------------|-----|
| 2. Ratings | `EloModel` | Strength per team; self-updates after every match (margin-of-victory aware). |
| 3. Match model | `PoissonMatch` | Two ratings + context → scoreline grid, 1X2 probabilities, or a sampled result. |
| 4. Simulator | `League`, `Knockout`, `monte_carlo` | Runs a competition format thousands of times for true probabilities. |
| 5. Validation | `Backtester` | Replays history, predicts before seeing results, scores with Brier / log-loss / calibration. |

(Layer 1, data ingestion, is intentionally left to you — see below.)

## Quick start
```python
from engine import EloModel, PoissonMatch, League, monte_carlo

elo = EloModel(base=1500, k=24, home_adv=55)
# ...feed historical results via elo.update(home, away, hg, ag)...

pm = PoissonMatch(elo)
pm.outcome_probs("Arsenal", "Chelsea")      # -> (home_win, draw, away_win)
pm.scoreline_probs("Arsenal", "Chelsea")    # -> full grid

lg = League(teams, fixtures)
monte_carlo(lambda: lg.simulate(pm)[0][0], n=10000)   # title odds
```

## Context features already wired in (`MatchContext`)
- Home advantage (per-competition tunable)
- Rest days / fixture congestion
- Heat stress + per-team acclimatization (the weather layer)
- Altitude edge
Extend `PoissonMatch._adjusted()` to add more (travel, motivation, key-player-out).

## Adding real data (Layer 1) — `sources.py`, free sources included
Adapters that emit the engine's match dict are in `sources.py`. All free, verified May 2026:

| Source | What you get | Key? | Notes |
|--------|-------------|------|-------|
| **football-data.org** | fixtures, results, standings — 12 major leagues + CL/WC | free key | 10 req/min; clean REST; throttled adapter included |
| **Understat** | **xG** (EPL, La Liga, Serie A, Bundesliga, Ligue 1, RFPL) | none | **Best surviving free xG** — feeds the dual model |
| **football-data.co.uk** | huge CSV archive of historical results (+ shots, odds) | none | best for **backtesting**; decades of data |
| **OpenLigaDB** | results, no key | none | mainly German football |

**⚠️ Important (Jan 2026): FBref lost its Opta xG data** after Stats Perform became
FIFA's exclusive betting-data distributor. FBref is no longer an xG source. **Understat
is now the best free xG option.** FotMob also has xG but via undocumented, fragile endpoints.

Combine a results feed with Understat xG using `merge_xg()` (needs a team-name alias map
since sources name clubs differently). See `example_realdata.py` for the full pipeline:
data → dual model → backtest → Monte Carlo title odds. It runs a synthetic fallback with
no key so you can see the shape immediately.

**Be a good citizen & check licensing:** cache responses, respect rate limits, and note
that free-to-view ≠ free-to-redistribute. Several sources restrict betting/commercial use.

## The xG upgrade (BUILT IN — `DualRatingModel`)
Maintains two Elos — one updated from actual results, one from xG — and blends them:
`rating = (1-blend)*results_elo + blend*xg_elo`. The xG Elo updates on *xG share*
(a continuous 0-1 score), so a team that dominates chances but loses on poor finishing
still gains rating. xG reacts faster and is less fooled by variance.

```python
from engine import DualRatingModel, Backtester
m = DualRatingModel(base=1500, k=24, k_xg=22, home_adv=55, blend=0.65)
Backtester(m).run(history)   # history dicts include xg_h, xg_a (falls back to goals if absent)
```
It exposes the same interface as `EloModel`, so it drops straight into `PoissonMatch`.
**Tune `blend` on your own data** via backtesting — real-world optimum is usually
~0.6-0.7 (teams have some genuine finishing skill, so pure xG overcorrects).
See `demo_xg.py` for a head-to-head showing the blend beats results-only out of sample.

## Honest limits (read this)
- A well-calibrated model is good for **forecasting and analysis**, not for beating
  betting markets. Bookmaker prices already embed sharper models + a margin (vig).
  To profit you must beat the *price*, consistently, after the margin — most don't.
- Always judge a model by **out-of-sample** Brier/log-loss and calibration, never by
  how confident or plausible its outputs look.
- Garbage in, garbage out: the engine is only as good as the data feeding it.
