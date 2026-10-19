# Bus-Bunching: wie lange hält der Takt? – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-bunching-demo.streamlit.app/)** -->

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`, Gruppe ÖPNV), vierte Demo der Seite [ÖPNV und Fernverkehr optimieren](https://sebastianhanisch.net/oepnv-fernverkehr-optimierung.html) nach dem festen Liniennetz ([transit-demo](https://github.com/sebastian-hanisch/transit-demo)), dem [Rufbus](https://github.com/sebastian-hanisch/rufbus-demo) und der [Tarifplanung](https://github.com/sebastian-hanisch/tarif-demo). Auf einer Ringlinie ist ein gleichmäßiger Takt **instabil**: Kommt ein Bus etwas später, wartet an der nächsten Haltestelle mehr Volk, der Halt dauert länger, der Bus wird noch später, und der Bus dahinter holt auf. Aus kleinen Störungen werden Pulke.

## Warum dieses Problem

Ohne Regelung warten die Fahrgäste auf der Ringlinie der Messreihe (24 Haltestellen, 8 Busse, Soll-Takt 7,5 min) im Mittel 14,6 ± 1,0 min statt 3,75 min beim gleichmäßigen Takt; der Variationskoeffizient der Abstände (CV) liegt bei 1,68. Ein Halten der Busse an den Haltestellen (Headway-Holding) senkt die Wartezeit auf 3,9 ± 0,0 min und kostet 17 % Umlaufzeit. Die Demo zeigt den **Mechanismus** im Zeit-Weg-Diagramm und ehrlich, was daran **nicht** trägt: Es gibt keinen scharfen Kipppunkt der Entstehung (die Kurve in der Last σ ist stetig), keine Optimierung (eine einfache Regel liegt am Optimum), und bei sehr vielen oder voll besetzten Bussen **schadet** das Halten.

## Modell

- **Linie:** Ring mit 24 Haltestellen, 2 bis 24 Busse (zu Beginn gleichmäßig verteilt), Soll-Umlaufzeit 60 min. Ein Bus fährt erst ein, wenn der Vorgänger abgefahren ist (Einzelsteg, plus 0,05 min).
- **Fahrgäste:** je Haltestelle ein Poisson-Strom mit 0,5 je Minute, Ziel gleichverteilt auf die übrigen Haltestellen (mittlere Fahrt 12 Halte). **Haltezeit** = Grundhalt 0,25 min + Zustiegszeit je einsteigendem Fahrgast; Aussteigezeit null. Last σ = Haltestellen · Zustiegszeit · Fahrgastrate (Standardfall σ 0,48, κ = Zustiegszeit · Rate = 0,02).
- **Fahrzeit** je Segment: Erlang-verteilt (Variationskoeffizient 0,2 / ≈ 0,41 / ≈ 0,58), **unabhängig** von Segment zu Segment, Mittel 2,1 min.
- **Wartebuchhaltung (Rao-Blackwell):** Gegeben die Zahl der Wartenden sind die Ankunftszeiten gleichverteilt, die Wartesumme ist n · g / 2; Wartende stehen in einer Warteschlange je Haltestelle, bei Platzgrenze steigen die ältesten ein, die übrigen warten auf den nächsten Bus.
- **Strategien** (benannte Varianten, jede einzeln gemessen): *Fahrplan-Holding* (Abfahrt an jeder c-ten Haltestelle nicht vor dem Sollzeitpunkt, Puffer 5 bis 20 %), *Headway-Holding* (Abfahrt nicht vor Abfahrt des Vordermanns + η · Soll-Takt, Haltezeit höchstens 3 min) und die *Feldregel* als Gegenprobe (nur jede dritte Haltestelle, η 0,8, Obergrenze 2 min). Überspringen gibt es nicht.
- Die Formeln stehen im Expander „📐 Mathematische Formulierung“ der App.

## Methodik

- **Plattformstabiler Zufall.** Die Simulation ist chaotisch: ein Unterschied in der letzten Stelle einer Fahrzeit kann nach Stunden die Reihenfolge zweier Busse umkehren. Deshalb gibt es SplitMix64-Ströme je Bus (Fahrzeit und Fahrgäste getrennt, blockweise mit numpy erzeugt, bitgleich zum Skalar-Erzeuger), einen eigenen Logarithmus und eine eigene Exponentialfunktion aus Grundrechenarten, und die Störung ist Erlang statt Gamma (`random.gammavariate` und `math.log` unterscheiden sich je Betriebssystem in der letzten Stelle). Ein Test sucht verbotene Bibliotheksaufrufe im Quelltext.
- **Live:** ein Szenario mit den Reglern der Seitenleiste (Strategie, Last σ, Störung, Busse, Platzgrenze, Betrachtung): Zeit-Weg-Diagramm ohne Regelung gegen die gewählte Strategie mit denselben Zufallszahlen, Kennzahlen als Mittel über 10 Zufalls-Seeds, Verlauf des Variationskoeffizienten, Handrechnungen daneben. Eine Meldung in vier Zuständen (keine Regelung, Regelung hilft, Regelung schadet, Zusammenbruch).
- **Messreihe (vorgerechnet, nie live):** 30 Zufalls-Seeds je Zelle (Parametersuche: Training Seeds 1 bis 30, Test Seeds 101 bis 160), Schicht 10 h mit 2 h Einschwingzeit und stationär 40 h mit 10 h, erzeugt mit `tools/sweep_bunching.py`, ausgewertet mit `tools/analyse.py` und als `data/bun_results.json` (unter 250 kB) abgelegt. Die Rohdaten (rund 77 MB) liegen nicht im Repo; die Werkzeuge schreiben sie in den Ordner der Umgebungsvariable `BUN_RAW_DIR`. `tools/pruefungen.py` enthält die Modellprüfungen.
- **Vorab-Reihe und Neumessung:** Die erste Messreihe lief mit `random.Random` und Gamma-Störung; für den Bau wurde alles auf dem plattformstabilen Kern neu gemessen (siehe „Befunde und Korrekturen gegenüber dem Plan“).

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen gelten für diese Ringlinie mit unabhängiger Fahrzeitstörung (Mittel ± Standardfehler über 30 Zufalls-Seeds, 10-h-Schicht, Basiseinstellung 8 Busse, σ 0,48, Störung mittel, unbegrenzte Plätze), stehen in `data/bun_results.json` und sind in `tests/test_claims.py` nachgerechnet.

| Frage | Befund |
|---|---|
| Was bringt Halten? | Wartezeit **14,6 ± 1,0 min** ohne Regelung, **4,1 ± 0,0** mit Fahrplan-Holding (Puffer 10 %), **3,9 ± 0,0** mit Headway-Holding (η 1,0); CV der Abstände 1,68, 0,36 und 0,22. Der Preis ist die Umlaufzeit: 66,0 und 70,3 min statt 60 min Soll (+10 % und +17 %). Die Gesamtreisezeit (Warten plus Fahren) sinkt gepaart um 10,9 ± 1,4 bzw. 9,1 ± 1,3 min. |
| Gibt es einen Kipppunkt der Entstehung? | **Nein.** Der Anteil der Zufalls-Seeds mit CV > 1,2 nach 7 h steigt ohne Regelung stetig mit der Last: 7 / 17 / 33 / 67 / 93 % bei σ 0,06 / 0,12 / 0,24 / 0,36 / 0,48; Mitte der Kurve bei σ ≈ 0,30. Selbst ohne Rückkopplung (σ = 0) wird der CV 0,86 (unabhängige Busse: 0,88). |
| Wo bricht es scharf? | Bei **σ ≈ 1**: Ohne Regelung steigt die Umlaufzeit stationär von 60 min (σ 0,12) auf 328 min (σ 0,96); die Konvoi-Formel (Pol bei σ = 1 + κ) trifft den freien Betrieb dann nur zu 50 %. Headway-Holding hält die Wartezeit bei 3,9 min bis σ 0,96, bei 1,08 sind es 5,2 min, bei 1,20 schon 34,4 min. **Fahrplan-Holding mit 10 % Puffer** bricht früher (6,4 min bei σ 0,72, 22,5 bei 0,84, 54,9 bei 0,96), mit 20 % Puffer erst bei σ 1,44: Der nötige Puffer wächst mit der Last. |
| Wie viele Busse spart das? | Ohne Regelung bräuchte man für dieselbe Wartezeit etwa **17,5 (Fahrplan) bzw. 17,9 (Headway) statt 8 Busse** (Interpolation über die Busanzahl). |
| Fahrplan oder Headway? | Bei langem Takt gewinnt Headway-Holding, bei kurzem das Fahrplan-Holding: Gesamtreisezeit Headway minus Fahrplan −0,89 min bei 2 Bussen, −0,11 bei 3, +0,46 bei 4, +1,35 bei 6, +1,82 bei 8. Der Unterschied ist klein; der echte Unterschied ist die Robustheit (siehe Zusammenbruch). |
| Wann schadet das Halten? | Bei **24 Bussen** (ein Bus je Haltestelle) liegt die Gesamtreisezeit ohne Regelung bei 32,9 ± 0,1 min, mit Fahrplan-Holding bei 34,7 ± 0,1, mit Headway-Holding bei 38,4 ± 0,1. Bei **50 Plätzen** (mittlere Besetzung 1,04) steigt die Wartezeit durch Headway-Holding von 11,2 auf 22,5 min. |
| Wie weit liegt eine einfache Regel vom Optimum? | Das Gitteroptimum des Fahrplan-Holdings liegt bei Kontrollhaltestelle jede 1. und 7,5 % Puffer (36,6 ± 0,1 min Gesamtreisezeit auf den Test-Seeds, ohne Regelung 46,0 ± 0,9). Die Regel „Fahrplan, jede Haltestelle, 10 % Puffer“ erreicht 97 % des möglichen Gewinns, „Fahrplan jede dritte, 10 %“ 94 %, Headway (η 1,0) 76 %, die Feldregel 66 % (bei hoher Last und starker Störung 29 %). 13 von 63 Gitterzellen liegen innerhalb 2 % des Optimums; in 80 von 567 Zellen ist Halten schlechter als nichts tun. |
| Gibt es einen stationären Zustand? | Nicht ohne Regelung: Die Wartezeit liegt in der Stunde 1 bei 4,2 min und erreicht ihren Spätwert (36,6 ± 0,3 min stationär) erst nach rund 15 h; mit Regelung ist er nach 1 bis 2 h erreicht. Mitrechnen der ersten 2 Stunden verzerrt die Schicht um 13 %. |
| Wartezeit-Paradox? | Gemessene Wartezeit gegen h̄ (1 + CV²) / 2 mit den gemessenen Abständen: Verhältnis 0,94 ohne Regelung (nicht exakt, weil Haltezeit und Fahrgäste während des Halts hineinspielen; bei d0 = s = 0 gilt die Formel auf 2 %). |
| Wie lange rechnet ein Live-Szenario? | Drei Strategien über 10 Zufalls-Seeds 0,66 s (Median, ein Prozess, Entwicklungsrechner); über 30 Zufalls-Seeds 1,95 s. Spinner und Ergebnis-Cache je Einstellung. Streamlit Cloud nicht gemessen. |

## Ehrliche Grenzen

- **Die Fahrzeitstörung ist unabhängig je Segment.** In der Praxis sind Verspätungen korreliert (Ampeln, Verkehr), was das Bunching beschleunigen würde; nicht gemessen.
- **Einzelsteg, Aussteigezeit null, gleichverteilte Ziele, keine Reaktion der Fahrgäste:** Die Zahlen sind ein Mechanismus, keine Prognose für eine reale Linie und keine Euro-Aussage.
- **Die Zahlen ohne Platzgrenze sind Obergrenzen.** Mit Platzgrenze sinkt der Gewinn des Haltens; bei Besetzung um 1 verschlechtert jede Strategie die Lage, und der Konvoi aus allen Bussen tritt nur ohne Grenze auf.
- **Kein scharfer Kipppunkt, kein Optimierungsergebnis.** Die Regeln R1, R3 und R4 der Optimum-Tabelle wurden nach Ansicht der Strategietabelle gewählt (nicht verblindet), nur R2 war vorab gesetzt; „Fahrplan, jede Haltestelle, 10 % Puffer“ ist faktisch das Optimum nur in diesem Modellbereich (Störung 0,2 bis 0,6, κ 0,02 bis 0,03, 10 h); bei hoher Last oder 40 h bricht ein fester Puffer.
- **Streuung wirkt nicht monoton:** Starke Störung bündelt in den ersten Stunden weniger, auf Dauer nicht. Eine Pauschalaussage „mehr Streuung, mehr Pulk“ gibt es deshalb nicht.
- **Erlang statt Gamma:** Variationskoeffizient 0,41 statt 0,40 und 0,58 statt 0,60; 423 der 2540 verglichenen Kennzahlen der Vorab-Reihe sind deshalb Ersatz-Zeilen (andere Störungsstärke als in der alten Reihe).
- **Der eigene Logarithmus und die eigene Exponentialfunktion** sind auf 1e-15 bzw. 4e-14 genau (relativ); für den Poisson-Sampler reicht das, die Plattformstabilität bleibt (nur Grundrechenarten).
- Nur 30 Zufalls-Seeds je Zelle: Standardfehler stehen überall dabei.

## Verifikation

- **Kern (`tests/test_sim.py`):** Handrechnung ohne Störung (konstanter Abstand, Wartezeit = Abstand / 2 bzw. (h − d0)² / (2h)), ein Bus gegen die geschlossene Lösung, Strategien ohne Störung ergeben die Umlaufzeit (1 + Puffer) · T0 bzw. η · T0, Erhaltungssätze (erzeugt = eingestiegen + wartend, eingestiegen = ausgestiegen + an Bord, Zahl der Busse, Ringfolge, Kachelung), eingefrorene Läufe für drei Zufalls-Seeds.
- **Orakel (`tests/test_oracle_bunching.py`):** Gleichgewichtstakt mit erwarteten Fahrgastzahlen auf 1e-9; Wartezeit-Paradox bei d0 = s = 0 mit unabhängigen Bussen (CV² = (B − 1) / (B + 1), Wartezeit / Takt = B / (B + 1)); Wachstumsrate einer kleinen Abstandsabweichung gegen die lineare Stabilitätsrechnung (Verzug um N / B Halte; Messreihe: Abweichung bis 3,5 %); dichter Konvoi gegen die geschlossene Formel (104,438 min).
- **Zufall (`tests/test_rng.py`):** SplitMix64 gegen die veröffentlichten Referenzwerte, Block-Strom bitgleich zum Skalar-Erzeuger, Poisson- und Erlang-Sampler gegen Mittel und Varianz, `ln` und `exp_neg` gegen die Bibliothek, kein `math.log`, `math.exp`, `random` im Quelltext.
- **Messreihe gegen Live:** Die Mittel der drei Hauptstrategien über 30 Zufalls-Seeds sind bitgleich zu einer Live-Rechnung (`tests/test_results.py`). In der Messreihe selbst: zwei Sweep-Läufe bitgleich.
- **Neumessung:** Von 2540 verglichenen Kennzahlen der Vorab-Reihe bestehen 2410, 125 sind verschoben, 5 brechen (siehe unten).
- **Mutationsprüfung:** `tools/mutation_check.py` ändert 37 Rechenstellen einzeln (Zustiegszeit, Einzelsteg, Strategien, Platzgrenze, Wartebuchhaltung, Konvoi-Formel, Zufall, Verdikt); alle 37 werden von mindestens einem Test gefunden. Bewusst nicht in der Liste: der Newton-Schritt der Wachstumsrate (konvergiert mit 200 Schritten zur selben Wurzel) und `g = t - ld` (unterscheidet sich nur, wenn ein Bus am Steg warten muss).
- **Presets:** Jede Geschichte stimmt auf dem gezeigten Szenario (`tests/test_stories.py`), jede Schwelle kippt einzeln an künstlichen Werten; die Zufalls-Seeds liegen außerhalb der Messreihe (503).
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jede Stufe jedes Reglers), Layout (Schnellstart oben, fester Kopf, aktives Preset hervorgehoben), Footer.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App |
| `data/bun_results.json`, `data/README_data.md` | vorgerechnete Messreihe und Beschreibung ihrer Schlüssel |
| `requirements-dev.txt` | Laufzeit plus pytest |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt) |
| `bun_constants.py` | Modellannahmen, Reglerstufen, benannte Strategien, Farben, Presets |
| `bun_evaluation.py` | Live-Szenario: Einstellungen, Simulation aller Strategien, Verläufe, Theorie, Verdikt |
| `bun_layout.py` | Fester Kopf (Stylesheet) |
| `bun_pdf_export.py` | Szenario-Bericht als PDF |
| `bun_presets.py` | Permalink (Begrenzen), Presets, Zufalls-Seed-Button |
| `bun_results.py` | Laden und Abfragen der vorgerechneten Messreihe |
| `bun_rng.py` | SplitMix64, Block-Strom, eigener Logarithmus und eigene Exponentialfunktion, Poisson, Erlang |
| `bun_sim.py` | Ereignissimulation mit Warteschlangen-Buchhaltung, Strategien und Platzgrenze |
| `bun_stories.py` | Abnahmekriterien der Presets |
| `bun_theory.py` | Gleichgewichtstakt, Wachstumsrate, Konvoi-Formel, Wartezeit-Paradox |
| `bun_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `tools/` | Sweeps, Analyse, Ergebnisdatei, Modellprüfungen, Preset-Suche, Mutationsprüfung |
| `tests/` | Handrechnung, Orakel, Zufall, Auswertung, Ergebnisse, Behauptungen, Presets, Layout, Smoke-Test, Footer |

