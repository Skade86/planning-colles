from fastapi import FastAPI, UploadFile, File, Query
from contextlib import asynccontextmanager
from fastapi import Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import csv
import io
import pandas as pd
from ortools.sat.python import cp_model
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId


# Utilisation du nouveau système lifespan pour l'init MongoDB
@asynccontextmanager
async def lifespan(app):
    global mongo_client, db
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DB]
    # Indexes utiles
    db.users.create_index("email", unique=True)
    # Seed utilisateurs de démo si absents
    if db.users.count_documents({"email": "admin@demo.fr"}) == 0:
        db.users.insert_one({
            "email": "admin@demo.fr",
            "nom": "Admin",
            "role": "professeur",
            "hashed_password": get_password_hash("admin"),
            "created_at": datetime.now(timezone.utc),
            "classes": ['PSIE'],
            'lycee': 'Lycée Camille Guérin'
        })
    if db.users.count_documents({"email": "user@demo.fr"}) == 0:
        db.users.insert_one({
            "email": "user@demo.fr",
            "nom": "Utilisateur",
            "role": "utilisateur",
            "hashed_password": get_password_hash("user"),
            "created_at": datetime.now(timezone.utc),
            "classes": ['PSIE'],
            'lycee': 'Lycée Camille Guérin'
        })
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://148.113.42.234:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Auth settings & models
# -----------------------
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[Literal["utilisateur", "professeur"]] = None

class User(BaseModel):
    email: str
    nom: Optional[str] = None
    role: Literal["utilisateur", "professeur"] = "utilisateur"

class UserInDB(User):
    hashed_password: str

class SignupRequest(BaseModel):
    email: str
    password: str
    nom: Optional[str] = None
    role: Literal["utilisateur", "professeur"] = "utilisateur"
    lycee: str
    classes: list[str]

# -----------------------
# MongoDB setup
# -----------------------
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB")

mongo_client: Optional[MongoClient] = None
db = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_user(username: str) -> Optional[UserInDB]:
    if db is None:
        return None
    doc = db.users.find_one({"email": username})
    if not doc:
        return None
    return UserInDB(email=doc["email"], nom=doc.get("nom"), role=doc.get("role", "utilisateur"), hashed_password=doc["hashed_password"])

async def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = await get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)  # noqa: F841
    except JWTError:
        raise credentials_exception
    user = await get_user(username)
    if user is None:
        raise credentials_exception
    return user

def require_role(*allowed_roles: Literal["utilisateur", "professeur"]):
    def _dep(user: UserInDB = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _dep

# -----------------------
# Auth routes
# -----------------------
@app.post("/api/auth/signup", response_model=User)
async def signup(req: SignupRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    exists = db.users.find_one({"email": req.email})
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")
    if not req.lycee or not req.classes or len(req.classes) == 0:
        raise HTTPException(status_code=400, detail="Lycée et au moins une classe sont obligatoires")
    db.users.insert_one({
        "email": req.email,
        "nom": req.nom,
        "role": req.role,
        "hashed_password": get_password_hash(req.password),
        "created_at": datetime.now(timezone.utc),
        "classes": req.classes,
        "lycee": req.lycee
    })
    return User(email=req.email, nom=req.nom, role=req.role)

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user.email, "role": user.role})
    return Token(access_token=access_token)

# -----------------------
# Profil utilisateur (lecture / mise à jour)
# -----------------------

class UserProfile(BaseModel):
    email: Optional[str] = None
    nom: Optional[str] = None
    classes: Optional[list[str]] = None
    lycee: Optional[str] = None

