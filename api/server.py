from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

from engine.data.adapters import DataAdapter
from engine.ratings.elo import EloEngine
from engine.match.model import MatchModel
from engine.simulate.simulator import Simulator
from engine.backtest.engine import BacktestEngine

app = FastAPI(title="FootyModel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
adapter = DataAdapter(api_key=os.environ.get("FOOTBALL_DATA_API_KEY"))
elo_engine = EloEngine()
match_model = MatchModel()

class LoadRequest(BaseModel):
    code: str
    season: str

class PredictRequest(BaseModel):
    home: str
    away: str
    neutral: bool = False
    heat: float = 20.0
    altitude: float = 0.0
    rest_days_h: int = 4
    rest_days_a: int = 4

class SimulateRequest(BaseModel):
    code: str
    format: str = "league"
    runs: int = 10000

@app.get("/catalog")
async def get_catalog():
    return {
        "competitions": [
            {"code": "E0", "name": "Premier League", "country": "England", "seasons": ["2324", "2223"]},
            {"code": "D1", "name": "Bundesliga", "country": "Germany", "seasons": ["2324", "2223"]},
            {"code": "bl1", "name": "Bundesliga (OpenLiga)", "country": "Germany", "seasons": ["2023", "2024"]}
        ]
    }

@app.post("/load")
async def load_competition(req: LoadRequest):
    global elo_engine
    elo_engine = EloEngine() # Reset engine
    
    if req.code == "bl1":
        matches = adapter.fetch_openligadb("bl1", req.season)
    elif req.code.startswith("PL"):
        matches = adapter.fetch_football_data_org(req.code, req.season)
    else:
        matches = adapter.fetch_football_data_co_uk(req.code, req.season)
        
    if not matches:
        raise HTTPException(status_code=404, detail="No matches found")
    
    backtester = BacktestEngine(elo_engine, match_model)
    backtester.run(matches)
    metrics = backtester.get_metrics()
    
    teams = sorted(list(elo_engine.match_counts.keys()))
    ratings_list = [elo_engine.get_full_ratings(t) for t in teams]
    
    return {
        "teams": ratings_list,
        "backtest": metrics,
        "match_count": len(matches)
    }

@app.get("/ratings/{code}")
async def get_ratings(code: str):
    teams = sorted(list(elo_engine.match_counts.keys()))
    return [elo_engine.get_full_ratings(t) for t in teams]

@app.post("/predict")
async def predict(req: PredictRequest):
    rh = elo_engine.get_rating(req.home)
    ra = elo_engine.get_rating(req.away)
    res = match_model.predict_match(
        rh, ra, 
        neutral=req.neutral, 
        temp_c=req.heat, 
        altitude_m=req.altitude,
        rest_days_h=req.rest_days_h,
        rest_days_a=req.rest_days_a
    )
    return {
        "h": res["1"],
        "d": res["X"],
        "a": res["2"],
        "egh": res["egh"],
        "ega": res["ega"],
        "scorelines": res["scorelines"]
    }

@app.post("/simulate")
async def simulate(req: SimulateRequest):
    sim = Simulator(match_model, iterations=req.runs)
    teams = sorted(list(elo_engine.match_counts.keys()))
    if not teams:
        raise HTTPException(status_code=400, detail="No teams loaded. Call /load first.")
    
    ratings = {t: elo_engine.get_rating(t) for t in teams}
    
    if req.format == "league":
        # Full round-robin
        fixtures = []
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                fixtures.append((teams[i], teams[j]))
                fixtures.append((teams[j], teams[i]))
        
        res = sim.simulate_league(teams, ratings, fixtures)
        return res
    elif req.format == "knockout":
        res = sim.simulate_knockout(teams, ratings)
        return res
    elif req.format == "group+knockout":
        # Split teams into groups of 4 automatically
        groups = {}
        for i in range(0, len(teams), 4):
            group_name = f"Group {chr(65 + i//4)}"
            groups[group_name] = teams[i:i+4]
        res = sim.simulate_group_knockout(groups, ratings)
        return res
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
