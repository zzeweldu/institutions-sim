from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CountryState


def compute_grievance(state: "CountryState", gini: float) -> float:
    inequality = max(0, (state.elite_pop * (1 - state.EI) - state.mass_pop * state.EI) /
                    (state.mass_pop + 1e-9))
    faction_dissatisfaction = 0.0
    if state.factions:
        faction_dissatisfaction = sum(
            max(0, 0.5 - f.loyalty) * (f.mass_share + f.elite_share)
            for f in state.factions
        )
    grievance = (
        (1 - state.EI) * 0.25 +
        (1 - state.PI) * 0.25 +
        (1 - state.sec) * 0.15 +
        gini * 0.20 +
        min(1.0, inequality) * 0.15 +
        min(1.0, faction_dissatisfaction) * 0.10
    )
    return max(0.0, min(1.0, grievance))


def update_unrest(state: "CountryState", gini: float) -> None:
    grievance = compute_grievance(state, gini)
    delta = grievance - state.unrest
    state.unrest += state.sim_cfg.unrest_adjust * delta * abs(delta)
    state.unrest = max(0.0, min(1.0, state.unrest))


def process_protests(state: "CountryState", repression_spending: float) -> None:
    cfg = state.sim_cfg
    if not state.protest and state.unrest > 0.4:
        trigger_p = cfg.protest_base * state.unrest
        for f in state.factions:
            if f.mobilized:
                trigger_p += 0.05
        if random.random() < trigger_p:
            state.protest = True
            state.protest_duration = 0
            state.events.append(f"M{state.month:03d}  🪧 Protest movement begins")

    if state.protest:
        state.protest_duration += 1
        state.infra *= 0.995
        state.unrest = min(1.0, state.unrest + 0.001)

        action = "concede" if state.unrest > 0.7 and random.random() < 0.1 else "repress"
        if action == "repress":
            if random.random() < 0.1 + 0.2 * repression_spending / (state.mass_pop + 1):
                state.protest = False
                state.unrest = min(1.0, state.unrest + 0.1)
                state.events.append(f"M{state.month:03d}  🔨 Protest suppressed")
            elif random.random() < 0.05 * state.protest_duration * state.unrest:
                from .war import CivilWar
                state.events.append(f"M{state.month:03d}  🔥 Repression backfires → civil war")
                state.war = CivilWar(state)
                state.protest = False
                state.unrest = max(0, state.unrest - 0.5)
        else:
            state.EI = min(1.0, state.EI + 0.05)
            state.PI = min(1.0, state.PI + 0.05)
            state.protest = False
            state.unrest = max(0, state.unrest - 0.3)
            state.events.append(f"M{state.month:03d}  🫱 Government concedes")
