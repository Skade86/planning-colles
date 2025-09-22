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
