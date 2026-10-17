from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field
from ..config.schema import SimConfig, StateConfig


class TriggerSpec(BaseModel):
    month: Optional[int] = None
    condition: Optional[str] = None


class EffectSpec(BaseModel):
    delta_EI: float = 0.0
    delta_PI: float = 0.0
    delta_unrest: float = 0.0
    delta_tech: float = 0.0
    delta_infra: float = 0.0
    kill_fraction: float = 0.0
    budget_inject: float = 0.0
    message: Optional[str] = None


class EventSpec(BaseModel):
    id: str
    trigger: TriggerSpec
    effect: EffectSpec
    once: bool = True
    fired: bool = False


class WinCondition(BaseModel):
    type: Literal["reach", "avoid", "survive"]
    metric: Optional[str] = None
    threshold: Optional[float] = None
    consecutive_months: int = 1
    _streak: int = 0

    def is_met(self, snap_dict: dict, history: list) -> bool:
        if self.type == "survive":
            return False
        val = snap_dict.get(self.metric, 0.0)
        met_now = False
        if self.type == "reach" and self.threshold is not None:
            met_now = val >= self.threshold
        elif self.type == "avoid" and self.threshold is not None:
            met_now = val <= self.threshold

        if met_now:
            self._streak += 1
        else:
            self._streak = 0
        return self._streak >= self.consecutive_months


class ScenarioSpec(BaseModel):
    name: str = "Scenario"
    description: str = ""
    initial_state: StateConfig = Field(default_factory=StateConfig)
    sim_config: SimConfig = Field(default_factory=SimConfig)
    events: list[EventSpec] = Field(default_factory=list)
    win_conditions: list[WinCondition] = Field(default_factory=list)
    lose_conditions: list[WinCondition] = Field(default_factory=list)
    max_months: int = 120
