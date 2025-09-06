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

uploaded_csv = None
generated_planning = None

def parse_groups(txt):
    if pd.isna(txt) or txt == '':
        return []
    if 'à' in txt:
        a, b = txt.split('à')
        return list(range(int(a.strip()), int(b.strip()) + 1))
    return [int(txt.strip())]

class PlanningAnalyzer:
    def __init__(self, csv_content):
        self.df = pd.read_csv(io.StringIO(csv_content), sep=';')
        self.df.columns = [c.strip() for c in self.df.columns]
        self.weeks = [str(w) for w in range(38, 46)]
        self.groups = list(range(1, 17))
        self.quinzaines = [(38, 39), (40, 41), (42, 43), (44, 45)]
        self.mois = [(38, 39, 40, 41), (42, 43, 44, 45)]

    def compter_colles_groupe_semaine(self, groupe, semaine):
        if semaine not in self.df.columns:
            return 0
        count = 0
        for _, row in self.df.iterrows():
            val = row[semaine]
            if pd.notna(val):
                try:
                    if int(float(str(val).strip())) == groupe:
                        count += 1
                except Exception:
                    pass
        return count

    def lister_creneaux_groupe_quinzaine_matiere(self, groupe, quinzaine_idx, matiere):
        if quinzaine_idx < 0 or quinzaine_idx >= len(self.quinzaines):
            return []
        semaine1, semaine2 = self.quinzaines[quinzaine_idx]
        creneaux = []
        for _, row in self.df.iterrows():
            if row['Matière'] == matiere:
                for semaine in [str(semaine1), str(semaine2)]:
                    val = row[semaine]
                    if pd.notna(val):
                        try:
                            if int(float(str(val).strip())) == groupe:
                                creneaux.append((semaine, row['Prof'], row['Jour'], row['Heure']))
                        except Exception:
                            pass
        return creneaux

    def stats_groupes(self):
        group_counts = {g: 0 for g in self.groups}
        for semaine in self.weeks:
            for _, row in self.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        g = int(float(str(val).strip()))
                        if g in group_counts:
                            group_counts[g] += 1
                    except Exception:
                        pass
        return group_counts

    def stats_matieres(self):
        mat_counts = {mat: 0 for mat in self.df['Matière'].unique()}
        for semaine in self.weeks:
            for _, row in self.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        int(float(str(val).strip()))
                        mat_counts[row['Matière']] += 1
                    except Exception:
                        pass
        return mat_counts

    def stats_profs(self):
        prof_counts = {prof: 0 for prof in self.df['Prof'].unique()}
        for semaine in self.weeks:
            for _, row in self.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        int(float(str(val).strip()))
                        prof_counts[row['Prof']] += 1
                    except Exception:
                        pass
        return prof_counts

    def charge_hebdo(self):
        charge = {}
        for g in self.groups:
            charge[g] = []
            for semaine in self.weeks:
                count = self.compter_colles_groupe_semaine(g, semaine)
                charge[g].append(count)
        return charge

    def verifier_contraintes_groupe(self, groupe):
        erreurs = []
        # 1. Vérifier fréquences par matière
        for matiere in ['Mathématiques', 'Physique', 'Anglais']:
            for q_idx, (s1, s2) in enumerate(self.quinzaines):
                creneaux = self.lister_creneaux_groupe_quinzaine_matiere(groupe, q_idx, matiere)
                if len(creneaux) != 1:
                    erreurs.append(f"{matiere} - Quinzaine {q_idx+1}: {len(creneaux)} colle(s) au lieu de 1")
        for matiere in ['Chimie', 'S.I']:
            for m_idx, semaines_mois in enumerate(self.mois):
                count = 0
                for semaine in semaines_mois:
                    for _, row in self.df.iterrows():
                        if row['Matière'] == matiere:
                            val = row[str(semaine)]
                            if pd.notna(val):
                                try:
                                    if int(float(str(val).strip())) == groupe:
                                        count += 1
                                except Exception:
                                    pass
                if count != 1:
                    erreurs.append(f"{matiere} - Mois {m_idx+1}: {count} colle(s) au lieu de 1")
        count_francais = 0
        for semaine in self.weeks:
            for _, row in self.df.iterrows():
                if row['Matière'] == 'Français':
                    val = row[semaine]
                    if pd.notna(val):
                        try:
                            if int(float(str(val).strip())) == groupe:
                                count_francais += 1
                        except Exception:
                            pass
        if count_francais != 1:
            erreurs.append(f"Français - Semestre: {count_francais} colle(s) au lieu de 1")
        # 2. Vérifier rotation des profs
        for matiere in ['Mathématiques', 'Physique', 'Anglais']:
            profs_par_quinzaine = []
            for q_idx in range(len(self.quinzaines)):
                creneaux = self.lister_creneaux_groupe_quinzaine_matiere(groupe, q_idx, matiere)
                profs = [c[1] for c in creneaux]
                profs_par_quinzaine.append(profs)
            for q_idx in range(len(profs_par_quinzaine) - 1):
                profs_q1 = set(profs_par_quinzaine[q_idx])
                profs_q2 = set(profs_par_quinzaine[q_idx + 1])
                intersection = profs_q1.intersection(profs_q2)
                if intersection:
                    erreurs.append(f"{matiere}: Prof(s) {list(intersection)} dans quinzaines consécutives {q_idx+1} et {q_idx+2}")
        # 3. Vérifier charge hebdomadaire
        for semaine in self.weeks:
            nb_colles = self.compter_colles_groupe_semaine(groupe, semaine)
            if not (1 <= nb_colles <= 4):
                erreurs.append(f"Semaine {semaine}: {nb_colles} colle(s) (doit être entre 1 et 4)")
        return erreurs

    def verifier_contraintes_globales(self):
        erreurs = []
        # Prof pas 2 groupes en même temps
        for semaine in self.weeks:
            prof_creneaux = defaultdict(list)
            for _, row in self.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        groupe = int(float(str(val).strip()))
                        key = (row['Prof'], row['Jour'], row['Heure'])
                        prof_creneaux[key].append(groupe)
                    except Exception:
                        pass
            for (prof, jour, heure), groupes in prof_creneaux.items():
                if len(groupes) > 1:
                    erreurs.append(f"Semaine {semaine}: {prof} a les groupes {groupes} en même temps ({jour} {heure})")
        # Groupe pas 2 colles en même temps
        for groupe in self.groups:
            for semaine in self.weeks:
                creneaux_groupe = []
                for _, row in self.df.iterrows():
                    val = row[semaine]
                    if pd.notna(val):
                        try:
                            if int(float(str(val).strip())) == groupe:
                                creneaux_groupe.append((row['Jour'], row['Heure']))
                        except Exception:
                            pass
                if len(creneaux_groupe) != len(set(creneaux_groupe)):
                    doublons = [c for c in set(creneaux_groupe) if creneaux_groupe.count(c) > 1]
                    erreurs.append(f"Groupe {groupe}, Semaine {semaine}: créneaux en double {doublons}")
        return erreurs

    def statistiques_globales(self):
        total_creneaux = len(self.df) * len(self.weeks)
        creneaux_utilises = 0
        for semaine in self.weeks:
            for _, row in self.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        int(float(str(val).strip()))
                        creneaux_utilises += 1
                    except Exception:
                        pass
        return {
            "total_creneaux": total_creneaux,
            "creneaux_utilises": creneaux_utilises,
            "taux_utilisation": round(creneaux_utilises/total_creneaux*100, 1) if total_creneaux > 0 else 0
        }

