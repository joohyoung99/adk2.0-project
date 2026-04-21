from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"
    __table_args__ = (
        CheckConstraint(
            "route IN ('COOK_NOW', 'SUBSTITUTION', 'SHOPPING_NEEDED')",
            name="ck_route",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_text: Mapped[str] = mapped_column(nullable=False)
    context_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    route: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="recommendation_logs")  # type: ignore[name-defined]


class CookingHistory(Base):
    __tablename__ = "cooking_history"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    liked: Mapped[bool | None] = mapped_column()
    feedback_text: Mapped[str | None] = mapped_column()
    cooked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="cooking_history")  # type: ignore[name-defined]
    recipe: Mapped["Recipe"] = relationship()  # type: ignore[name-defined]
