from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CountryState


def compute_vote(state: "CountryState") -> tuple[float, float]:
    from .factions import faction_vote_modifier
    mass_power = state.mass_pop * (state.PI ** 2)
    elite_power = state.elite_pop
    total = mass_power + elite_power + 1e-9
    diff = (mass_power - elite_power) / total

    ei_reform_prob = max(0.1, min(0.9, 0.5 + 0.5 * diff))
    pi_reform_prob = max(0.2, min(0.8, 0.5 + 0.3 * diff))

    ei_modifier = faction_vote_modifier(state.factions, 1)
    pi_modifier = faction_vote_modifier(state.factions, 1)
    ei_reform_prob = max(0.05, min(0.95, ei_reform_prob + ei_modifier))
    pi_reform_prob = max(0.05, min(0.95, pi_reform_prob + pi_modifier))

    return ei_reform_prob, pi_reform_prob


def apply_vote(state: "CountryState") -> None:
    ei_prob, pi_prob = compute_vote(state)
    if random.random() < ei_prob:
        state.EI = min(1.0, state.EI + state.max_step)
    elif random.random() > 1 - ei_prob:
        state.EI = max(0.0, state.EI - state.max_step)

    if random.random() < pi_prob:
        state.PI = min(1.0, state.PI + state.max_step)
    elif random.random() > 1 - pi_prob:
        state.PI = max(0.0, state.PI - state.max_step)

    for f in state.factions:
        f.update_loyalty(state.EI, state.PI)
