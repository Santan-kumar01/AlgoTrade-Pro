from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from pydantic import ValidationError

from src.schemas import (
    BuyOrderRequest,
    SellOrderRequest,
    TradeResponse,
    TradeType,
)
from src.schemas.trading import (
    BuyOrderRequest as DirectBuyOrderRequest,
    SellOrderRequest as DirectSellOrderRequest,
    TradeResponse as DirectTradeResponse,
    TradeType as DirectTradeType,
)


def test_schema_exports():
    """Verify schemas and TradeType can be imported directly and from package."""
    assert BuyOrderRequest is DirectBuyOrderRequest
    assert SellOrderRequest is DirectSellOrderRequest
    assert TradeResponse is DirectTradeResponse
    assert TradeType is DirectTradeType


def test_trade_type_enum_values():
    """Verify TradeType enum definition and values."""
    assert TradeType.BUY == "BUY"
    assert TradeType.SELL == "SELL"
    assert issubclass(TradeType, str)
    assert len(TradeType) == 2


def test_buy_order_request_instantiation_with_typed_values():
    """Verify BuyOrderRequest instantiates with Python UUID and Decimal."""
    asset_id = uuid.uuid4()
    quantity = Decimal("10.50000000")
    price = Decimal("150.25000000")

    order = BuyOrderRequest(
        asset_id=asset_id,
        quantity=quantity,
        price=price,
    )

    assert order.asset_id == asset_id
    assert order.quantity == quantity
    assert order.price == price
    assert isinstance(order.asset_id, uuid.UUID)
    assert isinstance(order.quantity, Decimal)
    assert isinstance(order.price, Decimal)


def test_buy_order_request_parsing_from_strings():
    """Verify BuyOrderRequest parses valid string representations in Pydantic v2."""
    raw_uuid = "e888d455-7b4c-4e89-9a1b-123456789abc"
    order = BuyOrderRequest(
        asset_id=raw_uuid,
        quantity="5.12500000",
        price="250.75000000",
    )

    assert order.asset_id == uuid.UUID(raw_uuid)
    assert order.quantity == Decimal("5.12500000")
    assert order.price == Decimal("250.75000000")


def test_buy_order_request_rejects_invalid_uuid():
    """Verify BuyOrderRequest raises ValidationError for invalid UUID format."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id="not-a-valid-uuid",
            quantity=Decimal("10"),
            price=Decimal("100"),
        )


def test_buy_order_request_rejects_invalid_decimal():
    """Verify BuyOrderRequest raises ValidationError for unparseable decimal values."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity="invalid_number",
            price=Decimal("100"),
        )


def test_sell_order_request_instantiation_with_typed_values():
    """Verify SellOrderRequest instantiates with Python UUID and Decimal."""
    asset_id = uuid.uuid4()
    quantity = Decimal("3.00000000")
    price = Decimal("175.50000000")

    order = SellOrderRequest(
        asset_id=asset_id,
        quantity=quantity,
        price=price,
    )

    assert order.asset_id == asset_id
    assert order.quantity == quantity
    assert order.price == price
    assert isinstance(order.asset_id, uuid.UUID)
    assert isinstance(order.quantity, Decimal)
    assert isinstance(order.price, Decimal)


def test_sell_order_request_parsing_from_strings():
    """Verify SellOrderRequest parses valid string representations in Pydantic v2."""
    raw_uuid = "12345678-1234-5678-1234-567812345678"
    order = SellOrderRequest(
        asset_id=raw_uuid,
        quantity="12.00000000",
        price="320.10000000",
    )

    assert order.asset_id == uuid.UUID(raw_uuid)
    assert order.quantity == Decimal("12.00000000")
    assert order.price == Decimal("320.10000000")


def test_sell_order_request_rejects_invalid_uuid():
    """Verify SellOrderRequest raises ValidationError for invalid UUID format."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id="invalid-uuid-string",
            quantity=Decimal("5"),
            price=Decimal("50"),
        )


def test_sell_order_request_rejects_invalid_decimal():
    """Verify SellOrderRequest raises ValidationError for unparseable decimal values."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("5"),
            price="not_a_price",
        )


def test_schemas_are_separate_classes():
    """Verify BuyOrderRequest and SellOrderRequest are separate, distinct classes."""
    assert BuyOrderRequest is not SellOrderRequest
    buy_order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1"),
        price=Decimal("1"),
    )
    sell_order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1"),
        price=Decimal("1"),
    )
    assert type(buy_order) is not type(sell_order)


def test_trade_response_export():
    """Verify TradeResponse can be imported directly and from package."""
    assert TradeResponse is DirectTradeResponse


def test_trade_response_instantiation_with_typed_values():
    """Verify TradeResponse instantiates with typed UUID, Decimal, and datetime."""
    tx_id = uuid.uuid4()
    wallet_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    response = TradeResponse(
        id=tx_id,
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type=TradeType.BUY,
        quantity=Decimal("10.00000000"),
        price=Decimal("150.50000000"),
        total_amount=Decimal("1505.00000000"),
        created_at=now,
    )

    assert response.id == tx_id
    assert response.wallet_id == wallet_id
    assert response.asset_id == asset_id
    assert response.transaction_type == TradeType.BUY
    assert response.transaction_type == "BUY"
    assert response.quantity == Decimal("10.00000000")
    assert response.price == Decimal("150.50000000")
    assert response.total_amount == Decimal("1505.00000000")
    assert response.created_at == now


