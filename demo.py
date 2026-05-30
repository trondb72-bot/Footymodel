import random
from engine import EloModel, PoissonMatch, League, Knockout, monte_carlo, Backtester, MatchContext
random.seed(0)

print("="*64)
print("DEMO 1 — BACKTEST & CALIBRATION on synthetic 'true-skill' season")
print("="*64)
# Build a synthetic world with known true strengths, generate a season of results,
# then check the engine LEARNS those strengths and is well-calibrated.
import math
true={f"T{i}":1400+ i*22 for i in range(20)}  # 20 teams, spread of skill
def true_match(h,a):
    sup=(true[h]+55 - true[a])/130; tot=2.75
    ga=max(.12,tot/2+sup/2); gb=max(.12,tot/2-sup/2)
    def kn(l):
        L=math.exp(-l);k=0;p=1.0
        while True:
            k+=1;p*=random.random()
            if p<=L:return k-1
    return kn(ga),kn(gb)
teams=list(true)
history=[]
for season in range(3):  # 3 seasons of double round robin
    for h in teams:
        for a in teams:
            if h==a: continue
            hg,ag=true_match(h,a)
            history.append({"home":h,"away":a,"hg":hg,"ag":ag})
random.shuffle(history)  # chronological-ish; shuffle ok for demo

elo=EloModel(base=1500,k=24,home_adv=55)
bt=Backtester(elo)
report=bt.run(history)
print(f"Matches scored : {report['matches']}")
print(f"Brier score    : {report['brier']:.4f}   (lower=better; <0.20 good for 1X2)")
print(f"Log-loss       : {report['logloss']:.4f}   (lower=better; ~0.95-1.0 good)")
print("Calibration (predicted home-win prob -> actual home-win rate):")
for p,(rate,tot) in report["calibration"].items():
    if rate is not None and tot>30:
        bar="#"*int(rate*30)
        print(f"  pred {p:.1f} -> actual {rate:.2f}  (n={tot:4d}) {bar}")
# did Elo recover the true ranking?
learned=sorted(teams,key=lambda t:-elo.rating(t))
true_order=sorted(teams,key=lambda t:-true[t])
agree=sum(1 for i,t in enumerate(learned[:5]) if t in true_order[:5])
print(f"\nTop-5 recovery: engine's top 5 contains {agree}/5 of the truly-best teams.")

print("\n"+"="*64)
print("DEMO 2 — LEAGUE simulation (mini 6-team double round robin)")
print("="*64)
six=teams[:6]
fixtures=[(h,a) for h in six for a in six if h!=a]
lg=League(six,fixtures)
def champ():
    order,_=lg.simulate(PoissonMatch(elo)); return order[0]
probs=monte_carlo(champ, n=4000)
for t,p in list(probs.items())[:6]:
    print(f"  {t}: {p*100:4.1f}% to win the league   (Elo {elo.rating(t):.0f})")

print("\n"+"="*64)
print("DEMO 3 — KNOCKOUT (8-team single-leg cup)")
print("="*64)
eight=teams[-8:]
pairs=[(eight[i],eight[i+1]) for i in range(0,8,2)]
def cupwin():
    return Knockout(pairs).simulate(PoissonMatch(elo))[0]
cp=monte_carlo(cupwin,n=4000)
for t,p in list(cp.items()):
    print(f"  {t}: {p*100:4.1f}% to win the cup   (Elo {elo.rating(t):.0f})")
