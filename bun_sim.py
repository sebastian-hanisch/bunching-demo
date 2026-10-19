"""Ereignissimulation einer Ringlinie mit Bus-Bunching.

Zeit in Minuten. Ring mit N Haltestellen, B Busse, zu Beginn gleichmäßig verteilt. Fahrgäste je Haltestelle: Poisson-Strom mit Rate lam (je Minute),
Ziel gleichverteilt auf die übrigen N − 1 Haltestellen. Haltezeit = d0 + s · (Zahl der einsteigenden Wartenden). Fahrzeit je Segment: Erlang-verteilt mit
Mittel m und Variationskoeffizient 1/√k (k = 0: feste Fahrzeit). Jede Haltestelle ist ein Einzelsteg: Ein Bus fährt erst ein, wenn der Vorgänger abgefahren
ist (plus delta). Haltestrategien: 'none', 'sched' (Fahrplan-Holding an jeder c-ten Haltestelle, mit Puffer) und 'hw' (Headway-Holding mit Obergrenze).

Wartezeit-Buchhaltung (Rao-Blackwell): Ankunftszeiten der Wartenden werden nicht einzeln gezogen. Zwischen Abfahrt des Vorgängers und Ankunft ist die Zahl
na ~ Poisson(lam · g); gegeben na sind die Ankunftszeiten gleichverteilt, also E[Summe Wartezeit | na, g] = na · g / 2. Wartende stehen je Haltestelle in einer
FIFO-Warteschlange von Blöcken [n, a, b] (n Fahrgäste, Ankunftszeiten gleichverteilt auf (a, b)); bei Platzgrenze steigen die ältesten ein, die übrigen warten
auf den nächsten Bus. Fahrgäste, die während Halt und Holding eintreffen, steigen ohne Wartezeit zu, verlängern den Halt aber nicht (Effekt zweiter Ordnung).
Zufall: SplitMix64 je Bus (Fahrzeit und Fahrgäste getrennt), gemeinsame Zufallszahlen für alle Strategien (gepaarte Vergleiche).
"""

import heapq
import math
from dataclasses import dataclass

from bun_rng import Stream, erlang, poisson

BIN = 30.0          # Minuten je Auswertungsbin
INF = float("inf")


@dataclass(frozen=True)
class Params:
    N: int = 24                 # Haltestellen
    B: int = 8                  # Busse
    T0: float = 60.0            # Soll-Umlaufzeit (legt die reine Fahrzeit m fest)
    d0: float = 0.25            # Grundhalt je Haltestelle (min)
    s: float = 0.04             # Zustiegszeit je Fahrgast (min)
    lam: float = 0.5            # Fahrgäste je Haltestelle und Minute
    erlang_k: int = 6           # Form der Fahrzeitstörung (Variationskoeffizient 1/√k); 0 = keine Störung
    delta: float = 0.05         # Mindestabstand zweier Busse am Steg (min)
    T_end: float = 600.0        # Simulationsende (min)
    T_warm: float = 120.0       # Einschwingzeit (min), danach wird gemessen
    strat: str = "none"         # none | sched | hw
    c: int = 1                  # Kontrollhaltestelle jede c-te
    slack: float = 0.1          # sched: Puffer als Anteil der Soll-Umlaufzeit
    eta: float = 1.0            # hw: Soll-Abstand = eta · Soll-Takt
    hold_max: float = 3.0       # hw: Obergrenze der Haltezeit je Haltestelle (min)
    capa: float = INF           # Platzgrenze je Bus
    det: bool = False           # Prüfmodus: erwartete statt gezogener Fahrgastzahlen (nur ohne Platzgrenze)
    start: str = "even"         # Startaufstellung: even | convoy
    kick: float = 0.0           # Anfangsstörung der ersten Fahrt von Bus 0 (relativ)
    trace_from: float = 0.0     # Aufzeichnung der Halte (Bus, Haltestelle, Ankunft, Abfahrt) im Fenster [trace_from, trace_to)
    trace_to: float = 0.0
    bins: bool = False          # Bin-Daten (Abstände je 30 Minuten) mitliefern

    @property
    def lam_s(self):
        return self.s * self.lam

    @property
    def sigma(self):
        """Einsteige-Aufwand der ganzen Linie: σ = N · s · λ."""
        return self.N * self.s * self.lam


def derived(p):
    """Soll-Takt h0, mittlere Haltezeit D0 und reine Fahrzeit m je Segment bei Soll-Umlaufzeit T0 (Handrechnung ohne Störung)."""
    h0 = p.T0 / p.B
    D0 = p.d0 + p.s * p.lam * h0
    m = p.T0 / p.N - D0
    if m <= 0:
        raise ValueError("Fahrzeit m <= 0: Soll-Umlaufzeit zu klein für diese Haltezeiten")
    return h0, D0, m


