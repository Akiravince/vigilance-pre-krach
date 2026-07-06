# -*- coding: utf-8 -*-
"""Génère des fixtures SYNTHÉTIQUES dans data/fixtures/ pour tester la
plomberie du pipeline sans réseau. AUCUNE valeur n'est réelle.

    python tools/make_fixtures.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import FIXTURES  # noqa: E402

rng = np.random.default_rng(42)


def walk(start, end, freq, base, drift, vol, lo=None, hi=None):
    idx = pd.date_range(start, end, freq=freq)
    steps = rng.normal(drift, vol, len(idx))
    v = base + np.cumsum(steps)
    if lo is not None or hi is not None:
        v = np.clip(v, lo, hi)
    return pd.Series(v, index=idx)


SPECS = {
    # nom fixture: (start, freq, base, drift, vol, lo, hi)
    "QUSPAM770A":   ("1947-10-01", "QS", 60, 0.25, 1.2, 30, 180),   # % du PIB
    "GDP":          ("1947-01-01", "QS", 250, 90, 40, 200, None),    # Md$
    "NCBEILQ027S":  ("1945-10-01", "QS", 100000, 220000, 250000, 50000, None),  # M$
    "M2SL":         ("1959-01-01", "MS", 290, 55, 15, 280, None),
    "T10Y3M":       ("1982-01-01", "D", 1.5, 0.0, 0.02, -1.5, 4.5),
    "DFII10":       ("2003-01-01", "D", 2.0, 0.0, 0.015, -1.5, 3.5),
    "VIXCLS":       ("1990-01-01", "D", 18, 0.0, 0.35, 9, 80),
    "BAMLH0A0HYM2": ("1996-12-31", "D", 5.0, 0.0, 0.04, 2.4, 20),
    "AAA":          ("1919-01-01", "MS", 5.0, 0.0, 0.15, 2.0, 10),
    "BAA":          ("1919-01-01", "MS", 6.2, 0.0, 0.18, 2.8, 13),
    "DRTSCILM":     ("1990-04-01", "QS", 5, 0.0, 8, -30, 70),
    "shiller_cape": ("1881-01-01", "MS", 15, 0.01, 0.6, 5, 45),
    "aaii":         ("1987-07-01", "W-THU", 5, 0.0, 6, -40, 50),
    "putcall":      ("2006-10-01", "D", 0.65, 0.0, 0.012, 0.35, 1.2),
    "margin_debt":  ("1997-01-01", "MS", 100000, 2500, 6000, 50000, None),
}

END = "2026-06-30"


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, (start, freq, base, drift, vol, lo, hi) in SPECS.items():
        s = walk(start, END, freq, base, drift, vol, lo, hi)
        s.rename("value").to_csv(FIXTURES / f"{name}.csv", index_label="date")
        print(f"  {name:14s} {len(s):6d} obs  {s.index[0]:%Y-%m} → {s.index[-1]:%Y-%m}")
    (FIXTURES / "README.txt").write_text(
        "Donnees SYNTHETIQUES (tools/make_fixtures.py) - uniquement pour tester\n"
        "le pipeline hors ligne (--offline). Ne representent AUCUNE realite.\n",
        encoding="utf-8",
    )
    print("Fixtures OK ->", FIXTURES)


if __name__ == "__main__":
    main()
