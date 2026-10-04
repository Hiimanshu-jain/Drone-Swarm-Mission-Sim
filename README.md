# Mission Contracts: a mission-level orchestration simulator

**Team IRYS Iris · ELEVATE 1.0 · PS ID EL05**
*AI-Powered Autonomous Robot & Drone Swarm Mission Orchestration*

A small Python simulator used to test the ideas in our ELEVATE 1.0 submission. It compares how a heterogeneous robot and drone team handles mid-mission disruptions under different planning strategies, and it reproduces the numbers quoted in our slides.

> **Scope, stated plainly.** This is a simplified research simulator, not field data and not a ROS / Gazebo / PX4 integration. Agent speeds, energy budgets, task values and the disruption model are our own assumptions (listed below). Results show how the strategies compare *inside this model*.

> **Note on the slide figures.** Three figures on the submitted slides come from an earlier run of this simulator: **+14%** value vs a static plan, **35%** fewer task changes, and **6.7 s** single-planner time at 192 agents. The final code in this repository gives **+17.0%**, **36.7%** and about **4.3 s** (planning time varies by machine). All other slide figures (0.87 reviews / 97% of value at stake, about 1 ms per team, the ledger values, the hedging null result) reproduce exactly. The conclusions are unchanged. **Where the slides and this repository differ, this repository (the code and its printed output) is the reference.**

---

## The idea in one paragraph

Every plan is a **contract**: each task declares the assumptions it depends on (route open, link up, battery above reserve), and monitors watch them. When an assumption breaks, only its **blast radius** (the tasks that depend on it) is re-planned, using a six-rung Repair Ladder (local fix → neighbour swap → partial re-auction → global replan → descope → safe abort). A **counterfactual ledger** prices every decision as *value with the repair minus value without it*, and **stake-gated escalation** asks a human only when that value at stake is high. An LLM would only translate goals into a validated mission spec while deterministic gates decide what executes; that LLM layer is a design element and is **not simulated here**.

## What is simulated

| Item | Model |
|---|---|
| Agents (6) | Scout drone (speed 6, 60 min energy, survey) · Inspection drone (5, 45, inspect + survey) · Relay drone (5, 50, no tasks; comms-recovery role) · Heavy-lift drone (4, 40, deliver) · UGV-1 (2, 90, clear + inspect) · UGV-2 (2, 90, survey + deliver) |
| Tasks (22 per mission) | 8 survey, 4 inspect, 5 deliver, 5 clear. Random position in a 100 × 60 area, duration 2–5 min, value 5–10, deadline 30–60 min |
| Initial plan | Sequential greedy allocation by value per unit time (CBBA-style), subject to capability, deadline and energy-to-return constraints |
| Disruptions (4 per mission, random times 5–25 min) | **Route block** (agent delayed 6 min) · **Comms loss** (agent unreachable 12 min, or 3 min when relay-assisted) · **Low battery** (energy capped at 8 min) · **New priority task** (value 30, deadline +18 min) |
| Strategies | `static` (never replans) · `global` (replans everything, comms-blind) · `nocomms` (Ladder, not comms-aware) · `noladder` (global replan, comms-aware) · `ours` (Ladder + comms-aware; escalates to a global replan only when a local repair cannot place a task) |

Relay assistance is modelled only as a shorter comms outage. This is a simplification, and comms-awareness showed no statistically meaningful benefit in this model.

## Metrics

- **Value**: sum of rewards of tasks completed before their deadline. *Value vs static* is normalised by the static strategy's mean on the same missions.
- **Churn**: tasks moved to a different agent, per disruption event.
- **Ledger impact**: final mission value with every response, minus final value with that single response skipped.
- **Stake gate** (threshold θ): escalate a decision to a human when |impact| ≥ θ × mission value. *Coverage* = share of total |impact| contained in the escalated decisions.
- **Planning time**: wall-clock time of a greedy allocation of 4A tasks to A agents (NumPy), versus a single 6-agent team. Hierarchical teams are assumed to run in parallel, so the per-team time is reported.

## Run it

