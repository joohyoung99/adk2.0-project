from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserFridgeItem(Base):
    __tablename__ = "user_fridge_items"
    __table_args__ = (
        CheckConstraint(
            "storage_location IN ('fridge', 'freezer', 'pantry', 'other')",
            name="ck_storage_location",
        ),
        CheckConstraint(
            "freshness_score IS NULL OR freshness_score BETWEEN 0 AND 1",
            name="ck_freshness_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    storage_location: Mapped[str] = mapped_column(String(30), nullable=False, default="fridge")
    freshness_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="fridge_items")  # type: ignore[name-defined]
    ingredient: Mapped["Ingredient"] = relationship()  # type: ignore[name-defined]
