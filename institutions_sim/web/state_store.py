from __future__ import annotations
import json
from typing import Optional, Any
from ..runner.simulation import SimulationRunner
from ..runner.history import HistoryRecorder
from ..engine.state import CountryState
from ..config.schema import SimConfig, StateConfig


def runner_to_store(runner: SimulationRunner) -> dict:
    return runner.to_dict()


def store_to_runner(data: dict) -> Optional[SimulationRunner]:
    try:
        return SimulationRunner.from_dict(data)
    except Exception:
        return None


def history_from_store(data: dict) -> Optional[HistoryRecorder]:
    try:
        return HistoryRecorder.from_dict(data.get("history", {}))
    except Exception:
        return None


def create_runner_from_params(params: dict[str, Any]) -> SimulationRunner:
    sim_overrides = params.get("sim_cfg_overrides", {})
    cfg_kwargs = {
        k: v for k, v in params.items()
        if k in SimConfig.model_fields and v is not None
    }
    cfg_kwargs.update(sim_overrides)

    if "tax_rate" in params:
        cfg_kwargs["tax_rate"] = params["tax_rate"]
    if "protest_base" in params:
        cfg_kwargs["protest_base"] = params["protest_base"]
    if "coup_probability" in params:
        cfg_kwargs["coup_probability"] = params["coup_probability"]
    if "disaster_base" in params:
        cfg_kwargs["disaster_base"] = params["disaster_base"]
    if "resource_rent_share" in params:
        cfg_kwargs["resource_rent_share"] = params["resource_rent_share"]

    sim_cfg = SimConfig(**{k: v for k, v in cfg_kwargs.items()
                           if k in SimConfig.model_fields})

    seed_raw = params.get("seed", "")
    seed = int(seed_raw) if str(seed_raw).strip().isdigit() else None

    state_cfg = StateConfig(
        name=str(params.get("name", "Solaria")),
        pop=float(params.get("pop", 5_000_000)),
        tech=float(params.get("tech", 1.0)),
        elite_share=float(params.get("elite_share", 0.08)),
        EI=float(params.get("EI", 0.5)),
        PI=float(params.get("PI", 0.5)),
        max_step=float(params.get("max_step", 0.1)),
        seed=seed,
    )
    state = CountryState(state_cfg, sim_cfg)
    max_months = int(params.get("months", 120))
    return SimulationRunner(state, max_months=max_months)
