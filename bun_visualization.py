"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import bun_constants as C
from bun_evaluation import de

PALETTE = ["#1f6fb2", "#2a9d8f", "#8e44ad", "#d35400", "#16a085", "#7f8c8d", "#2c3e50", "#b03a2e", "#117a65", "#6c3483", "#af601a", "#1b4f72"]


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=380, legend_y=-0.25):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=legend_y), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_time_space(trace, window, n_stops, n_buses, title=None):
    """Zeit-Weg-Diagramm: Ringposition (Haltestelle) gegen Zeit, ein Streckenzug je Bus. Waagerechte Stücke sind Halte (Haltezeit und Holding), schräge die Fahrt.
    An der Ringnaht (letzte → erste Haltestelle) wird der Zug unterbrochen."""
    w0, w1 = window
    by_bus = {b: [] for b in range(n_buses)}
    for b, j, ta, dep in sorted(trace, key=lambda e: (e[0], e[2])):
        by_bus[b].append((j, ta, dep))
    fig = go.Figure()
    for b in range(n_buses):
        xs, ys = [], []
        prev = None
        for j, ta, dep in by_bus[b]:
            if prev is not None and j < prev:
                xs.append(None)
                ys.append(None)
            xs += [ta - w0, dep - w0]
            ys += [j + 1, j + 1]
            prev = j
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=PALETTE[b % len(PALETTE)], width=2), name=f"Bus {b + 1}", showlegend=n_buses <= 8,
                                 hovertemplate=f"Bus {b + 1}<br>Haltestelle %{{y}}<br>%{{x:.0f}} min nach Fensterbeginn<extra></extra>"))
    fig.update_xaxes(title="Minuten im Fenster", range=[0, w1 - w0])
    fig.update_yaxes(title="Haltestelle (Ring)", range=[0.5, n_stops + 0.5], dtick=4)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=13), x=0.02, y=0.98))
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    fig.update_layout(height=430, legend=dict(orientation="h", y=-0.2), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_cv_curves(curves, independent_cv=None):
    """Variationskoeffizient der Abstände über die Zeit je Strategie (Mittel über die Zufalls-Seeds, gleitende Stunde); gepunktet: Pulk-Schwelle und CV unabhängiger Busse."""
    fig = go.Figure()
    for key, (xs, ys) in curves.items():
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=C.STRATEGY_COLOR[key], width=3), name=C.STRATEGIES[key]["label"],
                                 hovertemplate="%{x:.1f} h: CV %{y:.2f}<extra></extra>"))
    fig.add_hline(y=C.PULSE_CV, line=dict(color=C.COLOR_IDEAL, dash="dot"), annotation_text=f"Pulk (CV {de(C.PULSE_CV)})", annotation_position="top left", annotation_bgcolor="rgba(255,255,255,0.7)")
    if independent_cv is not None:
        fig.add_hline(y=independent_cv, line=dict(color=C.COLOR_IDEAL, dash="dash"), annotation_text="unabhängige Busse", annotation_position="bottom left", annotation_bgcolor="rgba(255,255,255,0.7)")
    fig.update_xaxes(title="Zeit seit Betriebsbeginn (h)")
    fig.update_yaxes(title="Variationskoeffizient der Abstände", rangemode="tozero")
    return _base(fig, 360)


def build_cost_bars(a):
    """Warten und Fahren je Strategie (Mittel über die Zufalls-Seeds) übereinander, daneben die Umlaufzeit als Beschriftung."""
    keys = a.strategies
    labels = [f"{C.STRATEGIES[k]['label']}<br>Umlaufzeit {de(a.stat(k, 'cycle')[0], 0)} min" for k in keys]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[a.stat(k, "wait")[0] for k in keys], name="Warten", marker_color="#c8872b", text=[de(a.stat(k, "wait")[0]) for k in keys], textposition="inside"))
    fig.add_trace(go.Bar(x=labels, y=[a.stat(k, "ride")[0] for k in keys], name="Fahren im Bus", marker_color="#4c78a8", text=[de(a.stat(k, "ride")[0]) for k in keys], textposition="inside"))
    fig.add_hline(y=a.h0 / 2, line=dict(color=C.COLOR_IDEAL, dash="dot"), annotation_text="Warten bei gleichmäßigem Takt", annotation_position="top left", annotation_bgcolor="rgba(255,255,255,0.7)")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="Minuten je Fahrgast")
    return _base(fig, 400, legend_y=-0.35)