@app.get("/api/users/me")
async def get_me(user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    d = db.users.find_one({"email": user.email})
    if not d:
        return JSONResponse(status_code=404, content={"error": "Utilisateur introuvable"})
    return {
        "email": d["email"],
        "nom": d.get("nom"),
        "role": d.get("role"),
        "classes": d.get("classes", []),
        "matieres": d.get("matieres", []),
        "lycee": d.get("lycee")
    }

@app.put("/api/users/me")
async def update_me(payload: UserProfile, user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    update_doc = {k: v for k, v in payload.dict().items() if v is not None}
    if not update_doc:
        return {"updated": False}
    db.users.update_one({"email": user.email}, {"$set": update_doc})
    return {"updated": True}

# -----------------------
# Utils parsing groupes
# -----------------------
def parse_groups(txt):
    if pd.isna(txt) or txt == '':
        return []
    if 'à' in txt:
        a, b = txt.split('à')
        return list(range(int(a.strip()), int(b.strip()) + 1))
    return [int(str(txt).strip())]

def extract_all_groups(df):
    all_groups = set()
    for _, row in df.iterrows():
        all_groups.update(parse_groups(row['Groupes possibles semaine paire']))
        all_groups.update(parse_groups(row['Groupes possibles semaine impaire']))
    return sorted(list(all_groups))

# -----------------------
# Utils semaines dynamiques
# -----------------------
def extract_week_columns(df):
    """
    Retourne les colonnes semaines dans l'ordre du CSV.
    Ex: ["38","39","41","42",...], et leur version int.
    On ne trie pas : on respecte l'ordre fourni dans le fichier.
    """
    weeks_str = []
    for c in df.columns:
        if isinstance(c, str) and c.strip().isdigit():
            weeks_str.append(c.strip())
    weeks_int = [int(w) for w in weeks_str]
    return weeks_str, weeks_int

def make_windows_non_overlapping(weeks_list, size):
    """
    Découpe la liste des semaines en fenêtres non chevauchantes de 'size'.
    Ignore la dernière fenêtre si incomplète (ex: reste 1 semaine).
    Exemple: size=2 -> quinzaines, size=4 -> "mois" pédagogiques.
    """
    windows = []
    for i in range(0, len(weeks_list), size):
        chunk = weeks_list[i:i+size]
        if len(chunk) == size:
            windows.append(tuple(chunk))
    return windows

def parse_hhmm_range_to_minutes(hhmm_range):
    # "17h-18h" -> (1020, 1080)
    deb, fin = [p.strip() for p in str(hhmm_range).split('-')]
    def h2m(p):
        parts = str(p).split('h')
        h = int(parts[0]) if parts[0] else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        return h * 60 + m
    return h2m(deb), h2m(fin)

# -----------------------
# Génération OR-Tools avec semaines dynamiques
# -----------------------
def generate_planning_with_ortools(csv_content, mode="strict"):
    """
    Mode:
    - "strict": contraintes strictes (== 1) + interdit colles consécutives
    - "relaxed": fréquence >= 1 + interdit colles consécutives
    - "maximize": objectif de maximisation + minimise colles consécutives (pénalité douce)
    """
    df = pd.read_csv(io.StringIO(csv_content), sep=';')

    # Normalisation pour fiabiliser les contraintes
    df['Jour'] = df['Jour'].astype(str).str.strip()
    df['Heure'] = (
        df['Heure'].astype(str)
        .str.replace(' ', '', regex=False)  # "18h - 19h" -> "18h-19h"
        .str.strip()
    )

    groups = extract_all_groups(df)
    if not groups:
        return None, "Aucun groupe détecté dans le CSV"

    # Semaines dynamiques depuis le CSV (ordre respecté, non trié)
    weeks_str, weeks_int = extract_week_columns(df)
    if not weeks_str:
        return None, "Aucune colonne de semaine détectée dans le CSV"

    print(f"[DEBUG] Mode: {mode}, Groupes: {groups}, Weeks: {weeks_str}")

    # Fenêtres dynamiques basées sur la liste
    # Quinzaines: fenêtres non chevauchantes de 2 semaines (selon l'ordre du CSV)
    quinz = make_windows_non_overlapping(weeks_str, 2)
    # "Mois" pédagogiques: fenêtres non chevauchantes de 4 semaines
    mois = make_windows_non_overlapping(weeks_str, 4)
    eight_week_blocks = make_windows_non_overlapping(weeks_str, 8)

    # Création des slots
    slots = []
    for _, row in df.iterrows():
        slots.append(dict(
            mat=row['Matière'],
            prof=row['Prof'],
            day=row['Jour'],
            hour=row['Heure'],
            even=parse_groups(row['Groupes possibles semaine paire']),
            odd=parse_groups(row['Groupes possibles semaine impaire']),
            works_even=(str(row['Travaille les semaines paires']).strip() == 'Oui'),
            works_odd=(str(row['Travaille les semaines impaires']).strip() == 'Oui')
        ))

    model = cp_model.CpModel()
    X = {}

    # Variables: respect pair/impair + autorisations par slot
    for s, slot in enumerate(slots):
        for w_str, w_int in zip(weeks_str, weeks_int):
            for g in groups:
                if (w_int % 2 == 0 and (g not in slot['even'] or not slot['works_even'])) or \
                   (w_int % 2 == 1 and (g not in slot['odd'] or not slot['works_odd'])):
                    continue
                X[s, w_str, g] = model.NewBoolVar(f"x_{s}_{w_str}_{g}")

    # 1) Un seul groupe par slot/semaine
    for s in range(len(slots)):
        for w_str in weeks_str:
            model.Add(sum(X.get((s, w_str, g), 0) for g in groups) <= 1)

    # 1bis) Prof unique par créneau (hors maximize)
    if mode != "maximize":
        for w_str in weeks_str:
            for prof in df['Prof'].unique():
                for day in df['Jour'].unique():
                    for hour in df['Heure'].unique():
                        model.Add(
                            sum(
                                X.get((s, w_str, g), 0)
                                for s, sl in enumerate(slots)
                                if sl['prof'] == prof and sl['day'] == day and sl['hour'] == hour
                                for g in groups
                            ) <= 1
                        )

    # 2) Fréquences par matière (selon mode) sur fenêtres dynamiques
    if mode != "maximize":
        for g in groups:
            # 1 par quinzaine pour Maths/Physique/Anglais
            for mat in ['Mathématiques', 'Physique', 'Anglais']:
                for q in quinz:
                    constraint_sum = sum(
                        X.get((s, w, g), 0)
                        for s, sl in enumerate(slots) if sl['mat'] == mat
                        for w in q
                    )
                    if mode == "strict":
                        model.Add(constraint_sum == 1)
                    else:
                        model.Add(constraint_sum >= 1)

            # 1 par "mois" (4 semaines)
            for mat in ['Chimie', 'S.I']:
                for m in mois:
                    constraint_sum = sum(
                        X.get((s, w, g), 0)
                        for s, sl in enumerate(slots) if sl['mat'] == mat
                        for w in m
                    )
                    if mode == "strict":
                        model.Add(constraint_sum == 1)
                    else:
                        model.Add(constraint_sum >= 1)

            # Français: 1 sur toute la période (toutes semaines détectées)
            # Français: 1 par tranche de 8 semaines
            for g in groups:
                for block in eight_week_blocks:
                    constraint_sum = sum(
                        X.get((s, w, g), 0)
                        for s, sl in enumerate(slots) if sl['mat'] == 'Français'
                        for w in block
                    )
                    if mode == "strict":
                        model.Add(constraint_sum == 1)
                    else:
                        model.Add(constraint_sum >= 1)

    # 3) Rotation profs sur 2 quinzaines adjacentes (hors maximize)
    if mode != "maximize":
        if len(quinz) >= 2:
            for g in groups:
                for mat in ['Mathématiques', 'Physique', 'Anglais']:
                    profs_mat = sorted({sl['prof'] for sl in slots if sl['mat'] == mat})
                    for p in profs_mat:
                        for i in range(len(quinz) - 1):
                            Q1, Q2 = quinz[i], quinz[i + 1]
                            model.Add(
                                sum(
                                    X.get((s, w, g), 0)
                                    for s, sl in enumerate(slots) if sl['mat'] == mat and sl['prof'] == p
                                    for w in Q1
                                )
                                +
                                sum(
                                    X.get((s, w, g), 0)
                                    for s, sl in enumerate(slots) if sl['mat'] == mat and sl['prof'] == p
                                    for w in Q2
                                )
                                <= 1
                            )

    # 4) Pas deux colles même jour+heure pour un groupe
    for g in groups:
        for w_str in weeks_str:
            for day in df['Jour'].unique():
                for hour in df['Heure'].unique():
                    model.Add(
                        sum(
                            X.get((s, w_str, g), 0)
                            for s, sl in enumerate(slots)
                            if sl['day'] == day and sl['hour'] == hour
                        ) <= 1
                    )

    # 5) Charge hebdo (bornes)
    for g in groups:
        for w_str in weeks_str:
            if mode == "maximize":
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) <= 4)
            else:
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) >= 1)
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) <= 4)

    # 6) Interdire systématiquement les colles consécutives (hard constraint)
    for g in groups:
        for w_str in weeks_str:
            for day in df['Jour'].unique():
                # Créneaux de ce jour (triés par heure de début)
                slots_day = [(s, sl) for s, sl in enumerate(slots) if sl['day'] == day]
                slots_day.sort(key=lambda x: parse_hhmm_range_to_minutes(x[1]['hour'])[0])

                for i in range(len(slots_day) - 1):
                    s1, sl1 = slots_day[i]
                    s2, sl2 = slots_day[i + 1]
                    _, end1 = parse_hhmm_range_to_minutes(sl1['hour'])
                    start2, _ = parse_hhmm_range_to_minutes(sl2['hour'])

                    if end1 == start2:
                        # HARD: jamais 2 colles back-to-back pour un groupe
                        model.Add(X.get((s1, w_str, g), 0) + X.get((s2, w_str, g), 0) <= 1)
    
        # (Hard) Au plus 1 colle par jour pour chaque groupe et semaine
    for g in groups:
        for w_str in weeks_str:
            for day in df['Jour'].unique():
                model.Add(
                    sum(
                        X.get((s, w_str, g), 0)
                        for s, sl in enumerate(slots)
                        if sl['day'] == day
                    ) <= 1
                )
    # Objectif
    if mode == "maximize":
        model.Maximize(sum(X.values()))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.Solve(model)
    print(f"[DEBUG] Status: {status}, Mode: {mode}")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, f"Aucune solution trouvée en mode {mode}"

    # Injection: (ré)écrit uniquement les colonnes semaines détectées
    for w_str in weeks_str:
        col = []
        for s in range(len(slots)):
            g_found = ''
            for g in groups:
                if (s, w_str, g) in X and solver.Value(X[s, w_str, g]) == 1:
                    g_found = str(g)
                    break
            col.append(g_found)
        df[w_str] = col

    mode_msg = {
        "strict": "Planning généré (semaines dynamiques, consécutives interdites)",
        "relaxed": "Planning généré (semaines dynamiques, contraintes relâchées, consécutives interdites)",
        "maximize": "Planning généré (semaines dynamiques, max colles & min colles consécutives)"
    }
    #df = adjust_late_slots(df)
    return df, mode_msg.get(mode, f"Planning généré en mode {mode}")

