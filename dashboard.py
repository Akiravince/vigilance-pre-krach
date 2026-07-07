# -*- coding: utf-8 -*-
"""Phase 5 — Restitution HTML statique.

    python dashboard.py

Lit output/journal.csv, output/footprint_signes.csv, output/faux_positifs_signes.csv
et data/history/sign_scores.csv → écrit output/dashboard.html (autonome, aucun JS
externe hormis un <details> repliable natif, SVG inline).

Tâche 6 / 6b — Refonte visuelle GRAND PUBLIC. RÈGLE ABSOLUE : SEUL l'affichage
change. Aucun calcul touché — dashboard.py ne fait que LIRE les CSV et écrire le
HTML ; il n'écrit aucun CSV. Deux niveaux de lecture :
  · SURFACE : feu de synthèse « Niveau de vigilance d'ensemble » + phrase en clair
    + encart « signal le plus alarmant » + légende + mission + jauge « où en est-on
    vs la veille des krachs » + les signaux traduits (titre NEUTRE + mot d'échelle
    + couleur). Un titre NOMME le risque surveillé, il n'affirme pas un état présent.
  · DÉTAIL (repliable) : fiches techniques par signe (poids, z exact, badges,
    faux positifs) + un GRAPHIQUE d'historique par indicateur mesuré (tâche 6b :
    courbe z lue depuis sign_scores.csv, bandes de fond aux seuils, krachs ombrés,
    « pas de données à l'époque » pour un krach antérieur à la série), matrice
    d'empreinte, socles A+B / A, moyenne indicative, notes d'honnêteté.
Le feu = NIVEAU DE SYNTHÈSE (pas le pire signe).
"""
import sys

import pandas as pd

from common import DATA, OUT, agreger_signes, couleur, load_config

COL = {"vert": "#2e7d32", "orange": "#ef6c00", "rouge": "#c62828", "gris": "#9e9e9e"}
COL_BG = {"vert": "#e8f5e9", "orange": "#fff3e0", "rouge": "#fdecea", "gris": "#eceff1"}

# Dictionnaire grand public — titres NEUTRES (nomment le risque, n'affirment pas
# un état présent). Traductions validées (tâche 6) ; les 4 corrections demandées
# (n°3, 6, 8, 12) et la neutralisation générale des 14 titres sont intégrées.
TITRE = {
    "credit": "Endettement et levier (crédit, dette de marché, hors-bilan)",
    "euphorie": "L'euphorie spéculative des particuliers",
    "standards_pret": "Facilité d'accès au crédit bancaire",
    "survalorisation": "Valorisation des actions (cherté par rapport aux profits)",
    "monetaire": "La facilité des conditions monétaires (taux, liquidités)",
    "prime_risque": "L'écart de rémunération entre entreprises fragiles et solides",
    "fragilite": "Les banques et institutions financières sont-elles elles-mêmes fragiles ?",
    "surchauffe": "Les achats d'actions à crédit (argent emprunté)",
    "desequilibres": "Les États-Unis dépendent trop des capitaux étrangers "
                     "(déséquilibre qui peut se retourner brutalement)",
    "inegalites": "La concentration des richesses (part du top 1 %)",
    "dereglementation": "Les garde-fous réglementaires (déréglementation)",
    "narratif": "Le récit « cette fois, c'est différent »",
    "reflexivite": "Les boucles qui amplifient les hausses (rachats financés par la dette)",
    "ponzi": "La dépendance de la dette au refinancement (dynamique « Ponzi »)",
}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def mot_echelle(z: float) -> str:
    """Échelle en mots (pur affichage) : bas < normal < élevé < très élevé <
    extrême. Seuils d'affichage -0.5 / 0.5 / 1.5 / 2.5. « bas » distingue un
    signal franchement sous la norme (info en soi, plutôt rassurante) d'un
    signal simplement normal. N'affecte AUCUN seuil de couleur ni calcul."""
    if z != z:
        return "non mesuré"
    if z < -0.5:
        return "bas"
    if z < 0.5:
        return "normal"
    if z < 1.5:
        return "élevé"
    if z < 2.5:
        return "très élevé"
    return "extrême"


def bar(z: float, c: str) -> str:
    """Barre visuelle : z orienté borné à [-3, +3] → largeur [0, 100 %]."""
    if z != z:
        return '<div class="bar"><span class="na">non mesuré</span></div>'
    pct = max(0.0, min(100.0, (z + 3) / 6 * 100))
    return (f'<div class="bar"><div class="fill" style="width:{pct:.0f}%;'
            f'background:{COL[c]}"></div></div>')


