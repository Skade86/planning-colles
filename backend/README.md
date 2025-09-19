# Backend Planning Colles

## Lancer le backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
Le backend tourne alors sur http://localhost:8000

## Authentification (JWT)

- Endpoints:
  - `POST /api/auth/signup` (body JSON: `{ username, password, role }`)
  - `POST /api/auth/login` (form `application/x-www-form-urlencoded`: `username`, `password`) → `access_token`
- Envoyer le header `Authorization: Bearer <token>` pour les appels protégés.
- Rôles supportés: `utilisateur`, `professeur`.
  - Analyse (`/api/analyse_planning*`) accessible à tout utilisateur authentifié (démo).
  - Upload, génération, téléchargement réservés aux utilisateurs authentifiés.

Un utilisateur `admin` (role `professeur`) est pré-créé en dev: `admin` / `admin`.

## Configuration MongoDB (.env)

Crée un fichier `.env` dans `backend/` avec par exemple :

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=planning_colles
# Optionnel: SECRET_KEY personnalisé
SECRET_KEY=change-me-in-env
```

Le backend charge automatiquement ce fichier (via `python-dotenv`). Pour MongoDB Atlas, utilise l'URI fourni par Atlas.

## Persistance des plannings

- `POST /api/plannings/save` (auth requis)
  - Sauvegarde le dernier planning généré en mémoire (CSV) dans MongoDB.
  - Paramètre optionnel `name` (query) pour nommer le planning, sinon un nom par défaut est généré.
  - Réponse: `{ id, name, created_at }`

- `GET /api/plannings` (auth requis)
  - Liste les plannings (démo: tous les plannings, adapter pour filtrer par utilisateur si besoin).
  - Réponse: `{ items: [{ id, name, user, created_at }] }`

- `GET /api/plannings/{id}` (auth requis)
  - Récupère un planning stocké et renvoie `header` + `rows` pour affichage dans le frontend.

- `GET /api/plannings/{id}/download?format=csv|excel` (auth requis)
  - Télécharge un planning stocké au format CSV ou Excel stylé.