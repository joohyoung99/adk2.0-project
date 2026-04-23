from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.web import app
from app.schemas.agent_io import FridgeItemSnapshot

client = TestClient(app)

MOCK_FRIDGE = [
    FridgeItemSnapshot(
        ingredient_id=1,
        ingredient_name="계란",
        quantity=6.0,
        unit="개",
        freshness_score=5,
        expires_at=(date.today() + timedelta(days=10)).isoformat(),
    ),
    FridgeItemSnapshot(
        ingredient_id=2,
        ingredient_name="두부",
        quantity=1.0,
        unit="모",
        freshness_score=3,
        expires_at=(date.today() + timedelta(days=1)).isoformat(),
    ),
]

MOCK_EXPIRING = [MOCK_FRIDGE[1]]


@patch("app.api.fridge.user_repository.get_fridge_items", new_callable=AsyncMock)
@patch("app.api.fridge.user_repository.get_expiring_items", new_callable=AsyncMock)
@patch("app.api.fridge.AsyncSessionLocal")
def test_fridge_returns_items_and_expiring(mock_session_cls, mock_expiring, mock_fridge):
    mock_fridge.return_value = MOCK_FRIDGE
    mock_expiring.return_value = MOCK_EXPIRING
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session_cls.return_value = mock_cm

    response = client.get("/api/fridge/1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["fridge_items"]) == 2
    assert len(data["expiring_items"]) == 1
    assert data["expiring_items"][0]["ingredient_name"] == "두부"
    assert data["expiring_items"][0]["days_until_expiry"] == 1
