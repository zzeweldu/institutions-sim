from __future__ import annotations
import math, random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from ..config.schema import SimConfig, StateConfig, FactionConfig
from .economy import cobb_douglas, sector_tfp, compute_gini, resource_rent
from .factions import Faction
from .budget import FactionAllocator
from .military import Military
from .unrest import update_unrest, process_protests
from .institutions import apply_vote

if TYPE_CHECKING:
    from .war import War, CivilWar


@dataclass
class MonthSnapshot:
    month: int
    EI: float
    PI: float
    Y: float
    unrest: float
    gini: float
    mass_pop: float
    elite_pop: float
    infra: float
    tech: float
    pc: float
    sec: float
    infra_ratio: float
    loyalty: float
    war_front: float
    war_type: str
    protest_active: bool
    sector_output: dict[str, float]
    budget_split: dict[str, float]
    faction_states: list[dict]
    events: list[str]

    def to_dict(self) -> dict:
        d = {
            "month": self.month, "EI": self.EI, "PI": self.PI, "Y": self.Y,
            "unrest": self.unrest, "gini": self.gini,
            "mass_pop": self.mass_pop, "elite_pop": self.elite_pop,
            "infra": self.infra, "tech": self.tech, "pc": self.pc, "sec": self.sec,
            "infra_ratio": self.infra_ratio, "loyalty": self.loyalty,
            "war_front": self.war_front, "war_type": self.war_type,
            "protest_active": self.protest_active,
        }
        for k, v in self.sector_output.items():
            d[f"sector_{k}"] = v
        for k, v in self.budget_split.items():
            d[f"budget_{k}"] = v
        for fs in self.faction_states:
            fid = fs["id"]
            d[f"faction_{fid}_power"] = fs.get("power", 0.0)
            d[f"faction_{fid}_loyalty"] = fs.get("loyalty", 0.0)
        d["events"] = "|".join(self.events)
        return d


