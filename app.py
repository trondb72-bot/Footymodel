"""
footymodel — full-stack app backend (FastAPI).
Wraps the engine + data adapters and serves a web UI.

Run:
    pip install fastapi uvicorn requests
    python app.py            # then open http://localhost:8000

Set FOOTBALL_DATA_TOKEN env var (free key from football-data.org) to enable
live data. Without it, the app loads a bundled snapshot so everything works offline.
"""
import os, json, threading, datetime as dt
from typing import Optional
from engine import DualRatingModel, PoissonMatch, League, Knockout, monte_carlo, Backtester, MatchContext

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    raise SystemExit("Install deps first:  pip install fastapi uvicorn requests")

# ----------------------------------------------------------------------
# In-memory app state (one model per competition, rebuilt from its feed)
# ----------------------------------------------------------------------
class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.comps = {}      # code -> {"name","teams","feed","model","report","blend","loaded"}

    def competition(self, code):
        if code not in self.comps:
            raise HTTPException(404, f"Competition '{code}' not loaded. POST /api/load first.")
        return self.comps[code]

STORE = Store()
TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")

# competitions the UI offers
CATALOG = {
    "PL":  {"name": "Premier League",  "understat": "EPL"},
    "PD":  {"name": "La Liga",         "understat": "La_liga"},
    "SA":  {"name": "Serie A",         "understat": "Serie_A"},
    "BL1": {"name": "Bundesliga",      "understat": "Bundesliga"},
    "FL1": {"name": "Ligue 1",         "understat": "Ligue_1"},
}

# ----------------------------------------------------------------------
# Data loading: live (if token) else bundled snapshot
# ----------------------------------------------------------------------
def load_feed(code, season=2025):
    meta = CATALOG[code]
    if TOKEN:
        from sources import FootballDataOrg, Understat, merge_xg
        results = list(FootballDataOrg(TOKEN).matches(competition=code, season=season))
        try:
            xg = list(Understat().matches(league=meta["understat"], season=str(season)))
            def alias(n): return n.replace(" FC","").replace(" AFC","").replace("&","and").strip()
            feed = list(merge_xg(results, xg, alias=alias))
        except Exception:
            feed = results  # xG optional; degrade gracefully
        feed.sort(key=lambda m: m["date"] or "")
        return feed, "live (football-data.org + Understat xG)"
    # ---- bundled offline snapshot (synthetic but realistic) ----
    return _snapshot(code), "bundled snapshot (no API key set)"

def _snapshot(code):
    import random, math
    random.seed(hash(code) % 9999)
    names = {
        "PL": ["Arsenal","Man City","Liverpool","Tottenham","Chelsea","Newcastle",
               "Aston Villa","Man United","Brighton","West Ham","Crystal Palace","Everton"],
        "PD": ["Real Madrid","Barcelona","Atletico","Athletic","Villarreal","Betis",
               "Real Sociedad","Sevilla","Valencia","Girona","Getafe","Osasuna"],
        "SA": ["Inter","Napoli","Juventus","Milan","Atalanta","Roma",
               "Lazio","Fiorentina","Bologna","Torino","Udinese","Genoa"],
        "BL1":["Bayern","Leverkusen","Stuttgart","Dortmund","Leipzig","Frankfurt",
               "Freiburg","Wolfsburg","Hoffenheim","Mainz","Bremen","Augsburg"],
        "FL1":["PSG","Monaco","Marseille","Lille","Nice","Lyon",
               "Rennes","Lens","Strasbourg","Brest","Toulouse","Nantes"],
    }[code]
    true = {t: 1560 - i*16 + random.uniform(-12,12) for i,t in enumerate(names)}
    def kn(l):
        L=math.exp(-l);k=0;p=1.0
        while True:
            k+=1;p*=random.random()
            if p<=L:return k-1
    feed=[]; d=dt.date(2025,8,15)
    for rnd in range(2):
        for h in names:
            for a in names:
                if h==a: continue
                sup=(true[h]+55-true[a])/130
                xh=max(.2,1.4+sup/2); xa=max(.2,1.4-sup/2)
                feed.append({"home":h,"away":a,
                    "hg":kn(xh*random.uniform(.6,1.5)),"ag":kn(xa*random.uniform(.6,1.5)),
                    "xg_h":round(xh,2),"xg_a":round(xa,2),
                    "neutral":False,"importance":1.0,"date":d.isoformat()})
                d += dt.timedelta(days=1)
    return feed

