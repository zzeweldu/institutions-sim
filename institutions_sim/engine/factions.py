from __future__ import annotations
import random
from dataclasses import dataclass, field
from ..config.schema import FactionConfig


@dataclass
class Faction:
    id: str
    label: str
    mass_share: float = 0.0
    elite_share: float = 0.0
    ei_stance: float = 0.5
    pi_stance: float = 0.5
    preferred_alloc: dict[str, float] = field(default_factory=dict)
    loyalty: float = 0.7
    power: float = 0.0
    mobilized: bool = False

    @classmethod
    def from_config(cls, cfg: FactionConfig) -> "Faction":
        return cls(
            id=cfg.id,
            label=cfg.label,
            mass_share=cfg.mass_share,
            elite_share=cfg.elite_share,
            ei_stance=cfg.ei_stance,
            pi_stance=cfg.pi_stance,
            preferred_alloc=dict(cfg.preferred_alloc),
        )

    def update_power(self, mass_pop: float, elite_pop: float, PI: float) -> None:
        self.power = (
            self.mass_share * mass_pop * (PI ** 2) +
            self.elite_share * elite_pop
        )

    def update_loyalty(self, EI: float, PI: float) -> None:
        ei_satisfaction = 1.0 - abs(EI - self.ei_stance)
        pi_satisfaction = 1.0 - abs(PI - self.pi_stance)
        target = (ei_satisfaction + pi_satisfaction) / 2.0
        self.loyalty += 0.05 * (target - self.loyalty)
        self.loyalty = max(0.0, min(1.0, self.loyalty))

    def maybe_mobilize(self, unrest: float) -> bool:
        if self.loyalty < 0.3 and not self.mobilized:
            if random.random() < (0.3 - self.loyalty) * unrest:
                self.mobilized = True
        elif self.loyalty > 0.5:
            self.mobilized = False
        return self.mobilized

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "mass_share": self.mass_share,
            "elite_share": self.elite_share,
            "ei_stance": self.ei_stance,
            "pi_stance": self.pi_stance,
            "preferred_alloc": self.preferred_alloc,
            "loyalty": self.loyalty,
            "power": self.power,
            "mobilized": self.mobilized,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Faction":
        f = cls(
            id=d["id"], label=d["label"],
            mass_share=d["mass_share"], elite_share=d["elite_share"],
            ei_stance=d["ei_stance"], pi_stance=d["pi_stance"],
            preferred_alloc=d.get("preferred_alloc", {}),
        )
        f.loyalty = d.get("loyalty", 0.7)
        f.power = d.get("power", 0.0)
        f.mobilized = d.get("mobilized", False)
        return f


def coup_faction_boost(factions: list[Faction]) -> float:
    boost = 0.0
    for f in factions:
        if f.loyalty < 0.4 and f.elite_share > 0.01:
            boost += (0.4 - f.loyalty) * f.elite_share * 2.0
    return min(0.5, boost)


def faction_vote_modifier(factions: list[Faction], ei_direction: int) -> float:
    modifier = 0.0
    total_power = sum(f.power for f in factions) or 1.0
    for f in factions:
        if f.mobilized:
            stance_diff = f.ei_stance - 0.5
            modifier += (f.power / total_power) * stance_diff * ei_direction
    return max(-0.3, min(0.3, modifier))
