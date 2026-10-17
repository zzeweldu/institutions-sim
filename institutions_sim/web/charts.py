from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import plotly.graph_objects as go

if TYPE_CHECKING:
    from ..engine.state import MonthSnapshot
    from ..runner.history import HistoryRecorder

COLORS = {
    "EI":      "#89b4fa",
    "PI":      "#a6e3a1",
    "Y":       "#f9e2af",
    "unrest":  "#f38ba8",
    "gini":    "#cba6f7",
    "infra":   "#94e2d5",
    "loyalty": "#89dceb",
    "bg":      "#1e1e2e",
    "grid":    "#3a3a5e",
    "text":    "#cdd6f4",
}


def _base_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"], size=11),
        margin=dict(l=40, r=10, t=30, b=30),
        xaxis=dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"]),
        yaxis=dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    )
    base.update(kwargs)
    return base


_EMPTY = go.Figure(layout=_base_layout(title="No data"))


def ei_pi_line(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=h.get_series("EI"),
                             name="EI", line=dict(color=COLORS["EI"], width=2)))
    fig.add_trace(go.Scatter(x=months, y=h.get_series("PI"),
                             name="PI", line=dict(color=COLORS["PI"], width=2)))
    fig.update_layout(**_base_layout(title="Institutional Scores", yaxis_range=[0, 1]))
    return fig


def output_log(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    Y = h.get_series("Y")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=Y, name="Output",
                             fill="tozeroy",
                             line=dict(color=COLORS["Y"], width=2),
                             fillcolor="rgba(249,226,175,0.15)"))
    fig.update_layout(**_base_layout(title="Economic Output", yaxis_type="log"))
    return fig


def unrest_gauge(snap: "MonthSnapshot") -> go.Figure:
    val = snap.unrest * 100
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        gauge={
            "axis": {"range": [0, 100], "tickcolor": COLORS["text"]},
            "bar": {"color": COLORS["unrest"]},
            "bgcolor": COLORS["bg"],
            "steps": [
                {"range": [0, 40],  "color": "#2a2a3e"},
                {"range": [40, 70], "color": "#3a2a3e"},
                {"range": [70, 100], "color": "#4a2a3e"},
            ],
        },
        number={"suffix": "%", "font": {"color": COLORS["text"]}},
        title={"text": "Unrest", "font": {"color": COLORS["text"]}},
    ))
    fig.update_layout(**_base_layout(margin=dict(l=20, r=20, t=40, b=20)))
    return fig


def capital_stocks(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    for key, color, name in [
        ("tech", COLORS["EI"], "Tech"),
        ("infra", COLORS["infra"], "Infra"),
        ("pc", COLORS["PI"], "Prod. Capital"),
    ]:
        fig.add_trace(go.Scatter(x=months, y=h.get_series(key),
                                 name=name, line=dict(color=color, width=1.5)))
    fig.update_layout(**_base_layout(title="Capital Stocks"))
    return fig


def kpi_cards(snap: "MonthSnapshot") -> go.Figure:
    labels = ["EI", "PI", "Unrest", "Gini", "Loyalty"]
    values = [snap.EI, snap.PI, snap.unrest, snap.gini, snap.loyalty]
    colors = [COLORS["EI"], COLORS["PI"], COLORS["unrest"], COLORS["gini"], COLORS["loyalty"]]
    fig = go.Figure()
    for i, (label, val, color) in enumerate(zip(labels, values, colors)):
        fig.add_trace(go.Indicator(
            mode="number",
            value=round(val, 3),
            title={"text": label, "font": {"size": 11, "color": color}},
            number={"font": {"color": color, "size": 20}},
            domain={"x": [i / 5, (i + 1) / 5], "y": [0, 1]},
        ))
    fig.update_layout(**_base_layout(title="", margin=dict(l=10, r=10, t=20, b=10)))
    return fig


def sector_bar(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    for sector, color in [("agriculture", "#a6e3a1"), ("industry", "#89b4fa"), ("services", "#f9e2af")]:
        fig.add_trace(go.Bar(
            x=months, y=h.get_series(f"sector_{sector}"),
            name=sector.capitalize(), marker_color=color,
        ))
    fig.update_layout(**_base_layout(title="Sector Output", barmode="stack"))
    return fig


def gini_line(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=h.get_series("gini"),
                             name="Gini", line=dict(color=COLORS["gini"], width=2),
                             fill="tozeroy", fillcolor="rgba(203,166,247,0.15)"))
    fig.update_layout(**_base_layout(title="Gini Coefficient", yaxis_range=[0, 1]))
    return fig


def income_comparison(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    mass_pop = h.get_series("mass_pop")
    elite_pop = h.get_series("elite_pop")
    Y = h.get_series("Y")
    EI = h.get_series("EI")
    mass_inc = [y * ei / (mp + 1e-9) for y, ei, mp in zip(Y, EI, mass_pop)]
    elite_inc = [y * (1 - ei) / (ep + 1e-9) for y, ei, ep in zip(Y, EI, elite_pop)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=mass_inc, name="Mass per-cap",
                             line=dict(color=COLORS["EI"], width=2)))
    fig.add_trace(go.Scatter(x=months, y=elite_inc, name="Elite per-cap",
                             line=dict(color=COLORS["unrest"], width=2)))
    fig.update_layout(**_base_layout(title="Per-capita Income", yaxis_type="log"))
    return fig


def budget_waterfall(snap: "MonthSnapshot") -> go.Figure:
    labels = list(snap.budget_split.keys())
    vals   = [round(v * 100, 1) for v in snap.budget_split.values()]
    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker_color=[COLORS["EI"], COLORS["PI"], COLORS["Y"],
                      COLORS["unrest"], COLORS["gini"]][:len(labels)],
    ))
    fig.update_layout(**_base_layout(title="Budget Allocation (%)", yaxis_title="%"))
    return fig


