# -*- coding: utf-8 -*-
"""Fonctions partagées : config, clé API, accès données, transformations, z-scores.

Principe non négociable (§7 du brief) : la MÊME méthode de normalisation est
appliquée à l'historique (calibrate.py) et au présent (monitor.py). Les deux
passent par compute_panel() — un seul chemin de code.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
FIXTURES = DATA / "fixtures"
MANUAL = DATA / "manual"
OUT = ROOT / "output"

UA = {"User-Agent": "Mozilla/5.0 (outil-vigilance-pre-krach; usage personnel)"}


# ---------------------------------------------------------------- config / clé
def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env() -> None:
    """Charge le fichier .env (jamais commité) dans os.environ."""
    envf = ROOT / ".env"
    if not envf.exists():
        return
    for line in envf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def fred_key() -> str | None:
    load_env()
    return os.environ.get("FRED_API_KEY") or None


# ---------------------------------------------------------------------- réseau
def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


# ------------------------------------------------------------------ FRED
def fetch_fred(series_id: str, api_key: str | None = None) -> pd.Series:
    """Série FRED. Avec clé → API officielle ; sans clé → CSV public fredgraph."""
    if api_key:
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}&file_type=json"
            "&observation_start=1900-01-01"
        )
        payload = json.loads(http_get(url).decode("utf-8"))
        if "observations" not in payload:
            raise RuntimeError(f"FRED API: réponse inattendue pour {series_id}: {payload}")
        rows = [(o["date"], o["value"]) for o in payload["observations"]]
    else:
        text = http_get(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        ).decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(text))
        if df.shape[1] < 2:
            raise RuntimeError(f"fredgraph: format inattendu pour {series_id}")
        rows = list(zip(df.iloc[:, 0], df.iloc[:, 1]))
    s = pd.Series({d: v for d, v in rows})
    s.index = pd.to_datetime(s.index)
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    s.name = series_id
    if s.empty:
        raise RuntimeError(f"Série vide : {series_id}")
    return s


# ------------------------------------------------------- sources non-FRED
def _read_series_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    s = pd.Series(df.iloc[:, 1].values, index=pd.to_datetime(df.iloc[:, 0]))
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def _manual_or_fail(name: str, hint: str) -> pd.Series:
    f = MANUAL / f"{name}.csv"
    if f.exists():
        return _read_series_csv(f)
    raise RuntimeError(f"{name}: pas de collecte automatique fiable. {hint}")


def _parse_ie_data(raw: bytes) -> pd.Series:
    """Parse le fichier officiel de Robert Shiller (ie_data.xls, feuille 'Data').

    Dates au format décimal AAAA.MM où '.1' = octobre et '.01' = janvier →
    on lit la colonne Date en TEXTE pour ne pas perdre le zéro final.
    """
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data", header=None, dtype=str)
    hdr_row = cape_col = None
    for i in range(min(15, len(df))):
        for jcol, cell in enumerate(df.iloc[i]):
            c = str(cell).strip().upper()
            if c == "CAPE" or "P/E10" in c:
                hdr_row, cape_col = i, jcol
                break
        if hdr_row is not None:
            break
    if hdr_row is None:
        raise RuntimeError("ie_data.xls: colonne CAPE introuvable (format modifié ?)")

    out = {}
    for _, row in df.iloc[hdr_row + 1:].iterrows():
        d, v = str(row.iloc[0]).strip(), row.iloc[cape_col]
        m = re.match(r"^(\d{4})\.(\d{1,2})", d)
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if not m or val != val:
            continue
        year, frac = int(m.group(1)), m.group(2)
        month = int(frac) if len(frac) == 2 else int(frac) * 10  # '.1' = octobre
        if 1 <= month <= 12:
            out[pd.Timestamp(year=year, month=month, day=1)] = val
    if len(out) < 100:
        raise RuntimeError(f"ie_data.xls: seulement {len(out)} valeurs CAPE lues")
    s = pd.Series(out).sort_index()
    s.name = "shiller_cape"
    return s


def _shillerdata_url() -> str:
    """Resout le lien de telechargement courant d'ie_data.xls sur
    shillerdata.com (site OFFICIEL et MAINTENU ; l'URL du blob change a
    chaque mise a jour). Le site est un builder GoDaddy : selon le rendu,
    les '/' des URLs sont echappes en JSON (barre inverse + '/') ou encodes
    en unicode (u002F) -> on desechappe le HTML avant de chercher.
    En cas d'echec, la page recue est sauvee dans data/cache/ pour diagnostic."""
    html = http_get("https://shillerdata.com", timeout=60).decode("utf-8", errors="replace")
    for esc, rep in (("\\/", "/"), ("\\u002F", "/"), ("\\u002f", "/"),
                     ("\\u0026", "&"), ("&amp;", "&")):
        html = html.replace(esc, rep)
    m = re.search(
        r'(?:https?:)?//[a-z0-9.]*wsimg\.com/[^"\'()\s<>]*ie_data[^"\'()\s<>]*',
        html, re.IGNORECASE,
    )
    if not m:
        CACHE.mkdir(parents=True, exist_ok=True)
        dump = CACHE / "shillerdata_page.html"
        dump.write_text(html, encoding="utf-8")
        raise RuntimeError(
            "shillerdata.com: lien ie_data.xls introuvable dans la page "
            f"(page recue sauvee dans {dump} pour diagnostic)"
        )
    url = m.group(0).split("\\")[0]
    if url.startswith("//"):
        url = "https:" + url
    return url


