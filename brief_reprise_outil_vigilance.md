# Brief de reprise — Outil de vigilance pré-krach (marchés US)

> **But de ce document.** Servir de point de départ complet pour la phase de *fabrication* de l'outil (dans Cowork ou Claude Code). Il capture toutes les décisions déjà prises afin qu'aucun contexte ne soit perdu. Il est auto-suffisant : la personne qui reprend n'a pas besoin de l'historique de conversation.

---

## 1. Objectif du projet

Construire un outil analytique qui :
1. traduit 16 « signes précurseurs de krach » (issus d'une revue de la littérature) en indicateurs **quantifiables et publics** ;
2. mesure chacun de ces signes pour les **grands krachs américains depuis 1900** (empreinte historique de référence) ;
3. **suit automatiquement, chaque jour**, l'état actuel des marchés US selon les mêmes indicateurs ;
4. produit un **indice de vigilance** par signe + composite, honnête sur ses limites (compteur de faux positifs).

**Nature de l'outil : instrument d'analyse et de pédagogie. PAS un générateur de signaux de trading. Aucune prétention prédictive sur le *timing*.**

---

## 2. Décisions d'architecture (déjà arrêtées)

| Élément | Choix | Raison |
|---|---|---|
| Langage | **Python** | z-scores sur bases historiques + calcul quotidien |
| Automatisation | **GitHub Actions** (`cron` quotidien) | gratuit, aucun serveur à maintenir, tourne sans intervention |
| Source de données principale | **API FRED** (Fed de Saint-Louis) | gratuite, une clé, milliers de séries US |
| Sources complémentaires | CBOE (VIX, put/call), FINRA (margin debt), fichier CAPE de Shiller, AAII (sentiment) | signes non couverts par FRED |
| Profondeur historique | **Jordà-Schularick-Taylor Macrohistory Database** + données Shiller (CAPE depuis 1871) | pour les krachs d'avant-guerre |
| Stockage | **Fichiers CSV versionnés** dans le dépôt | pas de base de données ; historique horodaté |
| Affichage | **Page HTML statique** régénérée chaque jour, publiée via GitHub Pages | 100 % automatique |
| Périmètre | **États-Unis uniquement** | choix explicite |
| Fréquence | **Quotidienne** | NB : séries macro lentes (mensuelles/trimestrielles) ne bougent qu'à leur publication ; le quotidien rafraîchit surtout les signaux de marché |

---

## 3. Prérequis à la charge de l'utilisateur (~30 min, une seule fois)

1. Créer un **compte GitHub**.
2. Obtenir une **clé API FRED gratuite** (fredaccount.stlouisfed.org → API Keys).
3. Coller cette clé comme **secret GitHub** dans le dépôt (`Settings → Secrets → Actions`), nom suggéré `FRED_API_KEY`. **La clé ne doit jamais être écrite en dur dans le code ni partagée.**

---

## 4. Les 16 signes et leur pondération de crédibilité

Poids issus d'un scoring de crédibilité des sources (0-10) réalisé en amont. `N` = nombre de sources ; `Qual. moy.` = qualité moyenne pondérée du consensus. **Trier l'agrégation composite par ces poids.**

| # | Signe | N | Qual. moy. | Dans le MVP ? |
|---|---|---|---|---|
| 1 | Expansion excessive du crédit / endettement (levier) | 19 | 8,03 | ✅ |
| 2 | Euphorie spéculative / psychologie de foule *(approx.)* | 12 | 7,63 | ✅ |
| 3 | Innovation financière / opacité / relâchement des standards de prêt | 10 | 7,70 | ✅ |
| 4 | Déplacement : narratif « cette fois c'est différent » *(qualitatif)* | 9 | 7,78 | — |
| 5 | Survalorisation / accélération des prix vs fondamentaux | 9 | 7,44 | ✅ |
| 6 | Fragilité structurelle du système financier | 8 | 8,75 | — |
| 7 | Complaisance réglementaire / déréglementation | 7 | 8,43 | — |
| 8 | Déséquilibres globaux / flux de capitaux | 6 | 8,50 | — |
| 9 | Conditions monétaires accommodantes / taux bas | 5 | 7,90 | ✅ |
| 10 | Compression des primes de risque / complaisance | 5 | 7,80 | ✅ |
| 11 | Réflexivité / boucles de rétroaction | 4 | 7,75 | — |
| 12 | Surchauffe des transactions (volumes, IPO, margin) | 4 | 7,63 | — |
| 13 | Dynamique « Ponzi » (refinancement perpétuel) | 4 | 7,50 | — |
| 14 | Détresse / retrait des initiés (smart money) | 4 | 7,50 | — |
| 15 | Montée des inégalités / concentration des richesses | 3 | 8,33 | — |
| 16 | Déclencheur imprévisible / fragilité cachée | 3 | 7,50 | — (non mesurable par nature) |

**Note d'honnêteté à conserver dans l'outil :** signe 16 non mesurable a priori ; signes 2, 4, 11, 14 seulement *approximatifs* (proxies imparfaits) → à marquer visuellement pour ne jamais les confondre avec des mesures dures.

---

## 5. Le MVP — 6 signes câblés de bout en bout (à construire en premier)

| Signe (n°) | Métrique US concrète | Série / source | ID FRED (à vérifier) |
|---|---|---|---|
| Crédit/levier (1) | Credit-to-GDP gap ; dette sur marge | BIS via FRED ; FINRA | *à confirmer* ; margin debt = source FINRA directe |
| Survalorisation (5) | CAPE de Shiller ; capitalisation/PIB (« Buffett ») | Shiller `ie_data.xls` ; Wilshire 5000 ÷ PIB | `WILL5000INDFC`, `GDP` |
| Compression du risque (10) | Spread high yield (OAS) ; VIX | ICE BofA ; CBOE | `BAMLH0A0HYM2`, `VIXCLS` |
| Monétaire (9) | Courbe 10a-3m ; M2 ; taux réel | FRED | `T10Y3M`, `M2SL`, `DFII10` |
| Standards de prêt (3) | Enquête SLOOS (durcissement C&I) | Fed | `DRTSCILM` |
| Euphorie (2) *approx.* | Sentiment AAII ; put/call | AAII ; CBOE | sources directes (hors FRED) |

> Les ID marqués *à confirmer* doivent être validés au premier appel API ; ne pas les supposer corrects.

---

## 6. Démarche de fabrication (phases)

- **Phase 1 — Cadre par configuration.** Un unique fichier `config` (YAML/JSON) : pour chaque signe → métrique(s), ID de série, *sens du danger* (ex. spread bas = danger), méthode de normalisation, poids de crédibilité. Ajouter un signe plus tard = ajouter une ligne, pas réécrire le code.
- **Phase 2 — Calibration historique (`calibrate.py`, exécuté une fois).** Rapatrier l'historique long ; calculer z-scores glissants ; extraire le relevé **T-12 mois** avant chaque krach de la liste ; sauver la **matrice-empreinte** (CSV). Krachs retenus : **1929, 1937, 1973-74, 1987, 2000, 2008, 2020** (ajustable).
- **Phase 3 — Moteur live (`monitor.py`, quotidien).** Dernières valeurs → z-scores calculés **sur la même base** que l'historique (crucial) → note par signe (vert/orange/rouge) → agrégation en indice composite **pondéré crédibilité** → mise à jour du journal des faux positifs.
- **Phase 4 — Automatisation.** Workflow GitHub Actions `schedule: cron` quotidien → lance `monitor.py`, archive les CSV, régénère le dashboard.
- **Phase 5 — Visualisation (`dashboard.py` → HTML).** Par signe : thermomètre du jour, lecture chiffrée, comparaison à l'empreinte de *chaque* krach, indice global, **compteur de faux positifs**.
- **Phase 6 — Extension.** Ajouter les signes 4, 6-8, 11-16 un par un via la config, en marquant distinctement approximatifs et qualitatifs.

---

## 7. Méthode de normalisation (transversale, non négociable)

- Ne jamais comparer des valeurs brutes entre époques → utiliser **z-score ou percentile** relatif à la propre histoire de chaque série.
- **Même méthode appliquée à l'historique ET au présent**, sinon aucune comparaison n'est valide.
- Gérer le **sens du danger** série par série (certaines : haut = danger ; d'autres inversées, ex. VIX très bas = complaisance).
- Sortie = **thermomètre par signe + indice composite**, jamais un « oui/non krach ».

---

## 8. Discipline anti-illusion (à intégrer dans l'outil lui-même)

1. **Backtest sans triche** : vérifier que l'indice s'allume avant les krachs historiques, en se méfiant du surajustement et du biais rétrospectif.
2. **Compteur de faux positifs visible** : afficher combien de fois l'indice a été « rouge » sans krach. C'est la garantie d'honnêteté.
3. **Le signe 16 reste hors de portée** : l'outil mesure la *fragilité accumulée*, pas le *timing de l'étincelle*.
4. **Biais de survie** : la calibration ne repose que sur les krachs *survenus* ; le vrai taux de faux positifs des marqueurs est inconnu et probablement élevé.

---

## 9. Première tâche concrète pour l'agent qui reprend

Construire le MVP (section 5) de bout en bout :
1. `config.yaml` avec les 6 signes du MVP.
2. `calibrate.py` : empreinte historique des 6 signes sur les 7 krachs.
3. `monitor.py` : relevé quotidien + z-scores + indice composite pondéré.
4. `.github/workflows/daily.yml` : automatisation quotidienne.
5. `dashboard.py` : page HTML de restitution.
Tester d'abord l'appel FRED (valider les ID de séries), puis itérer.
