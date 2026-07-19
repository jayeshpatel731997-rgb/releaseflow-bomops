import argparse
from app.db.seed import SCENARIOS, seed_database
from app.db.session import SessionLocal
parser=argparse.ArgumentParser();parser.add_argument('scenario',choices=[s[0] for s in SCENARIOS]);args=parser.parse_args()
with SessionLocal() as db: seed_database(db)
print(next(case_id for key,case_id,*_ in SCENARIOS if key==args.scenario))
