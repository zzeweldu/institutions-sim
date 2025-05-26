from sim_config import CFG
from war import War, CivilWar
import random

class Military:
    def __init__(self, state, mass_fraction=.8, training_delay=2):
        self.state = state
        self.mass_fraction = mass_fraction
        self.training_delay = training_delay
        self.training_queue = []       # (months left, n)
        self.ready_conscripts = 0
        self.base_ratio = 0.003        # starts ~0.3 % professionals
        self.core_mass = self.core_elite = 0
        self.loyalty = 1.0
        self.recompute()

    # ――― hiring / retiring core soldiers ―――
    def _adjust_core(self):
        pop_now = self.state.pop
        desired_ratio = max(CFG["min_ratio"], min(self.base_ratio, CFG["max_ratio"]))
        target_core = desired_ratio * pop_now
        gap = target_core - (self.core_mass + self.core_elite)
        delta = max(-CFG["hire_limit"]*pop_now, min(CFG["hire_limit"]*pop_now, gap))
        self.core_mass  += delta * self.mass_fraction
        self.core_elite += delta * (1-self.mass_fraction)

    def update_professional(self):
        self._adjust_core()

    # ――― training pipeline ―――
    def process_training(self):
        nxt=[]
        for m,n in self.training_queue:
            if m<=1:
                self.ready_conscripts += n
            else:
                nxt.append((m-1,n))
        self.training_queue = nxt

    def draft(self, n):
        n=int(n)
        if n<=0 or n>self.state.mass_pop: return
        self.state.mass_pop -= n
        self.training_queue.append((self.training_delay, n))
        print(f"    Drafted {n:,.0f} civilians → training")

        base_penalty = (20 * n) / (self.state.mass_pop + self.state.elite_pop + 1e-9)

        # Multiplier based on state condition
        if isinstance(self.state.war, CivilWar):
            mult = 3.0  # Draftees may sympathize with rebels
        elif self.state.war:
            mult = 0.5  # War increases urgency, but still unpopular
        else:
            mult = 1.5  # Drafting in peacetime is very unpopular

        unrest_increase = base_penalty * mult
        self.state.unrest = min(1.0, self.state.unrest + unrest_increase)

        print(f"    🧨 Unrest increased by {unrest_increase:.3f} due to draft")

    def demobilise(self):
        back = self.ready_conscripts + sum(n for _,n in self.training_queue)
        self.state.mass_pop += back
        self.ready_conscripts = 0
        self.training_queue.clear()
        print(f"    Demobilised {back:,.0f} conscripts")

    # ――― combat power & loyalty ―――
    def recompute(self):
        self.update_professional(); self.process_training()
        self.mass_members  = self.core_mass + self.ready_conscripts
        self.elite_members = self.core_elite
        tot = self.mass_members + self.elite_members
        ei,sec = self.state.EI, self.state.sec
        baseL = (ei*self.mass_members + (1-ei)*self.elite_members)/(tot+1e-9)
        self.loyalty = max(0, min(1, baseL + 0.2*(sec-1)))

    def strength(self):
        manpower = self.mass_members + 2*self.elite_members
        return manpower * (1 + CFG["equip_weight"]*(self.state.sec-1))

    def coup_check(self):
      # Coup *attempt* happens with probability proportional to disloyalty
      success_chance = 0.25 + 0.5 * (1 - self.loyalty)
      attempt_chance = success_chance * CFG["coup_probability"]
      if random.random() < attempt_chance:
          # Success depends on remaining loyalty
          success_chance = 0.25 + 0.5 * (1 - self.loyalty)  # e.g. 25–75% range
          if random.random() < success_chance:
              print("\n⚔️ Coup SUCCESS → EI & PI regress")
              self.state.log(f"⚠️ Coup attempt SUCCESS - institutions regress")
              
              purge_factor = (self.loyalty) * 0.2  # up to 20% of core lost if very loyal
              lost_mass = self.core_mass * purge_factor
              lost_elite = self.core_elite * purge_factor
              lost_con = self.ready_conscripts * purge_factor * 0.2
              
              self.state.EI = max(0, self.state.EI - 0.4)
              self.state.PI = max(0, self.state.PI - 0.4)
              self.state.unrest += (self.loyalty * 0.3)
          else:
              print("\n⚔️  Coup FAILED → Crackdown")
              self.state.log(f"🛡️ Coup attempt FAILED – crackdown and purge")
              self.state.sec *= 1.05
              purge_factor = (1.01 - self.loyalty) * 0.2  # up to 20% of core lost if very disloyal
              lost_mass = self.core_mass * purge_factor
              lost_elite = self.core_elite * purge_factor
              lost_con = self.ready_conscripts * purge_factor * 0.2

              self.core_mass = max(0, self.core_mass - lost_mass)
              self.core_elite = max(0, self.core_elite - lost_elite)
              self.ready_conscripts = max(0, self.ready_conscripts - lost_con)


              print(f"    👤 Purged {lost_mass + lost_elite + lost_con:,.0f} soldiers")
              self.state.sec *= 1.05



    def monthly(self):
      # Adjust base_ratio depending on war performance
      if self.state.war:
          # boost target ratio depending on how bad the war is going
          # front near 0 → heavy losses, raise base_ratio
          # front near 1 → winning, no urgent change
          front_line = getattr(self.state.war, "front", 0.5)
          pressure = max(0, 0.5 - front_line)  # only increase if losing
          adjustment = 0.004 * pressure  # scale max boost to +0.002 at front=0
          self.base_ratio = min(CFG["max_ratio"], self.base_ratio + adjustment)

      else:
          # If peacetime, gradually revert base_ratio to default
          default = 0.003
          self.base_ratio += 0.001 * (default - self.base_ratio)

      self.recompute()

