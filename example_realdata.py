"""
End-to-end example: free data -> dual xG ratings -> backtest -> simulate.
Network calls are commented with the exact usage; the script runs a synthetic
fallback so you can see the full pipeline shape without an API key.

To run for real:
  1. pip install requests   (or rely on urllib as the adapters do)
  2. Get a free key: https://www.football-data.org/client/register
  3. Uncomment the LIVE block below.
"""
from engine import DualRatingModel, PoissonMatch, League, monte_carlo, Backtester, MatchContext
from sources import FootballDataOrg, Understat, FootballDataCoUk, merge_xg

def live_pipeline(token):
    # ---- LIVE: Premier League results + Understat xG, merged ----
    results = list(FootballDataOrg(token).matches(competition="PL", season=2025))
    xg      = list(Understat().matches(league="EPL", season="2025"))
    # name reconciliation: Understat uses "Manchester United", football-data "Manchester United FC", etc.
    # Provide an alias map; here a trivial normalizer strips common suffixes.
    def alias(n):
        return (n.replace(" FC","").replace(" AFC","").replace("&","and").strip())
    merged = list(merge_xg(results, xg, alias=alias))
    merged.sort(key=lambda m: m["date"] or "")
    return merged

def synthetic_fallback():
    import random, math; random.seed(3)
    teams=[f"Club{i}" for i in range(12)]; true={t:1450+i*30 for i,t in enumerate(teams)}
    def kn(l):
        L=math.exp(-l);k=0;p=1.0
        while True:
            k+=1;p*=random.random()
            if p<=L:return k-1
    feed=[]
    for _ in range(2):
        for h in teams:
            for a in teams:
                if h==a: continue
                sup=(true[h]+55-true[a])/130; xh=max(.15,1.375+sup/2); xa=max(.15,1.375-sup/2)
                feed.append({"home":h,"away":a,"hg":kn(xh*random.uniform(.6,1.5)),
                    "ag":kn(xa*random.uniform(.6,1.5)),
                    "xg_h":round(xh,2),"xg_a":round(xa,2),
                    "neutral":False,"importance":1.0,"date":"2025-01-01"})
    return teams, feed

if __name__ == "__main__":
    TOKEN = None   # put your football-data.org key here to go live
    if TOKEN:
        feed = live_pipeline(TOKEN)
        teams = sorted({m["home"] for m in feed} | {m["away"] for m in feed})
        print(f"Loaded {len(feed)} real matches with xG where available.")
    else:
        teams, feed = synthetic_fallback()
        print(f"No API key set — running synthetic demo ({len(feed)} matches).")

    # 1) Train + validate the dual xG model
    model = DualRatingModel(base=1500, k=24, k_xg=22, home_adv=55, blend=0.65)
    report = Backtester(model).run(feed)
    print(f"\nBacktest: {report['matches']} matches | "
          f"Brier {report['brier']:.4f} | LogLoss {report['logloss']:.4f}")

    # 2) Current model ratings (results+xG blended)
    print("\nTop teams by blended rating:")
    for t in sorted(teams, key=lambda t:-model.rating(t))[:6]:
        print(f"  {t:14s} {model.rating(t):7.1f}  "
              f"(results {model.results.rating(t):.0f} / xG {model.xg.rating(t):.0f})")

    # 3) Forecast the rest of a season via Monte Carlo
    fixtures=[(h,a) for h in teams for a in teams if h!=a]
    lg=League(teams,fixtures); pm=PoissonMatch(model)
    odds=monte_carlo(lambda: lg.simulate(pm)[0][0], n=4000)
    print("\nTitle odds (next simulated season):")
    for t,p in list(odds.items())[:6]:
        print(f"  {t:14s} {p*100:4.1f}%")