# -----------------------
# Export Excel avec style
# -----------------------

def export_excel_with_style(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Planning", index=False)

        workbook = writer.book
        worksheet = writer.sheets["Planning"]

        # Formats
        header_format = workbook.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "bg_color": "#DCE6F1", "border": 1
        })
        normal_format = workbook.add_format({"border": 1, "align": "center"})
        grey_format   = workbook.add_format({"border": 1, "align": "center", "bg_color": "#E6E6E6"})

        # Largeur colonnes auto
        for col_num, value in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, 12)

        # Masquer colonnes "Groupes possibles semaine paire/impaire"
        worksheet.set_column("E:H", None, None, {"hidden": True})

        # En-têtes stylées
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Contenu stylé
        for row in range(1, len(df) + 1):
            for col in range(len(df.columns)):
                val = df.iloc[row - 1, col]
                if pd.isna(val) or str(val).strip() == "":
                    worksheet.write(row, col, "", grey_format)
                else:
                    worksheet.write(row, col, val, normal_format)

    out.seek(0)
    return out

# -----------------------
# PlanningAnalyzer avec colles consécutives
# -----------------------

class PlanningAnalyzer:
    def __init__(self, csv_content):
        self.df = pd.read_csv(io.StringIO(csv_content), sep=';')

        # Semaines dynamiques (colonnes numériques, ordre du CSV, non trié)
        self.weeks = [int(c) for c in self.df.columns if str(c).isdigit()]
        # NE PAS trier les semaines, respecter l'ordre du CSV
        self.groups = list(range(1, 16))  # 15 groupes

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

        # Maths / Physique / Anglais → 1 par quinzaine
        for matiere in ["Mathématiques", "Physique", "Anglais"]:
            for quin in self.groups_2:
                count = sum(
                    sum(1 for colle in group_weeks.get(w, []) if colle[0] == matiere)
                    for w in quin
                )
                if count != 1:
                    erreurs.append(f"{matiere} - Quinzaine {quin}: {count} colles (attendu: 1)")

        # Chimie / SI → 1 par 4 semaines
        for matiere in ["Chimie", "S.I"]:
            for bloc in self.groups_4:
                count = sum(
                    sum(1 for colle in group_weeks.get(w, []) if colle[0] == matiere)
                    for w in bloc
                )
                if count != 1:
                    erreurs.append(f"{matiere} - Bloc {bloc}: {count} colles (attendu: 1)")

        # Français → 1 par 8 semaines (vérification robuste)
        if self.groups_8:
            # Si on a des blocs de 8 semaines complets, on les utilise
            for bloc in self.groups_8:
                count = sum(
                    sum(1 for colle in group_weeks.get(w, [])
                        if colle[0].strip().lower() in ["français", "francais"])
                    for w in bloc
                )
                if count != 1:
                    erreurs.append(f"Français - Bloc {bloc}: {count} colles (attendu: 1)")
        else:
            # Si pas de bloc de 8 semaines complet, on vérifie sur toute la période
            # (max 1 colle de français sur toute la période)
            count = sum(
                sum(1 for colle in group_weeks.get(w, [])
                    if colle[0].strip().lower() in ["français", "francais"])
                for w in self.weeks
            )
            if count > 1:
                erreurs.append(f"Français - Période complète {tuple(self.weeks)}: {count} colles (max 1 autorisée sur {len(self.weeks)} semaines)")
                erreurs.append(f"Français - Période complète {tuple(self.weeks)}: {count} colles (max 1 autorisée)")
            # Note: on n'exige pas 1 colle si la période est courte

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
uploaded_csv, generated_planning = None, None

