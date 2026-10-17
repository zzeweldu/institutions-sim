from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CountryState
    from ..config.schema import SimConfig


class Military:
    def __init__(self, state: "CountryState"):
        self.state = state
        self.mass_fraction = 0.8
        self.training_delay = 2
        self.training_queue: list[tuple[int, float]] = []
        self.ready_conscripts = 0.0
        self.base_ratio = 0.003
        self.core_mass = 0.0
        self.core_elite = 0.0
        self.loyalty = 1.0
        self.mass_members = 0.0
        self.elite_members = 0.0
        self.recompute()

    @property
    def cfg(self) -> "SimConfig":
        return self.state.sim_cfg

    def _adjust_core(self) -> None:
        pop_now = self.state.pop
        desired = max(self.cfg.min_ratio, min(self.base_ratio, self.cfg.max_ratio))
        target = desired * pop_now
        gap = target - (self.core_mass + self.core_elite)
        delta = max(-self.cfg.hire_limit * pop_now,
                    min(self.cfg.hire_limit * pop_now, gap))
        self.core_mass  += delta * self.mass_fraction
        self.core_elite += delta * (1 - self.mass_fraction)

    def update_professional(self) -> None:
        self._adjust_core()

    def process_training(self) -> None:
        nxt = []
        for m, n in self.training_queue:
            if m <= 1:
                self.ready_conscripts += n
            else:
                nxt.append((m - 1, n))
        self.training_queue = nxt

    def draft(self, n: float) -> None:
        n = int(n)
        if n <= 0 or n > self.state.mass_pop:
            return
        self.state.mass_pop -= n
        self.training_queue.append((self.training_delay, n))

        from .factions import coup_faction_boost
        opposition_boost = sum(
            f.mass_share for f in self.state.factions if f.loyalty < 0.4
        )
        base_penalty = (20 * n) / (self.state.pop + 1e-9)
        if self.state.war and not isinstance(self.state.war, type(None)):
            from .war import CivilWar
            mult = 3.0 if type(self.state.war).__name__ == "CivilWar" else 0.5
        else:
            mult = 1.5
        mult *= 1 + opposition_boost
        self.state.unrest = min(1.0, self.state.unrest + base_penalty * mult)

    def demobilise(self) -> None:
        back = self.ready_conscripts + sum(n for _, n in self.training_queue)
        self.state.mass_pop += back
        self.ready_conscripts = 0.0
        self.training_queue.clear()

    def recompute(self) -> None:
        self.update_professional()
        self.process_training()
        self.mass_members  = self.core_mass + self.ready_conscripts
        self.elite_members = self.core_elite
        tot = self.mass_members + self.elite_members
        ei, sec = self.state.EI, self.state.sec
        baseL = (ei * self.mass_members + (1 - ei) * self.elite_members) / (tot + 1e-9)
        self.loyalty = max(0.0, min(1.0, baseL + 0.2 * (sec - 1)))

    def strength(self) -> float:
        manpower = self.mass_members + 2 * self.elite_members
        return manpower * (1 + self.cfg.equip_weight * (self.state.sec - 1))

    def coup_check(self) -> None:
        from .factions import coup_faction_boost
        faction_boost = coup_faction_boost(self.state.factions)
        attempt_chance = (0.25 + 0.5 * (1 - self.loyalty)) * self.cfg.coup_probability
        attempt_chance = min(0.8, attempt_chance + faction_boost * self.cfg.coup_probability)
        if random.random() < attempt_chance:
            success_chance = 0.25 + 0.5 * (1 - self.loyalty)
            if random.random() < success_chance:
                self.state.events.append(f"M{self.state.month:03d}  ⚠️ Coup SUCCESS – institutions regress")
                self.state.EI = max(0.0, self.state.EI - 0.4)
                self.state.PI = max(0.0, self.state.PI - 0.4)
                self.state.unrest += self.loyalty * 0.3
            else:
                self.state.events.append(f"M{self.state.month:03d}  🛡️ Coup FAILED – crackdown")
                purge = (1.01 - self.loyalty) * 0.2
                self.core_mass  = max(0, self.core_mass  - self.core_mass  * purge)
                self.core_elite = max(0, self.core_elite - self.core_elite * purge)
                self.ready_conscripts = max(0, self.ready_conscripts - self.ready_conscripts * purge * 0.2)
                self.state.sec *= 1.05

    def to_dict(self) -> dict:
        return {
            "base_ratio": self.base_ratio,
            "core_mass": self.core_mass,
            "core_elite": self.core_elite,
            "ready_conscripts": self.ready_conscripts,
            "loyalty": self.loyalty,
            "training_queue": self.training_queue,
        }

    @classmethod
    def from_dict(cls, d: dict, state: "CountryState") -> "Military":
        m = cls.__new__(cls)
        m.state = state
        m.mass_fraction = 0.8
        m.training_delay = 2
        m.base_ratio = d.get("base_ratio", 0.003)
        m.core_mass = d.get("core_mass", 0.0)
        m.core_elite = d.get("core_elite", 0.0)
        m.ready_conscripts = d.get("ready_conscripts", 0.0)
        m.loyalty = d.get("loyalty", 1.0)
        m.training_queue = [tuple(x) for x in d.get("training_queue", [])]
        m.mass_members = m.core_mass + m.ready_conscripts
        m.elite_members = m.core_elite
        return m
