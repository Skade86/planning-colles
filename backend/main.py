# --- Imports standards ---
import os
import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# --- Imports externes ---
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Query, Depends, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from ortools.sat.python import cp_model
from typing import Optional, Literal
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from bson import ObjectId

# --- Imports locaux ---
from db import get_db, init_db
from users import router as users_router, UserInDB, get_current_user, get_password_hash

from utils import export_excel_with_style, convert_form_to_csv
from logic import generate_planning_with_ortools, parse_groups, extract_all_groups, extract_week_columns, make_windows_non_overlapping, parse_hhmm_range_to_minutes
import shared_state

# Utilisation du nouveau système lifespan pour l'init MongoDB
@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://148.113.42.234:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Import des routers ---
from routes.planning import router as planning_router
from routes.generation import router as generation_router

app.include_router(users_router)
app.include_router(planning_router)
app.include_router(generation_router)

# -----------------------
# PlanningAnalyzer avec colles consécutives
# -----------------------

class PlanningAnalyzer:
    def __init__(self, csv_content, regles_alternance=None):
        self.df = pd.read_csv(io.StringIO(csv_content), sep=';')

        # Semaines dynamiques (colonnes numériques, ordre du CSV, non trié)
        self.weeks = [int(c) for c in self.df.columns if str(c).isdigit()]
        # NE PAS trier les semaines, respecter l'ordre du CSV
        
        # Détection automatique du nombre de groupes basé sur les données réelles
        all_groups = set()
        for week in self.weeks:
            week_str = str(week)
            for _, row in self.df.iterrows():
                val = row.get(week_str, "")
                try:
                    g = int(val)
                    if g > 0:  # Ignorer les valeurs négatives ou nulles
                        all_groups.add(g)
                except (ValueError, TypeError):
                    continue
        
        # Créer la liste des groupes triée
        self.groups = sorted(list(all_groups)) if all_groups else list(range(1, 16))  # fallback à 15 si aucun groupe détecté
        
        # Règles d'alternance configurables (par défaut: anciennes règles hardcodées)
        self.regles_alternance = regles_alternance or {
            'Mathématiques': { 'active': True, 'frequence': 2 },
            'Physique': { 'active': True, 'frequence': 2 },
            'Chimie': { 'active': True, 'frequence': 4 },
            'Anglais': { 'active': True, 'frequence': 2 },
            'Français': { 'active': True, 'frequence': 8 },
            'S.I': { 'active': True, 'frequence': 4 }
        }

        def make_windows_non_overlapping(weeks, size):
            return [tuple(weeks[i:i+size]) for i in range(0, len(weeks), size)
                    if len(weeks[i:i+size]) == size]

        self.groups_2 = make_windows_non_overlapping(self.weeks, 2)
        self.groups_4 = make_windows_non_overlapping(self.weeks, 4)
        self.groups_8 = make_windows_non_overlapping(self.weeks, 8)

    # -------------------- CONTRAINTES GLOBALES --------------------
    def verifier_contraintes_globales(self):
        erreurs = []
        for week in self.weeks:
            week_str = str(week)
            creneaux = {}

            for _, row in self.df.iterrows():
                val = row.get(week_str, "")
                try:
                    g = int(val)
                except (ValueError, TypeError):
                    continue

                prof = row.get("Prof", "Inconnu")
                jour = row.get("Jour", "Inconnu")
                heure = row.get("Heure", "Inconnu")
                matiere = row.get("Matière", "Inconnue")
                key = (jour, heure)
                creneaux.setdefault(key, []).append((prof, g, matiere))

            for (jour, heure), entries in creneaux.items():
                # Prof : pas 2 groupes en parallèle
                prof_to_groups = {}
                for prof, group, _ in entries:
                    prof_to_groups.setdefault(prof, []).append(group)
                for prof, groups in prof_to_groups.items():
                    if len(groups) > 1:
                        erreurs.append(f"Semaine {week}: PROF {prof} → groupes {sorted(groups)} ({jour} {heure})")

                # Groupe : pas 2 colles différentes en parallèle
                group_to_matieres = {}
                for prof, group, mat in entries:
                    group_to_matieres.setdefault(group, []).append((mat, prof))
                for group, mats in group_to_matieres.items():
                    if len(mats) > 1:
                        erreurs.append(f"Semaine {week}: GROUPE {group} → colles {mats} en parallèle ({jour} {heure})")

        return erreurs

    # -------------------- CONTRAINTES PAR GROUPE --------------------
    def verifier_contraintes_groupe(self, groupe):
        erreurs = []
        group_weeks = {w: [] for w in self.weeks}

        # Construire dict colles pour ce groupe
        for week in self.weeks:
            week_str = str(week)
            for _, row in self.df.iterrows():
                val = row.get(week_str, "")
                try:
                    g = int(val)
                except (ValueError, TypeError):
                    continue
                if g == groupe:
                    group_weeks[week].append([row["Matière"], row["Prof"], row["Jour"], row["Heure"]])

        # Vérification dynamique basée sur les règles configurables
        for matiere, regle in self.regles_alternance.items():
            if not regle.get('active', False):
                continue  # Ignorer les matières non activées
                
            frequence = regle.get('frequence', 2)
            
            if frequence == 1:
                # Chaque semaine - vérifier chaque semaine individuellement
                for week in self.weeks:
                    count = sum(1 for colle in group_weeks.get(week, []) if colle[0] == matiere)
                    if count != 1:
                        erreurs.append(f"{matiere} - Semaine {week}: {count} colles (attendu: 1 chaque semaine)")
                        
            elif frequence == 2:
                # Quinzaine - utiliser groups_2
                for quin in self.groups_2:
                    count = sum(
                        sum(1 for colle in group_weeks.get(w, []) if colle[0] == matiere)
                        for w in quin
                    )
                    if count != 1:
                        erreurs.append(f"{matiere} - Quinzaine {quin}: {count} colles (attendu: 1)")
                        
            elif frequence == 4:
                # 4 semaines - utiliser groups_4
                for bloc in self.groups_4:
                    count = sum(
                        sum(1 for colle in group_weeks.get(w, []) if colle[0] == matiere)
                        for w in bloc
                    )
                    if count != 1:
                        erreurs.append(f"{matiere} - Bloc {bloc}: {count} colles (attendu: 1)")
                        
            elif frequence == 8:
                # 8 semaines - utiliser groups_8 ou vérification globale
                if self.groups_8:
                    # Si on a des blocs de 8 semaines complets, on les utilise
                    for bloc in self.groups_8:
                        count = sum(
                            sum(1 for colle in group_weeks.get(w, []) 
                                if colle[0].strip().lower() == matiere.strip().lower())
                            for w in bloc
                        )
                        if count != 1:
                            erreurs.append(f"{matiere} - Bloc {bloc}: {count} colles (attendu: 1)")
                else:
                    # Si pas de bloc de 8 semaines complet, on vérifie sur toute la période
                    # (max 1 colle sur toute la période)
                    count = sum(
                        sum(1 for colle in group_weeks.get(w, [])
                            if colle[0].strip().lower() == matiere.strip().lower())
                        for w in self.weeks
                    )
                    if count > 1:
                        erreurs.append(f"{matiere} - Période complète {tuple(self.weeks)}: {count} colles (max 1 autorisée)")

        # Pas plus d'1 colle par jour
        for week in self.weeks:
            by_day = {}
            for mat, prof, jour, heure in group_weeks.get(week, []):
                by_day.setdefault(jour, []).append((mat, prof, heure))
            for jour, colles in by_day.items():
                if len(colles) > 1:
                    erreurs.append(
                        f"Groupe {groupe}, Semaine {week}, Jour {jour}: {len(colles)} colles (max 1 autorisée)"
                    )

        return erreurs

    # -------------------- CONSÉCUTIVES --------------------
    def _parse_heure_debut(self, heure_str):
        try:
            return int(str(heure_str).split("h-")[0])
        except Exception:
            return -1

    def colles_consecutives_par_groupe(self):
        result = {g: [] for g in self.groups}
        for g in self.groups:
            for week in self.weeks:
                week_str = str(week)
                colles = []
                for _, row in self.df.iterrows():
                    val = row.get(week_str, "")
                    try:
                        v = int(val)
                    except (ValueError, TypeError):
                        continue
                    if v == g:
                        colles.append((row["Jour"], row["Heure"], row["Matière"], row["Prof"]))

                # Groupement par jour
                by_day = {}
                for jour, heure, mat, prof in colles:
                    by_day.setdefault(jour, []).append((self._parse_heure_debut(heure), heure, mat, prof))

                for jour, items in by_day.items():
                    items.sort(key=lambda x: x[0])
                    for i in range(len(items) - 1):
                        if items[i+1][0] - items[i][0] == 1:
                            result[g].append(
                                f"Groupe {g}, Semaine {week}, {jour}: colles consécutives {items[i][1]} ({items[i][2]}-{items[i][3]}) puis {items[i+1][1]} ({items[i+1][2]}-{items[i+1][3]})"
                            )
        return result

    def verifier_colles_consecutives(self):
        messages = []
        data = self.colles_consecutives_par_groupe()
        for g, lst in data.items():
            messages.extend(lst)
        return messages

    # -------------------- STATS --------------------
    def stats_groupes(self):
        counts = {g: 0 for g in self.groups}
        for w in [str(w) for w in self.weeks]:
            for v in self.df[w]:
                try:
                    g = int(v)
                except (ValueError, TypeError):
                    continue
                if g in counts:
                    counts[g] += 1
        return counts

    def stats_matieres(self):
        mat_counts = {}
        for w in [str(w) for w in self.weeks]:
            for _, row in self.df.iterrows():
                try:
                    int(row[w])
                except (ValueError, TypeError):
                    continue
                mat = row["Matière"]
                mat_counts[mat] = mat_counts.get(mat, 0) + 1
        return mat_counts

    def stats_profs(self):
        prof_counts = {}
        for w in [str(w) for w in self.weeks]:
            for _, row in self.df.iterrows():
                try:
                    int(row[w])
                except (ValueError, TypeError):
                    continue
                prof = row["Prof"]
                prof_counts[prof] = prof_counts.get(prof, 0) + 1
        return prof_counts

    def charge_hebdo(self):
        charge = {g: [] for g in self.groups}
        for w in [str(w) for w in self.weeks]:
            weekly_counts = {g: 0 for g in self.groups}
            for _, row in self.df.iterrows():
                try:
                    g = int(row[w])
                except (ValueError, TypeError):
                    continue
                if g in weekly_counts:
                    weekly_counts[g] += 1
            for g in self.groups:
                charge[g].append(weekly_counts[g])
        return charge

    def statistiques_globales(self):
        # Calcul des créneaux réellement autorisés (selon contraintes du CSV)
        total_authorized = 0
        used = 0
        
        for w_int in self.weeks:
            w_str = str(w_int)
            is_even = w_int % 2 == 0
            
            for _, row in self.df.iterrows():
                # Vérifier si le prof travaille cette semaine
                works_even = str(row.get('Travaille les semaines paires', '')).strip().lower() == 'oui'
                works_odd = str(row.get('Travaille les semaines impaires', '')).strip().lower() == 'oui'
                
                if (is_even and works_even) or (not is_even and works_odd):
                    total_authorized += 1
                    
                    # Vérifier si un groupe est affecté à ce créneau
                    try:
                        int(row[w_str])
                        used += 1
                    except (ValueError, TypeError):
                        continue
        
        taux = round((used/total_authorized)*100, 1) if total_authorized else 0
        return {"total_creneaux": total_authorized, "creneaux_utilises": used, "taux_utilisation": taux}

    # -------------------- COMPATIBILITÉS PROFESSEURS --------------------
    def verifier_compatibilites_profs(self):
        """
        Vérifie que les professeurs respectent leurs disponibilités paires/impaires
        """
        erreurs = []

        for _, row in self.df.iterrows():
            prof = row.get("Prof", "Inconnu")
            matiere = row.get("Matière", "Inconnue")
            jour = row.get("Jour", "Inconnu")
            heure = row.get("Heure", "Inconnu")

            # Récupérer les disponibilités du prof
            travaille_paires = str(row.get("Travaille les semaines paires", "")).strip().lower() == "oui"
            travaille_impaires = str(row.get("Travaille les semaines impaires", "")).strip().lower() == "oui"

            # Vérifier chaque semaine où ce prof a une colle
            for week in self.weeks:
                week_str = str(week)
                val = row.get(week_str, "")

                try:
                    groupe = int(val)
                except (ValueError, TypeError):
                    continue  # Pas de groupe assigné cette semaine

                # Vérifier la compatibilité semaine paire/impaire
                is_even_week = week % 2 == 0

                if is_even_week and not travaille_paires:
                    erreurs.append(
                        f"Prof {prof} ({matiere}) a une colle groupe {groupe} en semaine {week} (PAIRE) "
                        f"mais ne travaille pas les semaines paires ({jour} {heure})"
                    )
                elif not is_even_week and not travaille_impaires:
                    erreurs.append(
                        f"Prof {prof} ({matiere}) a une colle groupe {groupe} en semaine {week} (IMPAIRE) "
                        f"mais ne travaille pas les semaines impaires ({jour} {heure})"
                    )

        return erreurs

    # -------------------- MÉTHODES UTILITAIRES --------------------
    def is_group_match(self, cell_value, groupe_id):
        """Vérifie si la valeur de la cellule correspond au groupe donné"""
        try:
            return int(cell_value) == groupe_id
        except (ValueError, TypeError):
            return False

    def compter_colles_groupe_semaine(self, groupe_id, semaine):
        """Compte le nombre de colles pour un groupe dans une semaine donnée"""
        count = 0
        semaine_str = str(semaine)
        for _, row in self.df.iterrows():
            if self.is_group_match(row.get(semaine_str, ""), groupe_id):
                count += 1
        return count

    # -------------------- WRAPPER --------------------
    def contraintes(self):
        return {
            "globales": self.verifier_contraintes_globales(),
            "groupes": {g: self.verifier_contraintes_groupe(g) for g in self.groups},
            "consecutives": self.verifier_colles_consecutives(),
            "compatibilites_profs": self.verifier_compatibilites_profs()
        }

