from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user_id
from src.api.trading import get_trading_service
from src.core.database import get_db
from src.core.exceptions import (
    AssetInactiveError,
    AssetNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidTradeAmountError,
    TradingEngineException,
    WalletNotFoundError,
)
from src.main import app
from src.models import Transaction, User


@pytest.fixture
def api_setup():
    """Provide authenticated user, mock DB session, and mock trading service for API tests."""
    user_id = uuid4()
    asset_id = uuid4()
    wallet_id = uuid4()

    user = User(
        id=user_id,
        email="trader@example.com",
        password_hash="argon2-hashed-password",
    )

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    mock_service = MagicMock()
    mock_service.execute_buy = AsyncMock()
    mock_service.execute_sell = AsyncMock()

    async def override_get_db():
        yield mock_db

    def override_current_user_id():
        return user_id

    def override_trading_service():
        return mock_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_current_user_id
    app.dependency_overrides[get_trading_service] = override_trading_service

    try:
        yield {
            "user": user,
            "user_id": user_id,
            "asset_id": asset_id,
            "wallet_id": wallet_id,
            "mock_db": mock_db,
            "mock_service": mock_service,
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_trading_service, None)


@pytest.mark.asyncio
async def test_buy_order_success(api_setup):
    """Verify POST /api/v1/trades/buy executes a buy order and returns HTTP 201 with TradeResponse."""
    setup = api_setup
    tx_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=tx_id,
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="BUY",
        quantity=Decimal("2.50000000"),
        price=Decimal("100.00000000"),
        total_amount=Decimal("250.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_buy.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "2.50000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(tx_id)
    assert data["wallet_id"] == str(setup["wallet_id"])
    assert data["asset_id"] == str(setup["asset_id"])
    assert data["transaction_type"] == "BUY"
    assert data["quantity"] == "2.50000000"
    assert data["price"] == "100.00000000"
    assert data["total_amount"] == "250.00000000"
    assert "created_at" in data

    # Verify service received authenticated user's ID and exact Decimal inputs
    setup["mock_service"].execute_buy.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("2.50000000"),
        price=Decimal("100.00000000"),
        session=setup["mock_db"],
    )

    # Verify endpoint does NOT commit or roll back independently
    setup["mock_db"].commit.assert_not_called()
    setup["mock_db"].rollback.assert_not_called()


@pytest.mark.asyncio
async def test_buy_order_rejects_unauthenticated_request():
    """Verify POST /api/v1/trades/buy rejects requests without authorization header."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json={
                "asset_id": str(uuid4()),
                "quantity": "1.00000000",
                "price": "100.00000000",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_buy_order_rejects_invalid_token():
    """Verify POST /api/v1/trades/buy rejects requests with an invalid bearer token."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json={
                "asset_id": str(uuid4()),
                "quantity": "1.00000000",
                "price": "100.00000000",
            },
            headers={"Authorization": "Bearer invalid-expired-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_buy_order_ignores_client_supplied_wallet_id(api_setup):
    """Verify client-supplied wallet_id is ignored and service resolves wallet strictly via user_id."""
    setup = api_setup
    untrusted_wallet_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        total_amount=Decimal("50.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_buy.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "50.00000000",
        "wallet_id": str(untrusted_wallet_id),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    setup["mock_service"].execute_buy.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        session=setup["mock_db"],
    )


@pytest.mark.asyncio
async def test_buy_order_ignores_client_supplied_user_id(api_setup):
    """Verify client-supplied user_id in payload is ignored and authenticated user is used."""
    setup = api_setup
    untrusted_user_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        total_amount=Decimal("50.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_buy.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "50.00000000",
        "user_id": str(untrusted_user_id),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    setup["mock_service"].execute_buy.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        session=setup["mock_db"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"asset_id": str(uuid4()), "quantity": "0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "-1.0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "0"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "-50.00"},
        {"asset_id": str(uuid4()), "quantity": "1.123456789", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "100.123456789"},
        {"asset_id": "not-a-valid-uuid", "quantity": "1.0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "invalid", "price": "100.00"},
    ],
)
async def test_buy_order_rejects_schema_validation_errors(api_setup, payload):
    """Verify request payloads failing Pydantic schema validation return HTTP 422."""
    setup = api_setup

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 422
    setup["mock_service"].execute_buy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,expected_status,expected_detail",
    [
        (
            AssetNotFoundError(uuid4()),
            404,
            "The specified tradable asset does not exist.",
        ),
        (
            WalletNotFoundError(uuid4()),
            404,
            "User trading wallet not found.",
        ),
        (
            AssetInactiveError("BTC"),
            400,
            "Asset BTC is inactive and cannot be traded.",
        ),
        (
            InsufficientFundsError(Decimal("10"), Decimal("100")),
            400,
            "Insufficient wallet balance to execute this buy order.",
        ),
        (
            CurrencyMismatchError("USD", "EUR"),
            400,
            "Wallet and asset currencies must match.",
        ),
        (
            InvalidTradeAmountError("Quantity cannot exceed decimal limit."),
            400,
            "Quantity cannot exceed decimal limit.",
        ),
        (
            TradingEngineException(
                "A generic trading engine failure.",
                "GENERIC_TRADING_ERROR",
            ),
            400,
            "A generic trading engine failure.",
        ),
    ],
)
async def test_buy_order_maps_domain_exceptions_to_http_errors(
    api_setup, exception, expected_status, expected_detail
):
    """Verify domain exceptions raised by TradingService map to correct HTTP status codes and details."""
    setup = api_setup
    setup["mock_service"].execute_buy.side_effect = exception

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


