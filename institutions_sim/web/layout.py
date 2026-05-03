from __future__ import annotations
import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from ..scenarios.loader import list_presets


def _slider_row(label, id_key, min_val, max_val, step, value):
    return dbc.Row([
        dbc.Col(html.Label(label, style={"fontSize": "12px", "color": "#cdd6f4"}), width=6),
        dbc.Col(dcc.Slider(
            id={"type": "cfg-slider", "key": id_key},
            min=min_val, max=max_val, step=step, value=value,
            marks=None,
            tooltip={"placement": "bottom", "always_visible": False},
        ), width=6),
    ], className="mb-1")


def _input_row(label, id_key, value, input_type="number"):
    return dbc.Row([
        dbc.Col(html.Label(label, style={"fontSize": "12px", "color": "#cdd6f4"}), width=6),
        dbc.Col(dbc.Input(
            id={"type": "cfg-input", "key": id_key},
            type=input_type, value=value, size="sm",
            style={"backgroundColor": "#2a2a3e", "color": "#cdd6f4", "border": "1px solid #3a3a5e"},
        ), width=6),
    ], className="mb-1")


def sidebar():
    presets = list_presets()
    preset_options = [{"label": "— none —", "value": ""}] + [
        {"label": p.replace("_", " ").title(), "value": p} for p in presets
    ]
    return dbc.Col([
        html.H5("Configuration", style={"color": "#89b4fa", "marginBottom": "12px"}),
        html.Label("Preset Scenario", style={"fontSize": "12px", "color": "#cdd6f4"}),
        dcc.Dropdown(id="scenario-dropdown", options=preset_options, value="",
                     clearable=False,
                     style={"backgroundColor": "#2a2a3e", "color": "#cdd6f4",
                            "border": "1px solid #3a3a5e", "marginBottom": "10px"}),
        html.Hr(style={"borderColor": "#3a3a5e"}),
        html.Label("Mode", style={"fontSize": "12px", "color": "#cdd6f4"}),
        dcc.RadioItems(id="mode-radio",
                       options=[{"label": " Sandbox", "value": "sandbox"},
                                {"label": " Research", "value": "research"},
                                {"label": " Game",    "value": "game"}],
                       value="sandbox",
                       labelStyle={"display": "block", "color": "#cdd6f4", "fontSize": "12px"},
                       style={"marginBottom": "10px"}),
        html.Hr(style={"borderColor": "#3a3a5e"}),
        html.H6("Initial State", style={"color": "#a6e3a1", "marginBottom": "8px"}),
        _input_row("Name", "name", "Solaria", "text"),
        _input_row("Population", "pop", 5_000_000),
        _slider_row("EI (start)", "EI", 0, 1, 0.01, 0.5),
        _slider_row("PI (start)", "PI", 0, 1, 0.01, 0.5),
        _slider_row("Tech (start)", "tech", 0.1, 5, 0.1, 1.0),
        _slider_row("Elite Share", "elite_share", 0.01, 0.3, 0.01, 0.08),
        _slider_row("Max Vote Step", "max_step", 0.01, 0.3, 0.01, 0.1),
        _input_row("Seed (blank=random)", "seed", "", "text"),
        html.Hr(style={"borderColor": "#3a3a5e"}),
        html.H6("Simulation", style={"color": "#a6e3a1", "marginBottom": "8px"}),
        _input_row("Months", "months", 120),
        _slider_row("Tax Rate", "tax_rate", 0.05, 0.5, 0.01, 0.2),
        _slider_row("Protest Base", "protest_base", 0.01, 0.3, 0.01, 0.05),
        _slider_row("Coup Probability", "coup_probability", 0.01, 0.2, 0.01, 0.05),
        _slider_row("Disaster Base", "disaster_base", 0.0, 0.15, 0.005, 0.03),
        _slider_row("Resource Rent Share", "resource_rent_share", 0.0, 0.5, 0.01, 0.0),
        html.Hr(style={"borderColor": "#3a3a5e"}),
        dbc.Row([
            dbc.Col(dbc.Button("▶ Run All", id="btn-run",   color="success",   size="sm", className="w-100")),
            dbc.Col(dbc.Button("⏭ Step",    id="btn-step",  color="primary",   size="sm", className="w-100")),
            dbc.Col(dbc.Button("⟳ Reset",   id="btn-reset", color="secondary", size="sm", className="w-100")),
        ], className="g-1"),
        html.Div(id="outcome-badge", className="mt-2"),
        html.Hr(style={"borderColor": "#3a3a5e"}),
        dbc.Switch(id="autorun-toggle", label="Auto-run", value=False,
                   style={"color": "#cdd6f4", "fontSize": "12px"}),
        dcc.Interval(id="autorun-interval", interval=200, n_intervals=0, disabled=True),
    ], width=2, style={
        "backgroundColor": "#181825", "padding": "16px",
        "height": "100vh", "overflowY": "auto",
        "borderRight": "1px solid #3a3a5e",
    })