def test_trade_response_accepts_trade_type_enums():
    """Verify TradeResponse accepts TradeType.BUY and TradeType.SELL."""
    tx_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    buy_resp = TradeResponse(
        id=tx_id,
        wallet_id=tx_id,
        asset_id=tx_id,
        transaction_type=TradeType.BUY,
        quantity=Decimal("10.00000000"),
        price=Decimal("100.00000000"),
        total_amount=Decimal("1000.00000000"),
        created_at=now,
    )
    assert buy_resp.transaction_type is TradeType.BUY
    assert buy_resp.transaction_type == "BUY"

    sell_resp = TradeResponse(
        id=tx_id,
        wallet_id=tx_id,
        asset_id=tx_id,
        transaction_type=TradeType.SELL,
        quantity=Decimal("5.00000000"),
        price=Decimal("200.00000000"),
        total_amount=Decimal("1000.00000000"),
        created_at=now,
    )
    assert sell_resp.transaction_type is TradeType.SELL
    assert sell_resp.transaction_type == "SELL"


def test_trade_response_parsing_from_strings():
    """Verify TradeResponse parses valid string representations in Pydantic v2."""
    raw_id = "11111111-1111-1111-1111-111111111111"
    raw_wallet_id = "22222222-2222-2222-2222-222222222222"
    raw_asset_id = "33333333-3333-3333-3333-333333333333"
    raw_created_at = "2026-11-14T20:00:00Z"

    response = TradeResponse(
        id=raw_id,
        wallet_id=raw_wallet_id,
        asset_id=raw_asset_id,
        transaction_type="SELL",
        quantity="5.50000000",
        price="200.00000000",
        total_amount="1100.00000000",
        created_at=raw_created_at,
    )

    assert response.id == uuid.UUID(raw_id)
    assert response.wallet_id == uuid.UUID(raw_wallet_id)
    assert response.asset_id == uuid.UUID(raw_asset_id)
    assert response.transaction_type == TradeType.SELL
    assert response.transaction_type == "SELL"
    assert response.quantity == Decimal("5.50000000")
    assert response.price == Decimal("200.00000000")
    assert response.total_amount == Decimal("1100.00000000")
    assert isinstance(response.created_at, datetime)


def test_trade_response_rejects_unsupported_transaction_type():
    """Verify TradeResponse rejects unsupported transaction types like HOLD."""
    tx_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        TradeResponse(
            id=tx_id,
            wallet_id=tx_id,
            asset_id=tx_id,
            transaction_type="HOLD",
            quantity=Decimal("1.00000000"),
            price=Decimal("100.00000000"),
            total_amount=Decimal("100.00000000"),
            created_at=now,
        )

    with pytest.raises(ValidationError):
        TradeResponse(
            id=tx_id,
            wallet_id=tx_id,
            asset_id=tx_id,
            transaction_type="INVALID",
            quantity=Decimal("1.00000000"),
            price=Decimal("100.00000000"),
            total_amount=Decimal("100.00000000"),
            created_at=now,
        )


def test_trade_response_from_orm_attributes():
    """Verify TradeResponse validates directly from an ORM-like object via from_attributes."""
    class MockTransaction:
        id = uuid.uuid4()
        wallet_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        transaction_type = "BUY"
        quantity = Decimal("2.00000000")
        price = Decimal("100.00000000")
        total_amount = Decimal("200.00000000")
        created_at = datetime.now(timezone.utc)

    mock_tx = MockTransaction()
    response = TradeResponse.model_validate(mock_tx)

    assert response.id == mock_tx.id
    assert response.wallet_id == mock_tx.wallet_id
    assert response.asset_id == mock_tx.asset_id
    assert response.transaction_type == TradeType.BUY
    assert response.transaction_type == "BUY"
    assert response.quantity == Decimal("2.00000000")
    assert response.price == Decimal("100.00000000")
    assert response.total_amount == Decimal("200.00000000")
    assert response.created_at == mock_tx.created_at


def test_trade_response_rejects_invalid_types():
    """Verify TradeResponse raises ValidationError on malformed input data."""
    valid_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        TradeResponse(
            id="bad-uuid",
            wallet_id=valid_id,
            asset_id=valid_id,
            transaction_type="BUY",
            quantity=Decimal("1"),
            price=Decimal("1"),
            total_amount=Decimal("1"),
            created_at=now,
        )

    with pytest.raises(ValidationError):
        TradeResponse(
            id=valid_id,
            wallet_id=valid_id,
            asset_id=valid_id,
            transaction_type="BUY",
            quantity="not-a-decimal",
            price=Decimal("1"),
            total_amount=Decimal("1"),
            created_at=now,
        )

    with pytest.raises(ValidationError):
        TradeResponse(
            id=valid_id,
            wallet_id=valid_id,
            asset_id=valid_id,
            transaction_type="BUY",
            quantity=Decimal("1"),
            price=Decimal("1"),
            total_amount=Decimal("1"),
            created_at="not-a-datetime",
        )
