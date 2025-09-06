from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import csv
import io
import pandas as pd
from ortools.sat.python import cp_model
from collections import defaultdict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _unique_minimal_families(families):
    """
    Conserve les sous-plages minimales:
    - élimine les familles qui sont des sur-ensembles stricts d'une autre
    - déduplique
    """
    # normaliser en tuples triés uniques
    norm = []
    for fam in families:
        if fam:
            t = tuple(sorted(set(int(x) for x in fam)))
            if t not in norm:
                norm.append(t)
    # enlever les sur-ensembles
    keep = []
    for f in norm:
        is_superset = any(set(other).issubset(set(f)) and set(other) != set(f) for other in norm)
        if not is_superset:
            keep.append(f)
    # retourner en listes
    return [list(f) for f in keep]

def detect_group_families(df):
    """
    Détecte automatiquement les familles de groupes à partir des colonnes
    'Groupes possibles semaine paire' et 'Groupes possibles semaine impaire'.
    On retourne des sous-plages minimales (ex: [1..8], [9..16] plutôt que [1..16]).
    """
    raw_families = []
    for col in ['Groupes possibles semaine paire', 'Groupes possibles semaine impaire']:
        if col not in df.columns:
            continue
        for _, val in df[col].dropna().items():
            fam = parse_groups(val)
            if fam:
                raw_families.append(fam)
    families = _unique_minimal_families(raw_families)
    # si aucune famille détectée, fallback = une seule famille avec tous les groupes
    if not families:
        families = [extract_all_groups(df)]
    return families


