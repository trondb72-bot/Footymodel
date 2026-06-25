from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class MatchData:
    home: str
    away: str
    hg: int
    ag: int
    xg_h: Optional[float] = None
    xg_a: Optional[float] = None
    neutral: bool = False
    importance: float = 1.0
    date: Optional[date] = None

    def __post_init__(self):
        if self.xg_h is None:
            self.xg_h = float(self.hg)
        if self.xg_a is None:
            self.xg_a = float(self.ag)
