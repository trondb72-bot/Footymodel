# Running the footymodel app

## 1. Install
```bash
pip install fastapi uvicorn requests
```

## 2. (Optional) enable live data
Get a free key at https://www.football-data.org/client/register then:
```bash
export FOOTBALL_DATA_TOKEN="your_key_here"     # Windows: set FOOTBALL_DATA_TOKEN=...
```
Without a key the app runs on a realistic bundled snapshot — everything still works.

## 3. Start
```bash
python app.py
```
Open http://localhost:8000

## What you can do
- **Load & train** a competition (Premier League, La Liga, Serie A, Bundesliga, Ligue 1).
  Builds dual Elo+xG ratings and shows the out-of-sample Brier / log-loss.
- **Blend slider** — set how much weight goes to xG vs. results (re-load to apply).
- **Team Ratings** — blended rating plus the results-only and xG-only components.
- **Match Predictor** — win/draw/win %, expected goals, and likeliest scorelines.
  Toggle neutral venue and dial in heat stress (the weather layer).
- **Season Simulation** — Monte Carlo over a full double round-robin for
  champion / top-4 / relegation probabilities.

## Architecture
```
  Browser UI (static/index.html)
        │  fetch /api/*
        ▼
  FastAPI (app.py)  ──  wraps  ──▶  engine.py   (Elo, DualRating, Poisson, League/Knockout, Backtester)
        │                              sources.py (football-data.org, Understat xG, CSV, OpenLigaDB)
        ▼
  in-memory model per competition
```
The web layer is thin — all forecasting is the engine you already have.