# -----------------------
# Génération OR-Tools ROBUSTE (3 niveaux)
# -----------------------
def generate_planning_with_ortools(csv_content, mode="strict"):
    """
    Mode peut être:
    - "strict": toutes contraintes strictes (== 1)
    - "relaxed": contraintes de fréquence >= 1 au lieu de == 1
    - "maximize": objectif de maximisation, contraintes minimales
    """
    df = pd.read_csv(io.StringIO(csv_content), sep=';')
    groups = extract_all_groups(df)
    if not groups:
        return None, "Aucun groupe détecté dans le CSV"

    print(f"[DEBUG] Mode: {mode}, Groupes: {groups}")

    slots = []
    for _, row in df.iterrows():
        slots.append(dict(
            mat=row['Matière'],
            prof=row['Prof'],
            day=row['Jour'],
            hour=row['Heure'],
            even=parse_groups(row['Groupes possibles semaine paire']),
            odd=parse_groups(row['Groupes possibles semaine impaire']),
            works_even=row['Travaille les semaines paires'] == 'Oui',
            works_odd=row['Travaille les semaines impaires'] == 'Oui'
        ))

    weeks = list(range(38, 46))
    model = cp_model.CpModel()
    X = {}

    # Variables
    for s, slot in enumerate(slots):
        for w in weeks:
            for g in groups:
                if (w % 2 == 0 and (g not in slot['even'] or not slot['works_even'])) or \
                   (w % 2 == 1 and (g not in slot['odd'] or not slot['works_odd'])):
                    continue
                X[s, w, g] = model.NewBoolVar(f"x_{s}_{w}_{g}")

    # Contrainte 1: pas deux groupes dans le même slot
    for s in range(len(slots)):
        for w in weeks:
            model.Add(sum(X.get((s, w, g), 0) for g in groups) <= 1)

    # Contrainte 1bis: prof unique par créneau (sauf en mode maximize)
    if mode != "maximize":
        for w in weeks:
            for prof in df['Prof'].unique():
                for day in df['Jour'].unique():
                    for hour in df['Heure'].unique():
                        model.Add(
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots)
                                if sl['prof'] == prof and sl['day'] == day and sl['hour'] == hour
                                for g in groups) <= 1
                        )

    # Contrainte 2: fréquences (strict vs relaxed)
    quinz = [(38, 39), (40, 41), (42, 43), (44, 45)]
    mois  = [(38, 39, 40, 41), (42, 43, 44, 45)]

    if mode != "maximize":
        for g in groups:
            # Mathématiques, Physique, Anglais: 1 par quinzaine
            for mat in ['Mathématiques', 'Physique', 'Anglais']:
                for q in quinz:
                    constraint_sum = sum(X.get((s, w, g), 0)
                                       for s, sl in enumerate(slots) if sl['mat'] == mat
                                       for w in q)
                    if mode == "strict":
                        model.Add(constraint_sum == 1)
                    else:  # relaxed
                        model.Add(constraint_sum >= 1)

            # Chimie, S.I: 1 par mois
            for mat in ['Chimie', 'S.I']:
                for m in mois:
                    constraint_sum = sum(X.get((s, w, g), 0)
                                       for s, sl in enumerate(slots) if sl['mat'] == mat
                                       for w in m)
                    if mode == "strict":
                        model.Add(constraint_sum == 1)
                    else:  # relaxed
                        model.Add(constraint_sum >= 1)

            # Français: 1 sur toute la période
            constraint_sum = sum(X.get((s, w, g), 0)
                               for s, sl in enumerate(slots) if sl['mat'] == 'Français'
                               for w in weeks)
            if mode == "strict":
                model.Add(constraint_sum == 1)
            else:  # relaxed
                model.Add(constraint_sum >= 1)

    # Contrainte 3: rotation profs (sauf en mode maximize)
    if mode != "maximize":
        adj_quinz = [(0, 1), (1, 2), (2, 3)]
        for g in groups:
            for mat in ['Mathématiques', 'Physique', 'Anglais']:
                for p in set(sl['prof'] for sl in slots if sl['mat'] == mat):
                    for q1, q2 in adj_quinz:
                        Q1, Q2 = quinz[q1], quinz[q2]
                        model.Add(
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots)
                                if sl['mat'] == mat and sl['prof'] == p
                                for w in Q1) +
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots)
                                if sl['mat'] == mat and sl['prof'] == p
                                for w in Q2)
                            <= 1)

    # Contrainte 4: pas deux colles même jour+heure pour un groupe
    for g in groups:
        for w in weeks:
            for day in df['Jour'].unique():
                for hour in df['Heure'].unique():
                    model.Add(
                        sum(X.get((s, w, g), 0)
                            for s, sl in enumerate(slots)
                            if sl['day'] == day and sl['hour'] == hour) <= 1)

    # Contrainte 5: charge hebdo
    for g in groups:
        for w in weeks:
            if mode == "maximize":
                # En mode maximize, on accepte 0 colles par semaine
                model.Add(sum(X.get((s, w, g), 0) for s in range(len(slots))) <= 4)
            else:
                model.Add(sum(X.get((s, w, g), 0) for s in range(len(slots))) >= 1)
                model.Add(sum(X.get((s, w, g), 0) for s in range(len(slots))) <= 4)

    # Objectif en mode maximize
    if mode == "maximize":
        model.Maximize(sum(X.values()))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.Solve(model)

    print(f"[DEBUG] Status: {status}, Mode: {mode}")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, f"Aucune solution trouvée en mode {mode}"

    # Inject solution dans df
    for w in weeks:
        col = []
        for s in range(len(slots)):
            g_found = ''
            for g in groups:
                if (s, w, g) in X and solver.Value(X[s, w, g]) == 1:
                    g_found = str(g)
                    break
            col.append(g_found)
        df[str(w)] = col

    mode_msg = {
        "strict": "Planning généré avec toutes les contraintes strictes",
        "relaxed": "Planning généré avec contraintes relâchées (>= 1 au lieu de == 1)",
        "maximize": "Planning généré en mode sauvegarde (maximisation des colles possibles)"
    }

    return df, mode_msg.get(mode, f"Planning généré en mode {mode}")


