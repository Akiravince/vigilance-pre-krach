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

from common import (DATA, OUT, agreger_signes, compute_panel,
                    faux_positifs_par_signe, load_config, pouvoir_predictif)


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
    # Variante « socle » (tâche 4 pt 4) : agrégats calculés UNIQUEMENT sur les
    # étages A+B (comparables sur les 5 krachs post-1945) et A seul (1929/1937),
    # via agreger_signes — même chemin de code, étage = métadonnée config.
    sdf, zdf = p["sign_scores"], p["metric_z"]
    seuils = cfg["normalisation"]["seuils"]
    poids_cfg = {s["key"]: float(s["poids"]) for s in cfg["signes"]}
    et = {s["key"]: s.get("etage") for s in cfg["signes"]}
    keys_ab = [k for k in sdf.columns if et.get(k) in ("A", "B")]
    keys_a = [k for k in sdf.columns if et.get(k) == "A"]
    ag_ab = agreger_signes(sdf[keys_ab], {k: poids_cfg[k] for k in keys_ab}, seuils)
    ag_a = agreger_signes(sdf[keys_a], {k: poids_cfg[k] for k in keys_a}, seuils)
    rows_s, rows_m = {}, {}
    for k in cfg["krachs"]:
        t12 = pd.Timestamp(k["date"]) - pd.DateOffset(months=12)
        # asof PAR COLONNE (DataFrame.asof écarte toute ligne contenant un NaN)
        rows_s[k["nom"]] = sdf.apply(lambda c: c.asof(t12))
        rows_m[k["nom"]] = zdf.apply(lambda c: c.asof(t12))
        rows_s[k["nom"]]["pire_z"] = ag["pire_z"].asof(t12)
        rows_s[k["nom"]]["moyenne_indicative"] = ag["moyenne_indicative"].asof(t12)
        rows_s[k["nom"]]["pire_z_socle_ab"] = ag_ab["pire_z"].asof(t12)
        rows_s[k["nom"]]["moyenne_socle_ab"] = ag_ab["moyenne_indicative"].asof(t12)
        rows_s[k["nom"]]["pire_z_socle_a"] = ag_a["pire_z"].asof(t12)
    fp_s = pd.DataFrame(rows_s)
    fp_m = pd.DataFrame(rows_m)
    OUT.mkdir(exist_ok=True)
    fp_s.to_csv(OUT / "footprint_signes.csv", index_label="signe")
    fp_m.to_csv(OUT / "footprint_metrics.csv", index_label="metrique")

    print("\nEmpreinte (score par signe, z oriente, a T-12 mois de chaque krach) :")
    print(fp_s.round(2).to_string())

    # ------------------------- faux positifs PAR SIGNE (tache 1, point 5)
    fpx = faux_positifs_par_signe(sdf, cfg["krachs"], seuils)
    fpx.to_csv(OUT / "faux_positifs_signes.csv", index_label="signe")
    print("\nFaux positifs par signe (mois >= orange sans krach sous 24 mois ;")
    print("les ~24 derniers mois, non confirmables, comptent en faux positifs) :")
    aff = fpx.copy()
    aff["taux_faux"] = (aff["taux_faux"].astype(float) * 100).round(0)
    print(aff.to_string())

    # ----------------- pouvoir predictif par signe (tache 3 v3 : persistance)
    # A = part des mois >= orange en fenetre pre-krach [T-18, T-6] (pooled) ;
    # B = part des mois tranquilles >= orange (hors [T-18, T+24] de tout krach) ;
    # NSR = B/A (Kaminsky-Reinhart, meme unite : proportion de mois).
    # NE MODIFIE PAS config.yaml : tableau d'aide a la decision uniquement.
    poids_actuels = {s["key"]: float(s["poids"]) for s in cfg["signes"]}
    pp = pouvoir_predictif(sdf, cfg["krachs"], seuils, poids_actuels)
    pp.to_csv(OUT / "pouvoir_predictif_signes.csv", index_label="signe")
    aff = pp.copy()
    for c in ("puissance_A", "fausses_alertes_B"):
        aff[c] = (aff[c].astype(float) * 100).round(0)
    for c in ("nsr", "racine_inv_nsr", "poids_final"):
        aff[c] = aff[c].astype(float).round(2)
    print("\nPouvoir predictif v4 (NSR persistance ; poids = racine(1/NSR) sous")
    print("contraintes : indicatif <= 1.0x moyenne, plafond 1.5x, plancher bruite) :")
    print(aff[["puissance_A", "fausses_alertes_B", "nsr", "racine_inv_nsr",
               "n_krachs_couverts", "n_krachs_persistants", "indicatif",
               "bruite", "plafonne", "poids_actuel", "poids_final"]].to_string())
    print(f"somme poids actuels {pp['poids_actuel'].sum():.2f} -> "
          f"somme poids finaux {pp['poids_final'].sum():.2f}")

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
    # Traçabilité des poids (tache 3 v4) : provenance + derive eventuelle entre
    # les poids en vigueur (config.yaml) et la recommandation du jour.
    drift = float((pp["poids_final"] - pp["poids_actuel"]).abs().max())
    lignes += [
        "",
        "PROVENANCE DES POIDS : " + " ".join(str(cfg.get("provenance_poids",
                                                         "non documentee")).split()),
        f"Ecart max |poids config - recommandation NSR du jour| : {drift:.2f}"
        + (" (ATTENTION : > 0.5, relancer l'analyse ou re-valider les poids)"
           if drift > 0.5 else " (OK)"),
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
