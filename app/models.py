from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    trade_id: Mapped[UUID] = mapped_column(primary_key=True)
    product: Mapped[str] = mapped_column(Text)
    volume: Mapped[float] = mapped_column(Numeric(18, 4))
    price: Mapped[float] = mapped_column(Numeric(18, 4))
    side: Mapped[str] = mapped_column(String(4))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pnl: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    sealed: Mapped[bool] = mapped_column(default=False, server_default="false")


class Total(Base):
    __tablename__ = "totals"

    product: Mapped[str] = mapped_column(Text, primary_key=True)
    total: Mapped[float] = mapped_column(
        Numeric(24, 4), default=0, server_default="0"
    )
    trades: Mapped[int] = mapped_column(default=0, server_default="0")


class Audit(Base):
    __tablename__ = "price_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[UUID]
    user_id: Mapped[str] = mapped_column(Text)
    new_price: Mapped[float] = mapped_column(Numeric(18, 4))
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