def fetch_shiller_cape() -> pd.Series:
    """CAPE Shiller. Ordre : 1) fichier manuel ; 2) URL forcée SHILLER_XLS_URL
    (.env) ; 3) shillerdata.com (officiel, maintenu) ; 4) miroir Yale (long
    mais figé fin 2023) ; 5) multpl.com. Une source n'est acceptée sans
    avertissement que si son dernier point a moins de 6 mois."""
    f = MANUAL / "shiller_cape.csv"
    if f.exists():
        return _read_series_csv(f)

    load_env()
    fresh_limit = pd.Timestamp.now() - pd.DateOffset(months=6)
    tried, stale = [], None

    candidates = []
    if os.environ.get("SHILLER_XLS_URL"):
        candidates.append(("SHILLER_XLS_URL (.env)",
                           lambda: os.environ["SHILLER_XLS_URL"]))
    candidates += [
        ("shillerdata.com", _shillerdata_url),
        ("miroir Yale http", lambda: "http://www.econ.yale.edu/~shiller/data/ie_data.xls"),
        ("miroir Yale https", lambda: "https://www.econ.yale.edu/~shiller/data/ie_data.xls"),
    ]
    for label, get_url in candidates:
        try:
            s = _parse_ie_data(http_get(get_url(), timeout=90))
            if s.index[-1] >= fresh_limit:
                print(f"  (CAPE via {label}, dernier point {s.index[-1]:%Y-%m})")
                return s
            tried.append(f"{label}: donnees figees a {s.index[-1]:%Y-%m}")
            if stale is None or s.index[-1] > stale.index[-1]:
                stale = s
        except Exception as e:
            tried.append(f"{label}: {e}")

    try:
        html = http_get("https://www.multpl.com/shiller-pe/table/by-month").decode(
            "utf-8", errors="replace"
        )
        rows = re.findall(
            r"<td[^>]*>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td[^>]*>\s*([\d.,]+)",
            html,
        )
        if not rows:
            raise RuntimeError("table CAPE introuvable (format modifie ?)")
        s = pd.Series(
            {pd.to_datetime(d): float(v.replace(",", "")) for d, v in rows}
        ).sort_index()
        s.name = "shiller_cape"
        if s.index[-1] >= fresh_limit:
            print(f"  (CAPE via multpl.com, dernier point {s.index[-1]:%Y-%m})")
            return s
        tried.append(f"multpl.com: donnees figees a {s.index[-1]:%Y-%m}")
        if stale is None or s.index[-1] > stale.index[-1]:
            stale = s
    except Exception as e:
        tried.append(f"multpl.com: {e}")

    if stale is not None:
        print("  !! CAPE: AUCUNE source fraiche. Utilisation de donnees FIGEES a "
              f"{stale.index[-1]:%Y-%m}. Details :", file=sys.stderr)
        for t in tried:
            print(f"     - {t}", file=sys.stderr)
        print("     Contournement : recuperer le lien 'ie_data (xls)' sur "
              "https://shillerdata.com et le coller dans .env sous "
              "SHILLER_XLS_URL=<url>", file=sys.stderr)
        return stale
    raise RuntimeError("CAPE indisponible - " + " | ".join(tried))


