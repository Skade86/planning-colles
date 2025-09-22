
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
import pandas as pd
from datetime import datetime, timezone
from bson import ObjectId
from db import get_db
from users import UserInDB, get_current_user, get_password_hash
from utils import export_excel_with_style

router = APIRouter()


def _safe_object_id(oid: str) -> ObjectId:
	try:
		return ObjectId(oid)
	except Exception:
		raise HTTPException(status_code=400, detail="Identifiant invalide")


@router.post("/api/plannings/save")
async def save_planning(
	name: str = Query(None),
	user: UserInDB = Depends(get_current_user)
):
	from ..main import generated_planning
	db = get_db()
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
	return {
		"id": str(res.inserted_id),
		"name": doc["name"],
		"created_at": doc["created_at"].isoformat()
	}


@router.get("/api/plannings")
async def list_plannings(
	user: UserInDB = Depends(get_current_user)
):
	db = get_db()
	if db is None:
		return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
	user_doc = db.users.find_one({"email": user.email})
	if not user_doc:
		return JSONResponse(status_code=404, content={"error": "Utilisateur introuvable"})
	user_classes = set(user_doc.get("classes", []))
	user_lycee = user_doc.get("lycee", "")
	allowed_users = set()
	for u in db.users.find({"lycee": user_lycee}):
		classes = set(u.get("classes", []))
		if user_classes & classes:
			allowed_users.add(u["email"])
	cursor = db.plannings.find(
		{"user": {"$in": list(allowed_users)}},
		{"csv_content": 0}
	).sort("created_at", -1)
	items = []
	for d in cursor:
		items.append({
			"id": str(d["_id"]),
			"name": d.get("name", "Planning"),
			"user": d.get("user", ""),
			"created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
		})
	return {"items": items}


@router.get("/api/plannings/{planning_id}")
async def get_planning(
	planning_id: str,
	user: UserInDB = Depends(get_current_user)
):
	db = get_db()
	if db is None:
		return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
	d = db.plannings.find_one({"_id": _safe_object_id(planning_id)})
	if not d:
		return JSONResponse(status_code=404, content={"error": "Planning introuvable"})
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
	return {
		"id": planning_id,
		"name": d.get("name"),
		"header": df.columns.tolist(),
		"rows": df.values.tolist()
	}


@router.get("/api/plannings/{planning_id}/download")
async def download_saved_planning(
	planning_id: str,
	format: str = Query("csv", enum=["csv", "excel"]),
	user: UserInDB = Depends(get_current_user)
):
	db = get_db()
	if db is None:
		return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
	d = db.plannings.find_one({"_id": _safe_object_id(planning_id)})
	if not d:
		return JSONResponse(status_code=404, content={"error": "Planning introuvable"})
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
