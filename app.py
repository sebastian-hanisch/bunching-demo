"""Bus-Bunching: wie lange hält der Takt? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Auf einer Ringlinie wird ein gleichmäßiger Takt von selbst instabil: Ein verspäteter Bus trifft mehr Wartende, hält länger und wird noch später, der Bus dahinter holt auf.
Live ein Szenario im Zeit-Weg-Diagramm, ohne Regelung gegen eine Haltestrategie, daneben die vorgerechnete Messreihe über 30 Zufalls-Seeds.

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import bun_constants as C
import bun_evaluation as ev
import bun_results as Rs
import bun_theory as TH
from bun_evaluation import Settings, de
from bun_layout import dunkles_design, kopf_css
from bun_pdf_export import build_report
from bun_presets import (
    SETTING_SPECS,
    allowed_windows,
    fix_state,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)
from bun_visualization import (
    build_buses_curve,
    build_collapse,
    build_cost_bars,
    build_cv_curves,
    build_heatmap,
    build_sigma_curve,
    build_time_space,
)

st.set_page_config(page_title="Bus-Bunching – Sebastian Hanisch", layout="wide")


@st.cache_resource(show_spinner=False, max_entries=10)
def _analysis(s: Settings):
    return ev.analyse(s)


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in bun_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🚌 Bus-Bunching: wie lange hält der Takt?")
st.markdown(
    """
Auf einer Ringlinie ist ein **gleichmäßiger Takt instabil**: Kommt ein Bus etwas später, warten an der nächsten Haltestelle mehr Fahrgäste, der Halt dauert länger, der Bus wird noch später, und der Bus dahinter holt auf.
Aus kleinen Störungen werden **Pulke**, und die Fahrgäste warten ein Vielfaches des Solls. Die Demo rechnet live ein Szenario (Last, Störung, Busse, Platzgrenze) im **Zeit-Weg-Diagramm**, ohne Regelung gegen eine **Haltestrategie**,
und zeigt daneben die **vorgerechnete Messreihe** über 30 Zufalls-Seeds.