## Bewusst nicht umgesetzt

- Überspringen von Haltestellen (wirkt im Standardfall kaum, nie wie Holding), adaptive Strategien mit Blick auf den Folgebus, korrelierte Fahrzeitstörungen, mehrere Plätze am Steg.
- Fahrgastverhalten (Reaktion auf lange Wartezeiten), Linien mit Endpunkten und Wendezeit, Tageszeitprofile, Fahrerpausen, Euro-Kosten.
- Animation der Busse (nur ein Standbild je Drei-Stunden-Fenster), Regler für die Obergrenze der Haltezeit (wirkt nur unter 2 bis 3 min) und für die Kontrollhaltestellen-Dichte (nur über die benannten Varianten).

## Befunde und Korrekturen gegenüber dem Plan

- **Neumessung auf dem plattformstabilen Kern:** Von 2540 verglichenen Kennzahlen der Vorab-Reihe bestehen 2410, 125 sind verschoben, 5 brechen (Urteilsregeln vor der Neumessung festgelegt; Toleranz: zwei kombinierte Standardfehler, mindestens 2 % relativ und 0,005 absolut). Die fünf Brüche sind Grenzfälle an einer Schwelle: zwei Anteile am Statusrand bei starker Störung (Ersatz-Zeilen), ein Vorzeichen bei starker Störung (Ersatz-Zeile), „ohne Regelung schlechter als Headway“ bei 12 Bussen (39,2 ± 0,8 gegen 38,3 ± 0,1) und das Fleet-Äquivalent bei hoher Last für Headway (23,5; die Vorab-Reihe nannte „über der Messgrenze von 24 Bussen“).
- **Wartezeit-Minderung:** Die Vorab-Aussage „−75 %“ gilt neu für die Schicht als rund −72 bis −73 % (stationär rund −89 %).
- **Kapazität:** Die endliche Platzgrenze war im Kern zunächst eine Gleitkommazahl und brach die Einsteigenden-Zählung; der Fehler ist behoben (Platzgrenze als Ganzzahl), die Messreihe ist davon nicht betroffen.
- **Presets:** sieben, alle mit demselben Zufalls-Seed 503; „Seltene Busse“ nutzt 2 statt 3 Busse, weil der Vorsprung des Headway-Holdings bei 3 Bussen (−0,11 min) zu klein für ein Preset ist.
- **Strategien als benannte Varianten:** keine freien Parameter, nur gemessene Stufen; ohne Regler für die Obergrenze (toter Regler ab 3 min).

