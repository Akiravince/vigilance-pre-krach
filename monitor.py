# -*- coding: utf-8 -*-
"""Phase 3 — Moteur live (quotidien).

    python monitor.py [--offline]

Recalcule TOUT le panel depuis l'historique complet (même chemin de code que
calibrate.py → z-scores strictement comparables), puis relève, PAR SIGNE, la
dernière valeur disponible (les séries ont des fréquences et délais de
publication différents). Un signe dont la donnée a plus de 12 mois est marqué
périmé et sort du composite. Journal : 1 ligne par jour d'exécution.
"""
import sys
from datetime import date

import pandas as pd

from common import OUT, compute_panel, couleur, load_config

MAX_AGE_MONTHS = 12  # au-delà, un signe est périmé et exclu du composite


def main() -> int:
    offline = "--offline" in sys.argv
    cfg = load_config()
    seuils = cfg["normalisation"]["seuils"]
    if offline:
        print("MODE OFFLINE - donnees synthetiques, resultats NON interpretables\n")

    print("Collecte et normalisation...")
    p = compute_panel(cfg, offline=offline)
    sdf = p["sign_scores"]
    today = sdf.dropna(how="all").index[-1]

    poids_total = sum(float(s["poids"]) for s in cfg["signes"])
    row = {"date_execution": date.today().isoformat(), "date_donnees": f"{today:%Y-%m-%d}"}
    num = den = 0.0

    print(f"\nRELEVE (mois de reference {today:%Y-%m}, execute le {row['date_execution']})")
    print("-" * 78)
    for sign in cfg["signes"]:
        k, w = sign["key"], float(sign["poids"])
        approx = " (~ proxy)" if sign.get("approximatif") else ""
        lv = sdf[k].last_valid_index() if k in sdf.columns else None
        if lv is None:
            print(f"  GRIS    z=  n/a  (aucune donnee)      "
                  f"n.{sign['numero']:<2d} {sign['nom']}{approx}")
            row[f"z_{k}"], row[f"couleur_{k}"], row[f"date_{k}"] = "", "gris", ""
            continue
        z = float(sdf[k].loc[lv])
        age = (today.year - lv.year) * 12 + (today.month - lv.month)
        perime = age > MAX_AGE_MONTHS
        c = "gris" if perime else couleur(z, seuils)
        note = f"(donnees {lv:%Y-%m}" + (", PERIMEES)" if perime else ")")
        print(f"  {c.upper():6s}  z={z:+5.2f}  {note:22s} "
              f"n.{sign['numero']:<2d} {sign['nom']}{approx}")
        row[f"z_{k}"] = round(z, 3)
        row[f"couleur_{k}"] = c
        row[f"date_{k}"] = f"{lv:%Y-%m}"
        if not perime:
            num += w * z
            den += w

    zc = num / den if den else float("nan")
    cc = couleur(zc, seuils)
    couverture = den / poids_total
    row.update(composite=round(zc, 3) if zc == zc else "",
               couleur_composite=cc, couverture=round(couverture, 3))
    print("-" * 78)
    print(f"  COMPOSITE : {cc.upper()}  z={zc:+.2f}   "
          f"couverture ponderee : {couverture:.0%} "
          f"(signes a jour uniquement, poids credibilite)")

    # ------------------------------------------------ journal (1 ligne/jour)
    OUT.mkdir(exist_ok=True)
    jf = OUT / "journal.csv"
    try:
        j = pd.read_csv(jf, dtype=str) if jf.exists() else pd.DataFrame()
    except Exception:
        j = pd.DataFrame()
    if len(j) and "date_execution" in j.columns:
        j = j[j["date_execution"] != row["date_execution"]]
    j = pd.concat([j, pd.DataFrame([row])], ignore_index=True)
    j = j.dropna(axis=1, how="all")
    j.to_csv(jf, index=False)

    n_rouge = int((j["couleur_composite"] == "rouge").sum())
    print(f"\nJournal : {len(j)} releve(s), dont {n_rouge} rouge(s). "
          f"Compteur de faux positifs live : {n_rouge} rouge(s) sans krach constate a ce jour.")
    if p["indisponibles"]:
        print("Metriques optionnelles indisponibles : "
              + ", ".join(k for k, _ in p["indisponibles"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
