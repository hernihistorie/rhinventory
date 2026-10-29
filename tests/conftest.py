"""
Pytest configuration for rhinventory tests.

The PostgreSQL test database is provided by the root conftest.py.
"""
import os
import pytest

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import User, Organization


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