@app.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...), user: UserInDB = Depends(get_current_user)):
    global uploaded_csv
    content = await file.read()
    decoded=content.decode("utf-8")
    uploaded_csv=decoded
    reader=csv.reader(io.StringIO(decoded),delimiter=';')
    rows=list(reader)
    return {"header":rows[0],"preview":rows[1:6]}

@app.post("/api/generate_planning")
async def generate_planning(user: UserInDB = Depends(get_current_user)):
    global uploaded_csv, generated_planning
    if not uploaded_csv: 
        return JSONResponse(status_code=400, content={"error":"Aucun fichier CSV uploadé."})

    # Essai 1: mode strict
    print("[INFO] Tentative mode strict...")
    df_result, message = generate_planning_with_ortools(uploaded_csv, mode="strict")
    
    if df_result is None:
        # Essai 2: mode relaxed
        print("[INFO] Échec mode strict, tentative mode relaxed...")
        df_result, message = generate_planning_with_ortools(uploaded_csv, mode="relaxed")
        
        if df_result is None:
            # Essai 3: mode maximize (sauvegarde)
            print("[INFO] Échec mode relaxed, tentative mode maximize...")
            df_result, message = generate_planning_with_ortools(uploaded_csv, mode="maximize")
            
            if df_result is None:
                return JSONResponse(status_code=400, content={"error": "Impossible de générer un planning même en mode sauvegarde"})

    output=io.StringIO()
    df_result.to_csv(output,sep=';',index=False)
    generated_planning=output.getvalue()
    
    return {
        "header": df_result.columns.tolist(),
        "rows": df_result.values.tolist(),
        "message": message
    }

