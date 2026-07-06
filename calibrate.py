# -*- coding: utf-8 -*-
"""Phase 2 — Calibration historique (à exécuter une fois, ré-exécutable).

    python calibrate.py [--offline]

Produit :
  data/history/panel_z.csv        z orienté par métrique (mensuel)
  data/history/sign_scores.csv    score par signe (mensuel)
  data/history/composite.csv     agrégation mensuelle : pire signe, comptes
                                 orange/rouge, moyenne indicative (ex-composite ;
                                 la colonne `composite` est conservée = moyenne)
  output/footprint_signes.csv    empreinte : score par signe à T-12 de chaque krach
  output/footprint_metrics.csv   idem au niveau métrique
  output/backtest.txt            backtest honnête + faux positifs historiques

Tâche 1 : l'agrégation (pire signe + comptes + moyenne indicative) vient de
common.agreger_signes — même chemin de code que monitor.py.

--offline : utilise les fixtures SYNTHÉTIQUES (test de plomberie uniquement).
"""
import sys

import pandas as pd

from common import DATA, OUT, compute_panel, faux_positifs_par_signe, load_config


def main() -> int:
    offline = "--offline" in sys.argv
    cfg = load_config()
    if offline:
        print("MODE OFFLINE - donnees synthetiques, resultats NON interpretables\n")

    print("Collecte et normalisation...")
    p = compute_panel(cfg, offline=offline)
    ag = p["agreg"]

    hist = DATA / "history"
    hist.mkdir(parents=True, exist_ok=True)
    p["metric_z"].to_csv(hist / "panel_z.csv", index_label="date")
    p["sign_scores"].to_csv(hist / "sign_scores.csv", index_label="date")
    # `composite` (= moyenne indicative) conservé pour ne pas casser les
    # lecteurs existants ; les nouvelles colonnes portent l'en-tête non diluant.
    out_hist = ag.copy()
    out_hist.insert(0, "composite", ag["moyenne_indicative"])
    out_hist.to_csv(hist / "composite.csv", index_label="date")

    # ---------------------------------------------- empreinte T-12 mois
    sdf, zdf = p["sign_scores"], p["metric_z"]
    rows_s, rows_m = {}, {}
    for k in cfg["krachs"]:
        t12 = pd.Timestamp(k["date"]) - pd.DateOffset(months=12)
        # asof PAR COLONNE (DataFrame.asof écarte toute ligne contenant un NaN)
        rows_s[k["nom"]] = sdf.apply(lambda c: c.asof(t12))
        rows_m[k["nom"]] = zdf.apply(lambda c: c.asof(t12))
        rows_s[k["nom"]]["pire_z"] = ag["pire_z"].asof(t12)
        rows_s[k["nom"]]["moyenne_indicative"] = ag["moyenne_indicative"].asof(t12)
    fp_s = pd.DataFrame(rows_s)
    fp_m = pd.DataFrame(rows_m)
    OUT.mkdir(exist_ok=True)
    fp_s.to_csv(OUT / "footprint_signes.csv", index_label="signe")
    fp_m.to_csv(OUT / "footprint_metrics.csv", index_label="metrique")

    print("\nEmpreinte (score par signe, z oriente, a T-12 mois de chaque krach) :")
    print(fp_s.round(2).to_string())

    # ------------------------- faux positifs PAR SIGNE (tache 1, point 5)
    seuils = cfg["normalisation"]["seuils"]
    fpx = faux_positifs_par_signe(sdf, cfg["krachs"], seuils)
    fpx.to_csv(OUT / "faux_positifs_signes.csv", index_label="signe")
    print("\nFaux positifs par signe (mois >= orange sans krach sous 24 mois ;")
    print("les ~24 derniers mois, non confirmables, comptent en faux positifs) :")
    aff = fpx.copy()
    aff["taux_faux"] = (aff["taux_faux"].astype(float) * 100).round(0)
    print(aff.to_string())

    # ---------------------------------------------- backtest anti-illusion
    # Depuis la tâche 1, « rouge » = couleur d'EN-TÊTE (pire signe >= seuil),
    # plus la moyenne : le compte de mois rouges augmente mécaniquement.
    pire_v = ag["pire_z"].dropna()
    rouges = pire_v[pire_v >= seuils["orange"]]
    moy_v = ag["moyenne_indicative"].dropna()
    rouges_moy = moy_v[moy_v >= seuils["orange"]]
    crash_dates = [pd.Timestamp(k["date"]) for k in cfg["krachs"]]

    def pre_crash(d):  # rouge dans les 24 mois précédant un krach ?
        return any(0 <= (c - d).days <= 731 for c in crash_dates)

    vrais = sum(pre_crash(d) for d in rouges.index)
    faux = len(rouges) - vrais
    lignes = [
        "BACKTEST HONNETE (ne pas sur-interpreter)",
        f"Periode couverte par l'agregation : {pire_v.index[0]:%Y-%m} -> {pire_v.index[-1]:%Y-%m}",
        f"Mois 'rouges' EN-TETE (pire signe, z >= {seuils['orange']}) : {len(rouges)}",
        f"  dont dans les 24 mois precedant un krach liste : {vrais}",
        f"  dont FAUX POSITIFS (rouge sans krach sous 24 mois) : {faux}",
        f"(pour memoire, ancienne definition par la moyenne : {len(rouges_moy)} mois rouges)",
        "",
        "Rappels : biais de survie (calibre sur les krachs survenus uniquement) ;",
        "couverture partielle avant 1990 (la plupart des series sont recentes) ;",
        "l'en-tete 'pire signe' est VOLONTAIREMENT plus sensible que la moyenne",
        "-> plus d'alertes, donc plus de faux positifs : c'est le prix de la",
        "non-dilution ; le signe 16 (declencheur) reste par nature hors de portee.",
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