# -----------------------
# Extension à 24 semaines (rotation par familles détectées)
# -----------------------
def _numeric_week_cols(df):
    return sorted([int(c) for c in df.columns if str(c).isdigit()])

def extend_to_24_weeks(df8_weeks_csv: str, original_csv: str) -> pd.DataFrame:
    """
    df8_weeks_csv: CSV du planning déjà généré (8 semaines)
    original_csv: CSV d'origine (pour détecter les familles)
    Retourne un DataFrame avec 24 semaines:
      - Bloc 1: semaines existantes (8)
      - Bloc 2: rotation +1 cran au sein de chaque famille
      - Bloc 3: rotation +2 crans au sein de chaque famille
    """
    df8 = pd.read_csv(io.StringIO(df8_weeks_csv), sep=';')
    df_orig = pd.read_csv(io.StringIO(original_csv), sep=';')

    families = detect_group_families(df_orig)  # ex: [[1..8], [9..16]]
    print(f"[INFO] Familles détectées pour rotation: {families}")

    week_cols = _numeric_week_cols(df8)
    if len(week_cols) < 8:
        raise ValueError("Le planning 8 semaines ne contient pas 8 colonnes de semaines numériques.")

    base_weeks_sorted = week_cols[:8]
    max_week = max(base_weeks_sorted)

    # On va créer 16 nouvelles colonnes après la dernière semaine existante
    # Bloc 2: +1 cran, Bloc 3: +2 crans
    for block_shift in [1, 2]:
        for idx, base_w in enumerate(base_weeks_sorted):
            new_week = max_week + (block_shift - 1) * 8 + (idx + 1)
            new_week_str = str(new_week)
            base_col = df8[str(base_w)].copy()

            # Appliquer la rotation famille par famille
            col_rot = base_col.copy()
            for fam in families:
                fam_sorted = list(sorted(fam))
                # mapping de remplacement pour ce shift
                mapping = {}
                size = len(fam_sorted)
                if size <= 1:
                    continue
                # Construire mapping str(g) -> str(rotated)
                for pos, g in enumerate(fam_sorted):
                    rotated = fam_sorted[(pos + block_shift) % size]
                    mapping[str(g)] = str(rotated)
                # appliquer mapping
                col_rot = col_rot.replace(mapping)

            df8[new_week_str] = col_rot
            
    for col in df8.columns:
        if str(col).isdigit():
            df8[col] = (
                df8[col]
                .apply(lambda v: str(int(float(v))) if str(v).replace('.', '', 1).isdigit() else ("" if pd.isna(v) else str(v)))
            )

    return df8


# -----------------------
# PlanningAnalyzer (inchangé)
# -----------------------
class PlanningAnalyzer:
    def __init__(self, csv_content):
        self.df = pd.read_csv(io.StringIO(csv_content), sep=';')
        self.weeks = [str(w) for w in _numeric_week_cols(self.df)]
        self.groups = extract_all_groups(self.df)
        self.quinzaines = [(38,39),(40,41),(42,43),(44,45)]
        self.mois = [(38,39,40,41),(42,43,44,45)]

    def is_group_match(self,val,groupe):
        if pd.isna(val): return False
        try: return int(float(val))==int(groupe)
        except: return False

    def compter_colles_groupe_semaine(self,g,semaine):
        if semaine not in self.df.columns: return 0
        return sum(1 for _,row in self.df.iterrows() if self.is_group_match(row[semaine],g))

    def stats_groupes(self):
        group_counts={g:0 for g in self.groups}
        for s in self.weeks:
            for _,row in self.df.iterrows():
                try:
                    v=int(float(row[s])) if not pd.isna(row[s]) else None
                    if v in group_counts: group_counts[v]+=1
                except: pass
        return group_counts

    def stats_matieres(self):
        mat_counts={m:0 for m in self.df['Matière'].unique()}
        for s in self.weeks:
            for _,row in self.df.iterrows():
                for g in self.groups:
                    if self.is_group_match(row[s],g): mat_counts[row['Matière']]+=1
        return mat_counts

    def stats_profs(self):
        prof_counts={p:0 for p in self.df['Prof'].unique()}
        for s in self.weeks:
            for _,row in self.df.iterrows():
                for g in self.groups:
                    if self.is_group_match(row[s],g): prof_counts[row['Prof']]+=1
        return prof_counts

    def charge_hebdo(self):
        return {g:[self.compter_colles_groupe_semaine(g,str(w)) for w in _numeric_week_cols(self.df)] for g in self.groups}

    def verifier_contraintes_groupe(self,g): return []
    def verifier_contraintes_globales(self): return []
    def statistiques_globales(self):
        total=len(self.df)*len(self.weeks)
        used=sum(1 for s in self.weeks for _,row in self.df.iterrows() for g in self.groups if self.is_group_match(row[s],g))
        return {"total_creneaux":total,"creneaux_utilises":used,"taux_utilisation":round(used/total*100,1) if total>0 else 0}


