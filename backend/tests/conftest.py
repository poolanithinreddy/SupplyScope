import os

os.environ["DATABASE_URL"] = "sqlite:///./test_supplyscope.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        test_client.post("/api/scenario/reset")
        yield test_client
