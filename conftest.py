"""
Root pytest configuration shared by all test directories.

This module sets up a PostgreSQL test database using podman.
"""
import os
import subprocess
import time
import pytest


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