@app.post("/api/analyse_planning")
async def analyse_planning(file: UploadFile = File(...), user: UserInDB = Depends(get_current_user)):
    """
    Attend un upload CSV via form-data: clé "file"
    """
    if not file:
        return JSONResponse(content={"error": "Aucun fichier reçu"}, status_code=400)

    try:
        content = (await file.read()).decode("utf-8")
        analyzer = PlanningAnalyzer(content)

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

@app.get("/api/analyse_planning_generated")
def analyse_planning_generated(user: UserInDB = Depends(get_current_user)):
    """
    Analyse le planning généré en mémoire (sans upload de fichier)
    """
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})

    try:
        analyzer = PlanningAnalyzer(generated_planning)

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

@app.get("/api/get_groups")
def get_groups(user: UserInDB = Depends(get_current_user)):
    global generated_planning
    if not generated_planning: 
        return JSONResponse(status_code=400, content={"error":"Aucun planning généré."})
    
    analyzer=PlanningAnalyzer(generated_planning)
    return {"groups":analyzer.groups}

@app.get("/api/group_details/{groupe_id}")
def group_details(groupe_id: int, user: UserInDB = Depends(get_current_user)):
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})

    try:
        analyzer = PlanningAnalyzer(generated_planning)

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

@app.get("/api/download_planning")
async def download_planning(format: str = Query("csv", enum=["csv", "excel"]), user: UserInDB = Depends(get_current_user)):
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    
    df = pd.read_csv(io.StringIO(generated_planning), sep=';')
    
    if format == "excel":
        out = io.BytesIO()
        out = export_excel_with_style(df)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=planning_optimise.xlsx"}
        )
    else:  # CSV par défaut
        return StreamingResponse(
            io.StringIO(generated_planning),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=planning_optimise.csv"}
        )

