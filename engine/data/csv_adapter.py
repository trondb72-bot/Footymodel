import csv
import requests
from datetime import datetime
from typing import List
from io import StringIO
from .base import DataAdapter
from .models import MatchData

class CSVAdapter(DataAdapter):
    def fetch_matches(self, url: str) -> List[MatchData]:
        response = requests.get(url)
        response.raise_for_status()
        
        f = StringIO(response.text)
        reader = csv.DictReader(f)
        
        matches = []
        for row in reader:
            try:
                # football-data.co.uk uses dd/mm/yy or dd/mm/yyyy
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
        return matches
