import subprocess

from flask_login import login_user
import pytest
from sqlalchemy import text

from rhinventory.db import User
from rhinventory.models.asset_attributes import Platform
from rhinventory.models.log import LogItem
from rhinventory.models.log_transaction import REDACTED, REPO_ROOT, LogTransaction, _alembic_revision


@pytest.fixture(autouse=True)
def forget_setup_transactions(db_session):
    """Leave out the transactions of the app fixture creating its user."""
    db_session.query(LogItem).delete()
    db_session.query(LogTransaction).delete()
    db_session.commit()


def write(db_session, name: str) -> None:
    db_session.add(Platform.from_name(name))
    db_session.commit()


def transactions(db_session) -> list[LogTransaction]:
    db_session.expire_all()
    return db_session.query(LogTransaction).order_by(LogTransaction.created_at).all()


def test_writes_in_a_request_record_its_context(app, db_session):
    user = db_session.query(User).first()
    with app.test_request_context("/asset/edit/?id=5&key=pushkey_secret", method="POST"):
        login_user(user)
        write(db_session, "NES")

    [log_transaction] = transactions(db_session)
    assert log_transaction.kind == "http"
    assert log_transaction.user_id == user.id
    assert (log_transaction.method, log_transaction.endpoint, log_transaction.url_rule) == \
        ("POST", "asset.edit_view", "/asset/edit/")
    assert log_transaction.args == {"id": "5", "key": REDACTED}
    assert log_transaction.command is None

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    assert log_transaction.git_sha == head
    assert log_transaction.git_dirty is not None

    # The stack ends where the write was made, without the logging machinery
    frames = [frame.rsplit(":", 1) for frame in log_transaction.stack[-2:]]
    assert [location for location, _ in frames] == [
        "rhinventory/models/tests/test_log_transaction.py:test_writes_in_a_request_record_its_context",
        "rhinventory/models/tests/test_log_transaction.py:write",
    ]
    assert all(line.isdigit() for _, line in frames)

    assert {log_item.transaction_id for log_item in db_session.query(LogItem)} == {log_transaction.id}


def test_each_commit_is_a_transaction_of_its_request(app, db_session):
    with app.test_request_context("/asset/new/", method="POST"):
        write(db_session, "NES")
        write(db_session, "SNES")
    with app.test_request_context("/asset/new/", method="POST"):
        write(db_session, "N64")

    first, second, other_request = transactions(db_session)
    assert len({first.id, second.id, other_request.id}) == 3
    assert first.request_id == second.request_id != other_request.request_id


def test_rolled_back_transaction_isnt_recorded(app, db_session):
    with app.test_request_context("/asset/new/", method="POST"):
        db_session.add(Platform.from_name("NES"))
        db_session.flush()
        db_session.rollback()
        write(db_session, "SNES")

    [log_transaction] = transactions(db_session)
    assert {log_item.transaction_id for log_item in db_session.query(LogItem)} == {log_transaction.id}


def test_writes_outside_requests_are_attributed_to_the_script(db_session):
    write(db_session, "NES")
    write(db_session, "SNES")

    first, second = transactions(db_session)
    assert first.kind == "script"
    assert "pytest" in first.command
    assert (first.endpoint, first.args, first.user_id) == (None, None, None)
    assert first.request_id == second.request_id


def test_writes_in_flask_commands_are_attributed_to_the_command(app, db_session):
    @app.cli.command("make-platform")
    def make_platform():
        write(db_session, "NES")

    result = app.test_cli_runner().invoke(args=["make-platform"])
    assert result.exit_code == 0, result.output

    [log_transaction] = transactions(db_session)
    assert log_transaction.kind == "cli"
    assert log_transaction.command.endswith("make-platform")


def test_alembic_revision_is_read_from_the_database(db_session):
    assert _alembic_revision() is None  # the test database is made without alembic

    db_session.execute(text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)"))
    db_session.execute(text("INSERT INTO alembic_version VALUES ('5b3e7a835057')"))
    db_session.commit()
    try:
        assert _alembic_revision() == "5b3e7a835057"
    finally:
        db_session.execute(text("DROP TABLE alembic_version"))
        db_session.commit()