@pytest.mark.asyncio
async def test_buy_order_unexpected_service_exception_returns_500(api_setup):
    """Verify unhandled service exceptions result in HTTP 500 Internal Server Error."""
    setup = api_setup
    setup["mock_service"].execute_buy.side_effect = RuntimeError("Database connection pool exhausted")

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/buy",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 500


def test_buy_route_is_registered():
    """Verify POST /api/v1/trades/buy is registered in the FastAPI application routes."""
    paths = app.openapi()["paths"]
    assert "/api/v1/trades/buy" in paths
    assert "post" in paths["/api/v1/trades/buy"]


@pytest.mark.asyncio
async def test_sell_order_success(api_setup):
    """Verify POST /api/v1/trades/sell executes a sell order and returns HTTP 201 with TradeResponse."""
    setup = api_setup
    tx_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=tx_id,
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="SELL",
        quantity=Decimal("2.50000000"),
        price=Decimal("100.00000000"),
        total_amount=Decimal("250.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_sell.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "2.50000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(tx_id)
    assert data["wallet_id"] == str(setup["wallet_id"])
    assert data["asset_id"] == str(setup["asset_id"])
    assert data["transaction_type"] == "SELL"
    assert data["quantity"] == "2.50000000"
    assert data["price"] == "100.00000000"
    assert data["total_amount"] == "250.00000000"
    assert "created_at" in data

    # Verify service received authenticated user's ID and exact Decimal inputs
    setup["mock_service"].execute_sell.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("2.50000000"),
        price=Decimal("100.00000000"),
        session=setup["mock_db"],
    )

    # Verify endpoint does NOT commit or roll back independently
    setup["mock_db"].commit.assert_not_called()
    setup["mock_db"].rollback.assert_not_called()


