import json
import os
from datetime import datetime
from typing import List, Optional
from .models import MatchData
from .csv_adapter import CSVAdapter
from .openligadb_adapter import OpenLigaDBAdapter

class DataLoader:
    def __init__(self, cache_dir: str = "/home/team/shared/footymodel/data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.csv_adapter = CSVAdapter()
        self.openliga_adapter = OpenLigaDBAdapter()

    def _get_cache_path(self, competition: str, season: str) -> str:
        return os.path.join(self.cache_dir, f"{competition}_{season}.json")

    def load_from_csv(self, url: str, competition: str, season: str, force_refresh: bool = False) -> List[MatchData]:
        cache_path = self._get_cache_path(competition, season)
        if not force_refresh and os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                data = json.load(f)
                matches = []
                for m in data:
                    if m.get('date') and isinstance(m['date'], str):
                        m['date'] = datetime.strptime(m['date'], '%Y-%m-%d').date()
                    matches.append(MatchData(**m))
                return matches
        
        matches = self.csv_adapter.fetch_matches(url)
        
        # Save to cache
        with open(cache_path, 'w') as f:
            json.dump([m.__dict__ for m in matches], f, default=str)
            
        return matches

    def load_from_openliga(self, league: str, season: str, force_refresh: bool = False) -> List[MatchData]:
        cache_path = self._get_cache_path(league, season)
        if not force_refresh and os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                data = json.load(f)
                matches = []
                for m in data:
                    if m.get('date') and isinstance(m['date'], str):
                        m['date'] = datetime.strptime(m['date'], '%Y-%m-%d').date()
                    matches.append(MatchData(**m))
                return matches
        
        matches = self.openliga_adapter.fetch_matches(league, season)
        
        with open(cache_path, 'w') as f:
            json.dump([m.__dict__ for m in matches], f, default=str)
            
        return matches

    def load_competition(self, competition: str, season: str) -> List[MatchData]:
        # Placeholder for other adapters
        # For now, let's assume we use CSV for some known competitions
        # E.g. E0 (Premier League)
        urls = {
            "E0": f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv",
            "D1": f"https://www.football-data.co.uk/mmz4281/{season}/D1.csv",
        }
        
        if competition in urls:
            return self.load_from_csv(urls[competition], competition, season)
        
        return []
