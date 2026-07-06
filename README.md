# Outil de vigilance pré-krach — marchés US (MVP 6 signes)

Instrument d'analyse et de pédagogie. **Pas** un générateur de signaux de
trading ; aucune prétention sur le *timing*. Voir `brief_reprise_outil_vigilance.md`.

## Démarrage (local)

```
pip install -r requirements.txt
```

1. **Clé FRED** (gratuite) : la créer sur https://fredaccount.stlouisfed.org/apikeys,
   copier `.env.example` → `.env`, y coller la clé. `.env` est dans `.gitignore`,
   la clé n'est jamais commitée ni écrite dans le code.
2. **Valider les ID de séries** : `python test_fred.py`
   (fonctionne aussi sans clé, via le CSV public FRED — la clé sera obligatoire
   pour la version GitHub Actions).
3. **Calibration historique** : `python calibrate.py`
   → empreinte des 7 krachs (`output/footprint_*.csv`), backtest honnête.
4. **Relevé du jour** : `python monitor.py` → console + `output/journal.csv`.
5. **Dashboard** : `python dashboard.py` → ouvrir `output/dashboard.html`.

Test de plomberie sans réseau : `python tools/make_fixtures.py` puis
`python calibrate.py --offline` / `python monitor.py --offline`
(données synthétiques, résultats non interprétables).

## Sources manuelles optionnelles (`data/manual/`)

| Fichier | Contenu | Source |
|---|---|---|
| `margin_debt.csv` | date,value (M$) | FINRA « Margin Statistics » |
| `aaii.csv` | date,value (bull% − bear%, pts) | AAII Sentiment Survey |
| `putcall.csv` | date,value (ratio put/call actions) | CBOE |
| `shiller_cape.csv` | date,value (CAPE) | ie_data.xls de Shiller (sinon repli multpl.com) |

CAPE : ordre de collecte = fichier manuel → `SHILLER_XLS_URL` (.env) →
shillerdata.com (officiel, maintenu) → miroir Yale (figé fin 2023) → multpl.com.
Si aucune source « fraîche » (< 6 mois) n'est trouvée, un avertissement `!!`
liste les échecs et le contournement (coller l'URL du lien « ie_data (xls) »
de shillerdata.com dans `.env` sous `SHILLER_XLS_URL`).

Absentes → métriques marquées « indisponible », jamais bloquantes.

## Choix méthodologiques clés

- Z-score **expansif point-in-time** (aucun regard vers le futur), même chemin
  de code pour la calibration et le suivi live (`common.compute_panel`).
- Gap crédit/PIB : filtre HP **unilatéral** λ=400 000 (méthode BIS).
- Indicateur Buffett recalculé en `NCBEILQ027S / GDP` — les séries Wilshire
  ont été **retirées de FRED le 3 juin 2024**.
- Composite = moyenne des signes pondérée par la crédibilité des sources,
  renormalisée sur les signes disponibles (couverture affichée).
- Avant ~1990, la couverture est très partielle (seul le CAPE remonte à 1881) :
  l'empreinte des krachs anciens est incomplète par honnêteté, pas par bug.

## Automatisation quotidienne (GitHub Actions — Phase 4)

Le workflow `.github/workflows/daily.yml` tourne chaque jour à 22h30 UTC
(après la clôture US) : calibrate → monitor → dashboard, commit des CSV
horodatés, publication du dashboard sur GitHub Pages.

Mise en route (une fois) :

1. Créer un dépôt GitHub (privé ou public) et pousser ce dossier :
   `git init && git add -A && git commit -m "MVP vigilance pré-krach" &&
   git branch -M main && git remote add origin <url_du_depot> && git push -u origin main`
   (`.env` est ignoré par git — la clé ne part jamais dans le dépôt).
2. Dans le dépôt : Settings → Secrets and variables → Actions →
   « New repository secret » → nom `FRED_API_KEY`, valeur = la clé.
   Optionnel : secret `SHILLER_XLS_URL` (même rôle que dans `.env`).
3. Settings → Pages → Source : **GitHub Actions**.
4. Premier lancement manuel : onglet Actions → « vigilance-quotidienne » →
   « Run workflow ». Le dashboard sera servi à l'URL GitHub Pages du dépôt.

## Étapes suivantes

- Extension aux 16 signes via `config.yaml` — Phase 6 (marquer distinctement
  approximatifs et qualitatifs).