def main_tabs():
    return dbc.Col([
        dbc.Tabs(id="main-tabs", active_tab="tab-overview", children=[
            dbc.Tab(label="Overview", tab_id="tab-overview", children=[
                dbc.Row([dbc.Col(dcc.Graph(id="chart-kpi", style={"height": "170px"}), width=12)], className="mt-2"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-unrest-gauge", style={"height": "220px"}), width=3),
                    dbc.Col(dcc.Graph(id="chart-ei-pi",        style={"height": "220px"}), width=5),
                    dbc.Col(dcc.Graph(id="chart-capital",      style={"height": "220px"}), width=4),
                ], className="mt-2"),
                dbc.Row([dbc.Col(dcc.Graph(id="chart-output", style={"height": "250px"}), width=12)], className="mt-2"),
            ]),
            dbc.Tab(label="Economy", tab_id="tab-economy", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-sector-bar", style={"height": "280px"}), width=6),
                    dbc.Col(dcc.Graph(id="chart-gini",       style={"height": "280px"}), width=6),
                ], className="mt-2"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-income",          style={"height": "280px"}), width=6),
                    dbc.Col(dcc.Graph(id="chart-budget-waterfall", style={"height": "280px"}), width=6),
                ], className="mt-2"),
            ]),
            dbc.Tab(label="Military", tab_id="tab-military", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-military-line", style={"height": "300px"}), width=8),
                    dbc.Col(dcc.Graph(id="chart-war-timeline",  style={"height": "300px"}), width=4),
                ], className="mt-2"),
            ]),
            dbc.Tab(label="Factions", tab_id="tab-factions", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-faction-power",   style={"height": "300px"}), width=6),
                    dbc.Col(dcc.Graph(id="chart-faction-loyalty", style={"height": "300px"}), width=6),
                ], className="mt-2"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-faction-bubble", style={"height": "280px"}), width=6),
                ], className="mt-2"),
            ]),
            dbc.Tab(label="World", tab_id="tab-world", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(id="chart-world-map", style={"height": "400px"}), width=12),
                ], className="mt-2"),
                html.P("Multi-state world view. Configure multiple states via scenario files.",
                       style={"color": "#6c7086", "fontSize": "12px", "marginLeft": "10px"}),
            ]),
            dbc.Tab(label="Export", tab_id="tab-export", children=[
                dbc.Row([dbc.Col([
                    html.H6("Download Data", style={"color": "#89b4fa", "marginTop": "12px"}),
                    dbc.ButtonGroup([
                        dbc.Button("Download CSV",  id="btn-download-csv",  color="primary", outline=True, size="sm"),
                        dbc.Button("Download JSON", id="btn-download-json", color="primary", outline=True, size="sm"),
                    ], className="mb-3"),
                    dcc.Download(id="download-csv"),
                    dcc.Download(id="download-json"),
                    html.H6("Recent History (last 12 months)", style={"color": "#89b4fa"}),
                    html.Div(id="export-table-container"),
                ], width=12)], className="mt-2 ms-2"),
            ]),
        ]),
        dbc.Collapse([
            html.Hr(style={"borderColor": "#3a3a5e", "marginTop": "10px"}),
            html.H6("Event Log", style={"color": "#f38ba8", "marginLeft": "10px"}),
            dcc.Textarea(id="event-log", readOnly=True, style={
                "width": "100%", "height": "120px",
                "backgroundColor": "#181825", "color": "#cdd6f4",
                "border": "1px solid #3a3a5e", "fontSize": "11px",
                "fontFamily": "monospace", "resize": "none",
            }),
        ], id="log-collapse", is_open=True),
        dbc.Button("▾ Event Log", id="log-toggle", color="link", size="sm",
                   style={"color": "#6c7086", "fontSize": "11px", "marginLeft": "5px"}),
    ], width=10, style={"backgroundColor": "#1e1e2e", "padding": "0 10px"})


def create_layout():
    return html.Div([
        dcc.Store(id="sim-store",    storage_type="session"),
        dcc.Store(id="config-store", storage_type="session"),
        dcc.Store(id="month-counter", data=0),
        dbc.Navbar(
            dbc.Container([
                html.A(dbc.Row([
                    dbc.Col(html.Span("🏛", style={"fontSize": "20px"})),
                    dbc.Col(dbc.NavbarBrand("institutions-sim", className="ms-2",
                                            style={"color": "#89b4fa", "fontWeight": "bold"})),
                ], align="center"), href="#"),
                html.Span(id="step-counter",
                          style={"color": "#6c7086", "fontSize": "12px", "marginLeft": "auto"}),
            ], fluid=True),
            color="#181825", dark=True,
            style={"borderBottom": "1px solid #3a3a5e", "padding": "4px 0"},
        ),
        dbc.Row([sidebar(), main_tabs()],
                style={"margin": "0", "height": "calc(100vh - 48px)", "overflow": "hidden"}),
    ], style={"backgroundColor": "#1e1e2e", "height": "100vh", "overflow": "hidden"})
