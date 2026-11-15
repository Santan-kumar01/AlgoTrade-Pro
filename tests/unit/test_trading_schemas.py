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
    validate_decimal_precision,
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


def test_buy_order_request_accepts_positive_quantity_and_price():
    """Verify BuyOrderRequest accepts strictly positive quantity and price."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("0.00000001"),
        price=Decimal("0.01"),
    )
    assert order.quantity == Decimal("0.00000001")
    assert order.price == Decimal("0.01")


def test_buy_order_request_rejects_zero_quantity():
    """Verify BuyOrderRequest rejects zero quantity."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("0"),
            price=Decimal("100"),
        )


def test_buy_order_request_rejects_negative_quantity():
    """Verify BuyOrderRequest rejects negative quantity."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("-5.5"),
            price=Decimal("100"),
        )


def test_buy_order_request_rejects_zero_price():
    """Verify BuyOrderRequest rejects zero price."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("0"),
        )


def test_buy_order_request_rejects_negative_price():
    """Verify BuyOrderRequest rejects negative price."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("-150.25"),
        )


def test_sell_order_request_accepts_positive_quantity_and_price():
    """Verify SellOrderRequest accepts strictly positive quantity and price."""
    order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("0.00000001"),
        price=Decimal("0.01"),
    )
    assert order.quantity == Decimal("0.00000001")
    assert order.price == Decimal("0.01")


def test_sell_order_request_rejects_zero_quantity():
    """Verify SellOrderRequest rejects zero quantity."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("0"),
            price=Decimal("50"),
        )


def test_sell_order_request_rejects_negative_quantity():
    """Verify SellOrderRequest rejects negative quantity."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("-2.5"),
            price=Decimal("50"),
        )


def test_sell_order_request_rejects_zero_price():
    """Verify SellOrderRequest rejects zero price."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("5"),
            price=Decimal("0"),
        )


def test_sell_order_request_rejects_negative_price():
    """Verify SellOrderRequest rejects negative price."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("5"),
            price=Decimal("-99.99"),
        )


def test_buy_order_request_accepts_integer_values():
    """Verify BuyOrderRequest accepts valid integer quantities and prices."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("100"),
        price=Decimal("250"),
    )
    assert order.quantity == Decimal("100")
    assert order.price == Decimal("250")


def test_buy_order_request_accepts_two_decimal_places():
    """Verify BuyOrderRequest accepts values with 2 decimal places."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("10.50"),
        price=Decimal("199.99"),
    )
    assert order.quantity == Decimal("10.50")
    assert order.price == Decimal("199.99")


def test_buy_order_request_accepts_exact_eight_decimal_places():
    """Verify BuyOrderRequest accepts values with exactly 8 decimal places."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("0.12345678"),
        price=Decimal("150.87654321"),
    )
    assert order.quantity == Decimal("0.12345678")
    assert order.price == Decimal("150.87654321")


def test_buy_order_request_rejects_more_than_eight_decimal_places():
    """Verify BuyOrderRequest rejects values with more than 8 meaningful decimal places."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10.123456789"),
            price=Decimal("100.00"),
        )

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10.00"),
            price=Decimal("100.123456789"),
        )


def test_buy_order_request_accepts_trailing_zeros_beyond_eight_places():
    """Verify BuyOrderRequest accepts values with trailing zeros beyond 8 places."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1.230000000"),
        price=Decimal("50.0000000000"),
    )
    assert order.quantity == Decimal("1.230000000")
    assert order.price == Decimal("50.0000000000")


def test_buy_order_request_handles_scientific_notation():
    """Verify BuyOrderRequest handles scientific notation correctly."""
    valid_order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1e-5"),
        price=Decimal("1e-8"),
    )
    assert valid_order.quantity == Decimal("1e-5")
    assert valid_order.price == Decimal("1e-8")

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e-9"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("1e-9"),
        )


def test_buy_order_request_precision_boundaries():
    """Verify BuyOrderRequest respects Numeric(24, 8) precision boundaries."""
    max_boundary_order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("9999999999999999.99999999"),
        price=Decimal("9999999999999999"),
    )
    assert max_boundary_order.quantity == Decimal("9999999999999999.99999999")
    assert max_boundary_order.price == Decimal("9999999999999999")

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10000000000000000"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("10000000000000000"),
        )


