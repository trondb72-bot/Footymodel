import requests
import json
import os
import csv
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from io import StringIO
from .models import MatchData

class DataAdapter:
    def __init__(self, cache_dir: str = "/home/team/shared/footymodel/data/cache", api_key: Optional[str] = None):
        self.cache_dir = cache_dir
        self.api_key = api_key
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, source: str, competition: str, season: str) -> str:
        return os.path.join(self.cache_dir, f"{source}_{competition}_{season}.json")

    def _load_cache(self, source: str, competition: str, season: str) -> Optional[List[MatchData]]:
        path = self._get_cache_path(source, competition, season)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                matches = []
                for m in data:
                    if m.get('date') and isinstance(m['date'], str):
                        m['date'] = datetime.strptime(m['date'], '%Y-%m-%d').date()
                    matches.append(MatchData(**m))
                return matches
        return None

    def _save_cache(self, source: str, competition: str, season: str, matches: List[MatchData]):
        path = self._get_cache_path(source, competition, season)
        with open(path, 'w') as f:
            json.dump([m.__dict__ for m in matches], f, default=str)

    def fetch_football_data_co_uk(self, competition: str, season: str) -> List[MatchData]:
        # season in format 2324
        cached = self._load_cache("fd_uk", competition, season)
        if cached: return cached

        url = f"https://www.football-data.co.uk/mmz4281/{season}/{competition}.csv"
        response = requests.get(url)
        response.raise_for_status()
        
        f = StringIO(response.text)
        reader = csv.DictReader(f)
        matches = []
        for row in reader:
            try:
                date_str = row.get('Date', '')
                dt = None
                if date_str:
                    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
                        try:
                            dt = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                
                matches.append(MatchData(
                    home=row['HomeTeam'],
                    away=row['AwayTeam'],
                    hg=int(row['FTHG']),
                    ag=int(row['FTAG']),
                    date=dt
                ))
            except (KeyError, ValueError):
                continue
        
        self._save_cache("fd_uk", competition, season, matches)
        return matches

    def fetch_openligadb(self, league: str, season: str) -> List[MatchData]:
        cached = self._load_cache("openliga", league, season)
        if cached: return cached

        url = f"https://api.openligadb.de/getmatchdata/{league}/{season}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        matches = []
        for item in data:
            if not item.get('matchIsFinished'): continue
            results = item.get('matchResults', [])
            if not results: continue
            final_result = results[-1]
            hg = final_result.get('pointsTeam1')
            ag = final_result.get('pointsTeam2')
            date_str = item.get('matchDateTime')
            dt = datetime.fromisoformat(date_str).date() if date_str else None
            
            matches.append(MatchData(
                home=item['team1']['teamName'],
                away=item['team2']['teamName'],
                hg=hg,
                ag=ag,
                date=dt
            ))
        
        self._save_cache("openliga", league, season, matches)
        return matches

    def fetch_football_data_org(self, competition: str, season: str) -> List[MatchData]:
        # Free key needed in headers: X-Auth-Token
        if not self.api_key:
            return []
            
        cached = self._load_cache("fd_org", competition, season)
        if cached: return cached

        url = f"https://api.football-data.org/v4/competitions/{competition}/matches?season={season}"
        headers = {'X-Auth-Token': self.api_key}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        matches = []
        for m in data.get('matches', []):
            if m.get('status') != 'FINISHED': continue
            score = m.get('score', {}).get('fullTime', {})
            hg = score.get('home')
            ag = score.get('away')
            if hg is None or ag is None: continue
            
            date_str = m.get('utcDate')
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date() if date_str else None
            
            matches.append(MatchData(
                home=m['homeTeam']['name'],
                away=m['awayTeam']['name'],
                hg=hg,
                ag=ag,
                date=dt
            ))
            
        self._save_cache("fd_org", competition, season, matches)
        return matches
