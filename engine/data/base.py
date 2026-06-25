from abc import ABC, abstractmethod
from typing import List
from .models import MatchData

class DataAdapter(ABC):
    @abstractmethod
    def fetch_matches(self, competition: str, season: str) -> List[MatchData]:
        pass
