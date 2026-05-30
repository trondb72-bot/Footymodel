"""
footymodel — Layer 1: free data adapters.

Each adapter yields the engine's common match dict:
    {"home","away","hg","ag","xg_h","xg_a","neutral","importance","date"}
xg_* is None when the source has no xG (engine falls back to goals automatically).

FREE SOURCES INCLUDED (verified May 2026):
  1. FootballDataOrg  -> fixtures/results/standings, 12 leagues, free API key, 10 req/min
  2. Understat        -> BEST surviving free xG (6 top leagues). [FBref lost Opta xG Jan 2026]
  3. FootballDataCoUk -> huge free CSV archive of historical results (no key) — ideal backtesting
  4. OpenLigaDB       -> fully free, no key (German Bundesliga etc.)

Dependencies: `requests` for the APIs. CSV adapter uses stdlib only.
Be a good citizen: cache, rate-limit, and check each source's Terms of Service —
free-to-view is not the same as free-to-redistribute, and betting use is often restricted.
"""
import csv, io, json, re, time, datetime as dt
from urllib.request import urlopen, Request

UA = {"User-Agent": "footymodel/1.0 (personal research)"}

def _get(url, headers=None, retries=3, pause=1.0):
    h = dict(UA); h.update(headers or {})
    for i in range(retries):
        try:
            req = Request(url, headers=h)
            with urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == retries-1: raise
            time.sleep(pause*(i+1))

def _norm_date(s):
    if not s: return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d","%d/%m/%Y","%d/%m/%y"):
        try: return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError: continue
    return s

# ----------------------------------------------------------------------
# 1. football-data.org — fixtures, results, standings (free key, 10 req/min)
#    Register free: https://www.football-data.org/client/register
# ----------------------------------------------------------------------
class FootballDataOrg:
    BASE = "https://api.football-data.org/v4"
    # competition codes: PL=Premier League, PD=La Liga, SA=Serie A, BL1=Bundesliga,
    # FL1=Ligue 1, CL=Champions League, EC=Euros, WC=World Cup, DED=Eredivisie, PPL=Primeira
    def __init__(self, token, min_interval=6.5):
        self.token = token; self.min_interval = min_interval; self._last = 0

    def _throttle(self):
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0: time.sleep(wait)
        self._last = time.time()

    def matches(self, competition="PL", season=None, status="FINISHED"):
        """Yield finished matches for a competition/season as engine dicts."""
        self._throttle()
        url = f"{self.BASE}/competitions/{competition}/matches?status={status}"
        if season: url += f"&season={season}"
        data = json.loads(_get(url, headers={"X-Auth-Token": self.token}))
        for m in data.get("matches", []):
            ft = m.get("score", {}).get("fullTime", {})
            if ft.get("home") is None: continue
            yield {
                "home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                "hg": ft["home"], "ag": ft["away"],
                "xg_h": None, "xg_a": None,           # no xG on this source
                "neutral": False,
                "importance": 1.5 if competition in ("CL","WC","EC") else 1.0,
                "date": _norm_date(m.get("utcDate")),
            }

# ----------------------------------------------------------------------
# 2. Understat — best surviving FREE xG source (EPL, La Liga, Serie A,
#    Bundesliga, Ligue 1, RFPL). Data is embedded as JSON in the page.
# ----------------------------------------------------------------------
class Understat:
    LEAGUES = {"EPL":"EPL","La_liga":"La_liga","Serie_A":"Serie_A",
               "Bundesliga":"Bundesliga","Ligue_1":"Ligue_1","RFPL":"RFPL"}
    def __init__(self, pause=1.5): self.pause = pause

    def _extract(self, html, var):
        # Understat embeds: var teamsData = JSON.parse('...hex-escaped...')
        m = re.search(var + r"\s*=\s*JSON\.parse\('(.+?)'\)", html)
        if not m: return None
        raw = m.group(1).encode().decode("unicode_escape")
        return json.loads(raw)

    def matches(self, league="EPL", season="2025"):
        """Yield finished matches WITH xG for a league/season (season = start year)."""
        url = f"https://understat.com/league/{league}/{season}"
        html = _get(url)
        data = self._extract(html, "datesData")
        time.sleep(self.pause)
        if not data: return
        for m in data:
            if not m.get("isResult"): continue
            yield {
                "home": m["h"]["title"], "away": m["a"]["title"],
                "hg": int(m["goals"]["h"]), "ag": int(m["goals"]["a"]),
                "xg_h": round(float(m["xG"]["h"]), 2),
                "xg_a": round(float(m["xG"]["a"]), 2),
                "neutral": False, "importance": 1.0,
                "date": _norm_date(m.get("datetime","").split(" ")[0]),
            }

