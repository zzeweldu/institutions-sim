from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .state import CountryState, MonthSnapshot


@dataclass
class TradeLink:
    source: str
    target: str
    volume: float = 1.0


class World:
    def __init__(self, states: list[CountryState],
                 trade_links: Optional[list[TradeLink]] = None,
                 adjacency: Optional[dict[str, list[str]]] = None):
        self.states = states
        self.trade_links = trade_links or []
        self.adjacency = adjacency or {}

    def _apply_trade(self) -> None:
        state_map = {s.name: s for s in self.states}
        for link in self.trade_links:
            src = state_map.get(link.source)
            tgt = state_map.get(link.target)
            if src is None or tgt is None:
                continue
            volume = link.volume * src.month_output if hasattr(src, "month_output") else 0
            flow = src.sim_cfg.trade_multiplier * src.pc * link.volume
            if src.unrest > 0.6:
                flow *= 0.5
            tgt.budget += flow

    def _apply_contagion(self) -> None:
        state_map = {s.name: s for s in self.states}
        for name, neighbors in self.adjacency.items():
            state = state_map.get(name)
            if state is None:
                continue
            for nb_name in neighbors:
                nb = state_map.get(nb_name)
                if nb and nb.unrest > 0.6:
                    contagion = nb.sim_cfg.contagion_strength * (nb.unrest - 0.6)
                    state.unrest = min(1.0, state.unrest + contagion * 0.01)

    def _check_invasions(self) -> None:
        state_map = {s.name: s for s in self.states}
        for attacker in self.states:
            if attacker.unrest > 0.3 or attacker.war:
                continue
            for defender_name in self.adjacency.get(attacker.name, []):
                defender = state_map.get(defender_name)
                if defender is None or defender.war:
                    continue
                att_str = attacker.mil.strength()
                def_str = defender.mil.strength()
                if att_str > 1.5 * def_str:
                    from .war import War
                    defender.events.append(
                        f"M{defender.month:03d}  🔥 Invaded by {attacker.name}"
                    )
                    defender.war = War(defender, enemy_str=att_str)
                    break

    def month_step(self) -> list[MonthSnapshot]:
        self._apply_trade()
        self._apply_contagion()
        self._check_invasions()
        return [s.month_step() for s in self.states]

    def to_dict(self) -> dict:
        return {
            "states": [s.to_dict() for s in self.states],
            "trade_links": [
                {"source": t.source, "target": t.target, "volume": t.volume}
                for t in self.trade_links
            ],
            "adjacency": self.adjacency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "World":
        states = [CountryState.from_dict(sd) for sd in d.get("states", [])]
        trade_links = [
            TradeLink(**tl) for tl in d.get("trade_links", [])
        ]
        return cls(states, trade_links, d.get("adjacency", {}))
