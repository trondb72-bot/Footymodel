import math
from datetime import datetime
from typing import List, Dict, Any, Tuple
from ..data.models import MatchData
from ..ratings.elo import EloEngine
from ..match.model import MatchModel

class BacktestEngine:
    def __init__(self, elo_engine: EloEngine, match_model: MatchModel):
        self.elo = elo_engine
        self.model = match_model
        self.predictions = [] # List of {"pred": dict, "actual": str}
        self.calibration_points = []
        
    def run(self, matches: List[MatchData]):
        # Sort matches by date to ensure chronological updates
        sorted_matches = sorted(matches, key=lambda m: m.date if m.date else datetime.min)
        
        self.predictions = []
        for m in sorted_matches:
            # 1. Get ratings BEFORE update
            rh = self.elo.get_rating(m.home)
            ra = self.elo.get_rating(m.away)
            
            # 2. Predict match result
            pred = self.model.predict_match(rh, ra, neutral=m.neutral)
            actual = "1" if m.hg > m.ag else ("X" if m.hg == m.ag else "2")
            
            self.predictions.append({"pred": pred, "actual": actual})
            
            # 3. Update Elo with the actual result
            self.elo.update(m.home, m.away, m.hg, m.ag, m.xg_h, m.xg_a, neutral=m.neutral, importance=m.importance)
        
        self._calculate_calibration()
            
    def _calculate_calibration(self):
        if not self.predictions:
            self.calibration_points = []
            return

        # Calibration bins for '1' (Home Win)
        # Using 10 bins (0.0-0.1, 0.1-0.2, ..., 0.9-1.0)
        bin_observed = [[] for _ in range(10)]
        bin_predicted = [[] for _ in range(10)]
        
        for p in self.predictions:
            pred = p["pred"]
            actual = p["actual"]
            
            # Calibration data (Home Win)
            idx = min(9, int(pred["1"] * 10))
            bin_observed[idx].append(1.0 if actual == "1" else 0.0)
            bin_predicted[idx].append(pred["1"])
            
        self.calibration_points = []
        for i in range(10):
            if bin_observed[i]:
                self.calibration_points.append({
                    "bin": f"{i/10.0:.1f}-{(i+1)/10.0:.1f}",
                    "observed_freq": sum(bin_observed[i]) / len(bin_observed[i]),
                    "predicted_prob": sum(bin_predicted[i]) / len(bin_predicted[i]),
                    "count": len(bin_observed[i])
                })
            else:
                self.calibration_points.append({
                    "bin": f"{i/10.0:.1f}-{(i+1)/10.0:.1f}",
                    "observed_freq": 0.0,
                    "predicted_prob": (i + 0.5) / 10.0,
                    "count": 0
                })

    def get_calibration_curve(self) -> List[Dict[str, Any]]:
        return self.calibration_points

    def get_metrics(self) -> Dict[str, Any]:
        if not self.predictions:
            return {}
            
        brier_sum = 0.0
        log_loss_sum = 0.0
        correct = 0
        
        for p in self.predictions:
            pred = p["pred"]
            actual = p["actual"]
            
            # Brier Score: avg over 3 classes (1, X, 2)
            # Standard Brier for multi-class is sum((p-o)^2). 
            # Prompt says "avg over 3 classes", which sometimes means sum((p-o)^2)/3.
            bmatch = 0.0
            for outcome in ["1", "X", "2"]:
                o_k = 1.0 if outcome == actual else 0.0
                bmatch += (pred[outcome] - o_k) ** 2
            brier_sum += (bmatch / 3.0) 
            
            # Log Loss
            log_loss_sum -= math.log(max(1e-15, pred[actual]))
            
            # Accuracy
            predicted_outcome = max(["1", "X", "2"], key=lambda k: pred[k])
            if predicted_outcome == actual:
                correct += 1
                
        n = len(self.predictions)
        return {
            "brier": brier_sum / n,
            "log_loss": log_loss_sum / n,
            "accuracy": correct / n,
            "calibration_points": self.calibration_points,
            "match_count": n
        }