def chart_svg(series: pd.Series, seuils: dict, krachs: list) -> str:
    """Tâche 6b — mini-graphique d'historique d'un indicateur (AFFICHAGE seul, lu
    depuis data/history/sign_scores.csv, aucun z recalculé). Bandes de fond
    vert/orange/rouge aux seuils 0.5/1.5 ; courbe z de la 1re donnée réelle à
    aujourd'hui ; 7 krachs ombrés (grisés + « pas de données à l'époque » s'ils
    précèdent la série, jamais l'impression que l'indicateur n'a rien vu) ;
    marqueur aujourd'hui ; années de krach staggerées pour rester lisibles."""
    s = series.dropna()
    if len(s) < 2:
        return ""
    key = str(series.name)
    start, today = s.index.min(), s.index.max()
    z_today = float(s.iloc[-1])
    axis0 = min(start, min(d for _, d in krachs))
    a0, t0 = axis0.toordinal(), today.toordinal()
    span = max(1, t0 - a0)
    ymin = min(float(s.min()), -1.0)
    ymax = max(float(s.max()), 2.0)
    W, H = 560, 140
    PX0, PX1, PYt, PYb = 6, 554, 30, 116

    def X(d):
        return PX0 + (d.toordinal() - a0) / span * (PX1 - PX0)

    def Y(z):
        z = max(ymin, min(ymax, z))
        return PYb - (z - ymin) / (ymax - ymin) * (PYb - PYt)

    def cl(y):
        return max(PYt, min(PYb, y))

    y05, y15 = cl(Y(0.5)), cl(Y(1.5))
    bands = (
        f'<rect x="{PX0}" y="{y05:.1f}" width="{PX1-PX0}" height="{PYb-y05:.1f}" fill="{COL_BG["vert"]}"/>'
        f'<rect x="{PX0}" y="{y15:.1f}" width="{PX1-PX0}" height="{y05-y15:.1f}" fill="{COL_BG["orange"]}"/>'
        f'<rect x="{PX0}" y="{PYt}" width="{PX1-PX0}" height="{y15-PYt:.1f}" fill="{COL_BG["rouge"]}"/>'
        f'<line x1="{PX0}" y1="{y05:.1f}" x2="{PX1}" y2="{y05:.1f}" stroke="#c8bfae" stroke-width="0.6" stroke-dasharray="3 2"/>'
        f'<line x1="{PX0}" y1="{y15:.1f}" x2="{PX1}" y2="{y15:.1f}" stroke="#e0b48a" stroke-width="0.6" stroke-dasharray="3 2"/>')
    xs = X(start)
    has_grey = xs > PX0 + 1
    grey = ""
    if has_grey:
        grey = (
            f'<defs><pattern id="hd_{key}" width="6" height="6" patternTransform="rotate(45)" '
            f'patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#eceff1"/>'
            f'<line x1="0" y1="0" x2="0" y2="6" stroke="#cfd8dc" stroke-width="1.4"/></pattern></defs>'
            f'<rect x="{PX0}" y="{PYt}" width="{xs-PX0:.1f}" height="{PYb-PYt}" fill="url(#hd_{key})"/>'
            f'<text x="{(PX0+xs)/2:.0f}" y="{(PYt+PYb)/2:.0f}" text-anchor="middle" '
            f'class="nodata">pas de données à l\'époque</text>')
    kr = []
    prev_x, prev_row = -999.0, 0
    for nom, d in sorted(krachs, key=lambda nd: nd[1]):
        if d.toordinal() < a0:
            continue
        x = X(d)
        avant = d < start
        fill = "#b0bec5" if avant else "#78909c"
        op = "0.30" if avant else "0.34"
        row = (1 - prev_row) if (x - prev_x) < 42 else 0
        prev_x, prev_row = x, row
        ly = PYt - 4 - row * 9
        kr.append(
            f'<rect x="{x-3:.1f}" y="{PYt}" width="6" height="{PYb-PYt}" fill="{fill}" opacity="{op}"/>'
            f'<text x="{x:.0f}" y="{ly}" text-anchor="middle" class="kyr" '
            f'fill="{"#9aa7b0" if avant else "#546e7a"}">{nom.split("-")[0]}</text>')
    pts = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in s.items())
    curve = f'<polyline points="{pts}" fill="none" stroke="#37474f" stroke-width="1.3"/>'
    xt, yt2 = X(today), Y(z_today)
    ct = COL[couleur(z_today, seuils)]
    start_mk = (f'<line x1="{xs:.1f}" y1="{PYt}" x2="{xs:.1f}" y2="{PYb}" stroke="#8d6e63" '
                f'stroke-width="1" stroke-dasharray="2 2"/>')
    today_mk = (f'<circle cx="{xt:.1f}" cy="{yt2:.1f}" r="4.5" fill="{ct}" stroke="#fff" stroke-width="1.5"/>'
                f'<text x="{xt:.0f}" y="{max(PYt+9, yt2-8):.0f}" text-anchor="end" class="tdy">aujourd\'hui</text>')
    svg = (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
           f'aria-label="Historique du signal">'
           f'{bands}{grey}{"".join(kr)}{curve}{start_mk}{today_mk}</svg>')
    an = start.year
    lg = ('<div class="clg">Fond '
          f'<b style="background:{COL_BG["vert"]}"></b> normal '
          f'<b style="background:{COL_BG["orange"]}"></b> élevé '
          f'<b style="background:{COL_BG["rouge"]}"></b> extrême · '
          'bandes grises = les 7 krachs · ● = aujourd\'hui'
          + (' · zone hachurée = avant les premières données' if has_grey else '')
          + f'. Série disponible depuis {an}.</div>')
    return f'<div class="chart-wrap">{svg}</div>{lg}'


