# 🏊🚴🏃 Triathlon Trainer

Application web mobile (PWA) pour préparer un **triathlon distance M** (1,5 km natation / 40 km vélo / 10 km course).

- **Plan d'entraînement** généré automatiquement jusqu'à la date de course : périodisation foncier → développement → spécifique → affûtage, semaines allégées toutes les 4 semaines, enchaînements vélo-course.
- **Journal des séances** : durée, distance, ressenti (RPE), FC moyenne, notes. Validation en un clic d'une séance du plan.
- **Suivi de progression** : volume hebdomadaire réalisé par sport face au volume prévu, totaux, assiduité, allures calculées.
- **Installable sur le téléphone** (manifest + service worker), consultation hors ligne des pages déjà visitées.

## Stack

| Couche | Techno |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| Données | SQLite via [SQLModel](https://sqlmodel.tiangolo.com/) |
| Front | Templates Jinja2 + [htmx](https://htmx.org/) (pas de build JS) |
| Graphiques | [Chart.js](https://www.chartjs.org/) |
| Tests | pytest + TestClient |

htmx et Chart.js sont embarqués dans `app/static/js/` : aucune dépendance à un CDN.

## Démarrer

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0
```

Puis ouvrir http://localhost:8000, aller dans **Réglages**, saisir la date de course et le volume hebdomadaire visé au pic.

Pour l'utiliser depuis le téléphone sur le réseau local : `http://<ip-du-pc>:8000`. L'installation en PWA (« Ajouter à l'écran d'accueil ») demande du HTTPS, sauf sur `localhost`.

La base est stockée dans `./data/triathlon.db` ; autre emplacement : `TRI_DB_URL=sqlite:////chemin/vers/base.db`.

## Tests

```bash
pytest -q
```

## Structure

```
app/
  main.py      # routes FastAPI (pages HTML + /api/stats/weekly)
  models.py    # tables SQLModel : Settings, PlannedSession, LoggedSession
  plan.py      # générateur de plan (fonction pure, testée)
  stats.py     # agrégats : volume hebdo, totaux, assiduité, allures
  templates/   # Jinja2 + htmx
  static/      # CSS, JS, icônes, manifest, service worker
tests/
```

## Comment le plan est construit

- Durée : de 3 à 16 semaines, la dernière se termine le jour de la course.
- Répartition des phases (ex. 16 sem.) : 6 foncier, 5 développement, 3 spécifique, 2 affûtage.
- Volume : ~55 % du volume pic au départ, 100 % en phase spécifique, 70 % puis 45 % en affûtage ; semaine allégée (×0,65) toutes les 4 semaines.
- Semaine type : repos / natation qualité / course qualité / vélo qualité / natation endurance / sortie longue vélo (+ enchaînement) / sortie longue course.

Régénérer le plan (changement de date ou de volume) conserve le journal et rattache les séances déjà validées.

## Pistes

- [ ] Import des activités Strava / Garmin (fichiers FIT/GPX)
- [ ] Zones cardio et allures personnalisées (test VMA, CSS natation, FTP)
- [ ] Déplacer / modifier une séance du plan
- [ ] Saisie hors ligne avec synchronisation
- [ ] Déploiement (Docker, Fly.io / Render)