@app.post("/api/generate_from_form")
async def generate_from_form(form_data: dict, user: UserInDB = Depends(get_current_user)):
    """
    Génère un planning à partir des données du formulaire de saisie
    """
    global generated_planning
    
    try:
        # Convertir les données du formulaire en CSV
        csv_content = convert_form_to_csv(form_data)
        
        # Générer le planning avec OR-Tools (essai des 3 modes)
        print("[INFO] Tentative mode strict...")
        df_result, message = generate_planning_with_ortools(csv_content, mode="strict")
        
        if df_result is None:
            print("[INFO] Échec mode strict, tentative mode relaxed...")
            df_result, message = generate_planning_with_ortools(csv_content, mode="relaxed")
            
            if df_result is None:
                print("[INFO] Échec mode relaxed, tentative mode maximize...")
                df_result, message = generate_planning_with_ortools(csv_content, mode="maximize")
                
                if df_result is None:
                    return JSONResponse(
                        status_code=400, 
                        content={"error": "Impossible de générer un planning avec les contraintes données"}
                    )

        # Sauvegarder le planning généré
        output = io.StringIO()
        df_result.to_csv(output, sep=';', index=False)
        generated_planning = output.getvalue()
        
        return {
            "header": df_result.columns.tolist(),
            "rows": df_result.values.tolist(),
            "message": message + " (généré depuis le formulaire)"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur lors de la génération: {str(e)}"}
        )

def convert_form_to_csv(form_data):
    """
    Convertit les données du formulaire en format CSV équivalent
    """
    semaines = form_data.get('semaines', [])
    professeurs = form_data.get('professeurs', [])
    creneaux = form_data.get('creneaux', [])
    
    # Créer les en-têtes
    headers = [
        'Matière', 'Prof', 'Jour', 'Heure',
        'Groupes possibles semaine paire', 'Groupes possibles semaine impaire',
        'Travaille les semaines paires', 'Travaille les semaines impaires'
    ] + [str(s) for s in semaines]
    
    # Créer les lignes de données
    rows = []
    for creneau in creneaux:
        # Trouver le professeur correspondant
        prof_info = None
        for prof in professeurs:
            if prof.get('nom') == creneau.get('professeur'):
                prof_info = prof
                break
        
        if not prof_info:
            continue
            
        # Formater les plages de groupes
        groupes_paires = f"{creneau.get('groupesPaires', {}).get('min', 1)} à {creneau.get('groupesPaires', {}).get('max', 15)}"
        groupes_impaires = f"{creneau.get('groupesImpaires', {}).get('min', 1)} à {creneau.get('groupesImpaires', {}).get('max', 15)}"
        
        # Ligne de données
        row = [
            creneau.get('matiere', ''),
            creneau.get('professeur', ''),
            creneau.get('jour', ''),
            creneau.get('heure', ''),
            groupes_paires,
            groupes_impaires,
            'Oui' if prof_info.get('travaillePaires', True) else 'Non',
            'Oui' if prof_info.get('travailleImpaires', True) else 'Non'
        ] + [''] * len(semaines)  # Colonnes semaines vides initialement
        
        rows.append(row)
    
    # Créer le CSV
    csv_content = ';'.join(headers) + '\n'
    for row in rows:
        csv_content += ';'.join(str(cell) for cell in row) + '\n'
    
    return csv_content

@app.get("/api/hello")
def hello():
    return {"message":"Backend Planning Colles avec OR-Tools (semaines dynamiques)"}

# -----------------------
# Persistence des plannings (MongoDB)
# -----------------------

def _safe_object_id(oid: str) -> ObjectId:
    try:
        return ObjectId(oid)
    except Exception:
        raise HTTPException(status_code=400, detail="Identifiant invalide")

@app.post("/api/plannings/save")
async def save_planning(name: str = Query(None), user: UserInDB = Depends(get_current_user)):
    global generated_planning
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré à sauvegarder"})

    now = datetime.now(timezone.utc)
    doc = {
        "user": user.email,
        "name": name or f"Planning {now.date().isoformat()} {now.strftime('%H:%M')}",
        "created_at": now,
        "csv_content": generated_planning,
    }
    res = db.plannings.insert_one(doc)
    return {"id": str(res.inserted_id), "name": doc["name"], "created_at": doc["created_at"].isoformat()}