def build_model(feed, blend=0.65):
    model = DualRatingModel(base=1500, k=24, k_xg=22, home_adv=55, blend=blend)
    report = Backtester(model).run(feed)
    return model, report

# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
app = FastAPI(title="footymodel")

class LoadReq(BaseModel):
    competition: str
    season: int = 2025
    blend: float = 0.65

class MatchReq(BaseModel):
    competition: str
    home: str
    away: str
    neutral: bool = False
    heat: float = 0.0

class SimReq(BaseModel):
    competition: str
    n: int = 5000

@app.get("/api/catalog")
def catalog():
    return {"competitions": [{"code":c,"name":m["name"]} for c,m in CATALOG.items()],
            "data_mode": "live" if TOKEN else "snapshot"}

@app.post("/api/load")
def load(req: LoadReq):
    if req.competition not in CATALOG:
        raise HTTPException(400, "Unknown competition")
    with STORE.lock:
        feed, mode = load_feed(req.competition, req.season)
        if not feed:
            raise HTTPException(502, "No data returned from source")
        model, report = build_model(feed, req.blend)
        teams = sorted({m["home"] for m in feed} | {m["away"] for m in feed})
        STORE.comps[req.competition] = {
            "name": CATALOG[req.competition]["name"], "teams": teams,
            "feed": feed, "model": model, "report": report,
            "blend": req.blend, "mode": mode,
        }
    return {"ok": True, "competition": req.competition, "name": CATALOG[req.competition]["name"],
            "teams": teams, "matches": len(feed), "mode": mode,
            "brier": round(report["brier"],4), "logloss": round(report["logloss"],4)}

@app.get("/api/ratings/{code}")
def ratings(code: str):
    c = STORE.competition(code); m = c["model"]
    rows = [{"team":t,
             "rating":round(m.rating(t),1),
             "results":round(m.results.rating(t),1),
             "xg":round(m.xg.rating(t),1)} for t in c["teams"]]
    rows.sort(key=lambda r:-r["rating"])
    return {"ratings": rows, "blend": c["blend"]}

@app.post("/api/predict")
def predict(req: MatchReq):
    c = STORE.competition(req.competition)
    pm = PoissonMatch(c["model"])
    ctx = MatchContext(neutral=req.neutral, heat=req.heat)
    hw,dr,aw = pm.outcome_probs(req.home, req.away, ctx)
    grid = pm.scoreline_probs(req.home, req.away, ctx, maxg=5)
    top = sorted(grid.items(), key=lambda kv:-kv[1])[:6]
    eg = pm.expected_goals(req.home, req.away, ctx)
    return {
        "home":req.home,"away":req.away,
        "prob_home":round(hw*100,1),"prob_draw":round(dr*100,1),"prob_away":round(aw*100,1),
        "xg_home":round(eg[0],2),"xg_away":round(eg[1],2),
        "scorelines":[{"score":f"{i}-{j}","prob":round(p*100,1)} for (i,j),p in top],
    }

@app.post("/api/simulate")
def simulate(req: SimReq):
    c = STORE.competition(req.competition)
    teams = c["teams"]; pm = PoissonMatch(c["model"])
    fixtures = [(h,a) for h in teams for a in teams if h!=a]
    lg = League(teams, fixtures)
    # gather full-distribution outcomes: champion + top4 + relegation
    from collections import defaultdict
    pos = defaultdict(lambda: defaultdict(int))
    n = max(500, min(req.n, 20000))
    for _ in range(n):
        order,_ = lg.simulate(pm)
        for rank,t in enumerate(order):
            pos[t]["champ"] += 1 if rank==0 else 0
            pos[t]["top4"]  += 1 if rank<4 else 0
            pos[t]["releg"] += 1 if rank>=len(teams)-3 else 0
    rows = [{"team":t,
             "champ":round(100*pos[t]["champ"]/n,1),
             "top4":round(100*pos[t]["top4"]/n,1),
             "releg":round(100*pos[t]["releg"]/n,1)} for t in teams]
    rows.sort(key=lambda r:-r["champ"])
    return {"n":n,"table":rows}

@app.get("/api/health")
def health(): return {"ok":True,"mode":"live" if TOKEN else "snapshot"}

# serve frontend
@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__),"static","index.html")) as f:
        return f.read()

if os.path.isdir(os.path.join(os.path.dirname(__file__),"static")):
    app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__),"static")), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))   # hosting platforms set $PORT
    print(f"footymodel starting on :{port} — data mode: {'LIVE' if TOKEN else 'SNAPSHOT (set FOOTBALL_DATA_TOKEN for live)'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
