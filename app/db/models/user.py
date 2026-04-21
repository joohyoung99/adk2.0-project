from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    preference: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False)
    fridge_items: Mapped[list["UserFridgeItem"]] = relationship(back_populates="user")  # type: ignore[name-defined]
    recommendation_logs: Mapped[list["RecommendationLog"]] = relationship(back_populates="user")  # type: ignore[name-defined]
    cooking_history: Mapped[list["CookingHistory"]] = relationship(back_populates="user")  # type: ignore[name-defined]


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("spice_level BETWEEN 0 AND 5", name="ck_spice_level"),
        CheckConstraint("cooking_skill IN ('beginner', 'intermediate', 'advanced')", name="ck_cooking_skill"),
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    spice_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    disliked_ingredients: Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    allergies: Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    dietary_tags: Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    cooking_skill: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="preference")
