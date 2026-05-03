from __future__ import annotations
import json
from typing import Optional
from ..engine.state import MonthSnapshot


class HistoryRecorder:
    def __init__(self) -> None:
        self.snapshots: list[MonthSnapshot] = []

    def record(self, snap: MonthSnapshot) -> None:
        self.snapshots.append(snap)

    def latest(self) -> Optional[MonthSnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    def months(self) -> list[int]:
        return [s.month for s in self.snapshots]

    def get_series(self, key: str) -> list:
        result = []
        for s in self.snapshots:
            d = s.to_dict()
            result.append(d.get(key))
        return result

    def _rows(self) -> list[dict]:
        rows = []
        for s in self.snapshots:
            d = s.to_dict()
            d.pop("events", None)
            rows.append(d)
        return rows

    def to_csv(self) -> str:
        rows = self._rows()
        if not rows:
            return ""
        cols = list(rows[0].keys())
        lines = [",".join(cols)]
        for row in rows:
            lines.append(",".join(str(row.get(c, "")) for c in cols))
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self._rows(), indent=2)

    def to_dict(self) -> dict:
        return {"snapshots": [s.to_dict() for s in self.snapshots]}

    @classmethod
    def from_dict(cls, d: dict) -> "HistoryRecorder":
        rec = cls()
        for sd in d.get("snapshots", []):
            snap = _snap_from_dict(sd)
            rec.snapshots.append(snap)
        return rec


def _snap_from_dict(d: dict) -> MonthSnapshot:
    sector_output = {}
    budget_split = {}
    faction_states = []

    for k, v in d.items():
        if k.startswith("sector_"):
            sector_output[k[7:]] = v
        elif k.startswith("budget_"):
            budget_split[k[7:]] = v

    fids = set()
    for k in d:
        if k.startswith("faction_") and k.endswith("_power"):
            fids.add(k[8:-6])
    for fid in sorted(fids):
        faction_states.append({
            "id": fid,
            "power": d.get(f"faction_{fid}_power", 0.0),
            "loyalty": d.get(f"faction_{fid}_loyalty", 0.0),
        })

    events_raw = d.get("events", "")
    events = events_raw.split("|") if isinstance(events_raw, str) and events_raw else []

    return MonthSnapshot(
        month=d["month"], EI=d["EI"], PI=d["PI"], Y=d["Y"],
        unrest=d["unrest"], gini=d.get("gini", 0.0),
        mass_pop=d.get("mass_pop", 0.0), elite_pop=d.get("elite_pop", 0.0),
        infra=d.get("infra", 0.0), tech=d.get("tech", 1.0),
        pc=d.get("pc", 0.0), sec=d.get("sec", 0.0),
        infra_ratio=d.get("infra_ratio", 1.0),
        loyalty=d.get("loyalty", 1.0),
        war_front=d.get("war_front", 0.0),
        war_type=d.get("war_type", "none"),
        protest_active=d.get("protest_active", False),
        sector_output=sector_output,
        budget_split=budget_split,
        faction_states=faction_states,
        events=events,
    )
