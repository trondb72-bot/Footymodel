import sys
import os

# Add project root to path
sys.path.append("/home/team/shared/footymodel")

from engine.data.models import MatchData
from engine.ratings.elo import EloEngine
from engine.match.model import MatchModel

def test_workflow():
    print("Testing Engine Workflow...")
    
    # 1. Setup Engine
    elo = EloEngine()
    model = MatchModel()
    
    # 2. Synthetic Data
    matches = [
        MatchData(home="Arsenal", away="Man City", hg=2, ag=1, xg_h=2.1, xg_a=1.2),
        MatchData(home="Liverpool", away="Chelsea", hg=1, ag=1, xg_h=1.5, xg_a=0.8),
        MatchData(home="Man City", away="Liverpool", hg=3, ag=0, xg_h=2.5, xg_a=0.5),
    ]
    
    # 3. Process Matches
    for m in matches:
        print(f"Updating Elo for {m.home} vs {m.away} ({m.hg}-{m.ag})")
        elo.update(m.home, m.away, m.hg, m.ag, m.xg_h, m.xg_a)
        
    # 4. Predict Next Match
    rh = elo.get_rating("Arsenal")
    ra = elo.get_rating("Man City")
    
    print(f"Arsenal Rating: {rh:.2f}")
    print(f"Man City Rating: {ra:.2f}")
    
    prediction = model.predict_match(rh, ra)
    print(f"Prediction Arsenal vs Man City:")
    print(f"  Win: {prediction['1']*100:.1f}%")
    print(f"  Draw: {prediction['X']*100:.1f}%")
    print(f"  Loss: {prediction['2']*100:.1f}%")
    print(f"  Exp Goals: {prediction['egh']:.2f} - {prediction['ega']:.2f}")

if __name__ == "__main__":
    test_workflow()