def _take(q, x, ta, xlong):
    """Die x ältesten Wartenden der Warteschlange q steigen ein. Gibt (Wartesumme, Zahl mit Wartezeit > xlong) zurück.
    Für t Fahrgäste eines Blocks [n, a, b] ist die erwartete Ankunftssumme t·a + (b − a)·t·(t + 1) / (2 (n + 1))."""
    wsum = 0.0
    nlong = 0.0
    rem = x
    cth = ta - xlong
    while rem > 0 and q:
        n, a, bb = q[0]
        t = n if n <= rem else rem
        ssum = t * a + (bb - a) * t * (t + 1) / (2.0 * (n + 1))
        wsum += t * ta - ssum
        if bb > a:
            f = (cth - a) / (bb - a)
            f = 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)
            nl = n * f
            nlong += nl if nl < t else t
        elif cth > a:
            nlong += t
        if t == n:
            q.pop(0)
        else:
            q[0] = [n - t, a + (bb - a) * t / n, bb]
        rem -= t
    return wsum, nlong


def simulate(p: Params, seed):
    N, B = p.N, p.B
    lam, s, d0, delta = p.lam, p.s, p.d0, p.delta
    T_end, T_warm = p.T_end, p.T_warm
    strat, det = p.strat, p.det
    capa = p.capa if p.capa == INF else int(p.capa)      # Platzgrenze als Ganzzahl (sonst wären die Einsteigenden Gleitkommazahlen)
    if det and capa != INF:
        raise ValueError("Der Prüfmodus rechnet nur ohne Platzgrenze")
    h0, D0, m = derived(p)
    nb = int(math.ceil(T_end / BIN))
    wb = int(round(T_warm / BIN))

    rn_trav = [Stream(int(seed) + ((2 * b + 1) << 40)) for b in range(B)]
    rn_pass = [Stream(int(seed) + ((2 * b + 2) << 40)) for b in range(B)]

    def travel(b):
        return erlang(rn_trav[b], p.erlang_k, m) if p.erlang_k > 0 else m

    pos0 = [0] * B if p.start == "convoy" else [int(round(b * N / B)) % N for b in range(B)]
    last_dep = [0.0] * N
    for j in range(N):
        best = min((pos0[b] - j) % N for b in range(B))
        last_dep[j] = -best * (m + D0)
    ld_init_sum = sum(last_dep)
    pos = [(x + 1) % N for x in pos0]
    k = [0] * B
    on_cnt = [[0] * N for _ in range(B)]
    on_t = [[0.0] * N for _ in range(B)]
    load = [0] * B
    queues = [[] for _ in range(N)]
    heap = []
    for b in range(B):
        tt = travel(b)
        if b == 0 and p.kick:
            tt *= 1.0 + p.kick
        heap.append((tt, b))
    heapq.heapify(heap)

    c = max(1, int(p.c))
    tau = (1.0 + p.slack) * p.T0 / N
    h_soll = p.eta * h0
    z = lambda: [0.0] * nb
    b_pass, b_wait, b_long, b_H, b_H2, b_Hn, b_bunch = z(), z(), z(), z(), z(), z(), z()
    b_ride, b_alight, b_hold, b_vis, b_full = z(), z(), z(), z(), z()
    xlong = 1.5 * h0
    half = 0.5 * h0
    generated = 0.0
    boarded_total = 0.0
    maxload = 0
    tile_total = 0.0
    alighted_total = 0
    t0_first = [None] * B
    t0_last = [0.0] * B
    t0_cnt = [0] * B
    trace = []
    tr0, tr1 = p.trace_from, p.trace_to

    while heap:
        t, b = heapq.heappop(heap)
        if t > T_end:
            heapq.heappush(heap, (t, b))
            break
        j = pos[b]
        k[b] += 1
        rd = rn_pass[b]
        ld = last_dep[j]
        ta = t if t >= ld + delta else ld + delta
        g = ta - ld
        bi = min(int(ta // BIN), nb - 1)
        if j == 0 and ta >= T_warm:
            if t0_first[b] is None:
                t0_first[b] = ta
            t0_last[b] = ta
            t0_cnt[b] += 1
        na = lam * g if det else poisson(rd, lam * g)
        generated += na
        q = queues[j]
        if na:
            q.append([na, ld, ta])
        cnt = on_cnt[b][j]
        if cnt:
            if ta >= T_warm:
                b_ride[bi] += cnt * ta - on_t[b][j]
                b_alight[bi] += cnt
            alighted_total += cnt
            load[b] -= cnt
            on_cnt[b][j] = 0
            on_t[b][j] = 0.0
        waiting = sum(x[0] for x in q)
        free = capa - load[b]
        k1 = waiting if waiting < free else free
        if k1 < waiting:
            b_full[bi] += 1
        wsum, nlong = _take(q, k1, ta, xlong)
        D = d0 + s * k1
        ready = ta + D
        dep = ready
        if strat == "sched":
            if j % c == 0:
                sd = k[b] * tau
                if sd > dep:
                    dep = sd
        elif strat == "hw":
            if j % c == 0:
                want = ld + h_soll
                if want > dep:
                    hold = want - dep
                    dep = dep + (hold if hold < p.hold_max else p.hold_max)
        hold = dep - ready
        nx = lam * (dep - ta) if det else poisson(rd, lam * (dep - ta))
        generated += nx
        free2 = free - k1
        k2 = nx if nx < free2 else free2
        if nx - k2 > 0:
            q.append([nx - k2, ta, dep])
        boarded_total += k1 + k2
        load[b] += k1 + k2
        if load[b] > maxload:
            maxload = load[b]
        if not det:
            oc = on_cnt[b]
            ot = on_t[b]
            for _ in range(k1):
                d = j + 1 + int(rd.uniform() * (N - 1))
                if d >= N:
                    d -= N
                oc[d] += 1
                ot[d] += ta
            if k2:
                tm = 0.5 * (ta + dep)
                for _ in range(k2):
                    d = j + 1 + int(rd.uniform() * (N - 1))
                    if d >= N:
                        d -= N
                    oc[d] += 1
                    ot[d] += tm
        H = dep - ld
        last_dep[j] = dep
        tile_total += H
        if ta >= T_warm:
            b_pass[bi] += k1 + k2
            b_wait[bi] += wsum
            b_long[bi] += nlong
        bd = min(int(dep // BIN), nb - 1)
        b_H[bd] += H
        b_H2[bd] += H * H
        b_Hn[bd] += 1
        if H < half:
            b_bunch[bd] += 1
        b_hold[bd] += hold
        b_vis[bd] += 1
        if tr0 <= ta < tr1:
            trace.append((b, j, ta, dep))
        tt = dep + travel(b)
        pos[b] = (j + 1) % N
        heapq.heappush(heap, (tt, b))

    res = dict(h0=h0, m=m, D0=D0, maxload=maxload, generated=generated, boarded=boarded_total, alighted=alighted_total,
               queued=sum(x[0] for qq in queues for x in qq), onboard=sum(load), tile_resid=(sum(last_dep) - ld_init_sum) - tile_total,
               nbus=len({bb for _, bb in heap}), ring_ok=all(pos[b] == (pos0[b] + 1 + k[b]) % N for b in range(B)))
    sl = slice(wb, nb)
    S = lambda a: sum(a[sl])
    npass = S(b_pass)
    res["npass"] = npass
    res["wait"] = S(b_wait) / npass if npass else float("nan")
    res["long"] = S(b_long) / npass if npass else float("nan")
    nH = S(b_Hn)
    if nH:
        mean_H = S(b_H) / nH
        var_H = S(b_H2) / nH - mean_H * mean_H
        res["hbar"] = mean_H
        res["cv"] = math.sqrt(max(var_H, 0.0)) / mean_H
        res["bunch"] = S(b_bunch) / nH
        cl = [(t0_last[b] - t0_first[b]) / (t0_cnt[b] - 1) for b in range(B) if t0_cnt[b] >= 2]
        res["cycle"] = sum(cl) / len(cl) if cl else float("nan")
        res["hold"] = S(b_hold) / nH
        res["fullshare"] = S(b_full) / S(b_vis)
    else:
        for key in ("hbar", "cv", "bunch", "cycle", "hold", "fullshare"):
            res[key] = float("nan")
    n_al = S(b_alight)
    res["ride"] = S(b_ride) / n_al if n_al else float("nan")
    res["total"] = res["wait"] + res["ride"] if n_al else float("nan")
    res["visits"] = nH
    if tr1 > tr0:
        res["trace"] = trace
    if p.bins:
        res["bins"] = dict(H=b_H, H2=b_H2, Hn=b_Hn, bunch=b_bunch, wait=b_wait, pass_=b_pass, long=b_long, ride=b_ride, alight=b_alight, hold=b_hold, vis=b_vis)
    return res


def mean_se(xs):
    xs = [x for x in xs if x == x]
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    mu = sum(xs) / n
    if n < 2:
        return mu, float("nan")
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    return mu, math.sqrt(var / n)