def fetch_aaii() -> pd.Series:
    """Écart haussiers − baissiers AAII (hebdo). Le .xls public exige souvent une
    session navigateur → fallback fichier manuel data/manual/aaii.csv (date,value)."""
    try:
        raw = http_get("https://www.aaii.com/files/surveys/sentiment.xls")
        df = pd.read_excel(io.BytesIO(raw))
        cols = {c.strip().lower(): c for c in df.columns if isinstance(c, str)}
        d, b, be = cols.get("date"), cols.get("bullish"), cols.get("bearish")
        if not (d and b and be):
            raise RuntimeError("colonnes AAII inattendues")
        s = pd.Series(
            (pd.to_numeric(df[b], errors="coerce") - pd.to_numeric(df[be], errors="coerce")).values * 100,
            index=pd.to_datetime(df[d], errors="coerce"),
        ).dropna().sort_index()
        if s.empty:
            raise RuntimeError("AAII vide")
        return s
    except Exception:
        return _manual_or_fail(
            "aaii",
            "Déposer data/manual/aaii.csv (colonnes: date,value = bull% - bear%).",
        )


def fetch_putcall() -> pd.Series:
    return _manual_or_fail(
        "putcall",
        "Déposer data/manual/putcall.csv (colonnes: date,value) — "
        "source CBOE, pas d'endpoint public stable.",
    )


def fetch_margin_debt() -> pd.Series:
    return _manual_or_fail(
        "margin_debt",
        "Déposer data/manual/margin_debt.csv (colonnes: date,value en M$) — "
        "source https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics",
    )


# ------------------------------------------------------------ cache / offline
def get_series(name: str, source: str, offline: bool = False) -> pd.Series:
    """Récupère une série brute avec cache CSV. `name` = ID FRED ou nom logique.

    offline=True → lit data/fixtures/{name}.csv (données SYNTHÉTIQUES de test).
    """
    if offline:
        f = FIXTURES / f"{name}.csv"
        if not f.exists():
            raise RuntimeError(f"Fixture absente : {f}")
        return _read_series_csv(f)

    cachef = CACHE / f"{name}.csv"
    try:
        if source == "fred":
            s = fetch_fred(name, fred_key())
        elif source == "shiller":
            s = fetch_shiller_cape()
        elif source == "aaii":
            s = fetch_aaii()
        elif source == "cboe":
            s = fetch_putcall()
        elif source == "finra":
            s = fetch_margin_debt()
        else:
            raise RuntimeError(f"Source inconnue : {source}")
        CACHE.mkdir(parents=True, exist_ok=True)
        s.rename("value").to_csv(cachef, index_label="date")
        return s
    except Exception as e:
        if cachef.exists():
            print(f"  ! {name}: échec de collecte ({e}) → cache utilisé", file=sys.stderr)
            return _read_series_csv(cachef)
        raise


# ------------------------------------------------------------- transformations
def to_monthly(s: pd.Series) -> pd.Series:
    """Ramène toute série au pas mensuel (début de mois).
    Fréquence fine (quotidien/hebdo) → moyenne mensuelle ; sinon dernière valeur.
    Les séries trimestrielles sont propagées (ffill) au plus 5 mois."""
    s = s.sort_index()
    per_month = s.groupby(s.index.to_period("M")).size().median()
    m = s.resample("MS").mean() if per_month >= 3 else s.resample("MS").last()
    return m.ffill(limit=5)


def hp_trend(y: np.ndarray, lam: float) -> np.ndarray:
    n = len(y)
    if n < 8:
        return y.copy()
    d = np.zeros((n - 2, n))
    for i in range(n - 2):
        d[i, i], d[i, i + 1], d[i, i + 2] = 1.0, -2.0, 1.0
    return np.linalg.solve(np.eye(n) + lam * (d.T @ d), y)


def one_sided_hp_gap(s: pd.Series, lam: float = 400_000, min_obs: int = 40) -> pd.Series:
    """Gap « à la BIS » : écart au trend HP calculé UNIQUEMENT avec l'information
    disponible à chaque date (one-sided, λ=400 000, données trimestrielles)."""
    q = s.resample("QS").last().dropna()
    vals = q.values.astype(float)
    gap = np.full(len(q), np.nan)
    for t in range(min_obs - 1, len(q)):
        gap[t] = vals[t] - hp_trend(vals[: t + 1], lam)[-1]
    return pd.Series(gap, index=q.index).dropna()


