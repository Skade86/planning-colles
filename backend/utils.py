def convert_form_to_csv(form_data):
    """
    Convertit les données du formulaire en format CSV équivalent
    """
    semaines = form_data.get('semaines', [])
    professeurs = form_data.get('professeurs', [])
    creneaux = form_data.get('creneaux', [])
    headers = [
        'Matière', 'Prof', 'Jour', 'Heure',
        'Groupes possibles semaine paire', 'Groupes possibles semaine impaire',
        'Travaille les semaines paires', 'Travaille les semaines impaires'
    ] + [str(s) for s in semaines]
    rows = []
    for creneau in creneaux:
        prof_info = None
        for prof in professeurs:
            if prof.get('nom') == creneau.get('professeur'):
                prof_info = prof
                break
        if not prof_info:
            continue
        groupes_paires = f"{creneau.get('groupesPaires', {}).get('min', 1)} à {creneau.get('groupesPaires', {}).get('max', 15)}"
        groupes_impaires = f"{creneau.get('groupesImpaires', {}).get('min', 1)} à {creneau.get('groupesImpaires', {}).get('max', 15)}"
        row = [
            creneau.get('matiere', ''),
            creneau.get('professeur', ''),
            creneau.get('jour', ''),
            creneau.get('heure', ''),
            groupes_paires,
            groupes_impaires,
            'Oui' if prof_info.get('travaillePaires', True) else 'Non',
            'Oui' if prof_info.get('travailleImpaires', True) else 'Non'
        ] + [''] * len(semaines)
        rows.append(row)
    csv_content = ';'.join(headers) + '\n'
    for row in rows:
        csv_content += ';'.join(str(cell) for cell in row) + '\n'
    return csv_content
import io
import pandas as pd

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
