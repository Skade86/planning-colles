import os
from dotenv import load_dotenv
from pymongo import MongoClient
from typing import Optional

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB")

_mongo_client: Optional[MongoClient] = None
_db = None

def init_db():
    global _mongo_client, _db
    if _mongo_client is None or _db is None:
        _mongo_client = MongoClient(MONGODB_URI)
        _db = _mongo_client[MONGODB_DB]
        _db.users.create_index("email", unique=True)
    return _db

def get_db():
    """Toujours retourner une instance de la base initialisée."""
    return init_db()
