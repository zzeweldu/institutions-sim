import random, math
from sim_config import CFG

# ────────── War class ──────────
class War:
    def __init__(self, state):
        self.s = state
        self.front = 0.5
        self.months = 0
        
        self.reinforce_rate = 0.02
        variance = random.uniform(CFG["min_enemy_strength"], CFG["max_enemy_strength"])  # introduces randomness: from easy to strong
        self.enemy_str = self.s.mil.strength() * variance
        # track cumulative losses for summary
        self.civ_loss = 0.0
        self.cons_loss = 0.0
        self.pro_loss  = 0.0


    def _label(self, score):
        return "Defence wins" if score < 0 else "Offence wins"

    def _act(self, bias):
        # return (action, bonus)
        p_att = min(1, max(0, 0.3 + 0.3*bias))			
        p_ret = min(1, max(0, 0.3 - 0.3*bias))
        r = random.random()
        if r < p_att:
            return ("attack", 0.3)
        if r > 1 - p_ret:
            return ("retreat", -0.3)
        return ("hold", 0.0)

    def battle(self, sec_sp):
        self.months += 1
        ours, enemy = self.s.mil.strength(), self.enemy_str
        bias = (ours - enemy) / (enemy + 1e-9)
        a, a_bonus = self._act(bias)
        e, e_bonus = self._act(-bias)

        score = 0.4 * math.tanh(bias) + a_bonus - e_bonus + random.gauss(0, 0.25)
        qual = "decisive" if abs(score) > 0.9 else "pyrrhic" if abs(score) < 0.2 else "regular"
        shift_base = {"pyrrhic": 0.01, "regular": 0.03, "decisive": 0.07}[qual]
        shift = shift_base * (1 if score > 0 else -1)
        if a == "retreat":
            shift = -abs(shift) * 1.4
        if e == "retreat":
            shift = abs(shift) * 1.4
        if a == "hold" and e == "hold":
          shift = 0.0
          qual = "stalemate"
        self.front = max(0, min(1, self.front + shift))

        # casualty rate scales with how deep the fight is inside territory (loc)
        loc = 1 - self.front
        rate = 0.003 * (1.5 if qual == "decisive" else 0.7 if qual == "pyrrhic" else 0.2 if qual == "stalemate" else 1)
        rate *= random.uniform(0.8, 1.2)

        # calculate losses
        civ_mass_loss = self.s.mass_pop * rate * 0.01 * loc
        civ_elite_loss = self.s.elite_pop * rate * 0.005 * loc
        cons_loss = min(self.s.mil.ready_conscripts, rate * 1.3 * self.s.mil.ready_conscripts)
        pro_m_loss = min(self.s.mil.core_mass, rate * 0.9 * self.s.mil.core_mass)
        pro_e_loss = min(self.s.mil.core_elite, rate * 0.9 * self.s.mil.core_elite)

        # apply losses & accumulate
        self.s.mass_pop -= civ_mass_loss
        self.s.elite_pop -= civ_elite_loss
        self.s.mil.ready_conscripts -= cons_loss
        self.s.mil.core_mass -= pro_m_loss
        self.s.mil.core_elite -= pro_e_loss
        self.s.mil.recompute()

        self.civ_loss += civ_mass_loss + civ_elite_loss
        self.cons_loss += cons_loss
        self.pro_loss += pro_m_loss + pro_e_loss
        
        self.enemy_str += self.reinforce_rate * self.enemy_str
        
        # degrade security harder as war drags on
        self.s.sec = max(0.1, self.s.sec * (1 - 0.01 * loc))
        self.s.sec = max(0.1, self.s.sec * 0.98 + 0.000002 * sec_sp)

        # print round summary
        bar = "=" * int(self.front * 20) + "-" * (20 - int(self.front * 20))
        print(
            f"    ROUND {self.months:02d} | our {a:<7} vs enemy {e:<7} | {qual.capitalize():<8} | {self._label(score)}"
        )
        print(f"             front [{bar}] {self.front:.2f}")
        self.s.log(f"{self.s.name} [{bar}] Enemy")        
        print(
            f"             civ loss {civ_mass_loss + civ_elite_loss:>8,.0f} | cons {cons_loss:>7,.0f} | pros {pro_m_loss + pro_e_loss:>7,.0f}"
        )

    def _peace_desc(self):
        f = self.front
        if f >= 0.8:
            return "very favourable"
        if f >= 0.6:
            return "favourable"
        if f <= 0.2:
            return "very unfavourable"
        if f <= 0.4:
            return "unfavourable"
        return "even"

    def resolve(self):
        ended = False
        if self.front <= 0:
            print("🏳️  Total defeat. Occupied.")
            self.s.unrest  = min(1, self.s.unrest + 0.15)
            self.s.mil.loyalty = max(0, self.s.mil.loyalty - 0.15)
            print("• unrest +15 pp, army loyalty –15 pp")
            ended = True
        elif self.front >= 1:
            bonus = 0.05
            print("🏆  Total victory!")
            self.s.tech   *= 1 + bonus
            self.s.infra  *= 1 + bonus
            self.s.pc     *= 1 + bonus
            self.s.unrest = max(0, self.s.unrest - 0.10)
            print("• tech/infra/pc +5 %, unrest –10 pp")
            ended = True
        elif random.random() < 0.01 + 0.002 * self.months + 0.03 * max(0, self.front - 0.5):
            print(f"🕊️  Peace treaty signed ({self._peace_desc()}).")
            ended = True

        if ended:
            self.s.mil.demobilise()
            print(
                f"=== WAR ENDS after {self.months} months ===\n"
                f"   • Civilian dead : {self.civ_loss:,.0f}\n"
                f"   • Conscripts KIA: {self.cons_loss:,.0f}\n"
                f"   • Professionals : {self.pro_loss:,.0f}\n"
            )
            emoji = None
            res = "victory" if self.front >= 1 else "defeat"  if self.front <= 0 else "treaty"
            emoji = "🏆" if self.front >= 1 else "🏳️" if self.front <= 0 else "🕊️"
            
                
                
            self.s.log(f"{emoji} External war ended – {self._peace_desc()} {res}, {self.civ_loss + self.cons_loss + self.pro_loss:,.0f} casualties")
            self.s.war = None
        return ended

    def month(self, sp):
        self.battle(sp)
        self.resolve()
        