def generate_planning_with_ortools(csv_content):
    try:
        df = pd.read_csv(io.StringIO(csv_content), sep=';')
        slots = []
        for i, row in df.iterrows():
            slots.append(dict(
                id=i,
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
        groups = list(range(1, 17))
        model = cp_model.CpModel()
        X = {}
        for s, slot in enumerate(slots):
            for w in weeks:
                for g in groups:
                    if (w % 2 == 0 and (g not in slot['even'] or not slot['works_even'])) or \
                       (w % 2 == 1 and (g not in slot['odd'] or not slot['works_odd'])):
                        continue
                    X[s, w, g] = model.NewBoolVar(f"x_{s}_{w}_{g}")
        for s in range(len(slots)):
            for w in weeks:
                model.Add(sum(X.get((s, w, g), 0) for g in groups) <= 1)
        quinz = [(38, 39), (40, 41), (42, 43), (44, 45)]
        mois = [(38, 39, 40, 41), (42, 43, 44, 45)]
        for g in groups:
            for mat in ['Mathématiques', 'Physique', 'Anglais']:
                for q in quinz:
                    model.Add(
                        sum(X.get((s, w, g), 0)
                            for s, sl in enumerate(slots) if sl['mat'] == mat
                            for w in q) == 1)
            for mat in ['Chimie', 'S.I']:
                for m in mois:
                    model.Add(
                        sum(X.get((s, w, g), 0)
                            for s, sl in enumerate(slots) if sl['mat'] == mat
                            for w in m) == 1)
            model.Add(
                sum(X.get((s, w, g), 0)
                    for s, sl in enumerate(slots) if sl['mat'] == 'Français'
                    for w in weeks) == 1)
        adj_quinz = [(0, 1), (1, 2), (2, 3)]
        for g in groups:
            for mat in ['Mathématiques', 'Physique', 'Anglais']:
                for p in set(sl['prof'] for sl in slots if sl['mat'] == mat):
                    for q1, q2 in adj_quinz:
                        Q1, Q2 = quinz[q1], quinz[q2]
                        model.Add(
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == mat and sl['prof'] == p
                                for w in Q1) +
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == mat and sl['prof'] == p
                                for w in Q2)
                            <= 1)
        for g in groups:
            for w in weeks:
                for day in df['Jour'].unique():
                    for hour in df['Heure'].unique():
                        model.Add(
                            sum(X.get((s, w, g), 0)
                                for s, sl in enumerate(slots)
                                if sl['day'] == day and sl['hour'] == hour) <= 1)
        for g in groups:
            for w in weeks:
                model.Add(sum(X.get((s, w, g), 0) for s in range(len(slots))) >= 1)
                model.Add(sum(X.get((s, w, g), 0) for s in range(len(slots))) <= 4)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
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
            return df, "Planning généré avec succès"
        else:
            return None, "Aucune solution trouvée (contraintes trop strictes)"
    except Exception as e:
        return None, f"Erreur lors de la génération: {str(e)}"

