import random, math
from engine import EloModel, DualRatingModel, Backtester
random.seed(7)

# --- Synthetic world: true skill drives xG; actual goals = xG + finishing noise ---
# Some teams are "wasteful" (underperform xG), some "clinical" (overperform), randomly per match.
N_TEAMS=20
true={f"T{i}":1400+i*22 for i in range(N_TEAMS)}
teams=list(true)

def kn(l):
    L=math.exp(-l);k=0;p=1.0
    while True:
        k+=1;p*=random.random()
        if p<=L:return k-1

def gen_match(h,a):
    # expected goals from TRUE skill
    sup=(true[h]+55-true[a])/130
    xh=max(.12,2.75/2+sup/2); xa=max(.12,2.75/2-sup/2)
    # actual goals: Poisson around a NOISILY finished version of xG
    # finishing multiplier adds variance that a results-only model will chase
    fh=xh*random.uniform(0.5,1.6); fa=xa*random.uniform(0.5,1.6)
    hg,ag=kn(fh),kn(fa)
    # reported xG = true xG with small measurement noise
    return {"home":h,"away":a,"hg":hg,"ag":ag,
            "xg_h":round(xh*random.uniform(0.85,1.15),2),
            "xg_a":round(xa*random.uniform(0.85,1.15),2)}

# build 3 seasons; hold out the last season as out-of-sample test
def season():
    g=[]
    for h in teams:
        for a in teams:
            if h!=a: g.append(gen_match(h,a))
    random.shuffle(g); return g
train=season()+season()
test=season()

def evaluate(model, label):
    bt=Backtester(model)
    bt.run(train)                  # learn on training seasons
    # now score test season WITHOUT updating (freeze) — measure pure forecast quality
    from engine import PoissonMatch, MatchContext
    pm=PoissonMatch(model)
    brier=logloss=0.0; n=0
    for m in test:
        hw,dr,aw=pm.outcome_probs(m["home"],m["away"])
        actual=0 if m["hg"]>m["ag"] else 1 if m["hg"]==m["ag"] else 2
        probs=[hw,dr,aw]
        brier+=sum((probs[k]-(1.0 if actual==k else 0))**2 for k in range(3))/3
        logloss+= -math.log(max(probs[actual],1e-9)); n+=1
    print(f"{label:28s} Brier {brier/n:.4f}   LogLoss {logloss/n:.4f}")
    return brier/n

print("Out-of-sample forecast quality (lower = better):\n")
b_res = evaluate(EloModel(base=1500,k=24,home_adv=55), "Results-only Elo")
b_dual= evaluate(DualRatingModel(base=1500,k=24,k_xg=22,home_adv=55,blend=0.5), "Dual (results+xG, 50/50)")
b_xg  = evaluate(DualRatingModel(base=1500,k=24,k_xg=22,home_adv=55,blend=0.75),"Dual (xG-weighted, 75% xG)")

print(f"\nImprovement of 50/50 blend over results-only: {100*(b_res-b_dual)/b_res:+.1f}% Brier")
print("In a world where finishing luck adds noise (like real football),")
print("the xG blend sees through variance and forecasts better.")

# blend sweep to find the sweet spot
print("\nBlend sweep (Brier, lower better):")
for bl in [0.0,0.25,0.5,0.65,0.8,1.0]:
    b=evaluate(DualRatingModel(base=1500,k=24,k_xg=22,home_adv=55,blend=bl), f"  blend={bl:.2f}")

print("""
NOTE — why 100% xG 'wins' here but won't on real data:
This synthetic world makes finishing 100% random noise, so xG IS ground truth
and more xG weight is always better. Real teams have SOME repeatable finishing
skill, so the empirically-best blend on real data is usually ~0.6-0.7, not 1.0.
Tune `blend` by backtesting on YOUR data — that's the whole point of Layer 5.
""")
