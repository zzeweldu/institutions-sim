from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class DevelopmentTargets(BaseModel):
    tech: float = 3.0
    infra: float = 2.5
    pc: float = 2.5


class SimConfig(BaseModel):
    mass_growth: float = 0.0015
    elite_growth: float = 0.0010
    infra_decay: float = 0.005
    sec_decay: float = 0.005
    tax_rate: float = 0.20
    vote_interval: int = 6
    min_ratio: float = 0.002
    max_ratio: float = 0.01
    hire_limit: float = 0.0002
    inertia_expand: float = 0.10
    inertia_contract: float = 0.03
    soldier_cost: float = 1.5
    conscript_cost: float = 0.7
    base_draft: float = 0.05
    base_invade: float = 0.0002
    safe_ratio: float = 0.013
    invade_k: float = 20.0
    min_enemy_strength: float = 0.5
    max_enemy_strength: float = 1.3
    vote_step: float = 0.02
    unrest_adjust: float = 0.001
    unrest_output_penalty: float = 0.05
    protest_base: float = 0.05
    coup_probability: float = 0.05
    equip_weight: float = 0.01
    alloc_floor: float = 0.05
    repression_effectiveness: float = 0.15
    repression_cost_fraction: float = 0.20
    disaster_base: float = 0.03
    disaster_infra_coeff: float = 0.01
    disaster_unrest_coeff: float = 0.01
    resource_rent_share: float = 0.0
    faction_influence: float = 0.30
    trade_multiplier: float = 0.02
    contagion_strength: float = 0.05
    targets: DevelopmentTargets = Field(default_factory=DevelopmentTargets)
    sector_weights: dict[str, float] = Field(
        default_factory=lambda: {"agriculture": 0.25, "industry": 0.45, "services": 0.30}
    )

    def apply_overrides(self, overrides: dict[str, Any]) -> "SimConfig":
        return self.model_copy(update=overrides)


class FactionConfig(BaseModel):
    id: str
    label: str
    mass_share: float = 0.0
    elite_share: float = 0.0
    ei_stance: float = 0.5
    pi_stance: float = 0.5
    preferred_alloc: dict[str, float] = Field(default_factory=dict)


class StateConfig(BaseModel):
    name: str = "Solaria"
    pop: float = 5_000_000
    tech: float = 1.0
    elite_share: float = 0.08
    EI: float = 0.5
    PI: float = 0.5
    max_step: float = 0.1
    seed: int | None = None
    factions: list[FactionConfig] = Field(default_factory=list)