Weiter unten: **📐 Wie lange hält der Takt?**, **💰 Was kostet das Halten?**, **📊 Was die Messreihe über 30 Zufalls-Seeds zeigt** und der Expander **🔧 Wie wir das erreichen**.
Nachbarn: das feste Liniennetz der [ÖPNV-Liniennetz-Demo](https://sebastianhanisch-transit-demo.streamlit.app/), der [Taktfahrplan](https://sebastianhanisch-taktfahrplan-demo.streamlit.app/), der [Rufbus](https://sebastianhanisch-rufbus-demo.streamlit.app/) und die [Tarifplanung](https://sebastianhanisch-tarif-demo.streamlit.app/).
"""
)

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()
fix_state()


def _window_label(w):
    return f"Stunden {w * C.WINDOW_HOURS} bis {(w + 1) * C.WINDOW_HOURS}"


with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Haltestrategie**")
    strategy = st.selectbox("Strategie", tuple(C.STRATEGIES), key="strategy_select", format_func=lambda k: C.STRATEGIES[k]["label"],
                            help="Eine benannte Variante; jede ist in der Messreihe einzeln gemessen. Die „Feldregel“ (nur jede dritte Haltestelle, kurze Obergrenze) ist die Gegenprobe: „nahe am Optimum“ gilt nur für vernünftige Regeln.")
    st.markdown("**Linie und Verkehr**")
    load = st.selectbox("Last σ (Einsteige-Aufwand der Linie)", C.LOAD_CHOICES, key="load_select", format_func=lambda v: f"σ {de(v, 2)}",
                        help="σ = Haltestellen · Zustiegszeit · Fahrgastrate: wie viel Haltezeit je Minute die ganze Linie fürs Einsteigen braucht. Bei σ ≈ 1 schafft ein einzelner Bus das nicht mehr: Zusammenbruch. ρ = σ / Busse (steht unter „Linie und Annahmen“).")
    noise = st.selectbox("Störung der Fahrzeiten", tuple(C.NOISE_CHOICES), key="noise_select", format_func=lambda k: C.NOISE_LABELS[k],
                         help="Streuung der Fahrzeit je Segment, unabhängig von Segment zu Segment (Praxis: meist korreliert, das beschleunigt das Bunching). Die Wirkung ist nicht monoton.")
    buses = st.selectbox("Busse (Soll-Umlaufzeit 60 min)", C.BUSES_CHOICES, key="buses_select", format_func=lambda b: f"{b} Busse, Soll-Takt {de(60 / b, 1)} min",
                         help="Bei 24 Bussen steht rechnerisch ein Bus je Haltestelle: Dann schadet das Halten.")
    capacity = st.selectbox("Platzgrenze je Bus", C.CAPACITY_CHOICES, key="capacity_select", format_func=lambda k: C.CAPACITY_LABELS[k],
                            help="Mit Platzgrenze bleiben Fahrgäste an der Haltestelle zurück. Bei 50 Plätzen ist die Linie voll besetzt: Halten verschlechtert die Lage. Die Zahlen ohne Grenze sind Obergrenzen.")
    horizon = st.selectbox("Betrachtung", tuple(C.HORIZONS), key="horizon_select", format_func=lambda k: C.HORIZON_LABELS[k],
                           help="Ohne Regelung gibt es in einer Schicht keinen stationären Zustand; 40 Stunden zeigen, wohin es läuft.")
    window = st.selectbox("Zeitfenster des Diagramms", allowed_windows(horizon), key="window_select", format_func=_window_label,
                          help="Welche drei Stunden das Zeit-Weg-Diagramm zeigt; die Kennzahlen gelten für den ganzen Zeitraum nach der Einschwingzeit.")
    seed = st.number_input("Zufalls-Seed des Szenarios", *(SETTING_SPECS["seed_input"].lo, SETTING_SPECS["seed_input"].hi), key="seed_input", step=1)
    st.button("🎲 Neues Szenario generieren", width="stretch", on_click=randomize_seed)

sync_query_params({k: st.session_state[k] for k in SETTING_SPECS})

settings = Settings(strategy=strategy, load=float(load), noise=noise, buses=int(buses), capacity=capacity, horizon=horizon, window=int(window), seed=int(seed))

with st.spinner(f"Simuliere {len(ev.strategies_for(settings))} Strategien über {C.LIVE_SEEDS} Zufalls-Seeds …"):
    a = _analysis(settings)
p = a.params
h0, D0, m = ev.derived(p)

with st.expander("📍 Linie und Annahmen (aus den Reglern abgeleitet)"):
    st.dataframe(pd.DataFrame([
        {"Größe": "Haltestellen / Busse", "Wert": f"{p.N} / {p.B}"},
        {"Größe": "Soll-Takt h0 = Soll-Umlaufzeit / Busse", "Wert": f"{de(h0, 2)} min"},
        {"Größe": "Zustiegszeit je Fahrgast s", "Wert": f"{de(p.s, 3)} min"},
        {"Größe": "mittlere Haltezeit bei gleichmäßigem Takt", "Wert": f"{de(D0, 2)} min"},
        {"Größe": "reine Fahrzeit je Segment m", "Wert": f"{de(m, 2)} min"},
        {"Größe": "κ = s · λ (Verstärkung je Halt)", "Wert": de(p.lam_s, 3)},
        {"Größe": "σ = N · κ, ρ = σ / B", "Wert": f"{de(p.sigma, 2)}, {de(p.sigma / p.B, 3)}"},
    ]), width="stretch", hide_index=True)
    st.caption(f"Fahrgäste: {de(C.LAM, 1)} je Haltestelle und Minute, Ziel gleichverteilt (mittlere Fahrt {p.N // 2} Halte). Fahrzeit-Störung: Erlang mit Form {p.erlang_k}. Kennzahlen: Mittel über {C.LIVE_SEEDS} Zufalls-Seeds ab {settings.seed}.")

# --- Ihr Szenario --------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ihr Szenario")
w0, w1 = a.window
right = settings.strategy if settings.strategy != "none" else "hw10"
st.caption(f"Zeit-Weg-Diagramm der Stunden {int(w0 // 60)} bis {int(w1 // 60)} (Zufalls-Seed {settings.seed}): Jede Linie ist ein Bus, waagerechte Stücke sind Halte (Haltezeit und Holding). Gleiche Zufallszahlen in beiden Feldern.")
dl, dr = st.columns(2)
with dl:
    st.markdown("**Ohne Regelung**")
    st.plotly_chart(build_time_space(a.trace["none"], a.window, p.N, p.B), width="stretch", key="ts_none")
with dr:
    st.markdown(f"**{C.STRATEGIES[right]['label']}**" + (" (zum Vergleich)" if settings.strategy == "none" else ""))
    st.plotly_chart(build_time_space(a.trace[right], a.window, p.N, p.B), width="stretch", key="ts_right")

kind, text = ev.verdict(a)
getattr(st, kind)(text)

mc1, mc2, mc3 = st.columns(3)
s_key = settings.strategy
mc1.metric("Wartezeit", f"{de(a.stat(s_key, 'wait')[0])} min", delta=f"{de(a.stat(s_key, 'wait')[0] - a.stat('none', 'wait')[0])} gegen ohne Regelung", delta_color="inverse",
           help=f"Mittel über {C.LIVE_SEEDS} Zufalls-Seeds, nach der Einschwingzeit. Gleichmäßiger Takt: {de(h0 / 2, 2)} min.")
mc2.metric("Gesamtreisezeit (Warten + Fahren)", f"{de(a.stat(s_key, 'total')[0])} min", delta=f"{de(a.stat(s_key, 'total')[0] - a.stat('none', 'total')[0])} gegen ohne Regelung", delta_color="inverse",
           help="Wartezeit plus Fahrzeit im Bus.")
mc3.metric("Umlaufzeit", f"{de(a.stat(s_key, 'cycle')[0], 0)} min", delta=f"{de(a.stat(s_key, 'cycle')[0] - a.stat('none', 'cycle')[0], 0)} gegen ohne Regelung", delta_color="inverse",
           help=f"Der Preis des Haltens. Soll-Umlaufzeit {de(p.T0, 0)} min.")

rows = []
for key in a.strategies:
    w, w_se = a.stat(key, "wait")
    cv, _ = a.stat(key, "cv")
    rows.append({"Strategie": C.STRATEGIES[key]["label"], "Wartezeit (min)": f"{de(w)} ± {de(w_se)}", "Fahrzeit im Bus (min)": de(a.stat(key, "ride")[0]), "Gesamt (min)": de(a.stat(key, "total")[0]),
                 "CV der Abstände": de(cv, 2), "Wartezeit > 1,5 · Soll-Takt (%)": de(100 * a.stat(key, "long")[0], 0), "Umlaufzeit (min)": de(a.stat(key, "cycle")[0], 0),
                 "Halt über Mindesthalt (min)": de(a.stat(key, "hold")[0], 2)})
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
st.caption("Mittel ± Standardfehler über die Zufalls-Seeds. „Anteil gebündelt“ fehlt mit Absicht: Bei Headway-Holding ist er per Konstruktion null und sagt nichts.")

# --- Wie lange hält der Takt? -------------------------------------------------------------------------------------------------------------

st.markdown("## 📐 Wie lange hält der Takt?")
curves = {k: ev.cv_curve(a.runs, k) for k in a.strategies}
th = ev.theory(a)
st.plotly_chart(build_cv_curves(curves, th["independent_cv"]), width="stretch", key="cv_curves")
t_none, share_none = ev.time_to_pulse(a.runs, "none")
st.markdown(
    f"**Ohne Regelung** überschreitet der Variationskoeffizient der Abstände {de(C.PULSE_CV)} (Pulk) "
    + (f"im Median nach **{de(t_none)} h**" if t_none is not None else "in weniger als der Hälfte der Läufe")
    + f" ({de(100 * share_none, 0)} % der Zufalls-Seeds erreichen ihn im betrachteten Zeitraum). Es gibt **keinen scharfen Einsatz**: Die Kurve steigt stetig mit der Last. "
    f"Selbst ohne jede Rückkopplung (σ = 0) laufen {p.B} unabhängige Busse auseinander (CV {de(th['independent_cv'], 2)}); die Rückkopplung verschärft und beschleunigt das nur."
)
tc1, tc2, tc3 = st.columns(3)
tc1.metric("Wachstumsrate der Abstandsabweichung", f"{de(th['growth'], 2)} je Stunde", help="Aus der linearen Stabilitätsrechnung (Verzug um N/B Halte berücksichtigt): Eine kleine Abweichung wächst um diesen Faktor im Exponenten je Stunde.")
tc2.metric("Umlaufzeit eines dichten Konvois", "unendlich" if th["convoy"] == float("inf") else f"{de(th['convoy'], 0)} min", help="Obergrenze für den freien Betrieb: Fahren alle Busse zusammen, nimmt der erste alle Wartenden mit. Bei σ = 1 + κ wird sie unendlich.")
tc3.metric("Gleichgewichtstakt (ohne Störung)", f"{de(th['h_eq'], 2)} min", help="Gleichmäßiger Takt mit Rückkopplung (erwartete Fahrgastzahlen): weicht leicht vom Soll-Takt ab, weil die Haltezeit an den Wartenden hängt (Fahrgäste, die während des Halts eintreffen, verlängern ihn nicht).")
hb = a.stat("none", "wait")[0]
st.caption(f"Wartezeit-Paradox: Bei zufällig eintreffenden Fahrgästen wartet man im Mittel h̄ (1 + CV²) / 2 statt h̄ / 2. Ohne Regelung gemessen: {de(hb)} min; mit dem gemessenen CV {de(a.stat('none', 'cv')[0], 2)} "
           f"und h̄ ≈ {de(a.stat('none', 'hbar')[0])} min ergibt die Formel {de(TH.mean_wait_formula(a.stat('none', 'hbar')[0], a.stat('none', 'cv')[0]))} min (nicht exakt, weil Haltezeit und Fahrgäste während des Halts hineinspielen).")

# --- Was kostet das Halten? ---------------------------------------------------------------------------------------------------------------

st.markdown("## 💰 Was kostet das Halten?")
st.plotly_chart(build_cost_bars(a), width="stretch", key="cost_bars")
st.markdown(
    "Halten spart Wartezeit und kostet **Umlaufzeit**: Der Bus steht an Haltestellen, bis der Abstand stimmt. Ob sich das lohnt, sagt die **Gesamtreisezeit** (Warten plus Fahren). "
    "Bei sehr vielen Bussen (24, ein Bus je Haltestelle) und bei voll besetzten Bussen hebt die längere Fahrzeit den Gewinn auf: Das zeigen die Presets „Zu viele Busse“ und „Volle Busse“."
)

st.markdown("## 📊 Was die Messreihe über 30 Zufalls-Seeds zeigt")
st.caption("Vorgerechnet, kein Rechnen im Browser: Ringlinie mit 24 Haltestellen, Soll-Umlaufzeit 60 min, 30 Zufalls-Seeds je Zelle, Mittel ± Standardfehler. Die Messreihe gilt für ihre Basiseinstellung "
           "(8 Busse, Störung mittel, σ 0,48, unbegrenzte Plätze) und die vorgerechneten Abweichungen davon, nicht für die Regler der Seitenleiste.")

st.markdown("### Der Takt zerfällt stetig, nicht schlagartig")
rows6, rows25 = Rs.sigma_table(6), Rs.sigma_table(25)
st.plotly_chart(build_sigma_curve({"Störung mittel (cv ≈ 0,41)": rows6, "Störung schwach (cv 0,2)": rows25}), width="stretch", key="series_sigma")
mid = None
for r0, r1 in zip(rows6, rows6[1:]):
    p0, p1 = r0["anteil_cv_ueber_1_2_bei_7h"]["p"], r1["anteil_cv_ueber_1_2_bei_7h"]["p"]
    if p0 < 0.5 <= p1:
        mid = r0["sigma"] + (r1["sigma"] - r0["sigma"]) * (0.5 - p0) / (p1 - p0)
base_row = rows6[0]
st.markdown(
    f"Anteil der Zufalls-Seeds, in denen der Variationskoeffizient der Abstände nach 7 Stunden über {de(C.PULSE_CV)} liegt, ohne Regelung: {', '.join(de(100 * r['anteil_cv_ueber_1_2_bei_7h']['p'], 0) + ' %' for r in rows6[1:6])} "
    f"bei σ = {', '.join(de(r['sigma'], 2) for r in rows6[1:6])}. Die Mitte der Kurve liegt bei σ ≈ {de(mid, 2)}; **einen scharfen Einsatz gibt es nicht**. Selbst ohne jede Rückkopplung (σ = 0) streuen die Abstände von selbst: "
    f"CV {de(base_row['cv_18_24h']['mean'], 2)} nach 18 bis 24 h (unabhängige Busse: {de(TH.independent_bus_cv(8), 2)}). Die Rückkopplung beschleunigt und verschärft das nur."
)
st.dataframe(pd.DataFrame([{"σ": de(r["sigma"], 2), "ρ = σ / B": de(r["rho"], 3), "Wachstum je Stunde (Theorie)": de(r["wachstum_je_h"], 2), "CV 0–4 h": Rs.stat_text(r["cv_0_4h"], 2), "CV 6,5–7,5 h": Rs.stat_text(r["cv_6_5_7_5h"], 2),
                            "CV 18–24 h": Rs.stat_text(r["cv_18_24h"], 2), "Wartezeit 18–24 h (min)": Rs.stat_text(r["wait_18_24h"]), "Seeds mit Pulk nach 7 h": Rs.share_text(r["anteil_cv_ueber_1_2_bei_7h"])} for r in rows6]),
             width="stretch", hide_index=True)

st.markdown("### Scharf ist erst der Zusammenbruch bei σ ≈ 1")
coll, clab = Rs.collapse_series(), Rs.collapse_labels()
st.plotly_chart(build_collapse(coll, clab), width="stretch", key="series_collapse")


def _first_break(key, factor=3.0):
    base = coll[0]["wartezeit"][key]["mean"]
    for r in coll:
        if r["wartezeit"][key]["mean"] > factor * base:
            return r["sigma"]
    return None


br = {k: _first_break(k) for k in ("hw1_10", "sched1_10", "sched1_20")}
r96 = next(r for r in coll if abs(r["sigma"] - 0.96) < 1e-9)
st.markdown(
    f"Stationär (40 h), 8 Busse. **Ohne Regelung** steigt die Umlaufzeit von {de(coll[0]['umlaufzeit_ohne']['mean'], 0)} min bei σ = {de(coll[0]['sigma'], 2)} auf {de(r96['umlaufzeit_ohne']['mean'], 0)} min bei σ = 0,96; "
    f"die Formel für den dichten Konvoi (Pol bei σ = 1 + κ) trifft den freien Betrieb nur zu {de(100 * r96['verhaeltnis'], 0)} % (der Konvoi ist die Obergrenze). Die Wartezeit steigt ohne Regelung von {de(coll[0]['wartezeit']['none']['mean'])} auf {de(r96['wartezeit']['none']['mean'])} min. "
    f"Wartezeit dreimal so hoch wie bei der schwächsten Last: **Headway-Holding** ab σ = {de(br['hw1_10'], 2)}, **Fahrplan-Holding mit 10 % Puffer** ab σ = {de(br['sched1_10'], 2)}, mit 20 % Puffer ab σ = {de(br['sched1_20'], 2)}: "
    "**der nötige Puffer wächst mit der Last**, ein fester Puffer ist nicht robust."
)
st.dataframe(pd.DataFrame([{"σ": de(r["sigma"], 2), "Umlaufzeit ohne Regelung (min)": Rs.stat_text(r["umlaufzeit_ohne"], 0), "Konvoi-Formel (min)": "unendlich" if r["konvoi_formel"] == float("inf") else de(r["konvoi_formel"], 0),
                            "Wartezeit ohne (min)": de(r["wartezeit"]["none"]["mean"]), "Headway η 1,0": de(r["wartezeit"]["hw1_10"]["mean"]), "Fahrplan 10 %": de(r["wartezeit"]["sched1_10"]["mean"]),
                            "Fahrplan 20 %": de(r["wartezeit"]["sched1_20"]["mean"])} for r in coll]), width="stretch", hide_index=True)
st.caption("„–“: In 40 Stunden kam bei dieser Last kein vollständiger Umlauf eines Busses zustande, die Umlaufzeit ist nicht messbar.")

st.markdown("### Was Halten kostet und wann es sich nicht lohnt")
srows = Rs.strategy_rows("basis/schicht")
st.dataframe(pd.DataFrame([{"Strategie": r["label"], "Wartezeit (min)": Rs.stat_text(r["wait"]), "Fahrzeit im Bus (min)": de(r["ride"]["mean"]), "Gesamt (min)": de(r["total"]["mean"]), "CV der Abstände": de(r["cv"]["mean"], 2),
                            "Umlaufzeit (min)": de(r["cycle"]["mean"], 1), "Halt über Mindesthalt (min)": de(r["hold"]["mean"], 2), "Gesamt gegen ohne (gepaart)": Rs.stat_text(r["d_total_gegen_none"])} for r in srows.values()]),
             width="stretch", hide_index=True)
n0, h10, s10 = srows["none"], srows["hw_c1_e1.0_o3"], srows["sched_c1_p10"]
fl = Rs.fleet_equivalent()
st.markdown(
    f"10-h-Schicht, Standardfall. Wartezeit ohne Regelung {Rs.stat_text(n0['wait'])} min, mit Fahrplan-Holding (10 %) {Rs.stat_text(s10['wait'])}, mit Headway-Holding (η 1,0) {Rs.stat_text(h10['wait'])} "
    f"(gleichmäßiger Takt: {de(Rs.model()['h0'] / 2, 2)}). Das spart {de(100 * (1 - s10['wait']['mean'] / n0['wait']['mean']), 0)} % bzw. {de(100 * (1 - h10['wait']['mean'] / n0['wait']['mean']), 0)} % der Wartezeit und kostet "
    f"{de(100 * (s10['cycle']['mean'] / 60 - 1), 0)} % bzw. {de(100 * (h10['cycle']['mean'] / 60 - 1), 0)} % Umlaufzeit. **Ohne Regelung bräuchte man für dieselbe Wartezeit etwa {de(fl['basis/sched1_10']['B_eq'], 1)} (Fahrplan) bzw. {de(fl['basis/hw1_10']['B_eq'], 1)} (Headway) statt 8 Busse** "
    "(Interpolation der Wartezeit über die Busanzahl)."
)
bt, bl = Rs.busse("basis/schicht"), Rs.busse_labels()
st.plotly_chart(build_buses_curve(bt, Rs.bus_counts(), bl), width="stretch", key="series_buses")
hf = Rs.headway_minus_schedule("basis/schicht")
flip = [b for b in sorted(hf, key=int) if hf[b]["total"] > 0]
st.markdown(
    f"**Gesamtreisezeit gegen die Zahl der Busse** (Warten plus Fahren, Soll-Umlaufzeit 60 min). Headway-Holding schlägt das Fahrplan-Holding bei {', '.join(b for b in sorted(hf, key=int) if hf[b]['total'] <= 0)} Bussen "
    f"(Unterschied {de(min(hf[b]['total'] for b in hf if hf[b]['total'] <= 0), 1)} bis {de(max(hf[b]['total'] for b in hf if hf[b]['total'] <= 0), 1)} min), das Fahrplan-Holding ab {flip[0]} Bussen. Der Unterschied ist klein; "
    "der echte Unterschied ist die Robustheit (siehe Zusammenbruch). **Bei sehr vielen Bussen schadet das Halten:** "
    f"Mit 24 Bussen (ein Bus je Haltestelle) liegt die Gesamtreisezeit ohne Regelung bei {Rs.stat_text(bt['24/none']['total'])} min, mit Fahrplan-Holding bei {Rs.stat_text(bt['24/sched1_10']['total'])} und mit Headway-Holding bei {Rs.stat_text(bt['24/hw1_10']['total'])}: "
    "Die Wartezeit sinkt, die längere Fahrzeit im Bus frisst den Gewinn."
)
cap = Rs.capacity("0.02/schicht")
st.markdown("**Volle Busse.** Mit Platzgrenze bleiben Fahrgäste zurück, und jede Haltestrategie kostet Umläufe. Wartezeit in min (10-h-Schicht, Standardlast):")
st.dataframe(pd.DataFrame([{"Platzgrenze": C.CAPACITY_LABELS.get(k, "unbegrenzt" if k == "unbegrenzt" else f"{k} Plätze"), "mittlere Besetzung": ("–" if k == "unbegrenzt" else de(cap[k]["besetzung_je_kapazitaet"], 2)),
                            "ohne Regelung": de(cap[k]["none"]["wait"]["mean"]), "Fahrplan 10 %": de(cap[k]["sched1_10"]["wait"]["mean"]), "Headway η 1,0": de(cap[k]["hw1_10"]["wait"]["mean"]),
                            "Umlaufzeit ohne / Fahrplan / Headway (min)": f"{de(cap[k]['none']['cycle']['mean'], 0)} / {de(cap[k]['sched1_10']['cycle']['mean'], 0)} / {de(cap[k]['hw1_10']['cycle']['mean'], 0)}"}
                           for k in ("30", "40", "50", "60", "80", "120", "unbegrenzt")]), width="stretch", hide_index=True)
st.caption("Bei einer mittleren Besetzung von etwa 1 und darüber ist die Linie kapazitätsgebunden: Die Zahlen des Standardfalls ohne Platzgrenze sind Obergrenzen für den Gewinn des Haltens, und ein Konvoi aus allen Bussen tritt nur ohne Grenze auf.")

st.markdown("### Eine einfache Regel liegt am Optimum")
opt = Rs.optimum("basis/total")
rl = Rs.rule_labels()
st.plotly_chart(build_heatmap(opt["flaeche_sched_test"]), width="stretch", key="series_heat")
sk = opt["optimum"]["sched"]["schluessel"]
st.markdown(
    f"Fläche der Gesamtreisezeit des Fahrplan-Holdings über Kontrollhaltestellen und Puffer (Test-Seeds 101 bis 160, Standardfall). Das Optimum liegt bei Kontrollhaltestelle jede {sk[1]}. und {de(100 * sk[2], 1)} % Puffer: {Rs.stat_text(opt['optimum']['sched']['test'])} min "
    f"(ohne Regelung {Rs.stat_text(opt['none_test'])}). Die Fläche ist flach: {Rs.share_text(opt['breite']['sched_2%'])} Zellen liegen innerhalb 2 % des Optimums, {Rs.share_text(opt['breite']['sched_10%'])} innerhalb 10 %. "
    f"In {Rs.share_text(opt['schlechter_als_nichts'])} Zellen des Gitters ist Halten schlechter als nichts tun."
)
combos = ("basis/total", "basis/w2", "basis/wait", "hart/total", "hart/w2", "hart/wait")
combo_label = {"basis/total": "Standard, Gesamtreisezeit", "basis/w2": "Standard, 2 · Warten + Fahren", "basis/wait": "Standard, Wartezeit", "hart/total": "hart, Gesamtreisezeit",
               "hart/w2": "hart, 2 · Warten + Fahren", "hart/wait": "hart, Wartezeit"}
rule_keys = ["R1 hw c=1 eta=1.0 cap=3", "R2 hw c=3 eta=0.8 cap=2", "R3 sched c=3 slack=0.10", "R4 sched c=1 slack=0.10"]
st.dataframe(pd.DataFrame([{"Bedingung und Zielgröße": combo_label[c], **{f"{k[:2]}: {rl[k[:2]]}": f"{de(100 * Rs.optimum(c)['regeln'][k]['gewinnanteil'], 0)} %" for k in rule_keys}} for c in combos]),
             width="stretch", hide_index=True)
st.caption("Anteil des mit dem Gitter möglichen Gewinns (gegen „ohne Regelung“), den die Regel auf den Test-Seeds erreicht; „hart“: starke Störung und hohe Last. Die Regeln R1, R3 und R4 wurden nach Ansicht der Strategietabelle gewählt (nicht verblindet), R2 ist die vorab gesetzte Feldregel. "
           "Wer eine Parametersuche zeigt, zeigt am besten die flache Fläche, nicht den Treffer.")

st.markdown("---")

st.markdown("### 📄 Szenario-Bericht")
report = build_report(
    "Bus-Bunching: wie lange hält der Takt?",
    [("Strategie", C.STRATEGIES[settings.strategy]["label"]), ("Last σ", de(settings.load, 2)), ("Störung der Fahrzeiten", C.NOISE_LABELS[settings.noise]), ("Busse", str(settings.buses)),
     ("Platzgrenze", C.CAPACITY_LABELS[settings.capacity]), ("Betrachtung", C.HORIZON_LABELS[settings.horizon]), ("Zufalls-Seed", str(settings.seed))],
    [(C.STRATEGIES[k]["label"], f"Wartezeit {de(a.stat(k, 'wait')[0])} min, Gesamt {de(a.stat(k, 'total')[0])} min, CV {de(a.stat(k, 'cv')[0], 2)}, Umlaufzeit {de(a.stat(k, 'cycle')[0], 0)} min") for k in a.strategies],
    text.replace("**", ""),
    [f"Mittel über {C.LIVE_SEEDS} Zufalls-Seeds ab {settings.seed}. Mechanismus einer Ringlinie mit unabhängiger Fahrzeitstörung, keine Prognose für eine reale Linie."],
)
st.download_button("PDF herunterladen", report, file_name="bus_bunching_szenario.pdf", mime="application/pdf", key="pdf_download")

st.markdown("---")

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_strat, tab_theory, tab_model, tab_series = st.tabs(["🧮 Strategien", "🔬 Theorie und Orakel", "📋 Modell und Annahmen", "📈 Messreihe"])

    with tab_strat:
        st.markdown(
            """
Alle Strategien sehen nur den **Vordermann** und die **Uhr**, nicht die Wartenden an den nächsten Haltestellen. Gehalten wird an Haltestellen, an denen kein Fahrgast mehr einsteigt, bis die Regel erfüllt ist.

| Variante | Was sie tut | Wann sie reicht | Preis und Schwäche |
|---|---|---|---|
| keine Regelung | Jeder Bus fährt ab, sobald die Fahrgäste eingestiegen sind | Nur bei sehr kleiner Last und schwacher Störung | Die Abstände zerfallen, die Wartezeit ist ein Vielfaches des Solls |
| Fahrplan-Holding, Puffer p | Ein Bus fährt nicht vor dem Sollzeitpunkt k · τ ab, τ = (1 + p) · Soll-Umlaufzeit / Haltestellen | Bei mäßiger Last; schon ein kleiner Puffer holt verspätete Busse wieder ein | Der Puffer kostet p der Umlaufzeit. Er ist fest: Bei hoher Last reicht er nicht mehr, der nötige Puffer wächst mit der Last |
| Headway-Holding, η | Ein Bus fährt nicht vor Abfahrt des Vordermanns + η · Soll-Takt ab (Haltezeit höchstens 3 min) | Hält die Abstände bis nahe an den Zusammenbruch; besser bei wenigen Bussen (langer Takt) | Reagiert auf jede zufällig kurze Lücke und verbraucht mehr Umlaufzeit, besonders bei starker Störung |
| Feldregel | Wie Headway, aber nur an jeder dritten Haltestelle, η 0,8, Obergrenze 2 min | Als Gegenprobe: Eine Regel, die auf den ersten Blick vernünftig aussieht, bleibt oft weit hinter einer guten zurück | In einzelnen Szenarien schlechter als nichts tun |
"""
        )
        st.caption("Die Parameter jeder Variante sind fest und in der Messreihe einzeln gemessen. Es gibt kein Überspringen: Es wirkt im Standardfall kaum (viele Fahrgäste steigen aus), nie so wie Holding.")

    with tab_theory:
        st.markdown(
            """
**Gleichgewichtstakt.** Ohne Störung bleibt der Takt gleichmäßig, weicht aber leicht vom Soll-Takt ab, weil die Haltezeit an den Wartenden hängt (Gleichung im Expander „📐 Mathematische Formulierung“).

**Wachstumsrate.** Die lineare Stabilitätsrechnung sagt, wie schnell eine kleine Abweichung der Abstände wächst; der Verzug um N / B Halte (der Vordermann hat die Haltestelle so viele Halte früher bedient) senkt die Rate gegenüber dem naiven Ansatz ohne Verzug.

**Konvoi.** Fahren alle Busse dicht beieinander, nimmt der erste alle Wartenden mit. Seine Umlaufzeit hat einen Pol bei σ = 1 + κ: Dort schafft ein einzelner Bus den Einsteige-Aufwand der Linie nicht mehr.

**Wartezeit-Paradox.** Bei zufällig eintreffenden Fahrgästen und Abstandsmittel h̄ mit Variationskoeffizient CV beträgt die mittlere Wartezeit h̄ (1 + CV²) / 2. Bei B unabhängig umlaufenden Bussen ist CV² = (B − 1) / (B + 1) und die Wartezeit B / (B + 1) mal der Takt.
"""
        )
        st.dataframe(pd.DataFrame([
            {"Größe": "Gleichgewichtstakt (ohne Störung)", "Rechnung": f"{de(th['h_eq'], 2)} min", "Soll-Takt": f"{de(h0, 2)} min"},
            {"Größe": "mittlere Wartezeit im Gleichgewicht", "Rechnung": f"{de(th['w_eq'], 2)} min", "Soll-Takt": f"{de(h0 / 2, 2)} min (halber Takt)"},
            {"Größe": "Wachstumsrate je Stunde", "Rechnung": de(th["growth"], 2), "Soll-Takt": "–"},
            {"Größe": "Umlaufzeit eines dichten Konvois", "Rechnung": "unendlich" if th["convoy"] == float("inf") else f"{de(th['convoy'], 0)} min", "Soll-Takt": f"{de(p.T0, 0)} min Soll-Umlaufzeit"},
            {"Größe": "CV unabhängiger Busse √((B − 1) / (B + 1))", "Rechnung": de(th["independent_cv"], 2), "Soll-Takt": "–"},
        ]), width="stretch", hide_index=True)
        st.caption("Orakel der Tests: Alle diese Rechnungen werden gegen die Simulation geprüft (ohne Störung exakt, mit Störung statistisch); siehe README, Abschnitt Verifikation.")

    with tab_model:
        st.markdown(
            """
**Annahmen, die die Demo setzt** (Wer setzt an: die Demo, soweit nicht ein Regler genannt ist):

| Annahme | Wert | Wirkung |
|---|---|---|
| Linie | Ring mit 24 Haltestellen, Busse zu Beginn gleichmäßig verteilt, feste Fahrtrichtung | Der Ring vermeidet Endpunkteffekte; N ist fest |
| Fahrgäste | je Haltestelle Poisson-Strom mit 0,5 je Minute, Ziel gleichverteilt auf die übrigen Haltestellen (mittlere Fahrt 12 Halte) | keine Pendlerströme, keine Verhaltensänderung |
| Haltezeit | Grundhalt 0,25 min plus Zustiegszeit je einsteigendem Fahrgast; Aussteigezeit null | Zustiegszeit über den Regler „Last σ“ |
| Fahrzeit | Mittel 2,1 min je Segment, Erlang-verteilt, unabhängig von Segment zu Segment | Regler „Störung“; Praxis: meist korreliert (Ampeln, Verkehr), das beschleunigt das Bunching |
| Steg | ein Bus fährt erst ein, wenn der Vorgänger abgefahren ist (+ 0,05 min); Überholen auf der Strecke möglich | wirkt nur ohne Regelung merklich |
| Wartebuchhaltung | Erwartungswert (gegeben die Zahl Wartender sind die Ankunftszeiten gleichverteilt); Fahrgäste, die während des Halts eintreffen, steigen ohne Wartezeit zu | lückenlos geprüft |
| Platzgrenze | pauschal je Bus, wer nicht mehr einsteigen kann, wartet auf den nächsten | Regler „Platzgrenze“; ohne Grenze sind die Zahlen Obergrenzen |
| Strategien | benannte Varianten, jede mit festen Parametern | Regler „Strategie“ |

**Was nicht gemessen ist:** Die Fahrzeitstörung ist unabhängig je Segment, die Linie hat nur einen Steg, die Aussteigezeit ist null, die Fahrgäste ändern ihr Verhalten nicht. Die Demo zeigt einen **Mechanismus**, keine Prognose für eine reale Linie und keine Euro-Aussage.
"""
        )

    with tab_series:
        st.markdown(f"Alle Zahlen dieses Tabs stammen aus der vorgerechneten Messreihe (30 Zufalls-Seeds, Mittel ± Standardfehler; Median mit P10 bis P90 steht in `data/bun_results.json`). Stand der Messreihe: {Rs.meta()['stand']}.")
        st.markdown("**Strategien im Standardfall, stationär (40 h, 10 h Einschwingzeit).** Ohne Regelung gibt es in der Schicht keinen stationären Zustand; hier zeigt sich, wohin es läuft.")
        st.dataframe(pd.DataFrame([{"Strategie": r["label"], "Wartezeit (min)": Rs.stat_text(r["wait"]), "Gesamt (min)": de(r["total"]["mean"]), "CV der Abstände": de(r["cv"]["mean"], 2), "Umlaufzeit (min)": de(r["cycle"]["mean"], 1),
                                    "Gesamt gegen ohne (gepaart)": Rs.stat_text(r["d_total_gegen_none"])} for r in Rs.strategy_rows("basis/stat").values()]), width="stretch", hide_index=True)
        st.markdown("**Zeit bis zum Pulk** (Median, ohne Regelung): Mehr Busse bei gleicher Last verzögern ihn kaum; erst ein Bus je Haltestelle bringt Aufschub, und längere Linien bündeln stärker.")
        st.dataframe(pd.DataFrame([{"Variante": r["variante"], "Busse": r["B"], "Haltestellen": r["N"], "σ": de(r["sigma"], 2), "Median der Zeit bis CV > 1,2 (h)": ("–" if r["median_h"] is None else de(r["median_h"], 1)),
                                    "Seeds mit Pulk in 24 h": Rs.share_text(r["erreicht_in_24h"]), "CV 18–24 h": Rs.stat_text(r["cv_18_24h"], 2)} for r in Rs.time_to_pulse_rows()]), width="stretch", hide_index=True)
        st.markdown("**Wartezeit-Paradox in den Läufen.** Gemessene Wartezeit gegen h̄ (1 + CV²) / 2 mit den gemessenen Abständen (nicht exakt, weil Haltezeit und Fahrgäste während des Halts hineinspielen; exakt bei d0 = s = 0).")
        st.dataframe(pd.DataFrame([{"Strategie": r["label"], "gemessen (min)": Rs.stat_text(r["wait"]), "Formel (min)": Rs.stat_text(r["vorhersage"]), "Verhältnis": de(r["verhaeltnis"]["mean"], 2)} for r in Rs.paradox_rows()]),
                     width="stretch", hide_index=True)
        st.markdown("**Empfindlichkeit gegen Modellannahmen** (10-h-Schicht, Wartezeit in min):")
        sens = Rs.sensitivity()
        variants = [k.rsplit("/", 1)[0] for k in sens if k.endswith("/none")]
        vlabel = {"basis": "Standard", "delta0": "Mindestabstand 0", "delta0.25": "Mindestabstand 0,25 min", "delta0.5": "Mindestabstand 0,5 min", "d0=0.1": "Grundhalt 0,1 min", "d0=0.5": "Grundhalt 0,5 min",
                  "N12": "12 Haltestellen (8 Busse)", "N30_B10": "30 Haltestellen, 10 Busse", "T0=90": "Soll-Umlaufzeit 90 min", "T0=40": "Soll-Umlaufzeit 40 min"}
        st.dataframe(pd.DataFrame([{"Variante": vlabel.get(v, v), "ohne Regelung": Rs.stat_text(sens[f"{v}/none"]["wait"]), "Fahrplan 10 %": Rs.stat_text(sens[f"{v}/sched1_10"]["wait"]), "Headway η 1,0": Rs.stat_text(sens[f"{v}/hw1_10"]["wait"])}
                                   for v in variants]), width="stretch", hide_index=True)
        st.markdown("**Einschwingzeit.** Wartezeit in den Stunden nach dem Start, und die Zeit, nach der der Verlauf innerhalb von 5 % seines Spätwerts liegt:")
        sett = Rs.settling()
        st.dataframe(pd.DataFrame([{"Strategie": C.STRATEGIES.get(k, {"label": k})["label"] if k in C.STRATEGIES else k, "Stunde 1": de(v["wait_h1"]["mean"]), "Stunde 4": de(v["wait_h4"]["mean"]), "Stunde 12": de(v["wait_h12"]["mean"]),
                                    "Spätwert": de(v["wait_late"]["mean"]), "innerhalb 5 % nach (h)": ("nie" if v["settle5"] is None else de(v["settle5"], 1)), "Verzerrung durch die ersten 2 h": f"{de(100 * v['verzerrung'], 0)} %"}
                                   for k, v in sett.items()]), width="stretch", hide_index=True)
        tm = Rs.timing()
        st.markdown("**Rechenzeiten** (Median, ein Prozess; Streamlit Cloud nicht gemessen):")
        st.dataframe(pd.DataFrame([{"Messung": k, "Median (s)": de(v["median"], 3), "Maximum (s)": de(v["max"], 3)} for grp in ("live", "zeit_weg") for k, v in tm[grp].items()]), width="stretch", hide_index=True)
        ck = Rs.checks()
        failed = [k for k, v in ck.items() if v.get("ok") is False]
        st.caption(f"Modellprüfungen der Messreihe: {sum(1 for v in ck.values() if v.get('ok'))} von {len(ck)} bestanden"
                   + (f"; nicht bestanden: {', '.join(failed)} (Genauigkeit der eigenen Exponentialfunktion 4e-14 statt 1e-14 verlangt; für den Poisson-Sampler ausreichend)." if failed else "."))

st.markdown("---")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Szenario.** Eine Ringlinie mit 24 Haltestellen und 2 bis 24 Bussen. An jeder Haltestelle kommen Fahrgäste zufällig an (Poisson) und wollen zu einer zufälligen anderen Haltestelle. Ein Bus hält, bis alle Wartenden eingestiegen sind: Die Haltezeit
hängt also an der Zahl der Wartenden. Die Fahrzeit je Segment streut zufällig.

**Der Mechanismus.** Ein Bus, der etwas später kommt, trifft mehr Wartende, hält länger und wird noch später; der Bus dahinter trifft weniger Wartende, hält kürzer und holt auf. Aus kleinen Störungen werden Pulke, in denen mehrere Busse zusammen fahren,
während danach eine große Lücke klafft. Die Fahrgäste warten im Mittel ein Vielfaches des Solls (Wartezeit-Paradox).

**Haltestrategien.** *Fahrplan-Holding* lässt einen Bus an jeder Haltestelle nicht vor dem Sollzeitpunkt abfahren, *Headway-Holding* nicht vor dem Abstand zum Vordermann. Beide holen verspätete Busse wieder ein und kosten Umlaufzeit.

**Live und Messreihe.** Ein Szenario streut von Zufalls-Seed zu Zufalls-Seed, und ein Pulk braucht Zeit. Deshalb zeigt die Demo das Mittel über 10 Zufalls-Seeds, und daneben steht die vorgerechnete Messreihe über 30 Zufalls-Seeds.
Die erste Zeit nach dem Start wird verworfen (Einschwingzeit); ohne Regelung gibt es in einer Schicht keinen stationären Zustand.

**Grenzen.** Unabhängige Störungen, ein Steg, keine Aussteigezeit, unbegrenzte Plätze im Standardfall: Die Zahlen sind Mechanismus, keine Prognose.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown("Haltezeit eines Busses an einer Haltestelle mit $n$ einsteigenden Wartenden, Grundhalt $d_0$ und Zustiegszeit $s$; Abfahrt ohne Regelung:")
    st.latex(r"D = d_0 + s\,n, \qquad t_{\text{ab}} = t_{\text{an}} + D")
    st.markdown("Mit der Fahrgastrate $\\lambda$ ist $n \\approx \\lambda g$ für den Abstand $g$ zum Vordermann. Die Rückkopplung wird durch $\\kappa$ und die Last der ganzen Linie durch $\\sigma$ (bei $N$ Haltestellen) gemessen:")
    st.latex(r"\kappa = s\,\lambda, \qquad \sigma = N\,\kappa, \qquad \rho = \sigma / B")
    st.markdown("**Fahrplan-Holding** mit Sollzeitpunkt $k\\,\\tau$ vor dem $k$-ten Halt des Busses, $\\tau = (1 + p)\\,T_0 / N$; **Headway-Holding** mit Soll-Abstand $\\eta\\,h_0$ zur Abfahrt $t^{\\text{Vorg}}$ des Vordermanns und Obergrenze $H$:")
    st.latex(r"t_{\text{ab}} = \max\bigl(t_{\text{an}} + D,\ k\,\tau\bigr), \qquad t_{\text{ab}} = t_{\text{an}} + D + \min\bigl(H,\ \max(0,\ t^{\text{Vorg}} + \eta\,h_0 - t_{\text{an}} - D)\bigr)")
    st.markdown("**Gleichgewichtstakt** ohne Störung (Haltezeit mit erwarteten Fahrgastzahlen), reine Fahrzeit $m$:")
    st.latex(r"h_{\text{eq}} = \frac{N m / B + N d_0 / \bigl(B (1 + \kappa)\bigr)}{1 - N\kappa / \bigl(B (1 + \kappa)\bigr)}")
    st.markdown("**Konvoi:** Fahren alle Busse zusammen, hat der erste die Umlaufzeit")
    st.latex(r"T_c = \frac{N m + N (d_0 - \kappa \Delta) / (1 + \kappa)}{1 - \sigma / (1 + \kappa)}")
    st.markdown("mit dem Abstand $\\Delta$ des letzten Busses zum ersten. Der Nenner wird bei $\\sigma = 1 + \\kappa$ null: Zusammenbruch. **Wartezeit-Paradox:** bei Abstandsmittel $\\bar h$ und Variationskoeffizient $\\mathrm{CV}$")
    st.latex(r"\bar W = \bar h\,\frac{1 + \mathrm{CV}^2}{2}")

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [ÖPNV und Fernverkehr optimieren](https://sebastianhanisch.net/oepnv-fernverkehr-optimierung.html)."
)
