#!/usr/bin/env python3
"""CLI driver for institutions-sim."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from institutions_sim.config.schema import SimConfig, StateConfig
from institutions_sim.engine.state import CountryState
from institutions_sim.runner.simulation import SimulationRunner
from institutions_sim.scenarios.loader import load_scenario, load_preset, list_presets


def main() -> None:
    p = argparse.ArgumentParser(prog="institutions-sim-cli",
                                description="Institutional dynamics CLI")
    p.add_argument("--name",   "-n", default="Solaria")
    p.add_argument("--pop",    "-p", default=5_000_000, type=float)
    p.add_argument("--tech",   "-t", default=1.0, type=float)
    p.add_argument("--ei",     default=0.5, type=float)
    p.add_argument("--pi",     default=0.5, type=float)
    p.add_argument("--elite-share", default=0.08, type=float)
    p.add_argument("--months", "-m", default=120, type=int)
    p.add_argument("--max-step", default=0.1, type=float)
    p.add_argument("--seed",   type=int)
    p.add_argument("--scenario",      help="path to scenario JSON file")
    p.add_argument("--scenario-name", help="built-in preset name")
    p.add_argument("--list-presets",  action="store_true")
    p.add_argument("--export-csv",    metavar="FILE")
    p.add_argument("--export-json",   metavar="FILE")
    p.add_argument("--cfg",           help="JSON dict of SimConfig overrides")
    p.add_argument("--quiet", "-q",   action="store_true")
    p.add_argument("--sweep", nargs=4, metavar=("KEY", "LO", "HI", "N"),
                   help="parameter sweep: KEY LO HI N")
    args = p.parse_args()

    if args.list_presets:
        for name in list_presets():
            print(name)
        return

    if args.sweep:
        key, lo, hi, n = args.sweep[0], float(args.sweep[1]), float(args.sweep[2]), int(args.sweep[3])
        import numpy as np
        vals = [lo + (hi - lo) * i / max(1, n - 1) for i in range(n)]
        all_rows: list[str] = []
        header_written = False
        for val in vals:
            runner = _build_runner(args, {key: val})
            runner.run_headless()
            for row in runner.history._rows():
                row[key] = val
                if not header_written:
                    all_rows.append(",".join(str(k) for k in row.keys()))
                    header_written = True
                all_rows.append(",".join(str(v) for v in row.values()))
        out = "\n".join(all_rows)
        if args.export_csv:
            Path(args.export_csv).write_text(out)
        else:
            print(out)
        return

    scenario = None
    if args.scenario:
        scenario = load_scenario(args.scenario)
    elif args.scenario_name:
        scenario = load_preset(args.scenario_name)

    runner = _build_runner(args, {}, scenario)

    while runner.step():
        if not args.quiet:
            s = runner.state
            h = runner.history.latest()
            print(
                f"M{s.month:03d}  EI={s.EI:.3f}  PI={s.PI:.3f}  "
                f"Y={h.Y:,.0f}  unrest={s.unrest:.3f}  "
                f"war={'yes' if s.war else 'no'}"
            )

    if runner.outcome:
        print(f"\nOutcome: {runner.outcome.upper()}")

    if args.export_csv:
        Path(args.export_csv).write_text(runner.history.to_csv())
        print(f"CSV saved to {args.export_csv}")
    if args.export_json:
        Path(args.export_json).write_text(runner.history.to_json())
        print(f"JSON saved to {args.export_json}")


def _build_runner(args, overrides: dict, scenario=None) -> SimulationRunner:
    cfg_overrides: dict = {}
    if getattr(args, "cfg", None):
        cfg_overrides.update(json.loads(args.cfg))
    cfg_overrides.update(overrides)

    if scenario:
        sim_cfg = scenario.sim_config.apply_overrides(cfg_overrides)
        state_cfg = scenario.initial_state
        max_months = scenario.max_months
    else:
        sim_cfg = SimConfig().apply_overrides(cfg_overrides)
        state_cfg = StateConfig(
            name=args.name,
            pop=args.pop,
            tech=args.tech,
            EI=args.ei,
            PI=args.pi,
            elite_share=args.elite_share,
            max_step=args.max_step,
            seed=args.seed,
        )
        max_months = args.months

    state = CountryState(state_cfg, sim_cfg)
    return SimulationRunner(state, max_months=max_months, scenario=scenario)


if __name__ == "__main__":
    main()
