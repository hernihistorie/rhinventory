from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rhinventory.db import User
from rhinventory.extensions import db

class EventPushKey(db.Model):
    __tablename__ = 'event_push_keys'

    id: Mapped[int] = mapped_column(primary_key=True)
    application_name: Mapped[str | None] = mapped_column()
    namespace: Mapped[str] = mapped_column()
    key: Mapped[str] = mapped_column(index=True)
    authorized_at: Mapped[datetime] = mapped_column()
    authorized_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    uses_remaining: Mapped[int | None] = mapped_column()

    authorized_by_user: Mapped[User] = relationship()

    events: Mapped[list[DBEvent]] = relationship(back_populates="event_push_key")

class DBEvent(db.Model):
    __tablename__ = 'events'

    id: Mapped[UUID] = mapped_column(primary_key=True)

    namespace: Mapped[str] = mapped_column(index=True)
    class_name: Mapped[str] = mapped_column(index=True)
    timestamp: Mapped[datetime] = mapped_column()
    ingested_at: Mapped[datetime] = mapped_column()
    event_push_key_id: Mapped[int] = mapped_column(ForeignKey('event_push_keys.id'))

    data: Mapped[dict] = mapped_column(JSONB)

    # INFO: Here you could do something like
    # name = index_property("data", "name")

    event_push_key: Mapped[EventPushKey] = relationship()
