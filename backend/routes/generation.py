from fastapi import APIRouter, UploadFile, File, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import io
import csv
import pandas as pd
from logic import generate_planning_with_ortools
from utils import export_excel_with_style, convert_form_to_csv
from users import UserInDB, get_current_user
import shared_state

router = APIRouter()

@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...), user: UserInDB = Depends(get_current_user)):
    content = await file.read()
    decoded = content.decode("utf-8")
    shared_state.uploaded_csv = decoded
    reader = csv.reader(io.StringIO(decoded), delimiter=';')
    rows = list(reader)
    return {"header": rows[0], "preview": rows[1:6]}

@router.post("/api/generate_planning")
async def generate_planning(user: UserInDB = Depends(get_current_user)):
    if not shared_state.uploaded_csv:
        return JSONResponse(status_code=400, content={"error": "Aucun fichier CSV uploadé."})
    
    print("[INFO] Tentative mode strict...")
    df_result, message = generate_planning_with_ortools(shared_state.uploaded_csv, mode="strict")
    if df_result is None:
        print("[INFO] Échec mode strict, tentative mode relaxed...")
        df_result, message = generate_planning_with_ortools(shared_state.uploaded_csv, mode="relaxed")
        if df_result is None:
            print("[INFO] Échec mode relaxed, tentative mode maximize...")
            df_result, message = generate_planning_with_ortools(shared_state.uploaded_csv, mode="maximize")
            if df_result is None:
                return JSONResponse(status_code=400, content={"error": "Impossible de générer un planning même en mode sauvegarde"})
    output = io.StringIO()
    df_result.to_csv(output, sep=';', index=False)
    shared_state.generated_planning = output.getvalue()
    return {
        "header": df_result.columns.tolist(),
        "rows": df_result.values.tolist(),
        "message": message
    }

@router.post("/api/generate_from_form")
async def generate_from_form(form_data: dict, user: UserInDB = Depends(get_current_user)):
    global generated_planning
    try:
        csv_content = convert_form_to_csv(form_data)
        print("[INFO] Tentative mode strict...")
        df_result, message = generate_planning_with_ortools(csv_content, mode="strict")
        if df_result is None:
            print("[INFO] Échec mode strict, tentative mode relaxed...")
            df_result, message = generate_planning_with_ortools(csv_content, mode="relaxed")
            if df_result is None:
                print("[INFO] Échec mode relaxed, tentative mode maximize...")
                df_result, message = generate_planning_with_ortools(csv_content, mode="maximize")
                if df_result is None:
                    return JSONResponse(status_code=400, content={"error": "Impossible de générer un planning avec les contraintes données"})
        output = io.StringIO()
        df_result.to_csv(output, sep=';', index=False)
        shared_state.generated_planning = output.getvalue()
        return {
            "header": df_result.columns.tolist(),
            "rows": df_result.values.tolist(),
            "message": message + " (généré depuis le formulaire)"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Erreur lors de la génération: {str(e)}"})

@router.get("/api/download_planning")
async def download_planning(format: str = Query("csv", enum=["csv", "excel"]), user: UserInDB = Depends(get_current_user)):
    if not shared_state.generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    df = pd.read_csv(io.StringIO(shared_state.generated_planning), sep=';')
    if format == "excel":
        out = export_excel_with_style(df)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=planning_optimise.xlsx"}
        )
    else:
        return StreamingResponse(
            io.StringIO(shared_state.generated_planning),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=planning_optimise.csv"}
        )

@router.get("/api/get_groups")
def get_groups(user: UserInDB = Depends(get_current_user)):
    if not shared_state.generated_planning:
        return JSONResponse(status_code=400, content={"error": "Aucun planning généré."})
    from main import PlanningAnalyzer
    analyzer = PlanningAnalyzer(shared_state.generated_planning)
    return {"groups": analyzer.groups}
