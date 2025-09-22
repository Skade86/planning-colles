from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, Literal
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from db import get_db
import os

# -----------------------
# Modèles utilisateurs
# -----------------------
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

class UserProfile(BaseModel):
    email: Optional[str] = None
    nom: Optional[str] = None
    classes: Optional[list[str]] = None
    lycee: Optional[str] = None

# -----------------------
# Auth utils
# -----------------------
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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
    db = get_db()
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
# Router utilisateurs
# -----------------------
router = APIRouter()

@router.post("/api/auth/signup", response_model=User)
async def signup(req: SignupRequest):
    db = get_db()
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

@router.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user.email, "role": user.role})
    return Token(access_token=access_token)

@router.get("/api/users/me")
async def get_me(user: UserInDB = Depends(get_current_user)):
    db = get_db()
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

@router.put("/api/users/me")
async def update_me(payload: UserProfile, user: UserInDB = Depends(get_current_user)):
    db = get_db()
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    update_doc = {k: v for k, v in payload.dict().items() if v is not None}
    if not update_doc:
        return {"updated": False}
    db.users.update_one({"email": user.email}, {"$set": update_doc})
    return {"updated": True}

class PasswordChangeRequest(BaseModel):
    password: str

@router.put("/api/users/me/password")
async def change_password(payload: PasswordChangeRequest, user: UserInDB = Depends(get_current_user)):
    db = get_db()
    if db is None:
        return JSONResponse(status_code=500, content={"error": "Base de données non initialisée"})
    if not payload.password or len(payload.password) < 4:
        return JSONResponse(status_code=400, content={"error": "Mot de passe trop court"})
    db.users.update_one({"email": user.email}, {"$set": {"hashed_password": get_password_hash(payload.password)}})
    return {"updated": True}
