import random
import math
from typing import List, Dict, Any, Tuple, Optional

class Simulator:
    def __init__(self, model, iterations: int = 10000):
        self.model = model
        self.iterations = iterations

    def _sample_match(self, rh: float, ra: float, neutral: bool = False) -> Tuple[int, int]:
        pred = self.model.predict_match(rh, ra, neutral=neutral)
        # Sample from the grid
        hg = random.choices(range(10), weights=[self.model._poisson_pmf(i, pred['egh']) for i in range(10)])[0]
        ag = random.choices(range(10), weights=[self.model._poisson_pmf(i, pred['ega']) for i in range(10)])[0]
        return hg, ag

    def _resolve_tie(self, t1: str, t2: str, ratings: Dict[str, float]) -> str:
        r1 = ratings[t1]
        r2 = ratings[t2]
        # P(A) = 1 / (1 + 10^((Rb - Ra) / 400))
        prob1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
        return t1 if random.random() < prob1 else t2

    def simulate_league(self, teams: List[str], ratings: Dict[str, float], fixtures: List[Tuple[str, str]]) -> Dict[str, Any]:
        results = {team: {
            "winner": 0, "top4": 0, "relegated": 0, 
            "total_pts": 0, "total_gd": 0, "total_gf": 0, "total_rank": 0
        } for team in teams}
        
        for _ in range(self.iterations):
            table = {team: {"pts": 0, "gd": 0, "gf": 0} for team in teams}
            for h, a in fixtures:
                hg, ag = self._sample_match(ratings[h], ratings[a])
                if hg > ag: table[h]["pts"] += 3
                elif ag > hg: table[a]["pts"] += 3
                else:
                    table[h]["pts"] += 1
                    table[a]["pts"] += 1
                table[h]["gd"] += (hg - ag)
                table[a]["gd"] += (ag - hg)
                table[h]["gf"] += hg
                table[a]["gf"] += ag
            
            ranked = sorted(teams, key=lambda t: (table[t]["pts"], table[t]["gd"], table[t]["gf"]), reverse=True)
            for rank, team in enumerate(ranked):
                pos = rank + 1
                results[team]["total_rank"] += pos
                results[team]["total_pts"] += table[team]["pts"]
                results[team]["total_gd"] += table[team]["gd"]
                results[team]["total_gf"] += table[team]["gf"]
                if pos == 1: results[team]["winner"] += 1
                if pos <= 4: results[team]["top4"] += 1
                if pos > len(teams) - 3: results[team]["relegated"] += 1

        final_teams = []
        for t in teams:
            final_teams.append({
                "team": t,
                "champion_pct": results[t]["winner"] / self.iterations,
                "top4_pct": results[t]["top4"] / self.iterations,
                "relegated_pct": results[t]["relegated"] / self.iterations,
                "avg_rank": results[t]["total_rank"] / self.iterations,
                "avg_pts": results[t]["total_pts"] / self.iterations
            })
        return {"teams": final_teams}

    def simulate_knockout(self, teams: List[str], ratings: Dict[str, float]) -> Dict[str, Any]:
        champs = {t: 0 for t in teams}
        semis = {t: 0 for t in teams}
        
        for _ in range(self.iterations):
            current_round = list(teams)
            while len(current_round) > 1:
                # Mark semifinalists
                if len(current_round) == 4:
                    for t in current_round: semis[t] += 1
                
                next_round = []
                for i in range(0, len(current_round), 2):
                    t1 = current_round[i]
                    if i + 1 >= len(current_round):
                        next_round.append(t1)
                        continue
                    t2 = current_round[i+1]
                    hg, ag = self._sample_match(ratings[t1], ratings[t2], neutral=True)
                    if hg > ag: next_round.append(t1)
                    elif ag > hg: next_round.append(t2)
                    else: next_round.append(self._resolve_tie(t1, t2, ratings))
                current_round = next_round
            champs[current_round[0]] += 1
            
        return {
            "teams": [{
                "team": t, 
                "champion_pct": champs[t] / self.iterations,
                "semifinalist_pct": semis[t] / self.iterations
            } for t in teams]
        }

    def simulate_group_knockout(self, groups: Dict[str, List[str]], ratings: Dict[str, float]) -> Dict[str, Any]:
        all_teams = [t for g in groups.values() for t in g]
        champs = {t: 0 for t in all_teams}
        semis = {t: 0 for t in all_teams}
        
        for _ in range(self.iterations):
            qualified = []
            for g_name, g_teams in groups.items():
                g_table = {t: {"pts": 0, "gd": 0, "gf": 0} for t in g_teams}
                # Single round robin for group (neutral)
                for i in range(len(g_teams)):
                    for j in range(i + 1, len(g_teams)):
                        t1, t2 = g_teams[i], g_teams[j]
                        hg, ag = self._sample_match(ratings[t1], ratings[t2], neutral=True)
                        if hg > ag: g_table[t1]["pts"] += 3
                        elif ag > hg: g_table[t2]["pts"] += 3
                        else:
                            g_table[t1]["pts"] += 1
                            g_table[t2]["pts"] += 1
                        g_table[t1]["gd"] += (hg - ag)
                        g_table[t2]["gd"] += (ag - hg)
                        g_table[t1]["gf"] += hg
                        g_table[t2]["gf"] += ag
                
                ranked = sorted(g_teams, key=lambda t: (g_table[t]["pts"], g_table[t]["gd"], g_table[t]["gf"]), reverse=True)
                qualified.extend(ranked[:2]) # Top 2 advance
            
            # Knockout
            current_round = qualified
            while len(current_round) > 1:
                if len(current_round) == 4:
                    for t in current_round: semis[t] += 1
                next_round = []
                for i in range(0, len(current_round), 2):
                    t1 = current_round[i]
                    if i + 1 >= len(current_round):
                        next_round.append(t1)
                        continue
                    t2 = current_round[i+1]
                    hg, ag = self._sample_match(ratings[t1], ratings[t2], neutral=True)
                    if hg > ag: next_round.append(t1)
                    elif ag > hg: next_round.append(t2)
                    else: next_round.append(self._resolve_tie(t1, t2, ratings))
                current_round = next_round
            if current_round:
                champs[current_round[0]] += 1
                
        return {
            "teams": [{
                "team": t, 
                "champion_pct": champs[t] / self.iterations,
                "semifinalist_pct": semis[t] / self.iterations
            } for t in all_teams]
        }
