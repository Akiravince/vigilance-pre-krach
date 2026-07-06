# -*- coding: utf-8 -*-
"""Phase 2 — Calibration historique (à exécuter une fois, ré-exécutable).

    python calibrate.py [--offline]

Produit :
  data/history/panel_z.csv        z orienté par métrique (mensuel)
  data/history/sign_scores.csv    score par signe (mensuel)
  data/history/composite.csv     indice composite pondéré + couverture
  output/footprint_signes.csv    empreinte : score par signe à T-12 de chaque krach
  output/footprint_metrics.csv   idem au niveau métrique
  output/backtest.txt            backtest honnête + faux positifs historiques

--offline : utilise les fixtures SYNTHÉTIQUES (test de plomberie uniquement).
"""
import sys

import pandas as pd

from common import DATA, OUT, compute_panel, load_config


def main() -> int:
    offline = "--offline" in sys.argv
    cfg = load_config()
    if offline:
        print("MODE OFFLINE - donnees synthetiques, resultats NON interpretables\n")

    print("Collecte et normalisation...")
    p = compute_panel(cfg, offline=offline)

    hist = DATA / "history"
    hist.mkdir(parents=True, exist_ok=True)
    p["metric_z"].to_csv(hist / "panel_z.csv", index_label="date")
    p["sign_scores"].to_csv(hist / "sign_scores.csv", index_label="date")
    pd.DataFrame({"composite": p["composite"], "couverture": p["coverage"]}).to_csv(
        hist / "composite.csv", index_label="date"
    )

    # ---------------------------------------------- empreinte T-12 mois
    sdf, zdf, comp = p["sign_scores"], p["metric_z"], p["composite"]
    rows_s, rows_m = {}, {}
    for k in cfg["krachs"]:
        t12 = pd.Timestamp(k["date"]) - pd.DateOffset(months=12)
        # asof PAR COLONNE (DataFrame.asof écarte toute ligne contenant un NaN)
        rows_s[k["nom"]] = sdf.apply(lambda c: c.asof(t12))
        rows_m[k["nom"]] = zdf.apply(lambda c: c.asof(t12))
        rows_s[k["nom"]]["composite"] = comp.asof(t12)
    fp_s = pd.DataFrame(rows_s)
    fp_m = pd.DataFrame(rows_m)
    OUT.mkdir(exist_ok=True)
    fp_s.to_csv(OUT / "footprint_signes.csv", index_label="signe")
    fp_m.to_csv(OUT / "footprint_metrics.csv", index_label="metrique")

    print("\nEmpreinte (score par signe, z oriente, a T-12 mois de chaque krach) :")
    print(fp_s.round(2).to_string())

    # ---------------------------------------------- backtest anti-illusion
    seuils = cfg["normalisation"]["seuils"]
    comp_v = comp.dropna()
    rouges = comp_v[comp_v >= seuils["orange"]]
    crash_dates = [pd.Timestamp(k["date"]) for k in cfg["krachs"]]

    def pre_crash(d):  # rouge dans les 24 mois précédant un krach ?
        return any(0 <= (c - d).days <= 731 for c in crash_dates)

    vrais = sum(pre_crash(d) for d in rouges.index)
    faux = len(rouges) - vrais
    lignes = [
        "BACKTEST HONNETE (ne pas sur-interpreter)",
        f"Periode couverte par le composite : {comp_v.index[0]:%Y-%m} -> {comp_v.index[-1]:%Y-%m}",
        f"Mois 'rouges' (z composite >= {seuils['orange']}) : {len(rouges)}",
        f"  dont dans les 24 mois precedant un krach liste : {vrais}",
        f"  dont FAUX POSITIFS (rouge sans krach sous 24 mois) : {faux}",
        "",
        "Rappels : biais de survie (calibre sur les krachs survenus uniquement) ;",
        "couverture partielle avant 1990 (la plupart des series sont recentes) ;",
        "le signe 16 (declencheur) reste par nature hors de portee.",
    ]
    (OUT / "backtest.txt").write_text("\n".join(lignes), encoding="utf-8")
    print("\n" + "\n".join(lignes))

    if p["indisponibles"]:
        print("\nMetriques optionnelles indisponibles :")
        for key, err in p["indisponibles"]:
            print(f"  - {key}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
