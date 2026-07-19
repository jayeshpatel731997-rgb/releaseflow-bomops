import os

os.environ["DATABASE_URL"] = "sqlite:///./test_releaseflow.db"
import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed_database
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(autouse=True)
def seeded_db():
    with SessionLocal() as db:
        seed_database(db)
    yield


@pytest.fixture
def client():
    return TestClient(app)
