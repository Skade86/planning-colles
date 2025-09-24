import io
import pandas as pd
from ortools.sat.python import cp_model

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

def extract_week_columns(df):
    weeks_str = []
    for c in df.columns:
        if isinstance(c, str) and c.strip().isdigit():
            weeks_str.append(c.strip())
    weeks_int = [int(w) for w in weeks_str]
    return weeks_str, weeks_int

def make_windows_non_overlapping(weeks_list, size):
    windows = []
    for i in range(0, len(weeks_list), size):
        chunk = weeks_list[i:i+size]
        if len(chunk) == size:
            windows.append(tuple(chunk))
    return windows

def parse_hhmm_range_to_minutes(hhmm_range):
    deb, fin = [p.strip() for p in str(hhmm_range).split('-')]
    def h2m(p):
        parts = str(p).split('h')
        h = int(parts[0]) if parts[0] else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        return h * 60 + m
    return h2m(deb), h2m(fin)

def generate_planning_with_ortools(csv_content, mode="strict", regles_alternance=None):
    df = pd.read_csv(io.StringIO(csv_content), sep=';')
    df['Jour'] = df['Jour'].astype(str).str.strip()
    df['Heure'] = (
        df['Heure'].astype(str)
        .str.replace(' ', '', regex=False)
        .str.strip()
    )
    groups = extract_all_groups(df)
    if not groups:
        return None, "Aucun groupe détecté dans le CSV"
    weeks_str, weeks_int = extract_week_columns(df)
    if not weeks_str:
        return None, "Aucune colonne de semaine détectée dans le CSV"
    quinz = make_windows_non_overlapping(weeks_str, 2)
    mois = make_windows_non_overlapping(weeks_str, 4)
    eight_week_blocks = make_windows_non_overlapping(weeks_str, 8)
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
    for s, slot in enumerate(slots):
        for w_str, w_int in zip(weeks_str, weeks_int):
            for g in groups:
                if (w_int % 2 == 0 and (g not in slot['even'] or not slot['works_even'])) or \
                   (w_int % 2 == 1 and (g not in slot['odd'] or not slot['works_odd'])):
                    continue
                X[s, w_str, g] = model.NewBoolVar(f"x_{s}_{w_str}_{g}")
    for s in range(len(slots)):
        for w_str in weeks_str:
            model.Add(sum(X.get((s, w_str, g), 0) for g in groups) <= 1)
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
    # Règles d'alternance par défaut si non fournies
    if regles_alternance is None:
        print("[DEBUG] Utilisation des règles par défaut")
        regles_alternance = {
            'Mathématiques': {'active': True, 'frequence': 2},
            'Physique': {'active': True, 'frequence': 2},
            'Anglais': {'active': True, 'frequence': 2},
            'Chimie': {'active': True, 'frequence': 4},
            'S.I': {'active': True, 'frequence': 4},
            'Français': {'active': True, 'frequence': 8}
        }
    else:
        print(f"[DEBUG] Utilisation des règles personnalisées: {regles_alternance}")
    
    # Application des contraintes d'alternance dynamiques
    if mode != "maximize":
        for g in groups:
            # Obtenir toutes les matières présentes dans les créneaux
            matieres_presentes = {sl['mat'] for sl in slots}
            
            for matiere in matieres_presentes:
                regle = regles_alternance.get(matiere)
                if not regle or not regle.get('active', True):
                    print(f"[DEBUG] Matière {matiere} désactivée ou pas de règle")
                    continue  # Ignorer les matières désactivées
                
                frequence = regle.get('frequence', 2)
                print(f"[DEBUG] Application règle pour {matiere}: fréquence={frequence}")
                
                # Créer les blocs selon la fréquence
                if frequence == 1:
                    # Chaque semaine - une colle par groupe par semaine
                    print(f"[DEBUG] {matiere}: Contrainte 1 colle/groupe/semaine")
                    for g in groups:
                        for w_str in weeks_str:
                            constraint_sum = sum(
                                X.get((s, w_str, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == matiere
                            )
                            if mode == "strict":
                                model.Add(constraint_sum == 1)
                            else:
                                model.Add(constraint_sum >= 1)
                elif frequence == 2:
                    # Quinzaines
                    print(f"[DEBUG] {matiere}: Contrainte 1 colle/groupe/quinzaine")
                    for g in groups:
                        for q in quinz:
                            constraint_sum = sum(
                                X.get((s, w, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == matiere
                                for w in q
                            )
                            if mode == "strict":
                                model.Add(constraint_sum == 1)
                            else:
                                model.Add(constraint_sum >= 1)
                elif frequence == 4:
                    # Blocs de 4 semaines
                    print(f"[DEBUG] {matiere}: Contrainte 1 colle/groupe/4semaines")
                    for g in groups:
                        for m in mois:
                            constraint_sum = sum(
                                X.get((s, w, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == matiere
                                for w in m
                            )
                            if mode == "strict":
                                model.Add(constraint_sum == 1)
                            else:
                                model.Add(constraint_sum >= 1)
                elif frequence == 8:
                    # Blocs de 8 semaines
                    print(f"[DEBUG] {matiere}: Contrainte 1 colle/groupe/8semaines")
                    for g in groups:
                        for block in eight_week_blocks:
                            constraint_sum = sum(
                                X.get((s, w, g), 0)
                                for s, sl in enumerate(slots) if sl['mat'] == matiere
                                for w in block
                            )
                            if mode == "strict":
                                model.Add(constraint_sum == 1)
                            else:
                                model.Add(constraint_sum >= 1)
    # Contrainte d'alternance des professeurs (pour les matières avec fréquence quinzaine)
    if mode != "maximize":
        if len(quinz) >= 2:
            for g in groups:
                # Obtenir toutes les matières présentes dans les créneaux
                matieres_presentes = {sl['mat'] for sl in slots}
                
                for matiere in matieres_presentes:
                    regle = regles_alternance.get(matiere)
                    if not regle or not regle.get('active', True):
                        continue
                    
                    # Appliquer l'alternance seulement pour les matières en quinzaine
                    if regle.get('frequence', 2) == 2:
                        profs_mat = sorted({sl['prof'] for sl in slots if sl['mat'] == matiere})
                        for p in profs_mat:
                            for i in range(len(quinz) - 1):
                                Q1, Q2 = quinz[i], quinz[i + 1]
                                model.Add(
                                    sum(
                                        X.get((s, w, g), 0)
                                        for s, sl in enumerate(slots) if sl['mat'] == matiere and sl['prof'] == p
                                        for w in Q1
                                    )
                                    +
                                    sum(
                                        X.get((s, w, g), 0)
                                        for s, sl in enumerate(slots) if sl['mat'] == matiere and sl['prof'] == p
                                        for w in Q2
                                    )
                                    <= 1
                                )
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
    for g in groups:
        for w_str in weeks_str:
            if mode == "maximize":
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) <= 4)
            else:
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) >= 1)
                model.Add(sum(X.get((s, w_str, g), 0) for s in range(len(slots))) <= 4)
    for g in groups:
        for w_str in weeks_str:
            for day in df['Jour'].unique():
                slots_day = [(s, sl) for s, sl in enumerate(slots) if sl['day'] == day]
                slots_day.sort(key=lambda x: parse_hhmm_range_to_minutes(x[1]['hour'])[0])
                for i in range(len(slots_day) - 1):
                    s1, sl1 = slots_day[i]
                    s2, sl2 = slots_day[i + 1]
                    _, end1 = parse_hhmm_range_to_minutes(sl1['hour'])
                    start2, _ = parse_hhmm_range_to_minutes(sl2['hour'])
                    if end1 == start2:
                        model.Add(X.get((s1, w_str, g), 0) + X.get((s2, w_str, g), 0) <= 1)
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
    if mode == "maximize":
        model.Maximize(sum(X.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, f"Aucune solution trouvée en mode {mode}"
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
    return df, mode_msg.get(mode, f"Planning généré en mode {mode}")