# ------------------------------------------------------------------------------------------------------------------ Messreihe
def build_sigma_curve(rows_by_label):
    """Anteil der Zufalls-Seeds mit Pulk (CV der Abstände über 1,2) nach 7 Stunden gegen die Last σ, ohne Regelung: eine stetige S-Kurve, kein scharfer Einsatz."""
    fig = go.Figure()
    for (label, rows), color in zip(rows_by_label.items(), (C.COLOR_NONE, C.COLOR_SCHED)):
        fig.add_trace(go.Scatter(x=[r["sigma"] for r in rows], y=[r["anteil_cv_ueber_1_2_bei_7h"]["p"] for r in rows], mode="lines+markers", name=label, line=dict(color=color, width=3),
                                 customdata=[f"{r['anteil_cv_ueber_1_2_bei_7h']['k']} von {r['anteil_cv_ueber_1_2_bei_7h']['n']}" for r in rows],
                                 hovertemplate="σ %{x:.2f}: %{y:.0%} der Zufalls-Seeds (%{customdata})<extra></extra>"))
    fig.add_hline(y=0.5, line=dict(color=C.COLOR_IDEAL, dash="dot"))
    fig.update_xaxes(title="Last σ")
    fig.update_yaxes(title="Anteil der Zufalls-Seeds mit Pulk nach 7 h", tickformat=".0%", range=[0, 1.02])
    return _base(fig, 360)


def build_collapse(series, labels, keys=("none", "hw1_10", "sched1_10", "sched1_20")):
    """Wartezeit (logarithmische Achse) gegen die Last σ für vier Strategien (B = 8, stationär); gepunktet: σ = 1, wo ein einzelner Bus den Einsteige-Aufwand nicht mehr schafft."""
    fig = go.Figure()
    colors = {"none": C.COLOR_NONE, "hw1_10": C.COLOR_HW, "sched1_10": C.COLOR_SCHED, "sched1_20": "#8fb3d9"}
    for k in keys:
        fig.add_trace(go.Scatter(x=[r["sigma"] for r in series], y=[r["wartezeit"][k]["mean"] for r in series], mode="lines+markers", name=labels[k], line=dict(color=colors[k], width=3),
                                 hovertemplate="σ %{x:.2f}: %{y:.1f} min<extra></extra>"))
    fig.add_vline(x=1.0, line=dict(color=C.COLOR_IDEAL, dash="dot"), annotation_text="σ = 1", annotation_position="top", annotation_bgcolor="rgba(255,255,255,0.7)")
    fig.update_xaxes(title="Last σ")
    fig.update_yaxes(title="Wartezeit (min, logarithmisch)", type="log")
    return _base(fig, 380)


def build_buses_curve(tables, bus_counts, labels, keys=("none", "sched1_10", "hw1_10")):
    """Gesamtreisezeit (Warten + Fahren) gegen die Zahl der Busse bei gleicher Soll-Umlaufzeit; bei vielen Bussen schlägt „ohne Regelung“ jedes Holding."""
    fig = go.Figure()
    colors = {"none": C.COLOR_NONE, "sched1_10": C.COLOR_SCHED, "hw1_10": C.COLOR_HW}
    for k in keys:
        pts = [tables[f"{b}/{k}"]["total"] for b in bus_counts]
        fig.add_trace(go.Scatter(x=list(bus_counts), y=[p["mean"] for p in pts], error_y=dict(type="data", array=[p["se"] for p in pts], visible=True), mode="lines+markers", name=labels[k],
                                 line=dict(color=colors[k], width=3), hovertemplate="%{x} Busse: %{y:.1f} min<extra></extra>"))
    fig.update_xaxes(title="Busse (Soll-Umlaufzeit 60 min)", type="log", tickvals=list(bus_counts), ticktext=[str(b) for b in bus_counts])
    fig.update_yaxes(title="Gesamtreisezeit (min)")
    return _base(fig, 380)


def build_heatmap(area, optimum_key=None):
    """Fläche der Gesamtreisezeit über Kontrollhaltestellen-Dichte c und Puffer des Fahrplan-Holdings (Test-Seeds): Sie ist flach rund um das Optimum."""
    fig = go.Figure(go.Heatmap(x=[f"{100 * p:g} %".replace(".", ",") for p in area["puffer"]], y=[f"jede {c}." if c > 1 else "jede" for c in area["c"]],
                               z=area["gesamtreisezeit_mittel"], colorscale="Viridis_r", colorbar=dict(title="Gesamtreisezeit (min)", thickness=12),
                               hovertemplate="Puffer %{x}, Kontrollhaltestelle %{y}: %{z:.1f} min<extra></extra>"))
    fig.update_xaxes(title="Puffer des Fahrplan-Holdings", type="category")
    fig.update_yaxes(title="Kontrollhaltestelle", type="category")
    return _base(fig, 360)
