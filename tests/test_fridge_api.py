from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.web import app
from app.api.fridge import _days_until
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


def _make_mock_session():
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


# ── _days_until 단위 테스트 ───────────────────────────────────
def test_days_until_none_input():
    assert _days_until(None) is None


def test_days_until_future():
    future = (date.today() + timedelta(days=3)).isoformat()
    assert _days_until(future) == 3


def test_days_until_today():
    assert _days_until(date.today().isoformat()) == 0


def test_days_until_malformed():
    assert _days_until("not-a-date") is None


# ── 엔드포인트 테스트 ─────────────────────────────────────────
@patch("app.api.fridge.user_repository.get_fridge_items", new_callable=AsyncMock)
@patch("app.api.fridge.user_repository.get_expiring_items", new_callable=AsyncMock)
@patch("app.api.fridge.AsyncSessionLocal")
def test_fridge_returns_items_and_expiring(mock_session_cls, mock_expiring, mock_fridge):
    mock_fridge.return_value = MOCK_FRIDGE
    mock_expiring.return_value = MOCK_EXPIRING
    mock_session_cls.return_value = _make_mock_session()

    response = client.get("/api/fridge/1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["fridge_items"]) == 2
    assert len(data["expiring_items"]) == 1
    assert data["expiring_items"][0]["ingredient_name"] == "두부"
    assert data["expiring_items"][0]["days_until_expiry"] == 1


@patch("app.api.fridge.user_repository.get_fridge_items", new_callable=AsyncMock)
@patch("app.api.fridge.user_repository.get_expiring_items", new_callable=AsyncMock)
@patch("app.api.fridge.AsyncSessionLocal")
def test_fridge_empty(mock_session_cls, mock_expiring, mock_fridge):
    mock_fridge.return_value = []
    mock_expiring.return_value = []
    mock_session_cls.return_value = _make_mock_session()

    response = client.get("/api/fridge/1")

    assert response.status_code == 200
    data = response.json()
    assert data["fridge_items"] == []
    assert data["expiring_items"] == []


@patch("app.api.fridge.user_repository.get_fridge_items", new_callable=AsyncMock)
@patch("app.api.fridge.user_repository.get_expiring_items", new_callable=AsyncMock)
@patch("app.api.fridge.AsyncSessionLocal")
def test_fridge_item_with_no_expiry(mock_session_cls, mock_expiring, mock_fridge):
    item_no_expiry = FridgeItemSnapshot(
        ingredient_id=3,
        ingredient_name="소금",
        quantity=500.0,
        unit="g",
        freshness_score=5,
        expires_at=None,
    )
    mock_fridge.return_value = [item_no_expiry]
    mock_expiring.return_value = []
    mock_session_cls.return_value = _make_mock_session()

    response = client.get("/api/fridge/1")

    assert response.status_code == 200
    data = response.json()
    assert data["fridge_items"][0]["days_until_expiry"] is None
