import requests
from datetime import datetime
from typing import List
from .base import DataAdapter
from .models import MatchData

class OpenLigaDBAdapter(DataAdapter):
    def fetch_matches(self, league: str, season: str) -> List[MatchData]:
        url = f"https://api.openligadb.de/getmatchdata/{league}/{season}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        matches = []
        for item in data:
            if not item.get('matchIsFinished'):
                continue
                
            # Goals
            results = item.get('matchResults', [])
            if not results:
                continue
            
            # Usually the last result in the list is the final one
            final_result = results[-1]
            hg = final_result.get('pointsTeam1')
            ag = final_result.get('pointsTeam2')
            
            # Date
            date_str = item.get('matchDateTime')
            dt = None
            if date_str:
                # 2024-05-18T15:30:00
                dt = datetime.fromisoformat(date_str).date()
            
            matches.append(MatchData(
                home=item['team1']['teamName'],
                away=item['team2']['teamName'],
                hg=hg,
                ag=ag,
                date=dt
            ))
        return matches