def gauge_svg(frac_r: pd.Series, frac_med: float, frac_today: float) -> str:
    """Jauge « où en est-on vs la veille des krachs » — part des signaux au rouge.
    Triangle = aujourd'hui ; points = chaque krach à T-12 ; trait rouge = médiane
    pré-krach (libellé AU-DESSUS pour ne pas télescoper les krachs). Labels de
    krachs répartis sur autant de rangées que nécessaire, avec traits de rappel."""
    W, H = 660, 185
    x0, x1, yt = 44, 600, 86

    def X(p):
        return x0 + p / 100 * (x1 - x0)

    labels = []
    row_last_right = {}
    for name, val in sorted(frac_r.items(), key=lambda kv: kv[1]):
        x = X(val * 100)
        txt = f"{name} · {val * 100:.0f}%"
        half = len(txt) * 3.7 + 7
        row = 0
        while row_last_right.get(row, -999) > x - half:
            row += 1
        row_last_right[row] = x + half
        ly = yt + 22 + row * 16
        labels.append(
            f'<line x1="{x:.0f}" y1="{yt+6}" x2="{x:.0f}" y2="{ly-9:.0f}" '
            f'stroke="#b0a89a" stroke-width="1"/>'
            f'<circle cx="{x:.0f}" cy="{yt}" r="4.5" fill="#8d6e63"/>'
            f'<text x="{x:.0f}" y="{ly:.0f}" text-anchor="middle" class="gk">{txt}</text>')
    xt, xmed = X(frac_today * 100), X(frac_med * 100)
    return (
        f'<svg viewBox="0 0 {W} {H}" class="gaugeA" role="img" '
        f'aria-label="Position actuelle par rapport a la veille des krachs passes">'
        f'<defs><linearGradient id="gg" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="#c8e6c9"/><stop offset="0.5" stop-color="#ffe0b2"/>'
        f'<stop offset="1" stop-color="#ffcdd2"/></linearGradient></defs>'
        f'<rect x="{x0}" y="{yt-7}" width="{x1-x0}" height="14" rx="7" fill="url(#gg)"/>'
        f'<text x="{x0}" y="{yt-44}" class="gz">calme</text>'
        f'<text x="{x1}" y="{yt-44}" text-anchor="end" class="gz">configuration d\'avant-krach</text>'
        f'<line x1="{xmed:.0f}" y1="{yt-30:.0f}" x2="{xmed:.0f}" y2="{yt+8}" stroke="#c62828" '
        f'stroke-width="1.5" stroke-dasharray="4 3"/>'
        f'<text x="{xmed:.0f}" y="{yt-34:.0f}" text-anchor="middle" class="gmed">'
        f'médiane pré-krach {frac_med:.0%}</text>'
        f'<polygon points="{xt:.0f},{yt-9} {xt-7:.0f},{yt-22} {xt+7:.0f},{yt-22}" fill="#111"/>'
        f'<text x="{xt:.0f}" y="{yt-27:.0f}" text-anchor="middle" class="gtoday">'
        f'Aujourd\'hui&#160;{frac_today:.0%}</text>'
        f'{"".join(labels)}</svg>')