# -----------------------
# API ROUTES
# -----------------------

@app.post("/api/analyse_planning")
async def analyse_planning(file: UploadFile = File(...), reglesAlternance: str = Form(None)):
    """
    Attend un upload CSV via form-data: clé "file" + règles d'alternance optionnelles
    """
    if not file:
        return JSONResponse(content={"error": "Aucun fichier reçu"}, status_code=400)

    try:
        content = (await file.read()).decode("utf-8")
        
        # Parse les règles d'alternance si fournies
        regles = {}
        if reglesAlternance:
            try:
                regles = json.loads(reglesAlternance)
            except json.JSONDecodeError:
                return JSONResponse(content={"error": "Format invalide pour reglesAlternance"}, status_code=400)
        
        analyzer = PlanningAnalyzer(content, regles_alternance=regles)

        stats = {
            "groupes": analyzer.stats_groupes(),
            "matieres": analyzer.stats_matieres(),
            "profs": analyzer.stats_profs(),
            "charge_hebdo": analyzer.charge_hebdo(),
            "globales": analyzer.statistiques_globales()
        }

        contraintes = analyzer.contraintes()

        resume = {
            "total_erreurs": (len(contraintes["globales"]) +
                              sum(len(v) for v in contraintes["groupes"].values()) +
                              len(contraintes["consecutives"]) +
                              len(contraintes["compatibilites_profs"])),
            "globales_ok": len(contraintes["globales"]) == 0,
            "groupes_ok": all(len(v) == 0 for v in contraintes["groupes"].values()),
            "consecutives_ok": len(contraintes["consecutives"]) == 0,
            "compatibilites_profs_ok": len(contraintes["compatibilites_profs"]) == 0,
        }

        return {
            "resume": resume,
            "stats": stats,
            "contraintes": contraintes
        }

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

