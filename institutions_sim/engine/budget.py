from __future__ import annotations
import random
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CountryState

LINES = ("tech", "infra", "pc", "sec", "welfare")


class BudgetAllocator(Protocol):
    def __call__(self, state: "CountryState") -> dict[str, float]: ...


def heuristic_weights(state: "CountryState", jitter: float = 0.03) -> dict[str, float]:
    cfg = state.sim_cfg
    econ_ok = state.unrest < 0.35
    war_time = state.war is not None
    high_u = state.unrest > 0.6
    base = 0.10
    w = {
        "tech":    base + (0.25 if econ_ok else 0.10),
        "infra":   base + (0.25 if econ_ok else 0.10),
        "pc":      base + (0.15 if econ_ok else 0.05),
        "sec":     base + (0.25 if (war_time or high_u) else 0.10),
        "welfare": base + (0.25 if high_u else 0.05),
    }
    for k in w:
        w[k] = max(cfg.alloc_floor, w[k] + random.uniform(-jitter, jitter))
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


class HeuristicAllocator:
    def __call__(self, state: "CountryState") -> dict[str, float]:
        return heuristic_weights(state)


class FactionAllocator:
    def __init__(self, faction_weight: float = 0.30):
        self.faction_weight = faction_weight

    def __call__(self, state: "CountryState") -> dict[str, float]:
        base = heuristic_weights(state)
        if not state.factions:
            return base
        total_power = sum(f.power for f in state.factions) or 1.0
        faction_pref: dict[str, float] = dict.fromkeys(LINES, 0.0)
        for f in state.factions:
            w = f.power / total_power
            for line in LINES:
                faction_pref[line] += w * f.preferred_alloc.get(line, 1.0 / len(LINES))
        s = sum(faction_pref.values()) or 1.0
        faction_pref = {k: v / s for k, v in faction_pref.items()}
        fw = self.faction_weight
        blended = {k: (1 - fw) * base[k] + fw * faction_pref[k] for k in LINES}
        s2 = sum(blended.values())
        return {k: v / s2 for k, v in blended.items()}