@app.get("/api/plannings")
async def list_plannings(user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    # On récupère les emails des users du même lycée et ayant au moins une classe en commun
    user_doc = db.users.find_one({"email": user.email})
    if not user_doc:
        return JSONResponse(status_code=404, content={"error": "Utilisateur introuvable"})
    user_classes = set(user_doc.get("classes", []))
    user_lycee = user_doc.get("lycee", "")
    # Trouver tous les utilisateurs du même lycée et au moins une classe en commun
    allowed_users = set()
    for u in db.users.find({"lycee": user_lycee}):
        classes = set(u.get("classes", []))
        if user_classes & classes:
            allowed_users.add(u["email"])
    cursor = db.plannings.find({"user": {"$in": list(allowed_users)}}, {"csv_content": 0}).sort("created_at", -1)
    items = []
    for d in cursor:
        items.append({
            "id": str(d["_id"]),
            "name": d.get("name", "Planning"),
            "user": d.get("user", ""),
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
        })
    return {"items": items}

@app.get("/api/plannings/{planning_id}")
async def get_planning(planning_id: str, user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    d = db.plannings.find_one({"_id": _safe_object_id(planning_id)})
    if not d:
        return JSONResponse(status_code=404, content={"error": "Planning introuvable"})
    # Restriction d'accès : même lycée ET au moins une classe en commun
    user_doc = db.users.find_one({"email": user.email})
    if not user_doc:
        return JSONResponse(status_code=404, content={"error": "Utilisateur introuvable"})
    user_classes = set(user_doc.get("classes", []))
    user_lycee = user_doc.get("lycee", "")
    owner_doc = db.users.find_one({"email": d.get("user")})
    if not owner_doc:
        return JSONResponse(status_code=404, content={"error": "Auteur du planning introuvable"})
    owner_classes = set(owner_doc.get("classes", []))
    owner_lycee = owner_doc.get("lycee", "")
    if user_lycee != owner_lycee or not (user_classes & owner_classes):
        return JSONResponse(status_code=403, content={"error": "Accès refusé à ce planning"})
    df = pd.read_csv(io.StringIO(d.get("csv_content", "")), sep=';')
    return {"id": planning_id, "name": d.get("name"), "header": df.columns.tolist(), "rows": df.values.tolist()}

@app.get("/api/plannings/{planning_id}/download")
async def download_saved_planning(planning_id: str, format: str = Query("csv", enum=["csv", "excel"]), user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    d = db.plannings.find_one({"_id": _safe_object_id(planning_id)})
    if not d:
        return JSONResponse(status_code=404, content={"error": "Planning introuvable"})
    # Restriction d'accès : même lycée ET au moins une classe en commun
    user_doc = db.users.find_one({"email": user.email})
    if not user_doc:
        return JSONResponse(status_code=404, content={"error": "Utilisateur introuvable"})
    user_classes = set(user_doc.get("classes", []))
    user_lycee = user_doc.get("lycee", "")
    owner_doc = db.users.find_one({"email": d.get("user")})
    if not owner_doc:
        return JSONResponse(status_code=404, content={"error": "Auteur du planning introuvable"})
    owner_classes = set(owner_doc.get("classes", []))
    owner_lycee = owner_doc.get("lycee", "")
    if user_lycee != owner_lycee or not (user_classes & owner_classes):
        return JSONResponse(status_code=403, content={"error": "Accès refusé à ce planning"})
    csv_content = d.get("csv_content", "")
    if format == "excel":
        df = pd.read_csv(io.StringIO(csv_content), sep=';')
        out = export_excel_with_style(df)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={d.get('name','planning')}.xlsx"}
        )
    else:
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={d.get('name','planning')}.csv"}
        )

# --- Changement de mot de passe utilisateur ---
from pydantic import BaseModel as PydanticBaseModel

class PasswordChangeRequest(PydanticBaseModel):
    password: str

@app.put("/api/users/me/password")
async def change_password(payload: PasswordChangeRequest, user: UserInDB = Depends(get_current_user)):
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    if not payload.password or len(payload.password) < 4:
        return JSONResponse(status_code=400, content={"error": "Mot de passe trop court"})
    db.users.update_one({"email": user.email}, {"$set": {"hashed_password": get_password_hash(payload.password)}})
    return {"updated": True}