# -----------------------
# API ROUTES
# -----------------------
uploaded_csv, generated_planning = None, None

@app.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    global uploaded_csv
    content = await file.read()
    decoded=content.decode("utf-8")
    uploaded_csv=decoded
    reader=csv.reader(io.StringIO(decoded),delimiter=';')
    rows=list(reader)
    return {"header":rows[0],"preview":rows[1:6]}

@app.post("/api/generate_planning")
async def generate_planning():
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
async def analyse_planning():
    global generated_planning
    if not generated_planning: 
        return JSONResponse(status_code=400, content={"error":"Aucun planning généré."})
    
    analyzer=PlanningAnalyzer(generated_planning)
    return {
        "stats":{
            "groupes":analyzer.stats_groupes(),
            "matieres":analyzer.stats_matieres(),
            "profs":analyzer.stats_profs(),
            "charge_hebdo":analyzer.charge_hebdo(),
            "globales":analyzer.statistiques_globales()
        },
        "contraintes":{"groupes":{},"globales":[]}
    }

@app.get("/api/get_groups")
def get_groups():
    global generated_planning
    if not generated_planning: 
        return JSONResponse(status_code=400, content={"error":"Aucun planning généré."})
    
    analyzer=PlanningAnalyzer(generated_planning)
    return {"groups":analyzer.groups}

@app.get("/api/group_details/{groupe_id}")
def group_details(groupe_id: int):
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
            for _, row in analyzer.df.iterrows():
                if analyzer.is_group_match(row[s], groupe_id):
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
                for _, row in analyzer.df.iterrows():
                    if row["Matière"] == matiere and analyzer.is_group_match(row[s], groupe_id):
                        count += 1
            stats["colles_par_matiere"][matiere] = count

        return {"groupe": groupe_id, "creneaux": creneaux, "stats": stats}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur interne: {str(e)}"}
        )

@app.get("/api/download_planning")
def download_planning():
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    
    return StreamingResponse(
        io.StringIO(generated_planning),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=planning_optimise.csv"}
    )

@app.post("/api/extend_planning")
async def extend_planning():
    """
    Étend le planning 8 semaines actuel à 24 semaines par rotations internes
    aux familles de groupes détectées automatiquement à partir du CSV initial.
    """
    global uploaded_csv, generated_planning
    if not uploaded_csv or not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Générez d'abord un planning 8 semaines."})
    try:
        df24 = extend_to_24_weeks(generated_planning, uploaded_csv)
        out = io.StringIO()
        df24.to_csv(out, sep=';', index=False)
        csv_bytes = out.getvalue()
        return StreamingResponse(
            io.StringIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=planning_24_semaines.csv"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Extension impossible: {str(e)}"})

@app.get("/api/hello")
def hello(): 
    return {"message":"Backend Planning Colles avec OR-Tools (3 niveaux) + extension 24 semaines par rotation de familles"}