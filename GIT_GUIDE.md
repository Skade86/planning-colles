# Planning Colles - Gestion Git Locale

## 🎯 Commandes Git essentielles pour votre projet

### Commandes de base
```bash
# Voir l'état du dépôt
git status

# Ajouter tous les fichiers modifiés
git add .

# Faire un commit avec message
git commit -m "Description des changements"

# Voir l'historique des commits
git log --oneline

# Voir les différences non commitées
git diff
```

### Gestion des branches
```bash
# Créer une nouvelle branche
git checkout -b nom-de-la-branche

# Changer de branche
git checkout nom-de-la-branche

# Lister toutes les branches
git branch

# Fusionner une branche dans main
git checkout main
git merge nom-de-la-branche
```

### Commandes utiles
```bash
# Annuler les modifications non commitées
git checkout -- nom-du-fichier

# Revenir au commit précédent (attention!)
git reset --hard HEAD~1

# Voir les fichiers ignorés par .gitignore
git status --ignored
```

## 🚀 Workflow recommandé

1. **Avant de commencer à travailler :**
   ```bash
   git status
   ```

2. **Après avoir fait des modifications :**
   ```bash
   git add .
   git commit -m "Ajout de [fonctionnalité/correction]"
   ```

3. **Pour une nouvelle fonctionnalité importante :**
   ```bash
   git checkout -b feature/nouvelle-fonctionnalite
   # ... travail ...
   git add .
   git commit -m "Implémentation nouvelle fonctionnalité"
   git checkout main
   git merge feature/nouvelle-fonctionnalite
   ```

## 📁 Fichiers ignorés par Git

Le fichier `.gitignore` exclut automatiquement :
- `node_modules/` et `__pycache__/`
- Fichiers de build et temporaires
- Logs et fichiers système
- Fichiers CSV/Excel (données sensibles)
- Scripts temporaires du launcher

## 💡 Conseils

- **Commitez souvent** : Petits commits fréquents plutôt que gros commits rares
- **Messages clairs** : Décrivez ce que fait le commit, pas comment
- **Branches** : Utilisez des branches pour les nouvelles fonctionnalités
- **Sauvegarde** : Votre dépôt local est déjà une excellente sauvegarde !