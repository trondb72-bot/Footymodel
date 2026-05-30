"""
footymodel — a reusable football prediction engine.
Works for any competition: leagues, knockouts, or group+knockout tournaments.
Layers: Ratings (Elo) -> Match model (Poisson) -> Competition simulator (Monte Carlo) -> Backtest/calibration.
"""
import math, random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ----------------------------------------------------------------------
# LAYER 2: RATINGS ENGINE (Elo, self-updating)
# ----------------------------------------------------------------------
class EloModel:
    def __init__(self, base=1500, k=32, home_adv=60, regress=0.0):
        self.r = defaultdict(lambda: base)
        self.k = k; self.home_adv = home_adv; self.base = base; self.regress = regress

    def rating(self, team): return self.r[team]

    def expected(self, ra, rb):  # logistic expectation for team A
        return 1.0 / (1 + 10 ** ((rb - ra) / 400))

    def update(self, home, away, hg, ag, neutral=False, importance=1.0):
        ha = 0 if neutral else self.home_adv
        ea = self.expected(self.r[home] + ha, self.r[away])
        sa = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        # margin-of-victory multiplier (FIFA-style): bigger wins move ratings more
        gd = abs(hg - ag)
        mov = math.log(max(gd, 1) + 1) * (2.2 / ((abs(self.r[home]-self.r[away]) * 0.001) + 2.2))
        delta = self.k * importance * mov * (sa - ea)
        self.r[home] += delta
        self.r[away] -= delta

    def update_soft(self, home, away, score_a, neutral=False, importance=1.0, mov=1.0):
        """Update using a continuous result in [0,1] instead of win/draw/loss.
        Used by the xG Elo: score_a is derived from xG share, so a team that
        dominated chances but lost on finishing still gains rating."""
        ha = 0 if neutral else self.home_adv
        ea = self.expected(self.r[home] + ha, self.r[away])
        delta = self.k * importance * mov * (score_a - ea)
        self.r[home] += delta
        self.r[away] -= delta

    def new_season_regress(self):
        # pull ratings partway back to mean between seasons
        for t in self.r:
            self.r[t] = self.r[t] + self.regress * (self.base - self.r[t])


class DualRatingModel:
    """Maintains two Elos — one from actual results, one from xG — and blends them.
    Exposes the same .rating()/.home_adv interface as EloModel so it drops straight
    into PoissonMatch. blend=0.0 is pure results, 1.0 is pure xG."""
    def __init__(self, base=1500, k=24, k_xg=20, home_adv=55, blend=0.5):
        self.results = EloModel(base=base, k=k, home_adv=home_adv)
        self.xg = EloModel(base=base, k=k_xg, home_adv=home_adv)
        self.blend = blend
        self.home_adv = home_adv
        self.base = base

    def rating(self, team):
        return (1 - self.blend) * self.results.rating(team) + self.blend * self.xg.rating(team)

    def update(self, home, away, hg, ag, xg_h=None, xg_a=None,
               neutral=False, importance=1.0):
        # results Elo: standard win/draw/loss with margin-of-victory
        self.results.update(home, away, hg, ag, neutral, importance)
        # xG Elo: continuous score from xG share; if xG missing, fall back to goals
        eh = xg_h if xg_h is not None else hg
        ea = xg_a if xg_a is not None else ag
        total = eh + ea
        score_a = 0.5 if total <= 0 else eh / total          # xG share in [0,1]
        movx = math.log(abs(eh - ea) + 1) + 1.0              # bigger xG gap moves more
        self.xg.update_soft(home, away, score_a, neutral, importance, mov=movx)

    def new_season_regress(self):
        self.results.new_season_regress(); self.xg.new_season_regress()


