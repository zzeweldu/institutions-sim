from __future__ import annotations
from typing import Any
from dash import Input, Output, State, ctx, ALL, no_update
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table

from . import charts as C
from .state_store import runner_to_store, store_to_runner, create_runner_from_params, history_from_store
from ..scenarios.loader import load_preset


def register_callbacks(app) -> None:

    @app.callback(
        Output("sim-store", "data"),
        Output("step-counter", "children"),
        Output("outcome-badge", "children"),
        Input("btn-step", "n_clicks"),
        Input("btn-run", "n_clicks"),
        Input("btn-reset", "n_clicks"),
        Input("autorun-interval", "n_intervals"),
        State("sim-store", "data"),
        State("config-store", "data"),
        State("mode-radio", "value"),
        prevent_initial_call=True,
    )
    def control_simulation(step_clicks, run_clicks, reset_clicks,
                           _intervals, sim_data, cfg_data, mode):
        triggered = ctx.triggered_id
        if triggered == "btn-reset":
            runner = create_runner_from_params(cfg_data or {})
            return runner_to_store(runner), "M000", None

        runner = store_to_runner(sim_data) if sim_data else None
        if runner is None:
            runner = create_runner_from_params(cfg_data or {})

        if runner.outcome:
            color = "success" if runner.outcome == "win" else \
                    "danger"  if runner.outcome == "lose" else "secondary"
            badge = dbc.Badge(runner.outcome.upper(), color=color, className="ms-1")
            return no_update, f"M{runner.state.month:03d}", badge

        if triggered in ("btn-step", "autorun-interval"):
            runner.step()
        elif triggered == "btn-run":
            runner.run_headless()

        outcome = runner.outcome
        badge = None
        if outcome:
            color = "success" if outcome == "win" else \
                    "danger"  if outcome == "lose" else "secondary"
            badge = dbc.Badge(outcome.upper(), color=color, className="ms-1")

        return runner_to_store(runner), f"M{runner.state.month:03d} / {runner.max_months}", badge

    @app.callback(
        Output("autorun-interval", "disabled"),
        Input("autorun-toggle", "value"),
    )
    def toggle_autorun(enabled):
        return not enabled

    @app.callback(
        Output("log-collapse", "is_open"),
        Input("log-toggle", "n_clicks"),
        State("log-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_log(n, is_open):
        return not is_open

    @app.callback(
        Output("chart-kpi", "figure"),
        Output("chart-unrest-gauge", "figure"),
        Output("chart-ei-pi", "figure"),
        Output("chart-output", "figure"),
        Output("chart-capital", "figure"),
        Output("chart-sector-bar", "figure"),
        Output("chart-gini", "figure"),
        Output("chart-income", "figure"),
        Output("chart-budget-waterfall", "figure"),
        Output("chart-military-line", "figure"),
        Output("chart-war-timeline", "figure"),
        Output("chart-faction-power", "figure"),
        Output("chart-faction-loyalty", "figure"),
        Output("chart-faction-bubble", "figure"),
        Output("event-log", "value"),
        Input("sim-store", "data"),
    )
    def update_charts(sim_data):
        if not sim_data:
            return (C._EMPTY,) * 14 + ("No simulation data yet. Press Run or Step.",)
        h = history_from_store(sim_data)
        if h is None or not h.snapshots:
            return (C._EMPTY,) * 14 + ("No snapshots recorded yet.",)
        latest = h.latest()
        events_text = "\n".join(
            ev for s in h.snapshots[-20:] for ev in s.events
        )
        return (
            C.kpi_cards(latest),
            C.unrest_gauge(latest),
            C.ei_pi_line(h),
            C.output_log(h),
            C.capital_stocks(h),
            C.sector_bar(h),
            C.gini_line(h),
            C.income_comparison(h),
            C.budget_waterfall(latest),
            C.military_line(h),
            C.war_timeline(h),
            C.faction_power_bars(h),
            C.faction_loyalty_heatmap(h),
            C.faction_bubble(latest),
            events_text or "No events yet.",
        )

    @app.callback(
        Output("chart-world-map", "figure"),
        Input("sim-store", "data"),
    )
    def update_world_map(sim_data):
        if not sim_data:
            return C._EMPTY
        h = history_from_store(sim_data)
        latest = h.latest() if h else None
        if latest is None:
            return C._EMPTY
        runner = store_to_runner(sim_data)
        name = runner.state.name if runner else "State"
        return C.world_choropleth({name: latest}, metric="EI")

    @app.callback(
        Output("export-table-container", "children"),
        Input("sim-store", "data"),
    )
    def update_export_table(sim_data):
        if not sim_data:
            return html.P("Run a simulation to see data here.", style={"color": "#6c7086"})
        h = history_from_store(sim_data)
        if not h or not h.snapshots:
            return html.P("No data yet.", style={"color": "#6c7086"})
        recent = h.snapshots[-12:]
        cols = ["month", "EI", "PI", "Y", "unrest", "gini", "loyalty", "infra_ratio", "war_type", "protest_active"]
        rows = []
        for s in recent:
            d = s.to_dict()
            rows.append({c: round(d[c], 3) if isinstance(d[c], float) else d[c]
                         for c in cols if c in d})
        return dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in cols if rows and c in rows[0]],
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#2a2a3e", "color": "#89b4fa",
                          "fontWeight": "bold", "border": "1px solid #3a3a5e"},
            style_cell={"backgroundColor": "#1e1e2e", "color": "#cdd6f4",
                        "border": "1px solid #3a3a5e", "fontSize": "11px", "textAlign": "right"},
            style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#181825"}],
            page_size=12,
        )

    @app.callback(
        Output("download-csv", "data"),
        Input("btn-download-csv", "n_clicks"),
        State("sim-store", "data"),
        prevent_initial_call=True,
    )
    def download_csv(_, sim_data):
        if not sim_data:
            return no_update
        h = history_from_store(sim_data)
        if not h:
            return no_update
        runner = store_to_runner(sim_data)
        name = runner.state.name if runner else "simulation"
        return dcc.send_string(h.to_csv(), f"{name}_history.csv")

    @app.callback(
        Output("download-json", "data"),
        Input("btn-download-json", "n_clicks"),
        State("sim-store", "data"),
        prevent_initial_call=True,
    )
    def download_json(_, sim_data):
        if not sim_data:
            return no_update
        h = history_from_store(sim_data)
        if not h:
            return no_update
        runner = store_to_runner(sim_data)
        name = runner.state.name if runner else "simulation"
        return dcc.send_string(h.to_json(), f"{name}_history.json")

    @app.callback(
        Output("config-store", "data"),
        Input({"type": "cfg-slider", "key": ALL}, "value"),
        Input({"type": "cfg-input", "key": ALL}, "value"),
        Input("scenario-dropdown", "value"),
    )
    def update_config(slider_vals, input_vals, scenario_name):
        params: dict[str, Any] = {}
        if ctx.inputs_list:
            for item_group in ctx.inputs_list[:2]:
                if isinstance(item_group, list):
                    for item in item_group:
                        key = item["id"]["key"]
                        val = item.get("value")
                        if val is not None:
                            params[key] = val
        if scenario_name:
            try:
                spec = load_preset(scenario_name)
                ic = spec.initial_state.model_dump()
                sc = spec.sim_config.model_dump()
                for k in ("EI", "PI", "tech", "elite_share", "max_step", "pop", "name"):
                    if k in ic:
                        params[k] = ic[k]
                params["sim_cfg_overrides"] = {
                    k: v for k, v in sc.items()
                    if k not in ("targets", "sector_weights")
                }
                params["months"] = spec.max_months
            except Exception:
                pass
        return params