```bash
pip install numpy
python Swarm_Mission_Sim.py     # simulator, ablations, ledger, scaling  -> writes results.json
python stake_gate.py            # stake-gated escalation analysis        -> adds "stake" to results.json
```

Takes a few minutes. Randomness is seeded, so value, churn, ledger and stake-gate numbers are deterministic; planning times depend on your machine.

## Results from our final run

200 randomised missions, 4 disruptions each. Error is the 95% interval.

| Strategy | Value vs static plan | Churn (tasks moved per event) |
|---|---|---|
| Static plan | 100.0 ± 1.4 | 0.00 |
| Global replan (comms-blind) | 115.1 ± 2.3 | 0.49 |
| Ladder, not comms-aware | 115.8 ± 2.4 | 0.35 |
| Global replan, comms-aware | 112.9 ± 2.3 | 0.58 |
| **Ours: Ladder + comms-aware** | **117.0 ± 2.4** | **0.36** |

Other results:

- **Ledger (seed 5):** priority-task insertion +30.0 (22.7% of mission value); low-battery re-auction +1.4; route block and link loss 0.0 (no action needed).
- **Stake gate:** at a 5% threshold, 0.87 human reviews per mission (versus 4 disruption events) cover 97% of the value at stake. At 10%: 0.67 reviews / 88%. At 20%: 0.29 reviews / 46%.
- **Planning time (ms), agents → single global planner / one 6-agent team:** 6 → 1/1 · 12 → 2/0 · 24 → 9/1 · 48 → 70/0 · 96 → 533/1 · 192 → 4290/1.
- **Hedged allocation (n = 120):** 104.4 → 105.3, difference not significant (95% interval ± 1.8).

## How to read the results (including what did not work)

- **Adaptive replanning beats a static plan** (+13% to +17% value). This is the expected result.
- **Ladder vs global replan.** Value is statistically equal (differences are within the error bars). The Ladder moves **36.7% fewer tasks** than the comms-aware global replan (0.36 vs 0.58 per event), the comparison that isolates the blast-radius effect, and 25.9% fewer than the comms-blind global replan (0.49). Its practical advantages are plan stability and scaling.
- **Scaling.** A single global planner's time grows rapidly with fleet size (about 4.3 s at 192 agents on our machine), while a 6-agent team stays near 1 ms.
- **Negative result.** Hedging the initial allocation against tail risk (choosing among candidate plans by worst-quartile outcome over sampled disruptions) gave **no significant gain**. We do not claim it.
- **Not measured.** The benefit of comms-as-a-resource planning, the value-of-information data policy, mission non-viability detection, and LLM mission parsing are design elements only.

## Known limitations

- Simplified kinematics (straight-line travel; no terrain, collision or separation modelling).
- Commit-at-start execution: a task that has started always completes.
- Only 4 disruption types, 4 per mission, at random times.
- Parameters are ours, not calibrated to real vehicles.
- Next steps: Gazebo / AirSim / PX4 SITL integration, fault injection and stress tests, then hardware-in-the-loop.

## Repository contents

| File | Purpose |
|---|---|
| `Swarm_Mission_Sim.py` | Simulator, strategies, ablations, hedging test, ledger and scaling benchmark |
| `stake_gate.py` | Stake-gated escalation analysis (adds results to `results.json`) |
| `results.json` | Output of the final run of both scripts |
| `README.md` | This file |

## Selected references

Gerkey & Matarić (2004), task-allocation taxonomy, *IJRR*. Korsah, Stentz & Dias (2013), MRTA taxonomy, *IJRR*. Choi, Brunet & How (2009), CBBA, *IEEE T-RO*. Erol, Hendler & Nau (1994), HTN planning, *AAAI*. Nau et al. (2003), SHOP2, *JAIR*. Colledanchise & Ögren (2018), *Behavior Trees in Robotics and AI*. LLM multi-robot planning: SMART-LLM (arXiv:2309.10062), COHERENT (arXiv:2409.15146), CoMuRoS (arXiv:2511.22354). Calibrated escalation: KnowNo (Ren et al., CoRL 2023). Full list in the submission deck.

