# Planning Colles - Projet Complet

## Structure

- `backend/` : API FastAPI (upload CSV, endpoints planning)
- `frontend/` : Application React (upload, affichage planning)

## Lancement rapide

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

## Utilisation

1. Lance le backend (http://localhost:8000)
2. Lance le frontend (http://localhost:3000)
3. Upload un fichier CSV via l'interface web

Tu peux ensuite compléter la logique de génération de planning dans `backend/main.py` !

## Dépannage

- Si erreur "metadata-generation-failed" : `pip install --upgrade pip setuptools wheel`
- Si erreur "react-scripts not found" : `rm -rf node_modules && npm install`
- Si erreur "Unexpected token '<'" : vérifier que le backend tourne sur le port 8000
