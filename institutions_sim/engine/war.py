from __future__ import annotations
import random, math
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .state import CountryState


class War:
    def __init__(self, state: "CountryState", enemy_str: Optional[float] = None):
        self.s = state
        self.front = 0.5
        self.months = 0
        self.reinforce_rate = 0.02
        cfg = state.sim_cfg
        if enemy_str is not None:
            self.enemy_str = enemy_str
        else:
            variance = random.uniform(cfg.min_enemy_strength, cfg.max_enemy_strength)
            self.enemy_str = state.mil.strength() * variance
        self.civ_loss = 0.0
        self.cons_loss = 0.0
        self.pro_loss = 0.0

    def _act(self, bias: float) -> tuple[str, float]:
        p_att = min(1, max(0, 0.3 + 0.3 * bias))
        p_ret = min(1, max(0, 0.3 - 0.3 * bias))
        r = random.random()
        if r < p_att:    return ("attack",  0.3)
        if r > 1 - p_ret: return ("retreat", -0.3)
        return ("hold", 0.0)

    def battle(self, sec_sp: float) -> None:
        self.months += 1
        ours, enemy = self.s.mil.strength(), self.enemy_str
        bias = (ours - enemy) / (enemy + 1e-9)
        a, a_bonus = self._act(bias)
        e, e_bonus = self._act(-bias)
        score = 0.4 * math.tanh(bias) + a_bonus - e_bonus + random.gauss(0, 0.25)
        qual = "decisive" if abs(score) > 0.9 else "pyrrhic" if abs(score) < 0.2 else "regular"
        if a == "hold" and e == "hold":
            qual = "stalemate"
            shift = 0.0
        else:
            shift_base = {"pyrrhic": 0.01, "regular": 0.03, "decisive": 0.07}[qual]
            shift = shift_base * (1 if score > 0 else -1)
            if a == "retreat": shift = -abs(shift) * 1.4
            if e == "retreat": shift =  abs(shift) * 1.4
        self.front = max(0, min(1, self.front + shift))

        loc = 1 - self.front
        rate = 0.003 * {"decisive": 1.5, "pyrrhic": 0.7, "stalemate": 0.2, "regular": 1.0}[qual]
        rate *= random.uniform(0.8, 1.2)

        civ_mass  = self.s.mass_pop  * rate * 0.01 * loc
        civ_elite = self.s.elite_pop * rate * 0.005 * loc
        cons_loss = min(self.s.mil.ready_conscripts, rate * 1.3 * self.s.mil.ready_conscripts)
        pro_m     = min(self.s.mil.core_mass,  rate * 0.9 * self.s.mil.core_mass)
        pro_e     = min(self.s.mil.core_elite, rate * 0.9 * self.s.mil.core_elite)

        self.s.mass_pop  -= civ_mass
        self.s.elite_pop -= civ_elite
        self.s.mil.ready_conscripts -= cons_loss
        self.s.mil.core_mass  -= pro_m
        self.s.mil.core_elite -= pro_e
        self.s.mil.recompute()

        self.civ_loss  += civ_mass + civ_elite
        self.cons_loss += cons_loss
        self.pro_loss  += pro_m + pro_e
        self.enemy_str += self.reinforce_rate * self.enemy_str
        self.s.sec = max(0.1, self.s.sec * (1 - 0.01 * loc))

    def resolve(self) -> bool:
        ended = False
        if self.front <= 0:
            self.s.events.append(f"M{self.s.month:03d}  🏳️ Total defeat – occupied")
            self.s.unrest = min(1, self.s.unrest + 0.15)
            self.s.mil.loyalty = max(0, self.s.mil.loyalty - 0.15)
            ended = True
        elif self.front >= 1:
            self.s.events.append(f"M{self.s.month:03d}  🏆 Total victory!")
            for attr in ("tech", "infra", "pc"):
                setattr(self.s, attr, getattr(self.s, attr) * 1.05)
            self.s.unrest = max(0, self.s.unrest - 0.10)
            ended = True
        elif random.random() < 0.01 + 0.002 * self.months + 0.03 * max(0, self.front - 0.5):
            self.s.events.append(f"M{self.s.month:03d}  🕊️ Peace treaty signed")
            ended = True
        if ended:
            self.s.mil.demobilise()
            self.s.war = None
        return ended

    def month(self, sp: float) -> None:
        self.battle(sp)
        self.resolve()

    def to_dict(self) -> dict:
        return {
            "type": "War",
            "front": self.front,
            "months": self.months,
            "enemy_str": self.enemy_str,
            "civ_loss": self.civ_loss,
            "cons_loss": self.cons_loss,
            "pro_loss": self.pro_loss,
        }

    @classmethod
    def from_dict(cls, d: dict, state: "CountryState") -> "War":
        w = cls.__new__(cls)
        w.s = state
        w.front = d["front"]
        w.months = d["months"]
        w.enemy_str = d["enemy_str"]
        w.reinforce_rate = 0.02
        w.civ_loss = d.get("civ_loss", 0.0)
        w.cons_loss = d.get("cons_loss", 0.0)
        w.pro_loss = d.get("pro_loss", 0.0)
        return w