# ----------------------------------------------------------------------
# LAYER 3: MATCH MODEL (Poisson scoreline distribution)
# ----------------------------------------------------------------------
@dataclass
class MatchContext:
    neutral: bool = False
    home_rest_days: Optional[int] = None
    away_rest_days: Optional[int] = None
    heat: float = 0.0          # 0..3 stress; plug weather layer here
    home_heat_adapt: float = 0.5
    away_heat_adapt: float = 0.5
    altitude_edge: float = 0.0 # +ve favours home

class PoissonMatch:
    def __init__(self, elo: EloModel, goals_per_game=2.75, div=130.0):
        self.elo = elo; self.gpg = goals_per_game; self.div = div

    def _adjusted(self, home, away, ctx: MatchContext):
        ra, rb = self.elo.rating(home), self.elo.rating(away)
        ra += 0 if ctx.neutral else self.elo.home_adv
        # rest-day edge
        if ctx.home_rest_days is not None and ctx.away_rest_days is not None:
            ra += 4 * (ctx.home_rest_days - ctx.away_rest_days)
        # heat: acclimatization + underdog compression
        if ctx.heat > 0:
            ra += (ctx.home_heat_adapt - ctx.away_heat_adapt) * 22 * ctx.heat
            ra += -0.06 * ctx.heat * (ra - rb)
        ra += ctx.altitude_edge
        return ra, rb

    def expected_goals(self, home, away, ctx=MatchContext()):
        ra, rb = self._adjusted(home, away, ctx)
        sup = (ra - rb) / self.div
        total = self.gpg * (1 - 0.05 * ctx.heat)
        return max(0.12, total/2 + sup/2), max(0.12, total/2 - sup/2)

    def scoreline_probs(self, home, away, ctx=MatchContext(), maxg=8):
        ga, gb = self.expected_goals(home, away, ctx)
        def pois(k, l): return math.exp(-l) * l**k / math.factorial(k)
        grid = {}
        for i in range(maxg+1):
            for j in range(maxg+1):
                grid[(i,j)] = pois(i, ga) * pois(j, gb)
        return grid

    def outcome_probs(self, home, away, ctx=MatchContext()):
        grid = self.scoreline_probs(home, away, ctx)
        hw = sum(p for (i,j),p in grid.items() if i>j)
        dr = sum(p for (i,j),p in grid.items() if i==j)
        aw = sum(p for (i,j),p in grid.items() if i<j)
        return hw, dr, aw

    def sample(self, home, away, ctx=MatchContext()):
        ga, gb = self.expected_goals(home, away, ctx)
        def knuth(l):
            L=math.exp(-l); k=0; p=1.0
            while True:
                k+=1; p*=random.random()
                if p<=L: return k-1
        return knuth(ga), knuth(gb)


# ----------------------------------------------------------------------
# LAYER 4: COMPETITION SIMULATOR (format described as data)
# ----------------------------------------------------------------------
class League:
    """Round-robin. fixtures: list of (home, away). double=True plays reverse too."""
    def __init__(self, teams, fixtures, points=(3,1,0)):
        self.teams=teams; self.fixtures=fixtures; self.points=points

    def simulate(self, match: PoissonMatch, ctx_for=lambda h,a: MatchContext()):
        tab={t:{"pts":0,"gf":0,"ga":0,"w":0,"d":0,"l":0} for t in self.teams}
        for h,a in self.fixtures:
            hg,ag = match.sample(h,a,ctx_for(h,a))
            tab[h]["gf"]+=hg; tab[h]["ga"]+=ag; tab[a]["gf"]+=ag; tab[a]["ga"]+=hg
            if hg>ag: tab[h]["pts"]+=self.points[0]; tab[h]["w"]+=1; tab[a]["l"]+=1
            elif hg<ag: tab[a]["pts"]+=self.points[0]; tab[a]["w"]+=1; tab[h]["l"]+=1
            else:
                tab[h]["pts"]+=self.points[1]; tab[a]["pts"]+=self.points[1]
                tab[h]["d"]+=1; tab[a]["d"]+=1
        order=sorted(self.teams, key=lambda t:(tab[t]["pts"], tab[t]["gf"]-tab[t]["ga"], tab[t]["gf"]), reverse=True)
        return order, tab

