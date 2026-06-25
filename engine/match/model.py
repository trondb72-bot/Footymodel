import math
from typing import Dict, Tuple, List, Optional, Any

class MatchModel:
    def __init__(self, avg_total_goals: float = 2.7, home_adv_elo: float = 55):
        self.avg_total_goals = avg_total_goals
        self.home_adv_elo = home_adv_elo

    def _poisson_pmf(self, k: int, lam: float) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def predict_match(self, 
                      rating_h: float, 
                      rating_a: float, 
                      neutral: bool = False,
                      rest_days_h: Optional[int] = None,
                      rest_days_a: Optional[int] = None,
                      temp_c: float = 20.0,
                      altitude_m: float = 0.0) -> Dict[str, Any]:
        
        # Adjust ratings for home advantage
        rh_adj = rating_h + (0 if neutral else self.home_adv_elo)
        ra_adj = rating_a

        # Context adjustments to rating (Elo)
        # Rest days (+4 Elo per rest day gap)
        if rest_days_h is not None and rest_days_a is not None:
            rest_gap = rest_days_h - rest_days_a
            rh_adj += (rest_gap * 4)

        # Context adjustments to total goals
        total = self.avg_total_goals
        
        # Heat (suppress goals up to 15%)
        # Above 25C, suppress by 1% per degree, cap at 15%
        if temp_c > 25:
            suppression = min(0.15, (temp_c - 25) * 0.01)
            total *= (1.0 - suppression)
            
        # Altitude (suppress goals above 1500m)
        if altitude_m > 1500:
            # Simple linear suppression: 5% at 3000m
            alt_suppression = min(0.05, (altitude_m - 1500) * 0.000033)
            total *= (1.0 - alt_suppression)

        # Supremacy
        supremacy = (rh_adj - ra_adj) / 130.0
        
        # Expected goals
        egh = max(0.12, total / 2.0 + supremacy / 2.0)
        ega = max(0.12, total / 2.0 - supremacy / 2.0)
        
        # Probabilities
        prob_h = 0.0
        prob_d = 0.0
        prob_a = 0.0
        scorelines = []
        
        max_g = 10 # Lead said grid 0..9
        for i in range(max_g):
            p_i = self._poisson_pmf(i, egh)
            for j in range(max_g):
                p_j = self._poisson_pmf(j, ega)
                p_ij = p_i * p_j
                
                scorelines.append(((i, j), p_ij))
                
                if i > j:
                    prob_h += p_ij
                elif i == j:
                    prob_d += p_ij
                else:
                    prob_a += p_ij
                    
        # Sort scorelines by probability
        scorelines.sort(key=lambda x: x[1], reverse=True)
                    
        return {
            "1": prob_h,
            "X": prob_d,
            "2": prob_a,
            "egh": egh,
            "ega": ega,
            "scorelines": [[f"{s[0][0]}-{s[0][1]}", s[1]] for s in scorelines[:10]]
        }
