from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from .schema import EventSpec

if TYPE_CHECKING:
    from ..engine.state import CountryState

_SAFE_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or,
    ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
    ast.Not, ast.USub,
)


def _safe_eval(expr: str, context: dict) -> bool:
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _SAFE_NODES):
                return False
        allowed = {k: v for k, v in context.items()
                   if isinstance(v, (int, float, bool, str))}
        return bool(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, allowed))
    except Exception:
        return False


class EventEngine:
    def __init__(self, events: list[EventSpec]):
        self.events = events

    def check_and_fire(self, snap_dict: dict, state: "CountryState") -> list[EventSpec]:
        fired = []
        for ev in self.events:
            if ev.once and ev.fired:
                continue
            triggered = False
            if ev.trigger.month is not None and snap_dict.get("month") == ev.trigger.month:
                triggered = True
            if ev.trigger.condition and _safe_eval(ev.trigger.condition, snap_dict):
                triggered = True
            if triggered:
                self._apply(ev.effect, state)
                ev.fired = True
                fired.append(ev)
        return fired

    def _apply(self, effect, state: "CountryState") -> None:
        state.EI    = max(0.0, min(1.0, state.EI    + effect.delta_EI))
        state.PI    = max(0.0, min(1.0, state.PI    + effect.delta_PI))
        state.unrest = max(0.0, min(1.0, state.unrest + effect.delta_unrest))
        state.tech  *= 1 + effect.delta_tech
        state.infra *= 1 + effect.delta_infra
        if effect.kill_fraction > 0:
            state.mass_pop  *= (1 - effect.kill_fraction)
            state.elite_pop *= (1 - effect.kill_fraction * 0.5)
        state.budget += effect.budget_inject
