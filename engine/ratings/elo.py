import math
from typing import Dict, Tuple, List, Any

class EloEngine:
    def __init__(self, 
                 k_results: float = 28, 
                 k_xg: float = 21, 
                 home_adv: float = 55,
                 blend_xg: float = 0.65):
        self.k_results = k_results
        self.k_xg = k_xg
        self.home_adv = home_adv
        self.blend_xg = blend_xg
        
        # team -> rating
        self.ratings_results = {}
        self.ratings_xg = {}
        self.match_counts = {}

    def get_rating(self, team: str) -> float:
        r_res = self.ratings_results.get(team, 1500.0)
        r_xg = self.ratings_xg.get(team, 1500.0)
        return (1 - self.blend_xg) * r_res + self.blend_xg * r_xg

    def get_full_ratings(self, team: str) -> Dict[str, Any]:
        r_res = self.ratings_results.get(team, 1500.0)
        r_xg = self.ratings_xg.get(team, 1500.0)
        return {
            "team": team,
            "blended": (1 - self.blend_xg) * r_res + self.blend_xg * r_xg,
            "results_elo": r_res,
            "xg_elo": r_xg,
            "matches": self.match_counts.get(team, 0)
        }

    def _expected_score(self, ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    def _mov_multiplier(self, gd: int, ra: float, rb: float) -> float:
        if gd == 0:
            return 1.0
        # Lead's formula: ln(|gd|+1)*(2.2/(|Ra-Rb|*0.001+2.2))
        return math.log(abs(gd) + 1.0) * (2.2 / (abs(ra - rb) * 0.001 + 2.2))

    def update(self, home_team: str, away_team: str, hg: int, ag: int, xg_h: float, xg_a: float, neutral: bool = False, importance: float = 1.0):
        # Current ratings
        rh_res = self.ratings_results.get(home_team, 1500.0)
        ra_res = self.ratings_results.get(away_team, 1500.0)
        
        rh_xg = self.ratings_xg.get(home_team, 1500.0)
        ra_xg = self.ratings_xg.get(away_team, 1500.0)

        # Home advantage adjustment
        rh_res_adj = rh_res + (0 if neutral else self.home_adv)
        rh_xg_adj = rh_xg + (0 if neutral else self.home_adv)

        # 1. Results Elo
        ea_res = self._expected_score(rh_res_adj, ra_res)
        sa_res = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        gd = hg - ag
        mov = self._mov_multiplier(gd, rh_res_adj, ra_res)
        
        delta_res = self.k_results * importance * mov * (sa_res - ea_res)
        self.ratings_results[home_team] = rh_res + delta_res
        self.ratings_results[away_team] = ra_res - delta_res

        # 2. xG Elo
        ea_xg = self._expected_score(rh_xg_adj, ra_xg)
        if xg_h + xg_a > 0:
            sa_xg = xg_h / (xg_h + xg_a)
        else:
            sa_xg = 0.5
        
        delta_xg = self.k_xg * importance * (sa_xg - ea_xg)
        self.ratings_xg[home_team] = rh_xg + delta_xg
        self.ratings_xg[away_team] = ra_xg - delta_xg
        
        # Update match counts
        self.match_counts[home_team] = self.match_counts.get(home_team, 0) + 1
        self.match_counts[away_team] = self.match_counts.get(away_team, 0) + 1