@pytest.mark.asyncio
async def test_sell_order_rejects_unauthenticated_request():
    """Verify POST /api/v1/trades/sell rejects requests without authorization header."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json={
                "asset_id": str(uuid4()),
                "quantity": "1.00000000",
                "price": "100.00000000",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sell_order_rejects_invalid_token():
    """Verify POST /api/v1/trades/sell rejects requests with an invalid bearer token."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json={
                "asset_id": str(uuid4()),
                "quantity": "1.00000000",
                "price": "100.00000000",
            },
            headers={"Authorization": "Bearer invalid-expired-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sell_order_ignores_client_supplied_wallet_id(api_setup):
    """Verify client-supplied wallet_id is ignored and service resolves wallet strictly via user_id."""
    setup = api_setup
    untrusted_wallet_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        total_amount=Decimal("50.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_sell.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "50.00000000",
        "wallet_id": str(untrusted_wallet_id),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    setup["mock_service"].execute_sell.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        session=setup["mock_db"],
    )


@pytest.mark.asyncio
async def test_sell_order_ignores_client_supplied_user_id(api_setup):
    """Verify client-supplied user_id in payload is ignored and authenticated user is used."""
    setup = api_setup
    untrusted_user_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_transaction = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet_id"],
        asset_id=setup["asset_id"],
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        total_amount=Decimal("50.00000000"),
        created_at=now,
    )
    setup["mock_service"].execute_sell.return_value = mock_transaction

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "50.00000000",
        "user_id": str(untrusted_user_id),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 201
    setup["mock_service"].execute_sell.assert_awaited_once_with(
        user_id=setup["user_id"],
        asset_id=setup["asset_id"],
        quantity=Decimal("1.00000000"),
        price=Decimal("50.00000000"),
        session=setup["mock_db"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"asset_id": str(uuid4()), "quantity": "0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "-1.0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "0"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "-50.00"},
        {"asset_id": str(uuid4()), "quantity": "1.123456789", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "1.0", "price": "100.123456789"},
        {"asset_id": "not-a-valid-uuid", "quantity": "1.0", "price": "100.00"},
        {"asset_id": str(uuid4()), "quantity": "invalid", "price": "100.00"},
    ],
)
async def test_sell_order_rejects_schema_validation_errors(api_setup, payload):
    """Verify request payloads failing Pydantic schema validation return HTTP 422."""
    setup = api_setup

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 422
    setup["mock_service"].execute_sell.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,expected_status,expected_detail",
    [
        (
            AssetNotFoundError(uuid4()),
            404,
            "The specified tradable asset does not exist.",
        ),
        (
            WalletNotFoundError(uuid4()),
            404,
            "User trading wallet not found.",
        ),
        (
            AssetInactiveError("BTC"),
            400,
            "Asset BTC is inactive and cannot be traded.",
        ),
        (
            InsufficientHoldingsError(Decimal("0.5"), Decimal("2.0")),
            400,
            "Insufficient asset holdings to execute this sell order.",
        ),
        (
            CurrencyMismatchError("USD", "EUR"),
            400,
            "Wallet and asset currencies must match.",
        ),
        (
            InvalidTradeAmountError("Quantity cannot exceed decimal limit."),
            400,
            "Quantity cannot exceed decimal limit.",
        ),
        (
            TradingEngineException(
                "A generic trading engine failure.",
                "GENERIC_TRADING_ERROR",
            ),
            400,
            "A generic trading engine failure.",
        ),
    ],
)
async def test_sell_order_maps_domain_exceptions_to_http_errors(
    api_setup, exception, expected_status, expected_detail
):
    """Verify domain exceptions raised by TradingService map to correct HTTP status codes and details."""
    setup = api_setup
    setup["mock_service"].execute_sell.side_effect = exception

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


@pytest.mark.asyncio
async def test_sell_order_unexpected_service_exception_returns_500(api_setup):
    """Verify unhandled service exceptions result in HTTP 500 Internal Server Error."""
    setup = api_setup
    setup["mock_service"].execute_sell.side_effect = RuntimeError("Database connection pool exhausted")

    payload = {
        "asset_id": str(setup["asset_id"]),
        "quantity": "1.00000000",
        "price": "100.00000000",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/trades/sell",
            json=payload,
            headers={"Authorization": "Bearer valid-test-token"},
        )

    assert response.status_code == 500


def test_sell_route_is_registered():
    """Verify POST /api/v1/trades/sell is registered in the FastAPI application routes."""
    paths = app.openapi()["paths"]
    assert "/api/v1/trades/sell" in paths
    assert "post" in paths["/api/v1/trades/sell"]
