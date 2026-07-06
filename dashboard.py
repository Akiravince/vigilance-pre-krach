# -*- coding: utf-8 -*-
"""Phase 5 — Restitution HTML statique.

    python dashboard.py

Lit output/journal.csv, output/footprint_signes.csv, data/history/composite.csv
→ écrit output/dashboard.html (autonome, aucun JS externe).
"""
import sys

import pandas as pd

from common import DATA, OUT, couleur, load_config

COL = {"vert": "#2e7d32", "orange": "#ef6c00", "rouge": "#c62828", "gris": "#9e9e9e"}


def thermo(z: float, seuils: dict) -> str:
    """Barre thermomètre : z orienté borné à [-3, +3]."""
    if z != z:
        return '<div class="thermo"><span class="na">indisponible</span></div>'
    pct = max(0.0, min(100.0, (z + 3) / 6 * 100))
    c = COL[couleur(z, seuils)]
    return (f'<div class="thermo"><div class="fill" style="width:{pct:.0f}%;'
            f'background:{c}"></div><span class="zlab">z={z:+.2f}</span></div>')


def sparkline(comp: pd.Series, w: int = 640, h: int = 80) -> str:
    s = comp.dropna().tail(240)  # 20 ans
    if len(s) < 2:
        return ""
    lo, hi = min(s.min(), -1), max(s.max(), 2)
    xs = [i / (len(s) - 1) * (w - 10) + 5 for i in range(len(s))]
    ys = [h - 5 - (v - lo) / (hi - lo) * (h - 10) for v in s]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    y15 = h - 5 - (1.5 - lo) / (hi - lo) * (h - 10)
    return (f'<svg viewBox="0 0 {w} {h}" class="spark">'
            f'<line x1="5" y1="{y15:.1f}" x2="{w-5}" y2="{y15:.1f}" '
            f'stroke="#c62828" stroke-dasharray="4 3" stroke-width="1"/>'
            f'<polyline points="{pts}" fill="none" stroke="#37474f" stroke-width="1.5"/>'
            f'</svg><div class="legend">Composite — 20 dernières années '
            f'(pointillé rouge = seuil {1.5})</div>')


def _f(v) -> float:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return float("nan")


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
    comp_hist = pd.read_csv(DATA / "history" / "composite.csv",
                            index_col=0, parse_dates=True)["composite"]
    n_rouge = int((j["couleur_composite"] == "rouge").sum())

    zc = float(r["composite"])
    cc = str(r["couleur_composite"])

    cards = []
    for sign in cfg["signes"]:
        k = sign["key"]
        z = _f(r.get(f"z_{k}"))
        if sign.get("qualitatif"):
            badge = '<span class="badge badge-q">⚠ qualitatif — jugement, non mesuré</span>'
        elif sign.get("approximatif"):
            badge = '<span class="badge">≈ proxy approximatif</span>'
        else:
            badge = ""
        mets = "".join(
            f'<li>{m["description"]}'
            + (' <span class="badge">≈</span>' if m.get("approximatif") else "")
            + (' <em>(optionnelle)</em>' if m.get("optional") else "")
            + "</li>"
            for m in sign["metrics"]
        )
        cards.append(f"""
    <div class="card" style="border-left:6px solid {COL[couleur(z, seuils)]}">
      <h3>n°{sign['numero']} — {sign['nom']} {badge}</h3>
      {thermo(z, seuils)}
      <details><summary>métriques (poids crédibilité {sign['poids']})</summary><ul>{mets}</ul></details>
    </div>""")

    # tableau empreinte : signes × krachs + colonne aujourd'hui
    noms = {s["key"]: f"n°{s['numero']} {s['nom']}" for s in cfg["signes"]}
    head = "".join(f"<th>{c}</th>" for c in fp.columns)
    body = []
    for idx, row_fp in fp.iterrows():
        cells = []
        for v in row_fp:
            if pd.isna(v):
                cells.append('<td class="na">–</td>')
            else:
                cells.append(f'<td style="color:{COL[couleur(float(v), seuils)]}">{float(v):+.2f}</td>')
        tv = _f(r["composite"] if idx == "composite" else r.get(f"z_{idx}"))
        tcell = ('<td class="na">–</td>' if tv != tv else
                 f'<td class="today" style="color:{COL[couleur(tv, seuils)]}">{tv:+.2f}</td>')
        label = "COMPOSITE" if idx == "composite" else noms.get(idx, idx)
        body.append(f"<tr><td class='rowh'>{label}</td>{''.join(cells)}{tcell}</tr>")

    indispo_note = ""
    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Vigilance pré-krach — marchés US</title>
<style>
 body{{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#f5f5f2;color:#263238}}
 .wrap{{max-width:860px;margin:0 auto;padding:24px}}
 h1{{font-size:1.5em;margin-bottom:0}} .sub{{color:#607d8b;margin-top:4px}}
 .gauge{{background:#fff;border-radius:10px;padding:18px 22px;margin:18px 0;
        box-shadow:0 1px 3px rgba(0,0,0,.12);border-left:8px solid {COL[cc]}}}
 .gauge .big{{font-size:2em;font-weight:700;color:{COL[cc]}}}
 .card{{background:#fff;border-radius:8px;padding:12px 16px;margin:10px 0;
       box-shadow:0 1px 2px rgba(0,0,0,.10)}}
 .card h3{{margin:2px 0 8px;font-size:1.02em}}
 .badge{{background:#fff3e0;color:#e65100;border:1px solid #ffb74d;border-radius:10px;
        font-size:.72em;padding:1px 8px;vertical-align:middle}}
 .badge-q{{background:#ede7f6;color:#4527a0;border-color:#b39ddb}}
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
couverture pondérée {float(r['couverture']):.0%}</div>

<div class="gauge">
  <div>Indice composite (z pondéré crédibilité)</div>
  <div class="big">{cc.upper()} &nbsp; z = {zc:+.2f}</div>
  <div class="legend">vert &lt; {seuils['vert']} ≤ orange &lt; {seuils['orange']} ≤ rouge —
  compteur de faux positifs live : <b>{n_rouge}</b> relevé(s) rouge(s) sans krach constaté</div>
  {sparkline(comp_hist)}
</div>

<h2>Les {len(cfg['signes'])} signes suivis</h2>
{''.join(cards)}

<h2>Comparaison à l'empreinte des krachs (z par signe à T−12 mois)</h2>
<table><tr><th></th>{head}<th>Aujourd'hui</th></tr>{''.join(body)}</table>
<div class="legend">« – » : série trop récente pour couvrir ce krach (la plupart des
séries publiques démarrent après 1945, voire 1990).</div>

<div class="warn" style="margin-top:18px"><b>Notes d'honnêteté (à ne jamais retirer)</b><br>
· Instrument d'analyse et de pédagogie — <b>pas</b> un signal de trading, aucune prétention sur le <i>timing</i>.<br>
· Signe n°2 marqué « ≈ » : proxies imparfaits de la psychologie de foule.<br>
· Signes « ⚠ qualitatif » (ex. n°7 déréglementation) : jugement, PAS une mesure — gris et hors composite tant qu'aucune évaluation manuelle n'est fournie.<br>
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