class Knockout:
    """Single or two-legged bracket. bracket: list of (teamA, teamB) for round 1."""
    def __init__(self, pairs, two_legged=False):
        self.pairs=pairs; self.two_legged=two_legged

    def _tie(self, match, a, b):
        if self.two_legged:
            g1=match.sample(a,b); g2=match.sample(b,a)
            agg_a=g1[0]+g2[1]; agg_b=g1[1]+g2[0]
            if agg_a!=agg_b: return a if agg_a>agg_b else b
        else:
            hg,ag=match.sample(a,b,MatchContext(neutral=True))
            if hg!=ag: return a if hg>ag else b
        # penalties ~ Elo-weighted
        ra,rb=match.elo.rating(a),match.elo.rating(b)
        return a if random.random()< ra/(ra+rb) else b

    def simulate(self, match):
        cur=list(self.pairs); results={}
        rnd=1
        while len(cur)>=1:
            winners=[]
            for a,b in cur:
                w=self._tie(match,a,b); winners.append(w)
            results[f"round{rnd}"]=winners
            if len(winners)==1: return winners[0], results
            cur=[(winners[i],winners[i+1]) for i in range(0,len(winners),2)]
            rnd+=1

def monte_carlo(sim_once, n=10000):
    """sim_once() -> returns a label (champion / winner). Returns prob dict."""
    counts=defaultdict(int)
    for _ in range(n):
        counts[sim_once()]+=1
    return {k: v/n for k,v in sorted(counts.items(), key=lambda x:-x[1])}


# ----------------------------------------------------------------------
# LAYER 5: BACKTESTING & CALIBRATION
# ----------------------------------------------------------------------
class Backtester:
    """Replays historical matches chronologically, predicts each before seeing result,
       updates ratings after. Scores with Brier + log-loss + calibration buckets."""
    def __init__(self, elo: EloModel):
        self.elo=elo

    def run(self, history):
        """history: list of dicts {home,away,hg,ag,neutral,importance}"""
        pm=PoissonMatch(self.elo)
        brier=0.0; logloss=0.0; n=0
        buckets=defaultdict(lambda:[0,0])  # predicted-bin -> [hits, total]
        for m in history:
            hw,dr,aw=pm.outcome_probs(m["home"],m["away"],MatchContext(neutral=m.get("neutral",False)))
            actual = 0 if m["hg"]>m["ag"] else 1 if m["hg"]==m["ag"] else 2
            probs=[hw,dr,aw]
            # Ranked Probability Score is ideal for ordered 1X2; here we use the
            # standard multiclass Brier AVERAGED over the 3 classes (0..1 scale).
            sq=sum((probs[k]-(1.0 if actual==k else 0.0))**2 for k in range(3))
            brier+= sq/3.0
            p_actual=max(probs[actual],1e-9)
            logloss+= -math.log(p_actual)
            # calibration: track the predicted home-win prob vs whether home won
            b=round(hw*10)/10
            buckets[b][0]+= 1 if actual==0 else 0
            buckets[b][1]+=1
            n+=1
            # Pass xG through if the model + data support it (DualRatingModel).
            if hasattr(self.elo, "xg"):
                self.elo.update(m["home"],m["away"],m["hg"],m["ag"],
                                xg_h=m.get("xg_h"), xg_a=m.get("xg_a"),
                                neutral=m.get("neutral",False), importance=m.get("importance",1.0))
            else:
                self.elo.update(m["home"],m["away"],m["hg"],m["ag"],
                                neutral=m.get("neutral",False), importance=m.get("importance",1.0))
        return {
            "matches":n,
            "brier":brier/n,           # lower better; ~0.18-0.20 is good for 1X2
            "logloss":logloss/n,       # lower better; ~0.95-1.0 is good
            "calibration":{round(k,1):(h/t if t else None, t) for k,(h,t) in sorted(buckets.items())}
        }
