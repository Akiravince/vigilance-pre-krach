# -*- coding: utf-8 -*-
"""Étape 0 — Validation des ID de séries FRED (à lancer AVANT tout le reste).

    python test_fred.py

Avec une clé dans .env → API officielle ; sans clé → CSV public fredgraph
(mêmes données, permet déjà de valider les ID). Code retour ≠ 0 si un ID
FRED obligatoire échoue.
"""
import sys

from common import fetch_fred, fred_key, get_series, load_config


def main() -> int:
    cfg = load_config()
    key = fred_key()
    print(f"Clé FRED : {'présente (.env)' if key else 'ABSENTE → repli CSV public fredgraph'}\n")

    fred_ids, others = [], []
    for sign in cfg["signes"]:
        for m in sign["metrics"]:
            (fred_ids if m["source"] == "fred" else others).append(m)
    fred_series = sorted(
        {m["series"] for m in fred_ids}
        | {m["subtract_series"] for m in fred_ids if m.get("subtract_series")}
        | {"GDP"}
    )

    failures = 0
    print("── Séries FRED " + "─" * 50)
    for sid in fred_series:
        try:
            s = fetch_fred(sid, key)
            print(f"  ✓ {sid:14s} {s.index[0]:%Y-%m-%d} → {s.index[-1]:%Y-%m-%d}"
                  f"   n={len(s):6d}   dernier={s.iloc[-1]:.2f}")
        except Exception as e:
            failures += 1
            print(f"  ✗ {sid:14s} ÉCHEC : {e}")

    print("\n── Sources non-FRED (best effort) " + "─" * 31)
    for m in others:
        try:
            s = get_series(m["series"], m["source"])
            print(f"  ✓ {m['series']:14s} ({m['source']})"
                  f" {s.index[0]:%Y-%m-%d} → {s.index[-1]:%Y-%m-%d}   dernier={s.iloc[-1]:.2f}")
        except Exception as e:
            flag = "– optionnelle, non bloquante" if m.get("optional") else "✗ BLOQUANTE"
            print(f"  {flag} {m['series']} ({m['source']}) : {e}")
            if not m.get("optional"):
                failures += 1

    print("\n" + ("TOUT EST BON - passer a calibrate.py" if failures == 0
                  else f"{failures} echec(s) bloquant(s) - corriger la collecte"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