## Verwandte Demos mit demselben mathematischen Modell

- **[transit-demo](https://github.com/sebastian-hanisch/transit-demo):** das feste Liniennetz; dort wird die Linienführung gewählt, hier der Betrieb auf einer gegebenen Linie.
- **[taktfahrplan-demo](https://github.com/sebastian-hanisch/taktfahrplan-demo):** Abfahrtsminuten für feste Linien; hier entscheidet der Fahrplan nicht, sondern das Verhalten im Betrieb.
- **[rufbus-demo](https://github.com/sebastian-hanisch/rufbus-demo):** Rufbus oder Linienbus, gleiche Kulisse (Ereignissimulation, SplitMix64), andere Frage.
- **[tarif-demo](https://github.com/sebastian-hanisch/tarif-demo):** die Preise auf demselben Netz; gleiche Methodik (vorgerechnete Messreihe, Neumessung auf ganzzahligem Generator).
- **[mm1-queue-demo](https://github.com/sebastian-hanisch/mm1-queue-demo):** Warteschlangentheorie mit zufälligen Ankünften; das Wartezeit-Paradox dieser Demo ist das Gegenstück bei Busankünften.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly und NumPy.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [ÖPNV und Fernverkehr optimieren](https://sebastianhanisch.net/oepnv-fernverkehr-optimierung.html).
