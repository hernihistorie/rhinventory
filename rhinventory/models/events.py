from typing import Any
from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rhinventory.db import User
from rhinventory.extensions import db


class PushKey(db.Model):
    __tablename__ = 'push_keys'

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(index=True)
    uses_remaining: Mapped[int | None] = mapped_column()
    authorized_at: Mapped[datetime] = mapped_column()
    authorized_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))

    authorized_by_user: Mapped[User] = relationship()

    event_sessions: Mapped[list["EventSession"]] = relationship(back_populates="push_key")


class EventSession(db.Model):
    __tablename__ = 'event_sessions'

    id: Mapped[int] = mapped_column(primary_key=True)
    application_name: Mapped[str | None] = mapped_column()
    namespace: Mapped[str] = mapped_column()
    internal: Mapped[bool] = mapped_column(default=False)
    closed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime | None] = mapped_column(default=datetime.now)
    push_key_id: Mapped[int | None] = mapped_column(ForeignKey('push_keys.id'))
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))

    push_key: Mapped[PushKey | None] = relationship(back_populates="event_sessions")
    user: Mapped[User | None] = relationship()

    events: Mapped[list["DBEvent"]] = relationship(back_populates="event_session")

class DBEvent(db.Model):
    __tablename__ = 'events'

    id: Mapped[UUID] = mapped_column(primary_key=True)

    namespace: Mapped[str] = mapped_column(index=True)
    class_name: Mapped[str] = mapped_column(index=True)
    timestamp: Mapped[datetime] = mapped_column()
    ingested_at: Mapped[datetime] = mapped_column()
    event_session_id: Mapped[int] = mapped_column(ForeignKey('event_sessions.id'))

    data: Mapped[dict[Any, Any]] = mapped_column(JSONB)

    # INFO: Here you could do something like
    # name = index_property("data", "name")

    event_session: Mapped[EventSession] = relationship()