class AnalysisRequest(BaseModel):
    reglesAlternance: dict = {}

@app.post("/api/analyse_planning_generated")
def analyse_planning_generated(request: AnalysisRequest):
    """
    Analyse le planning généré en mémoire (sans upload de fichier)
    Accepte les règles d'alternance configurables en JSON
    """
    if not shared_state.generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})

    try:
        analyzer = PlanningAnalyzer(shared_state.generated_planning, regles_alternance=request.reglesAlternance)

        stats = {
            "groupes": analyzer.stats_groupes(),
            "matieres": analyzer.stats_matieres(),
            "profs": analyzer.stats_profs(),
            "charge_hebdo": analyzer.charge_hebdo(),
            "globales": analyzer.statistiques_globales()
        }

        contraintes = analyzer.contraintes()

        resume = {
            "total_erreurs": (len(contraintes["globales"]) +
                              sum(len(v) for v in contraintes["groupes"].values()) +
                              len(contraintes["consecutives"]) +
                              len(contraintes["compatibilites_profs"])),
            "globales_ok": len(contraintes["globales"]) == 0,
            "groupes_ok": all(len(v) == 0 for v in contraintes["groupes"].values()),
            "consecutives_ok": len(contraintes["consecutives"]) == 0,
            "compatibilites_profs_ok": len(contraintes["compatibilites_profs"]) == 0,
        }

        return {
            "resume": resume,
            "stats": stats,
            "contraintes": contraintes
        }

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/group_details/{groupe_id}")
def group_details(groupe_id: int, user: UserInDB = Depends(get_current_user)):
    if not shared_state.generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})

    try:
        analyzer = PlanningAnalyzer(shared_state.generated_planning)

        if groupe_id not in analyzer.groups:
            return JSONResponse(status_code=404, content={"error": f"Groupe {groupe_id} introuvable"})

        # Créneaux du groupe
        creneaux = []
        for s in analyzer.weeks:
            s_str = str(s)
            for _, row in analyzer.df.iterrows():
                if analyzer.is_group_match(row.get(s_str, ""), groupe_id):
                    creneaux.append({
                        "semaine": s,
                        "matiere": row["Matière"],
                        "prof": row["Prof"],
                        "jour": row["Jour"],
                        "heure": row["Heure"]
                    })

        # Stats : par semaine et par matière
        stats = {
            "colles_par_semaine": {
                s: analyzer.compter_colles_groupe_semaine(groupe_id, s)
                for s in analyzer.weeks
            },
            "colles_par_matiere": {}
        }
        for matiere in analyzer.df["Matière"].unique():
            count = 0
            for s in analyzer.weeks:
                s_str = str(s)
                for _, row in analyzer.df.iterrows():
                    if row["Matière"] == matiere and analyzer.is_group_match(row.get(s_str, ""), groupe_id):
                        count += 1
            stats["colles_par_matiere"][matiere] = count

        return {"groupe": groupe_id, "creneaux": creneaux, "stats": stats}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur interne: {str(e)}"}
        )


@app.get("/api/hello")
def hello():
    return {"message":"Backend Planning Colles avec OR-Tools (semaines dynamiques)"}

