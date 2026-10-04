"""Stake-gated escalation analysis (companion to Swarm_Mission_Sim.py).
Reproduces: 'N human reviews per mission cover X% of the value at stake'.
Usage: python Swarm_Mission_Sim.py   (writes results.json)  then  python stake_gate.py   (adds a 'stake' entry to results.json)
"""
import json, random, statistics as st
import Swarm_Mission_Sim as sim

N = 150   # missions (seeds 0..149)
rows = []
for sd in range(N):
    rng = random.Random(sd)
    ag, ts, ev = sim.mk(rng); sim.alloc(ts, ag)
    v = sim.execute('ours', ag, ts, ev)[0]                                       # value with every response
    impact = [v - sim.run('ours', sd, skip=(k,))[0] for k in range(4)]            # counterfactual impact of each response
    rows.append((v, impact))

stake = {}
for th in (0.05, 0.10, 0.20):                                                     # escalate if |impact| >= th * mission value
    esc = [sum(1 for x in imp if abs(x) >= th * v) for v, imp in rows]
    tot = sum(abs(x) for v, imp in rows for x in imp)
    cov = sum(abs(x) for v, imp in rows for x in imp if abs(x) >= th * v)
    stake[str(th)] = dict(reviews_per_mission=st.mean(esc), value_at_stake_covered_pct=100 * cov / tot, events_per_mission=4)
    print(f"Stake gate {th:.0%}: {st.mean(esc):.2f} reviews/mission (of 4 events) cover {100*cov/tot:.0f}% of value at stake")

try:
    J = json.load(open('results.json'))
except FileNotFoundError:
    J = {}
J['stake'] = stake
json.dump(J, open('results.json', 'w'), default=float, indent=1)
