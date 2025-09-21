from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient
from datetime import datetime, timezone

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB")

mongo_client = MongoClient(MONGODB_URI) if MONGODB_URI else None
db = mongo_client[MONGODB_DB] if mongo_client and MONGODB_DB else None

def ensure_demo_users(get_password_hash):
    """Ensure demo users and indexes exist. get_password_hash should be passed from main to avoid import cycle."""
    if db is None:
        return
    db.users.create_index("email", unique=True)
    now = datetime.now(timezone.utc)
    if db.users.count_documents({"email": "admin@demo.fr"}) == 0:
        db.users.insert_one({
            "email": "admin@demo.fr",
            "nom": "Admin",
            "role": "professeur",
            "hashed_password": get_password_hash("admin"),
            "created_at": now,
            "classes": ['PSIE'],
            'lycee': 'Lycée Camille Guérin'
        })
    if db.users.count_documents({"email": "user@demo.fr"}) == 0:
        db.users.insert_one({
            "email": "user@demo.fr",
            "nom": "Utilisateur",
            "role": "utilisateur",
            "hashed_password": get_password_hash("user"),
            "created_at": now,
            "classes": ['PSIE'],
            'lycee': 'Lycée Camille Guérin'
        })

