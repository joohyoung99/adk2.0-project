from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    substitutions_as_original: Mapped[list["IngredientSubstitution"]] = relationship(
        back_populates="original_ingredient",
        foreign_keys="IngredientSubstitution.original_ingredient_id",
    )
    substitutions_as_substitute: Mapped[list["IngredientSubstitution"]] = relationship(
        back_populates="substitute_ingredient",
        foreign_keys="IngredientSubstitution.substitute_ingredient_id",
    )


class IngredientSubstitution(Base):
    __tablename__ = "ingredient_substitutions"
    __table_args__ = (
        CheckConstraint("original_ingredient_id <> substitute_ingredient_id", name="ck_no_self_sub"),
        UniqueConstraint("original_ingredient_id", "substitute_ingredient_id", name="uq_substitution_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    original_ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    substitute_ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    substitution_ratio: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)
    note: Mapped[str | None] = mapped_column()

    original_ingredient: Mapped["Ingredient"] = relationship(
        back_populates="substitutions_as_original",
        foreign_keys=[original_ingredient_id],
    )
    substitute_ingredient: Mapped["Ingredient"] = relationship(
        back_populates="substitutions_as_substitute",
        foreign_keys=[substitute_ingredient_id],
    )
