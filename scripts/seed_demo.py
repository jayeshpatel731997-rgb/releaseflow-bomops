from app.db.seed import seed_database
from app.db.session import SessionLocal
with SessionLocal() as db: print(seed_database(db))
