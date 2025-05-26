from __future__ import annotations
import matplotlib.pyplot as plt
import math, random, time, sys
from typing import Dict, List, Optional, Callable
from sim_config import CFG
from war import War, CivilWar
from military import Military



def _now(month: int) -> str:
    """M12 → 'M012' so lexical order = chronological order."""
    return f"M{month:03d}"

# ─────────────────── UTILITY ───────────────────────
_now = lambda m: f"M{m:03d}"

# ────────────────── LEARNING AGENT ─────────────────

class HeuristicAllocator:
    """Baseline weights from conditions  +  small random jitter each month."""
    LINES = ("tech", "infra", "pc", "sec", "welfare")

    def __init__(self, jitter: float = 0.03):
        self.jitter = jitter

    def __call__(self, st:'State') -> Dict[str, float]:
        # ------- deterministic part -------
        w = dict.fromkeys(self.LINES, 0.0)
        econ_ok   = st.unrest < 0.35
        war_time  = st.war is not None
        high_u    = st.unrest > 0.6

        base = 0.10                               
        w["tech"]    = base + (0.25 if econ_ok else 0.10)
        w["infra"]   = base + (0.25 if econ_ok else 0.10)
        w["pc"]      = base + (0.15 if econ_ok else 0.05)
        w["sec"]     = base + (0.25 if (war_time or high_u) else 0.10)
        w["welfare"] = base + (0.25 if high_u else 0.05)

        # ------- add jitter & renormalise -------
        for k in w:
            w[k] = max(CFG["alloc_floor"],
                       w[k] + random.uniform(-self.jitter, self.jitter))
        s = sum(w.values())
        return {k: v / s for k, v in w.items()}
            