def military_line(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=h.get_series("loyalty"),
                             name="Loyalty", line=dict(color=COLORS["loyalty"], width=2)))
    fig.update_layout(**_base_layout(title="Military Loyalty", yaxis_range=[0, 1]))
    return fig


def war_timeline(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    war_front = h.get_series("war_front")
    war_type  = h.get_series("war_type")
    colors = [
        "#f38ba8" if wt == "CivilWar" else "#fab387" if wt == "War" else "#2a2a3e"
        for wt in war_type
    ]
    fig = go.Figure(go.Bar(x=months, y=war_front, marker_color=colors, name="Front"))
    fig.update_layout(**_base_layout(title="War Front (red=Civil, orange=External)"))
    return fig


def faction_power_bars(h: "HistoryRecorder") -> go.Figure:
    months = h.months()
    fig = go.Figure()
    if not h.snapshots:
        fig.update_layout(**_base_layout(title="Faction Power"))
        return fig
    faction_ids = [fs["id"] for fs in h.snapshots[-1].faction_states]
    palette = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7"]
    for i, fid in enumerate(faction_ids):
        series = h.get_series(f"faction_{fid}_power")
        fig.add_trace(go.Scatter(x=months, y=series, name=fid,
                                 line=dict(color=palette[i % len(palette)], width=2)))
    fig.update_layout(**_base_layout(title="Faction Power"))
    return fig


def faction_loyalty_heatmap(h: "HistoryRecorder") -> go.Figure:
    if not h.snapshots:
        return go.Figure(layout=_base_layout(title="Faction Loyalty"))
    faction_ids = [fs["id"] for fs in h.snapshots[-1].faction_states]
    months = h.months()
    z = [[h.get_series(f"faction_{fid}_loyalty")[i] or 0 for fid in faction_ids]
         for i in range(len(months))]
    fig = go.Figure(go.Heatmap(
        z=list(zip(*z)) if z else [],
        x=months, y=faction_ids,
        colorscale="RdYlGn", zmin=0, zmax=1,
    ))
    fig.update_layout(**_base_layout(title="Faction Loyalty Heatmap"))
    return fig


def faction_bubble(snap: "MonthSnapshot") -> go.Figure:
    if not snap.faction_states:
        return go.Figure(layout=_base_layout(title="Faction Position"))
    fig = go.Figure()
    palette = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7"]
    for i, fs in enumerate(snap.faction_states):
        fig.add_trace(go.Scatter(
            x=[fs.get("power", 0)],
            y=[fs.get("loyalty", 0)],
            mode="markers+text",
            text=[fs.get("id", "")],
            marker=dict(size=20, color=palette[i % len(palette)], opacity=0.8),
            name=fs.get("id", ""),
        ))
    fig.update_layout(**_base_layout(
        title="Faction Bubble (power vs loyalty)",
        xaxis_title="Power", yaxis_title="Loyalty",
        yaxis_range=[0, 1],
    ))
    return fig


def world_choropleth(states_latest: dict[str, "MonthSnapshot"],
                     metric: str = "EI") -> go.Figure:
    names = list(states_latest.keys())
    vals  = [getattr(s, metric, 0.0) for s in states_latest.values()]
    fig = go.Figure(go.Bar(
        x=names, y=vals,
        marker_color=COLORS["EI"],
    ))
    fig.update_layout(**_base_layout(
        title=f"World Comparison — {metric}",
        yaxis_range=[0, 1] if metric in ("EI", "PI") else None,
    ))
    return fig
