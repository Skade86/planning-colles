from fastapi import FastAPI, UploadFile, File, Query
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
            
    # Corriger les numéros de groupes : forcer en entiers ou vide
    for col in df8.columns:
        if str(col).isdigit():
            df8[col] = (
                df8[col]
                .apply(lambda v: str(int(float(v))) if str(v).replace('.', '', 1).isdigit() else ("" if pd.isna(v) else str(v)))
            )

    return df8

def adjust_late_slots(df):
    """
    Corrige les cas où un prof a deux créneaux consécutifs (même jour)
    avec un seul rempli. Si possible, on vide toujours le créneau le plus tardif
    pour que le colleur termine plus tôt.
    
    CORRECTION: Vérifie maintenant les contraintes paire/impaire avant déplacement.
    """
    week_cols = [c for c in df.columns if str(c).isdigit()]

    # Pour chaque prof et chaque jour de la semaine
    for prof in df['Prof'].unique():
        for day in df['Jour'].unique():
            # Extraire les créneaux de ce prof à ce jour
            subset = df[(df['Prof'] == prof) & (df['Jour'] == day)].copy()

            # Trier dans l'ordre des heures (important pour détecter "avant / après")
            subset = subset.sort_values('Heure')

            row_indices = list(subset.index)

            # Parcourir semaine par semaine
            for w in week_cols:
                prev_idx = None
                for idx in row_indices:
                    g = str(df.at[idx, w]) if not pd.isna(df.at[idx, w]) and str(df.at[idx, w]).strip() != "" else ""

                    if prev_idx is not None:
                        prev_g = str(df.at[prev_idx, w]) if not pd.isna(df.at[prev_idx, w]) and str(df.at[prev_idx, w]).strip() != "" else ""

                        # Cas : groupe uniquement sur le créneau tardif
                        if g != "" and prev_g == "":
                            try:
                                group_id = int(g)  # Convertir en int pour les vérifications
                            except ValueError:
                                continue  # Ignorer si pas un nombre valide

                            # Vérifier qu'il n'y a pas déjà une colle pour ce groupe à l'heure précédente dans df
                            jour_prev = df.at[prev_idx, 'Jour']
                            heure_prev = df.at[prev_idx, 'Heure']

                            conflict = False
                            for _, row in df[df['Jour'] == jour_prev].iterrows():
                                if str(row[w]).strip() == str(group_id) and row['Heure'] == heure_prev:
                                    conflict = True
                                    break

                            # ✅ NOUVELLE VÉRIFICATION : contraintes paire/impaire
                            if not conflict:
                                try:
                                    week_num = int(w)
                                    prev_row = df.iloc[prev_idx]
                                    
                                    if week_num % 2 == 0:  # Semaine paire
                                        allowed_groups = parse_groups(prev_row['Groupes possibles semaine paire'])
                                    else:  # Semaine impaire
                                        allowed_groups = parse_groups(prev_row['Groupes possibles semaine impaire'])
                                    
                                    # Vérifier si le groupe est autorisé dans le créneau précédent
                                    if group_id not in allowed_groups:
                                        conflict = True  # Empêcher le déplacement
                                        print(f"[DEBUG] Déplacement bloqué: Groupe {group_id} non autorisé en semaine {week_num} ({'paire' if week_num % 2 == 0 else 'impaire'}) pour {prev_row['Prof']} {prev_row['Jour']} {prev_row['Heure']}")
                                
                                except (ValueError, KeyError):
                                    conflict = True  # En cas d'erreur, ne pas déplacer

                            # Si pas de conflit → décaler le groupe au créneau précédent
                            if not conflict:
                                df.at[prev_idx, w] = group_id
                                df.at[idx, w] = ""
                                print(f"[DEBUG] Déplacement OK: Groupe {group_id} déplacé vers {prev_row['Prof']} {prev_row['Jour']} {prev_row['Heure']} semaine {w}")

                    prev_idx = idx
    return df

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

        # Semaines dynamiques (colonnes numériques)
        self.weeks = [int(c) for c in self.df.columns if str(c).isdigit()]
        self.weeks.sort()
        self.groups = list(range(1, 16))  # 15 groupes

        # Fenêtres dynamiques NON CHEVAUCHANTES (comme OR-Tools)
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

        # Français → 1 par 8 semaines
        for bloc in self.groups_8:
            count = sum(
                sum(1 for colle in group_weeks.get(w, []) if colle[0] == "Français")
                for w in bloc
            )
            if count != 1:
                erreurs.append(f"Français - Bloc {bloc}: {count} colles (attendu: 1)")

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
        total_slots = len(self.df) * len(self.weeks)
        used = 0
        for w in [str(w) for w in self.weeks]:
            for v in self.df[w]:
                try:
                    int(v)
                    used += 1
                except (ValueError, TypeError):
                    continue
        taux = round((used/total_slots)*100, 1) if total_slots else 0
        return {"total_creneaux": total_slots, "creneaux_utilises": used, "taux_utilisation": taux}

    # -------------------- WRAPPER --------------------
    def contraintes(self):
        return {
            "globales": self.verifier_contraintes_globales(),
            "groupes": {g: self.verifier_contraintes_groupe(g) for g in self.groups},
            "consecutives": self.verifier_colles_consecutives()
        }

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
async def analyse_planning(file: UploadFile = File(...)):
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
            "total_erreurs": len(contraintes["globales"]) + sum(len(v) for v in contraintes["groupes"].values()) + len(contraintes["consecutives"]),
            "globales_ok": len(contraintes["globales"]) == 0,
            "groupes_ok": all(len(v) == 0 for v in contraintes["groupes"].values()),
            "consecutives_ok": len(contraintes["consecutives"]) == 0,
        }

        return {
            "resume": resume,
            "stats": stats,
            "contraintes": contraintes
        }

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

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
async def download_planning(format: str = Query("csv", enum=["csv", "excel"])):
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

@app.post("/api/extend_planning")
async def extend_planning(format: str = Query("csv", enum=["csv", "excel"])):
    """
    Étend le planning 8 semaines actuel à 24 semaines par rotations internes
    aux familles de groupes détectées automatiquement à partir du CSV initial.
    Le résultat est renvoyé soit en CSV (par défaut), soit en Excel si ?format=excel
    """
    global uploaded_csv, generated_planning
    if not uploaded_csv or not generated_planning:
        return JSONResponse(status_code=400, content={"error": "Générez d'abord un planning 8 semaines."})
    
    try:
        df24 = extend_to_24_weeks(generated_planning, uploaded_csv)
        
        if format == "excel":
            out = io.BytesIO()
            out = export_excel_with_style(df24)
            out.seek(0)
            return StreamingResponse(
                out,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=planning_24_semaines.xlsx"}
            )
        else:  # CSV par défaut
            out = io.StringIO()
            df24.to_csv(out, sep=';', index=False)
            return StreamingResponse(
                io.StringIO(out.getvalue()),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=planning_24_semaines.csv"}
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Extension impossible: {str(e)}"})

@app.get("/api/hello")
def hello(): 
    return {"message":"Backend Planning Colles avec OR-Tools (semaines dynamiques) + extension 24 semaines par rotation de familles"}