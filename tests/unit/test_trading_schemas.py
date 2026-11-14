from decimal import Decimal
import uuid
import pytest
from pydantic import ValidationError

from src.schemas import BuyOrderRequest, SellOrderRequest
from src.schemas.trading import (
    BuyOrderRequest as DirectBuyOrderRequest,
    SellOrderRequest as DirectSellOrderRequest,
)


def test_schema_exports():
    """Verify BuyOrderRequest and SellOrderRequest can be imported directly and from package."""
    assert BuyOrderRequest is DirectBuyOrderRequest
    assert SellOrderRequest is DirectSellOrderRequest


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