def apply_transform(raw: pd.Series, transform: str, gdp: pd.Series | None = None) -> pd.Series:
    if transform == "level":
        return to_monthly(raw)
    if transform == "yoy_pct":
        m = to_monthly(raw)
        return (m.pct_change(12) * 100).dropna()
    if transform == "hp_gap":
        return to_monthly(one_sided_hp_gap(raw))
    if transform == "ratio_gdp":
        if gdp is None:
            raise RuntimeError("ratio_gdp nécessite la série GDP")
        num_q = raw.resample("QS").last()
        gdp_q = gdp.resample("QS").last()
        ratio = (num_q / 1000.0) / gdp_q * 100.0  # M$ → Md$, en % du PIB
        return to_monthly(ratio.dropna())
    raise RuntimeError(f"Transformation inconnue : {transform}")


# ------------------------------------------------------------------- z-scores
def expanding_z(x: pd.Series, min_periods: int) -> pd.Series:
    """Z-score en fenêtre expansive : à chaque date, moyenne/écart-type calculés
    sur la propre histoire de la série jusqu'à cette date (point-in-time)."""
    mu = x.expanding(min_periods=min_periods).mean()
    sd = x.expanding(min_periods=min_periods).std()
    z = (x - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan)


def couleur(z: float, seuils: dict) -> str:
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return "gris"
    if z < seuils["vert"]:
        return "vert"
    if z < seuils["orange"]:
        return "orange"
    return "rouge"


# ------------------------------------------------------------------- le panel
def compute_panel(cfg: dict, offline: bool = False, verbose: bool = True) -> dict:
    """Construit le panel mensuel complet : z par métrique, score par signe,
    composite pondéré crédibilité. Chemin de code UNIQUE calibration/live."""
    norm = cfg["normalisation"]
    default_min = int(norm.get("min_hist_months", 120))

    gdp = None
    metric_z, metric_val, indispo = {}, {}, []

    for sign in cfg["signes"]:
        for m in sign["metrics"]:
            name, src = m["series"], m["source"]
            try:
                raw = get_series(name, src, offline)
                if m.get("subtract_series"):
                    other = get_series(m["subtract_series"], src, offline)
                    raw = (to_monthly(raw) - to_monthly(other)).dropna()
                if m["transform"] == "ratio_gdp" and gdp is None:
                    gdp = get_series("GDP", "fred", offline)
                val = apply_transform(raw, m["transform"], gdp)
                z = expanding_z(val, int(m.get("min_hist_months", default_min)))
                if m["danger"] == "low":
                    z = -z
                metric_z[m["key"]] = z
                metric_val[m["key"]] = val
                if verbose:
                    print(f"  + {m['key']:18s} [{name}] {val.index[0]:%Y-%m} -> {val.index[-1]:%Y-%m}")
            except Exception as e:
                if m.get("optional"):
                    indispo.append((m["key"], str(e)))
                    if verbose:
                        print(f"  - {m['key']}: indisponible ({e})", file=sys.stderr)
                else:
                    raise

    zdf = pd.DataFrame(metric_z).sort_index()
    vdf = pd.DataFrame(metric_val).sort_index()

    sign_scores, weights = {}, {}
    for sign in cfg["signes"]:
        keys = [m["key"] for m in sign["metrics"] if m["key"] in zdf.columns]
        if keys:
            sign_scores[sign["key"]] = zdf[keys].mean(axis=1)
            weights[sign["key"]] = float(sign["poids"])
    sdf = pd.DataFrame(sign_scores)

    w = pd.Series(weights)
    avail = sdf.notna()
    weight_sum = avail.mul(w, axis=1).sum(axis=1)
    composite = sdf.mul(w, axis=1).sum(axis=1, min_count=1) / weight_sum.replace(0, np.nan)
    coverage = weight_sum / w.sum()

    return {
        "metric_z": zdf,
        "metric_val": vdf,
        "sign_scores": sdf,
        "composite": composite,
        "coverage": coverage,
        "weights": weights,
        "indisponibles": indispo,
    }