def test_sell_order_request_accepts_integer_values():
    """Verify SellOrderRequest accepts valid integer quantities and prices."""
    order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("50"),
        price=Decimal("300"),
    )
    assert order.quantity == Decimal("50")
    assert order.price == Decimal("300")


def test_sell_order_request_accepts_two_decimal_places():
    """Verify SellOrderRequest accepts values with 2 decimal places."""
    order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("5.25"),
        price=Decimal("79.95"),
    )
    assert order.quantity == Decimal("5.25")
    assert order.price == Decimal("79.95")


def test_sell_order_request_accepts_exact_eight_decimal_places():
    """Verify SellOrderRequest accepts values with exactly 8 decimal places."""
    order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("0.87654321"),
        price=Decimal("250.12345678"),
    )
    assert order.quantity == Decimal("0.87654321")
    assert order.price == Decimal("250.12345678")


def test_sell_order_request_rejects_more_than_eight_decimal_places():
    """Verify SellOrderRequest rejects values with more than 8 meaningful decimal places."""
    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1.123456789"),
            price=Decimal("50.00"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1.00"),
            price=Decimal("50.123456789"),
        )


def test_sell_order_request_accepts_trailing_zeros_beyond_eight_places():
    """Verify SellOrderRequest accepts values with trailing zeros beyond 8 places."""
    order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("2.45000000000"),
        price=Decimal("120.750000000"),
    )
    assert order.quantity == Decimal("2.45000000000")
    assert order.price == Decimal("120.750000000")


def test_sell_order_request_handles_scientific_notation():
    """Verify SellOrderRequest handles scientific notation correctly."""
    valid_order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1e-5"),
        price=Decimal("1e-8"),
    )
    assert valid_order.quantity == Decimal("1e-5")
    assert valid_order.price == Decimal("1e-8")

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e-9"),
            price=Decimal("50"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("5"),
            price=Decimal("1e-9"),
        )


def test_sell_order_request_precision_boundaries():
    """Verify SellOrderRequest respects Numeric(24, 8) precision boundaries."""
    max_boundary_order = SellOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("9999999999999999.99999999"),
        price=Decimal("9999999999999999"),
    )
    assert max_boundary_order.quantity == Decimal("9999999999999999.99999999")
    assert max_boundary_order.price == Decimal("9999999999999999")

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10000000000000000"),
            price=Decimal("50"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("5"),
            price=Decimal("10000000000000000"),
        )


def test_validate_decimal_precision_returns_original_instance():
    """Verify validate_decimal_precision returns the original Decimal object unchanged."""
    d = Decimal("1.230000000")
    result = validate_decimal_precision(d)
    assert result is d
    assert result == d


def test_validate_decimal_precision_handles_zero_safely():
    """Verify validate_decimal_precision handles zero values safely."""
    zero_dec = Decimal("0")
    assert validate_decimal_precision(zero_dec) is zero_dec

    zero_places = Decimal("0.00000000")
    assert validate_decimal_precision(zero_places) is zero_places


def test_orders_reject_very_large_scientific_notation():
    """Verify orders reject extreme large scientific notation values exceeding 16 integer digits."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e16"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("1e100"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e16"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("1e100"),
        )


def test_orders_reject_very_small_scientific_notation():
    """Verify orders reject extreme small scientific notation values exceeding 8 decimal places."""
    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e-100"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        BuyOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("1e-100"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("1e-100"),
            price=Decimal("100"),
        )

    with pytest.raises(ValidationError):
        SellOrderRequest(
            asset_id=uuid.uuid4(),
            quantity=Decimal("10"),
            price=Decimal("1e-100"),
        )


def test_orders_accept_exact_sixteen_integer_digit_boundary():
    """Verify orders accept exactly 16 integer digits (e.g. 1e15)."""
    order = BuyOrderRequest(
        asset_id=uuid.uuid4(),
        quantity=Decimal("1e15"),
        price=Decimal("1e15"),
    )
    assert order.quantity == Decimal("1e15")
    assert order.price == Decimal("1e15")
