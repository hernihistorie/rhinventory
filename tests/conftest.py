"""
Pytest configuration for rhinventory tests.

This module sets up a PostgreSQL test database using podman.
"""
import os
import subprocess
import time
import pytest

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import User, Organization


# PostgreSQL test container configuration (for local development)
POSTGRES_CONTAINER_NAME = "rhinventory_test_db"
POSTGRES_VERSION = "16"
POSTGRES_PORT = "5433"  # Use non-default port to avoid conflicts
POSTGRES_USER = "rhinventory_test"
POSTGRES_PASSWORD = "test_password"
POSTGRES_DB = "rhinventory_test"


def start_postgres_container():
    """Start PostgreSQL container using podman."""
    # Try to start existing container, or create new one if it doesn't exist
    result = subprocess.run(
        ["podman", "start", POSTGRES_CONTAINER_NAME],
        capture_output=True,
        check=False
    )
    
    if result.returncode != 0:
        # Container doesn't exist, create it
        subprocess.run([
            "podman", "run",
            "--name", POSTGRES_CONTAINER_NAME,
            "-e", f"POSTGRES_USER={POSTGRES_USER}",
            "-e", f"POSTGRES_PASSWORD={POSTGRES_PASSWORD}",
            "-e", f"POSTGRES_DB={POSTGRES_DB}",
            "-p", f"{POSTGRES_PORT}:5432",
            "-d",
            f"postgres:{POSTGRES_VERSION}"
        ], check=True)
    
    # Wait for PostgreSQL to be ready
    for _ in range(30):
        result = subprocess.run(
            ["podman", "exec", POSTGRES_CONTAINER_NAME, "pg_isready", "-U", POSTGRES_USER],
            capture_output=True,
            check=False
        )
        if result.returncode == 0:
            time.sleep(1)  # Give it a moment to fully initialize
            return
        time.sleep(1)
    
    raise RuntimeError("PostgreSQL container failed to start in time")


def get_database_url():
    """Get the database URL for the test database."""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"


@pytest.fixture(scope="session")
def database_url():
    """Provide database URL for tests."""
    # Use TEST_DATABASE_URL if set (e.g., in CI or custom environments)
    env_db_url = os.getenv("TEST_DATABASE_URL")
    if env_db_url:
        return env_db_url
    
    # Otherwise, start local podman container
    start_postgres_container()
    return get_database_url()


class TestAppConfig:
    """Test configuration for the Flask app."""
    TESTING = True
    GITHUB_CLIENT_ID = None
    GITHUB_CLIENT_SECRET = None
    FILES_DIR = "files"
    SECRET_KEY = "test-secret-key-for-testing-only"
    SENTRY_DSN = None
    DROPZONE_PATH = "dropzone"
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_FILE_STORE = "local"
    FILE_STORE_LOCATIONS = {"local": "files", "local_nas": "files2"}


@pytest.fixture()
def app(database_url):
    """Create and configure a test Flask application instance."""
    # Set database URL in config
    TestAppConfig.SQLALCHEMY_DATABASE_URI = database_url
    
    app = create_app(config_object=TestAppConfig)

    with app.app_context():
        # Create dropzone directory
        os.makedirs(app.config['DROPZONE_PATH'], exist_ok=True)
        
        # Drop all tables and recreate them for a clean state
        db.drop_all()
        db.create_all()

        # Create test user
        user = User(username="pytest", read_access=True, write_access=True, admin=True)
        db.session.add(user)

        # Create test organization
        org = Organization(name="Testing z.s.")
        db.session.add(org)

        db.session.commit()

        user_id = user.id

    # Set up automatic login for tests
    @app.login_manager.request_loader
    def load_user_from_request(request):
        return db.session.get(User, user_id)
    
    yield app

    # Cleanup after test
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Create a test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture()
def db_session(app):
    """Provide a database session for tests."""
    with app.app_context():
        yield db.session
