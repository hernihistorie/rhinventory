"""Where database writes came from: who made them, how, and with which code.

Each database transaction that writes logs or events gets one LogTransaction,
which the LogItem and DBEvent rows it wrote reference.  This is a reified
transaction, as in Datomic: the transaction is itself a record that can be
queried.  The writes of one HTTP request or script run share a request_id.
"""
import datetime
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

import click
import flask_login
from flask import current_app, has_app_context, has_request_context, request
from sqlalchemy import ForeignKey, event, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from rhinventory.extensions import db

REDACTED = "[redacted]"
"""Logged in place of a secret value."""

SECRET_ARG_NAMES = ("key", "token", "code", "state", "password", "secret")
"""Request args whose name contains one of these have their value redacted."""

REPO_ROOT = Path(__file__).resolve().parents[2]
STACK_DIRS = (REPO_ROOT / "rhinventory", REPO_ROOT / "scripts")
# The logging machinery's own frames say nothing about where a write came from
STACK_SKIPPED_FILES = (Path(__file__).resolve(), REPO_ROOT / "rhinventory" / "models" / "log.py")
STACK_DEPTH = 15

_SESSION_INFO_KEY = "rhinventory_log_transaction"
_REQUEST_ID_ENVIRON_KEY = "rhinventory.request_id"
_PROCESS_REQUEST_ID = uuid.uuid7()
"""Ties together the writes of a script or CLI command run."""


class LogTransaction(db.Model):
    """The context of a database transaction that wrote logs or events."""
    __tablename__ = 'log_transactions'
    rhinventory_log = False

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)

    kind: Mapped[str] = mapped_column()
    """"http" for requests, "cli" for flask commands, "script" for anything else."""
    request_id: Mapped[uuid.UUID] = mapped_column(index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))

    command: Mapped[str | None] = mapped_column()
    """The flask command or script that ran, for "cli" and "script"."""
    method: Mapped[str | None] = mapped_column()
    endpoint: Mapped[str | None] = mapped_column(index=True)
    url_rule: Mapped[str | None] = mapped_column()
    args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    """Path and query string args of the request, with secrets redacted."""

    git_sha: Mapped[str | None] = mapped_column()
    git_dirty: Mapped[bool | None] = mapped_column()
    alembic_revision: Mapped[str | None] = mapped_column()
    stack: Mapped[list[str] | None] = mapped_column(JSONB)
    """The rhinventory frames that started the transaction's first write,
    as path:function:line, innermost last.  With git_sha, each is a permalink."""

    user = relationship("User")


def current_log_transaction(session: Session) -> LogTransaction:
    """The LogTransaction of the session's current transaction, made on first use."""
    log_transaction = session.info.get(_SESSION_INFO_KEY)
    if log_transaction is None:
        log_transaction = LogTransaction(**_context(), **_versions(), stack=_stack())
        session.add(log_transaction)
        session.info[_SESSION_INFO_KEY] = log_transaction
    return log_transaction


@event.listens_for(Session, "after_transaction_end")
def _forget_log_transaction(session: Session, transaction: Any) -> None:
    if transaction.parent is None:
        session.info.pop(_SESSION_INFO_KEY, None)


def _context() -> dict[str, Any]:
    if has_request_context():
        user = flask_login.current_user
        return {
            "kind": "http",
            "request_id": request.environ.setdefault(_REQUEST_ID_ENVIRON_KEY, uuid.uuid7()),
            "user_id": user.id if user and user.is_authenticated else None,
            "method": request.method,
            "endpoint": request.endpoint,
            "url_rule": request.url_rule.rule if request.url_rule else None,
            "args": _request_args() or None,
        }
    click_context = click.get_current_context(silent=True)
    if click_context is not None:
        return {"kind": "cli", "request_id": _PROCESS_REQUEST_ID, "command": click_context.command_path}
    return {"kind": "script", "request_id": _PROCESS_REQUEST_ID, "command": _script_name()}


def _request_args() -> dict[str, Any]:
    args: dict[str, Any] = {
        name: value if isinstance(value, (str, int, float, bool)) else str(value)
        for name, value in (request.view_args or {}).items()
    }
    for name, values in request.args.lists():
        args[name] = values[0] if len(values) == 1 else values
    return {
        name: REDACTED if any(secret in name.lower() for secret in SECRET_ARG_NAMES) else value
        for name, value in args.items()
    }


def _script_name() -> str:
    script = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if script is None:
        return "python"
    if script.is_relative_to(REPO_ROOT):
        return str(script.relative_to(REPO_ROOT))
    return script.name


def _stack() -> list[str]:
    frames = traceback.StackSummary.extract(traceback.walk_stack(None), lookup_lines=False)
    stack = []
    for frame in reversed(frames):
        path = Path(frame.filename)
        if path in STACK_SKIPPED_FILES or not any(path.is_relative_to(directory) for directory in STACK_DIRS):
            continue
        stack.append(f"{path.relative_to(REPO_ROOT)}:{frame.name}:{frame.lineno}")
    return stack[-STACK_DEPTH:]


def _versions() -> dict[str, Any]:
    """The code and schema versions the app runs, read once.

    deploy.sh restarts the app after pulling and migrating, so they stay current.
    """
    if not has_app_context():
        return {"git_sha": None, "git_dirty": None, "alembic_revision": None}
    versions = current_app.extensions.get("rhinventory_log_versions")
    if versions is None:
        git_sha, git_dirty = _git_revision()
        versions = {"git_sha": git_sha, "git_dirty": git_dirty, "alembic_revision": _alembic_revision()}
        current_app.extensions["rhinventory_log_versions"] = versions
    return versions


def _git_revision() -> tuple[str | None, bool | None]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    try:
        return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        return None, None


def _alembic_revision() -> str | None:
    # On its own connection, so a failure can't abort the transaction being logged
    with db.engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