class CivilWar:
    def __init__(self, state: "CountryState"):
        self.s = state
        self.front = 0.5
        self.months = 0

        defect = 1 - state.mil.loyalty
        faction_defect = sum(
            f.mass_share for f in state.factions if f.loyalty < 0.3
        )
        rebel_pop_share = state.unrest * 0.01 + faction_defect * 0.05
        self.rebel_cons = int(rebel_pop_share * state.mass_pop) + int(defect * state.mil.ready_conscripts)
        self.rebel_pros = int(defect * state.mil.core_mass + (defect / 3) * state.mil.core_elite)

        state.mass_pop -= self.rebel_cons
        state.mil.ready_conscripts -= defect * state.mil.ready_conscripts
        state.mil.core_mass  -= defect * state.mil.core_mass
        state.mil.core_elite -= (defect / 10) * state.mil.core_elite
        state.mil.recompute()

        self.rebel_strength = self.rebel_cons + self.rebel_pros
        self.gov_casualties = 0.0
        self.reb_casualties = 0.0
        self.civ_casualties = 0.0
        state.events.append(f"M{state.month:03d}  ⚔️ Civil war – {self.rebel_cons + self.rebel_pros:,} rebels")

    def _act(self) -> tuple[str, float]:
        r = random.random()
        if r < 0.3: return ("attack",  0.3)
        if r > 0.7: return ("retreat", -0.3)
        return ("hold", 0.0)

    def battle(self) -> None:
        self.months += 1
        gov_str = self.s.mil.strength()
        reb_str = self.rebel_cons + 2 * self.rebel_pros
        bias = (gov_str - reb_str) / (reb_str + 1e-9)
        a, a_bonus = self._act()
        e, e_bonus = self._act()
        score = 0.4 * math.tanh(bias) + a_bonus - e_bonus + random.gauss(0, 0.25)
        qual = "decisive" if abs(score) > 0.9 else "pyrrhic" if abs(score) < 0.2 else "regular"
        if a == "hold" and e == "hold":
            qual = "stalemate"
            shift = 0.0
        else:
            shift_base = {"pyrrhic": 0.01, "regular": 0.03, "decisive": 0.07}[qual]
            shift = shift_base * (1 if score > 0 else -1)
            if a == "retreat": shift = -abs(shift) * 1.4
            if e == "retreat": shift =  abs(shift) * 1.4
        self.front = max(0, min(1, self.front + shift))

        rate = 0.002 * {"decisive": 1.5, "pyrrhic": 0.7, "stalemate": 0.2, "regular": 1.0}[qual]
        rate *= random.uniform(0.8, 1.2)
        total = (gov_str + reb_str) * rate
        civ_loss = self.s.mass_pop * rate * 0.01
        self.s.mass_pop -= civ_loss
        self.civ_casualties += civ_loss
        gov_loss_ratio = 0.4 if score > 0 else 0.6
        gov_loss = total * gov_loss_ratio
        reb_loss = total * (1 - gov_loss_ratio)
        self.s.mil.ready_conscripts = max(0, self.s.mil.ready_conscripts - gov_loss * 0.7)
        self.s.mil.core_mass = max(0, self.s.mil.core_mass - gov_loss * 0.3)
        self.rebel_strength = max(0, self.rebel_strength - reb_loss)
        self.gov_casualties += gov_loss
        self.reb_casualties += reb_loss
        self.rebel_strength += self.s.unrest * self.s.mass_pop * 0.0001 * (1 - self.front)
        self.s.infra *= (1 - 0.05 * rate / 0.002)
        self.s.mil.recompute()

    def resolve(self) -> bool:
        if self.front <= 0:
            self.s.events.append(f"M{self.s.month:03d}  🟥 Rebels win")
            self.s.EI = min(1.0, self.s.EI + 0.4)
            self.s.PI = min(1.0, self.s.PI + 0.4)
            self.s.war = None
            return True
        if self.front >= 1:
            self.s.events.append(f"M{self.s.month:03d}  🟦 Government prevails")
            self.s.EI = max(0.0, self.s.EI - 0.4)
            self.s.PI = max(0.0, self.s.PI - 0.4)
            self.s.war = None
            return True
        if random.random() < 0.01 + 0.005 * self.months:
            self.s.events.append(f"M{self.s.month:03d}  🕊️ Civil war peace treaty")
            if self.front > 0.6:
                self.s.EI = max(0.0, self.s.EI - 0.1)
                self.s.PI = max(0.0, self.s.PI - 0.1)
            elif self.front < 0.4:
                self.s.EI = min(1.0, self.s.EI + 0.1)
                self.s.PI = min(1.0, self.s.PI + 0.1)
            self.s.war = None
            return True
        return False

    def month(self, sp: float) -> None:
        self.battle()
        if self.resolve():
            self.s.mass_pop += self.rebel_strength

    def to_dict(self) -> dict:
        return {
            "type": "CivilWar",
            "front": self.front,
            "months": self.months,
            "rebel_strength": self.rebel_strength,
            "rebel_cons": self.rebel_cons,
            "rebel_pros": self.rebel_pros,
            "gov_casualties": self.gov_casualties,
            "reb_casualties": self.reb_casualties,
            "civ_casualties": self.civ_casualties,
        }

    @classmethod
    def from_dict(cls, d: dict, state: "CountryState") -> "CivilWar":
        cw = cls.__new__(cls)
        cw.s = state
        cw.front = d["front"]
        cw.months = d["months"]
        cw.rebel_strength = d.get("rebel_strength", 0.0)
        cw.rebel_cons = d.get("rebel_cons", 0)
        cw.rebel_pros = d.get("rebel_pros", 0)
        cw.gov_casualties = d.get("gov_casualties", 0.0)
        cw.reb_casualties = d.get("reb_casualties", 0.0)
        cw.civ_casualties = d.get("civ_casualties", 0.0)
        return cw