class State:
    def __init__(self, name, pop, tech, elite_share=0.08, EI=0.1, PI=0.1, out_scale=100, max_step=0.1):
        self.name=name; self.month=0; self.max_step=max_step
        self.mass_pop=pop*(1-elite_share); self.elite_pop=pop*elite_share
        self.tech=tech; self.infra=self.pc=self.sec=pop
        self.base_infra = self.infra
        self.EI=EI; self.PI=PI; self.scale=out_scale; self.budget=0
        self.unrest=0
        self.mil=Military(self)
        self.war=None; self.last_vote=0
        self.protest = False
        self.protest_duration = 0
        
        #LEarning Allocator
        self.alloc = HeuristicAllocator()
        
        # ── time‑series tracking ──
        self.trend = {"EI": [], "PI": [], "Y": [], "infra": []}
        self.events: List[str] = []

    @property
    def pop(self): return self.mass_pop + self.elite_pop
    
    def log(self, msg: str):
        self.events.append(f"{_now(self.month)}  {msg}")
    
    def _alloc_split(self):
        t   = CFG["targets"]
        w = {
            "tech" : max(0, (t["tech"]  - self.tech)  / t["tech"]),
            "infra": max(0, (t["infra"] - self.infra) / t["infra"]),
            "pc"   : max(0, (t["pc"]    - self.pc)    / t["pc"]),
            "sec"  : max(0, 1 - self.sec),
        }

        # contextual boosts
        if self.war:            w["sec"]  += 0.6
        if self.unrest > 0.4:   w["sec"]  += 0.4 * self.unrest
        war_dmg = 1 - self.infra / max(1e-6, self.tech + self.pc)
        w["infra"] += 0.3 * war_dmg
        if self.EI < 0.4:       w["pc"]   += 0.5

        # normalise + set floors
        tot = sum(w.values())
        for k in w:
            w[k] = max(CFG["alloc_floor"], w[k] / (tot + 1e-9))
        # re-normalise so they sum to 1 exactly
        s = sum(w.values())
        return {k: v / s for k, v in w.items()}

    def raw_out(self):
        ε = 0.2
        fac = min(self.tech, self.pc) + ε * max(self.tech, self.pc)
        output = self.tech * (((self.mass_pop * self.EI) + self.elite_pop)**0.67) * ((self.pc +self.infra)**0.33)
        if self.unrest > 0.4:
            output *= 1 - CFG["unrest_output_penalty"]
        if self.war:
            output *= 1 - self.war.front
        return output

    def invade_prob(self):
        r = (self.mil.mass_members + self.mil.elite_members)/self.pop
        risk = CFG["base_invade"] + CFG["invade_k"] * max(0, CFG["safe_ratio"]-r)
        return max(0.002, min(1, risk))

    def adjust_prof_ratio(self):
        risk=self.invade_prob()
        target=CFG["min_ratio"] + (CFG["max_ratio"]-CFG["min_ratio"])*(risk/0.5)
        target=min(CFG["max_ratio"], max(CFG["min_ratio"], target))
        cur=self.mil.base_ratio
        rate=CFG["inertia_expand"] if target>cur else CFG["inertia_contract"]
        self.mil.base_ratio += rate*(target-cur)
        self.mil.base_ratio = max(CFG["min_ratio"], min(CFG["max_ratio"], self.mil.base_ratio))
        self.mil.update_professional()

    def update_unrest(self, avg_mass_income, avg_elite_income, repression_spending):
        grievance = (
        (1 - self.EI) +
        (1 - self.PI) +
        (1 - self.sec) +
        max(0, (avg_elite_income - avg_mass_income) / (avg_mass_income + 1e-9))
    ) / 4
        
        delta = grievance - self.unrest
        adjustment = CFG["unrest_adjust"] * delta * abs(delta)
        self.unrest += adjustment
        self.unrest = max(0, min(1, self.unrest))


        # PROTEST STATE TRIGGER
        if not self.protest and self.unrest > 0.4 and random.random() < CFG["protest_base"] * (self.unrest):
            print("\n🪧 Protests erupt! Masses take to the streets.")
            self.log("🪧Protest movement begins")
            self.protest = True
            self.protest_duration = 0

        # ONGOING PROTEST EFFECTS
        if self.protest:
            self.protest_duration += 1
            self.infra *= 0.995  # infrastructure erosion
            self.unrest = min(1, self.unrest  + 0.001)  # agitation builds

            print(f"\n🚨 Protest ongoing ({self.protest_duration} months)")

            if self.unrest > 0.7 and random.random()<0.1: action="concede"
            else: action="repress"

            if action == "repress":
                print("repressing")
                if random.random() < 0.1 + 0.2 * repression_spending / (self.mass_pop + 1):
                    print("🔨 Protest crushed by force.")
                    self.log("🔨Protest suppressed")
                    self.protest = False
                    self.unrest = min(1, self.unrest + 0.1)  # backlash
                elif random.random() < (0.05 * self.protest_duration) * self.unrest:
                    print("🔥 Repression backfires → Civil war!")
                    self.log("🔥 Protest repression backfires")
                    self.war = CivilWar(self)
                    self.protest = False
                    self.unrest = max(0, self.unrest - 0.5)

            elif action == "concede":
                print("🫱 Government concedes to demands.")
                self.log("🫱 Govt concedes to protestors")
                self.EI = min(1.0, self.EI + 0.05)
                self.PI = min(1.0, self.PI + 0.05)
                self.protest = False
                self.unrest = max(0, self.unrest - 0.3)

    def _maybe_draft(self) -> None:
        """
        Decide whether to call up additional conscripts.

        Logic
        -----
        • Baseline desire ∝ invasion-risk  (same as before).  
        • Multiplied by (1 + κ) if a war is in progress,
        where κ = max(0, 0.6 − front) / 0.6   ∈ [0,1].
        – front = 1   => κ = 0   (we are winning, no extra pressure)  
        – front = 0.5 => κ = 0.17  
        – front = 0   => κ = 1   (total retreat, double the draft desire)
        • Still scaled down as EI rises.
        """
        #––– should we even consider drafting? –––––––––––––––––––––––––––––
        if not self.war and self.invade_prob() <= 0.02:
            return

        # baseline factor driven by external threat
        base_fraction = self.invade_prob() * 0.05          # unchanged

        # extra pressure if an *ongoing* war is going badly
        pressure = 0.0
        if self.war:
            # front ∈ [0,1]  (0 = enemy at gates, 1 = victory)
            pressure = max(0.0, 0.6 - self.war.front) / 0.6   # linear ramp 0→1

        # combine components
        draft_fraction = base_fraction * (1 + pressure) * (1.2 - self.EI)

        desired = draft_fraction * self.pop
        shortfall = desired - self.mil.ready_conscripts

        if shortfall > 0:
            self.mil.draft(shortfall)
              
    def _maybe_disaster(self):
        p = (
            CFG["disaster_base"]
            + CFG["disaster_infra_coeff"]
            + CFG["disaster_unrest_coeff"] * self.unrest
        )
        if random.random() >= p:
            return                    # no event this month
        print(p)
        severity = random.gammavariate(2, 0.04)    # mean ≈0.08

        # Damage & casualties
        self.infra *= max(0, 1 - severity)
        mass_kill  = self.mass_pop  * 0.03 * severity
        elite_kill = self.elite_pop * 0.01 * severity
        self.mass_pop  = max(0, self.mass_pop  - mass_kill)
        self.elite_pop = max(0, self.elite_pop - elite_kill)
        self.sec  *= max(0.1, 1 - 0.4*severity)
        
        print(f"\n🌪️ Natural disaster! Severity {severity*100:.1f}%")
        self.log(f"🌪️ Natural disaster of {severity*100:.1f}% severity, {mass_kill+elite_kill:,.0f} dead")

        # Discontent shock
        shock = 0.5 * severity
        self.unrest = min(1.0, self.unrest + shock)

        print(f"   • {mass_kill+elite_kill:,.0f} dead, infra now {self.infra:.2f}, unrest +{shock:.2f}")


    def month_step(self):
        self.month+=1
        self._maybe_disaster()
        self.mass_pop*=1+CFG["mass_growth"]
        self.elite_pop*=1+CFG["elite_growth"]
        self.infra*=1-CFG["infra_decay"]
        self.sec*=1-CFG["sec_decay"]

        gross=self.scale*self.raw_out()
        tax=gross*CFG["tax_rate"]
        net_income = gross - tax
        per_capita_income = net_income / (self.mass_pop + self.elite_pop + 1e-9)
        self.budget+=tax

        self.adjust_prof_ratio()
        num_pros = self.mil.core_mass + self.mil.core_elite
        num_cons = self.mil.ready_conscripts
        soldier_cost = CFG["soldier_cost"] * per_capita_income
        conscript_cost = CFG["conscript_cost"] * per_capita_income
        payroll = soldier_cost * num_pros + conscript_cost * num_cons
        self.budget=max(0, self.budget-payroll)

        split = self.alloc(self)
        invest = self.budget; self.budget = 0.0
            
        repression_spending = (invest*split["sec"]) * CFG["repression_cost_fraction"]
        self.tech*=1+0.0003*math.log1p(invest*split["tech"])
        self.infra*=1+0.001*math.log1p(invest*split["infra"])
        self.pc*=1+0.001*math.log1p(invest*split["pc"])
        security_invest = invest*split["sec"] - repression_spending
        self.sec *= 1 + 0.001*math.log1p(max(0, security_invest))
        
        welfare_spend = invest * split["welfare"]
        mass_share = 0.5 + 0.5 * (1 - self.EI)  # 1.0 at EI=0  → all to masses; 0.5 at EI=1
        mass_transfer   = welfare_spend * mass_share
        elite_transfer  = welfare_spend - mass_transfer

        avg_mass_income  = (net_income * self.EI) / self.mass_pop + mass_transfer / max(1, self.mass_pop)
        avg_elite_income = (net_income * (1 - self.EI)) / self.elite_pop + elite_transfer / max(1, self.elite_pop)


        avg_mass_income = (gross-tax)*self.EI/self.mass_pop
        avg_elite_income = (gross-tax)*(1-self.EI)/self.elite_pop

        self.update_unrest(avg_mass_income, avg_elite_income, repression_spending)

        if self.month - self.last_vote >= CFG["vote_interval"]:
          mass_vote_power = self.mass_pop * (self.PI ** 2)
          elite_vote_power = self.elite_pop
          total = mass_vote_power + elite_vote_power
          diff = (mass_vote_power - elite_vote_power) / (total + 1e-9)

          # Reform probability for EI — responsive
          ei_reform_prob = 0.5 + 0.5 * diff
          ei_reform_prob = max(0.1, min(0.9, ei_reform_prob))

          # Reform probability for PI — dampened
          pi_reform_prob = 0.5 + 0.3 * diff  #40% less responsive
          pi_reform_prob = max(0.2, min(0.8, pi_reform_prob))  #slightly narrower band

          if random.random() < ei_reform_prob:
              self.EI = min(1.0, self.EI + self.max_step)
          elif random.random() > 1 - ei_reform_prob:
              self.EI = max(0.0, self.EI - self.max_step)

          if random.random() < pi_reform_prob:
              self.PI = min(1.0, self.PI + self.max_step)
          elif random.random() > 1 - pi_reform_prob:
              self.PI = max(0.0, self.PI - self.max_step)

          self.last_vote = self.month
          
        self.trend["EI"].append(self.EI)
        self.trend["PI"].append(self.PI)
        self.trend["Y"].append(gross)
        self.trend["infra"].append(self.infra/self.base_infra)

        self.mil.recompute()
        self.mil.coup_check()
        self._maybe_draft()

        if not self.war and random.random()<self.invade_prob():
            print("\n🔥 External invasion! WAR begins.")
            self.log("🔥 External war started")
            self.war=War(self)
        if self.war:
            self.war.month(sp=invest*split["sec"])


        warflag=""
        if self.war:
            f=int(self.war.front*20)
            shields = "=" * f
            swords = "-" * (20 - f)
            warflag = f"(WAR {self.war.front:.2f}) [{shields}{swords}]"

        unrest_bar = "✊"*int(self.unrest*20) + "-"*(20-int(self.unrest*20))
        army_tot=self.mil.mass_members+self.mil.elite_members
        abar=min(20,int((army_tot/self.pop)*400))

        print(f"=== 🗕️ Month {self.month} — {self.name} {warflag} ===")
        print(f"😠 Discontent : {self.unrest*100:4.1f}% [{unrest_bar}]")
        print(f"🧑‍♂️ Pop   : Mass {self.mass_pop:>10,.0f} | Elite {self.elite_pop:>9,.0f}")
        print(f"💰 Econ  : {gross:>12,.2f} | Tax {tax:>9,.2f} | Pay {payroll:>9,.2f}")
        print(f"🏛️ Inst. : Economic {self.EI:.2f} | Political {self.PI:.2f}")
        print(f"📈 Cap   : Tech {self.tech:,.2f} | Infra {self.infra:,.2f} | PC {self.pc:,.2f} | Sec {self.sec:,.2f}")
        print(f"🧾 Budget breakdown (after tax {tax:,.2f}):")

        print(f"   • Tech        : {invest*split['tech']:>9,.2f}")
        print(f"   • Infrastructure: {invest*split['infra']:>9,.2f}")
        print(f"   • Production Capital : {invest*split['pc']:>9,.2f}")
        print(f"   • Security     : {invest*split['sec']:>9,.2f} (incl. {repression_spending:,.2f} on repression)")
        print(f"   • Military        : {payroll:>9,.2f}")
        print(f"   • Welfare        : {welfare_spend:>9,.2f}")

        print(f"🪰‼️ Army  : {army_tot:>9,.0f} (Core {self.mil.core_mass+self.mil.core_elite:,.0f} | Con {self.mil.ready_conscripts:,.0f})")
        print(f"         Ratio {self.mil.base_ratio*100:5.2f}% | ❤️ Loyalty {self.mil.loyalty:.2f}")
        print("==================================")
        time.sleep(CFG["sleep"])
    
    def plot_history(self):
        months = range(1, len(self.trend["EI"]) + 1)
        plt.figure(figsize=(8, 5))
        plt.plot(months, self.trend["EI"], label="Economic Inst. (EI)")
        plt.plot(months, self.trend["PI"], label="Political Inst. (PI)")
        y_scaled = [y / max(self.trend["Y"], default=1) for y in self.trend["Y"]]
        plt.plot(months, y_scaled, label="Output (scaled)")
        plt.xlabel("Month")
        plt.title(f"Trajectory of {self.name}")
        plt.legend()
        plt.tight_layout()
        plt.show()



