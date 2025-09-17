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
  - Analyse (`/api/analyse_planning*`) réservée aux `professeur`.
  - Upload, génération, téléchargement réservés aux utilisateurs authentifiés.

Un utilisateur `admin` (role `professeur`) est pré-créé en dev: `admin` / `admin`.