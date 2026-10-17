from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from ..engine.state import CountryState
from ..engine.world import World
from ..config.schema import SimConfig, StateConfig
from .history import HistoryRecorder

if TYPE_CHECKING:
    from ..scenarios.schema import ScenarioSpec


class SimulationRunner:
    def __init__(self, state: CountryState, max_months: int = 120,
                 scenario: Optional["ScenarioSpec"] = None):
        self.state = state
        self.max_months = max_months
        self.scenario = scenario
        self.history = HistoryRecorder()
        self.outcome: Optional[str] = None
        self._event_engine = None

        if scenario and scenario.events:
            from ..scenarios.events import EventEngine
            self._event_engine = EventEngine(scenario.events)

    def step(self) -> bool:
        if self.outcome or self.state.month >= self.max_months:
            return False
        snap = self.state.month_step()
        self.history.record(snap)

        if self._event_engine:
            fired = self._event_engine.check_and_fire(snap.to_dict(), self.state)
            for ev in fired:
                self.state.events.append(f"M{self.state.month:03d}  📋 {ev.effect.message or ev.id}")

        if self.scenario:
            snap_d = snap.to_dict()
            for wc in self.scenario.win_conditions:
                if wc.is_met(snap_d, self.history.snapshots):
                    self.outcome = "win"
                    return False
            for lc in self.scenario.lose_conditions:
                if lc.is_met(snap_d, self.history.snapshots):
                    self.outcome = "lose"
                    return False

        if self.state.month >= self.max_months:
            self.outcome = "survive" if not self.outcome else self.outcome
        return self.outcome is None

    def run_headless(self) -> None:
        while self.step():
            pass

    def to_dict(self) -> dict:
        return {
            "state": self.state.to_dict(),
            "max_months": self.max_months,
            "outcome": self.outcome,
            "history": self.history.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationRunner":
        state = CountryState.from_dict(d["state"])
        runner = cls(state, max_months=d.get("max_months", 120))
        runner.outcome = d.get("outcome")
        runner.history = HistoryRecorder.from_dict(d.get("history", {}))
        return runner


class WorldRunner:
    def __init__(self, world: World, max_months: int = 120):
        self.world = world
        self.max_months = max_months
        self.histories = {s.name: HistoryRecorder() for s in world.states}

    def step(self) -> bool:
        if any(s.month >= self.max_months for s in self.world.states):
            return False
        snaps = self.world.month_step()
        for snap in snaps:
            state = next((s for s in self.world.states if s.month == snap.month), None)
            pass
        for s, snap in zip(self.world.states, snaps):
            self.histories[s.name].record(snap)
        return True

    def run_headless(self) -> None:
        while self.step():
            pass
