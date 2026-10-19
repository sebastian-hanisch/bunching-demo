"""Sucht für jedes Preset Zufalls-Seeds außerhalb der Messreihe (ab 500), auf denen die Abnahmekriterien aus bun_stories.py gelten.

Aufruf:  python -B tools/preset_search.py [erster Seed] [Anzahl]    (Standard: 500, 20)
Ausgabe: je Preset die Seeds, die das Kriterium erfüllen, und die Zahl der Presets, die ein Seed zugleich erfüllt (alle Presets teilen sich einen Seed)."""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bun_constants as C  # noqa: E402
import bun_evaluation as ev  # noqa: E402
import bun_stories as ST  # noqa: E402


def main(first=500, count=20):
    good = {name: [] for name in C.PRESETS}
    for seed in range(first, first + count):
        for name, preset in C.PRESETS.items():
            a = ev.analyse(ST.settings_of(preset, seed=seed))
            if ST.check(name, a):
                good[name].append(seed)
        print(seed, "erfüllt:", [n for n in C.PRESETS if seed in good[n]], flush=True)
    for name, seeds in good.items():
        print(f"{name}: {len(seeds)}/{count} Seeds erfüllen das Kriterium: {seeds}")
    common = [s for s in range(first, first + count) if all(s in good[n] for n in C.PRESETS)]
    print("Seeds, die alle Presets erfüllen:", common)


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:3]])
