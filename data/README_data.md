# data/bun_results.json

Vorgerechnete Messreihe der Bus-Bunching-Demo (nie im Browser gerechnet). Erzeugt mit `tools/sweep_bunching.py` (Rohdaten), `tools/analyse.py` (Aggregation) und `tools/dump_results.py` (diese Datei). UTF-8, Zahlen auf 6 gültige Stellen gerundet. ±Unendlich steht als Text `"inf"` / `"-inf"` in der Datei (JSON kennt kein Infinity), NaN und fehlende Werte als `null`.

Ringlinie mit 24 Haltestellen, Soll-Umlaufzeit 60 min, Fahrgastrate 0,5 je Haltestelle und Minute; Zufalls-Seeds 1 bis 30 (Parametersuche: Training 1 bis 30, Test 101 bis 160); Fenster: Schicht 10 h mit 2 h Einschwingzeit, stationär 40 h mit 10 h, Verlauf 24 h. Störung der Fahrzeiten: Erlang mit Form k (Variationskoeffizient 1/√k); Basis k = 6.

**Statistikfelder** haben die Form `{n, mean, se, med, p10, p90}` (Zahl der Zufalls-Seeds, Mittel, Standardfehler, Median, 10. und 90. Perzentil), **Anteile** die Form `{k, n, p}`.

| Schlüssel | Inhalt |
|---|---|
| `meta` | Stand, Seeds, Fenster, Ersatz von Gamma durch Erlang, Beschreibung der Bedingungen (`basis`, `cv0.2`, `cv0.6`, `kap0.01`, `kap0.03`, `hart`) |
| `modell` | Standardfall: N, B, T0, d0, s, λ, δ, Erlang-Form, h0, m, D0, κ, σ, ρ, Gleichgewichtstakt, Wachstumsrate je Stunde (Theorie), Konvoi-Umlaufzeit |
| `entstehung` | `sigma_tabelle_k6` und `sigma_tabelle_k25`: je Last σ der Variationskoeffizient (CV) der Abstände und die Wartezeit in den Phasen 0–4 h, 6,5–7,5 h und 18–24 h ohne Regelung, Anteil der Zufalls-Seeds mit CV > 1,2 nach 7 h, Wachstumsrate aus der Theorie; `zeit_bis_pulk`: Median der Zeit bis CV > 1,2 je Busanzahl und Linienlänge; `verlauf_sigma_0_48`: Verlauf von CV und Wartezeit über 24 h (none, hw1_10, sched1_10) |
| `zusammenbruch` | `reihe_B8`: je σ von 0,12 bis 2,4 stationär die Umlaufzeit ohne Regelung, die Konvoi-Formel, das Verhältnis und die Wartezeit je Strategie (none, hw1_10, sched1_10, sched1_20); `tabelle_B4_8_12`: dieselbe Wartezeit für 4, 8 und 12 Busse |
| `strategien` | je Bedingung (`basis/schicht`, `basis/stat`, `cv0.2/schicht`, `cv0.6/schicht`, `kap0.01/schicht`, `kap0.03/schicht`) die Zeilen der Strategien mit `wait`, `ride`, `total`, `cv`, `long`, `bunch`, `cycle`, `hold` und der gepaarten Differenz der Gesamtreisezeit gegen „ohne Regelung“; `paradox`: gemessene Wartezeit gegen h̄ (1 + CV²) / 2 |
| `busse` | je Bedingung und Horizont `"B/Strategie"` mit `wait` und `total` für 2, 3, 4, 6, 8, 12 und 24 Busse; `fleet_aequivalent` (Zahl der Busse ohne Regelung für dieselbe Wartezeit), `headway_minus_fahrplan` (gepaarte Differenz je Busanzahl) |
| `gitter` | Regel gegen Optimum für sechs Kombinationen aus Bedingung (`basis`, `hart`) und Zielgröße (`total`, `w2`, `wait`): Optimum auf den Trainings-Seeds und seine Bewertung auf den Test-Seeds, Regeln R1 bis R4 mit Lücke und Gewinnanteil, Breite des Optimums, Zahl der Zellen schlechter als nichts tun; bei `basis/total` zusätzlich die Fläche des Fahrplan-Holdings (c × Puffer), die Wirkung der Obergrenze der Haltezeit und der Kontrollhaltestellen-Dichte; `pro_B`: Optimum je Busanzahl |
| `kapazitaet` | je Last (κ) und Horizont (`0.02/schicht` usw.) und Platzgrenze (30 bis 120, `unbegrenzt`) die Kennzahlen je Strategie (none, sched1_10, hw1_10) mit `voll_anteil` und die mittlere Besetzung je Platzgrenze |
| `sensitivitaet` | Wartezeit, CV, Umlaufzeit und Gesamtreisezeit je Strategie bei geänderten Annahmen (Mindestabstand, Grundhalt, Haltestellenzahl, Soll-Umlaufzeit) |
| `einschwing` | Verlauf der Wartezeit in den Stunden nach dem Start je Strategie, Zeit bis zum Spätwert (`settle5`, `settle10`), Verzerrung durch Mitrechnen der ersten 2 Stunden |
| `rechenzeit` | Rechenzeiten (Median, 90. Perzentil, Maximum) für einen Lauf, mehrere Strategien über 10 und 30 Zufalls-Seeds und die Zeit-Weg-Daten |
| `pruefungen` | Ergebnisse der Modellprüfungen (`tools/pruefungen.py`): Poisson- und Erlang-Sampler, `ln` und `exp_neg`, Block-Strom gegen SplitMix64, die Handrechnungen T3 bis T10, Erhaltung, Determinismus, Nullspalten |