class CountryState:
    def __init__(self, cfg: StateConfig, sim_cfg: SimConfig):
        self.name = cfg.name
        self.month = 0
        self.max_step = cfg.max_step
        self.sim_cfg = sim_cfg

        self._rng = random.Random(cfg.seed)

        pop = cfg.pop
        self.mass_pop  = pop * (1 - cfg.elite_share)
        self.elite_pop = pop * cfg.elite_share
        self.tech  = cfg.tech
        self.infra = pop
        self.pc    = pop
        self.sec   = pop
        self.base_infra = self.infra
        self.EI = cfg.EI
        self.PI = cfg.PI
        self.budget = 0.0
        self.unrest = 0.0
        self.protest = False
        self.protest_duration = 0
        self.last_vote = 0
        self.events: list[str] = []

        self.factions: list[Faction] = [Faction.from_config(fc) for fc in cfg.factions]
        self.alloc = FactionAllocator()
        self.mil = Military(self)
        self.war: Optional[object] = None

    @property
    def pop(self) -> float:
        return self.mass_pop + self.elite_pop

    def invade_prob(self) -> float:
        cfg = self.sim_cfg
        r = (self.mil.mass_members + self.mil.elite_members) / (self.pop + 1e-9)
        risk = cfg.base_invade + cfg.invade_k * max(0, cfg.safe_ratio - r)
        return max(0.002, min(1.0, risk))

    def adjust_prof_ratio(self) -> None:
        cfg = self.sim_cfg
        risk = self.invade_prob()
        target = cfg.min_ratio + (cfg.max_ratio - cfg.min_ratio) * (risk / 0.5)
        target = min(cfg.max_ratio, max(cfg.min_ratio, target))
        cur = self.mil.base_ratio
        rate = cfg.inertia_expand if target > cur else cfg.inertia_contract
        self.mil.base_ratio += rate * (target - cur)
        self.mil.base_ratio = max(cfg.min_ratio, min(cfg.max_ratio, self.mil.base_ratio))
        self.mil.update_professional()

    def _maybe_disaster(self) -> None:
        cfg = self.sim_cfg
        p = cfg.disaster_base + cfg.disaster_infra_coeff + cfg.disaster_unrest_coeff * self.unrest
        if self._rng.random() >= p:
            return
        severity = self._rng.gammavariate(2, 0.04)
        self.infra *= max(0, 1 - severity)
        mass_kill  = self.mass_pop  * 0.03 * severity
        elite_kill = self.elite_pop * 0.01 * severity
        self.mass_pop  = max(0, self.mass_pop  - mass_kill)
        self.elite_pop = max(0, self.elite_pop - elite_kill)
        self.sec *= max(0.1, 1 - 0.4 * severity)
        shock = 0.5 * severity
        self.unrest = min(1.0, self.unrest + shock)
        self.events.append(
            f"M{self.month:03d}  🌪️ Disaster severity={severity*100:.1f}% "
            f"{mass_kill+elite_kill:,.0f} dead"
        )

    def _maybe_draft(self) -> None:
        if not self.war and self.invade_prob() <= 0.02:
            return
        base_fraction = self.invade_prob() * 0.05
        pressure = 0.0
        if self.war:
            front = getattr(self.war, "front", 0.5)
            pressure = max(0.0, 0.6 - front) / 0.6
        draft_fraction = base_fraction * (1 + pressure) * (1.2 - self.EI)
        desired = draft_fraction * self.pop
        shortfall = desired - self.mil.ready_conscripts
        if shortfall > 0:
            self.mil.draft(shortfall)

    def month_step(self) -> MonthSnapshot:
        self.month += 1
        step_events_start = len(self.events)

        self._maybe_disaster()

        cfg = self.sim_cfg
        self.mass_pop  *= 1 + cfg.mass_growth
        self.elite_pop *= 1 + cfg.elite_growth
        self.infra *= 1 - cfg.infra_decay
        self.sec   *= 1 - cfg.sec_decay

        infra_ratio = self.infra / max(1e-6, self.base_infra)
        tfp = sector_tfp(self.EI, self.tech, infra_ratio, cfg.sector_weights)
        base_output = cobb_douglas(self.mass_pop, self.elite_pop, self.EI,
                                   self.pc, self.infra, self.tech)
        gross = base_output * tfp

        if self.unrest > 0.4:
            gross *= 1 - cfg.unrest_output_penalty
        if self.war:
            gross *= 1 - getattr(self.war, "front", 0.5) * 0.5

        rent, dutch_drag = resource_rent(gross, cfg.resource_rent_share, self.EI)
        if dutch_drag > 0:
            self.EI = max(0.0, self.EI - dutch_drag * 0.01)

        tax = (gross + rent) * cfg.tax_rate
        net_income = gross - tax
        self.budget += tax

        self.adjust_prof_ratio()
        num_pros = self.mil.core_mass + self.mil.core_elite
        num_cons = self.mil.ready_conscripts
        per_capita = net_income / (self.pop + 1e-9)
        payroll = (cfg.soldier_cost * num_pros + cfg.conscript_cost * num_cons) * per_capita
        self.budget = max(0, self.budget - payroll)

        split = self.alloc(self)
        invest = self.budget
        self.budget = 0.0

        repression_spending = invest * split["sec"] * cfg.repression_cost_fraction
        self.tech  *= 1 + 0.0003 * math.log1p(invest * split["tech"])
        self.infra *= 1 + 0.001  * math.log1p(invest * split["infra"])
        self.pc    *= 1 + 0.001  * math.log1p(invest * split["pc"])
        self.sec   *= 1 + 0.001  * math.log1p(max(0, invest * split["sec"] - repression_spending))

        mass_income  = net_income * self.EI
        elite_income = net_income * (1 - self.EI)
        gini = compute_gini(self.mass_pop, self.elite_pop, mass_income, elite_income)

        update_unrest(self, gini)
        process_protests(self, repression_spending)

        if self.month - self.last_vote >= cfg.vote_interval:
            apply_vote(self)
            self.last_vote = self.month

        for f in self.factions:
            f.update_power(self.mass_pop, self.elite_pop, self.PI)
            f.maybe_mobilize(self.unrest)

        self.mil.recompute()
        self.mil.coup_check()
        self._maybe_draft()

        if not self.war and self._rng.random() < self.invade_prob():
            from .war import War
            self.events.append(f"M{self.month:03d}  🔥 External war begins")
            self.war = War(self)
        if self.war:
            self.war.month(sp=invest * split["sec"])

        step_events = self.events[step_events_start:]

        from .economy import compute_sector_productivity
        prod = compute_sector_productivity(self.EI, self.tech, infra_ratio)
        sector_output = {k: gross * cfg.sector_weights.get(k, 0) * prod[k]
                         for k in ("agriculture", "industry", "services")}

        war_front = getattr(self.war, "front", 0.0) if self.war else 0.0
        war_type = type(self.war).__name__ if self.war else "none"

        return MonthSnapshot(
            month=self.month, EI=self.EI, PI=self.PI, Y=gross,
            unrest=self.unrest, gini=gini,
            mass_pop=self.mass_pop, elite_pop=self.elite_pop,
            infra=self.infra, tech=self.tech, pc=self.pc, sec=self.sec,
            infra_ratio=infra_ratio, loyalty=self.mil.loyalty,
            war_front=war_front, war_type=war_type,
            protest_active=self.protest,
            sector_output=sector_output,
            budget_split=split,
            faction_states=[f.to_dict() for f in self.factions],
            events=step_events,
        )

    def to_dict(self) -> dict:
        d = {
            "name": self.name, "month": self.month, "max_step": self.max_step,
            "mass_pop": self.mass_pop, "elite_pop": self.elite_pop,
            "tech": self.tech, "infra": self.infra, "pc": self.pc, "sec": self.sec,
            "base_infra": self.base_infra,
            "EI": self.EI, "PI": self.PI,
            "budget": self.budget, "unrest": self.unrest,
            "protest": self.protest, "protest_duration": self.protest_duration,
            "last_vote": self.last_vote,
            "events": self.events,
            "factions": [f.to_dict() for f in self.factions],
            "mil": self.mil.to_dict(),
            "war": self.war.to_dict() if self.war else None,
            "sim_cfg": self.sim_cfg.model_dump(),
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CountryState":
        from ..config.schema import SimConfig, StateConfig
        sim_cfg = SimConfig(**d.get("sim_cfg", {}))
        state_cfg = StateConfig(
            name=d["name"],
            pop=d["mass_pop"] + d["elite_pop"],
            tech=d["tech"],
            EI=d["EI"],
            PI=d["PI"],
            max_step=d.get("max_step", 0.1),
        )
        obj = cls.__new__(cls)
        obj.sim_cfg = sim_cfg
        obj.name = d["name"]
        obj.month = d["month"]
        obj.max_step = d.get("max_step", 0.1)
        obj.mass_pop = d["mass_pop"]
        obj.elite_pop = d["elite_pop"]
        obj.tech = d["tech"]
        obj.infra = d["infra"]
        obj.pc = d["pc"]
        obj.sec = d["sec"]
        obj.base_infra = d.get("base_infra", d["infra"])
        obj.EI = d["EI"]
        obj.PI = d["PI"]
        obj.budget = d.get("budget", 0.0)
        obj.unrest = d.get("unrest", 0.0)
        obj.protest = d.get("protest", False)
        obj.protest_duration = d.get("protest_duration", 0)
        obj.last_vote = d.get("last_vote", 0)
        obj.events = d.get("events", [])
        obj.factions = [Faction.from_dict(fd) for fd in d.get("factions", [])]
        obj.alloc = FactionAllocator()
        obj._rng = random.Random()
        obj.mil = Military.from_dict(d.get("mil", {}), obj)
        obj.war = None
        if d.get("war"):
            from .war import War, CivilWar
            wd = d["war"]
            if wd.get("type") == "CivilWar":
                obj.war = CivilWar.from_dict(wd, obj)
            else:
                obj.war = War.from_dict(wd, obj)
        return obj
