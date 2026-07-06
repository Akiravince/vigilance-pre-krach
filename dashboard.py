# -*- coding: utf-8 -*-
"""Phase 5 — Restitution HTML statique.

    python dashboard.py

Lit output/journal.csv, output/footprint_signes.csv, data/history/composite.csv
→ écrit output/dashboard.html (autonome, aucun JS externe, SVG inline).

Tâche 1 : l'en-tête est le PIRE signe (nom + z + couleur) et les comptes
orange/rouge — plus la moyenne, qui masquait les extrêmes. La moyenne
pondérée survit en « moyenne indicative », en petit. Les signes sont
présentés en scorecard triée par z décroissant.
"""
import sys

import pandas as pd

from common import DATA, OUT, agreger_signes, couleur, load_config

COL = {"vert": "#2e7d32", "orange": "#ef6c00", "rouge": "#c62828", "gris": "#9e9e9e"}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def thermo(z: float, seuils: dict, c: str | None = None) -> str:
    """Barre thermomètre : z orienté borné à [-3, +3]."""
    if z != z:
        return '<div class="thermo"><span class="na">indisponible</span></div>'
    pct = max(0.0, min(100.0, (z + 3) / 6 * 100))
    col = COL[c if c in COL else couleur(z, seuils)]
    return (f'<div class="thermo"><div class="fill" style="width:{pct:.0f}%;'
            f'background:{col}"></div><span class="zlab">z={z:+.2f}</span></div>')


def sparkline(pire: pd.Series, moyenne: pd.Series, seuil: float,
              w: int = 640, h: int = 80) -> str:
    """Pire signe (trait foncé) + moyenne indicative (gris clair), 20 ans."""
    p = pire.dropna().tail(240)
    if len(p) < 2:
        return ""
    m = moyenne.reindex(p.index)
    lo = min(p.min(), m.min(skipna=True), -1)
    hi = max(p.max(), m.max(skipna=True), 2)

    def pts(s: pd.Series) -> str:
        v = s.dropna()
        if len(v) < 2:
            return ""
        xs = {d: i / (len(p) - 1) * (w - 10) + 5 for i, d in enumerate(p.index)}
        return " ".join(f"{xs[d]:.1f},{h - 5 - (val - lo) / (hi - lo) * (h - 10):.1f}"
                        for d, val in v.items() if d in xs)

    ys = h - 5 - (seuil - lo) / (hi - lo) * (h - 10)
    poly_m = (f'<polyline points="{pts(m)}" fill="none" stroke="#b0bec5" '
              f'stroke-width="1"/>' if pts(m) else "")
    return (f'<svg viewBox="0 0 {w} {h}" class="spark">'
            f'<line x1="5" y1="{ys:.1f}" x2="{w-5}" y2="{ys:.1f}" '
            f'stroke="#c62828" stroke-dasharray="4 3" stroke-width="1"/>'
            f'{poly_m}'
            f'<polyline points="{pts(p)}" fill="none" stroke="#37474f" stroke-width="1.5"/>'
            f'</svg><div class="legend">20 dernières années — trait foncé : pire signe (en-tête) ; '
            f'gris clair : moyenne indicative ; pointillé rouge = seuil {seuil}</div>')