@app.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    global uploaded_csv
    content = await file.read()
    decoded = content.decode("utf-8")
    uploaded_csv = decoded
    reader = csv.reader(io.StringIO(decoded), delimiter=';')
    rows = list(reader)
    return {"header": rows[0], "preview": rows[1:6]}

@app.post("/api/generate_planning")
async def generate_planning():
    global uploaded_csv, generated_planning
    if not uploaded_csv:
        return JSONResponse(status_code=400, content={"error": "Aucun fichier CSV uploadé."})
    df_result, message = generate_planning_with_ortools(uploaded_csv)
    if df_result is None:
        return JSONResponse(status_code=400, content={"error": message})
    output = io.StringIO()
    df_result.to_csv(output, sep=';', index=False)
    generated_planning = output.getvalue()
    rows = df_result.values.tolist()
    header = df_result.columns.tolist()
    return {
        "header": header,
        "rows": rows,
        "message": message
    }

@app.post("/api/analyse_planning")
async def analyse_planning():
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    try:
        analyzer = PlanningAnalyzer(generated_planning)
        contraintes_groupes = {}
        for groupe in range(1, 17):
            contraintes_groupes[groupe] = analyzer.verifier_contraintes_groupe(groupe)
        contraintes_globales = analyzer.verifier_contraintes_globales()
        return {
            "stats": {
                "groupes": analyzer.stats_groupes(),
                "matieres": analyzer.stats_matieres(),
                "profs": analyzer.stats_profs(),
                "charge_hebdo": analyzer.charge_hebdo(),
                "globales": analyzer.statistiques_globales()
            },
            "contraintes": {
                "groupes": contraintes_groupes,
                "globales": contraintes_globales
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Erreur lors de l'analyse: {str(e)}"})

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

@app.get("/api/groupe_details/{groupe_id}")
def groupe_details(groupe_id: int):
    global generated_planning
    if not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    try:
        analyzer = PlanningAnalyzer(generated_planning)
        details = {}
        # Liste des créneaux pour ce groupe
        creneaux = []
        for semaine in analyzer.weeks:
            for _, row in analyzer.df.iterrows():
                val = row[semaine]
                if pd.notna(val):
                    try:
                        if int(float(str(val).strip())) == groupe_id:
                            creneaux.append({
                                "semaine": semaine,
                                "matiere": row["Matière"],
                                "prof": row["Prof"],
                                "jour": row["Jour"],
                                "heure": row["Heure"]
                            })
                    except Exception:
                        pass
        # Colles par matière
        matieres = {}
        for mat in analyzer.df['Matière'].unique():
            matieres[mat] = []
            for semaine in analyzer.weeks:
                for _, row in analyzer.df.iterrows():
                    if row["Matière"] == mat:
                        val = row[semaine]
                        if pd.notna(val):
                            try:
                                if int(float(str(val).strip())) == groupe_id:
                                    matieres[mat].append({
                                        "semaine": semaine,
                                        "prof": row["Prof"],
                                        "jour": row["Jour"],
                                        "heure": row["Heure"]
                                    })
                            except Exception:
                                pass
        # Contraintes pour ce groupe
        contraintes = analyzer.verifier_contraintes_groupe(groupe_id)
        details["creneaux"] = creneaux
        details["colles_par_matiere"] = matieres
        details["contraintes"] = contraintes
        return details
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Erreur lors de l'analyse: {str(e)}"})

@app.get("/api/hello")
def hello():
    return {"message": "Backend Planning Colles avec OR-Tools et Analyse"}