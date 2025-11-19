# Running Tests

The rhinventory tests use PostgreSQL running in a podman container. This provides a realistic testing environment that matches the production database.

If you don't want to use the automatically set up PostgreSQL server, you can pass your own by providing the `TEST_DATABASE_URL` environment variable.

## Quick Start

The test infrastructure automatically starts the PostgreSQL container when you run tests:

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_rhinventory.py

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_rhinventory.py::test_index
```

## Managing the Test Database Container

The PostgreSQL container is managed automatically by the test fixtures. You can also manage it manually with podman:

```bash
# Check status
podman ps -a --filter name=rhinventory_test_db

# View logs
podman logs rhinventory_test_db

# Follow logs in real-time
podman logs -f rhinventory_test_db

# Stop the container
podman stop rhinventory_test_db

# Start the container
podman start rhinventory_test_db

# Remove the container (full reset)
podman rm -f rhinventory_test_db

# Connect to the database with psql
podman exec -it rhinventory_test_db psql -U rhinventory_test -d rhinventory_test
```

## Database Connection Details

When the test container is running, you can connect to it with these details:

- **Host:** localhost
- **Port:** 5433
- **Database:** rhinventory_test
- **User:** rhinventory_test
- **Password:** test_password

Connection string:
```
postgresql://rhinventory_test:test_password@localhost:5433/rhinventory_test
```

## CI/CD Integration

The test setup checks for the `TEST_DATABASE_URL` environment variable. If set, it uses that database. Otherwise, it starts a local podman container.

**Local development (default):**
```bash
uv run pytest  # Automatically starts podman container
```

**Using a custom database:**
```bash
TEST_DATABASE_URL=postgresql://user:pass@host:port/db uv run pytest
```

**GitHub Actions:**
The existing `.github/workflows/pytest.yml` sets `TEST_DATABASE_URL` to use the PostgreSQL service container.