def main() -> int:
    cfg = load_config()
    seuils = cfg["normalisation"]["seuils"]

    jf = OUT / "journal.csv"
    if not jf.exists():
        print("journal.csv absent — lancer d'abord monitor.py", file=sys.stderr)
        return 1
    j = pd.read_csv(jf)
    r = j.iloc[-1]

    fp = pd.read_csv(OUT / "footprint_signes.csv", index_col=0)
    fpxf = OUT / "faux_positifs_signes.csv"
    fpx = pd.read_csv(fpxf, index_col=0) if fpxf.exists() else None
    hist = pd.read_csv(DATA / "history" / "composite.csv", index_col=0, parse_dates=True)
    pire_hist = hist["pire_z"] if "pire_z" in hist.columns else hist["composite"]
    moy_hist = hist.get("moyenne_indicative", hist["composite"])

    # ------------------------- en-tête (tâche 1) : pire signe, plus la moyenne
    noms = {s["key"]: s["nom"] for s in cfg["signes"]}
    pire_k = str(r.get("pire_signe", "") or "")
    zp = _f(r.get("z_pire"))
    zm = _f(r.get("moyenne_indicative", r.get("composite")))
    cc = str(r.get("couleur_entete") or couleur(zp, seuils))
    n_o = int(_f(r.get("n_orange"))) if r.get("n_orange") == r.get("n_orange") else 0
    n_r = int(_f(r.get("n_rouge"))) if r.get("n_rouge") == r.get("n_rouge") else 0

    # Calibration (tâche 4 pt 3) : en FRACTION des signes mesurables, pas en
    # compte brut — les krachs anciens n'avaient que 2-3 séries. Comptes à T-12
    # recomptés depuis l'empreinte via agreger_signes (chemin de code commun).
    poids = {s["key"]: float(s["poids"]) for s in cfg["signes"]}
    sign_keys = [s["key"] for s in cfg["signes"]]
    ag_k = agreger_signes(fp.T.apply(pd.to_numeric, errors="coerce"), poids, seuils)
    fp_signes = fp.loc[[i for i in fp.index if i in sign_keys]].apply(
        pd.to_numeric, errors="coerce")
    mes_k = fp_signes.notna().sum(axis=0)              # signes mesurables par krach
    frac_r = (ag_k["n_rouge"] / mes_k).dropna()
    frac_o = (ag_k["n_orange"] / mes_k).dropna()
    # aujourd'hui : signes non gris (à jour) d'après le journal
    mes_now = sum(1 for k in sign_keys
                  if str(r.get(f"couleur_{k}", "")) in ("vert", "orange", "rouge"))

    # Compteur de faux positifs live : couleur d'en-tête (repli : ancienne colonne).
    ce = j["couleur_entete"] if "couleur_entete" in j.columns else pd.Series(dtype=str)
    ce = ce.reindex(j.index)
    if "couleur_composite" in j.columns:
        ce = ce.fillna(j["couleur_composite"])
    n_rouge_hist = int((ce == "rouge").sum())

    # --------------------------------- scorecard : TOUS les signes, z décroissant
    entries = []
    for sign in cfg["signes"]:
        k = sign["key"]
        z = _f(r.get(f"z_{k}"))
        c = str(r.get(f"couleur_{k}") or couleur(z, seuils))
        d = r.get(f"date_{k}")
        d = str(d) if d == d and d else "—"
        entries.append((sign, z, c, d))
    # tri : z décroissant ; à z indisponible égal, poids crédibilité décroissant
    entries.sort(key=lambda e: (e[1] != e[1],
                                -(e[1] if e[1] == e[1] else 0.0),
                                -float(e[0]["poids"])))

    cards = []
    for sign, z, c, d in entries:
        k = sign["key"]
        if sign.get("qualitatif"):
            badge = '<span class="badge badge-q">⚠ qualitatif — jugement, non mesuré</span>'
        elif sign.get("approximatif"):
            badge = '<span class="badge">≈ proxy approximatif</span>'
        else:
            badge = ""
        # Étage d'historique (tâche 4) : A backtestable 7/7, B post-1945, C récent
        et = sign.get("etage")
        if et:
            badge += f' <span class="badge badge-e">étage {et}</span>'
        else:
            badge += ' <span class="badge badge-g">hors étage — sans données</span>'
        if c == "gris":
            badge += ' <span class="badge badge-g">gris — hors en-tête</span>'
        # Drapeaux de fiabilité issus de la re-pondération NSR (config.yaml)
        if sign.get("indicatif"):
            badge += ' <span class="badge badge-g">indicatif — couverture faible, poids plafonné 1.0×</span>'
        if sign.get("bruite"):
            badge += ' <span class="badge">bruité — NSR ≥ 1, sous-pondéré</span>'
        if sign.get("plafonne"):
            badge += ' <span class="badge badge-g">plafonné</span>'
        mets = "".join(
            f'<li>{m["description"]}'
            + (' <span class="badge">≈</span>' if m.get("approximatif") else "")
            + (' <em>(optionnelle)</em>' if m.get("optional") else "")
            + "</li>"
            for m in sign["metrics"]
        )
        ztxt = f"z={z:+.2f}" if z == z else "z indisponible"
        fptxt = ""
        if fpx is not None and k in fpx.index:
            n_a, n_f = int(fpx.loc[k, "n_alertes"]), int(fpx.loc[k, "n_faux"])
            depuis = pd.Timestamp(fpx.loc[k, "debut"]).year
            if n_a:
                tx = float(fpx.loc[k, "taux_faux"])
                fptxt = (f' · faux positifs : <b>{tx:.0%}</b>'
                         f' ({n_f}/{n_a} mois ≥ orange depuis {depuis})')
            else:
                fptxt = f' · faux positifs : aucun mois ≥ orange depuis {depuis}'
        cards.append(f"""
    <div class="card" style="border-left:6px solid {COL.get(c, COL['gris'])}">
      <h3>n°{sign['numero']} — {sign['nom']} {badge}</h3>
      <div class="meta">{c} · {ztxt} · données {d}{fptxt}</div>
      {thermo(z, seuils, c)}
      <details><summary>métriques (poids crédibilité {sign['poids']})</summary><ul>{mets}</ul></details>
    </div>""")

    # ------------------- tableau empreinte : signes × krachs + colonne aujourd'hui
    row_labels = {s["key"]: f"n°{s['numero']} {s['nom']}" for s in cfg["signes"]}
    row_labels.update({"pire_z": "PIRE SIGNE (z max)",
                       "moyenne_indicative": "moyenne indicative",
                       "composite": "moyenne indicative (ex-composite)",
                       "pire_z_socle_ab": "PIRE SIGNE — socle A+B (9 signes comparables post-1945)",
                       "moyenne_socle_ab": "moyenne — socle A+B",
                       "pire_z_socle_a": "PIRE SIGNE — socle A seul (2 signes, voit 1929/1937)"})
    today_val = {"pire_z": zp, "moyenne_indicative": zm, "composite": zm,
                 "pire_z_socle_ab": _f(r.get("z_pire_socle_ab")),
                 "moyenne_socle_ab": _f(r.get("moyenne_socle_ab")),
                 "pire_z_socle_a": _f(r.get("z_pire_socle_a"))}
    head = "".join(f"<th>{c}</th>" for c in fp.columns)
    body = []
    for idx, row_fp in fp.iterrows():
        cells = []
        for v in row_fp:
            if pd.isna(v):
                cells.append('<td class="na">–</td>')
            else:
                cells.append(f'<td style="color:{COL[couleur(float(v), seuils)]}">{float(v):+.2f}</td>')
        tv = today_val.get(idx, _f(r.get(f"z_{idx}")))
        tcell = ('<td class="na">–</td>' if tv != tv else
                 f'<td class="today" style="color:{COL[couleur(tv, seuils)]}">{tv:+.2f}</td>')
        body.append(f"<tr><td class='rowh'>{row_labels.get(idx, idx)}</td>{''.join(cells)}{tcell}</tr>")

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Vigilance pré-krach — marchés US</title>
<style>
 body{{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#f5f5f2;color:#263238}}
 .wrap{{max-width:860px;margin:0 auto;padding:24px}}
 h1{{font-size:1.5em;margin-bottom:0}} .sub{{color:#607d8b;margin-top:4px}}
 .gauge{{background:#fff;border-radius:10px;padding:18px 22px;margin:18px 0;
        box-shadow:0 1px 3px rgba(0,0,0,.12);border-left:8px solid {COL[cc]}}}
 .gauge .big{{font-size:1.6em;font-weight:700;color:{COL[cc]}}}
 .gauge .counts{{font-size:1.1em;margin-top:4px}}
 .gauge .calib{{color:#455a64;font-size:.9em;margin-top:6px}}
 .gauge .moy{{color:#78909c;font-size:.85em;margin-top:8px}}
 .card{{background:#fff;border-radius:8px;padding:12px 16px;margin:10px 0;
       box-shadow:0 1px 2px rgba(0,0,0,.10)}}
 .card h3{{margin:2px 0 8px;font-size:1.02em}}
 .meta{{color:#78909c;font-size:.82em;margin-bottom:6px}}
 .badge{{background:#fff3e0;color:#e65100;border:1px solid #ffb74d;border-radius:10px;
        font-size:.72em;padding:1px 8px;vertical-align:middle}}
 .badge-q{{background:#ede7f6;color:#4527a0;border-color:#b39ddb}}
 .badge-g{{background:#eceff1;color:#546e7a;border-color:#b0bec5}}
 .badge-e{{background:#e3f2fd;color:#1565c0;border-color:#90caf9;font-weight:600}}
 .thermo{{position:relative;background:#eceff1;height:22px;border-radius:11px;overflow:hidden}}
 .fill{{height:100%}} .zlab{{position:absolute;top:2px;left:10px;font-size:.8em;color:#263238}}
 .na{{color:#90a4ae;font-style:italic}}
 table{{border-collapse:collapse;width:100%;background:#fff;font-size:.88em}}
 th,td{{border:1px solid #e0e0e0;padding:5px 8px;text-align:center}}
 .rowh{{text-align:left;font-weight:600}} .today{{background:#fffde7;font-weight:700}}
 .spark{{width:100%;background:#fff;border-radius:6px;margin-top:6px}}
 .legend{{font-size:.75em;color:#78909c}}
 .warn{{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:12px 16px;font-size:.88em}}
 footer{{color:#90a4ae;font-size:.8em;margin:24px 0}}
</style></head><body><div class="wrap">
<h1>Vigilance pré-krach — marchés US</h1>
<div class="sub">Données au {r['date_donnees']} · exécuté le {r['date_execution']} ·
couverture pondérée {_f(r.get('couverture')):.0%}</div>

<div class="gauge">
  <div>État d'alerte — piloté par le pire signe (agrégation non diluante)</div>
  <div class="big">{cc.upper()} — pire signe : {noms.get(pire_k, pire_k or '?')} &nbsp;z = {zp:+.2f}</div>
  <div class="counts"><b>{n_r}</b> rouge / <b>{n_o}</b> orange
  (sur les signes à jour, seuils : orange ≥ {seuils['vert']}, rouge ≥ {seuils['orange']})</div>
  <div class="calib">calibration : aujourd'hui <b>{n_r} rouge / {mes_now} signes mesurables
  ({n_r / mes_now if mes_now else float('nan'):.0%})</b> et {n_o} orange ({n_o / mes_now if mes_now else float('nan'):.0%})
  — à T−12 des {len(fp.columns)} krachs : médiane rouge <b>{frac_r.median():.0%}</b>
  (min–max {frac_r.min():.0%}–{frac_r.max():.0%}), médiane orange {frac_o.median():.0%}
  (fractions des signes mesurables à CHAQUE époque : {int(mes_k.min())} en {mes_k.idxmin()}, {int(mes_k.max())} en {mes_k.idxmax()})</div>
  <div class="moy">moyenne indicative (pondérée crédibilité, ex-« composite » — dilue les
  extrêmes, ne pilote plus l'en-tête) : z = {zm:+.2f} ({couleur(zm, seuils)}) —
  compteur de faux positifs live : <b>{n_rouge_hist}</b> en-tête(s) rouge(s) sans krach constaté</div>
  {sparkline(pire_hist, moy_hist, seuils['orange'])}
</div>

<h2>Scorecard des {len(cfg['signes'])} signes — triés par z décroissant</h2>
<div class="legend">Taux de faux positifs par signe : part des mois ≥ orange (z ≥ {seuils['vert']})
non suivis d'un krach listé sous 24 mois, sur tout l'historique du signe — un taux élevé
signale un indicateur chroniquement bruyant. Les ~24 derniers mois, non encore confirmables,
comptent en faux positifs.</div>
{''.join(cards)}

<h2>Comparaison à l'empreinte des krachs (z par signe à T−12 mois)</h2>
<table><tr><th></th>{head}<th>Aujourd'hui</th></tr>{''.join(body)}</table>
<div class="legend">« – » : série trop récente pour couvrir ce krach (la plupart des
séries publiques démarrent après 1945, voire 1990).</div>

<div class="warn" style="margin-top:18px"><b>Notes d'honnêteté (à ne jamais retirer)</b><br>
· Instrument d'analyse et de pédagogie — <b>pas</b> un signal de trading, aucune prétention sur le <i>timing</i>.<br>
· L'en-tête « pire signe » est volontairement plus sensible que l'ancienne moyenne :
plus d'alertes = plus de faux positifs. C'est le prix de la non-dilution.<br>
· Signe n°2 marqué « ≈ » : proxies imparfaits de la psychologie de foule.<br>
· Signes « ⚠ qualitatif » (ex. n°7 déréglementation) : jugement, PAS une mesure — gris et hors en-tête tant qu'aucune évaluation manuelle n'est fournie.<br>
· Calibration sur les seuls krachs survenus → biais de survie ; le vrai taux de faux positifs est inconnu et probablement élevé.<br>
· Le déclencheur (signe 16) est par nature non mesurable : l'outil suit la fragilité accumulée, pas l'étincelle.</div>

<footer>Généré par dashboard.py — sources : FRED (St. Louis Fed), BIS, Fed Z.1/SLOOS, Shiller, AAII, CBOE, FINRA.</footer>
</div></body></html>"""

    OUT.mkdir(exist_ok=True)
    (OUT / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"OK → {OUT / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
