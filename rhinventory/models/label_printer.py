import enum
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint, func
from sqlalchemy.orm import relationship, backref, Mapped, mapped_column
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db

LabelPrinterMethod = enum.Enum('LabelPrinterMethod', ["hhprint"])

class LabelPrinter(db.Model):
    __tablename__ = 'label_printers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str] = mapped_column(String, nullable=True)
    method: Mapped[LabelPrinterMethod] = mapped_column(Enum(LabelPrinterMethod), nullable=False)
    printer: Mapped[str] = mapped_column(String, nullable=True)
    backend: Mapped[str] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=True)
    label: Mapped[str] = mapped_column(String, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __str__(self) -> str:
        return f"LabelPrinter {self.name}"
