# -*- coding: utf-8 -*-
"""Phase 3 — Moteur live (quotidien).

    python monitor.py [--offline]

Recalcule TOUT le panel depuis l'historique complet (même chemin de code que
calibrate.py → z-scores strictement comparables), puis relève, PAR SIGNE, la
dernière valeur disponible (les séries ont des fréquences et délais de
publication différents). Un signe dont la donnée a plus de 12 mois est marqué
périmé et sort de l'agrégation. Journal : 1 ligne par jour d'exécution.

Tâche 1 : l'en-tête n'est plus la moyenne pondérée (diluante) mais le PIRE
signe + comptes orange/rouge, via common.agreger_signes (chemin commun).
L'ancienne moyenne survit en « moyenne indicative » (info secondaire).
"""
import sys
from datetime import date

import pandas as pd

from common import OUT, agreger_signes, compute_panel, couleur, load_config

MAX_AGE_MONTHS = 12  # au-delà, un signe est périmé et exclu de l'agrégation


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
    noms = {s["key"]: s["nom"] for s in cfg["signes"]}

    row = {"date_execution": date.today().isoformat(), "date_donnees": f"{today:%Y-%m-%d}"}
    releve = {}  # z du jour par signe (absent si périmé/gris) → agrégation commune

    print(f"\nRELEVE (mois de reference {today:%Y-%m}, execute le {row['date_execution']})")
    print("-" * 78)
    for sign in cfg["signes"]:
        k = sign["key"]
        approx = (" (qualitatif)" if sign.get("qualitatif")
                  else " (~ proxy)" if sign.get("approximatif") else "")
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
            releve[k] = z

    # ------------------------- en-tête non diluant (chemin de code commun)
    # Poids de TOUS les signes de la config : la couverture rapporte les signes
    # à jour au total de crédibilité, signes gris/qualitatifs inclus.
    poids = {s["key"]: float(s["poids"]) for s in cfg["signes"]}
    ag = agreger_signes(pd.DataFrame(releve, index=[today]),
                        poids, seuils).iloc[0]
    pire_k = ag["pire_signe"] if isinstance(ag["pire_signe"], str) else ""
    zp = float(ag["pire_z"])
    zm = float(ag["moyenne_indicative"])
    cc = str(ag["couleur_entete"])
    couverture = float(ag["couverture"])

    # Anciennes colonnes conservées à l'identique (composite = moyenne pondérée).
    row.update(composite=round(zm, 3) if zm == zm else "",
               couleur_composite=couleur(zm, seuils),
               couverture=round(couverture, 3))
    # Nouvelles colonnes (tâche 1).
    row.update(pire_signe=pire_k,
               z_pire=round(zp, 3) if zp == zp else "",
               n_orange=int(ag["n_orange"]), n_rouge=int(ag["n_rouge"]),
               couleur_entete=cc,
               moyenne_indicative=round(zm, 3) if zm == zm else "")

    print("-" * 78)
    print(f"  EN-TETE : {cc.upper()} — pire signe : {noms.get(pire_k, pire_k)} "
          f"z={zp:+.2f} — {int(ag['n_rouge'])} rouge / {int(ag['n_orange'])} orange")
    print(f"  moyenne indicative (ancien composite, diluante) : z={zm:+.2f} "
          f"({couleur(zm, seuils)}) ; couverture ponderee {couverture:.0%}")

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

    # Faux positifs : sur la couleur d'EN-TÊTE (pire signe) ; les anciennes
    # lignes du journal sans cette colonne retombent sur couleur_composite.
    ce = j["couleur_entete"] if "couleur_entete" in j.columns else pd.Series(dtype=str)
    ce = ce.reindex(j.index)
    if "couleur_composite" in j.columns:
        ce = ce.fillna(j["couleur_composite"])
    n_rouge_hist = int((ce == "rouge").sum())
    print(f"\nJournal : {len(j)} releve(s), dont {n_rouge_hist} en-tete(s) rouge(s). "
          f"Compteur de faux positifs live : {n_rouge_hist} rouge(s) sans krach constate a ce jour.")
    if p["indisponibles"]:
        print("Metriques optionnelles indisponibles : "
              + ", ".join(k for k, _ in p["indisponibles"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