def badges(sign: dict, c: str) -> str:
    b = []
    if sign.get("qualitatif"):
        b.append('<span class="badge badge-q">⚠ qualitatif — jugement, non mesuré</span>')
    elif sign.get("approximatif"):
        b.append('<span class="badge">≈ proxy approximatif</span>')
    et = sign.get("etage")
    b.append(f'<span class="badge badge-e">étage {et}</span>' if et
             else '<span class="badge badge-g">hors étage — sans données</span>')
    if c == "gris":
        b.append('<span class="badge badge-g">gris — hors en-tête</span>')
    if sign.get("indicatif"):
        b.append('<span class="badge badge-g">indicatif — couverture faible, poids plafonné 1.0×</span>')
    if sign.get("bruite"):
        b.append('<span class="badge">bruité — NSR ≥ 1, sous-pondéré</span>')
    if sign.get("plafonne"):
        b.append('<span class="badge badge-g">plafonné</span>')
    return " ".join(b)


def main() -> int:
    cfg = load_config()
    seuils = cfg["normalisation"]["seuils"]
    krachs = [(k["nom"], pd.Timestamp(k["date"])) for k in cfg["krachs"]]

    jf = OUT / "journal.csv"
    if not jf.exists():
        print("journal.csv absent — lancer d'abord monitor.py", file=sys.stderr)
        return 1
    j = pd.read_csv(jf)
    r = j.iloc[-1]

    fp = pd.read_csv(OUT / "footprint_signes.csv", index_col=0)
    fpxf = OUT / "faux_positifs_signes.csv"
    fpx = pd.read_csv(fpxf, index_col=0) if fpxf.exists() else None
    # tâche 6b : série z historique par indicateur (LECTURE seule pour les graphes)
    hsf = DATA / "history" / "sign_scores.csv"
    hist = (pd.read_csv(hsf, index_col=0, parse_dates=True) if hsf.exists()
            else pd.DataFrame())

    noms = {s["key"]: s["nom"] for s in cfg["signes"]}
    numero = {s["key"]: s["numero"] for s in cfg["signes"]}

    # ------------------------------------------------------- en-tête (pire signe)
    pire_k = str(r.get("pire_signe", "") or "")
    zp = _f(r.get("z_pire"))
    zm = _f(r.get("moyenne_indicative", r.get("composite")))
    n_o = int(_f(r.get("n_orange"))) if r.get("n_orange") == r.get("n_orange") else 0
    n_r = int(_f(r.get("n_rouge"))) if r.get("n_rouge") == r.get("n_rouge") else 0

    # ---- fractions de signaux au rouge/orange à T-12 de chaque krach + aujourd'hui.
    # Bloc de calcul INCHANGÉ : la jauge et le niveau de synthèse sont pilotés par
    # CES nombres, aucun nouveau calcul.
    poids = {s["key"]: float(s["poids"]) for s in cfg["signes"]}
    sign_keys = [s["key"] for s in cfg["signes"]]
    ag_k = agreger_signes(fp.T.apply(pd.to_numeric, errors="coerce"), poids, seuils)
    fp_signes = fp.loc[[i for i in fp.index if i in sign_keys]].apply(
        pd.to_numeric, errors="coerce")
    mes_k = fp_signes.notna().sum(axis=0)
    frac_r = (ag_k["n_rouge"] / mes_k).dropna()
    frac_o = (ag_k["n_orange"] / mes_k).dropna()
    mes_now = sum(1 for k in sign_keys
                  if str(r.get(f"couleur_{k}", "")) in ("vert", "orange", "rouge"))
    frac_med = float(frac_r.median())
    frac_o_med = float(frac_o.median())
    frac_today = n_r / mes_now if mes_now else float("nan")

    # ---- niveau de synthèse (règle d'AFFICHAGE, depuis ces fractions)
    if frac_today == frac_today and frac_today >= frac_med:
        niveau, ncol = "ALERTE", "rouge"
    elif n_r == 0 and (n_o / mes_now if mes_now else 1) < frac_o_med:
        niveau, ncol = "CALME", "vert"
    else:
        niveau, ncol = "VIGILANCE", "orange"

    n_kr = len(fp.columns)
    if niveau == "ALERTE":
        phrase = (f"Plusieurs signaux de fragilité sont au rouge en même temps : "
                  f"{n_r} sur {mes_now} aujourd'hui, un niveau comparable à la médiane "
                  f"de {frac_med:.0%} observée à la veille des {n_kr} grands krachs depuis "
                  f"1929. Configuration à surveiller de près.")
    elif niveau == "CALME":
        phrase = (f"Aucun signal de fragilité généralisée pour l'instant : {n_r} signal "
                  f"sur {mes_now} au rouge aujourd'hui, très en dessous des {frac_med:.0%} "
                  f"observés en médiane à la veille des {n_kr} grands krachs depuis 1929.")
    else:
        phrase = (f"Le marché est historiquement cher, mais la fragilité généralisée qui "
                  f"précède les krachs n'est pas là : {n_r} signal sur {mes_now} est au "
                  f"rouge aujourd'hui, contre {frac_med:.0%} en médiane à la veille des "
                  f"{n_kr} grands krachs depuis 1929. Vigilance, pas alerte.")

    # ---- signaux du jour, triés par z décroissant ; gris à part
    entries = []
    for sign in cfg["signes"]:
        k = sign["key"]
        z = _f(r.get(f"z_{k}"))
        c = str(r.get(f"couleur_{k}") or couleur(z, seuils))
        d = r.get(f"date_{k}")
        d = str(d) if d == d and d else "—"
        entries.append({"sign": sign, "k": k, "z": z, "c": c, "d": d})
    mesures = [e for e in entries if e["c"] != "gris"]
    gris = [e for e in entries if e["c"] == "gris"]
    mesures.sort(key=lambda e: (-(e["z"] if e["z"] == e["z"] else -9),
                                -float(e["sign"]["poids"])))

    surface_cards = "".join(
        f'<div class="sig" style="border-left:5px solid {COL[e["c"]]};background:{COL_BG[e["c"]]}">'
        f'<div class="sig-h"><span class="dot" style="background:{COL[e["c"]]}"></span>'
        f'<span class="sig-t">{TITRE[e["k"]]}</span>'
        f'<span class="sig-e" style="color:{COL[e["c"]]}">{mot_echelle(e["z"])}</span></div>'
        f'{bar(e["z"], e["c"])}</div>'
        for e in mesures)
    gris_items = "".join(
        f'<li><span class="dot" style="background:{COL["gris"]}"></span>{TITRE[e["k"]]}'
        + ('<span class="qbadge">jugement humain, non mesuré</span>'
           if e["sign"].get("qualitatif") else '<span class="qbadge">pas de donnée à jour</span>')
        + '</li>' for e in gris)

    # ---- DÉTAIL : fiches techniques (chiffres AU-DESSUS + graphique 6b en dessous)
    tech = []
    for e in sorted(entries, key=lambda e: (e["z"] != e["z"],
                                            -(e["z"] if e["z"] == e["z"] else 0.0),
                                            -float(e["sign"]["poids"]))):
        sign, k, z, c, d = e["sign"], e["k"], e["z"], e["c"], e["d"]
        mets = "".join(
            f'<li>{m["description"]}'
            + (' <span class="badge">≈</span>' if m.get("approximatif") else "")
            + (' <em>(optionnelle)</em>' if m.get("optional") else "") + "</li>"
            for m in sign["metrics"])
        ztxt = f"z={z:+.2f}" if z == z else "z indisponible"
        fptxt = ""
        if fpx is not None and k in fpx.index:
            n_a, n_faux = int(fpx.loc[k, "n_alertes"]), int(fpx.loc[k, "n_faux"])
            depuis = pd.Timestamp(fpx.loc[k, "debut"]).year
            if n_a:
                tx = float(fpx.loc[k, "taux_faux"])
                fptxt = (f' · faux positifs : <b>{tx:.0%}</b>'
                         f' ({n_faux}/{n_a} mois ≥ orange depuis {depuis})')
            else:
                fptxt = f' · faux positifs : aucun mois ≥ orange depuis {depuis}'
        # graphique d'historique (tâche 6b) : seulement pour les signaux mesurés
        chart = chart_svg(hist[k], seuils, krachs) if (len(hist) and k in hist.columns) else ""
        tech.append(
            f'<div class="tcard" style="border-left:6px solid {COL.get(c, COL["gris"])}">'
            f'<h4>n°{numero[k]} — {noms[k]} — <span class="gp">« {TITRE[k]} »</span> '
            f'{badges(sign, c)}</h4>'
            f'<div class="meta">{c} · {ztxt} · données {d}{fptxt}</div>'
            f'{bar(z, c)}'
            f'{chart}'
            f'<details><summary>métriques (poids crédibilité {sign["poids"]})</summary>'
            f'<ul>{mets}</ul></details></div>')

    # ---- DÉTAIL : matrice d'empreinte (signes × krachs + colonne aujourd'hui)
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
        body.append(f"<tr><td class='rowh'>{row_labels.get(idx, idx)}</td>"
                    f"{''.join(cells)}{tcell}</tr>")

    # ---- DÉTAIL : compteur de faux positifs live (couleur d'en-tête) — relégué bas
    ce = j["couleur_entete"] if "couleur_entete" in j.columns else pd.Series(dtype=str)
    ce = ce.reindex(j.index)
    if "couleur_composite" in j.columns:
        ce = ce.fillna(j["couleur_composite"])
    n_rouge_hist = int((ce == "rouge").sum())
    n_jours = len(j)

    couv = _f(r.get("couverture"))

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vigilance pré-krach — marchés US</title>
<style>
 :root{{--vert:#2e7d32;--orange:#ef6c00;--rouge:#c62828;--cream:#f7f3ec;--ink:#2b2b2b}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--cream);color:var(--ink);
   font-family:-apple-system,Segoe UI,system-ui,sans-serif;line-height:1.5}}
 .wrap{{max-width:640px;margin:0 auto;padding:20px 16px 48px}}
 h1{{font-family:Georgia,"Times New Roman",serif;font-size:1.35em;margin:0}}
 .sub{{color:#8a8378;font-size:.8em;margin:2px 0 18px}}
 .light{{display:flex;align-items:center;gap:14px;background:#fff;border-radius:14px;
   padding:16px 18px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .lamps{{display:flex;flex-direction:column;gap:6px;background:#263238;
   padding:8px;border-radius:20px}}
 .lamp{{width:20px;height:20px;border-radius:50%;background:#455a64;opacity:.25}}
 .lamp.on{{opacity:1;box-shadow:0 0 10px 1px currentColor}}
 .lv{{color:var(--vert)}} .lo{{color:var(--orange)}} .lr{{color:var(--rouge)}}
 .lamp.on.lv{{background:var(--vert)}} .lamp.on.lo{{background:var(--orange)}}
 .lamp.on.lr{{background:var(--rouge)}}
 .light .lbl{{font-size:.72em;color:#8a8378;text-transform:uppercase;letter-spacing:.04em}}
 .light .niv{{font-size:1.5em;font-weight:800}}
 .synth{{font-family:Georgia,serif;font-size:1.12em;line-height:1.55;margin:16px 2px}}
 .alarm{{background:#fdecea;border:1px solid #f3b8b0;border-left:6px solid var(--rouge);
   border-radius:10px;padding:12px 15px;margin:14px 0}}
 .alarm .k{{font-size:.72em;text-transform:uppercase;letter-spacing:.04em;color:var(--rouge);font-weight:700}}
 .alarm .v{{font-size:1.04em;margin-top:3px}}
 .legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:.8em;color:#5c554a;margin:14px 2px}}
 .legend b{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:middle}}
 .mission{{background:#fff;border:1px dashed #cbb;border-radius:10px;padding:12px 15px;
   font-size:.9em;color:#5c554a;margin:14px 0}}
 .mission b{{color:var(--ink)}}
 .panel{{background:#fff;border-radius:12px;padding:16px 16px 8px;margin:18px 0;
   box-shadow:0 1px 4px rgba(0,0,0,.07)}}
 .panel h2{{font-size:1.02em;margin:0 0 10px}}
 .gaugeA{{width:100%;height:auto}}
 .gz{{font-size:11px;fill:#8a8378}} .gk{{font-size:11px;fill:#5c554a}}
 .gmed{{font-size:11px;fill:#c62828}} .gtoday{{font-size:12px;fill:#111;font-weight:700}}
 .sig{{border-radius:9px;padding:9px 12px;margin:8px 0}}
 .sig-h{{display:flex;align-items:center;gap:9px}}
 .dot{{width:11px;height:11px;border-radius:50%;flex:0 0 auto}}
 .sig-t{{flex:1;font-size:.95em}}
 .sig-e{{font-size:.78em;font-weight:700;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap}}
 .bar{{position:relative;background:#e9e3d8;height:9px;border-radius:5px;overflow:hidden;margin-top:7px}}
 .bar .fill{{height:100%;border-radius:5px}}
 .na{{color:#9e9e9e;font-style:italic;font-size:.8em;padding-left:4px}}
 ul.gris{{list-style:none;padding:0;margin:6px 0 0}}
 ul.gris li{{display:flex;align-items:center;gap:9px;font-size:.9em;color:#6b6459;padding:5px 0}}
 .qbadge{{font-size:.72em;color:#8a8378;background:#eceff1;border-radius:8px;padding:1px 7px;margin-left:auto}}
 details.method>summary{{cursor:pointer;background:#2b2b2b;color:#fff;border-radius:10px;
   padding:12px 16px;font-weight:600;list-style:none;margin-top:8px}}
 details.method>summary::-webkit-details-marker{{display:none}}
 details.method>summary::before{{content:"\\25b8  "}}
 details.method[open]>summary::before{{content:"\\25be  "}}
 .detail{{padding:6px 2px}}
 .tcard{{background:#fff;border-radius:8px;padding:10px 14px;margin:9px 0;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
 .tcard h4{{margin:2px 0 6px;font-size:.95em}} .tcard .gp{{color:#5c554a;font-weight:500}}
 .meta{{color:#8a8378;font-size:.8em;margin-bottom:5px}}
 .badge{{background:#fff3e0;color:#e65100;border:1px solid #ffb74d;border-radius:10px;font-size:.68em;padding:1px 7px}}
 .badge-q{{background:#ede7f6;color:#4527a0;border-color:#b39ddb}}
 .badge-g{{background:#eceff1;color:#546e7a;border-color:#b0bec5}}
 .badge-e{{background:#e3f2fd;color:#1565c0;border-color:#90caf9;font-weight:600}}
 .chart-wrap{{background:#fffdf9;border:1px solid #eee6d8;border-radius:6px;padding:4px;margin-top:8px}}
 .chart{{width:100%;height:auto;display:block}}
 .kyr{{font-size:8px}} .nodata{{font-size:9px;fill:#90a4ae;font-style:italic}}
 .tdy{{font-size:9px;fill:#37474f;font-weight:700}}
 .clg{{font-size:.74em;color:#6b6459;margin:5px 2px 0}}
 .clg b{{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin:0 1px}}
 table{{border-collapse:collapse;width:100%;background:#fff;font-size:.82em;margin-top:6px}}
 th,td{{border:1px solid #e6e0d6;padding:4px 6px;text-align:center}}
 .rowh{{text-align:left;font-weight:600}} .today{{background:#fff9e6;font-weight:700}}
 .warn{{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:12px 15px;font-size:.85em;margin-top:14px}}
 .transp{{font-size:.8em;color:#8a8378;margin-top:14px;padding-top:10px;border-top:1px solid #e6e0d6}}
 details summary{{cursor:pointer}}
 footer{{color:#a49c8f;font-size:.75em;margin-top:26px}}
</style></head><body><div class="wrap">

<h1>Vigilance pré-krach — marchés US</h1>
<div class="sub">Données au {r['date_donnees']} · mis à jour le {r['date_execution']}</div>

<div class="light">
  <div class="lamps">
    <span class="lamp lr {'on' if ncol == 'rouge' else ''}"></span>
    <span class="lamp lo {'on' if ncol == 'orange' else ''}"></span>
    <span class="lamp lv {'on' if ncol == 'vert' else ''}"></span>
  </div>
  <div>
    <div class="lbl">Niveau de vigilance d'ensemble</div>
    <div class="niv" style="color:{COL[ncol]}">{niveau}</div>
  </div>
</div>

<p class="synth">{phrase}</p>

<div class="alarm">
  <div class="k">Signal le plus alarmant</div>
  <div class="v">les actions sont très chères par rapport aux profits des entreprises —
  niveau {mot_echelle(zp)}, vu seulement une poignée de fois depuis 1900.</div>
</div>

<div class="legend">
  <span><b style="background:{COL['vert']}"></b>vert : normal, rien d'inhabituel</span>
  <span><b style="background:{COL['orange']}"></b>orange : élevé, à surveiller</span>
  <span><b style="background:{COL['rouge']}"></b>rouge : extrême, rarement vu</span>
</div>

<div class="mission">
  Cet outil <b>mesure si le terrain est inflammable, pas s'il va prendre feu demain.</b>
  Ce n'est pas un conseil d'achat ou de vente.
</div>

<div class="panel">
  <h2>Où en est-on par rapport à la veille des krachs passés ?</h2>
  {gauge_svg(frac_r, frac_med, frac_today)}
  <div class="legend" style="margin-top:2px">
    <span>Chaque point = un krach, mesuré 12 mois avant. Le triangle = aujourd'hui.
    Plus on est à droite, plus la configuration ressemble à une veille de krach.</span>
  </div>
</div>

<h2 style="font-size:1.05em;margin:22px 2px 6px">Les {mes_now} signaux mesurés aujourd'hui</h2>
{surface_cards}
<div style="font-size:.82em;color:#8a8378;margin:12px 2px 4px">Non mesurés aujourd'hui :</div>
<ul class="gris">{gris_items}</ul>

<details class="method"><summary>Voir le détail / la méthode</summary>
<div class="detail">

<h3 style="font-size:.98em">Fiche technique de chaque signal (chiffres + graphique d'historique)</h3>
<div class="legend"><span>Sous les chiffres, un graphique montre l'évolution du signal dans le temps :
fond vert/orange/rouge aux mêmes seuils que les couleurs, krachs ombrés, position d'aujourd'hui.
« poids crédibilité » = re-pondération NSR ; « étage A/B/C » = profondeur d'historique
(A = backtestable jusqu'à 1929) ; « indicatif / bruité / plafonné » = drapeaux de fiabilité.
Taux de faux positifs = part des mois ≥ orange non suivis d'un krach sous 24 mois.</span></div>
{''.join(tech)}

<h3 style="font-size:.98em;margin-top:18px">Empreinte des krachs (z par signal à T−12 mois)</h3>
<table><tr><th></th>{head}<th>Aujourd'hui</th></tr>{''.join(body)}</table>
<div class="legend"><span>« – » : série trop récente pour couvrir ce krach (la plupart des
séries publiques démarrent après 1945, voire 1990). « Socle A+B » = signaux à long historique
(9 signaux post-1945) ; « socle A seul » = les 2 signaux qui remontent à 1929. « Moyenne
indicative » (pondérée crédibilité, ex-« composite ») dilue les extrêmes et ne pilote plus le
feu : z = {zm:+.2f} ({couleur(zm, seuils)}). Couverture pondérée du jour {couv:.0%}.</span></div>

<div class="warn"><b>Notes d'honnêteté (à ne jamais retirer)</b><br>
· Instrument d'analyse et de pédagogie — <b>pas</b> un signal de trading, aucune prétention sur le <i>timing</i>.<br>
· Le feu résume TOUS les signaux ; il est orange tant que la <i>configuration d'ensemble</i>
n'est pas celle d'une veille de krach — même si un signal isolé est au rouge (encart en haut de page).
L'en-tête « pire signe » est volontairement plus sensible : plus d'alertes = plus de faux positifs, c'est le prix de la non-dilution.<br>
· Signaux « ≈ » (proxy, ex. n°2) et « ⚠ qualitatif » (ex. n°7 déréglementation) : proxies imparfaits
ou jugement humain, jamais des mesures dures — gris et hors feu tant qu'aucune évaluation n'est fournie.<br>
· Calibration sur les seuls krachs survenus → biais de survie ; le vrai taux de faux positifs est inconnu et probablement élevé.<br>
· Le déclencheur (signe 16) est par nature non mesurable : l'outil suit la fragilité accumulée, pas l'étincelle.</div>

<div class="transp">Transparence — fausses alertes : depuis le lancement de l'outil ({n_jours} relevé(s)),
le signal le plus sensible (le « pire signal ») est passé au rouge {n_rouge_hist} jour(s) au total,
sans qu'aucun krach ait suivi à ce jour. Ce décompte d'honnêteté grossit dès qu'un seul indicateur
s'allume : il ne veut pas dire que le marché est en danger.</div>

</div></details>

<footer>Généré par dashboard.py — sources : FRED (St. Louis Fed), BIS, Fed Z.1/SLOOS, Shiller, AAII, CBOE, FINRA.</footer>
</div></body></html>"""

    OUT.mkdir(exist_ok=True)
    (OUT / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"OK → {OUT / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