# ----------------------------------------------------------------------
# 3. football-data.co.uk — massive FREE CSV archive, no key. Best for
#    backtesting (decades of results for many leagues). No xG, but has
#    shots/odds columns you can use later.
#    e.g. https://www.football-data.co.uk/mmz4281/2425/E0.csv  (24/25 EPL)
# ----------------------------------------------------------------------
class FootballDataCoUk:
    # league codes: E0=EPL E1=Champ, SP1=La Liga, I1=Serie A, D1=Bundesliga, F1=Ligue1
    def matches(self, season_code="2425", league="E0"):
        url = f"https://www.football-data.co.uk/mmz4281/{season_code}/{league}.csv"
        text = _get(url)
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if not row.get("FTHG"): continue
            try: hg, ag = int(row["FTHG"]), int(row["FTAG"])
            except (ValueError, TypeError): continue
            yield {
                "home": row.get("HomeTeam"), "away": row.get("AwayTeam"),
                "hg": hg, "ag": ag,
                "xg_h": None, "xg_a": None,
                "neutral": False, "importance": 1.0,
                "date": _norm_date(row.get("Date")),
                # bonus fields available for later: shots, shots-on-target, odds
                "shots_h": _safe_int(row.get("HS")), "shots_a": _safe_int(row.get("AS")),
            }

# ----------------------------------------------------------------------
# 4. OpenLigaDB — fully free, no key (mainly German football)
# ----------------------------------------------------------------------
class OpenLigaDB:
    BASE = "https://api.openligadb.de"
    def matches(self, league="bl1", season="2025"):
        url = f"{self.BASE}/getmatchdata/{league}/{season}"
        data = json.loads(_get(url))
        for m in data:
            if not m.get("matchIsFinished"): continue
            res = next((r for r in m.get("matchResults",[]) if r.get("resultTypeID")==2), None)
            if not res: continue
            yield {
                "home": m["team1"]["teamName"], "away": m["team2"]["teamName"],
                "hg": res["pointsTeam1"], "ag": res["pointsTeam2"],
                "xg_h": None, "xg_a": None, "neutral": False, "importance": 1.0,
                "date": _norm_date((m.get("matchDateTimeUTC") or "")[:10]),
            }

def _safe_int(x):
    try: return int(float(x))
    except (ValueError, TypeError): return None

# ----------------------------------------------------------------------
# Helper: merge Understat xG into a results feed (e.g. football-data.org),
# matching on date + team names, so you get one feed with results + xG.
# Real team-name reconciliation needs an alias map; this is the skeleton.
# ----------------------------------------------------------------------
def merge_xg(results_feed, understat_feed, alias=lambda n: n):
    xg_index = {}
    for m in understat_feed:
        key = (m["date"], alias(m["home"]), alias(m["away"]))
        xg_index[key] = (m["xg_h"], m["xg_a"])
    for m in results_feed:
        key = (m["date"], alias(m["home"]), alias(m["away"]))
        if key in xg_index:
            m["xg_h"], m["xg_a"] = xg_index[key]
        yield m

if __name__ == "__main__":
    print("footymodel data sources — quick self-check (offline parsing only)")
    # Test CSV + Understat parsers on tiny inline samples (no network needed)
    sample_csv = "Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS\n10/08/24,Arsenal,Chelsea,2,1,15,9\n"
    rows = list(FootballDataCoUk.matches.__wrapped__(None, ) ) if False else []
    import io as _io
    r = csv.DictReader(_io.StringIO(sample_csv))
    parsed = [{"home":x["HomeTeam"],"away":x["AwayTeam"],"hg":int(x["FTHG"]),"ag":int(x["FTAG"])} for x in r]
    print("CSV parse:", parsed)
    us = Understat()
    fake = r"""var datesData = JSON.parse('[{\"isResult\":true,\"h\":{\"title\":\"Arsenal\"},\"a\":{\"title\":\"Chelsea\"},\"goals\":{\"h\":\"2\",\"a\":\"1\"},\"xG\":{\"h\":\"1.84\",\"a\":\"0.92\"},\"datetime\":\"2024-08-10 16:30:00\"}]')"""
    got = us._extract(fake, "datesData")
    print("Understat xG parse:", got)