import argparse, textwrap, json, sys

def positive_float(x):
    try:
        x = float(x)
        assert x > 0
        return x
    except Exception:
        raise argparse.ArgumentTypeError(f"{x} must be a positive number")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python .py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            Run a single-state institutional simulation.

            EXAMPLES
            --------
            # default 120-month run
            python sim.py --name Solaria --pop 5e6 --tech 1.2 --months 120

            # faster loop, autocratic start, no UI sleep
            python sim.py -n Rexia -p 8e6 -t 0.8 --ei 0.3 --pi 0.2 -m 240 --nosleep
        """)
    )

    p.add_argument("--name",  "-n", default="Solaria",
                   help="state name (str)")
    p.add_argument("--pop",   "-p", default=5_000_000, type=positive_float,
                   help="initial population (float, people)")
    p.add_argument("--tech",  "-t", default=1.0,        type=positive_float,
                   help="starting technology index")
    p.add_argument("--elite-share", default=0.08, type=float,
                   help="share of elites in population (0-1)")
    p.add_argument("--ei", default=0.5, type=float,
                   help="initial economic-institution score (0-1)")
    p.add_argument("--pi", default=0.5, type=float,
                   help="initial political-institution score (0-1)")
    p.add_argument("--months", "-m", default=120, type=int,
                   help="simulation length in months")
    p.add_argument("--max-step", default=0.1, type=float,
                   help="max institutional change per vote (0-1)")
    p.add_argument("--nosleep", action="store_true",
                   help="skip UI sleep for faster headless runs")
    p.add_argument("--seed", type=int,
                   help="set RNG seed for reproducibility")

    # optional adhoc CFG overrides:  --cfg '{\"tax_rate\":0.15,\"sleep\":0}'
    p.add_argument("--cfg", type=str,
                   help="JSON dict with CFG overrides")

    return p


def run_from_cli():
    parser = build_parser()
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.cfg:
        try:
            overrides = json.loads(args.cfg)
            CFG.update(overrides)
        except Exception as e:
            sys.exit(f"Bad --cfg JSON: {e}")

    if args.nosleep:
        CFG["sleep"] = 0

    state = State(
        args.name,
        pop=float(args.pop),
        tech=args.tech,
        elite_share=args.elite_share,
        EI=args.ei,
        PI=args.pi,
        max_step=args.max_step,
    )

    for _ in range(args.months):
        state.month_step()
    state.plot_history()


# ───────── Main ─────────
if __name__ == "__main__":
    run_from_cli()
