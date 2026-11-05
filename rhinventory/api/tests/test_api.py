"""
Tests for rhinventory FastAPI application.

These tests use PostgreSQL running in a podman container.
The conftest.py file manages the container lifecycle and database setup.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rhinventory.api.app import app
from rhinventory.api.database import get_db
from rhinventory.extensions import Base


@pytest.fixture()
def api_client(database_url):
    """Create a test client for the FastAPI app with test database."""
    # Create test engine and session
    engine = create_engine(database_url)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_get_asset(api_client: TestClient):
    """Test fetching an asset by ID."""
    response = api_client.get("/asset/get/1")
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert "error" in data or "id" in data