# ────────── Civil War class ──────────
class CivilWar:
    def __init__(self, state):
        self.s = state
        self.front = 0.5
        self.months = 0
        self.rebel_str = 0.0

        # initialize rebel army
        defect_fraction = 1 - self.s.mil.loyalty
        self.rebel_cons = int(self.s.unrest * self.s.mass_pop * 0.01) + int(defect_fraction * self.s.mil.ready_conscripts)
        self.rebel_pros = int(defect_fraction * (self.s.mil.core_mass) + (defect_fraction/3 * self.s.mil.core_elite))

        # update state military after defections
        self.s.mass_pop -= self.rebel_cons
        self.s.mil.ready_conscripts -= defect_fraction * self.s.mil.ready_conscripts
        self.s.mil.core_mass -= defect_fraction * (self.s.mil.core_mass)
        self.s.mil.core_elite -= (defect_fraction/10 * self.s.mil.core_elite)
        self.s.mil.recompute()

        self.rebel_strength = self.rebel_cons + self.rebel_pros

        self.gov_casualties = 0
        self.reb_casualties = 0
        self.civ_casualties = 0

        print(f"⚔️ Civil War begins! {self.rebel_cons:,} rebel conscripts, {self.rebel_pros:,} professionals defect.")
        self.s.log(f"⚔ Civil-war started, {self.rebel_cons + self.rebel_pros:,} rebels")

    def _act(self):
        r = random.random()
        if r < 0.3: return ("attack", 0.3)
        if r > 0.7: return ("retreat", -0.3)
        return ("hold", 0.0)

    def battle(self):
      self.months += 1
      gov_strength = self.s.mil.strength()
      reb_strength = self.rebel_cons + 2 * self.rebel_pros
      bias = (gov_strength - reb_strength) / (reb_strength + 1e-9)

      a, a_bonus = self._act()
      e, e_bonus = self._act()

      score = 0.4 * math.tanh(bias) + a_bonus - e_bonus + random.gauss(0, 0.25)
      qual = "decisive" if abs(score) > 0.9 else "pyrrhic" if abs(score) < 0.2 else "regular"
      shift_base = {"pyrrhic": 0.01, "regular": 0.03, "decisive": 0.07}[qual]
      shift = shift_base * (1 if score > 0 else -1)
      if a == "retreat": shift = -abs(shift) * 1.4
      if e == "retreat": shift = abs(shift) * 1.4
      if a == "hold" and e == "hold":
          shift = 0.0
          qual = "stalemate"

      self.front = max(0, min(1, self.front + shift))

      # casualty intensity factor
      base_intensity = 0.002
      rate = base_intensity * (1.5 if qual == "decisive" else 0.7 if qual == "pyrrhic" else 0.2 if qual == "stalemate" else 1)
      rate *= random.uniform(0.8, 1.2)

      total_strength = gov_strength + reb_strength
      total_casualties = total_strength * rate

      # Civilian casualties are fixed share
      civ_loss = self.s.mass_pop * rate * 0.01
      self.s.mass_pop -= civ_loss
      self.civ_casualties += civ_loss

      # Military losses split by outcome
      gov_loss_ratio = 0.4 if score > 0 else 0.6  # winning side takes fewer
      gov_loss = total_casualties * gov_loss_ratio
      reb_loss = total_casualties * (1 - gov_loss_ratio)

      # Apply government losses
      gov_con_loss = gov_loss * 0.7
      gov_pro_loss = gov_loss * 0.3
      self.s.mil.ready_conscripts = max(0, self.s.mil.ready_conscripts - gov_con_loss)
      self.s.mil.core_mass = max(0, self.s.mil.core_mass - gov_pro_loss)

      # Apply rebel losses
      self.rebel_strength = max(0, self.rebel_strength - reb_loss)

      self.gov_casualties += gov_loss
      self.reb_casualties += reb_loss

      self.rebel_strength += self.s.unrest * self.s.mass_pop * 0.0001 * (1-self.front)
      self.s.mass_pop -= self.s.mass_pop * 0.0001 * (1-self.front)

      self.s.infra *= (1-0.05*rate/ base_intensity)
      self.s.mil.recompute()

      bar = "=" * int(self.front * 20) + "-" * (20 - int(self.front * 20))
      print(f"    CIVIL WAR ROUND {self.months:02d} | govt {a:<7} vs rebels {e:<7} | {qual.capitalize():<8}")
      print(f"             front [{bar}] {self.front:.2f} | govt strength: {int(gov_strength):,} rebel strength: {int(self.rebel_strength):,}")
      self.s.log(f"GOV [{bar}] REBELS") 
      print(f"             civ dead {civ_loss:>7,.0f} | govt {gov_loss:>7,.0f} | rebel {reb_loss:>7,.0f}")

    def resolve(self):
        # Victory conditions
        if self.front <= 0:
            print("🟥 Rebels win! Institutions reformed.")
            self.s.log("🟥 Civil-war ended – rebels win")
            self.s.EI = min(1.0, self.s.EI + 0.4)
            self.s.PI = min(1.0, self.s.PI + 0.4)
            self.s.war = None
            return True

        elif self.front >= 1:
            print("🟦 Government prevails. Rebels defeated.")
            self.s.log("🟦 Civil-war ended – govt prevails")
            self.s.EI = max(0.0, self.s.EI - 0.4)
            self.s.PI = max(0.0, self.s.PI - 0.4)
            self.s.war = None
            return True

        # Peace negotiation chance increases with war duration
        peace_prob = 0.01 + 0.005 * self.months
        if random.random() < peace_prob:
            print(f"🕊️ Peace treaty signed after {self.months} months of civil war.")
            
            # Institutional adjustment based on balance
            if self.front > 0.6:
                print("🟦 Government has advantage — institutions regress.")
                self.s.log("⚖️🟦 Civil-war ended – negotiated peace in government favor")
                self.s.EI = max(0.0, self.s.EI - 0.1)
                self.s.PI = max(0.0, self.s.PI - 0.1)
            elif self.front < 0.4:
                print("🟥 Rebels gain ground — institutions expand.")
                self.s.log("⚖️🟥 Civil-war ended –negotiated peace in rebel favor")
                self.s.EI = min(1.0, self.s.EI + 0.1)
                self.s.PI = min(1.0, self.s.PI + 0.1)
            else:
                print("⚖️ Stalemate — institutions remain unchanged.")
                self.s.log("⚖️Civil-war ended – negotiated peace in status quo")
            self.s.war = None
            return True
        return False


    def month(self, sp):
        self.battle()
        if self.resolve():
            self.s.mass_pop += self.rebel_strength
            print(f"=== CIVIL WAR ENDS after {self.months} months ===")
            print(f"   • Civilian dead  : {self.civ_casualties:,.0f}")
            print(f"   • Govt military : {self.gov_casualties:,.0f}")
            print(f"   • Rebel losses  : {self.reb_casualties:,.0f}\n")